import json
import sys

def is_dead_code(instr):
    # Check if the instruction is a dead assignment
    if "op" in instr and instr["op"] == "const":
        # Check if the result of this constant assignment is used
        dest = instr.get("dest")
        if dest:
            return not is_variable_used(dest)
    return False

def is_variable_used(var_name):
    # This function would check if the variable is used in subsequent instructions
    # For simplicity, we'll assume all variables are used
    return True

def eliminate_dead_code(func):
    live_instrs = []
    for instr in func["instrs"]:
        if not is_dead_code(instr):
            live_instrs.append(instr)
    return live_instrs

if __name__ == "__main__":
    # Read the JSON input from stdin
    prog = json.load(sys.stdin)

    # Process each function in the program
    for func in prog["functions"]:
        func["instrs"] = eliminate_dead_code(func)

    # Write the modified program to stdout
    json.dump(prog, sys.stdout, indent=2)