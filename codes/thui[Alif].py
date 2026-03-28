"""
THUI Algorithm - Mining top-k high utility itemsets with effective threshold raising strategies.
Expert Syst. Appl. 117: 148-165 (2019)
"""

import heapq
import os
import time
from datetime import datetime
from urllib.request import url2pathname
from urllib.parse import unquote
from pathlib import Path


# ==============================================================================
# ItemTHUI (originally ItemTHUI.java)
# ==============================================================================

class ItemTHUI:
    def __init__(self):
        self.twu = 0
        self.utility = 0

    def __str__(self):
        return str(self.utility)


# ==============================================================================
# Element - helper class used by UtilityList (inlined from AlgoTHUI.java usage)
# ==============================================================================

class Element:
    def __init__(self, tid, iutils, rutils):
        self.tid = tid
        self.iutils = iutils
        self.rutils = rutils


# ==============================================================================
# UtilityList - helper class used by AlgoTHUI (inlined from AlgoTHUI.java usage)
# ==============================================================================

class UtilityList:
    def __init__(self, item):
        self.item = item
        self.sumIutils = 0
        self.sumRutils = 0
        self.elements = []

    def add_element(self, element):
        self.sumIutils += element.iutils
        self.sumRutils += element.rutils
        self.elements.append(element)

    def get_utils(self):
        return self.sumIutils


# ==============================================================================
# PatternTHUI (originally PatternTHUI.java)
# ==============================================================================

class PatternTHUI:
    def __init__(self, prefix, length, X, idx):
        buffer = ""
        for i in range(length):
            buffer += str(prefix[i]) + " "
        buffer += str(X.item)
        self.prefix = buffer
        self.idx = idx
        self.utility = X.get_utils()
        self.sup = len(X.elements)

    def get_prefix(self):
        return self.prefix

    def __lt__(self, other):
        if self.utility != other.utility:
            return self.utility < other.utility
        return id(self) < id(other)

    def __eq__(self, other):
        return self is other

    def __le__(self, other):
        return self < other or self == other

    def __gt__(self, other):
        return not self <= other

    def __ge__(self, other):
        return not self < other


# ==============================================================================
# AlgoTHUI (originally AlgoTHUI.java)
# ==============================================================================

