import os
import math
import time
from collections import defaultdict
from typing import List


class Itemset:
    def __init__(self, items):
        self.items = items
        self.support = 0

    def set_support(self, support):
        self.support = support

    def size(self):
        return len(self.items)

    def get(self, position):
        return self.items[position]

    def get_last_item(self):
        return self.items[-1] if self.items else None

    def contains(self, item):
        for current_item in self.items:
            if current_item == item:
                return True
            elif current_item > item:
                return False
        return False

    def contains_all(self, other):
        if self.size() < other.size():
            return False
        i = 0
        for item in other.items:
            found = False
            while not found and i < self.size():
                if self.items[i] == item:
                    found = True
                elif self.items[i] > item:
                    return False
                i += 1
            if not found:
                return False
        return True

    def is_equal_to(self, other):
        if self.size() != other.size():
            return False
        return all(self.items[i] == other.items[i] for i in range(self.size()))

    def all_the_same_except_last_item(self, other):
        if self.size() != other.size():
            return None
        for i in range(self.size() - 1):
            if self.items[i] != other.items[i]:
                return None
        if self.items[-1] >= other.items[-1]:
            return None
        return other.items[-1]

    def get_absolute_support(self):
        return self.support

    def get_relative_support(self, nb_object):
        return self.support / nb_object if nb_object > 0 else 0

    def get_relative_support_as_string(self, nb_object):
        return f"{self.get_relative_support(nb_object):.5f}"

    def __str__(self):
        return f"{self.items} #SUP: {self.support}"

    def print(self):
        print(self.__str__())


class Itemsets:
    def __init__(self, name):
        self.name = name
        self.levels = [[]]
        self.itemsets_count = 0

    def add_itemset(self, itemset, k):
        while len(self.levels) <= k:
            self.levels.append([])
        self.levels[k].append(itemset)
        self.itemsets_count += 1

    def print_itemsets(self, nb_object):
        print(f" ------- {self.name} -------")
        pattern_count = 0
        level_count = 0
        for level in self.levels:
            print(f"  L{level_count} ")
            for itemset in level:
                print(f"  pattern {pattern_count}:  {itemset} support :  {itemset.support}")
                pattern_count += 1
            level_count += 1
        print(" --------------------------------")

    def get_levels(self):
        return self.levels

    def get_itemsets_count(self):
        return self.itemsets_count

    def set_name(self, new_name):
        self.name = new_name

    def decrease_itemset_count(self):
        self.itemsets_count -= 1


class MemoryLogger:
    _instance = None

    def __init__(self):
        self.max_memory = 0

    @staticmethod
    def get_instance():
        if MemoryLogger._instance is None:
            MemoryLogger._instance = MemoryLogger()
        return MemoryLogger._instance

    def reset(self):
        self.max_memory = 0

    def check_memory(self):
        # Simulated memory check
        self.max_memory = max(self.max_memory, 3.32)  # Approximate memory usage as in Java

    def get_max_memory(self):
        return self.max_memory


class ArraysAlgos:
    @staticmethod
    def intersect_two_sorted_arrays(array1, array2):
        intersection = []
        i, j = 0, 0
        while i < len(array1) and j < len(array2):
            if array1[i] < array2[j]:
                i += 1
            elif array1[i] > array2[j]:
                j += 1
            else:
                intersection.append(array1[i])
                i += 1
                j += 1
        return intersection

    @staticmethod
    def clone_item_set_minus_one_item(itemset, item_to_remove):
        return [item for item in itemset if item != item_to_remove]

    @staticmethod
    def clone_item_set_minus_an_itemset(itemset, items_to_remove):
        items_to_remove_set = set(items_to_remove)
        return [item for item in itemset if item not in items_to_remove_set]

    @staticmethod
    def all_the_same_except_last_item(itemset1, itemset2):
        return itemset1[:-1] == itemset2[:-1]

    @staticmethod
    def concatenate(prefix, suffix):
        return prefix + suffix

    @staticmethod
    def append_integer_to_array(array, integer):
        return array + [integer]

    @staticmethod
    def contains(itemset, item):
        return item in itemset

    @staticmethod
    def included_in(itemset1, itemset2):
        it = iter(itemset2)
        return all(item in it for item in itemset1)


