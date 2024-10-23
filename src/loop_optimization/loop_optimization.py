import functools
import json
import sys


CONTROL = ['jmp', 'br', 'ret']
side_effect_ops = {'alloc', 'free', 'load', 'store', 'ptradd', 'call', 'print'}


class Dataflow:
    def __init__(self, init, direction, meet, transfer):
        self.init = init
        self.direction = direction
        self.meet = meet
        self.transfer = transfer

    def dataflow(self, func_cfg):
        analysis = {}
        if self.direction == "FORWARD":
            preds = func_cfg['label2pred']
            succs = func_cfg['label2succ']
        if self.direction == "BACKWARD":
            preds = func_cfg['label2succ']
            succs = func_cfg['label2pred']
        worklist = set(func_cfg['label2block'].keys())
        analysis = {}
        for label in worklist:
            analysis[label] = (None, self.init)
        while worklist:
            label = worklist.pop()
            if len(preds[label]) == 0:
                live_var = self.init
            else:
                live_var = analysis[preds[label][0]][1]
                for i in range(1, len(preds[label])):
                    pred = preds[label][i]
                    live_var = self.meet(live_var, analysis[pred][1])
            outb = self.transfer(func_cfg['label2block'][label], live_var)
            if outb != analysis[label][1]:
                worklist.update(succs[label])
            analysis[label] = (live_var.copy(), outb.copy())
        if self.direction == "BACKWARD":
            for label, output in analysis.items():
                analysis[label] = (output[1], output[0])
        return analysis


def transfer(block, outb):
    live_var = outb.copy()
    for instr in reversed(block):
        if 'dest' in instr:
            live_var.discard(instr['dest'])
        for arg in instr.get('args', []):
            live_var.add(arg)
    return live_var


def live_vars_process(cfg):
    def meet(live1, live2): return live1.union(live2)
    solver = Dataflow(set(), "BACKWARD", meet, transfer)
    return solver.dataflow(cfg)


def find_loops(graph):
    def get_loop(start, end, dominators):
        interior_nodes = set()
        predecessors = graph['label2pred']
        to_visit = {end}
        while to_visit:
            block = to_visit.pop()
            if block == start:
                continue
            else:
                interior_nodes.add(block)
                for pred in predecessors[block]:
                    if start not in dominators[pred]:
                        return set()
                    elif pred not in interior_nodes:
                        to_visit.add(pred)

        loop = [start]
        interior_nodes.remove(end)
        for block in interior_nodes:
            loop.append(block)
        loop.append(end)
        return loop

    def dfs(block):
        for succ in label2succ[block]:
            if succ in doms[block] and succ != block:
                loops.append(get_loop(succ, block, doms))
            if succ not in visited:
                visited.add(succ)
                dfs(succ)
            continue
    loops = []
    visited = set()
    doms = get_dom(graph)
    label2succ = graph['label2succ'].copy()
    first = graph['blocks'][0][0]['label']
    dfs(first)
    return loops


def get_and_remove_loop_invariant(loop, live_in):
    not_loop_invariant = live_in.copy()
    changed = True
    while (changed):
        changed = False
        defined = set()
        for block in loop:
            for instr in block:
                if 'dest' in instr:
                    var = instr['dest']
                    if var not in not_loop_invariant:
                        op = instr['op']
                        if var in defined or op in side_effect_ops:
                            not_loop_invariant.add(var)
                            changed = True
                            continue
                        if op != 'const':
                            for arg in instr['args']:
                                if arg in not_loop_invariant:
                                    not_loop_invariant.add(var)
                                    changed = True
                                    continue
                    defined.add(var)

    loop_invariant = {}
    for block in loop:
        to_remove = []
        for i, instr in enumerate(block):
            if 'dest' in instr and instr['dest'] not in not_loop_invariant:
                loop_invariant[instr['dest']] = instr
                to_remove.append(i)
        for index in reversed(to_remove):
            del block[index]
    return loop_invariant


