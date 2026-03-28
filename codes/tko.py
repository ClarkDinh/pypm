import os
import sys
import time
import heapq
import psutil
from typing import Dict, List, Optional, Tuple


# ==============================================================================
# Element
# ==============================================================================

class Element:
    """
    Represents an Element of a utility list (tid, itemset utility, remaining utility).
    """

    def __init__(self, tid: int, iutils: int, rutils: int):
        self.tid: int = tid
        self.iutils: int = iutils
        self.rutils: int = rutils


# ==============================================================================
# UtilityList
# ==============================================================================

class UtilityList:
    """
    Represents a UtilityList for one item, storing Elements and running sums.
    """

    def __init__(self, item: int):
        self.item: int = item
        self.sum_iutils: int = 0
        self.sum_rutils: int = 0
        self.elements: List[Element] = []

    def add_element(self, element: Element) -> None:
        self.sum_iutils += element.iutils
        self.sum_rutils += element.rutils
        self.elements.append(element)

    def get_support(self) -> int:
        return len(self.elements)

    def get_utils(self) -> int:
        return self.sum_iutils


# ==============================================================================
# ItemsetTKO
# ==============================================================================

class ItemsetTKO:
    """
    Represents a high-utility itemset candidate with its utility score.
    Supports comparison by utility for use in a min-heap.
    """

    def __init__(self, itemset: List[int], item: int, utility: int):
        self.itemset: List[int] = list(itemset)
        self.item: int = item
        self.utility: int = utility

    def get_itemset(self) -> List[int]:
        return self.itemset

    def get_item(self) -> int:
        return self.item

    def __lt__(self, other: "ItemsetTKO") -> bool:
        return self.utility < other.utility

    def __le__(self, other: "ItemsetTKO") -> bool:
        return self.utility <= other.utility

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ItemsetTKO):
            return NotImplemented
        return self.utility == other.utility

    def __gt__(self, other: "ItemsetTKO") -> bool:
        return self.utility > other.utility

    def __ge__(self, other: "ItemsetTKO") -> bool:
        return self.utility >= other.utility

    def __repr__(self) -> str:
        parts = [str(i) for i in self.itemset]
        parts.append(str(self.item))
        return ",".join(parts)


# ==============================================================================
# MemoryLogger  (singleton)
# ==============================================================================

class MemoryLogger:
    """
    Records the maximum memory usage of the algorithm during execution.
    Implemented as a singleton.
    """

    _instance: Optional["MemoryLogger"] = None

    def __init__(self):
        self._max_memory: float = 0.0

    @classmethod
    def get_instance(cls) -> "MemoryLogger":
        if cls._instance is None:
            cls._instance = MemoryLogger()
        return cls._instance

    def get_max_memory(self) -> float:
        return self._max_memory

    def reset(self) -> None:
        self._max_memory = 0.0

    def check_memory(self) -> float:
        process = psutil.Process(os.getpid())
        current_memory = process.memory_info().rss / (1024 * 1024)  # bytes -> MB
        if current_memory > self._max_memory:
            self._max_memory = current_memory
        return current_memory


# ==============================================================================
# AlgoTKOBasic
# ==============================================================================

