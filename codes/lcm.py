import time
import psutil
from collections import deque, defaultdict

class Itemset:
    def __init__(self, items, support):
        self.items = sorted(items)  # Ensure the items are sorted
        self.support = support

class Itemsets:
    def __init__(self, name):
        self.name = name
        self.levels = defaultdict(list)

    def add_itemset(self, itemset):
        self.levels[len(itemset.items)].append(itemset)

    def get_count(self):
        return sum(len(itemsets) for itemsets in self.levels.values())

    def print_itemsets(self):
        print(f"---------- {self.name} ----------")
        max_length = max(self.levels.keys(), default=0)
        # Ensure L0 is printed even if there are no itemsets with length 0
        if 0 not in self.levels:
            print("  L0")
        for length in range(max_length + 1):
            if length in self.levels:
                print(f"  L{length}")
                for i, itemset in enumerate(self.levels[length]):
                    print(f"  pattern {i}: {', '.join(map(str, itemset.items))} support: {itemset.support}")
        print("---------------------------------")

class Dataset:
    def __init__(self, transactions):
        self.transactions = transactions

    def size(self):
        return len(self.transactions)

    def num_items(self):
        all_items = set()
        for transaction in self.transactions:
            all_items.update(transaction)
        return max(all_items) + 1

    def project_database(self, itemset):
        projected_transactions = []
        for transaction in self.transactions:
            if all(item in transaction for item in itemset):
                projected_transactions.append(transaction)
        return Dataset(projected_transactions)

    def get_support(self, itemset):
        count = 0
        for transaction in self.transactions:
            if all(item in transaction for item in itemset):
                count += 1
        return count

class AlgoLCM:
    def __init__(self, minsup, dataset):
        self.minsup = minsup
        self.dataset = dataset
        self.frequent_itemsets = Itemsets("FREQUENT ITEMSETS")
        self.closed_itemsets = {}

    def run_algorithm(self):
        start_time = time.time()
        memory_logger = MemoryLogger()
        memory_logger.start()

        stack = deque([([], self.dataset)])

        while stack:
            itemset, current_dataset = stack.pop()
            if len(itemset) > 0:
                support = current_dataset.get_support(itemset)
                if support >= self.minsup and self.is_closed(itemset, support, current_dataset):
                    itemset_obj = Itemset(itemset, support)
                    self.frequent_itemsets.add_itemset(itemset_obj)
                    self.closed_itemsets[tuple(sorted(itemset))] = support

            for item in range(self.dataset.num_items()):
                if item not in itemset and (len(itemset) == 0 or item > itemset[-1]):
                    new_itemset = itemset + [item]
                    if tuple(sorted(new_itemset)) not in self.closed_itemsets:
                        new_dataset = current_dataset.project_database(new_itemset)
                        if new_dataset.size() >= self.minsup:
                            stack.append((new_itemset, new_dataset))

        end_time = time.time()
        memory_logger.stop()

        print("========== LCM - STATS ===========")
        print(f" Freq. closed itemsets count: {self.frequent_itemsets.get_count()}")
        print(f" Total time ~: {int((end_time - start_time) * 1000)} ms")
        print(f" Max memory: {memory_logger.max_memory} MB")
        print("=================================")
        self.frequent_itemsets.print_itemsets()

    def is_closed(self, itemset, support, dataset):
        for transaction in dataset.transactions:
            if all(item in transaction for item in itemset):
                for item in range(dataset.num_items()):
                    if item not in itemset and all(i in transaction for i in itemset + [item]):
                        extended_itemset = itemset + [item]
                        if dataset.get_support(extended_itemset) == support:
                            return False
        return True

class MemoryLogger:
    def __init__(self):
        self.process = psutil.Process()
        self.max_memory = 0

    def start(self):
        self.max_memory = self.process.memory_info().rss / (1024 * 1024)

    def stop(self):
        current_memory = self.process.memory_info().rss / (1024 * 1024)
        if current_memory > self.max_memory:
            self.max_memory = current_memory

def read_transactions(file_path):
    transactions = []
    with open(file_path, 'r') as file:
        for line in file:
            transaction = list(map(int, line.strip().split()))
            transactions.append(transaction)
    return transactions

if __name__ == "__main__":
    file_path = "contextPasquier99.txt"
    transactions = read_transactions(file_path)
    dataset = Dataset(transactions)
    minsup = 0.4 * len(transactions)
    
    algo = AlgoLCM(minsup, dataset)
    algo.run_algorithm()
