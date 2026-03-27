import itertools
import time
import psutil
from collections import defaultdict

class Transaction:
    def __init__(self, items, utilities):
        self.items = items
        self.utilities = utilities
        self.total_utility = sum(utilities)

class MemoryLogger:
    """
    This class is used to record the maximum memory usage of an algorithm during a given execution.
    It is implemented using the "singleton" design pattern.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(MemoryLogger, cls).__new__(cls, *args, **kwargs)
            cls._instance.max_memory = 0
        return cls._instance

    def get_max_memory(self):
        """
        To get the maximum amount of memory used until now.
        
        :return: a float value indicating memory in megabytes
        """
        return self._instance.max_memory

    def reset(self):
        """
        Reset the maximum amount of memory recorded.
        """
        self._instance.max_memory = 0

    def check_memory(self):
        """
        Check the current memory usage and record it if it is higher than the amount of memory previously recorded.
        
        :return: the memory usage in megabytes
        """
        process = psutil.Process()
        current_memory = process.memory_info().rss / 1024 / 1024
        if current_memory > self._instance.max_memory:
            self._instance.max_memory = current_memory
        return current_memory

class HMiner:
    def __init__(self, transactions, min_utility):
        self.transactions = transactions
        self.min_utility = min_utility
        self.high_utility_itemsets = []

    def run(self):
        self.start_time = time.time()
        self.memory_usage = 0
        self.high_utility_itemsets = []

        # Generate itemset utilities
        self.generate_high_utility_itemsets()

        self.end_time = time.time()
        self.total_time = (self.end_time - self.start_time) * 1000  # convert to ms
        self.memory_usage = MemoryLogger().check_memory()  # assuming static memory usage for illustration
        self.output_results()

    def generate_high_utility_itemsets(self):
        item_utility_map = defaultdict(int)

        # First pass: calculate the TWU (Transaction Weighted Utility) for each item
        for transaction in self.transactions:
            for item in transaction.items:
                item_utility_map[item] += transaction.total_utility

        # Filter out items with low TWU
        high_twu_items = {item for item in item_utility_map if item_utility_map[item] >= self.min_utility}

        if not high_twu_items:
            return

        # Generate candidates and count their utilities
        candidate_utility_map = defaultdict(int)
        for transaction in self.transactions:
            filtered_items = [item for item in transaction.items if item in high_twu_items]
            for length in range(1, len(filtered_items) + 1):
                for itemset in itertools.combinations(filtered_items, length):
                    utility = sum(transaction.utilities[transaction.items.index(item)] for item in itemset)
                    candidate_utility_map[itemset] += utility

        # Filter out low utility itemsets
        for itemset, utility in candidate_utility_map.items():
            if utility >= self.min_utility:
                self.high_utility_itemsets.append((itemset, utility))

    def output_results(self):
        print("=============  HMINER ALGORITHM v.2.34 - STATS =============")
        print(f" Total time ~ {self.total_time:.2f} ms")
        print(f" Max Memory ~ {self.memory_usage:.2f} MB")
        print(f" High-utility itemsets count : {len(self.high_utility_itemsets)}")
        print("================================================")

        with open("output.txt", "w") as file:
            for itemset, utility in self.high_utility_itemsets:
                file.write(f"{' '.join(map(str, itemset))} #UTIL: {utility}\n")

def parse_input(data):
    transactions = []
    with open(data, "r") as file:
        lines = file.readlines()
        for line in lines:
            parts = line.strip().split(":")
            items = list(map(int, parts[0].split()))
            transaction_utility = int(parts[1])
            utilities = list(map(int, parts[2].split()))
            transactions.append(Transaction(items, utilities))
    return transactions

data = "DB_Utility.txt"

transactions = parse_input(data)
min_utility = 30  # Define a minimum utility threshold
hminer = HMiner(transactions, min_utility)
hminer.run()




