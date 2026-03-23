
from __future__ import annotations

import argparse
import time
from abc import ABC, abstractmethod
from bisect import bisect_left
from math import ceil
from typing import Dict, List, Optional, Sequence


# ---------------------------------------------------------------------------
# MemoryLogger (singleton)
# ---------------------------------------------------------------------------

import tracemalloc


class MemoryLogger:
    _instance: Optional["MemoryLogger"] = None

    @staticmethod
    def get_instance() -> "MemoryLogger":
        if MemoryLogger._instance is None:
            MemoryLogger._instance = MemoryLogger()
        return MemoryLogger._instance

    # Java alias
    getInstance = get_instance

    def __init__(self) -> None:
        self._max_mb: float = 0.0
        self._started = False

    def reset(self) -> None:
        if self._started:
            tracemalloc.stop()
        tracemalloc.start()
        self._started = True
        self._max_mb = 0.0

    def check_memory(self) -> float:
        if not self._started:
            return 0.0
        current, peak = tracemalloc.get_traced_memory()
        mb = peak / (1024 * 1024)
        if mb > self._max_mb:
            self._max_mb = mb
        return (tracemalloc.get_traced_memory()[0]) / (1024 * 1024)

    # Java aliases
    checkMemory = check_memory

    def get_max_memory(self) -> float:
        return round(self._max_mb, 3)

    getMaxMemory = get_max_memory


# ---------------------------------------------------------------------------
# Abstract itemset classes
# ---------------------------------------------------------------------------

class AbstractItemset(ABC):
    @abstractmethod
    def size(self) -> int: ...
    @abstractmethod
    def __str__(self) -> str: ...
    def print(self) -> None:
        print(str(self), end="")
    @abstractmethod
    def get_absolute_support(self) -> int: ...
    @abstractmethod
    def get_relative_support(self, nb_object: int) -> float: ...
    def get_relative_support_as_string(self, nb_object: int) -> str:
        freq = self.get_relative_support(nb_object)
        s = f"{freq:.5f}".rstrip("0").rstrip(".")
        return s if s else "0"
    @abstractmethod
    def contains(self, item: int) -> bool: ...


class AbstractOrderedItemset(AbstractItemset, ABC):
    @abstractmethod
    def get_absolute_support(self) -> int: ...
    @abstractmethod
    def size(self) -> int: ...
    @abstractmethod
    def get(self, position: int) -> int: ...

    def get_last_item(self) -> int:
        return self.get(self.size() - 1)

    def __str__(self) -> str:
        if self.size() == 0:
            return "EMPTYSET"
        return "".join(f"{self.get(i)} " for i in range(self.size()))

    def get_relative_support(self, nb_object: int) -> float:
        return float(self.get_absolute_support()) / float(nb_object)

    def contains(self, item: int) -> bool:
        for i in range(self.size()):
            v = self.get(i)
            if v == item:
                return True
            elif v > item:
                return False
        return False

    def contains_all(self, itemset2: "AbstractOrderedItemset") -> bool:
        if self.size() < itemset2.size():
            return False
        i = 0
        for j in range(itemset2.size()):
            found = False
            while not found and i < self.size():
                a = self.get(i); b = itemset2.get(j)
                if a == b:
                    found = True
                elif a > b:
                    return False
                i += 1
            if not found:
                return False
        return True

    def is_equal_to(self, itemset2: "AbstractOrderedItemset") -> bool:
        if self.size() != itemset2.size(): return False
        for i in range(self.size()):
            if itemset2.get(i) != self.get(i): return False
        return True

    def is_equal_to_array(self, itemset: Sequence[int]) -> bool:
        if self.size() != len(itemset): return False
        for i, v in enumerate(itemset):
            if v != self.get(i): return False
        return True

    def all_the_same_except_last_item_v2(self, itemset2: "AbstractOrderedItemset") -> bool:
        if itemset2.size() != self.size(): return False
        for i in range(self.size() - 1):
            if self.get(i) != itemset2.get(i): return False
        return True

    def all_the_same_except_last_item(self, itemset2: "AbstractOrderedItemset") -> Optional[int]:
        if itemset2.size() != self.size():
            return None
        for i in range(self.size()):
            if i == self.size() - 1:
                if self.get(i) >= itemset2.get(i):
                    return None
            else:
                if self.get(i) != itemset2.get(i):
                    return None
        return itemset2.get(itemset2.size() - 1)


