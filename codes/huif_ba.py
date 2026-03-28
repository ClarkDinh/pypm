"""
Python implementation of the HUIF-BA (High-Utility Itemset Finding - Bat Algorithm)
Original Java implementation by Wei Song, Chaomin Huang.
Reference: "Mining High Utility Itemsets Using Bio-Inspired Algorithms: 
            A Diverse Optimal Value Framework", IEEE Access, 2018.
"""

import random
import time
import os

# ─────────────────────────────────────────────
#  >>>  USER CONFIGURATION  <<<
# ─────────────────────────────────────────────
INPUT_FILE  = "contextHUIM.txt"   # dataset path relative to this script
OUTPUT_FILE = "Python_output.txt"             # output file path relative to this script

# Java-style threshold setting: same meaning as `int min_utility = 40;` in Java.
MIN_UTILITY = 40

# Optional ratio mode. If set (e.g. 0.5), it overrides MIN_UTILITY using:
# min_utility = ceil(total_transaction_utility * MIN_SUP_RATIO)
MIN_SUP_RATIO = None

# Optional reproducibility for Python runs. Set to None for fully random behavior.
RANDOM_SEED = 12345

# Optional comparison with Java result file after the Python run.
COMPARE_WITH_JAVA_OUTPUT = True
JAVA_OUTPUT_FILE = "../Java.output.txt"
# ─────────────────────────────────────────────


# ── Algorithm constants (mirror the Java final fields) ──
POP_SIZE = 100
MAX_ITER = 2000
FMIN, FMAX = 0.0, 1.0
AMIN, AMAX = 0.0, 2.0
ALPHA = 0.8
GAMMA = 0.9


# ── Data classes ────────────────────────────────────────

class Pair:
    __slots__ = ("item", "utility")
    def __init__(self, item=0, utility=0):
        self.item    = item
        self.utility = utility


class HUI:
    __slots__ = ("itemset", "fitness")
    def __init__(self, itemset, fitness):
        self.itemset = itemset
        self.fitness = fitness


class Item:
    __slots__ = ("item", "tids")          # tids: Python set of transaction indices
    def __init__(self, item, n_transactions):
        self.item = item
        self.tids = set()


class BAIndividual:
    """Mirrors the Java BAIndividual inner class.
    chrom is a Python set of bit-positions that are '1' (like a sparse BitSet).
    chrom_size is the total number of candidate items (= len(twu_pattern)).
    """
    def __init__(self, chrom_size):
        self.chrom_size      = chrom_size
        self.chrom           = set()          # set of indices where bit == 1
        self.velocity        = 2
        self.fitness         = 0.0
        self.freq            = 0.0
        self.loudness        = 0.0
        self.init_emission   = 0.0
        self.emission_rate   = 0.0

    def deepcopy(self, other):
        self.chrom_size    = other.chrom_size
        self.chrom         = set(other.chrom)
        self.velocity      = other.velocity
        self.fitness       = other.fitness
        self.freq          = other.freq
        self.loudness      = other.loudness
        self.init_emission = other.init_emission
        self.emission_rate = other.emission_rate

    def cardinality(self):
        return len(self.chrom)

    def get_bit(self, i):
        return i in self.chrom

    def set_bit(self, i):
        self.chrom.add(i)

    def clear_bit(self, i):
        self.chrom.discard(i)

    # ── fitness calculation (mirrors Java calculateFitness) ──
    def calculate_fitness(self, k, trans_list, database, twu_pattern):
        """k = number of set bits (cardinality), trans_list = list of transaction indices."""
        if k == 0:
            return
        fitness = 0
        # sorted list of set-bit positions (ascending) for this individual
        active_indices = sorted(self.chrom)
        active_items   = [twu_pattern[i] for i in active_indices]

        for p in trans_list:
            transaction = database[p]   # list of Pair
            temp = 0
            sum_util = 0
            q = 0
            i = 0
            # two-pointer walk matching active_items against transaction items
            while q < len(transaction) and i < len(active_items):
                if transaction[q].item == active_items[i]:
                    sum_util += transaction[q].utility
                    i += 1
                    q += 1
                    temp += 1
                else:
                    q += 1
            if temp == k:
                fitness += sum_util

        self.fitness = fitness


# ── Main algorithm class ─────────────────────────────────

