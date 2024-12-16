import os
import sys
import lark
import z3
from functools import reduce
from collections import defaultdict
from graphviz import Digraph

# Set directories here
input_dir = "operation_tests"
output_dir = "output"
visual_dir = "visualizations"

# Create output and visualization directories if they don't exist
os.makedirs(output_dir, exist_ok=True)
os.makedirs(visual_dir, exist_ok=True)

GRAMMAR = r"""
start: stmts expr

stmts: stmt*

stmt: CNAME ":=" expr ";"

?expr: logic_or
     | logic_or "?" expr ":" expr -> if

?logic_or: logic_and
         | logic_or "||" logic_and -> lor

?logic_and: compare
          | logic_and "&&" compare -> land

?compare: bitwise
        | compare "==" bitwise     -> eq
        | compare ">" bitwise      -> gt
        | compare "<" bitwise      -> lt

?bitwise: sum
        | bitwise "&" sum          -> band
        | bitwise "|" sum          -> bor
        | bitwise "^" sum          -> bxor

?sum: term
    | sum "+" term -> add
    | sum "-" term -> sub

?term: factor
     | term "*" factor -> mul
     | term "/" factor -> div
     | term "%" factor -> mod
     | term "<<" factor -> shl
     | term ">>" factor -> shr

?factor: item
       | "-" factor -> neg
       | "!" factor -> not

?item: NUMBER           -> num
     | CNAME           -> var
     | "(" expr ")"

%import common.NUMBER
%import common.CNAME
%import common.WS
%ignore WS
""".strip()

def to_bool(expr):
    if z3.is_bool(expr):
        return expr
    else:
        return expr != 0

def interp(tree, lookup, assign, sequence):
    op = tree.data
    if op in ('add', 'sub', 'mul', 'div', 'shl', 'shr', 'mod', 'band', 'bor', 'bxor'):
        lhs = interp(tree.children[0], lookup, assign, sequence)
        rhs = interp(tree.children[1], lookup, assign, sequence)
        if op == 'add':
            return lhs + rhs
        elif op == 'sub':
            return lhs - rhs
        elif op == 'mul':
            return lhs * rhs
        elif op == 'div':
            return z3.UDiv(lhs, rhs)
        elif op == 'mod':
            return z3.URem(lhs, rhs)
        elif op == 'shl':
            return lhs << rhs
        elif op == 'shr':
            return z3.LShR(lhs, rhs)
        elif op == 'band':
            return lhs & rhs
        elif op == 'bor':
            return lhs | rhs
        elif op == 'bxor':
            return lhs ^ rhs

    elif op in ('eq', 'gt', 'lt'):
        lhs = interp(tree.children[0], lookup, assign, sequence)
        rhs = interp(tree.children[1], lookup, assign, sequence)
        if op == 'eq':
            return lhs == rhs
        elif op == 'gt':
            return z3.UGT(lhs, rhs)
        elif op == 'lt':
            return z3.ULT(lhs, rhs)

    elif op in ('lor', 'land'):
        lhs = interp(tree.children[0], lookup, assign, sequence)
        rhs = interp(tree.children[1], lookup, assign, sequence)
        if op == 'lor':
            return z3.Or(lhs, rhs)
        elif op == 'land':
            return z3.And(lhs, rhs)

    elif op == 'not':
        sub = interp(tree.children[0], lookup, assign, sequence)
        return z3.Not(to_bool(sub))

    elif op == 'neg':
        sub = interp(tree.children[0], lookup, assign, sequence)
        return -sub

    elif op == 'num':
        val = int(tree.children[0])
        return z3.BitVecVal(val, 8)

    elif op == 'var':
        return lookup(tree.children[0])

    elif op == 'if':
        cond = interp(tree.children[0], lookup, assign, sequence)
        tval = interp(tree.children[1], lookup, assign, sequence)
        fval = interp(tree.children[2], lookup, assign, sequence)
        return z3.If(to_bool(cond), tval, fval)

    elif op == 'stmt':
        var_name = tree.children[0]
        val = interp(tree.children[1], lookup, assign, sequence)
        return assign(var_name, val)

    elif op == 'stmts':
        return sequence(interp(child, lookup, assign, sequence) for child in tree.children)

    elif op == 'start':
        equalities = interp(tree.children[0], lookup, assign, sequence)
        final_expr = interp(tree.children[1], lookup, assign, sequence)
        return final_expr, equalities

def pretty(tree, subst={}, paren=False):
    if paren:
        par = lambda s: '(' + s + ')'
    else:
        par = lambda s: s

    op = tree.data
    op_map = {
        'add': '+', 'sub': '-', 'mul': '*', 'div': '/', 'mod': '%',
        'shl': '<<', 'shr': '>>', 'band': '&', 'bor': '|', 'bxor': '^',
        'eq': '==', 'gt': '>', 'lt': '<',
        'lor': '||', 'land': '&&'
    }

    if op in op_map:
        lhs = pretty(tree.children[0], subst, True)
        rhs = pretty(tree.children[1], subst, True)
        c = op_map[op]
        return par(f'{lhs} {c} {rhs}')
    elif op == 'neg':
        sub = pretty(tree.children[0], subst)
        return '-' + sub
    elif op == 'not':
        sub = pretty(tree.children[0], subst)
        return '!' + sub
    elif op == 'num':
        return tree.children[0]
    elif op == 'var':
        name = tree.children[0]
        return str(subst.get(name, name))
    elif op == 'if':
        cond = pretty(tree.children[0], subst)
        true_val = pretty(tree.children[1], subst)
        false_val = pretty(tree.children[2], subst)
        return par(f'{cond} ? {true_val} : {false_val}')
    elif op == 'stmt':
        var_name = tree.children[0]
        expr = pretty(tree.children[1], subst)
        return f'{subst.get(var_name, var_name)} := {expr};\n'
    elif op == 'stmts':
        return ''.join(pretty(child, subst) for child in tree.children)
    elif op == 'start':
        stmts = pretty(tree.children[0], subst)
        expr = pretty(tree.children[1], subst)
        return f'{stmts}{expr}'
    else:
        return f'UNKNOWN({op})'

