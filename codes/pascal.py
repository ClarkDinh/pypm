import os
import time
import math
from abc import ABC, abstractmethod
from collections import defaultdict
import psutil

# Memory Logger
class MemoryLogger:
    _instance = None

    def __init__(self):
        self.max_memory = 0.0  # Store max memory in MB

    @staticmethod
    def get_instance():
        if MemoryLogger._instance is None:
            MemoryLogger._instance = MemoryLogger()
        return MemoryLogger._instance

    def get_max_memory(self) -> float:
        return self.max_memory

    def reset(self):
        self.max_memory = 0.0

    def check_memory(self) -> float:
        current_memory = psutil.Process().memory_info().rss / 1024 / 1024  # Convert bytes to MB
        if current_memory > self.max_memory:
            self.max_memory = current_memory
        return current_memory

# Abstract Itemset Classes
class AbstractItemset(ABC):
    def __init__(self):
        super().__init__()

    @abstractmethod
    def size(self) -> int:
        pass

    @abstractmethod
    def get_absolute_support(self) -> int:
        pass

    @abstractmethod
    def contains(self, item: int) -> bool:
        pass

    def print(self):
        print(str(self))

class AbstractOrderedItemset(AbstractItemset):
    def get_last_item(self) -> int:
        return self.get(self.size() - 1)

    def get_relative_support(self, nb_object: int) -> float:
        return self.get_absolute_support() / nb_object

    def contains_all(self, itemset2: 'AbstractOrderedItemset') -> bool:
        if self.size() < itemset2.size():
            return False
        i = 0
        for j in range(itemset2.size()):
            found = False
            while not found and i < self.size():
                if self.get(i) == itemset2.get(j):
                    found = True
                elif self.get(i) > itemset2.get(j):
                    return False
                i += 1
            if not found:
                return False
        return True

    def is_equal_to(self, itemset2: 'AbstractOrderedItemset') -> bool:
        if self.size() != itemset2.size():
            return False
        return all(self.get(i) == itemset2.get(i) for i in range(self.size()))

    def __str__(self) -> str:
        return " ".join(str(self.get(i)) for i in range(self.size()))

# ItemsetPascal Class
class ItemsetPascal(AbstractOrderedItemset):
    def __init__(self, itemset):
        self.itemset = itemset
        self.support = 0
        self.isGenerator = True
        self.pred_sup = float('inf')

    def get_absolute_support(self) -> int:
        return self.support

    def size(self) -> int:
        return len(self.itemset)

    def get(self, index: int) -> int:
        return self.itemset[index]

    def contains(self, item: int) -> bool:
        return item in self.itemset

    def set_absolute_support(self, support: int):
        self.support = support

# ArraysAlgos Utility Class
class ArraysAlgos:
    @staticmethod
    def same_as(itemset1, itemset2, pos_removed) -> int:
        j = 0
        for i in range(len(itemset1)):
            if j == pos_removed:
                j += 1
            if itemset1[i] < itemset2[j]:
                return -1
            elif itemset1[i] > itemset2[j]:
                return 1
            j += 1
        return 0

# ItemsetHashTree Class
class ItemsetHashTree:
    def __init__(self, itemset_size: int, branch_count: int = 30):
        self.itemset_size = itemset_size
        self.branch_count = branch_count
        self.candidate_count = 0
        self.root = InnerNode(branch_count)
        self.last_inserted_node = None

    def insert_candidate_itemset(self, itemset):
        self.candidate_count += 1
        self._insert_candidate_itemset(self.root, itemset, 0)

    def _insert_candidate_itemset(self, node, itemset, level):
        branch_index = itemset.itemset[level] % self.branch_count
        if isinstance(node, LeafNode):
            if node.candidates[branch_index] is None:
                node.candidates[branch_index] = []
            node.candidates[branch_index].append(itemset)
        else:
            if node.childs[branch_index] is None:
                next_node = LeafNode(self.branch_count) if level == self.itemset_size - 2 else InnerNode(self.branch_count)
                if isinstance(next_node, LeafNode):
                    next_node.next_leaf_node = self.last_inserted_node
                    self.last_inserted_node = next_node
                node.childs[branch_index] = next_node
            self._insert_candidate_itemset(node.childs[branch_index], itemset, level + 1)

class Node:
    pass

class InnerNode(Node):
    def __init__(self, branch_count: int):
        self.childs = [None] * branch_count

class LeafNode(Node):
    def __init__(self, branch_count: int):
        self.candidates = [None] * branch_count
        self.next_leaf_node = None

