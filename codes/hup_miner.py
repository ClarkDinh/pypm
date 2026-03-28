import itertools
import psutil
import time
from collections import defaultdict

class Transaction:
    def __init__(self, items, utilities, total_utility):
        self.items = items
        self.utilities = utilities
        self.total_utility = total_utility

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

def parse_data(file_path):
    transactions = []
    with open(file_path, 'r') as file:
        for line in file:
            parts = line.strip().split(':')
            items = list(map(int, parts[0].split()))
            total_utility = int(parts[1])
            utilities = list(map(int, parts[2].split()))
            transactions.append(Transaction(items, utilities, total_utility))
    return transactions

def generate_candidates(items, length):
    return list(itertools.combinations(items, length))

def calculate_utility(transactions, candidate):
    total_utility = 0
    for transaction in transactions:
        utility = 0
        if all(item in transaction.items for item in candidate):
            for item in candidate:
                index = transaction.items.index(item)
                utility += transaction.utilities[index]
        total_utility += utility
    return total_utility

def hup_miner(transactions, min_utility):
    items = sorted(set(item for transaction in transactions for item in transaction.items))
    high_utility_itemsets = []

    # Generate all possible candidate itemsets and calculate their utilities
    for length in range(1, len(items) + 1):
        candidate_itemsets = generate_candidates(items, length)
        for candidate in candidate_itemsets:
            total_utility = calculate_utility(transactions, candidate)
            if total_utility >= min_utility:
                high_utility_itemsets.append((candidate, total_utility))

            # Check and log memory usage
            MemoryLogger().check_memory()

    return high_utility_itemsets

def main():
    file_path = 'DB_Utility.txt'
    transactions = parse_data(file_path)
    min_utility = 30  # Set to the appropriate minimum utility

    memory_logger = MemoryLogger()
    memory_logger.reset()
    
    start_time = time.time()
    high_utility_itemsets = hup_miner(transactions, min_utility)
    end_time = time.time()
    
    print("=============  HUP-MINER ALGORITHM v0.96r18 - STATS =============")
    print(f" Total time: {int((end_time - start_time) * 1000)} ms")
    print(f" Memory ~ {memory_logger.get_max_memory():.2f} MB")
    print(f" High-utility itemsets count: {len(high_utility_itemsets)}")
    print("===================================================")
    
    with open('output.txt', 'w') as f:
        for itemset, utility in high_utility_itemsets:
            itemset_str = ' '.join(map(str, itemset))
            f.write(f"{itemset_str} #UTIL: {utility}\n")
            print(f"{itemset_str} #UTIL: {utility}")

if __name__ == "__main__":
    main()