def form_blocks(body):
    blocks = [[]]
    for i in body:
        if 'label' not in i:
            blocks[-1].append(i)
            if i['op'] in CONTROL:
                blocks.append([])
        else:
            blocks.append([i])

    return [block for block in blocks if block != []]


def label_blocks(blocks):
    label2block = {}
    i = 0
    for block in blocks:
        if 'label' in block[0]:
            label2block[block[0]['label']] = block
            block = block[1:]
        else:
            label = 'block' + str(i)
            block.insert(0, {'label': label})
            label2block[label] = block
            i += 1
    return label2block


def get_preds(label2succ):
    label2pred = {}
    for label in label2succ.keys():
        label2pred[label] = []
    for node, succrs in label2succ.items():
        for succ in succrs:
            label2pred[succ].append(node)
    return label2pred


def cfg(body):
    blocks = form_blocks(body)
    label2block = label_blocks(blocks)
    label2succ = {}
    for i in range(len(blocks)):
        last = blocks[i][-1]
        label = blocks[i][0]['label']
        if 'op' in last:
            if last['op'] in ['jmp', 'br']:
                label2succ[label] = last['labels']
            elif last['op'] == 'ret' or i == len(blocks) - 1:
                label2succ[label] = []
            else:
                label2succ[label] = [blocks[i+1][0]['label']]
        elif i < len(blocks) - 1:
            label2succ[label] = [blocks[i+1][0]['label']]
        else:
            label2succ[label] = []
    label2pred = get_preds(label2succ)
    return {'blocks': blocks, 'label2block': label2block, 'label2pred': label2pred, 'label2succ': label2succ}


def intersection(sets):
    if len(sets) == 0:
        return set()
    res = sets[0].copy()
    for s in sets[1:]:
        res = res.intersection(s)
    return res


def get_dom(graph):
    blocks = graph['blocks']
    label2block = graph['label2block']
    label2pred = graph['label2pred']
    dom = {label: {label for label in label2block} for label in label2block}
    dom[blocks[0][0]['label']] = {blocks[0][0]['label']}
    changed = True
    while changed:
        changed = False
        for block in blocks[1:]:
            label = block[0]['label']
            doms = intersection([dom.get(label, set())
                                for label in label2pred[label]])
            doms.add(label)
            if doms != dom.get(label):
                changed = True
                dom[label] = doms
    return dom


def licm(body):
    def compare_instr(i1, i2):
        if i1['dest'] in i2.get('args', []):
            return -1
        if i2['dest'] in i1.get('args', []):
            return 1
        return 0

    def find_block_index(label):
        for i in range(len(blocks)):
            if blocks[i][0]['label'] == label:
                return i
        return -1

    func_cfg = cfg(body)
    graph = func_cfg
    blocks = graph['blocks']
    loops = find_loops(func_cfg)
    for loop in loops:
        start_label = loop[0]
        invariants = get_and_remove_loop_invariant(
            [graph['label2block'][label] for label in loop], live_vars_process(func_cfg)[start_label][0])
        invariant_instrs = list(invariants.values())
        invariant_instrs.sort(key=functools.cmp_to_key(compare_instr))
        preheader_label = start_label + '_preheader'
        preheader = [{'label': preheader_label}]
        preheader.extend(invariant_instrs)
        blocks.insert(find_block_index(start_label), preheader)
        for pred in graph['label2pred'][start_label]:
            if pred not in loop:
                pred_block = graph['label2block'][pred]
                last = pred_block[-1]
                if 'op' in last and (last['op'] == 'br' or last['op'] == 'jmp'):
                    last['labels'] = list(
                        map(lambda x: preheader_label if x == start_label else x, last['labels']))
                else:
                    pred_block.append(
                        {'op': 'jmp', 'labels': [preheader_label]})
    return [instr for block in blocks for instr in block]


prog = json.load(sys.stdin)
for func in prog['functions']:
    func['instrs'] = licm(func['instrs'])
json.dump(prog, sys.stdout, indent=2, sort_keys=True)