class AlgoBio_HUIF_BA:

    def __init__(self):
        self.max_memory       = 0.0
        self.start_time       = 0
        self.end_time         = 0
        self.transaction_count = 0

        self.map_item_to_util  = {}
        self.map_item_to_sup   = {}
        self.map_item_to_twu   = {}
        self.map_item_to_twu0  = {}

        self.twu_pattern       = []   # list of candidate items (sorted)
        self.database          = []   # list of list[Pair]
        self.items             = []   # list of Item
        self.population        = []
        self.hui_sets          = []   # list of HUI
        self.hui_ba            = []   # list of BAIndividual (unique high-utility ones)
        self.percentage        = []
        self.percent_hui_ba    = []
        self.g_best            = None
        self.gen               = 0

    # ── Public entry point ────────────────────────────────

    def run_algorithm(self, input_path, output_path, min_utility):
        self.max_memory = 0.0
        self.start_time = time.time()

        # ── PASS 1: compute TWU, utility, support per item ──
        with open(input_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in ('#', '%', '@'):
                    continue
                parts        = line.split(":")
                items_str    = parts[0].strip().split()
                trans_util   = int(parts[1].strip())
                util_values  = parts[2].strip().split()

                for i, item_str in enumerate(items_str):
                    item    = int(item_str)
                    utility = int(util_values[i])

                    self.map_item_to_util[item] = self.map_item_to_util.get(item, 0) + utility
                    self.map_item_to_sup[item]  = self.map_item_to_sup.get(item, 0)  + 1
                    self.map_item_to_twu[item]  = self.map_item_to_twu.get(item, 0)  + trans_util
                    self.map_item_to_twu0[item] = self.map_item_to_twu0.get(item, 0) + trans_util

                self.transaction_count += 1

        # ── PASS 2: build pruned database ──
        with open(input_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in ('#', '%', '@'):
                    continue
                parts       = line.split(":")
                items_str   = parts[0].strip().split()
                util_values = parts[2].strip().split()

                revised = []
                for i, item_str in enumerate(items_str):
                    item    = int(item_str)
                    utility = int(util_values[i])
                    if self.map_item_to_twu.get(item, 0) >= min_utility:
                        revised.append(Pair(item, utility))
                    else:
                        self.map_item_to_twu0.pop(item, None)
                self.database.append(revised)

        # candidate items sorted ascending (mirrors Java Collections.sort)
        self.twu_pattern = sorted(self.map_item_to_twu0.keys())

        print(f"twuPattern: {len(self.twu_pattern)}")
        print(self.twu_pattern)

        # ── Build Item TID-sets ──
        n = len(self.twu_pattern)
        self.items = [Item(item, self.transaction_count) for item in self.twu_pattern]

        for tid, trans in enumerate(self.database):
            trans_items = {p.item for p in trans}
            for j, it in enumerate(self.items):
                if it.item in trans_items:
                    it.tids.add(tid)

        self._check_memory()

        # ── Run BA if there are candidates ──
        if n > 0:
            self.g_best = BAIndividual(n)
            self._pop_init(min_utility)

            for self.gen in range(MAX_ITER):
                self._next_gen_ba(min_utility)
                if self.hui_ba:
                    self.percent_hui_ba = self._roulette_percent_hui_ba()
                    num = self._roulette_select_hui_ba(self.percent_hui_ba)
                    self.g_best.deepcopy(self.hui_ba[num])

                if self.gen % 200 == 0:
                    print(f"Iteration {self.gen} - update end. HUIs No. is {len(self.hui_sets)}")

        # ── Write results ──
        self._write_out(output_path)
        self._check_memory()
        self.end_time = time.time()

    # ── Population initialisation (mirrors pop_Init) ─────

    def _pop_init(self, min_utility):
        n = len(self.twu_pattern)
        self.percentage = self._roulette_percent()
        print(self.percentage)

        for i in range(POP_SIZE):
            ind = BAIndividual(n)
            j   = 0
            k   = int(random.random() * n)

            while j < k:
                temp = self._roulette_select(self.percentage)
                if not ind.get_bit(temp):
                    j += 1
                    ind.set_bit(temp)

            trans_list = []
            self._pev_check(ind, trans_list)
            ind.calculate_fitness(k, trans_list, self.database, self.twu_pattern)

            ind.freq          = FMIN + (FMAX - FMIN) * random.random()
            ind.loudness      = AMIN + (AMAX - AMIN) * random.random()
            ind.init_emission = random.random()
            ind.emission_rate = ind.init_emission

            self.population.append(ind)

            if ind.fitness >= min_utility and ind.cardinality() > 0:
                self._insert(ind)
                self._add_hui_ba(ind)

            if i == 0:
                self.g_best.deepcopy(ind)
            else:
                if ind.fitness >= self.g_best.fitness:
                    self.g_best.deepcopy(ind)

    # ── One generation update (mirrors next_Gen_BA) ───────

    def _next_gen_ba(self, min_utility):
        n = len(self.twu_pattern)

        for i in range(POP_SIZE):
            ind = self.population[i]
            ind.freq = FMIN + (FMAX - FMIN) * random.random()

            dis_list   = self._bit_diff(self.g_best, ind)
            num        = int(len(dis_list) * ind.freq) + 1
            change_bit = 0

            if dis_list:
                for _ in range(num):
                    change_bit = int(len(dis_list) * random.random())
                    bit = dis_list[change_bit]
                    if ind.get_bit(bit):
                        ind.clear_bit(bit)
                    else:
                        ind.set_bit(bit)

            # random single-bit flip
            for _ in range(1):
                change_bit = int(n * random.random())
                if ind.get_bit(change_bit):
                    ind.clear_bit(change_bit)
                else:
                    ind.set_bit(change_bit)

            trans_list = []
            self._pev_check(ind, trans_list)
            ind.calculate_fitness(ind.cardinality(), trans_list, self.database, self.twu_pattern)

            if ind.fitness >= min_utility and ind.cardinality() > 0:
                self._insert(ind)
                self._add_hui_ba(ind)

            if ind.fitness > self.g_best.fitness:
                self.g_best.deepcopy(ind)

            rnd = random.random()
            total_loudness = sum(p.loudness for p in self.population)

            tmp = BAIndividual(n)
            tmp.deepcopy(ind)

            if rnd > ind.emission_rate:
                k = int(random.random() * n)
                if tmp.get_bit(k):
                    tmp.clear_bit(k)
                else:
                    tmp.set_bit(k)

            trans_list2 = []
            self._pev_check(tmp, trans_list2)
            tmp.calculate_fitness(tmp.cardinality(), trans_list2, self.database, self.twu_pattern)

            if tmp.fitness >= min_utility and tmp.cardinality() > 0:
                self._insert(tmp)
                self._add_hui_ba(tmp)

            if tmp.fitness > self.g_best.fitness:
                self.g_best.deepcopy(tmp)

            if tmp.fitness < self.g_best.fitness and random.random() < ind.loudness:
                ind.deepcopy(tmp)
                ind.loudness      *= ALPHA
                ind.emission_rate  = ind.init_emission * (1 - pow(2.718281828, -GAMMA * self.gen))

    # ── Helper: bit difference (XOR positions) ───────────

    def _bit_diff(self, g_best, ind):
        """Returns list of indices where g_best and ind differ."""
        diff = g_best.chrom.symmetric_difference(ind.chrom)
        # limit range to chrom_size (mirrors BitSet.length() behaviour)
        max_bit = max((g_best.chrom_size, ind.chrom_size), default=0)
        return sorted(b for b in diff if b < max_bit)

    # ── Helper: pev_Check (prune infeasible itemsets) ─────

    def _pev_check(self, ind, result_list):
        """
        Mirrors Java pev_Check.
        Intersects TID-sets of selected items; removes items that cause empty intersection.
        Fills result_list with surviving transaction indices.
        Returns True if intersection is non-empty, False otherwise.
        """
        active = sorted(ind.chrom)   # ascending bit positions
        if not active:
            return False

        current_tids = set(self.items[active[0]].tids)
        mid_tids     = set(current_tids)

        for idx in active[1:]:
            candidate = current_tids & self.items[idx].tids
            if candidate:
                current_tids = candidate
                mid_tids     = set(current_tids)
            else:
                # prune this bit
                current_tids = set(mid_tids)
                ind.clear_bit(idx)

        if not current_tids:
            return False

        result_list.extend(sorted(current_tids))
        return True

    # ── Helper: insert unique HUI into hui_sets ───────────

    def _insert(self, ind):
        n     = len(self.twu_pattern)
        parts = [str(self.twu_pattern[i]) for i in range(n) if ind.get_bit(i)]
        key   = " ".join(parts) + " "

        for h in self.hui_sets:
            if h.itemset == key:
                return
        self.hui_sets.append(HUI(key, ind.fitness))

    # ── Helper: add unique individual to hui_ba pool ──────

    def _add_hui_ba(self, ind):
        for existing in self.hui_ba:
            if existing.chrom == ind.chrom:
                return
        clone = BAIndividual(ind.chrom_size)
        clone.deepcopy(ind)
        self.hui_ba.append(clone)

    # ── Roulette helpers ──────────────────────────────────

    def _roulette_percent(self):
        total    = sum(self.map_item_to_twu[it] for it in self.twu_pattern)
        pct_list = []
        running  = 0.0
        for it in self.twu_pattern:
            running += self.map_item_to_twu[it]
            pct_list.append(running / total)
        self.percentage = pct_list
        return pct_list

    def _roulette_select(self, pct):
        r = random.random()
        for i, p in enumerate(pct):
            if i == 0:
                if 0 <= r <= p:
                    return 0
            elif pct[i-1] < r <= p:
                return i
        return 0

    def _roulette_percent_hui_ba(self):
        total    = sum(h.fitness for h in self.hui_ba)
        pct_list = []
        running  = 0.0
        for h in self.hui_ba:
            running += h.fitness
            pct_list.append(running / total)
        return pct_list

    def _roulette_select_hui_ba(self, pct):
        r = random.random()
        for i, p in enumerate(pct):
            if i == 0:
                if 0 <= r <= p:
                    return 0
            elif pct[i-1] < r <= p:
                return i
        return 0

    # ── Output ────────────────────────────────────────────

    def _write_out(self, output_path):
        lines = []
        for i, h in enumerate(self.hui_sets):
            line = f"{h.itemset}#UTIL: {float(h.fitness):.1f}"
            lines.append(line)
        with open(output_path, "w") as f:
            f.write("\n".join(lines))

    def _check_memory(self):
        # Python doesn't expose JVM-style memory; we skip or approximate.
        pass

    def print_stats(self):
        elapsed_ms = int((self.end_time - self.start_time) * 1000)
        print("=============  HUIF-BA ALGORITHM v.2.36 - STATS =============")
        print(f" Total time ~ {elapsed_ms} ms")
        print(f" Memory ~ N/A (Python)")
        print(f" High-utility itemsets count : {len(self.hui_sets)}")
        print("===================================================")


def _resolve_path(script_dir, raw_path):
    if os.path.isabs(raw_path):
        return raw_path
    return os.path.abspath(os.path.join(script_dir, raw_path))


def _sum_transaction_utility(input_path):
    total_utility = 0
    with open(input_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line[0] in ('#', '%', '@'):
                continue
            parts = line.split(":")
            total_utility += int(parts[1].strip())
    return total_utility


def _resolve_min_utility(input_path, min_utility, min_sup_ratio=None):
    if min_sup_ratio is not None:
        total_utility = _sum_transaction_utility(input_path)
        return int(total_utility * float(min_sup_ratio) + 0.999999999)
    return int(min_utility)


def _read_output_lines(path):
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        return [line.strip() for line in f if line.strip()]


def _compare_outputs(java_output_path, python_output_path):
    java_lines = _read_output_lines(java_output_path)
    py_lines = _read_output_lines(python_output_path)

    strict_match = java_lines == py_lines
    set_match = set(java_lines) == set(py_lines)

    print("\n--- Java vs Python comparison ---")
    print(f"Java output lines   : {len(java_lines)}")
    print(f"Python output lines : {len(py_lines)}")
    print(f"Exact order match   : {strict_match}")
    print(f"Set-wise match      : {set_match}")

    if not set_match:
        java_only = sorted(set(java_lines) - set(py_lines))
        py_only = sorted(set(py_lines) - set(java_lines))
        if java_only:
            print("Lines present in Java only:")
            for line in java_only:
                print(f"  {line}")
        if py_only:
            print("Lines present in Python only:")
            for line in py_only:
                print(f"  {line}")

    return strict_match, set_match


# ── Entry point ──────────────────────────────────────────

if __name__ == "__main__":
    # Resolve all configured paths relative to this script directory.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = _resolve_path(script_dir, INPUT_FILE)
    output_path = _resolve_path(script_dir, OUTPUT_FILE)
    java_output_path = _resolve_path(script_dir, JAVA_OUTPUT_FILE)

    if RANDOM_SEED is not None:
        random.seed(RANDOM_SEED)

    min_utility = _resolve_min_utility(input_path, MIN_UTILITY, MIN_SUP_RATIO)

    if MIN_SUP_RATIO is None:
        print(f"Running HUIF-BA with min_utility = {MIN_UTILITY}")
    else:
        print(f"Running HUIF-BA with minsup ratio = {MIN_SUP_RATIO}")
    print(f"Resolved min_utility = {min_utility}")
    print(f"Input : {input_path}")
    print(f"Output: {output_path}")
    print()

    algo = AlgoBio_HUIF_BA()
    algo.run_algorithm(input_path, output_path, min_utility)
    algo.print_stats()

    print(f"\nResults written to: {output_path}")
    print("\n--- Output preview ---")
    with open(output_path, "r") as f:
        content = f.read()
    print(content if content else "(no high-utility itemsets found)")

    if COMPARE_WITH_JAVA_OUTPUT:
        if os.path.exists(java_output_path):
            _compare_outputs(java_output_path, output_path)
        else:
            print("\nJava output file not found. Run Java first or set JAVA_OUTPUT_FILE correctly.")