# ---------------------------------------------------------------------------
# ArraysAlgos helpers (subset used by provided code)
# ---------------------------------------------------------------------------

def intersect_two_sorted_arrays(array1: Sequence[int], array2: Sequence[int]) -> List[int]:
    i = j = 0
    out: List[int] = []
    while i < len(array1) and j < len(array2):
        a, b = array1[i], array2[j]
        if a < b:
            i += 1
        elif b < a:
            j += 1
        else:
            out.append(a)
            i += 1; j += 1
    return out

def contains_or_equals_array(itemset1: Sequence[int], itemset2: Sequence[int]) -> bool:
    for v2 in itemset2:
        found = False
        for v1 in itemset1:
            if v1 == v2:
                found = True; break
            elif v1 > v2:
                return False
        if not found: return False
    return True

def contains_lex(itemset: Sequence[int], item: int) -> bool:
    for v in itemset:
        if v == item: return True
        elif v > item: return False
    return False


# ---------------------------------------------------------------------------
# Itemset / Itemsets
# ---------------------------------------------------------------------------

class Itemset(AbstractOrderedItemset):
    def __init__(self, items: List[int] | None = None, support: int = 0) -> None:
        super().__init__()
        self.itemset: List[int] = list(items) if items is not None else []
        self.support: int = support

    def getItems(self) -> List[int]:
        return self.itemset

    def get_absolute_support(self) -> int:
        return self.support

    def size(self) -> int:
        return len(self.itemset)

    def get(self, position: int) -> int:
        return self.itemset[position]

    def set_absolute_support(self, support: int) -> None:
        self.support = int(support)

    setAbsoluteSupport = set_absolute_support

    def increaseTransactionCount(self) -> None:
        self.support += 1

    def cloneItemSetMinusOneItem(self, item_to_remove: int) -> "Itemset":
        new_items: List[int] = []
        removed = False
        for v in self.itemset:
            if not removed and v == item_to_remove:
                removed = True
            else:
                new_items.append(v)
        return Itemset(new_items)

    def cloneItemSetMinusAnItemset(self, itemset_to_not_keep: "Itemset") -> "Itemset":
        to_drop = set(itemset_to_not_keep.itemset)
        new_items = [v for v in self.itemset if v not in to_drop]
        return Itemset(new_items)

    def intersection(self, itemset2: "Itemset") -> "Itemset":
        inter = intersect_two_sorted_arrays(self.getItems(), itemset2.getItems())
        return Itemset(inter)

    def __hash__(self) -> int:
        return hash(tuple(self.itemset))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Itemset) and self.itemset == other.itemset and self.support == other.support


class Itemsets:
    def __init__(self, name: str = "") -> None:
        self.name = name
        self.levels: List[List[Itemset]] = []
        self.itemsets_count: int = 0
        self.levels.append([])  # level 0

    def printItemsets(self, nbObject: int) -> None:
        print(f" ------- {self.name} -------")
        patternCount = 0
        for lvl_idx, level in enumerate(self.levels):
            print(f"  L{lvl_idx} ")
            for itemset in level:
                print(f"  pattern {patternCount}:  ", end="")
                itemset.print()
                print(f"support :  {itemset.get_absolute_support()}")
                patternCount += 1
        print(" --------------------------------")

    def addItemset(self, itemset: Itemset, k: int) -> None:
        while len(self.levels) <= k:
            self.levels.append([])
        self.levels[k].append(itemset)
        self.itemsets_count += 1

    def getLevels(self) -> List[List[Itemset]]:
        return self.levels

    def getItemsetsCount(self) -> int:
        return self.itemsets_count

    def setName(self, newName: str) -> None:
        self.name = newName

    def decreaseItemsetCount(self) -> None:
        self.itemsets_count -= 1


# ---------------------------------------------------------------------------
# FP-Tree structures
# ---------------------------------------------------------------------------

