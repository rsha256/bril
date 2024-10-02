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
    if not in_sets:
        return set()
    result = set(in_sets[0])
    for in_set in in_sets[1:]:
        result.update(in_set)
    return result

def transfer(block, out_set):
    kills = set()
    gens = set()

    for instr in reversed(block):
        if "dest" in instr:
            kills.add(instr["dest"])
        gens.update(arg for arg in instr.get("args", []))

    out = gens | (set(out_set) - kills)
    
    return block, out

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
            out_sets[b] = meet([in_sets[succ] for succ in succs[b]])

            # Propagate constants within the block
            new_block, in_set = transfer(blocks[b], out_sets[b])

            if in_sets[b] != in_set:
                in_sets[b] = in_set
                worklist.extend(preds[b])


            blocks[b] = new_block

        for i in range(len(blocks)):
            kept = []
            used = set()
            for instr in reversed(blocks[i]):
                if "dest" not in instr:
                    kept.append(instr)
                if "dest" in instr and (instr["dest"] in out_sets[i] or instr["dest"] in used):
                    kept.append(instr)
                used.update(instr.get("args", []))
            blocks[i] = kept[::-1]
    
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

if __name__ == "__main__":
    prog = json.load(sys.stdin)
    apply_lvn(prog)
    liveness_analysis(prog)
    json.dump(prog, sys.stdout, indent=2)
