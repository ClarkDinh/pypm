# lapin.py
# Single-file Python implementation of the LAPIN algorithm.

from __future__ import annotations

import math
import os
import time
from bisect import bisect_left
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set


# ----------------------------------------------------------------------
# MemoryLogger (singleton)
# ----------------------------------------------------------------------

try:
    import psutil  # optional
except ImportError:
    psutil = None


class MemoryLogger:
    _instance: "MemoryLogger" = None  # type: ignore

    def __init__(self) -> None:
        self.max_memory: float = 0.0

    @classmethod
    def get_instance(cls) -> "MemoryLogger":
        if cls._instance is None:
            cls._instance = MemoryLogger()
        return cls._instance

    def reset(self) -> None:
        self.max_memory = 0.0

    def get_max_memory(self) -> float:
        return self.max_memory

    def check_memory(self) -> float:
        current = self._get_current_memory_mb()
        if current > self.max_memory:
            self.max_memory = current
        return current

    def _get_current_memory_mb(self) -> float:
        # Java uses JVM heap; Python approximation using process RSS (if available).
        if psutil is not None:
            p = psutil.Process(os.getpid())
            return p.memory_info().rss / 1024.0 / 1024.0
        return 0.0  # safe fallback


# ----------------------------------------------------------------------
# AbstractTriangularMatrix + SparseTriangularMatrix
# ----------------------------------------------------------------------

class AbstractTriangularMatrix:
    def increment_count(self, i: int, j: int) -> None:
        raise NotImplementedError

    def get_support_for_items(self, i: int, j: int) -> int:
        raise NotImplementedError

    def set_support(self, i: int, j: int, support: int) -> None:
        raise NotImplementedError


class SparseTriangularMatrix(AbstractTriangularMatrix):
    """
    Faithful to Java: stores pairs under min(i,j) then max(i,j).
    """

    def __init__(self, item_count: int = 0) -> None:
        self.matrix: Dict[int, Dict[int, int]] = {}

    def increment_count(self, i: int, j: int) -> None:
        a, b = (i, j) if i < j else (j, i)
        row = self.matrix.get(a)
        if row is None:
            self.matrix[a] = {b: 1}
            return
        row[b] = row.get(b, 0) + 1

    def get_support_for_items(self, i: int, j: int) -> int:
        a, b = (i, j) if i < j else (j, i)
        row = self.matrix.get(a)
        if row is None:
            return 0
        return row.get(b, 0)

    def set_support(self, i: int, j: int, support: int) -> None:
        a, b = (i, j) if i < j else (j, i)
        row = self.matrix.get(a)
        if row is None:
            row = {}
            self.matrix[a] = row
        row[b] = int(support)

    # Java-style aliases (not strictly needed, but harmless)
    def incrementCount(self, i: int, j: int) -> None:
        self.increment_count(i, j)

    def getSupportForItems(self, i: int, j: int) -> int:
        return self.get_support_for_items(i, j)

    def setSupport(self, i: int, j: int, support: int) -> None:
        self.set_support(i, j, support)

    def __str__(self) -> str:
        lines = []
        for i in sorted(self.matrix.keys()):
            row = self.matrix[i]
            cols = " ".join(str(row[j]) for j in sorted(row.keys()))
            lines.append(f"{i}: {cols}")
        return "\n".join(lines) + ("\n" if lines else "")


# ----------------------------------------------------------------------
# BitSet-like (used inside Table vectors)
# ----------------------------------------------------------------------

class BitsetLike:
    """
    Minimal BitSet behavior needed by the algorithm.
    Backed by a Python set of indices set to 1.
    """

    __slots__ = ("_bits",)

    def __init__(self) -> None:
        self._bits: Set[int] = set()

    def set(self, index: int) -> None:
        self._bits.add(int(index))

    def get(self, index: int) -> bool:
        return int(index) in self._bits

    def clone(self) -> "BitsetLike":
        b = BitsetLike()
        b._bits = self._bits.copy()
        return b

    def __str__(self) -> str:
        # Java BitSet prints like "{1, 3, 10}"
        if not self._bits:
            return "{}"
        return "{" + ", ".join(str(x) for x in sorted(self._bits)) + "}"