class AlgoPASCAL:
    def __init__(self):
        self.k = 0
        self.total_candidate_count = 0
        self.start_timestamp = None
        self.end_timestamp = None
        self.itemset_count = 0
        self.minsup_relative = 0
        self.database = []
        self.max_itemset_size = float('inf')
        self.writer = None

    def run_algorithm(self, minsup, input_file, output_file):
        self.start_timestamp = time.time()
        self.writer = open(output_file, "w")
        
        self.itemset_count = 0
        self.total_candidate_count = 0
        MemoryLogger.get_instance().reset()
        transaction_count = 0

        # Step 1: Load database and count item support
        map_item_count = defaultdict(int)
        with open(input_file, "r") as reader:
            for line in reader:
                transaction = [int(item) for item in line.strip().split()]
                for item in transaction:
                    map_item_count[item] += 1
                self.database.append(transaction)
                transaction_count += 1

        # Step 2: Calculate minimum support
        self.minsup_relative = math.ceil(minsup * transaction_count)
        self.k = 1

        # Step 3: Find all frequent items of size 1
        frequent1 = []
        for item, support in map_item_count.items():
            if support >= self.minsup_relative and self.max_itemset_size >= 1:
                itemset = ItemsetPascal([item])
                itemset.isGenerator = (support != transaction_count)
                itemset.pred_sup = transaction_count
                itemset.set_absolute_support(support)
                frequent1.append(itemset)
                self.save_itemset_to_file(itemset)

        self.total_candidate_count += len(frequent1)
        frequent1.sort(key=lambda x: x.get(0))

        if frequent1 and self.max_itemset_size > 1:
            level = None
            self.k = 2
            while level or self.k == 2:
                MemoryLogger.get_instance().check_memory()
                candidates_k = self.generate_candidate2(frequent1) if self.k == 2 else self.generate_candidate_size_k(level)
                self.total_candidate_count += len(candidates_k)

                for candidate in candidates_k:
                    if not candidate.isGenerator:
                        continue
                    for transaction in self.database:
                        if len(transaction) < self.k:
                            continue
                        pos = 0
                        for item in transaction:
                            if item == candidate.itemset[pos]:
                                pos += 1
                                if pos == len(candidate.itemset):
                                    candidate.support += 1
                                    break
                            elif item > candidate.itemset[pos]:
                                break

                level = [candidate for candidate in candidates_k if candidate.get_absolute_support() >= self.minsup_relative]
                for candidate in level:
                    if candidate.get_absolute_support() == candidate.pred_sup:
                        candidate.isGenerator = False
                    self.save_itemset_to_file(candidate)
                
                self.k += 1
                if not level or self.k > self.max_itemset_size:
                    break
        
        self.end_timestamp = time.time()
        MemoryLogger.get_instance().check_memory()
        if self.writer:
            self.writer.close()

    def generate_candidate2(self, frequent1):
        candidates = []
        for i, itemset1 in enumerate(frequent1):
            for j in range(i + 1, len(frequent1)):
                itemset2 = frequent1[j]
                candidate = ItemsetPascal([itemset1.get(0), itemset2.get(0)])
                candidate.isGenerator = itemset1.isGenerator and itemset2.isGenerator
                candidate.pred_sup = min(itemset1.get_absolute_support(), itemset2.get_absolute_support())
                if not candidate.isGenerator:
                    candidate.support = candidate.pred_sup
                candidates.append(candidate)
        return candidates

    def generate_candidate_size_k(self, level_k_1):
        candidates = []
        for i, itemset1 in enumerate(level_k_1):
            for j in range(i + 1, len(level_k_1)):
                itemset2 = level_k_1[j]
                # Check if they have the same prefix, except the last item
                if itemset1.itemset[:-1] == itemset2.itemset[:-1] and itemset1.get(-1) < itemset2.get(-1):
                    new_itemset = itemset1.itemset + [itemset2.get(-1)]
                    new_itemset_pascal = ItemsetPascal(new_itemset)
                    if self.all_subsets_of_size_k_1_are_frequent(new_itemset_pascal, level_k_1):
                        candidates.append(new_itemset_pascal)
        return candidates

    def all_subsets_of_size_k_1_are_frequent(self, candidate_itemset, level_k_1):
        candidate = candidate_itemset.itemset
        for pos_removed in range(len(candidate)):
            subset = candidate[:pos_removed] + candidate[pos_removed+1:]
            found = any(level_k_1_item.itemset == subset for level_k_1_item in level_k_1)
            if not found:
                return False
        return True

    def save_itemset_to_file(self, itemset):
        self.writer.write(f"{itemset} #SUP: {itemset.get_absolute_support()} #IS_GENERATOR {itemset.isGenerator}\n")
        self.itemset_count += 1

    def print_stats(self):
        print("=============  PASCAL - STATS =============")
        print(f" Candidates count : {self.total_candidate_count}")
        print(f" The algorithm stopped at size {self.k - 1}, because there is no candidate")
        print(f" Frequent itemsets count : {self.itemset_count}")
        print(f" Maximum memory usage : {MemoryLogger.get_instance().get_max_memory()} mb")
        print(f" Total time ~ {round((self.end_timestamp - self.start_timestamp) * 1000)} ms")
        print("===========================================")


# Main Test Class
class MainTestPascal:
    @staticmethod
    def main():
        input_file = MainTestPascal.file_to_path("contextZart.txt")
        output_file = "pascal_outputs.txt"
        minsup = 0.5
        algorithm = AlgoPASCAL()
        algorithm.run_algorithm(minsup, input_file, output_file)
        algorithm.print_stats()

    @staticmethod
    def file_to_path(filename):
        return os.path.join(os.path.dirname(__file__), filename)

if __name__ == "__main__":
    MainTestPascal.main()
