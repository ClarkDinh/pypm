"""
HUIM Algorithms - Python Implementation
========================================
Direct Python translation of two Java High Utility Itemset Mining algorithms:
  1. HUIM-BPSO  (Binary Particle Swarm Optimization)
  2. HUIM-ACO   (Ant Colony Optimization)

Both algorithms find all high-utility itemsets whose utility >= min_utility.

Usage
-----
Run from the command line:
    python huim_algorithms.py --algo bpso --input contextHUIM.txt --min_utility 40
    python huim_algorithms.py --algo aco  --input contextHUIM.txt --min_utility 40
    python huim_algorithms.py --algo both --input contextHUIM.txt --min_utility 40

Or import and call directly:
    from huim_algorithms import run_bpso, run_aco
    bpso_results = run_bpso("contextHUIM.txt", min_utility=40)
    aco_results  = run_aco ("contextHUIM.txt", min_utility=40)

Authors of original Java:
  HUIM-BPSO: Jerry Chun-Wei Lin, Lu Yang, Philippe Fournier-Viger (2016)
  HUIM-ACO : Jiakai Nan, Wei Song (2020)
Python translation: automated port for result-equivalence testing
"""

import math
import random
import time
import argparse
from pathlib import Path
from copy import deepcopy
from collections import defaultdict


DEFAULT_BPSO_OUTPUT = "python_bpso_output.txt"
DEFAULT_ACO_OUTPUT = "python_aco_output.txt"


# =============================================================================
#  SHARED UTILITIES
# =============================================================================

def read_database(input_path):
    """
    Parse the HUIM transaction database file.

    File format per line:
        items : transaction_utility : item_utilities
    Example:
        2 3 4:9:2 2 5

    Returns
    -------
    transactions : list of list of (item, utility)
    transaction_utilities : list of int  (total utility per transaction)
    item_twu : dict  {item -> TWU}
    """
    transactions = []
    transaction_utilities = []
    item_twu = defaultdict(int)

    with open(input_path, "r") as fh:
        for line in fh:
            line = line.strip()
            if not line or line[0] in ("#", "%", "@"):
                continue
            parts = line.split(":")
            items_str = parts[0].strip().split()
            trans_util = int(parts[1].strip())
            utils_str = parts[2].strip().split()

            items = [int(x) for x in items_str]
            utils = [int(x) for x in utils_str]

            for item in items:
                item_twu[item] += trans_util

            transactions.append(list(zip(items, utils)))
            transaction_utilities.append(trans_util)

    return transactions, transaction_utilities, item_twu


def resolve_input_path(input_path):
    """
    Resolve dataset path from common project locations.

    This lets the script run from the Python folder without requiring users
    to pass an absolute --input each time.
    """
    provided = Path(input_path)
    if provided.exists():
        return str(provided)

    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir / input_path,
        script_dir.parent / input_path,
        script_dir.parent / "Java" / "src" / input_path,
        script_dir.parent / "Java" / "bin" / input_path,
        script_dir.parent / "Java" / "lib" / input_path,
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    checked = [str(provided)] + [str(c) for c in candidates]
    raise FileNotFoundError(
        "Could not find input dataset file. Checked:\n- " + "\n- ".join(checked)
    )


# =============================================================================
#  HUIM-BPSO
# =============================================================================

