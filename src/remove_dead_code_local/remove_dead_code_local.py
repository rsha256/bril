import json
import sys

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
    prog = json.load(sys.stdin)

    used_vars = get_used_variables(prog)
    last_definition = track_last_definition(prog)
    # Now we eliminate both dead code and redundant redefinitions
    for fn in prog["functions"]:
        fn["instrs"] = [
            instr for instr in fn["instrs"] 
            if should_keep(instr, used_vars, last_definition)
        ]

    json.dump(prog, sys.stdout, indent=2)
