import json
import sys
from collections import defaultdict

CF_OPS = ("br", "jmp")
TERMINATORS = ('br', 'jmp', 'ret')


class BasicBlock:
    def __init__(self, label: str = None):
        self.instrs: list[dict] = []
        self.label: str = label

    def __str__(self):
        return f"BasicBlock(label={self.label}, instrs={self.instrs})"

    def __lt__(self, other):
        return self.label < other.label

    def __eq__(self, other):
        return isinstance(other, BasicBlock) and self.label == other.label

    def __hash__(self):
        return hash(self.label)

    def add_instr(self, instr: dict):
        self.instrs.append(instr)


class CFG:
    def __init__(self):
        self.nodes = []
        self.edges = {}  # mapping from node to list of successor nodes

    def add_node(self, node):
        if node not in self.nodes:
            self.nodes.append(node)
            self.edges[node] = []

    def add_nodes_from(self, nodes):
        for node in nodes:
            self.add_node(node)

    def add_edge(self, from_node, to_node):
        self.add_node(from_node)
        self.add_node(to_node)
        self.edges[from_node].append(to_node)

    def add_edges_from(self, edge_list):
        for from_node, to_node in edge_list:
            self.add_edge(from_node, to_node)

    def clear(self):
        self.nodes = []
        self.edges = {}

    def get_edges(self):
        return [(from_node, to_node) for from_node in self.edges for to_node in self.edges[from_node]]

    def predecessors(self, node):
        """Returns a list of predecessor nodes for a given node."""
        return [from_node for from_node, to_nodes in self.edges.items() if node in to_nodes]

    def successors(self, node):
        """Returns a list of successor nodes for a given node."""
        return self.edges.get(node, [])

    def get_predecessors(self):
        """Returns a mapping from node to a list of predecessor nodes."""
        predecessors = {node: [] for node in self.nodes}
        for from_node, to_nodes in self.edges.items():
            for to_node in to_nodes:
                predecessors[to_node].append(from_node)
        return predecessors

    def __iter__(self):
        return iter(self.nodes)

    def dfs_postorder_nodes(self, source):
        visited = set()
        postorder = []

        def dfs(node):
            if node in visited:
                return
            visited.add(node)
            for neighbor in self.successors(node):
                dfs(neighbor)
            postorder.append(node)

        dfs(source)
        return postorder


def dfs_postorder_nodes(cfg, source):
    visited = set()
    postorder = []

    def dfs(node):
        if node in visited:
            return
        visited.add(node)
        for neighbor in cfg.successors(node):
            dfs(neighbor)
        postorder.append(node)

    dfs(source)
    return postorder


def construct_cfg(instrs):
    """Constructs a control flow graph from a list of instructions."""
    cfg = CFG()
    blocks = create_blocks(instrs)
    entry_block = blocks["sentinel_entry"]
    connect_blocks(cfg, blocks)
    return cfg, entry_block


def create_blocks(instrs):
    """Creates basic blocks from a list of instructions."""
    blocks = dict({"sentinel_entry": BasicBlock("sentinel_entry")})
    curr_block = blocks["sentinel_entry"]
    for instr in instrs:
        if "label" in instr and instr["label"] != "sentinel_entry":
            curr_block = BasicBlock(instr["label"])
            blocks[instr["label"]] = curr_block
        curr_block.add_instr(instr)
    return blocks


def connect_blocks(cfg, blocks):
    """Connects basic blocks in the control flow graph."""
    cfg.add_nodes_from(blocks.values())
    block_list = list(blocks.values())
    for i, block in enumerate(block_list):
        if is_control_flow_instr(block):
            connect_control_flow(cfg, block, blocks)
        elif i + 1 < len(block_list):
            cfg.add_edge(block, block_list[i + 1])


def is_control_flow_instr(block):
    """Checks if the last instruction in the block is a control flow operation."""
    return block.instrs and block.instrs[-1].get("op") in CF_OPS


def connect_control_flow(cfg, block, blocks):
    """Connects control flow edges based on branch/jump instructions."""
    for label in block.instrs[-1]["labels"]:
        cfg.add_edge(block, blocks[label])


def insert_node(cfg, target_node, reference_node, before=True):
    """Inserts a node in the CFG either before or after a reference node."""
    node_list = cfg.nodes.copy()
    index = node_list.index(reference_node) + (0 if before else 1)
    node_list.insert(index, target_node)
    recreate_cfg(cfg, node_list)


def insert_node_before(cfg, target_node, before_node):
    """Inserts a node before a specified node."""
    insert_node(cfg, target_node, before_node, before=True)


def insert_node_after(cfg, target_node, after_node):
    """Inserts a node after a specified node."""
    insert_node(cfg, target_node, after_node, before=False)