class AlgoHUIM_BPSO:
    """
    Binary Particle Swarm Optimization for High Utility Itemset Mining.

    Direct Python translation of AlgoHUIM_BPSO.java
    (Jerry Chun-Wei Lin, Lu Yang, Philippe Fournier-Viger, 2016)
    """

    POP_SIZE   = 20
    ITERATIONS = 10000
    C1, C2    = 2, 2
    W          = 0.9

    def __init__(self):
        self.hui_sets   = []   # list of (itemset_str, fitness)
        self.population = []   # list of {'X': [...], 'fitness': int}
        self.p_best     = []
        self.g_best     = None
        self.V          = []   # velocities
        self.percentage  = []
        self.twu_pattern = []
        self.map_item_twu  = {}
        self.map_item_twu0 = {}
        self.database   = []   # list of list of (item, utility)

    # ------------------------------------------------------------------
    def run(self, input_path, min_utility):
        start = time.time()

        # ---- first pass: compute TWU ----
        raw_trans, trans_utils, item_twu = read_database(input_path)
        self.map_item_twu  = dict(item_twu)
        self.map_item_twu0 = dict(item_twu)

        # ---- second pass: filter low-TWU items, build database ----
        for tx in raw_trans:
            revised = []
            for (item, util) in tx:
                if self.map_item_twu.get(item, 0) >= min_utility:
                    revised.append((item, util))
                else:
                    self.map_item_twu0.pop(item, None)
            self.database.append(revised)

        self.twu_pattern = sorted(self.map_item_twu0.keys())
        n = len(self.twu_pattern)

        # initialise pBest / gBest placeholders
        self.p_best = [{'X': [0]*n, 'fitness': 0} for _ in range(self.POP_SIZE)]
        self.g_best = {'X': [0]*n, 'fitness': 0}

        if n > 0:
            self._generate_pop(min_utility)
            for _ in range(self.ITERATIONS):
                self._update(min_utility)

        elapsed = time.time() - start
        return self.hui_sets, elapsed

    # ------------------------------------------------------------------
    def _roulette_percent(self):
        total = sum(self.map_item_twu[i] for i in self.twu_pattern)
        pct, running = [], 0
        for i in self.twu_pattern:
            running += self.map_item_twu[i]
            pct.append(running / total)
        return pct

    def _roulette_select(self, percentage):
        r = random.random()
        for i, p in enumerate(percentage):
            if i == 0:
                if 0 <= r <= p:
                    return 0
            elif percentage[i-1] < r <= p:
                return i
        return len(percentage) - 1

    def _fit_calculate(self, X, k):
        if k == 0:
            return 0
        fitness = 0
        for tx in self.database:
            j = q = i = temp = total = 0
            while j < k and q < len(tx) and i < len(X):
                if X[i] == 1:
                    tx_item, tx_util = tx[q]
                    tw_item = self.twu_pattern[i]
                    if tx_item < tw_item:
                        q += 1
                    elif tx_item == tw_item:
                        total += tx_util
                        j += 1; q += 1; temp += 1; i += 1
                    else:
                        j += 1; i += 1
                else:
                    i += 1
            if temp == k:
                fitness += total
        return fitness

    def _insert(self, particle):
        parts = []
        for i, item in enumerate(self.twu_pattern):
            if particle['X'][i] == 1:
                parts.append(str(item))
        key = " ".join(parts) + " "
        if not any(h[0] == key for h in self.hui_sets):
            self.hui_sets.append((key, particle['fitness']))

    def _copy_particle(self, src, dst):
        dst['X'] = src['X'][:]
        dst['fitness'] = src['fitness']

    def _generate_pop(self, min_utility):
        self.percentage = self._roulette_percent()
        n = len(self.twu_pattern)
        for i in range(self.POP_SIZE):
            X = [0] * n
            k = int(random.random() * n)
            j = 0
            while j < k:
                pos = self._roulette_select(self.percentage)
                if X[pos] == 0:
                    X[pos] = 1
                    j += 1
            fit = self._fit_calculate(X, k)
            particle = {'X': X, 'fitness': fit}
            self.population.append(particle)
            self._copy_particle(particle, self.p_best[i])
            if fit >= min_utility:
                self._insert(particle)
            if i == 0:
                self._copy_particle(self.p_best[i], self.g_best)
            elif self.p_best[i]['fitness'] > self.g_best['fitness']:
                self._copy_particle(self.p_best[i], self.g_best)
            vel = [random.random() for _ in range(n)]
            self.V.append(vel)

    def _update(self, min_utility):
        n = len(self.twu_pattern)
        for i in range(self.POP_SIZE):
            k = 0
            r1 = random.random()
            r2 = random.random()
            # update velocity
            for j in range(n):
                v = (self.V[i][j]
                     + r1 * (self.p_best[i]['X'][j] - self.population[i]['X'][j])
                     + r2 * (self.g_best['X'][j]    - self.population[i]['X'][j]))
                v = max(-2.0, min(2.0, v))
                self.V[i][j] = v
            # update particle
            for j in range(n):
                t1 = random.random()
                t2 = 1.0 / (1.0 + math.exp(-self.V[i][j]))
                if t1 < t2:
                    self.population[i]['X'][j] = 1
                    k += 1
                else:
                    self.population[i]['X'][j] = 0
            self.population[i]['fitness'] = self._fit_calculate(self.population[i]['X'], k)
            if self.population[i]['fitness'] > self.p_best[i]['fitness']:
                self._copy_particle(self.population[i], self.p_best[i])
                if self.p_best[i]['fitness'] > self.g_best['fitness']:
                    self._copy_particle(self.p_best[i], self.g_best)
            if self.population[i]['fitness'] >= min_utility:
                self._insert(self.population[i])


