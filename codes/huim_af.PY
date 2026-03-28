"""
HUIM-AF: High-Utility Itemset Mining using Artificial Fish Swarm Algorithm
Python translation of AlgoHUIM_AF.java

Usage:
    python huim_af.py --input DB_Utility.txt --output output.txt --min_utility 40

To test matching with Java output, adjust --min_utility as needed.
"""

import argparse
import os
import time
from copy import deepcopy


# ─────────────────────────────────────────────
#  Java-compatible Random Number Generator
# ─────────────────────────────────────────────

class JavaRandom:
    """
    Java-compatible Linear Congruential Generator (LCG).
    Matches java.util.Random behavior exactly.
    """
    def __init__(self, seed=None):
        if seed is None:
            # Use current time as seed
            seed = int(time.time() * 1000) & 0xFFFFFFFFFFFFFFFF
        else:
            seed = int(seed) & 0xFFFFFFFFFFFFFFFF
        
        # Java Random uses XOR with seed value
        self.seed = (seed ^ 0x5DEECE66D) & ((1 << 48) - 1)
    
    def next(self, bits):
        """Generate next random number with specified bits."""
        self.seed = (self.seed * 0x5DEECE66D + 0xB) & ((1 << 48) - 1)
        return self.seed >> (48 - bits)
    
    def nextDouble(self):
        """Returns double in range [0.0, 1.0), matching java.util.Random.nextDouble()"""
        return ((self.next(26) << 27) + self.next(27)) / (1 << 53)
    
    def nextInt(self, n=None):
        """Returns int, optionally bounded to [0, n)"""
        if n is None:
            return int(self.next(32)) - (1 << 31)
        
        if n <= 0:
            raise ValueError("n must be positive")
        
        if (n & -n) == n:  # n is power of 2
            return (n * self.next(31)) >> 31
        
        bits = self.next(31)
        val = bits % n
        while bits - val + (n - 1) < 0:
            bits = self.next(31)
            val = bits % n
        return val


# Create global random instance matching Java's default
_java_random = None

def set_random_seed(seed):
    """Set the global Java-compatible random seed."""
    global _java_random
    _java_random = JavaRandom(seed)

def get_random():
    """Get the global Java-compatible random instance."""
    global _java_random
    if _java_random is None:
        _java_random = JavaRandom()
    return _java_random


# ─────────────────────────────────────────────
#  Data classes
# ─────────────────────────────────────────────

class Pair:
    """Represents an item and its utility in a transaction."""
    def __init__(self, item=0, utility=0):
        self.item = item
        self.utility = utility


class HUI:
    """A discovered high-utility itemset."""
    def __init__(self, itemset: str, fitness: int):
        self.itemset = itemset
        self.fitness = fitness


class Item:
    """An item with a transaction-id bitmap (as a Python set of ints)."""
    def __init__(self, item: int, transaction_count: int):
        self.item = item
        self.TIDS: set = set()          # set of transaction indices
        self.transaction_count = transaction_count


# ─────────────────────────────────────────────
#  Fish class
# ─────────────────────────────────────────────

class Fish:
    """
    Artificial fish individual.
    X is a Python list of booleans (mirrors Java BitSet).
    """
    def __init__(self, length: int):
        self.X: list[bool] = [False] * length
        self.fitness: int = 0

    def copy_fish(self, other: "Fish"):
        self.X = other.X[:]
        self.fitness = other.fitness

    # ── fitness calculation ──────────────────
    def calculate_fitness(self, k: int, templist: list[int],
                          database: list[list[Pair]],
                          twu_pattern: list[int]):
        """
        k        – number of set bits (items in the candidate itemset)
        templist – list of transaction indices where the itemset occurs
        """
        if k == 0:
            self.fitness = 0
            return

        fitness = 0
        for p in templist:
            transaction = database[p]
            i = 0          # index into self.X / twu_pattern
            q = 0          # index into transaction
            temp = 0       # count of matched items
            s = 0          # accumulated utility

            while q < len(transaction) and i < len(self.X):
                if self.X[i]:
                    if transaction[q].item == twu_pattern[i]:
                        s += transaction[q].utility
                        i += 1
                        q += 1
                        temp += 1
                    else:
                        q += 1
                else:
                    i += 1

            if temp == k:
                fitness += s

        self.fitness = fitness

    def cardinality(self) -> int:
        return sum(1 for b in self.X if b)

    def length(self) -> int:
        return len(self.X)

    def get(self, i: int) -> bool:
        return self.X[i] if i < len(self.X) else False

    def set_bit(self, i: int, value: bool = True):
        self.X[i] = value

    def clear_bit(self, i: int):
        self.X[i] = False

    def __lt__(self, other: "Fish"):
        # Java compareTo returns -(fitness - other.fitness)  →  sort descending
        return self.fitness > other.fitness   # Python sort is ascending; flip


