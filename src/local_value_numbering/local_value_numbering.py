import json
import sys

# Helper function to canonicalize commutative operations
def canonicalize(op, args):
    if op in ["add", "mul", "eq"]:
        return tuple(sorted(args))
    return tuple(args)

# LVN table structures
val2var = {}          # Maps value tuples to representative variables
var_replacement = {}  # Maps variables to their representative variables
next_lvn = 0          # Counter for generating unique lvn.x variable names

# Perform Local Value Numbering (LVN) on a block of instructions
def lvn(block):
    global val2var, var_replacement, next_lvn

    new_instrs = []

    for instr in block:
        # Replace arguments with their representative variables
        if "args" in instr:
            new_args = [var_replacement.get(arg, arg) for arg in instr["args"]]
        else:
            new_args = []

        if "dest" in instr:
            op = instr["op"]

            if op == "const":
                value = ("const", instr["value"])

                if value in val2var:
                    # Constant already exists, map 'dest' to existing variable
                    existing_var = val2var[value]
                    var_replacement[instr["dest"]] = existing_var
                    # Do not emit redundant 'const' instruction
                    continue
                else:
                    # New constant, preserve the original variable
                    val2var[value] = instr["dest"]
                    var_replacement[instr["dest"]] = instr["dest"]
                    new_instrs.append(instr)
            else:
                # For non-const operations, canonicalize arguments if necessary
                canonical_args = canonicalize(op, new_args)
                value = (op,) + canonical_args

                if value in val2var:
                    # Expression already exists, map 'dest' to existing variable
                    existing_var = val2var[value]
                    var_replacement[instr["dest"]] = existing_var
                    # Do not emit redundant instruction
                    continue
                else:
                    # New unique expression, assign to a new lvn.x variable
                    lvn_var = f"lvn.{next_lvn}"
                    next_lvn += 1
                    val2var[value] = lvn_var
                    var_replacement[instr["dest"]] = lvn_var

                    # Emit the instruction with 'dest' replaced by 'lvn.x'
                    new_instr = dict(instr)  # Create a shallow copy
                    new_instr["dest"] = lvn_var
                    new_instr["args"] = list(canonical_args)
                    new_instrs.append(new_instr)
        else:
            # Instructions without 'dest' (e.g., 'print')
            # Replace their arguments with representative variables
            new_instr = dict(instr)  # Create a shallow copy
            new_instr["args"] = new_args
            new_instrs.append(new_instr)

    return new_instrs

# Check if the instruction has side effects
def is_pure(instr):
    if "op" not in instr:  # Labels are not pure instructions.
        return False
    return instr["op"] not in ["print", "store", "call", "free", "br", "jmp", "ret"]

def should_keep(instr, used_vars, last_definition):
    # If there is no 'op', it's likely a label, which should be kept.
    if "op" not in instr:
        return True
    
    if instr["op"] == "nop":
        return False

    # Remove instructions that assign to a variable that's immediately overwritten
    if "dest" in instr:
        dest = instr["dest"]
        if dest in last_definition and last_definition[dest] != instr:
            # If the variable is redefined, remove the previous definition.
            return False

    # Only remove if 'dest' isn't used later and the instruction is pure
    if "dest" in instr and instr["dest"] not in used_vars and is_pure(instr):
        return False

    return True

def get_used_variables(prog):
    used_vars = set()
    for fn in prog["functions"]:
        for instr in fn["instrs"]:
            if "args" in instr:
                used_vars.update(instr["args"])
    return used_vars

def track_last_definition(prog):
    last_definition = {}
    for fn in prog["functions"]:
        for instr in fn["instrs"]:
            if "dest" in instr:
                last_definition[instr["dest"]] = instr
    return last_definition

if __name__ == "__main__":
    # Read input from stdin (Bril program in JSON format)
    prog = json.load(sys.stdin)

    # Apply LVN to each function in the program
    for fn in prog.get("functions", []):
        fn["instrs"] = lvn(fn["instrs"])

    # Remove dead code and redundant redefinitions
    used_vars = get_used_variables(prog)
    last_definition = track_last_definition(prog)
    for fn in prog["functions"]:
        fn["instrs"] = [
            instr for instr in fn["instrs"] 
            if should_keep(instr, used_vars, last_definition)
        ]

    # Output the transformed program to stdout
    json.dump(prog, sys.stdout, indent=2)