# =============================================================================
#  HUIM-ACO  – supporting data structures
# =============================================================================

class Ant:
    """
    Direct translation of Ant.java
    """
    # class-level (static) decision table & exist-pheromones
    decision_table   = []
    exist_pheromones = []

    def __init__(self, length=0):
        self.bit_set       = set()       # replaces Java BitSet – stores item indices
        self.food_size     = 0
        self.food_twu      = 0
        self.current_food  = 0
        self.pass_food     = 0
        self.existed_foods    = []
        self.no_existed_foods = list(range(length))
        self._length = length            # total number of items

    # ---- food / bit helpers ----
    def is_own_food(self, idx):
        return idx in self.bit_set

    def set_food(self, bit_index):
        self.bit_set.add(bit_index)
        return self

    def bit_length(self):
        return max(self.bit_set) + 1 if self.bit_set else 0

    def cardinality(self):
        return len(self.bit_set)

    def clear_bit(self, idx):
        self.bit_set.discard(idx)

    def clear_all_bits(self):
        self.bit_set.clear()

    # ---- food tracking ----
    def set_existed_foods(self, idx):
        if idx not in self.existed_foods:
            self.existed_foods.append(idx)
            try:
                pos = self.no_existed_foods.index(idx)
                self.no_existed_foods.pop(pos)
            except ValueError:
                pass

    # ---- search strategies ----
    def search_food(self, htwus_1=None, huis=None, roulette=None):
        """Roulette-based search (method 1)."""
        while True:
            if not self.no_existed_foods:
                return -2
            while True:
                if roulette and roulette.is_changed and huis:
                    best_idx = huis.best_item_index
                    to_item = best_idx[roulette.whirl()]
                else:
                    to_item = roulette.whirl() if roulette else \
                              self.no_existed_foods[int(random.random() * len(self.no_existed_foods))]
                if to_item in self.no_existed_foods:
                    break
            if not self.is_own_food(to_item):
                return to_item

    def search_food_random(self):
        """Pure random search (fallback)."""
        while True:
            if not self.no_existed_foods:
                return -2
            to_item = self.no_existed_foods[int(random.random() * len(self.no_existed_foods))]
            if not self.is_own_food(to_item):
                return to_item

    def make_decision(self, decision_table):
        """Pheromone-table based decision (method 2)."""
        if not decision_table:
            return self.search_food_random()
        r = random.random()
        for i, p in enumerate(decision_table):
            if i == 0:
                if 0 <= r < p:
                    return Ant.exist_pheromones[0]
            elif decision_table[i-1] < r <= p:
                return Ant.exist_pheromones[i]
        return self.search_food_random()

    def selected_maximum_pheromones(self, global_pheromones):
        """Greedy maximum-pheromone selection (method 3)."""
        best_val = 0
        best_idx = -1
        for nf in self.no_existed_foods:
            a, b = (self.current_food, nf) if self.current_food < nf else (nf, self.current_food)
            val = global_pheromones[a][b]
            if val >= best_val:
                best_val = val
                best_idx = nf
        return best_idx

    def initialize_decision_table(self, global_pheromones):
        """Build the roulette for pheromone-guided search."""
        Ant.decision_table.clear()
        Ant.exist_pheromones.clear()
        total = 0.0
        for nf in self.no_existed_foods:
            a, b = (self.current_food, nf) if self.current_food < nf else (nf, self.current_food)
            total += global_pheromones[a][b]
        running = 0.0
        for nf in self.no_existed_foods:
            a, b = (self.current_food, nf) if self.current_food < nf else (nf, self.current_food)
            ph = global_pheromones[a][b]
            if ph != 0:
                running += ph
                Ant.decision_table.append(running / total)
                Ant.exist_pheromones.append(nf)

    def judge_food_size(self, trans_lists, item_list, database,
                        htwus_1, trans_utility_list=None):
        """Compute fitness (foodSize) and TWU (foodTWU) for current itemset."""
        food_size = 0
        food_twu  = 0
        for y in trans_lists:
            for x in item_list:
                v = database[y][x]
                if v is not None:
                    food_size += v
            if trans_utility_list is not None:
                food_twu += trans_utility_list[y]
        self.food_twu  = food_twu
        self.food_size = food_size

    def is_purchased_itemset(self, trans_lists, items_index, database, items_bitmap):
        """
        Check which transactions contain ALL items in the ant's current tour.
        Mirrors isPurchasedItemset in Ant.java (BitSet AND logic).
        """
        other_items_index = sorted(self.bit_set)   # bits set → item indices
        for idx in other_items_index:
            items_index.append(idx)

        if not other_items_index:
            return False

        # Start with bitmap of first item
        judged = set(items_bitmap[other_items_index[0]])
        mid_value = set(judged)

        for i in range(1, len(other_items_index)):
            judged &= set(items_bitmap[other_items_index[i]])

            if i == len(items_bitmap) - 1:
                if not judged:
                    self.clear_bit(other_items_index[i])
                    if other_items_index[i] in items_index:
                        items_index.remove(other_items_index[i])
                break

            if judged:
                mid_value = set(judged)
            else:
                judged = set(mid_value)
                self.clear_bit(other_items_index[i])
                if other_items_index[i] in items_index:
                    items_index.remove(other_items_index[i])

        if not judged:
            return False

        trans_lists.extend(sorted(judged))
        return True

    def release_pheromones(self, ant_colony, min_utility=None):
        a = min(self.current_food, self.pass_food)
        b = max(self.current_food, self.pass_food)
        if min_utility is not None:
            ant_colony.add_global_pheromones(a, b, self.food_size / min_utility)
        else:
            ant_colony.add_global_pheromones(a, b, 0.0)

    def copy_to(self, other):
        other.bit_set      = set(self.bit_set)
        other.food_size    = self.food_size
        other.food_twu     = self.food_twu
        other.current_food = self.current_food
        other.pass_food    = self.pass_food
        other.existed_foods    = self.existed_foods[:]
        other.no_existed_foods = self.no_existed_foods[:]

    def __lt__(self, other):   # for sort (descending food_size)
        return self.food_size > other.food_size


