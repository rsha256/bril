import json
import sys

def should_keep(instr, used_vars):
    # Labels and instructions without 'dest' are kept
    if 'op' not in instr or 'dest' not in instr:
        return True
    # Keep the instruction if its destination variable is used
    return instr['dest'] in used_vars

if __name__ == "__main__":
    prog = json.load(sys.stdin)
    for fn in prog["functions"]:
        # Collect all variables that are used
        used_vars = set()
        for instr in fn["instrs"]:
            args = instr.get("args", [])
            used_vars.update(args)
        # Keep instructions whose destination variables are used
        fn["instrs"] = [instr for instr in fn["instrs"] if should_keep(instr, used_vars)]
    json.dump(prog, sys.stdout, indent=2)