class FPNode:
    def __init__(self) -> None:
        self.item_id: int = -1
        self.counter: int = 1
        self.parent: Optional["FPNode"] = None
        self.childs: List["FPNode"] = []
        self.node_link: Optional["FPNode"] = None

    def get_child_with_id(self, id_: int) -> Optional["FPNode"]:
        for child in self.childs:
            if child.item_id == id_:
                return child
        return None

    def to_string(self, indent: str) -> str:
        out = [f"{self.item_id} (count={self.counter})\n"]
        new_indent = indent + "   "
        for child in self.childs:
            out.append(new_indent + child.to_string(new_indent))
        return "".join(out)

    def __str__(self) -> str:
        return str(self.item_id)


class FPTree:
    def __init__(self) -> None:
        self.header_list: List[int] = []
        self.map_item_nodes: Dict[int, FPNode] = {}
        self.map_item_last_node: Dict[int, FPNode] = {}
        self.root: FPNode = FPNode()

    def add_transaction(self, transaction: List[int]) -> None:
        current = self.root
        for item in transaction:
            child = current.get_child_with_id(item)
            if child is None:
                new_node = FPNode()
                new_node.item_id = item
                new_node.parent = current
                current.childs.append(new_node)
                current = new_node
                self._fix_node_links(item, new_node)
            else:
                child.counter += 1
                current = child

    def _fix_node_links(self, item: int, new_node: FPNode) -> None:
        last = self.map_item_last_node.get(item)
        if last is not None:
            last.node_link = new_node
        self.map_item_last_node[item] = new_node
        if item not in self.map_item_nodes:
            self.map_item_nodes[item] = new_node

    def add_prefix_path(self, prefix_path: List[FPNode], map_support_beta: Dict[int, int], relative_minsupp: int) -> None:
        path_count = prefix_path[0].counter
        current = self.root
        for i in range(len(prefix_path) - 1, 0, -1):
            path_item = prefix_path[i]
            if map_support_beta.get(path_item.item_id, 0) >= relative_minsupp:
                child = current.get_child_with_id(path_item.item_id)
                if child is None:
                    new_node = FPNode()
                    new_node.item_id = path_item.item_id
                    new_node.parent = current
                    new_node.counter = path_count
                    current.childs.append(new_node)
                    current = new_node
                    self._fix_node_links(path_item.item_id, new_node)
                else:
                    child.counter += path_count
                    current = child

    def create_header_list(self, map_support: Dict[int, int]) -> None:
        self.header_list = list(self.map_item_nodes.keys())
        self.header_list.sort(key=lambda it: (-map_support[it], it))

    def __str__(self) -> str:
        temp = "F"
        temp += f" HeaderList: {self.header_list}\n"
        temp += self.root.to_string("")
        return temp


# ---------------------------------------------------------------------------
# FP-Growth algorithm
# ---------------------------------------------------------------------------