def run(tree, env):
    def sequence(stmts):
        for _ in stmts:
            pass
    return interp(tree, env.__getitem__, env.__setitem__, sequence)

def z3_expr(tree, vars=None):
    vars = defaultdict(lambda: [], vars or {})
    current = defaultdict(lambda: 0)

    def new(name):
        v = z3.BitVec(f'{name}{"'" * len(vars[name])}', 8)
        vars[name].append(v)
        current[name] = -1
        return v

    def get_var(name):
        if name in vars:
            return vars[name][current[name]]
        else:
            return new(name)

    def set_var(name, val):
        return new(name) == val

    def sequence(stmts):
        return reduce(z3.And, stmts, True)

    return interp(tree, get_var, set_var, sequence), vars

def solve(phi):
    s = z3.Solver()
    s.add(phi)
    if s.check() == z3.sat:
        return s.model()
    return None

def model_values(model):
    return {d.name(): model[d] for d in model.decls()} if model else {}

def synthesize(tree1, tree2):
    (expr1, eqs1), vars1 = z3_expr(tree1)
    (expr2, eqs2), vars2 = z3_expr(tree2, vars1)

    plain_vars = [var for k,v in vars2.items() for var in v if not k.startswith('h')]

    goal = z3.ForAll(plain_vars, z3.Implies(z3.And(eqs1, eqs2), expr1 == expr2))
    return solve(goal)

def visualize_ast(tree, output_path):
    dot = Digraph()
    def add_node(node, counter=[0]):
        node_id = str(counter[0])
        counter[0] += 1

        if hasattr(node, 'data'):  # It's a Tree
            label = node.data
            dot.node(node_id, label)
            for child in node.children:
                child_id = add_node(child, counter)
                dot.edge(node_id, child_id)
        else:
            # It's a token
            dot.node(node_id, str(node), shape='box')
        return node_id
    add_node(tree)
    dot.render(output_path, format='png', cleanup=True)


def process_source(source, output_dir, visual_dir):
    # This function:
    # 1. Parses the source which contains two programs separated by ---
    # 2. Synthesizes and visualizes
    # 3. Returns a dict with { 'output': string_of_results, 'ast1': 'path/to/ast1.png', 'ast2': 'path/to/ast2.png' }

    parser = lark.Lark(GRAMMAR)
    if '---' not in source:
        return {'error': "No '---' delimiter found."}

    src1, src2 = source.split('---')
    tree1 = parser.parse(src1.strip())
    tree2 = parser.parse(src2.strip())

    model = synthesize(tree1, tree2)

    output_content = []
    output_content.append("Program 1:\n")
    output_content.append(pretty(tree1))
    output_content.append("\nProgram 2 (with holes filled):\n")
    output_content.append(pretty(tree2, model_values(model)))

    # Write output to a file or just return as string
    result_str = ''.join(output_content)

    # Visualize
    base_name = "uploaded"
    ast1_path = os.path.join(visual_dir, f'ast1_{base_name}')
    ast2_path = os.path.join(visual_dir, f'ast2_{base_name}')
    visualize_ast(tree1, ast1_path)
    visualize_ast(tree2, ast2_path)

    return {
      'output': result_str,
      'ast1': ast1_path + ".png",
      'ast2': ast2_path + ".png"
    }

if __name__ == '__main__':
    parser = lark.Lark(GRAMMAR)

    # Process each .txt file in the input directory
    for filename in os.listdir(input_dir):
        if filename.endswith('.txt'):
            input_path = os.path.join(input_dir, filename)
            with open(input_path, 'r') as f:
                source = f.read().strip()

            # Expect two programs separated by '---'
            if '---' not in source:
                print(f"Skipping {filename}: no '---' delimiter found.")
                continue

            src1, src2 = source.split('---')
            tree1 = parser.parse(src1.strip())
            tree2 = parser.parse(src2.strip())

            # Synthesize hole values
            model = synthesize(tree1, tree2)

            # Prepare output content
            output_content = []
            output_content.append("Program 1:\n")
            output_content.append(pretty(tree1))
            output_content.append("\nProgram 2 (with holes filled):\n")
            output_content.append(pretty(tree2, model_values(model)))

            base_name = os.path.splitext(filename)[0]
            output_file = os.path.join(output_dir, base_name + '_out.txt')
            with open(output_file, 'w') as out_f:
                out_f.write(''.join(output_content))

            # Visualize both ASTs
            ast1_path = os.path.join(visual_dir, f'ast1_{base_name}')
            ast2_path = os.path.join(visual_dir, f'ast2_{base_name}')
            visualize_ast(tree1, ast1_path)
            visualize_ast(tree2, ast2_path)

            print(f"Processed {filename}")
            print(f"Output written to {output_file}")
            print(f"ASTs visualized to {ast1_path}.png and {ast2_path}.png")