class AlgoTKOBasic:
    """
    Simple implementation of the TKO algorithm for mining
    Top-K High-Utility Itemsets (without all optimizations).

    Reference: Philippe Fournier-Viger et al.
    """

    def __init__(self):
        self.total_time: float = 0.0
        self.k: int = 0
        self.minutility: int = 1
        self._k_itemsets: List[ItemsetTKO] = []          # min-heap
        self._map_item_to_twu: Dict[int, int] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_algorithm(self, input_path: str, k: int) -> None:
        """
        Run the TKO-Basic algorithm.

        :param input_path: path to the input transaction database
        :param k:          number of top high-utility itemsets to discover
        """
        MemoryLogger.get_instance().reset()
        start_time = time.time()

        self.minutility = 1
        self.k = k
        self._k_itemsets = []
        self._map_item_to_twu = {}

        # ── First pass: compute TWU for every item ──────────────────────
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in ("#", "%", "@"):
                    continue

                parts = line.split(":")
                items = parts[0].split()
                transaction_utility = int(parts[1])

                for item_str in items:
                    item = int(item_str)
                    self._map_item_to_twu[item] = (
                        self._map_item_to_twu.get(item, 0) + transaction_utility
                    )

        # ── Build utility lists for every item ──────────────────────────
        map_item_to_ul: Dict[int, UtilityList] = {
            item: UtilityList(item) for item in self._map_item_to_twu
        }

        # Sort items by ascending TWU (ties broken by item id)
        list_items: List[UtilityList] = sorted(
            map_item_to_ul.values(),
            key=lambda ul: (self._map_item_to_twu[ul.item], ul.item),
        )

        # ── Second pass: populate utility lists ─────────────────────────
        with open(input_path, "r", encoding="utf-8") as f:
            tid = 0
            for line in f:
                line = line.strip()
                if not line or line[0] in ("#", "%", "@"):
                    continue

                parts = line.split(":")
                items = parts[0].split()
                utility_values = parts[2].split()

                remaining_utility = 0
                revised_transaction: List[Tuple[int, int]] = []

                for i, item_str in enumerate(items):
                    item = int(item_str)
                    utility = int(utility_values[i])
                    revised_transaction.append((item, utility))
                    remaining_utility += utility

                # Sort by the same TWU-based order used for list_items
                revised_transaction.sort(key=lambda p: self._compare_items_key(p[0]))

                for item, utility in revised_transaction:
                    remaining_utility -= utility
                    map_item_to_ul[item].add_element(
                        Element(tid, utility, remaining_utility)
                    )

                tid += 1

        MemoryLogger.get_instance().check_memory()

        # ── Recursive search ─────────────────────────────────────────────
        self._search([], None, list_items)

        MemoryLogger.get_instance().check_memory()
        self.total_time = time.time() - start_time

    def write_result_to_file(self, path: str) -> None:
        """Write the top-k itemsets to an output file."""
        with open(path, "w", encoding="utf-8") as f:
            lines = []
            for itemset in self._k_itemsets:
                parts = [str(i) for i in itemset.get_itemset()]
                parts.append(str(itemset.item))
                lines.append(" ".join(parts) + " #UTIL: " + str(itemset.utility))
            f.write("\n".join(lines))

    def print_stats(self) -> None:
        """Print execution statistics to stdout."""
        print("=============  TKO-BASIC - v.2.28 =============")
        print(f" High-utility itemsets count : {len(self._k_itemsets)}")
        print(f" Total time ~ {self.total_time:.3f} s")
        print(f" Memory ~ {MemoryLogger.get_instance().get_max_memory():.2f} MB")
        print("===================================================")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compare_items_key(self, item: int):
        """Sort key: (TWU, item_id) — mirrors Java's compareItems."""
        return (self._map_item_to_twu[item], item)

    def _search(
        self,
        prefix: List[int],
        p_ul: Optional[UtilityList],
        uls: List[UtilityList],
    ) -> None:
        """Recursive depth-first search for high-utility itemsets."""
        MemoryLogger.get_instance().check_memory()

        for i, X in enumerate(uls):
            # Record itemset if its utility meets the threshold
            if X.sum_iutils >= self.minutility:
                self._write_out(prefix, X.item, X.sum_iutils)

            # Pruning: only explore extensions if they may yield HUIs
            if X.sum_rutils + X.sum_iutils >= self.minutility:
                ex_uls: List[UtilityList] = [
                    self._construct(p_ul, X, uls[j])
                    for j in range(i + 1, len(uls))
                ]
                self._search(prefix + [X.item], X, ex_uls)

    def _write_out(self, prefix: List[int], item: int, utility: int) -> None:
        """Add a high-utility itemset to the top-k min-heap."""
        itemset = ItemsetTKO(prefix, item, utility)
        heapq.heappush(self._k_itemsets, itemset)

        if len(self._k_itemsets) > self.k:
            if utility > self.minutility:
                while len(self._k_itemsets) > self.k:
                    heapq.heappop(self._k_itemsets)
                if self._k_itemsets:
                    self.minutility = self._k_itemsets[0].utility

    def _construct(
        self,
        P: Optional[UtilityList],
        px: UtilityList,
        py: UtilityList,
    ) -> UtilityList:
        """Construct the utility list of itemset pXY from pX and pY."""
        pxy_ul = UtilityList(py.item)

        for ex in px.elements:
            ey = self._find_element_with_tid(py, ex.tid)
            if ey is None:
                continue

            if P is None:
                pxy_ul.add_element(Element(ex.tid, ex.iutils + ey.iutils, ey.rutils))
            else:
                e = self._find_element_with_tid(P, ex.tid)
                if e is not None:
                    pxy_ul.add_element(
                        Element(ex.tid, ex.iutils + ey.iutils - e.iutils, ey.rutils)
                    )

        return pxy_ul

    @staticmethod
    def _find_element_with_tid(
        ulist: UtilityList, tid: int
    ) -> Optional[Element]:
        """Binary search for an Element by tid inside a UtilityList."""
        lst = ulist.elements
        first, last = 0, len(lst) - 1

        while first <= last:
            middle = (first + last) >> 1
            mid_tid = lst[middle].tid
            if mid_tid < tid:
                first = middle + 1
            elif mid_tid > tid:
                last = middle - 1
            else:
                return lst[middle]

        return None


# ==============================================================================
# Main
# ==============================================================================

def main():
    # Input file: place DB_Utility.txt in the same folder as this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(script_dir, "DB_Utility.txt")
    output_path = os.path.join(script_dir, "output_py.txt")

    k = 20  # number of top high-utility itemsets to find

    algorithm = AlgoTKOBasic()
    algorithm.run_algorithm(input_path, k)
    algorithm.write_result_to_file(output_path)
    algorithm.print_stats()


if __name__ == "__main__":
    main()