# ------------------------------------------------------------------
class Roulette:
    """Translation of Roulette.java"""

    def __init__(self, htwus_1, item_and_twu):
        self.roulette   = []
        self.is_changed = False
        self._init(htwus_1, item_and_twu)

    def _init(self, htwus_1, item_and_twu):
        total = sum(item_and_twu[i] for i in htwus_1)
        running = 0.0
        for i in htwus_1:
            running += item_and_twu[i]
            self.roulette.append(running / total)

    def whirl(self):
        r = random.random()
        for i, p in enumerate(self.roulette):
            if i == 0:
                if 0 <= r <= p:
                    return 0
            elif self.roulette[i-1] < r <= p:
                return i
        return len(self.roulette) - 1

    @property
    def is_changed(self):
        return self._is_changed

    @is_changed.setter
    def is_changed(self, v):
        self._is_changed = v

    def reinit(self, htwus_1, item_and_twu):
        self.roulette.clear()
        self._init(htwus_1, item_and_twu)


# ------------------------------------------------------------------
class HUI:
    def __init__(self, itemset, utility):
        self.itemset = itemset
        self.utility = utility


class HUIS:
    """Translation of HUIS.java"""

    def __init__(self):
        self.hui_set              = []
        self.best_item            = []
        self.best_item_index      = []
        self.best_item_spare      = []
        self.best_item_index_spare = []

    def add_hui_from_ant(self, ant, htwus_1):
        parts = []
        for i, item in enumerate(htwus_1):
            if ant.is_own_food(i):
                parts.append(str(item))
                if item not in self.best_item_spare:
                    self.best_item_spare.append(item)
                    self.best_item_index_spare.append(i)

        key = " ".join(parts) + " " if parts else ""

        if not self.hui_set:
            self.hui_set.append(HUI(key, ant.food_size))
        else:
            if not any(h.itemset == key for h in self.hui_set):
                self.hui_set.append(HUI(key, ant.food_size))

    def copy_spare_to_best(self):
        self.best_item_index = self.best_item_index_spare[:]
        self.best_item       = self.best_item_spare[:]
        self.best_item_spare.clear()
        self.best_item_index_spare.clear()