# ----------------------------------------------------------------------
# Table + PositionVector
# ----------------------------------------------------------------------

class PositionVector:
    def __init__(self, position: int, bitset: BitsetLike) -> None:
        self.bitset = bitset
        self.position = int(position)

    def __str__(self) -> str:
        return f"{self.position} {self.bitset}"


class Table:
    def __init__(self) -> None:
        self.position_vectors: List[PositionVector] = []

    def add(self, vector: PositionVector) -> None:
        self.position_vectors.append(vector)

    def __str__(self) -> str:
        out = []
        for v in self.position_vectors:
            out.append(" " + str(v))
            out.append("\n")
        return "".join(out)


# ----------------------------------------------------------------------
# SEPositionList
# ----------------------------------------------------------------------

def _binary_search_int(a: List[int], x: int) -> int:
    """
    Equivalent to Java Arrays.binarySearch(int[], key).
    """
    i = bisect_left(a, x)
    if i != len(a) and a[i] == x:
        return i
    return -(i + 1)


class SEPositionList:
    def __init__(self, items_already_seen: Set[int]) -> None:
        self.list_items: List[int] = sorted(int(x) for x in items_already_seen)
        self.list_positions: List[List[int]] = [[] for _ in range(len(self.list_items))]

    def register(self, item: int, position: int) -> None:
        idx = _binary_search_int(self.list_items, int(item))
        self.list_positions[idx].append(int(position))

    def get_list_for_item(self, item: int) -> Optional[List[int]]:
        idx = _binary_search_int(self.list_items, int(item))
        if idx < 0:
            return None
        return self.list_positions[idx]

    def __str__(self) -> str:
        out = []
        for i in range(len(self.list_items)):
            out.append("  position list of item: ")
            out.append(str(self.list_items[i]))
            out.append("  is: ")
            for pos in self.list_positions[i]:
                out.append(str(pos))
                out.append(" ")
            out.append("\n")
        return "".join(out)


# ----------------------------------------------------------------------
# PairWithList + IEPositionList
# ----------------------------------------------------------------------

class PairWithList:
    __slots__ = ("item1", "item2", "list_positions")

    def __init__(self, item1: int, item2: int) -> None:
        self.item1 = int(item1)
        self.item2 = int(item2)
        self.list_positions: Optional[List[int]] = None

    def create_position_list(self) -> None:
        self.list_positions = []

    def compare_to(self, other: "PairWithList") -> int:
        val = self.item1 - other.item1
        if val == 0:
            val = self.item2 - other.item2
        return val

    def sort_key(self):
        return (self.item1, self.item2)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PairWithList):
            return False
        return self.item1 == other.item1 and self.item2 == other.item2


def _binary_search_pairs(a: List[PairWithList], key: PairWithList) -> int:
    """
    Equivalent to Java Collections.binarySearch(list, key) for PairWithList ordering.
    """
    lo, hi = 0, len(a) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        cmp = a[mid].compare_to(key)
        if cmp < 0:
            lo = mid + 1
        elif cmp > 0:
            hi = mid - 1
        else:
            return mid
    return -(lo + 1)


