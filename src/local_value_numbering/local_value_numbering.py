import json
import sys

def canonicalize(op, args):
    if op in ["add", "mul", "eq"]:
        return tuple(sorted(args))
    return tuple(args)

def lvn(block):
    val2var = {}
    var_replacement = {}
    next_lvn = 0
    new_instrs = []

    for instr in block:
        if "args" in instr:
            new_args = [var_replacement.get(arg, arg) for arg in instr["args"]]
        else:
            new_args = []

        if "dest" in instr:
            op = instr["op"]
            if op == "const":
                value = ("const", instr["value"])
                # If the destination has been reassigned, it clobbers its previous value
                var_replacement.pop(instr["dest"], None)
                val2var = {k: v for k, v in val2var.items() if v != instr["dest"]}  # Remove clobbered values
                if value in val2var:
                    existing_var = val2var[value]
                    var_replacement[instr["dest"]] = existing_var
                    continue
                else:
                    val2var[value] = instr["dest"]
                    var_replacement[instr["dest"]] = instr["dest"]
                    new_instrs.append(instr)
            elif op in ["add", "mul"]:
                canonical_args = canonicalize(op, new_args)
                value = (op,) + canonical_args
                # If the destination has been reassigned, it clobbers its previous value
                var_replacement.pop(instr["dest"], None)
                val2var = {k: v for k, v in val2var.items() if v != instr["dest"]}  # Remove clobbered values
                if value in val2var:
                    existing_var = val2var[value]
                    var_replacement[instr["dest"]] = existing_var
                    continue
                else:
                    val2var[value] = instr["dest"]
                    var_replacement[instr["dest"]] = instr["dest"]
                    new_instrs.append(instr)
            else:
                # For other operations, just insert the instruction and handle as usual
                var_replacement.pop(instr["dest"], None)
                val2var = {k: v for k, v in val2var.items() if v != instr["dest"]}  # Remove clobbered values
                new_instr = dict(instr)
                new_instr["args"] = new_args
                new_instrs.append(new_instr)
                var_replacement[instr["dest"]] = instr["dest"]
        else:
            # Handle non-destination instructions
            new_instr = dict(instr)
            if "args" in new_instr:
                new_instr["args"] = [var_replacement.get(arg, arg) for arg in new_instr["args"]]
            new_instrs.append(new_instr)

    return new_instrs

def split_blocks(instrs):
    blocks = []
    current_block = []
    for instr in instrs:
        current_block.append(instr)
        if instr["op"] in ["jmp", "br"]:
            blocks.append(current_block)
            current_block = []
    if current_block:
        blocks.append(current_block)
    return blocks

def join_blocks(blocks):
    instrs = []
    for block in blocks:
        instrs.extend(block)
    return instrs

def get_used_variables(prog):
    used_vars = set()
    for fn in prog["functions"]:
        for instr in fn["instrs"]:
            if "args" in instr:
                used_vars.update(instr["args"])
    return used_vars

def dce(prog):
    for fn in prog["functions"]:
        used_vars = set()
        new_instrs = []
        for instr in reversed(fn["instrs"]):
            if "op" not in instr or instr["op"] in ["print", "ret", "jmp", "br"]:
                new_instrs.insert(0, instr)
                if "args" in instr:
                    used_vars.update(instr["args"])
            elif "dest" in instr:
                if instr["dest"] in used_vars:
                    new_instrs.insert(0, instr)
                    if "args" in instr:
                        used_vars.update(instr["args"])
                    used_vars.discard(instr["dest"])
        fn["instrs"] = new_instrs
    return prog

if __name__ == "__main__":
    prog = json.load(sys.stdin)
    for fn in prog.get("functions", []):
        blocks = split_blocks(fn["instrs"])
        new_blocks = [lvn(block) for block in blocks]
        fn["instrs"] = join_blocks(new_blocks)
    prog = dce(prog)
    json.dump(prog, sys.stdout, indent=2)
