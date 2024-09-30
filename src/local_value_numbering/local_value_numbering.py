import json
import sys

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

if __name__ == "__main__":
    program = json.load(sys.stdin)
    for function in program["functions"]:
        optimized_instructions = []
        current_block = []
        for instruction in function["instrs"]:
            if "op" in instruction:
                current_block.append(instruction)
                if instruction["op"] in ["br", "jmp", "ret"]:
                    optimized_instructions += local_value_numbering(current_block)
                    current_block = []
            else:
                optimized_instructions += local_value_numbering(current_block)
                current_block = []
                optimized_instructions.append(instruction)
        optimized_instructions += local_value_numbering(current_block)
        function["instrs"] = optimized_instructions

    json.dump(program, sys.stdout, indent=2)
