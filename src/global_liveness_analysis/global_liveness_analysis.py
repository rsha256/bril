import json
import sys
from collections import defaultdict, deque

TERMINATORS = 'br', 'jmp', 'ret'

def form_blocks(instrs):
    cur_block = []
    for instr in instrs:
        if 'op' in instr:  # It's an instruction.
            cur_block.append(instr)
            if instr['op'] in TERMINATORS:
                yield cur_block
                cur_block = []
        else:  # It's a label.
            if cur_block:
                yield cur_block
            cur_block = [instr]
    if cur_block:
        yield cur_block

def predecessors_and_successors(blocks):
    """Compute predecessors and successors for each block."""
    preds = defaultdict(set)
    succs = defaultdict(list)

    for i, block in enumerate(blocks):
        last_instr = block[-1]
        if 'op' in last_instr and last_instr['op'] == 'br':
            if 'labels' in last_instr:
                succs[i] = [j for j, b in enumerate(blocks) if b[0].get('label') in last_instr['labels']]
        elif 'op' in last_instr and last_instr['op'] == 'jmp':
            if 'labels' in last_instr:
                succs[i] = [j for j, b in enumerate(blocks) if b[0].get('label') == last_instr['labels'][0]]
        else:
            if i + 1 < len(blocks):
                succs[i] = [i + 1]
        for s in succs[i]:
            preds[s].add(i)

    return preds, succs

def meet(in_sets):
    """Perform the meet operation for sets (set union for liveness)."""
    if not in_sets:
        return set()
    result = set(in_sets[0])
    for in_set in in_sets[1:]:
        result.update(in_set)
    return result

def transfer(block, in_set):
    out_set = set(in_set)
    kills = set()
    gens = set()

    for instr in reversed(block):
        if "dest" in instr:
            kills.add(instr["dest"])
        gens.update(arg for arg in instr.get("args", []) if arg not in kills)

    out_set = gens | (set(in_set) - kills)
    
    return block, out_set

def constant_propagation_and_folding(prog):
    for fn in prog["functions"]:
        blocks = list(form_blocks(fn["instrs"]))
        preds, succs = predecessors_and_successors(blocks)

        # Initialize in/out sets for each block
        in_sets = [set() for _ in blocks]
        out_sets = [set() for _ in blocks]
        worklist = deque(range(len(blocks)))

        while worklist:
            b = worklist.pop()
            # Compute out[b] as the meet of in[successors]
            out_sets[b] = meet([in_sets[succ] for succ in succs[b]])

            # Propagate constants within the block
            new_block, out_constants = transfer(blocks[b], out_sets[b])

            if in_sets[b] != out_constants:
                in_sets[b] = out_constants
                worklist.extend(preds[b])

            blocks[b] = new_block

        # Replace the function instructions with the optimized blocks
        fn["instrs"] = [instr for block in blocks for instr in block]

def should_keep(instr, used_vars):
    if 'op' not in instr or 'dest' not in instr:
        return True
    return instr['dest'] in used_vars

if __name__ == "__main__":
    prog = json.load(sys.stdin)
    constant_propagation_and_folding(prog)
    
    # Dead code elimination
    for fn in prog["functions"]:
        used_vars = set()
        for instr in fn["instrs"]:
            args = instr.get("args", [])
            used_vars.update(args)
        fn["instrs"] = [instr for instr in fn["instrs"] if should_keep(instr, used_vars)]
    
    json.dump(prog, sys.stdout, indent=2)
