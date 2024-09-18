import json
import sys

def canonicalize(op, args):
    if op in ["add", "mul", "eq"]:
        return tuple(sorted(args))
    return tuple(args)

val2var = {}
var_replacement = {}
next_lvn = 0

def lvn(block):
    global val2var, var_replacement, next_lvn
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
                if value in val2var:
                    existing_var = val2var[value]
                    var_replacement[instr["dest"]] = existing_var
                    continue
                else:
                    val2var[value] = instr["dest"]
                    var_replacement[instr["dest"]] = instr["dest"]
                    new_instrs.append(instr)
            else:
                canonical_args = canonicalize(op, new_args)
                value = (op,) + canonical_args
                if value in val2var:
                    existing_var = val2var[value]
                    var_replacement[instr["dest"]] = existing_var
                    continue
                else:
                    if all(arg.startswith("const") or arg.isdigit() for arg in new_args):
                        if op == "add":
                            result = sum(int(arg) for arg in new_args)
                        elif op == "mul":
                            result = 1
                            for arg in new_args:
                                result *= int(arg)
                        elif op == "eq":
                            result = int(new_args[0] == new_args[1])
                        else:
                            continue
                        new_instr = {
                            "op": "const",
                            "dest": instr["dest"],
                            "type": instr["type"],
                            "value": result
                        }
                        val2var[value] = instr["dest"]
                        var_replacement[instr["dest"]] = instr["dest"]
                        new_instrs.append(new_instr)
                    else:
                        lvn_var = f"lvn.{next_lvn}"
                        next_lvn += 1
                        val2var[value] = lvn_var
                        var_replacement[instr["dest"]] = lvn_var
                        new_instr = dict(instr)
                        new_instr["dest"] = lvn_var
                        new_instr["args"] = list(canonical_args)
                        new_instrs.append(new_instr)
        else:
            new_instr = dict(instr)
            if "args" in new_instr:
                new_instr["args"] = [var_replacement.get(arg, arg) for arg in new_instr["args"]]
            new_instrs.append(new_instr)
    return new_instrs

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
        fn["instrs"] = lvn(fn["instrs"])
    prog = dce(prog)
    json.dump(prog, sys.stdout, indent=2)
