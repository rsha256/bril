import json
import sys
from collections import defaultdict, deque

TERMINATORS = ('br', 'jmp', 'ret')
MEANINGFUL_OPS = {'ret', 'br', 'jmp', 'call', 'print', 'input'}

def form_blocks(instrs):
    """
    Divide instructions into basic blocks.
    A new block starts at a label or after a terminator instruction.
    """
    blocks = []
    current_block = []
    for instr in instrs:
        if 'op' in instr:
            current_block.append(instr)
            if instr['op'] in TERMINATORS:
                blocks.append(current_block)
                current_block = []
        else:
            # It's a label
            if current_block:
                blocks.append(current_block)
            current_block = [instr]
    if current_block:
        blocks.append(current_block)
    return blocks

def predecessors_and_successors(blocks):
    """
    Compute predecessors and successors for each block.
    """
    preds = defaultdict(set)
    succs = defaultdict(list)
    
    # Map labels to block indices
    label_to_block = {}
    for i, block in enumerate(blocks):
        if 'label' in block[0]:
            label_to_block[block[0]['label']] = i
    
    for i, block in enumerate(blocks):
        last_instr = block[-1]
        if 'op' in last_instr:
            op = last_instr['op']
            if op == 'br':
                # Branch with condition
                labels = last_instr.get('labels', [])
                args = last_instr.get('args', [])
                if len(labels) == 2:
                    # Conditional branch
                    target_true = label_to_block.get(labels[0])
                    target_false = label_to_block.get(labels[1])
                    if target_true is not None:
                        succs[i].append(target_true)
                        preds[target_true].add(i)
                    if target_false is not None:
                        succs[i].append(target_false)
                        preds[target_false].add(i)
            elif op == 'jmp':
                # Unconditional jump
                labels = last_instr.get('labels', [])
                if labels:
                    target = label_to_block.get(labels[0])
                    if target is not None:
                        succs[i].append(target)
                        preds[target].add(i)
            elif op == 'ret':
                # Return has no successors
                pass
            else:
                # Other operations fall through to the next block
                if i + 1 < len(blocks):
                    succs[i].append(i + 1)
                    preds[i + 1].add(i)
        else:
            # If the block doesn't end with an instruction, assume fall-through
            if i + 1 < len(blocks):
                succs[i].append(i + 1)
                preds[i + 1].add(i)
    
    return preds, succs

def compute_use_def(block, meaningful_ops):
    """
    Compute the use and def sets for a block based on meaningful operations.
    Includes dependencies to ensure variables used to compute live variables are marked as live.
    """
    use = set()
    defs = set()
    
    # Initial pass: identify variables used in meaningful operations and definitions
    for instr in block:
        op = instr.get('op')
        if op in meaningful_ops:
            args = instr.get('args', [])
            for arg in args:
                if arg not in defs:
                    use.add(arg)
            dest = instr.get('dest')
            if dest:
                defs.add(dest)
    
    # Iterate to include dependencies: variables used to compute variables in 'use'
    added = True
    while added:
        added = False
        for instr in block:
            dest = instr.get('dest')
            if dest and dest in use:
                args = instr.get('args', [])
                for arg in args:
                    if arg not in use and arg not in defs:
                        use.add(arg)
                        added = True
    return use, defs

def strong_liveness_analysis(prog):
    for fn in prog["functions"]:
        blocks = form_blocks(fn["instrs"])
        preds, succs = predecessors_and_successors(blocks)
        
        # Compute use and def for each block based on meaningful operations and dependencies
        use = []
        defs = []
        for block in blocks:
            u, d = compute_use_def(block, MEANINGFUL_OPS)
            use.append(u)
            defs.append(d)
        
        # Initialize in and out sets
        in_sets = [set() for _ in blocks]
        out_sets = [set() for _ in blocks]
        
        # Worklist algorithm for data-flow analysis
        worklist = deque(range(len(blocks)))
        
        while worklist:
            b = worklist.pop()
            # Save current out set
            old_out = out_sets[b].copy()
            
            # out[b] = union of in[s] for all successors s of b
            new_out = set()
            for s in succs[b]:
                new_out |= in_sets[s]
            out_sets[b] = new_out
            
            # in[b] = use[b] ∪ (out[b] - def[b])
            new_in = use[b] | (out_sets[b] - defs[b])
            if new_in != in_sets[b]:
                in_sets[b] = new_in
                # Add predecessors to the worklist
                for p in preds[b]:
                    worklist.append(p)
        
        # Dead Code Elimination based on strong liveness
        optimized_blocks = []
        for i, block in enumerate(blocks):
            live = out_sets[i].copy()
            kept = []
            # Iterate backwards through the block
            for instr in reversed(block):
                op = instr.get('op')
                dest = instr.get('dest')
                args = instr.get('args', [])
                
                if op in MEANINGFUL_OPS:
                    kept.append(instr)
                    # Add args to live
                    live |= set(args)
                elif dest:
                    if dest in live:
                        kept.append(instr)
                        # Remove dest from live and add args to live
                        live.remove(dest)
                        live |= set(args)
                    else:
                        # Instruction defines a variable that's not live; eliminate it
                        pass
                else:
                    # Instructions without dest (e.g., labels) are kept
                    kept.append(instr)
                    live |= set(args)
            # Reverse to maintain original order
            optimized_blocks.append(list(reversed(kept)))
        
        # Flatten the optimized blocks back into the function's instruction list
        optimized_instrs = []
        for block in optimized_blocks:
            optimized_instrs.extend(block)
        
        fn["instrs"] = optimized_instrs

if __name__ == "__main__":
    prog = json.load(sys.stdin)
    strong_liveness_analysis(prog)
    # apply_lvn(prog)
    json.dump(prog, sys.stdout, indent=2)
