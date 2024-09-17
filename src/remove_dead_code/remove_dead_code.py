import json
import sys

# Check if the instruction has side effects
def is_pure(instr):
    if "op" not in instr:  # Labels are not pure instructions.
        return False
    return instr["op"] not in ["print", "store", "call", "free", "br", "jmp", "ret"]

def should_keep(instr, used_vars):
    # If there is no 'op', it's likely a label, which should be kept.
    if "op" not in instr:
        return True
    
    if instr["op"] == "nop":
        return False

    # Only check 'dest' if it exists in the instruction
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

if __name__ == "__main__":
    prog = json.load(sys.stdin)

    used_vars = get_used_variables(prog)
    for fn in prog["functions"]:
        fn["instrs"] = [instr for instr in fn["instrs"] if should_keep(instr, used_vars)]

    json.dump(prog, sys.stdout, indent=2)