class AlgoFPGrowth:
    BUFFERS_SIZE = 2000

    def __init__(self) -> None:
        self.start_timestamp: int = 0
        self.end_time: int = 0
        self.transaction_count: int = 0
        self.itemset_count: int = 0
        self.min_support_relative: int = 0
        self.max_pattern_length: int = 1000
        self.min_pattern_length: int = 0
        self._writer: Optional[open] = None
        self.patterns: Optional[Itemsets] = None
        self.itemset_buffer: Optional[List[int]] = None
        self.fpnode_temp_buffer: Optional[List[FPNode]] = None
        self.itemset_output_buffer: Optional[List[int]] = None

    def run_algorithm(self, input_path: str, output_path: Optional[str], minsupp: float) -> Optional[Itemsets]:
        self.start_timestamp = int(time.time() * 1000)
        self.itemset_count = 0
        self.transaction_count = 0

        MemoryLogger.get_instance().reset()
        MemoryLogger.get_instance().check_memory()

        if output_path is None:
            self._writer = None
            self.patterns = Itemsets("FREQUENT ITEMSETS")
        else:
            self.patterns = None
            self._writer = open(output_path, "w", encoding="utf-8", newline="\n")
            self.itemset_output_buffer = [0] * self.BUFFERS_SIZE

        map_support = self._scan_database_for_single_items(input_path)
        self.min_support_relative = int(ceil(minsupp * self.transaction_count))

        tree = FPTree()
        with open(input_path, "r", encoding="utf-8") as f:
            for raw in f:
                if not raw or raw == "\n": continue
                line = raw.strip()
                if not line or line[0] in "#%@": continue
                txn: List[int] = []
                for tok in line.split(" "):
                    it = int(tok)
                    if map_support.get(it, 0) >= self.min_support_relative:
                        txn.append(it)
                txn.sort(key=lambda it: (-map_support[it], it))
                tree.add_transaction(txn)

        tree.create_header_list(map_support)

        if len(tree.header_list) > 0:
            self.itemset_buffer = [0] * self.BUFFERS_SIZE
            self.fpnode_temp_buffer = [None] * self.BUFFERS_SIZE  # type: ignore
            self._fpgrowth(tree, self.itemset_buffer, 0, self.transaction_count, map_support)

        if self._writer is not None:
            self._writer.close()
            self._writer = None

        self.end_time = int(time.time() * 1000)
        MemoryLogger.get_instance().check_memory()
        return self.patterns

    def _fpgrowth(self, tree: FPTree, prefix: List[int], prefix_len: int, prefix_support: int, map_support: Dict[int, int]) -> None:
        if prefix_len == self.max_pattern_length:
            return

        single_path = True
        position = 0
        if len(tree.root.childs) > 1:
            single_path = False
        else:
            if len(tree.root.childs) == 1:
                current = tree.root.childs[0]
                while True:
                    if len(current.childs) > 1:
                        single_path = False
                        break
                    self.fpnode_temp_buffer[position] = current  # type: ignore
                    position += 1
                    if len(current.childs) == 0:
                        break
                    current = current.childs[0]

        if single_path:
            self._save_all_combinations_of_prefix_path(self.fpnode_temp_buffer, position, prefix, prefix_len)
            return

        for idx in range(len(tree.header_list) - 1, -1, -1):
            item = tree.header_list[idx]
            support = map_support[item]
            prefix[prefix_len] = item
            beta_support = min(prefix_support, support)
            self._save_itemset(prefix, prefix_len + 1, beta_support)

            if prefix_len + 1 < self.max_pattern_length:
                prefix_paths: List[List[FPNode]] = []
                path = tree.map_item_nodes.get(item)
                map_support_beta: Dict[int, int] = {}
                while path is not None:
                    if path.parent.item_id != -1:
                        pp: List[FPNode] = []
                        pp.append(path)
                        path_count = path.counter
                        parent = path.parent
                        while parent.item_id != -1:
                            pp.append(parent)
                            map_support_beta[parent.item_id] = map_support_beta.get(parent.item_id, 0) + path_count
                            parent = parent.parent
                        prefix_paths.append(pp)
                    path = path.node_link

                tree_beta = FPTree()
                for pp in prefix_paths:
                    tree_beta.add_prefix_path(pp, map_support_beta, self.min_support_relative)
                if len(tree_beta.root.childs) > 0:
                    tree_beta.create_header_list(map_support_beta)
                    self._fpgrowth(tree_beta, prefix, prefix_len + 1, beta_support, map_support_beta)

    def _save_all_combinations_of_prefix_path(self, fpnode_temp_buffer: List[Optional[FPNode]], position: int, prefix: List[int], prefix_len: int) -> None:
        for mask in range(1, 1 << position):
            new_len = prefix_len
            support = 0
            for j in range(position):
                if mask & (1 << j):
                    if new_len == self.max_pattern_length:
                        break
                    prefix[new_len] = fpnode_temp_buffer[j].item_id  # type: ignore
                    support = fpnode_temp_buffer[j].counter  # type: ignore
                    new_len += 1
            else:
                self._save_itemset(prefix, new_len, support)
                continue

    def _scan_database_for_single_items(self, input_path: str) -> Dict[int, int]:
        map_support: Dict[int, int] = {}
        with open(input_path, "r", encoding="utf-8") as f:
            for raw in f:
                if not raw or raw == "\n": continue
                line = raw.strip()
                if not line or line[0] in "#%@": continue
                for tok in line.split(" "):
                    item = int(tok)
                    map_support[item] = map_support.get(item, 0) + 1
                self.transaction_count += 1
        return map_support

    def _save_itemset(self, itemset: List[int], length: int, support: int) -> None:
        if length < self.min_pattern_length:
            return
        self.itemset_count += 1
        if self._writer is not None:
            buf = self.itemset_output_buffer  # type: ignore
            for i in range(length):
                buf[i] = itemset[i]
            buf[:length] = sorted(buf[:length])
            s = " ".join(str(buf[i]) for i in range(length))
            s += " #SUP: " + str(support)
            self._writer.write(s); self._writer.write("\n")
        else:
            arr = itemset[:length]
            arr.sort()
            iset = Itemset(arr)
            iset.set_absolute_support(support)
            self.patterns.addItemset(iset, length)  # type: ignore

    def print_stats(self) -> None:
        print("=============  FP-GROWTH 2.42 - STATS =============")
        duration = self.end_time - self.start_timestamp
        print(f" Transactions count from database : {self.transaction_count}")
        print(f" Max memory usage: {MemoryLogger.get_instance().get_max_memory()} mb ")
        print(f" Frequent itemsets count : {self.itemset_count}")
        print(f" Total time ~ {duration} ms")
        print("===================================================")

    def get_database_size(self) -> int:
        return self.transaction_count

    def set_maximum_pattern_length(self, length: int) -> None:
        self.max_pattern_length = length

    def set_minimum_pattern_length(self, length: int) -> None:
        self.min_pattern_length = length

    # Java aliases
    setMaximumPatternLength = set_maximum_pattern_length
    setMinimumPatternLength = set_minimum_pattern_length
    getDatabaseSize = get_database_size
    printStats = print_stats


