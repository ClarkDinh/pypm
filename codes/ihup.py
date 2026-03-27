import time
import psutil
from itertools import combinations

def load_transactions(filename):
    transactions = []
    with open(filename, "r") as file:
        for line in file:
            parts = line.strip().split(":")
            items = list(map(int, parts[0].split()))
            total_util = int(parts[1])
            utilities = list(map(int, parts[2].split()))
            transactions.append((items, total_util, utilities))
    return transactions


def calculate_utility(itemset, transaction, utility):
    return sum(utility[transaction.index(item)] for item in itemset if item in transaction)

def find_candidates(transactions):
    items = set(item for transaction, _, _ in transactions for item in transaction)
    candidates = []
    for i in range(1, len(items) + 1):
        for combination in combinations(items, i):
            candidates.append(combination)
    return candidates

def find_huis(transactions, candidates, min_util):
    huis = []
    for candidate in candidates:
        total_utility = 0
        for transaction, trans_utility, utility in transactions:
            if set(candidate).issubset(set(transaction)):
                total_utility += calculate_utility(candidate, transaction, utility)
        if total_utility >= min_util:
            huis.append((candidate, total_utility))
    return huis

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

def ihup_algorithm(transactions, min_util):
    memory_logger = MemoryLogger()
    memory_logger.reset()

    start_time = time.time()

    candidates = find_candidates(transactions)
    
    huis = find_huis(transactions, candidates, min_util)

    # Check and log memory usage
    MemoryLogger().check_memory()

    end_time = time.time()

    print("=============  IHUP ALGORITHM - STATS =============")
    print(f" PHUIs (candidates) count: {len(candidates)}")
    print(f" Total time ~ {int((end_time - start_time)* 1000)} ms")
    print(f" Memory ~ {memory_logger.get_max_memory():.2f} MB")
    print(f" HUIs count : {len(huis)}")
    print("===================================================")

    with open("output.txt", "w") as file:
        for itemset, util in huis:
            file.write(f"{' '.join(map(str, itemset))} #UTIL: {util}\n")

transactions = load_transactions("DB_Utility.txt")

min_util = 30

ihup_algorithm(transactions, min_util)