# ------------------------------------------------------------------
class ItemsBitMap:
    """
    Translation of ItemsBitMap.java
    Stores, for each item, the set of transaction indices where it appears.
    """

    def __init__(self):
        self.bitmaps = []   # list of sets (one per item in htwus_1)

    def create_bitmap(self, htwus_1, database):
        """
        database[y][x] is None if item x is absent from transaction y,
        otherwise it holds the utility value.
        """
        n_items = len(htwus_1)
        n_trans = len(database)
        self.bitmaps = [set() for _ in range(n_items)]
        for x in range(n_items):
            for y in range(n_trans):
                if database[y][x] is not None:
                    self.bitmaps[x].add(y)


# ------------------------------------------------------------------
class AntColony:
    """Translation of AntColony.java"""

    def __init__(self, length):
        self.ant_colony_size = 0
        self.ants            = []
        self.search_times    = 0
        self.thresh1 = 0.0   # searchMethodThreshold1
        self.thresh2 = 0.0   # searchMethodThreshold2
        # globalPheromones[x][y], x < y
        n = max(length - 1, 1)
        self.global_pheromones = [[0.0]*length for _ in range(n)]
        self.roulette          = None

        # convergence tracking
        self.first_hui  = 0
        self.second_hui = 0
        self.third_hui  = 0
        self.init_hui   = 0
        self.reset_flag         = False
        self.filter_flag        = True
        self.copy_elite_flag    = False
        self.init_pheromone_times = -1
        self._length = length

    def add_global_pheromones(self, x, y, value):
        if x < len(self.global_pheromones) and y < len(self.global_pheromones[x]):
            self.global_pheromones[x][y] += value

    # ---- initialise ----
    def initialize(self, min_utility, htwus_1, database, bitmaps, huis):
        for _ in range(self.ant_colony_size):
            ant = Ant(len(htwus_1))
            to_food = self.roulette.whirl()
            trans_lists, item_list = [], []
            ant.set_food(to_food).is_purchased_itemset(trans_lists, item_list, database, bitmaps)
            ant.current_food = to_food
            ant.set_existed_foods(to_food)
            ant.judge_food_size(trans_lists, item_list, database, htwus_1)
            self.ants.append(ant)
            if ant.food_size >= min_utility and ant.cardinality() > 0:
                huis.add_hui_from_ant(ant, htwus_1)

    # ---- main search loop ----
    def search_food(self, min_utility, database, htwus_1, bitmaps, huis,
                    item_and_twu, trans_utility_list, debug=False):

        for st in range(self.search_times):
            if self.reset_flag:
                huis.copy_spare_to_best()
                n = len(htwus_1)
                self.global_pheromones = [[0.0]*n for _ in range(max(n-1, 1))]

            for ai in range(self.ant_colony_size):
                if self.reset_flag:
                    self.ants[ai].existed_foods.clear()
                    self.ants[ai].no_existed_foods.clear()
                    for idx in huis.best_item_index:
                        self.ants[ai].no_existed_foods.append(idx)

                    self.roulette.is_changed = True
                    self.roulette.reinit(huis.best_item, item_and_twu)
                    to_food = huis.best_item_index[self.roulette.whirl()]
                    self.ants[ai].current_food = to_food
                    self.ants[ai].clear_all_bits()
                    self.ants[ai].set_existed_foods(to_food)

                    if ai == self.ant_colony_size - 1:
                        self.first_hui  = 0
                        self.second_hui = 0
                        self.third_hui  = 0
                        self.init_hui   = len(huis.hui_set)
                        self.init_pheromone_times = st + 1
                        self.reset_flag = False
                        self.filter_flag = True
                    continue

                trans_lists, item_list = [], []

                if self.init_pheromone_times == st:
                    method = random.random() * self.thresh1
                else:
                    method = random.random() * self.thresh1 if st == 0 else random.random()

                if method <= self.thresh1:
                    to_food = self.ants[ai].search_food(htwus_1, huis, self.roulette)
                    if to_food in (-1, -2):
                        continue
                    self._ant_move(ai, to_food, min_utility, trans_lists, item_list,
                                   database, htwus_1, bitmaps, huis, trans_utility_list)

                elif self.thresh1 < method < self.thresh2:
                    self.ants[ai].initialize_decision_table(self.global_pheromones)
                    to_food = self.ants[ai].make_decision(Ant.decision_table)
                    Ant.decision_table.clear()
                    Ant.exist_pheromones.clear()
                    if to_food == -2:
                        continue
                    self._ant_move(ai, to_food, min_utility, trans_lists, item_list,
                                   database, htwus_1, bitmaps, huis, trans_utility_list)

                else:
                    to_food = self.ants[ai].selected_maximum_pheromones(self.global_pheromones)
                    if to_food == -1:
                        continue
                    self._ant_move(ai, to_food, min_utility, trans_lists, item_list,
                                   database, htwus_1, bitmaps, huis, trans_utility_list)

            self.first_hui  = self.second_hui
            self.second_hui = self.third_hui
            self.third_hui  = len(huis.hui_set)

            if (self.first_hui != self.init_hui
                    and self.second_hui == self.first_hui
                    and self.second_hui == self.third_hui):
                self.reset_flag = True

            if self.first_hui != self.init_hui and self.filter_flag:
                self.copy_elite_flag = True

            if self.copy_elite_flag:
                self.ants.sort()
                elite_count = int(self.ant_colony_size * 0.2)
                group_size  = self.ant_colony_size // elite_count if elite_count else 1
                for ei in range(elite_count):
                    for pi in range(1, group_size):
                        target = ei + pi * elite_count
                        if target < self.ant_colony_size:
                            self.ants[ei].copy_to(self.ants[target])
                self.filter_flag     = False
                self.copy_elite_flag = False

            if debug:
                print(f"  iter {st}: HUIs={len(huis.hui_set)}  "
                      f"{self.first_hui} {self.second_hui} {self.third_hui}  "
                      f"reset={self.reset_flag}")

    def _ant_move(self, ai, to_food, min_utility, trans_lists, item_list,
                  database, htwus_1, bitmaps, huis, trans_utility_list):
        ant = self.ants[ai]
        if ant.set_food(to_food).is_purchased_itemset(trans_lists, item_list, database, bitmaps):
            ant.pass_food    = ant.current_food
            ant.current_food = to_food
            ant.judge_food_size(trans_lists, item_list, database, htwus_1, trans_utility_list)
            trans_lists.clear()
            item_list.clear()

            if ant.food_twu < min_utility and ant.cardinality() == 2:
                ant.release_pheromones(self, min_utility)
                ant.clear_bit(to_food)
                ant.current_food = ant.pass_food
            elif ant.food_twu < min_utility:
                ant.clear_bit(to_food)
                ant.current_food = ant.pass_food
            else:
                ant.release_pheromones(self, min_utility)

            if ant.food_size >= min_utility and ant.cardinality() > 0:
                huis.add_hui_from_ant(ant, htwus_1)

        ant.set_existed_foods(to_food)