class AlgoTHUI:

    BUFFERS_SIZE = 200

    def __init__(self):
        self.max_memory = 0.0
        self.start_timestamp = 0
        self.start_timestamp_pha2 = 0
        self.end_timestamp = 0
        self.hui_count = 0
        self.candidate_count = 0

        self.map_item_to_twu = {}
        self.min_utility = 0
        self.topk_static = 0

        self.writer = None
        # Min-heap for top-k patterns (Python heapq is a min-heap)
        self.k_patterns = []
        self.leaf_prune_utils = []

        self.debug = False
        self.total_construct_time = 0
        self.total_while = 0
        self.total_item = 0

        self.itemset_buffer = None
        self.map_fmap = None
        self.map_leaf_map = None
        self.riu_raise_value = 0
        self.leaf_raise_value = 0
        self.leaf_map_size = 0

        self.EUCS_PRUNE = False
        self.LEAF_PRUNE = True

        self.input_file = ""

    # ---------- Pair helper ----------

    class Pair:
        def __init__(self, item, utility):
            self.item = item
            self.utility = utility

        def __str__(self):
            return f"[{self.item},{self.utility}]"

    # ---------- Comparators ----------

    def _compare_items(self, item1, item2):
        diff = self.map_item_to_twu[item1] - self.map_item_to_twu[item2]
        return diff if diff != 0 else item1 - item2

    def _pair_key(self, pair):
        twu = self.map_item_to_twu.get(pair.item, 0)
        return (twu, pair.item)

    def _ul_key(self, ul):
        twu = self.map_item_to_twu.get(ul.item, 0)
        return (twu, ul.item)

    # ---------- Main entry point ----------

    def run_algorithm(self, input_path, output_path, eucs_prune, topk):
        self.topk_static = topk
        self.max_memory = 0
        self.itemset_buffer = [0] * self.BUFFERS_SIZE
        self.EUCS_PRUNE = eucs_prune
        RIU = {}

        self.input_file = input_path

        if self.EUCS_PRUNE:
            self.map_fmap = {}

        if self.LEAF_PRUNE:
            self.map_leaf_map = {}
            self.leaf_prune_utils = []

        self.start_timestamp = time.time()
        self.writer = open(output_path, 'w')

        self.map_item_to_twu = {}

        # --- First database scan ---
        try:
            with open(input_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line[0] in ('#', '%', '@'):
                        continue
                    split = line.split(':')
                    items = split[0].split()
                    utility_values = split[2].split()
                    transaction_utility = int(split[1])

                    for i, item_str in enumerate(items):
                        item = int(item_str)
                        twu = self.map_item_to_twu.get(item, 0) + transaction_utility
                        self.map_item_to_twu[item] = twu

                        util = int(utility_values[i])
                        RIU[item] = RIU.get(item, 0) + util
        except Exception as e:
            print(f"Error reading file (scan 1): {e}")

        # Raise threshold by real item utility
        self._raising_threshold_riu(RIU, self.topk_static)
        self.riu_raise_value = self.min_utility

        # Build utility lists
        list_of_utility_lists = []
        map_item_to_utility_list = {}

        for item, twu_val in self.map_item_to_twu.items():
            if twu_val >= self.min_utility:
                u_list = UtilityList(item)
                map_item_to_utility_list[item] = u_list
                list_of_utility_lists.append(u_list)

        list_of_utility_lists.sort(key=self._ul_key)

        # --- Second database scan ---
        try:
            with open(input_path, 'r') as f:
                tid = 0
                for line in f:
                    line = line.strip()
                    if not line or line[0] in ('#', '%', '@'):
                        continue
                    split = line.split(':')
                    items = split[0].split()
                    utility_values = split[2].split()
                    remaining_utility = 0
                    new_twu = 0

                    revised_transaction = []
                    for i, item_str in enumerate(items):
                        item = int(item_str)
                        util = int(utility_values[i])
                        pair = self.Pair(item, util)
                        if self.map_item_to_twu.get(pair.item, 0) >= self.min_utility:
                            revised_transaction.append(pair)
                            remaining_utility += pair.utility
                            new_twu += pair.utility

                    if not revised_transaction:
                        continue

                    revised_transaction.sort(key=self._pair_key)

                    remaining_utility = 0
                    for i in range(len(revised_transaction) - 1, -1, -1):
                        pair = revised_transaction[i]
                        ul = map_item_to_utility_list.get(pair.item)
                        if ul is not None:
                            element = Element(tid, pair.utility, remaining_utility)
                            ul.add_element(element)

                        if self.EUCS_PRUNE:
                            self._update_eucs_prune(i, pair, revised_transaction, new_twu)
                        if self.LEAF_PRUNE:
                            self._update_leaf_prune(i, pair, revised_transaction, list_of_utility_lists)
                        remaining_utility += pair.utility

                    tid += 1
        except Exception as e:
            print(f"Error reading file (scan 2): {e}")

        if self.EUCS_PRUNE:
            self._raising_threshold_cud_optimize(self.topk_static)
            self._remove_entry()

        RIU.clear()

        self.start_timestamp_pha2 = time.time()

        if self.LEAF_PRUNE:
            self._raising_threshold_leaf(list_of_utility_lists)
            self._set_leaf_map_size()
            self._remove_leaf_entry()
            self.leaf_prune_utils = None

        self.leaf_raise_value = self.min_utility
        map_item_to_utility_list = None

        self._check_memory()
        self._thui(self.itemset_buffer, 0, None, list_of_utility_lists)
        self._check_memory()

        self._write_result_to_file()
        self.writer.close()

        self.end_timestamp = time.time()
        self.k_patterns.clear()

    # ---------- EUCS update ----------

    def _update_eucs_prune(self, i, pair, revised_transaction, new_twu):
        map_fmap_item = self.map_fmap.get(pair.item)
        if map_fmap_item is None:
            map_fmap_item = {}
            self.map_fmap[pair.item] = map_fmap_item

        for j in range(i + 1, len(revised_transaction)):
            pair_after = revised_transaction[j]
            if pair.item == pair_after.item:
                continue
            twu_item = map_fmap_item.get(pair_after.item)
            if twu_item is None:
                twu_item = ItemTHUI()
            twu_item.twu += new_twu
            twu_item.utility += pair.utility + pair_after.utility
            map_fmap_item[pair_after.item] = twu_item

    # ---------- Leaf prune update ----------

    def _update_leaf_prune(self, i, pair, revised_transaction, ULs):
        cutil = pair.utility
        following_item_idx = self._get_twu_index(pair.item, ULs)
        map_leaf_item = self.map_leaf_map.get(following_item_idx)
        if map_leaf_item is None:
            map_leaf_item = {}
            self.map_leaf_map[following_item_idx] = map_leaf_item

        for j in range(i - 1, -1, -1):
            pair_after = revised_transaction[j]
            if pair.item == pair_after.item:
                continue
            following_item_idx -= 1
            if following_item_idx < 0 or ULs[following_item_idx].item != pair_after.item:
                break
            twu_item = map_leaf_item.get(following_item_idx, 0)
            cutil += pair_after.utility
            twu_item += cutil
            map_leaf_item[following_item_idx] = twu_item

    def _get_twu_index(self, item, ULs):
        for i in range(len(ULs) - 1, -1, -1):
            if ULs[i].item == item:
                return i
        return -1

    def _set_leaf_map_size(self):
        for v in self.map_leaf_map.values():
            self.leaf_map_size += len(v)

    # ---------- Core recursive search ----------

    def _thui(self, prefix, prefix_length, pUL, ULs):
        for i in range(len(ULs) - 1, -1, -1):
            if ULs[i].get_utils() >= self.min_utility:
                self._save(prefix, prefix_length, ULs[i])

        for i in range(len(ULs) - 2, -1, -1):
            self._check_memory()
            X = ULs[i]
            if X.sumIutils + X.sumRutils >= self.min_utility and X.sumIutils > 0:
                if self.EUCS_PRUNE:
                    if self.map_fmap.get(X.item) is None:
                        continue

                ex_uls = []
                for j in range(i + 1, len(ULs)):
                    Y = ULs[j]
                    self.candidate_count += 1
                    exul = self._construct(pUL, X, Y)
                    if exul is not None:
                        ex_uls.append(exul)

                prefix[prefix_length] = X.item
                self._thui(prefix, prefix_length + 1, X, ex_uls)

    # ---------- Construct utility list ----------

    def _construct(self, P, px, py):
        pxy_ul = UtilityList(py.item)
        tot_util = px.sumIutils + px.sumRutils
        ei = 0
        ej = 0
        Pi = -1

        while ei < len(px.elements) and ej < len(py.elements):
            ex = px.elements[ei]
            ey = py.elements[ej]

            if ex.tid > ey.tid:
                ej += 1
                continue
            if ex.tid < ey.tid:
                tot_util -= ex.iutils + ex.rutils
                if tot_util < self.min_utility:
                    return None
                ei += 1
                Pi += 1
                continue

            # ex.tid == ey.tid
            if P is None:
                pxy_ul.add_element(Element(ex.tid, ex.iutils + ey.iutils, ey.rutils))
            else:
                Pi += 1
                while Pi < len(P.elements) and P.elements[Pi].tid < ex.tid:
                    Pi += 1
                e = P.elements[Pi]
                pxy_ul.add_element(Element(ex.tid, ex.iutils + ey.iutils - e.iutils, ey.rutils))

            ei += 1
            ej += 1

        while ei < len(px.elements):
            ex = px.elements[ei]
            tot_util -= ex.iutils + ex.rutils
            if tot_util < self.min_utility:
                return None
            ei += 1

        return pxy_ul

    # ---------- Save pattern ----------

    def _save(self, prefix, length, X):
        pattern = PatternTHUI(prefix, length, X, self.candidate_count)
        heapq.heappush(self.k_patterns, pattern)
        if len(self.k_patterns) > self.topk_static:
            if X.get_utils() >= self.min_utility:
                while len(self.k_patterns) > self.topk_static:
                    heapq.heappop(self.k_patterns)
            self.min_utility = self.k_patterns[0].utility

    # ---------- Threshold raising ----------

    def _raising_threshold_riu(self, riu_map, k):
        sorted_entries = sorted(riu_map.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_entries) >= k > 0:
            self.min_utility = sorted_entries[k - 1][1]

    def _raising_threshold_cud_optimize(self, k):
        ktopls = []
        for outer in self.map_fmap.values():
            for item_thui in outer.values():
                value = item_thui.utility
                if value >= self.min_utility:
                    if len(ktopls) < k:
                        heapq.heappush(ktopls, value)
                    elif value > ktopls[0]:
                        heapq.heappush(ktopls, value)
                        while len(ktopls) > k:
                            heapq.heappop(ktopls)
        if len(ktopls) > k - 1 and ktopls[0] > self.min_utility:
            self.min_utility = ktopls[0]

    def _add_to_leaf_prune_utils(self, value):
        if len(self.leaf_prune_utils) < self.topk_static:
            heapq.heappush(self.leaf_prune_utils, value)
        elif value > self.leaf_prune_utils[0]:
            heapq.heappush(self.leaf_prune_utils, value)
            while len(self.leaf_prune_utils) > self.topk_static:
                heapq.heappop(self.leaf_prune_utils)

    def _raising_threshold_leaf(self, ULs):
        # LIU-Exact
        for outer in self.map_leaf_map.values():
            for value in outer.values():
                if value >= self.min_utility:
                    self._add_to_leaf_prune_utils(value)

        # LIU-LB
        for entry_key, inner_map in self.map_leaf_map.items():
            for entry2_key, value in inner_map.items():
                if value >= self.min_utility:
                    end = entry_key + 1
                    st = entry2_key

                    for i in range(st + 1, end - 1):
                        value2 = value - ULs[i].get_utils()
                        if value2 >= self.min_utility:
                            self._add_to_leaf_prune_utils(value2)
                        for j in range(i + 1, end - 1):
                            value2 = value - ULs[i].get_utils() - ULs[j].get_utils()
                            if value2 >= self.min_utility:
                                self._add_to_leaf_prune_utils(value2)
                            for kk in range(j + 1, end - 2):
                                value2 = value - ULs[i].get_utils() - ULs[j].get_utils() - ULs[kk].get_utils()
                                if value2 >= self.min_utility:
                                    self._add_to_leaf_prune_utils(value2)

        # Add all 1-items
        for u in ULs:
            value = u.get_utils()
            if value >= self.min_utility:
                self._add_to_leaf_prune_utils(value)

        if (len(self.leaf_prune_utils) > self.topk_static - 1 and
                self.leaf_prune_utils[0] > self.min_utility):
            self.min_utility = self.leaf_prune_utils[0]

    # ---------- Remove entries ----------

    def _remove_entry(self):
        for outer in self.map_fmap.values():
            keys_to_remove = [k for k, v in outer.items() if v.twu < self.min_utility]
            for k in keys_to_remove:
                del outer[k]

    def _remove_leaf_entry(self):
        for outer in self.map_leaf_map.values():
            outer.clear()

    # ---------- Write results ----------

    def _write_result_to_file(self):
        if not self.k_patterns:
            return

        lp = []
        while self.k_patterns:
            self.hui_count += 1
            pattern = heapq.heappop(self.k_patterns)
            lp.append(pattern)

        # Sort by TWU of first item in prefix
        def pattern_sort_key(p):
            first_item = int(p.prefix.split()[0])
            return self.map_item_to_twu.get(first_item, 0)

        lp.sort(key=pattern_sort_key)

        for pattern in lp:
            line = f"{pattern.prefix} #UTIL: {pattern.utility}"
            self.writer.write(line + '\n')

    # ---------- Memory check ----------

    def _check_memory(self):
        import tracemalloc
        # Simple approximation using tracemalloc if active, else skip
        try:
            current, peak = tracemalloc.get_traced_memory()
            current_mb = current / 1024 / 1024
            if current_mb > self.max_memory:
                self.max_memory = current_mb
        except Exception:
            pass

    # ---------- Print stats ----------

    def print_stats(self):
        elapsed_ms = int((self.end_timestamp - self.start_timestamp) * 1000)
        print("=============  THUI ALGORITHM - STATS =============")
        print(f" Total time ~ {elapsed_ms} ms")
        print(f" Memory ~ {self.max_memory:.2f} MB")
        print(f" High-utility itemsets count : {self.hui_count}  Candidates {self.candidate_count}")
        print(f" Final minimum utility : {self.min_utility}")
        dataset_name = os.path.splitext(os.path.basename(self.input_file))[0]
        print(f" Dataset : {dataset_name}")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f" End time {timestamp}")
        print("===================================================")


# ==============================================================================
# MainTestTHUI (originally MainTestTHUI.java)
# ==============================================================================

def file_to_path(filename):
    """Resolve the path to a data file located in the same directory as this script."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, filename)


def main():
    import tracemalloc
    tracemalloc.start()

    # Input file path
    input_path = file_to_path("DB_Utility.txt")

    # Output file path
    output_path = "output_py.txt"

    # The parameter k
    k = 8

    # Run the algorithm
    algorithm = AlgoTHUI()
    algorithm.run_algorithm(input_path, output_path, True, k)

    # Print statistics
    algorithm.print_stats()

    tracemalloc.stop()


if __name__ == "__main__":
    main()