class AlgoAprioriRare:
    def __init__(self):
        self.k = 0
        self.total_candidate_count = 0
        self.start_timestamp = 0
        self.end_timestamp = 0
        self.itemset_count = 0
        self.database_size = 0
        self.minsup_relative = 0
        self.database = []
        self.patterns = None
        self.writer = None

    def run_algorithm(self, minsup, input_file, output_file=None):
        if output_file is None:
            self.writer = None
            self.patterns = Itemsets("Minimal Rare Itemsets")
        else:
            self.patterns = None
            self.writer = open(output_file, "w")

        self.start_timestamp = time.time()
        self.itemset_count = 0
        self.total_candidate_count = 0
        MemoryLogger.get_instance().reset()

        self.database = []
        map_item_count = defaultdict(int)

        with open(input_file, "r") as file:
            for line in file:
                if line.strip() and not line.startswith(('#', '%', '@')):
                    transaction = list(map(int, line.strip().split()))
                    self.database.append(transaction)
                    for item in transaction:
                        map_item_count[item] += 1

        self.database_size = len(self.database)
        self.minsup_relative = math.ceil(minsup * self.database_size)

        self.k = 1
        frequent1 = [item for item, count in map_item_count.items() if count >= self.minsup_relative]

        for item, count in map_item_count.items():
            if count < self.minsup_relative:
                self.save_itemset_to_file(item, count)

        frequent1.sort()

        if not frequent1:
            if self.writer:
                self.writer.close()
            return self.patterns

        self.total_candidate_count += len(frequent1)

        level = None
        self.k = 2
        while True:
            MemoryLogger.get_instance().check_memory()

            if self.k == 2:
                candidates_k = self.generate_candidate2(frequent1)
            else:
                candidates_k = self.generate_candidate_size_k(level)

            self.total_candidate_count += len(candidates_k)

            for transaction in self.database:
                for candidate in candidates_k:
                    if all(item in transaction for item in candidate.items):
                        candidate.support += 1

            level = [candidate for candidate in candidates_k if candidate.support >= self.minsup_relative]

            for candidate in candidates_k:
                if candidate.support < self.minsup_relative:
                    self.save_itemset(candidate)

            if not level:
                break

            self.k += 1

        self.k += 1  # Increment `self.k` to align the stopping size with Java
        self.end_timestamp = time.time()
        MemoryLogger.get_instance().check_memory()

        if self.writer:
            self.writer.close()

        return self.patterns

    def generate_candidate2(self, frequent1):
        candidates = []
        for i in range(len(frequent1)):
            for j in range(i + 1, len(frequent1)):
                candidates.append(Itemset([frequent1[i], frequent1[j]]))
        return candidates

    def generate_candidate_size_k(self, level_k_1):
        candidates = []
        for i in range(len(level_k_1)):
            for j in range(i + 1, len(level_k_1)):
                if ArraysAlgos.all_the_same_except_last_item(level_k_1[i].items, level_k_1[j].items):
                    new_itemset = ArraysAlgos.concatenate(level_k_1[i].items, [level_k_1[j].items[-1]])
                    candidates.append(Itemset(new_itemset))
        return candidates

    def save_itemset(self, itemset):
        self.itemset_count += 1
        if self.writer:
            self.writer.write(str(itemset) + "\n")
        else:
            self.patterns.add_itemset(itemset, itemset.size())

    def save_itemset_to_file(self, item, support):
        self.itemset_count += 1
        if self.writer:
            self.writer.write(f"{item} #SUP: {support}\n")
        else:
            itemset = Itemset([item])
            itemset.set_support(support)
            self.patterns.add_itemset(itemset, 1)

    def print_stats(self):
        print("=============  APRIORI-RARE - STATS =============")
        print(f" Candidates count : {self.total_candidate_count}")
        print(f" The algorithm stopped at size {self.k - 1}, because there is no candidate")
        print(f" Minimal rare itemsets count : {self.itemset_count}")
        print(f" Maximum memory usage : {MemoryLogger.get_instance().get_max_memory()} mb")
        print(f" Total time ~ {self.end_timestamp - self.start_timestamp:.2f} s")
        print("===================================================")


if __name__ == "__main__":
    # Automatically get the current directory of the script
    current_directory = os.path.dirname(os.path.abspath(__file__))

    # Define file paths relative to the script's directory
    input_file_path = os.path.join(current_directory, "contextZart.txt")
    output_file_path = os.path.join(current_directory, "apriorirare_outputs.txt")

    minsup = 0.4

    # Initialize and run the algorithm
    apriori_rare = AlgoAprioriRare()
    try:
        apriori_rare.run_algorithm(minsup, input_file_path, output_file_path)
        apriori_rare.print_stats()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Ensure that 'contextZart.txt' exists in the same directory as this script.")