# =============================================================================
#  AlgoHUIMACO  (top-level runner, mirrors AlgoHUIMACO.java)
# =============================================================================

class AlgoHUIMACO:
    """
    Ant Colony Optimization for High Utility Itemset Mining.
    Direct Python translation of AlgoHUIMACO.java (Jiakai Nan, Wei Song, 2020)
    """

    def run(self, input_path, min_utility, debug=False):
        start = time.time()

        # ---- parse & pre-process data ----
        raw_trans, trans_utils, item_twu = read_database(input_path)
        item_and_twu = dict(item_twu)

        # build HTWUs_1 (items with TWU >= min_utility)
        htwus_1 = sorted([item for item, twu in item_and_twu.items() if twu >= min_utility])

        # remove low-TWU items and build 2D database matrix
        n_trans = len(raw_trans)
        database = [[None] * len(htwus_1) for _ in range(n_trans)]
        adj_trans_utils = list(trans_utils)

        for y, tx in enumerate(raw_trans):
            for (item, util) in tx:
                if item in htwus_1:
                    x = htwus_1.index(item)
                    database[y][x] = util
                else:
                    adj_trans_utils[y] -= util

        trans_utility_list = adj_trans_utils

        # ---- bitmap ----
        items_bm = ItemsBitMap()
        items_bm.create_bitmap(htwus_1, database)

        # ---- ant colony ----
        huis = HUIS()
        if htwus_1:
            colony = AntColony(len(htwus_1))
            colony.ant_colony_size = 10000
            colony.search_times    = 50
            colony.thresh1         = 0.1
            colony.thresh2         = 0.7
            colony.roulette        = Roulette(htwus_1, item_and_twu)

            colony.initialize(min_utility, htwus_1, database,
                              items_bm.bitmaps, huis)
            colony.search_food(min_utility, database, htwus_1,
                               items_bm.bitmaps, huis,
                               item_and_twu, trans_utility_list, debug)

        elapsed = time.time() - start
        results = [(h.itemset, h.utility) for h in huis.hui_set]
        return results, elapsed