# ---------------------------------------------------------------------------
# RP-Tree structures
# ---------------------------------------------------------------------------

class RPNode:
    def __init__(self) -> None:
        self.item_id: int = -1
        self.counter: int = 1
        self.parent: Optional["RPNode"] = None
        self.childs: List["RPNode"] = []
        self.node_link: Optional["RPNode"] = None

    def get_child_with_id(self, id_: int) -> Optional["RPNode"]:
        for child in self.childs:
            if child.item_id == id_:
                return child
        return None

    def to_string(self, indent: str) -> str:
        out = [f"{self.item_id} (count={self.counter})\n"]
        new_indent = indent + "   "
        for child in self.childs:
            out.append(new_indent + child.to_string(new_indent))
        return "".join(out)

    def __str__(self) -> str:
        return str(self.item_id)


class RPTree:
    def __init__(self) -> None:
        self.header_list: List[int] = []
        self.map_item_nodes: Dict[int, RPNode] = {}
        self.map_item_last_node: Dict[int, RPNode] = {}
        self.root: RPNode = RPNode()

    def add_transaction(self, transaction: List[int]) -> None:
        current = self.root
        for item in transaction:
            child = current.get_child_with_id(item)
            if child is None:
                new_node = RPNode()
                new_node.item_id = item
                new_node.parent = current
                current.childs.append(new_node)
                current = new_node
                self._fix_node_links(item, new_node)
            else:
                child.counter += 1
                current = child

    def _fix_node_links(self, item: int, new_node: RPNode) -> None:
        last = self.map_item_last_node.get(item)
        if last is not None:
            last.node_link = new_node
        self.map_item_last_node[item] = new_node
        if item not in self.map_item_nodes:
            self.map_item_nodes[item] = new_node

    def add_prefix_path(self, prefix_path: List[RPNode], map_support_beta: Dict[int, int], relative_minsupp: int, relative_min_rare_supp: int) -> None:
        path_count = prefix_path[0].counter
        current = self.root
        for i in range(len(prefix_path) - 1, 0, -1):
            node = prefix_path[i]
            supp = map_support_beta.get(node.item_id, 0)
            if supp < relative_minsupp and supp >= relative_min_rare_supp:
                child = current.get_child_with_id(node.item_id)
                if child is None:
                    new_node = RPNode()
                    new_node.item_id = node.item_id
                    new_node.parent = current
                    new_node.counter = path_count
                    current.childs.append(new_node)
                    current = new_node
                    self._fix_node_links(node.item_id, new_node)
                else:
                    child.counter += path_count
                    current = child

    def create_header_list(self, map_support: Dict[int, int]) -> None:
        self.header_list = list(self.map_item_nodes.keys())
        self.header_list.sort(key=lambda it: (-map_support[it], it))

    def __str__(self) -> str:
        temp = "F"
        temp += f" HeaderList: {self.header_list}\n"
        temp += self.root.to_string("")
        return temp