class IEPositionList:
    def __init__(self) -> None:
        self.list_pairs: List[PairWithList] = []

    def sort(self) -> None:
        self.list_pairs.sort(key=lambda p: p.sort_key())

    def register(self, item1: int, item2: int, position: int) -> None:
        the_pair = PairWithList(item1, item2)
        idx = _binary_search_pairs(self.list_pairs, the_pair)
        if idx < 0:
            self.list_pairs.append(the_pair)
            the_pair.create_position_list()
            the_pair.list_positions.append(int(position))  # type: ignore[union-attr]
        else:
            existing = self.list_pairs[idx]
            existing.list_positions.append(int(position))  # type: ignore[union-attr]

    def get_list_for_pair(self, item1: int, item2: int) -> Optional[List[int]]:
        the_pair = PairWithList(item1, item2)
        idx = _binary_search_pairs(self.list_pairs, the_pair)
        if idx < 0:
            return None
        return self.list_pairs[idx].list_positions  # type: ignore[return-value]

    def __str__(self) -> str:
        out = []
        for p in self.list_pairs:
            out.append("  position list of pair: {")
            out.append(str(p.item1))
            out.append(",")
            out.append(str(p.item2))
            out.append("}  is: ")
            for pos in (p.list_positions or []):
                out.append(str(pos))
                out.append(" ")
            out.append("\n")
        return "".join(out)


# ----------------------------------------------------------------------
# Prefix
# ----------------------------------------------------------------------

class Prefix:
    def __init__(self) -> None:
        self.itemsets: List[List[int]] = []

    def clone_sequence(self) -> "Prefix":
        seq = Prefix()
        for itemset in self.itemsets:
            seq.itemsets.append([int(x) for x in itemset])
        return seq

    def size(self) -> int:
        return len(self.itemsets)

    def print(self) -> None:
        print(str(self), end="")

    def __str__(self) -> str:
        parts: List[str] = []
        for itemset in self.itemsets:
            parts.append("(")
            for item in itemset:
                parts.append(str(item))
                parts.append(" ")
            parts.append(")")
        parts.append("    ")
        return "".join(parts)


# ----------------------------------------------------------------------
# Helper: Java-like binarySearch for List[int] (Collections.binarySearch)
# ----------------------------------------------------------------------

def _java_binary_search(sorted_list: List[int], key: int) -> int:
    lo, hi = 0, len(sorted_list) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        v = sorted_list[mid]
        if v < key:
            lo = mid + 1
        elif v > key:
            hi = mid - 1
        else:
            return mid
    return -(lo) - 1


# ----------------------------------------------------------------------
# AlgoLAPIN_LCI
# ----------------------------------------------------------------------