# =============================================================================
#  PUBLIC API
# =============================================================================

def run_bpso(input_path, min_utility, output_path=None):
    """
    Run HUIM-BPSO and return list of (itemset_str, utility).
    Optionally write results to output_path.
    """
    algo = AlgoHUIM_BPSO()
    results, elapsed = algo.run(input_path, min_utility)
    _report("HUIM-BPSO", results, elapsed)
    if output_path:
        _write_output(results, output_path)
    return results


def run_aco(input_path, min_utility, output_path=None, debug=False):
    """
    Run HUIM-ACO and return list of (itemset_str, utility).
    Optionally write results to output_path.
    """
    algo = AlgoHUIMACO()
    results, elapsed = algo.run(input_path, min_utility, debug=debug)
    _report("HUIM-ACO", results, elapsed)
    if output_path:
        _write_output(results, output_path)
    return results


def compare_algorithms(input_path, min_utility):
    """
    Run both algorithms and show a side-by-side comparison.
    Returns (bpso_set, aco_set) where each is a frozenset of itemset strings.
    """
    print(f"\n{'='*60}")
    print(f"Comparing BPSO vs ACO  |  min_utility = {min_utility}")
    print(f"Input: {input_path}")
    print(f"{'='*60}\n")

    bpso_results, _ = AlgoHUIM_BPSO().run(input_path, min_utility)
    aco_results,  _ = AlgoHUIMACO().run(input_path, min_utility)

    bpso_items = {r[0].strip() for r in bpso_results}
    aco_items  = {r[0].strip() for r in aco_results}

    print(f"\n--- BPSO found {len(bpso_items)} HUIs ---")
    for s in sorted(bpso_items):
        util = next(r[1] for r in bpso_results if r[0].strip() == s)
        print(f"  {s}  #UTIL: {util}")

    print(f"\n--- ACO  found {len(aco_items)} HUIs ---")
    for s in sorted(aco_items):
        util = next(r[1] for r in aco_results if r[0].strip() == s)
        print(f"  {s}  #UTIL: {util}")

    only_bpso = bpso_items - aco_items
    only_aco  = aco_items  - bpso_items
    common    = bpso_items & aco_items

    print(f"\n--- Overlap ---")
    print(f"  Common      : {len(common)}")
    print(f"  Only BPSO   : {len(only_bpso)}  {sorted(only_bpso)}")
    print(f"  Only ACO    : {len(only_aco)}   {sorted(only_aco)}")

    return frozenset(bpso_items), frozenset(aco_items)