# ---------------------------------------------------------------------------
# RP-Growth algorithm
# ---------------------------------------------------------------------------

class AlgoRPGrowth:
    BUFFERS_SIZE = 2000

    def __init__(self) -> None:
        self.start_timestamp: int = 0
        self.end_time: int = 0
        self.transaction_count: int = 0
        self.itemset_count: int = 0
        self.min_rare_support_relative: int = 0
        self.min_support_relative: int = 0
        self.max_pattern_length: int = 1000
        self.min_pattern_length: int = 0
        self._writer: Optional[open] = None
        self.patterns: Optional[Itemsets] = None
        self.itemset_buffer: Optional[List[int]] = None
        self.rpnode_temp_buffer: Optional[List[Optional[RPNode]]] = None
        self.itemset_output_buffer: Optional[List[int]] = None

    def run_algorithm(self, input_path: str, output_path: Optional[str], minsupp: float, minraresupp: float) -> Optional[Itemsets]:
        self.start_timestamp = int(time.time() * 1000)
        self.itemset_count = 0
        self.transaction_count = 0

        MemoryLogger.get_instance().reset()
        MemoryLogger.get_instance().check_memory()

        if output_path is None:
            self._writer = None
            self.patterns = Itemsets("RARE ITEMSETS")
        else:
            self.patterns = None
            self._writer = open(output_path, "w", encoding="utf-8", newline="\n")
            self.itemset_output_buffer = [0] * self.BUFFERS_SIZE

        map_support = self._scan_database_for_single_items(input_path)
        self.min_rare_support_relative = int(ceil(minraresupp * self.transaction_count))
        self.min_support_relative = int(ceil(minsupp * self.transaction_count))

        tree = RPTree()
        with open(input_path, "r", encoding="utf-8") as f:
            for raw in f:
                if not raw or raw == "\n": continue
                line = raw.strip()
                if not line or line[0] in "#%@": continue
                txn: List[int] = []
                for tok in line.split(" "):
                    item = int(tok)
                    if map_support.get(item, 0) >= self.min_rare_support_relative:
                        txn.append(item)
                txn.sort(key=lambda it: (-map_support[it], it))
                if txn:
                    last_item = txn[-1]
                    last_count = map_support[last_item]
                    if last_count < self.min_support_relative:
                        tree.add_transaction(txn)

        tree.create_header_list(map_support)

        if len(tree.header_list) > 0:
            self.itemset_buffer = [0] * self.BUFFERS_SIZE
            self.rpnode_temp_buffer = [None] * self.BUFFERS_SIZE
            self._rpgrowth(tree, self.itemset_buffer, 0, self.transaction_count, map_support)

        if self._writer is not None:
            self._writer.close()
            self._writer = None

        self.end_time = int(time.time() * 1000)
        MemoryLogger.get_instance().check_memory()
        return self.patterns

    def _rpgrowth(self, tree: RPTree, prefix: List[int], prefix_len: int, prefix_support: int, map_support: Dict[int, int]) -> None:
        if prefix_len == self.max_pattern_length:
            return

        single_path = True
        position = 0
        if len(tree.root.childs) > 1:
            single_path = False
        else:
            if len(tree.root.childs) == 1:
                current = tree.root.childs[0]
                while True:
                    if len(current.childs) > 1:
                        single_path = False
                        break
                    self.rpnode_temp_buffer[position] = current
                    position += 1
                    if len(current.childs) == 0:
                        break
                    current = current.childs[0]

        if single_path and prefix_len > 0:
            self._save_all_combinations_of_prefix_path(self.rpnode_temp_buffer, position, prefix, prefix_len)
            return

        for idx in range(len(tree.header_list) - 1, -1, -1):
            item = tree.header_list[idx]
            support = map_support[item]
            if (prefix_len == 0) and (support >= self.min_support_relative):
                return
            prefix[prefix_len] = item
            beta_support = min(prefix_support, support)

            if (prefix_len > 0) or (support < self.min_support_relative):
                self._save_itemset(prefix, prefix_len + 1, beta_support)

            if prefix_len + 1 < self.max_pattern_length:
                prefix_paths: List[List[RPNode]] = []
                path = tree.map_item_nodes.get(item)
                map_support_beta: Dict[int, int] = {}

                while path is not None:
                    if path.parent.item_id != -1:
                        pp: List[RPNode] = []
                        pp.append(path)
                        path_count = path.counter
                        parent = path.parent
                        while parent.item_id != -1:
                            pp.append(parent)
                            map_support_beta[parent.item_id] = map_support_beta.get(parent.item_id, 0) + path_count
                            parent = parent.parent
                        prefix_paths.append(pp)
                    path = path.node_link

                tree_beta = RPTree()
                for pp in prefix_paths:
                    tree_beta.add_prefix_path(pp, map_support_beta, self.min_support_relative, self.min_rare_support_relative)

                if len(tree_beta.root.childs) > 0:
                    tree_beta.create_header_list(map_support_beta)
                    self._rpgrowth(tree_beta, prefix, prefix_len + 1, beta_support, map_support_beta)

    def _save_all_combinations_of_prefix_path(self, rpnode_temp_buffer: List[Optional[RPNode]], position: int, prefix: List[int], prefix_len: int) -> None:
        if prefix_len == 0:
            return
        for mask in range(1, 1 << position):
            new_len = prefix_len
            support = 0
            for j in range(position):
                if mask & (1 << j):
                    if new_len == self.max_pattern_length:
                        break
                    prefix[new_len] = rpnode_temp_buffer[j].item_id  # type: ignore
                    support = rpnode_temp_buffer[j].counter  # type: ignore
                    new_len += 1
            else:
                self._save_itemset(prefix, new_len, support)
                continue

    def _scan_database_for_single_items(self, input_path: str) -> Dict[int, int]:
        map_support: Dict[int, int] = {}
        with open(input_path, "r", encoding="utf-8") as f:
            for raw in f:
                if not raw or raw == "\n": continue
                line = raw.strip()
                if not line or line[0] in "#%@": continue
                for tok in line.split(" "):
                    item = int(tok)
                    map_support[item] = map_support.get(item, 0) + 1
                self.transaction_count += 1
        return map_support

    def _save_itemset(self, itemset: List[int], length: int, support: int) -> None:
        if length < self.min_pattern_length:
            return
        self.itemset_count += 1
        if self._writer is not None:
            buf = self.itemset_output_buffer  # type: ignore
            for i in range(length):
                buf[i] = itemset[i]
            buf[:length] = sorted(buf[:length])
            s = " ".join(str(buf[i]) for i in range(length))
            s += " #SUP: " + str(support)
            self._writer.write(s); self._writer.write("\n")
        else:
            arr = itemset[:length]
            arr.sort()
            iset = Itemset(arr)
            iset.set_absolute_support(support)
            self.patterns.addItemset(iset, length)  # type: ignore

    def print_stats(self) -> None:
        print("=============  RP-GROWTH 2.38 - STATS =============")
        duration = self.end_time - self.start_timestamp
        print(f" Transactions count from database : {self.transaction_count}")
        print(f" Max memory usage: {MemoryLogger.get_instance().get_max_memory()} mb ")
        print(f" Rare itemsets count : {self.itemset_count}")
        print(f" Total time ~ {duration} ms")
        print("===================================================")

    def get_database_size(self) -> int:
        return self.transaction_count

    def set_maximum_pattern_length(self, length: int) -> None:
        self.max_pattern_length = length

    def set_minimum_pattern_length(self, min_pattern_length: int) -> None:
        self.min_pattern_length = min_pattern_length

    # Java aliases
    setMaximumPatternLength = set_maximum_pattern_length
    setMinimumPatternLength = set_minimum_pattern_length
    getDatabaseSize = get_database_size
    printStats = print_stats


