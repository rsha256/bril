import json
import sys
from collections import defaultdict, deque

TERMINATORS = ('br', 'jmp', 'ret')

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
            else:
                in_sets[b] = {}

            # Propagate constants within the block
            new_block, out_constants = propagate_constants_in_block(blocks[b], in_sets[b])

            if out_sets[b] != out_constants:
                out_sets[b] = out_constants
                worklist.extend(succs[b])

            blocks[b] = new_block

        # Replace the function instructions with the optimized blocks
        fn["instrs"] = [instr for block in blocks for instr in block]

def local_value_numbering(instructions):
    value_to_number = {}
    number_to_value = {}
    variable_to_number = {}
    number_to_variable = {}
    counter = 0

    for instruction in instructions:
        if "dest" not in instruction:
            continue
        if not isinstance(instruction["type"], str):
            continue

        # Handle non-arithmetic or logic operations
        if instruction["op"] not in ["add", "mul", "sub", "div", "eq", "lt", "gt", "le", "ge", "not", "and", "or", "id"]:
            counter += 1
            number = counter
            number_to_value[number] = None
        else:
            # Collect argument values and perform value numbering
            arguments = []
            if "args" in instruction:
                for idx, argument in enumerate(instruction["args"]):
                    argument_number = variable_to_number.get(argument)
                    if argument_number is None:
                        arguments.append(argument)
                    else:
                        if number_to_variable[argument_number][0] != argument:
                            instruction["args"][idx] = number_to_variable[argument_number][0]
                        arguments.append(f"#.{argument_number}")
            if instruction["op"] in ["add", "mul"]:
                arguments.sort()
            if instruction["op"] == "const":
                value_repr = f"const {instruction['value']}"
            else:
                value_repr = f"{instruction['op']}{instruction['type']}{arguments}"

            if instruction["op"] == "id":
                number = variable_to_number.get(instruction["args"][0])
            else:
                number = value_to_number.get(value_repr)

            if number is None:
                counter += 1
                number = counter
                value_to_number[value_repr] = number
                number_to_value[number] = value_repr
            else:
                instruction["op"] = "id"
                instruction["args"] = [number_to_variable[number][0]]
                instruction.pop("funcs", None)

        # Remove the old number for the destination variable if it exists
        if instruction["dest"] in variable_to_number:
            old_number = variable_to_number[instruction["dest"]]
            number_to_variable[old_number].remove(instruction["dest"])
            if len(number_to_variable[old_number]) == 0:
                old_value = number_to_value.get(old_number)
                if old_value is not None:
                    value_to_number.pop(old_value)
                number_to_value.pop(old_number)

        # Update mappings for the current destination
        variable_to_number[instruction["dest"]] = number
        if number not in number_to_variable:
            number_to_variable[number] = [instruction["dest"]]
        else:
            number_to_variable[number].append(instruction["dest"])

    return instructions

def apply_lvn(prog):
    for function in prog["functions"]:
        optimized_instructions = []
        current_block = []
        for instruction in function["instrs"]:
            if "op" in instruction:
                current_block.append(instruction)
                if instruction["op"] in TERMINATORS:
                    optimized_instructions += local_value_numbering(current_block)
                    current_block = []
            else:
                optimized_instructions += local_value_numbering(current_block)
                current_block = []
                optimized_instructions.append(instruction)
        optimized_instructions += local_value_numbering(current_block)
        function["instrs"] = optimized_instructions

def should_keep(instr, used_vars):
    # Labels and instructions without 'dest' are kept
    if 'op' not in instr or 'dest' not in instr:
        return True
    # Keep the instruction if its destination variable is used
    return instr['dest'] in used_vars

def liveness_analysis(prog):
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
            out_sets[b] = set()
            for succ in succs[b]:
                out_sets[b].update(in_sets[succ])

            # Compute in[b] = use[b] ∪ (out[b] - def[b])
            use = set()
            defs = set()
            for instr in blocks[b]:
                if 'args' in instr:
                    use.update(instr['args'])
                if 'dest' in instr:
                    defs.add(instr['dest'])
            in_set = use.union(out_sets[b] - defs)

            if in_sets[b] != in_set:
                in_sets[b] = in_set
                worklist.extend(preds[b])

        # Dead Code Elimination based on liveness
        for i, block in enumerate(blocks):
            kept = []
            used = set(out_sets[i])
            for instr in reversed(block):
                if "dest" not in instr:
                    kept.append(instr)
                elif instr["dest"] in used:
                    kept.append(instr)
                # Update the used set with the arguments of the instruction
                if "args" in instr:
                    used.update(instr["args"])
            blocks[i] = kept[::-1]

        # Replace the function instructions with the optimized blocks
        fn["instrs"] = [instr for block in blocks for instr in block]

if __name__ == "__main__":
    prog = json.load(sys.stdin)
    
    # Step 1: Constant Propagation and Folding
    constant_propagation_and_folding(prog)
    
    # Step 2: Local Value Numbering (LVN)
    apply_lvn(prog)
    
    # Step 3: Liveness Analysis and Dead Code Elimination
    liveness_analysis(prog)
    
    json.dump(prog, sys.stdout, indent=2)