# =============================================================================
#  HELPERS
# =============================================================================

def _report(name, results, elapsed):
    print(f"\n{'='*55}")
    print(f"  {name} – STATS")
    print(f"{'='*55}")
    print(f"  Total time          : {elapsed*1000:.1f} ms")
    print(f"  High-utility count  : {len(results)}")
    print(f"{'='*55}")
    for itemset, util in results:
        print(f"  {itemset.strip()}  #UTIL: {util}")


def _write_output(results, path):
    with open(path, "w") as fh:
        for itemset, util in results:
            fh.write(f"{itemset}#UTIL: {util}\n")
    print(f"\n  Results written to: {path}")


# =============================================================================
#  CLI  ENTRY-POINT
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="HUIM-BPSO / HUIM-ACO – Python implementation"
    )
    parser.add_argument("--algo",        choices=["bpso", "aco", "both", "compare"],
                        default="both",
                        help="Which algorithm to run (default: both)")
    parser.add_argument("--input",       default="contextHUIM.txt",
                        help="Path to the transaction database file")
    parser.add_argument("--min_utility", type=int, default=20,
                        help="Minimum utility threshold (default: 20)")
    parser.add_argument("--output",      default=None,
                    help=("Optional output file path. For --algo both, this is used "
                        "as base name and _bpso/_aco suffixes are appended."))
    parser.add_argument("--debug",       action="store_true",
                        help="Print ACO iteration details")
    args = parser.parse_args()
    args.input = resolve_input_path(args.input)

    if args.algo == "bpso":
        out_bpso = args.output if args.output else DEFAULT_BPSO_OUTPUT
        run_bpso(args.input, args.min_utility, out_bpso)
    elif args.algo == "aco":
        out_aco = args.output if args.output else DEFAULT_ACO_OUTPUT
        run_aco(args.input, args.min_utility, out_aco, args.debug)
    elif args.algo == "compare":
        compare_algorithms(args.input, args.min_utility)
    else:   # both
        out_bpso = (args.output.replace(".txt", "_bpso.txt")
                    if args.output else DEFAULT_BPSO_OUTPUT)
        out_aco = (args.output.replace(".txt", "_aco.txt")
                   if args.output else DEFAULT_ACO_OUTPUT)
        run_bpso(args.input, args.min_utility,
                 out_bpso)
        run_aco (args.input, args.min_utility,
                 out_aco,
                 args.debug)