# ---------------------------------------------------------------------------
# Command-line interface (mirrors Java MainTest* examples)
# ---------------------------------------------------------------------------

def _cli_fp_save_file(args: argparse.Namespace) -> None:
    algo = AlgoFPGrowth()
    if args.maxlen is not None: algo.set_maximum_pattern_length(args.maxlen)
    if args.minlen is not None: algo.set_minimum_pattern_length(args.minlen)
    algo.run_algorithm(args.input, args.output, args.minsup)
    algo.print_stats()

def _cli_fp_save_mem(args: argparse.Namespace) -> None:
    algo = AlgoFPGrowth()
    if args.maxlen is not None: algo.set_maximum_pattern_length(args.maxlen)
    if args.minlen is not None: algo.set_minimum_pattern_length(args.minlen)
    patterns = algo.run_algorithm(args.input, None, args.minsup)
    algo.print_stats()
    patterns.printItemsets(algo.get_database_size())

def _cli_rp_save_file(args: argparse.Namespace) -> None:
    algo = AlgoRPGrowth()
    if args.maxlen is not None: algo.set_maximum_pattern_length(args.maxlen)
    if args.minlen is not None: algo.set_minimum_pattern_length(args.minlen)
    algo.run_algorithm(args.input, args.output, args.minsup, args.minraresup)
    algo.print_stats()