def recreate_cfg(cfg, node_list):
    """Recreates the CFG with a new node order."""
    edge_list = cfg.get_edges()
    cfg.clear()
    cfg.add_nodes_from(node_list)
    cfg.add_edges_from(edge_list)


def cfg_to_instrs(cfg):
    """Converts a CFG back to a flat list of instructions."""
    program = [{"label": "sentinel_entry"}] if needs_sentinel(cfg) else []
    for block in cfg.nodes:
        program.extend(block.instrs)
    return program


def needs_sentinel(cfg):
    """Checks if the CFG needs a sentinel entry label."""
    first_instr = next(iter(cfg.nodes))
    return first_instr.instrs and first_instr.instrs[0].get("label") != "sentinel_entry"


def add_terminators(cfg):
    """Adds terminators to blocks without them."""
    blocks = cfg.nodes
    for i, block in enumerate(blocks):
        if not block.instrs or len(block.instrs) <= 1:
            add_terminator(cfg, block, i, blocks)


def add_terminator(cfg, block, index, blocks):
    """Adds a terminator to a block based on its position in the CFG."""
    if index == len(blocks) - 1:
        block.add_instr({'op': 'ret', 'args': []})
    else:
        dest = blocks[index + 1].label
        block.add_instr({'op': 'jmp', 'labels': [dest]})
        cfg.add_edge(block, blocks[index + 1])


def get_variable_definition_blocks(cfg):
    out = defaultdict(set)
    for block in cfg.nodes:
        for instr in block.instrs:
            if 'dest' in instr:
                out[instr['dest']].add(block)
    return out


def intersect_multiple_sets(sets):
    sets = list(sets)
    if not sets:
        return set()
    return set.intersection(*sets)


def compute_cfg_dominators(cfg, entry):
    dominators = {v: set(cfg.nodes) for v in cfg.nodes}
    dominators[entry] = {entry}
    changed = True
    while changed:
        changed = False
        for node in cfg.nodes:
            if node == entry:
                continue
            preds = cfg.predecessors(node)
            if not preds:
                continue
            new_dom = intersect_multiple_sets(dominators[p] for p in preds)
            new_dom.add(node)
            if dominators[node] != new_dom:
                dominators[node] = new_dom
                changed = True

    idom = {}
    for node in cfg.nodes:
        if node == entry:
            idom[node] = None
            continue
        doms = dominators[node] - {node}
        idom[node] = max(doms, key=lambda n: len(dominators[n]))
    return idom


def compute_cfg_dominance_frontier(cfg, idom):
    df = {b: set() for b in cfg.nodes}
    for b in cfg.nodes:
        preds = cfg.predecessors(b)
        if len(preds) >= 2:
            for p in preds:
                runner = p
                while runner != idom[b]:
                    df[runner].add(b)
                    runner = idom[runner]
    return df


def compute_cfg_dominator_tree(idom):
    dom_tree = defaultdict(set)
    for node, parent in idom.items():
        if parent is not None:
            dom_tree[parent].add(node)
    return dom_tree


def get_block_variable_definitions(cfg):
    out = defaultdict(set)
    for block in cfg.nodes:
        for instr in block.instrs:
            if 'dest' in instr:
                out[instr['dest']].add(block)
    return dict(out)


def compute_phi_functions_for_blocks(cfg, df, defs):
    phis = {b: set() for b in cfg.nodes}
    for v, v_defs in defs.items():
        worklist = list(v_defs)
        processed = set()
        while worklist:
            d = worklist.pop()
            for block in df.get(d, []):
                if v not in phis[block]:
                    phis[block].add(v)
                    if block not in processed:
                        worklist.append(block)
                        processed.add(block)
    return phis


def get_function_variable_types(func):
    types = {arg['name']: arg['type'] for arg in func.get('args', [])}
    for instr in func['instrs']:
        if 'dest' in instr:
            types[instr['dest']] = instr['type']
    return types


def rename_variables_in_ssa(cfg, phis, dom_tree, arg_names, entry):
    stack = defaultdict(list, {v: [v] for v in arg_names})
    phi_args = {b: {p: [] for p in phis[b]} for b in cfg.nodes}
    phi_dests = {b: {p: None for p in phis[b]} for b in cfg.nodes}
    counters = defaultdict(int)

    def _push_fresh(var):
        fresh = f'{var}.{counters[var]}'
        counters[var] += 1
        stack[var].insert(0, fresh)
        return fresh

    def _rename(block):
        old_stack = {k: list(v) for k, v in stack.items()}
        for p in phis[block]:
            phi_dests[block][p] = _push_fresh(p)
        for instr in block.instrs:
            if 'args' in instr:
                instr['args'] = [stack[arg][0] for arg in instr['args']]
            if 'dest' in instr:
                instr['dest'] = _push_fresh(instr['dest'])
        for succ in cfg.successors(block):
            for p in phis[succ]:
                arg = stack[p][0] if stack.get(p) else "__undefined"
                phi_args[succ][p].append((block, arg))
        for child in dom_tree.get(block, []):
            _rename(child)
        stack.clear()
        stack.update(old_stack)

    _rename(entry)
    return phi_args, phi_dests