# ─────────────────────────────────────────────
#  Main algorithm
# ─────────────────────────────────────────────

class AlgoHUIM_AF:

    POP_SIZE   = 20
    ITERATIONS = 10000
    TRY_TIME   = 3
    DELTA      = 0.9

    def __init__(self):
        self.max_memory     = 0.0
        self.start_time     = 0
        self.end_time       = 0

        self.transaction_count = 0
        self.map_item_to_twu:  dict[int, int] = {}
        self.map_item_to_twu0: dict[int, int] = {}
        self.twu_pattern:      list[int]      = []

        self.database:         list[list[Pair]] = []
        self.items:            list[Item]       = []

        self.fish_population:    list[Fish] = []
        self.subfish_population: list[Fish] = []
        self.hui_sets:           list[HUI]  = []
        self.hui_ba:             list[Fish] = []

        self.percentage:     list[float] = []
        self.percent_hui_ba: list[float] = []

        self.step   = 0
        self.visual = 0
        self.is_swarm  = False
        self.is_fellow = False

    # ── public entry point ───────────────────
    def run_algorithm(self, input_path: str, output_path: str, min_utility: int):
        self.start_time = time.time()

        # Handle relative paths - look in script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if not os.path.isabs(input_path):
            test_path = os.path.join(script_dir, input_path)
            if os.path.exists(test_path):
                input_path = test_path
        
        if not os.path.isabs(output_path):
            output_path = os.path.join(script_dir, output_path)

        # ── first pass: compute TWU ──────────
        with open(input_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in ('#', '%', '@'):
                    continue
                self.transaction_count += 1
                parts = line.split(':')
                items_str = parts[0].split()
                trans_utility = int(parts[1])
                for it in items_str:
                    item = int(it)
                    self.map_item_to_twu[item]  = self.map_item_to_twu.get(item, 0)  + trans_utility
                    self.map_item_to_twu0[item] = self.map_item_to_twu0.get(item, 0) + trans_utility

        # ── second pass: build database ──────
        with open(input_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in ('#', '%', '@'):
                    continue
                parts = line.split(':')
                items_str      = parts[0].split()
                utility_values = parts[2].split()

                revised = []
                for i, it in enumerate(items_str):
                    p = Pair(int(it), int(utility_values[i]))
                    if self.map_item_to_twu.get(p.item, 0) >= min_utility:
                        revised.append(p)
                    else:
                        self.map_item_to_twu0.pop(p.item, None)
                self.database.append(revised)

        # twuPattern: sorted list of promising items
        self.twu_pattern = sorted(self.map_item_to_twu0.keys())

        # build bitmap items
        self.items = [Item(it, self.transaction_count) for it in self.twu_pattern]
        for t_idx, transaction in enumerate(self.database):
            for j, item_obj in enumerate(self.items):
                for pair in transaction:
                    if item_obj.item == pair.item:
                        item_obj.TIDS.add(t_idx)

        # ── run the fish swarm ───────────────
        if self.twu_pattern:
            self._generate_pop(min_utility)

            for j in range(self.ITERATIONS):
                self.visual = int(len(self.twu_pattern) * 0.1) + 1
                for i in range(self.POP_SIZE):
                    self.is_swarm  = False
                    self.is_fellow = False

                    fellow_fish = self._follow(i, min_utility)
                    if not self.is_fellow:
                        swarm_fish = self._swarm(i, min_utility)
                        if self.is_swarm:
                            self._subpop_set(i, swarm_fish)
                    else:
                        self._subpop_set(i, fellow_fish)

                    if not self.is_swarm and not self.is_fellow:
                        prey_fish = self._prey(i, min_utility)
                        self._subpop_set(i, prey_fish)

                self.subfish_population.extend(self.fish_population)
                self.subfish_population.sort()           # descending fitness
                for k in range(len(self.fish_population)):
                    self.fish_population[k] = self.subfish_population[k]
                self.subfish_population.clear()

        self._write_out(output_path)
        self.end_time = time.time()

    def _subpop_set(self, i: int, fish: "Fish"):
        """Mirror Java subfishpopulation.add(i, fish) – insert at index i."""
        if i < len(self.subfish_population):
            self.subfish_population[i] = fish
        else:
            # pad with None then set
            while len(self.subfish_population) < i:
                self.subfish_population.append(None)
            self.subfish_population.append(fish)

    # ── population initialisation ────────────
    def _generate_pop(self, min_utility: int):
        self.percentage = self._roulette_percent()

        for i in range(self.POP_SIZE):
            fish = Fish(len(self.twu_pattern))
            j = 0
            k = int(get_random().nextDouble() * len(self.twu_pattern))
            while j < k:
                temp = self._roulette_select(self.percentage)
                if not fish.get(temp):
                    j += 1
                    fish.set_bit(temp)

            trans_list: list[int] = []
            self._is_rba_individual(fish, trans_list)
            fish.calculate_fitness(k, trans_list, self.database, self.twu_pattern)
            self.fish_population.append(fish)

            if self.fish_population[i].fitness >= min_utility:
                self._insert(self.fish_population[i])
                self._add_hui_ba(self.fish_population[i])

    # ── follow behaviour ─────────────────────
    def _follow(self, i: int, min_utility: int) -> "Fish":
        size = len(self.twu_pattern)
        new_follow = Fish(size)
        new_follow.copy_fish(self.fish_population[i])
        best_fish = Fish(size)
        best_fish.copy_fish(self.fish_population[0])

        for m in range(self.POP_SIZE):
            dis_list = self._xor_individual(self.fish_population[i], self.fish_population[m])
            dis = len(dis_list)
            if self.visual > dis and self.fish_population[m].fitness > best_fish.fitness:
                best_fish.copy_fish(self.fish_population[m])

        dis1 = self._xor_individual(best_fish, self.fish_population[i])
        self.step = int(len(dis1) * get_random().nextDouble()) + 1

        if len(dis1) > 0:
            for _ in range(self.step):
                change_bit = int(len(dis1) * get_random().nextDouble())
                cb = dis1[change_bit]
                if new_follow.get(cb):
                    new_follow.clear_bit(cb)
                else:
                    new_follow.set_bit(cb)

            trans_list: list[int] = []
            self._is_rba_individual(new_follow, trans_list)
            new_follow.calculate_fitness(new_follow.cardinality(), trans_list,
                                         self.database, self.twu_pattern)
            if new_follow.fitness >= min_utility:
                self._insert(new_follow)
                self._add_hui_ba(new_follow)
            self.is_fellow = True
            return new_follow
        else:
            self.is_fellow = False
            return None

    # ── swarm behaviour ──────────────────────
    def _swarm(self, i: int, min_utility: int) -> "Fish":
        size = len(self.twu_pattern)
        count1 = [0] * size
        count0 = [0] * size
        new_swarm = Fish(size)
        new_swarm.copy_fish(self.fish_population[i])
        center_fish = Fish(size)

        for m in range(self.POP_SIZE):
            dis_list = self._xor_individual(new_swarm, self.fish_population[m])
            dis = len(dis_list)
            if self.visual > dis:
                for j in range(size):
                    if self.fish_population[m].get(j):
                        count1[j] += 1
                    else:
                        count0[j] += 1

        for j in range(size):
            center_fish.set_bit(j, count1[j] >= count0[j])

        trans_list: list[int] = []
        self._is_rba_individual(center_fish, trans_list)
        center_fish.calculate_fitness(center_fish.cardinality(), trans_list,
                                      self.database, self.twu_pattern)
        if center_fish.fitness >= min_utility:
            self._insert(center_fish)
            self._add_hui_ba(center_fish)

        if center_fish.fitness > self.fish_population[i].fitness:
            dis_list = self._xor_individual(center_fish, self.fish_population[i])
            self.step = int(len(dis_list) * get_random().nextDouble()) + 1
            if len(dis_list) > 0:
                for _ in range(self.step):
                    change_bit = int(len(dis_list) * get_random().nextDouble())
                    cb = dis_list[change_bit]
                    if new_swarm.get(cb):
                        new_swarm.clear_bit(cb)
                    else:
                        new_swarm.set_bit(cb)

            trans_list = []
            self._is_rba_individual(new_swarm, trans_list)
            new_swarm.calculate_fitness(new_swarm.cardinality(), trans_list,
                                        self.database, self.twu_pattern)
            if new_swarm.fitness >= min_utility:
                self._insert(new_swarm)
                self._add_hui_ba(new_swarm)
            self.is_swarm = True
            return new_swarm
        else:
            return None

    # ── prey behaviour ───────────────────────
    def _prey(self, i: int, min_utility: int) -> "Fish":
        size = len(self.twu_pattern)
        trans_list: list[int] = []
        temp_fish = Fish(size)
        temp_fish.copy_fish(self.fish_population[i])
        new_prey = Fish(size)
        new_prey.copy_fish(self.fish_population[i])

        flag = 0
        for _ in range(self.TRY_TIME):
            self.step = int(get_random().nextDouble() * self.visual) + 1
            for _ in range(self.step):
                change_bit = int(size * get_random().nextDouble())
                if temp_fish.get(change_bit):
                    temp_fish.clear_bit(change_bit)
                else:
                    temp_fish.set_bit(change_bit)

            self._is_rba_individual(temp_fish, trans_list)
            temp_fish.calculate_fitness(temp_fish.cardinality(), trans_list,
                                        self.database, self.twu_pattern)
            if temp_fish.fitness >= min_utility:
                self._insert(temp_fish)
                self._add_hui_ba(temp_fish)

            if temp_fish.fitness > new_prey.fitness:
                flag = 1
                new_prey.copy_fish(temp_fish)

            trans_list.clear()
            if flag == 1:
                break

        if flag == 0:
            self.step = int(get_random().nextDouble() * self.visual) + 1
            for _ in range(self.step):
                change_bit = int(len(self.twu_pattern) * get_random().nextDouble())
                if self.fish_population[i].get(change_bit):
                    new_prey.clear_bit(change_bit)
                else:
                    new_prey.set_bit(change_bit)

            self._is_rba_individual(new_prey, trans_list)
            new_prey.calculate_fitness(new_prey.cardinality(), trans_list,
                                       self.database, self.twu_pattern)
            if new_prey.fitness >= min_utility:
                self._insert(new_prey)
                self._add_hui_ba(new_prey)

        return new_prey

    # ── RBA individual check ─────────────────
    def _is_rba_individual(self, fish: "Fish", out_list: list[int]) -> bool:
        temp_indices = [i for i in range(fish.length()) if fish.get(i)]
        if not temp_indices:
            return False

        # start with TIDS of first item
        current_tids = self.items[temp_indices[0]].TIDS.copy()
        mid_tids     = current_tids.copy()

        for idx in temp_indices[1:]:
            intersected = current_tids & self.items[idx].TIDS
            if intersected:
                current_tids = intersected
                mid_tids     = intersected.copy()
            else:
                current_tids = mid_tids.copy()
                fish.clear_bit(idx)

        if not current_tids:
            return False

        out_list.extend(sorted(current_tids))
        return True

    # ── XOR difference list ──────────────────
    def _xor_individual(self, a: "Fish", b: "Fish") -> list[int]:
        size = max(len(a.X), len(b.X))
        result = []
        for i in range(size):
            av = a.get(i) if i < len(a.X) else False
            bv = b.get(i) if i < len(b.X) else False
            if av != bv:
                result.append(i)
        return result

    # ── huiBA management ────────────────────
    def _add_hui_ba(self, fish: "Fish"):
        tmp = Fish(len(self.twu_pattern))
        tmp.copy_fish(fish)
        for existing in self.hui_ba:
            if tmp.X == existing.X:
                return
        self.hui_ba.append(tmp)

    def _roulette_percent_hui_ba(self) -> list[float]:
        total = sum(f.fitness for f in self.hui_ba)
        result, running = [], 0.0
        for f in self.hui_ba:
            running += f.fitness
            result.append(running / total)
        return result

    def _roulette_select_hui_ba(self, pct: list[float]) -> int:
        r = get_random().nextDouble()
        for i, p in enumerate(pct):
            if i == 0:
                if 0 <= r <= p:
                    return 0
            elif pct[i-1] < r <= p:
                return i
        return len(pct) - 1

    # ── roulette for initial pop ─────────────
    def _roulette_percent(self) -> list[float]:
        total = sum(self.map_item_to_twu[it] for it in self.twu_pattern)
        result, running = [], 0.0
        for it in self.twu_pattern:
            running += self.map_item_to_twu[it]
            result.append(running / total)
        return result

    def _roulette_select(self, pct: list[float]) -> int:
        r = get_random().nextDouble()
        for i, p in enumerate(pct):
            if i == 0:
                if 0 <= r <= p:
                    return 0
            elif pct[i-1] < r <= p:
                return i
        return len(pct) - 1

    # ── insert into huiSets ──────────────────
    def _insert(self, fish: "Fish"):
        parts = []
        for i in range(len(self.twu_pattern)):
            if fish.get(i):
                parts.append(str(self.twu_pattern[i]))
        
        # Skip empty itemsets
        if not parts:
            return
            
        itemset_str = ' '.join(parts) + ' '

        if not self.hui_sets:
            self.hui_sets.append(HUI(itemset_str, fish.fitness))
        else:
            for existing in self.hui_sets:
                if existing.itemset == itemset_str:
                    return          # already present
            self.hui_sets.append(HUI(itemset_str, fish.fitness))

    # ── output ───────────────────────────────
    def _write_out(self, output_path: str):
        # Sort hui_sets by itemset string for consistent output order
        self.hui_sets.sort(key=lambda h: h.itemset)
        
        lines = []
        for hui in self.hui_sets:
            lines.append(f"{hui.itemset}#UTIL: {hui.fitness}")
        with open(output_path, 'w') as f:
            for line in lines:
                f.write(line + '\n')
            f.write('\n')  # Extra newline at the end, same as Java's writer.newLine()

    def print_stats(self):
        elapsed_ms = int((self.end_time - self.start_time) * 1000)
        print("=============  HUIM-AF ALGORITHM v.2.50 - STATS =============")
        print(f" Total time ~ {elapsed_ms} ms")
        print(f" High-utility itemsets count : {len(self.hui_sets)}")
        print("===================================================")


# ─────────────────────────────────────────────
#  Test / comparison helper
# ─────────────────────────────────────────────

def compare_outputs(file_a: str, file_b: str) -> bool:
    """
    Compare two output files (order-independent).
    Returns True if they contain exactly the same itemsets with the same utilities.
    """
    def parse(path):
        result = {}
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if '#UTIL:' in line:
                        parts   = line.split('#UTIL:')
                        itemset = frozenset(parts[0].strip().split())
                        util    = int(parts[1].strip())
                        result[itemset] = util
        except FileNotFoundError:
            print(f"File not found: {path}")
        return result

    a, b = parse(file_a), parse(file_b)
    if a == b:
        print("✅  MATCH — both outputs are identical.")
        return True
    else:
        only_a = {k: a[k] for k in a if k not in b}
        only_b = {k: b[k] for k in b if k not in a}
        diff   = {k for k in a if k in b and a[k] != b[k]}
        if only_a:
            print(f"❌  Only in {file_a}  ({len(only_a)} itemset(s)):")
            for k, v in only_a.items():
                print(f"     {' '.join(sorted(k))}  util={v}")
        if only_b:
            print(f"❌  Only in {file_b}  ({len(only_b)} itemset(s)):")
            for k, v in only_b.items():
                print(f"     {' '.join(sorted(k))}  util={v}")
        if diff:
            print(f"❌  Same itemset, different utility  ({len(diff)} case(s)):")
            for k in diff:
                print(f"     {' '.join(sorted(k))}  → {file_a}: {a[k]}  {file_b}: {b[k]}")
        return False


# ─────────────────────────────────────────────
#  Direct parameters (no argparse)
# ─────────────────────────────────────────────

# ====== SET PARAMETERS HERE ======
INPUT_PATH = "DB_Utility.txt"
OUTPUT_PATH = "outputs.txt"
MIN_UTILITY = 20
SEED = 0
COMPARE_PATH = None   # e.g. "output.txt", or None to skip comparison
# =================================


if __name__ == '__main__':
    # Set random seed
    if SEED is not None:
        set_random_seed(SEED)
        print(f"Using random seed: {SEED}")

    algo = AlgoHUIM_AF()
    algo.run_algorithm(INPUT_PATH, OUTPUT_PATH, MIN_UTILITY)
    algo.print_stats()

    print(f"\nOutput written to: {OUTPUT_PATH}")

    if COMPARE_PATH:
        print(f"\nComparing Python output ({OUTPUT_PATH}) vs Java output ({COMPARE_PATH}):")
        compare_outputs(OUTPUT_PATH, COMPARE_PATH)