def _cli_rp_save_mem(args: argparse.Namespace) -> None:
    algo = AlgoRPGrowth()
    if args.maxlen is not None: algo.set_maximum_pattern_length(args.maxlen)
    if args.minlen is not None: algo.set_minimum_pattern_length(args.minlen)
    patterns = algo.run_algorithm(args.input, None, args.minsup, args.minraresup)
    algo.print_stats()
    patterns.printItemsets(algo.get_database_size())


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="FP-Growth & RP-Growth (SPMF-style) in one file.")
    sub = p.add_subparsers(dest="cmd", required=True)

    fp_file = sub.add_parser("fp_save_file", help="Run FP-Growth and save to file")
    fp_file.add_argument("input")
    fp_file.add_argument("output")
    fp_file.add_argument("--minsup", type=float, default=0.4)
    fp_file.add_argument("--maxlen", type=int, default=None)
    fp_file.add_argument("--minlen", type=int, default=None)
    fp_file.set_defaults(func=_cli_fp_save_file)

    fp_mem = sub.add_parser("fp_save_mem", help="Run FP-Growth and keep in memory")
    fp_mem.add_argument("input")
    fp_mem.add_argument("--minsup", type=float, default=0.4)
    fp_mem.add_argument("--maxlen", type=int, default=None)
    fp_mem.add_argument("--minlen", type=int, default=None)
    fp_mem.set_defaults(func=_cli_fp_save_mem)

    rp_file = sub.add_parser("rp_save_file", help="Run RP-Growth and save to file")
    rp_file.add_argument("input")
    rp_file.add_argument("output")
    rp_file.add_argument("--minsup", type=float, default=0.6)
    rp_file.add_argument("--minraresup", type=float, default=0.1)
    rp_file.add_argument("--maxlen", type=int, default=None)
    rp_file.add_argument("--minlen", type=int, default=None)
    rp_file.set_defaults(func=_cli_rp_save_file)

    rp_mem = sub.add_parser("rp_save_mem", help="Run RP-Growth and keep in memory")
    rp_mem.add_argument("input")
    rp_mem.add_argument("--minsup", type=float, default=0.6)
    rp_mem.add_argument("--minraresup", type=float, default=0.1)
    rp_mem.add_argument("--maxlen", type=int, default=None)
    rp_mem.add_argument("--minlen", type=int, default=None)
    rp_mem.set_defaults(func=_cli_rp_save_mem)

    return p


if __name__ == "__main__":
    import sys, os

    # If no args: run RP-Growth like the Java MainTestRPGrowth_saveToFile
    # using files that live in the SAME FOLDER as this script.
    if len(sys.argv) == 1:
        base = os.path.dirname(os.path.abspath(__file__))
        input_path = os.path.join(base, "contextRP.txt")
        output_path = os.path.join(base, "rpgrowth_outputs.txt")

        if not os.path.exists(input_path):
            print(f'Error: expected dataset at "{input_path}" but it was not found.')
            sys.exit(1)

        algo = AlgoRPGrowth()
        algo.run_algorithm(input_path, output_path, 0.7, 0.1)
        algo.print_stats()
        print(f'Wrote rare itemsets to "{output_path}"')
        sys.exit(0)

    # Otherwise: use the CLI subcommands
    parser = _build_parser()
    args = parser.parse_args()
    args.func(args)