def insert_phi_functions_into_cfg(cfg, phi_args, phi_dests, types):
    for block in cfg.nodes:
        new_instrs = []
        if block.instrs and 'label' in block.instrs[0]:
            new_instrs.append(block.instrs[0])
            instrs_to_process = block.instrs[1:]
        else:
            instrs_to_process = block.instrs

        for dest, pairs in sorted(phi_args[block].items()):
            phi = {
                'op': 'phi',
                'dest': phi_dests[block][dest],
                'type': types[dest],
                'labels': [p[0].label for p in pairs],
                'args': [p[1] for p in pairs],
            }
            new_instrs.append(phi)
        new_instrs.extend(instrs_to_process)
        block.instrs = new_instrs


def combine_pointer_maps(predecessor_pointer_maps):
    """Combine pointer maps from predecessors."""
    combined_map = {}
    all_keys = {key for pred_map in predecessor_pointer_maps for key in pred_map}
    for key in all_keys:
        combined_values = {
            v for pred_map in predecessor_pointer_maps if key in pred_map for v in pred_map[key]}
        combined_map[key] = combined_values
    return combined_map


def update_use_map(use_map, argument, block_pointer_map):
    """Update the use map based on the given argument and pointer map."""
    pointer = block_pointer_map.get(argument, set())
    if "any" in pointer:
        for key in use_map:
            use_map[key] = (use_map[key][0], True)
    else:
        for store_dest, (instr, used) in use_map.items():
            if pointer.intersection(block_pointer_map.get(store_dest, set())):
                use_map[store_dest] = (instr, True)


def initialize_pointer_map(cfg, entry_block, argument_names):
    """Initialize the pointer map with entry block arguments pointing to 'any'."""
    pointer_map = {block.label: {} for block in cfg.nodes}
    pointer_map[entry_block.label] = {arg: {"any"} for arg in argument_names}
    return pointer_map


def process_instructions(block, block_pointer_map, store_use_map):
    """Process instructions within a block, updating the pointer map and use map."""
    for idx, instr in enumerate(block.instrs):
        if instr.get("op") == "alloc":
            block_pointer_map[instr["dest"]] = {f"{block.label}.{idx}"}
        elif instr.get("op") == "load":
            block_pointer_map[instr["dest"]] = {"any"}
            update_use_map(store_use_map, instr["args"][0], block_pointer_map)
        elif instr.get("op") in {"id", "ptradd"}:
            source = instr["args"][0]
            block_pointer_map[instr["dest"]
                              ] = block_pointer_map.get(source, set())
        elif instr.get("op") == "store":
            dest = instr["args"][0]
            prev_instr, used = store_use_map.get(dest, (None, True))
            if not used:
                prev_instr["op"] = "nop"
            store_use_map[dest] = (instr, False)


def perform_memory_analysis(cfg, entry_block, argument_names):
    """Perform memory analysis on the control flow graph."""
    pointer_map = initialize_pointer_map(cfg, entry_block, argument_names)
    post_order = list(reversed(cfg.dfs_postorder_nodes(entry_block)))
    worklist = post_order[:]

    while worklist:
        block = worklist.pop()
        predecessors = cfg.predecessors(block)
        predecessor_maps = [pointer_map[pred.label] for pred in predecessors]
        combined_map = combine_pointer_maps(predecessor_maps)
        store_use_map = {}

        process_instructions(block, combined_map, store_use_map)

        if pointer_map.get(block.label) != combined_map:
            pointer_map[block.label] = combined_map
            for succ in cfg.successors(block):
                if succ not in worklist:
                    worklist.append(succ)


if __name__ == "__main__":
    prog = json.load(sys.stdin)
    for fn in prog["functions"]:
        program_cfg, entry_block = construct_cfg(fn["instrs"])
        def_blocks = get_variable_definition_blocks(program_cfg)
        idom = compute_cfg_dominators(program_cfg, entry_block)
        df = compute_cfg_dominance_frontier(program_cfg, idom)
        phis = compute_phi_functions_for_blocks(program_cfg, df, def_blocks)
        types = get_function_variable_types(fn)
        arg_names = {arg['name'] for arg in fn.get('args', [])}
        dom_tree = compute_cfg_dominator_tree(idom)
        phi_args, phi_dests = rename_variables_in_ssa(
            program_cfg, phis, dom_tree, arg_names, entry_block)
        insert_phi_functions_into_cfg(program_cfg, phi_args, phi_dests, types)
        fn["instrs"] = cfg_to_instrs(program_cfg)

        perform_memory_analysis(program_cfg, entry_block, arg_names)

    json.dump(prog, sys.stdout, indent=2)