class AlgoLAPIN_LCI:
    # Debug flag
    DEBUG = False

    @dataclass(frozen=True)
    class Position:
        sid: int
        position: int  # Java short

    def __init__(self) -> None:
        self.start_time: int = 0
        self.end_time: int = 0
        self.pattern_count: int = 0

        self.minsup: int = 0

        self._writer = None

        self.tables: List[Table] = []
        self.se_position_list: List[SEPositionList] = []
        self.ie_position_list: List[IEPositionList] = []

        self.matrix_pair_count: SparseTriangularMatrix = SparseTriangularMatrix()

        self.input: Optional[str] = None

    def run_algorithm(self, input_path: str, output_file_path: str, minsup_rel: float) -> None:
        self.input = input_path
        self.pattern_count = 0

        MemoryLogger.get_instance().reset()
        self.start_time = int(time.time() * 1000)

        self._writer = open(output_file_path, "w", encoding="utf-8", newline="\n")
        try:
            self._lapin(input_path, minsup_rel)
        finally:
            self.end_time = int(time.time() * 1000)
            if self._writer is not None:
                self._writer.close()
                self._writer = None

    def _lapin(self, input_path: str, minsup_rel: float) -> None:
        if self.DEBUG:
            print("=== First database scan to count number of sequences and support of single items ===")

        sequence_count = 0
        largest_item_id = 0
        map_item_first_occurrences: Dict[int, List[AlgoLAPIN_LCI.Position]] = {}

        # FIRST SCAN
        with open(input_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.rstrip("\n\r")
                if not line:
                    continue
                if line[0] in ("#", "%", "@"):
                    continue

                items_already_seen: Set[int] = set()
                itemset_id = 0

                for token in line.split(" "):
                    if token == "-1":
                        itemset_id += 1
                    elif token == "-2":
                        pass
                    elif token == "":
                        continue
                    else:
                        item = int(token)
                        if item not in items_already_seen:
                            lst = map_item_first_occurrences.get(item)
                            if lst is None:
                                lst = []
                                map_item_first_occurrences[item] = lst
                            lst.append(self.Position(sequence_count, itemset_id))
                            items_already_seen.add(item)
                            if item > largest_item_id:
                                largest_item_id = item

                sequence_count += 1

        self.tables = [Table() for _ in range(sequence_count)]

        self.minsup = int(math.ceil(minsup_rel * sequence_count))
        if self.minsup == 0:
            self.minsup = 1

        if self.DEBUG:
            print("Number of items:", len(map_item_first_occurrences))
            print("Sequence count: ", sequence_count)
            print("Abs. minsup:", self.minsup, "sequences")
            print("Rel. minsup:", minsup_rel, "%")
            print("=== Determining the frequent items ===")

        frequent_items: List[int] = []
        for item, border in map_item_first_occurrences.items():
            if len(border) >= self.minsup:
                self._save_pattern_single_item(item, len(border))
                frequent_items.append(item)
                if self.DEBUG:
                    print(f" Item {item} is frequent with support = {len(border)}")

        if self.DEBUG:
            print("=== Second database scan to construct item-is-exist tables ===")

        frequent_items.sort()

        # SECOND SCAN
        self.matrix_pair_count = SparseTriangularMatrix(largest_item_id + 1)
        self.se_position_list = [None] * sequence_count  # type: ignore
        self.ie_position_list = [None] * sequence_count  # type: ignore

        with open(input_path, "r", encoding="utf-8", errors="replace") as f:
            current_sequence_id = 0
            for line in f:
                line = line.rstrip("\n\r")
                if not line:
                    continue
                if line[0] in ("#", "%", "@"):
                    continue

                matrix_pair_last_seen_in_sid = SparseTriangularMatrix(largest_item_id + 1)

                # positionCount = -1; count '-' chars
                position_count = -1
                for ch in line:
                    if ch == "-":
                        position_count += 1

                items_already_seen: Set[int] = set()
                table = Table()
                current_bitset = BitsetLike()

                seen_new_item = False
                tokens = line.split(" ")
                current_position = position_count
                current_itemset: List[int] = []

                for i in range(len(tokens) - 1, -1, -1):
                    token = tokens[i]

                    if token == "-1":
                        # update pair counts within current_itemset
                        for k in range(len(current_itemset)):
                            item1 = current_itemset[k]
                            for m in range(k + 1, len(current_itemset)):
                                item2 = current_itemset[m]
                                sid_val = matrix_pair_last_seen_in_sid.get_support_for_items(item1, item2)
                                if sid_val != current_sequence_id + 1:
                                    self.matrix_pair_count.increment_count(item1, item2)
                                    matrix_pair_last_seen_in_sid.set_support(item1, item2, current_sequence_id + 1)

                        current_itemset.clear()
                        current_position -= 1

                        if seen_new_item:
                            table.add(PositionVector(current_position, current_bitset.clone()))

                    elif token == "-2":
                        pass
                    elif token == "":
                        continue
                    else:
                        item = int(token)
                        if len(map_item_first_occurrences.get(item, [])) >= self.minsup:
                            if item not in items_already_seen:
                                seen_new_item = True
                                items_already_seen.add(item)
                                current_bitset.set(item)
                            current_itemset.append(item)

                # update pair counts for first position
                for k in range(len(current_itemset)):
                    item1 = current_itemset[k]
                    for m in range(k + 1, len(current_itemset)):
                        item2 = current_itemset[m]
                        sid_val = matrix_pair_last_seen_in_sid.get_support_for_items(item1, item2)
                        if sid_val != current_sequence_id + 1:
                            self.matrix_pair_count.increment_count(item1, item2)
                            matrix_pair_last_seen_in_sid.set_support(item1, item2, current_sequence_id + 1)

                if seen_new_item:
                    table.add(PositionVector(-1, current_bitset.clone()))

                self.se_position_list[current_sequence_id] = SEPositionList(items_already_seen)
                self.ie_position_list[current_sequence_id] = IEPositionList()

                if self.DEBUG:
                    print(f"Table for sequence {current_sequence_id} : {line}")
                    print(table)

                self.tables[current_sequence_id] = table
                current_sequence_id += 1

        # THIRD SCAN
        with open(input_path, "r", encoding="utf-8", errors="replace") as f:
            current_sequence_id = 0
            for line in f:
                line = line.rstrip("\n\r")
                if not line:
                    continue
                if line[0] in ("#", "%", "@"):
                    continue

                tokens = line.split(" ")
                current_itemset: List[int] = []
                itemset_id = 0

                for token in tokens:
                    if token == "-1":
                        if len(current_itemset) > 1:
                            for k in range(len(current_itemset)):
                                item1 = current_itemset[k]
                                for m in range(k + 1, len(current_itemset)):
                                    item2 = current_itemset[m]
                                    support = self.matrix_pair_count.get_support_for_items(item1, item2)
                                    if support >= self.minsup:
                                        self.ie_position_list[current_sequence_id].register(item1, item2, itemset_id)

                        itemset_id += 1
                        current_itemset.clear()

                    elif token == "-2":
                        pass
                    elif token == "":
                        continue
                    else:
                        item = int(token)
                        if len(map_item_first_occurrences.get(item, [])) >= self.minsup:
                            self.se_position_list[current_sequence_id].register(item, itemset_id)
                            current_itemset.append(item)

                if self.DEBUG:
                    print(f"SE Position list for sequence {current_sequence_id}")
                    print(self.se_position_list[current_sequence_id])
                    print(f"IE Position list for sequence {current_sequence_id}")
                    print(self.ie_position_list[current_sequence_id])

                self.ie_position_list[current_sequence_id].sort()
                current_sequence_id += 1

        if self.DEBUG:
            print("=== Starting sequential pattern generation ===")

        # pattern generation
        for i in range(len(frequent_items)):
            item1 = frequent_items[i]
            item1_border = map_item_first_occurrences[item1]

            if self.DEBUG:
                print(f"=== Considering item {item1}")
                print(f"  Border of {item1}")
                for pos in item1_border:
                    print(f"    seq: {pos.sid}    itemset: {pos.position}")

            if len(item1_border) >= self.minsup:
                prefix = Prefix()
                prefix.itemsets.append([item1])
                self._gen_patterns(prefix, item1_border, frequent_items, frequent_items, item1, True)

            for k in range(i + 1, len(frequent_items)):
                item2 = frequent_items[k]
                support = self.matrix_pair_count.get_support_for_items(item1, item2)

                if support >= self.minsup:
                    item2_border = map_item_first_occurrences[item2]
                    ie12_border: List[AlgoLAPIN_LCI.Position] = []

                    border_to_use = item2_border if len(item2_border) < len(item1_border) else item1_border

                    for seq_pos in border_to_use:
                        sid = seq_pos.sid
                        list_pos1 = self.se_position_list[sid].get_list_for_item(item1)
                        list_pos2 = self.se_position_list[sid].get_list_for_item(item2)
                        if list_pos1 is None or list_pos2 is None:
                            continue

                        idx1 = 0
                        idx2 = 0
                        while idx1 < len(list_pos1) and idx2 < len(list_pos2):
                            p1 = list_pos1[idx1]
                            p2 = list_pos2[idx2]
                            if p1 < p2:
                                idx1 += 1
                            elif p1 > p2:
                                idx2 += 1
                            else:
                                ie12_border.append(self.Position(sid, p1))
                                break

                    if self.DEBUG:
                        print(f"=== Considering the 2-IE sequence {{{item1},{item2}}}  with support {support}")
                        print(f"  Border of {{{item1},{item2}}}")
                        for pos in ie12_border:
                            print(f"    seq: {pos.sid}    itemset: {pos.position}")

                    prefix = Prefix()
                    prefix.itemsets.append([item1, item2])
                    self._save_pattern_prefix(prefix, support)
                    self._gen_patterns(prefix, ie12_border, frequent_items, frequent_items, item2, False)

        MemoryLogger.get_instance().check_memory()

    def _gen_patterns(
        self,
        prefix: Prefix,
        prefix_border: List["AlgoLAPIN_LCI.Position"],
        sn: List[int],
        in_items: List[int],
        has_to_be_greater_than_for_i_step: int,
        do_not_perform_i_extensions: bool,
    ) -> None:
        # ===== S-STEPS =====
        s_temp: List[int] = []
        s_temp_support: List[int] = []

        for item in sn:
            support = self._calculate_support_s_step(item, prefix_border)
            if support >= self.minsup:
                s_temp.append(item)
                s_temp_support.append(support)

        for k in range(len(s_temp)):
            item = s_temp[k]
            prefix_s = prefix.clone_sequence()
            prefix_s.itemsets.append([item])

            self._save_pattern_prefix(prefix_s, s_temp_support[k])

            new_border = self._recalculate_border_for_s_extension(prefix_border, item)
            self._gen_patterns(prefix_s, new_border, s_temp, s_temp, item, False)

        if do_not_perform_i_extensions:
            return

        # ===== I-STEPS =====
        i_temp: List[int] = []
        i_temp_border: List[List[AlgoLAPIN_LCI.Position]] = []

        idx = _java_binary_search(in_items, has_to_be_greater_than_for_i_step)
        # Java expects idx >= 0 here in practice.
        for i in range(idx, len(in_items)):
            item = in_items[i]

            last_itemset = prefix.itemsets[-1]
            will_add_second_item = (len(last_itemset) == 1)

            support_est = self._estimate_support_i_step(item, prefix_border)
            if support_est >= self.minsup:
                new_border = self._recalculate_border_for_i_extension(
                    last_itemset,
                    prefix_border,
                    has_to_be_greater_than_for_i_step,
                    item,
                    will_add_second_item,
                )
                if len(new_border) >= self.minsup:
                    i_temp.append(item)
                    i_temp_border.append(new_border)

        for k in range(len(i_temp)):
            item = i_temp[k]
            prefix_i = prefix.clone_sequence()
            prefix_i.itemsets[-1].append(item)

            new_border = i_temp_border[k]
            self._save_pattern_prefix(prefix_i, len(new_border))
            self._gen_patterns(prefix_i, new_border, s_temp, i_temp, item, False)

        MemoryLogger.get_instance().check_memory()

    def _recalculate_border_for_i_extension(
        self,
        prefix_last_itemset: List[int],
        prefix_border: List["AlgoLAPIN_LCI.Position"],
        item1: int,
        item2: int,
        will_add_second_item: bool,
    ) -> List["AlgoLAPIN_LCI.Position"]:
        new_border: List[AlgoLAPIN_LCI.Position] = []

        for prev in prefix_border:
            sid = prev.sid
            prev_itemset_id = prev.position
            position_lists = self.ie_position_list[sid]

            list_positions = position_lists.get_list_for_pair(item1, item2)
            if list_positions is not None:
                for pos in list_positions:
                    if pos >= prev_itemset_id:
                        if will_add_second_item is False:
                            plists = self.se_position_list[sid]
                            # labeled-continue equivalent
                            ok = True
                            for x in range(len(prefix_last_itemset) - 1):
                                item_x = prefix_last_itemset[x]
                                plist_x = plists.get_list_for_item(item_x)
                                if plist_x is None or _java_binary_search(plist_x, pos) < 0:
                                    ok = False
                                    break
                            if not ok:
                                continue
                        new_border.append(self.Position(sid, pos))
                        break

        return new_border

    def _estimate_support_i_step(self, item: int, item_border: List["AlgoLAPIN_LCI.Position"]) -> int:
        support = 0
        for pos in item_border:
            table = self.tables[pos.sid]
            for vector in table.position_vectors:
                if vector.position < pos.position:
                    if vector.bitset.get(item):
                        support += 1
                    break
        return support

    def _calculate_support_s_step(self, item: int, item_border: List["AlgoLAPIN_LCI.Position"]) -> int:
        support = 0
        for pos in item_border:
            table = self.tables[pos.sid]
            n = len(table.position_vectors)
            # skip the first vector (-1 row), scan from second-last down to 0
            for j in range(n - 2, -1, -1):
                vector = table.position_vectors[j]
                if vector.position >= pos.position:
                    if vector.bitset.get(item):
                        support += 1
                    break
        return support

    def _recalculate_border_for_s_extension(
        self,
        prefix_border: List["AlgoLAPIN_LCI.Position"],
        item: int,
    ) -> List["AlgoLAPIN_LCI.Position"]:
        new_border: List[AlgoLAPIN_LCI.Position] = []
        for prev in prefix_border:
            sid = prev.sid
            prev_itemset_id = prev.position
            position_lists = self.se_position_list[sid]
            list_positions = position_lists.get_list_for_item(item)

            if list_positions is not None:
                for pos in list_positions:
                    if pos > prev_itemset_id:
                        new_border.append(self.Position(sid, pos))
                        break
        return new_border

    def _save_pattern_single_item(self, item: int, support: int) -> None:
        self.pattern_count += 1
        s = f"{item} -1 #SUP: {support}"
        self._writer.write(s + "\n")  # type: ignore[union-attr]
        if self.DEBUG:
            print(s)

    def _save_pattern_prefix(self, prefix: Prefix, support: int) -> None:
        self.pattern_count += 1
        parts: List[str] = []
        for itemset in prefix.itemsets:
            for item in itemset:
                parts.append(str(item))
                parts.append(" ")
            parts.append("-1 ")
        parts.append("#SUP: ")
        parts.append(str(support))
        s = "".join(parts)
        self._writer.write(s + "\n")  # type: ignore[union-attr]
        if self.DEBUG:
            print(s)

    def print_statistics(self) -> None:
        # Faithful to your Java version (including the "bug" appending patternCount after max memory)
        r = []
        r.append("=============  LAPIN - STATISTICS =============\n Total time ~ ")
        r.append(str(self.end_time - self.start_time))
        r.append(" ms\n")
        r.append(" Frequent sequences count : " + str(self.pattern_count))
        r.append("\n")
        r.append(" Max memory (mb) : ")
        r.append(str(MemoryLogger.get_instance().get_max_memory()))
        r.append(str(self.pattern_count))  # matches Java code
        r.append("\n")
        r.append("===================================================")
        print("".join(r))


# ----------------------------------------------------------------------
# Main (equivalent to MainTestLAPIN_saveToFile.java)
# ----------------------------------------------------------------------

def file_to_path(filename: str) -> str:
    """
    Java used getResource() from the class path.
    Here we look next to lapin.py first, then fall back to Java/src/lapin/.
    """
    here = Path(__file__).resolve().parent
    p = (here / filename)
    if p.exists():
        return str(p)

    alt = Path("Java") / "src" / "lapin" / filename
    if alt.exists():
        return str(alt.resolve())

    raise FileNotFoundError(f"Could not locate {filename}. Tried:\n- {p}\n- {alt.resolve()}")


def main() -> None:
    input_path = file_to_path("contextPrefixSpan.txt")
    output_path = Path(__file__).resolve().parent / "output_py.txt"

    algo = AlgoLAPIN_LCI()
    minsup = 0.5
    algo.run_algorithm(input_path, output_path, minsup)
    algo.print_statistics()


if __name__ == "__main__":
    main()
