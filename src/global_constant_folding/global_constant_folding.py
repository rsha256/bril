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
            # Ensure the last instruction has 'labels' for branch targets
            if 'labels' in last_instr:
                succs[i] = [j for j, b in enumerate(blocks) if b[0].get('label') in last_instr['labels']]
        elif 'op' in last_instr and last_instr['op'] == 'jmp':
            # Ensure 'labels' exist for jmp targets
            if 'labels' in last_instr:
                succs[i] = [j for j, b in enumerate(blocks) if b[0].get('label') == last_instr['labels'][0]]
        else:
            if i + 1 < len(blocks):
                succs[i] = [i + 1]
        # Add predecessors
        for s in succs[i]:
            preds[s].add(i)

    return preds, succs

def meet(in_sets):
    """Perform the meet operation for constants (intersection of known constants)."""
    if not in_sets:
        return {}
    result = in_sets[0].copy()
    for in_set in in_sets[1:]:
        for var in list(result):
            if var not in in_set or result[var] != in_set[var]:
                del result[var]
    return result

def evaluate_expression(instr, constants):
    try:
        if instr["op"] == "add":
            return constants[instr["args"][0]] + constants[instr["args"][1]]
        elif instr["op"] == "sub":
            return constants[instr["args"][0]] - constants[instr["args"][1]]
        elif instr["op"] == "mul":
            return constants[instr["args"][0]] * constants[instr["args"][1]]
        elif instr["op"] == "div" and constants[instr["args"][1]] != 0:
            return constants[instr["args"][0]] // constants[instr["args"][1]]
        elif instr["op"] == "const":
            return instr["value"]
    except KeyError:
        pass
    return None

def propagate_constants_in_block(block, in_constants):
    out_constants = in_constants.copy()
    new_instrs = []

    for instr in block:
        if instr.get("op") == "const":
            out_constants[instr["dest"]] = instr["value"]
            new_instrs.append(instr)
        elif "args" in instr:
            if all(arg in out_constants for arg in instr["args"]):
                result = evaluate_expression(instr, out_constants)
                if result is not None:
                    new_instrs.append({"op": "const", "dest": instr["dest"], "type": instr["type"], "value": result})
                    out_constants[instr["dest"]] = result
                else:
                    new_instrs.append(instr)
            else:
                new_instrs.append(instr)
        else:
            new_instrs.append(instr)

        # Handle 'mov' instructions
        if instr.get("op") == "mov" and instr["args"][0] in out_constants:
            out_constants[instr["dest"]] = out_constants[instr["args"][0]]

    return new_instrs, out_constants

def constant_propagation_and_folding(prog):
    for fn in prog["functions"]:
        blocks = list(form_blocks(fn["instrs"]))
        preds, succs = predecessors_and_successors(blocks)

        # Initialize in/out sets for each block
        in_sets = [defaultdict(lambda: None) for _ in blocks]
        out_sets = [defaultdict(lambda: None) for _ in blocks]
        worklist = deque(range(len(blocks)))

        while worklist:
            b = worklist.pop()
            # Compute in[b] as the meet of out[predecessors]
            if preds[b]:
                in_sets[b] = meet([out_sets[p] for p in preds[b]])

            # Propagate constants within the block
            new_block, out_constants = propagate_constants_in_block(blocks[b], in_sets[b])

            if out_sets[b] != out_constants:
                out_sets[b] = out_constants
                worklist.extend(succs[b])

            blocks[b] = new_block

        # Replace the function instructions with the optimized blocks
        fn["instrs"] = [instr for block in blocks for instr in block]

def should_keep(instr, used_vars):
    # Labels and instructions without 'dest' are kept
    if 'op' not in instr or 'dest' not in instr:
        return True
    # Keep the instruction if its destination variable is used
    return instr['dest'] in used_vars

if __name__ == "__main__":
    prog = json.load(sys.stdin)
    constant_propagation_and_folding(prog)
    # Now do dead code elimination
    for fn in prog["functions"]:
        # Collect all variables that are used
        used_vars = set()
        for instr in fn["instrs"]:
            args = instr.get("args", [])
            used_vars.update(args)
        # Keep instructions whose destination variables are used
        fn["instrs"] = [instr for instr in fn["instrs"] if should_keep(instr, used_vars)]
    json.dump(prog, sys.stdout, indent=2)
