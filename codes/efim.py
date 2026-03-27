import itertools
import time
import psutil

class Transaction:
    def __init__(self, items, utilities):
        self.items = items
        self.utilities = utilities

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

class EFIM:
    def __init__(self, transactions, min_utility):
        self.transactions = transactions
        self.min_utility = min_utility
        self.high_utility_itemsets = []

    def run(self):
        self.start_time = time.time()
        self.transaction_count = len(self.transactions)
        self.partition_count = len(set([len(t.items) for t in self.transactions]))
        self.partition_size = max([len(t.items) for t in self.transactions])

        memory_logger = MemoryLogger()
        memory_logger.reset()

        # Flatten transactions to a single list of items with their utilities
        item_utility_dict = {}
        for transaction in self.transactions:
            for item, utility in zip(transaction.items, transaction.utilities):
                if item in item_utility_dict:
                    item_utility_dict[item] += utility
                else:
                    item_utility_dict[item] = utility

        memory_logger.check_memory()

        # Calculate utility for individual items
        for item, utility in item_utility_dict.items():
            if utility >= self.min_utility:
                self.high_utility_itemsets.append(([item], utility))

        memory_logger.check_memory()

        # Calculate utility for all itemsets
        items = list(item_utility_dict.keys())
        for i in range(2, len(items) + 1):
            for itemset in itertools.combinations(items, i):
                utility = self.calculate_utility(itemset)
                if utility >= self.min_utility:
                    self.high_utility_itemsets.append((itemset, utility))

        memory_logger.check_memory()

        self.total_time = (time.time() - self.start_time) * 1000  # in milliseconds

    def calculate_utility(self, itemset):
        utility = 0
        for transaction in self.transactions:
            if set(itemset).issubset(set(transaction.items)):
                indices = [transaction.items.index(item) for item in itemset]
                utility += sum([transaction.utilities[idx] for idx in indices])
        return utility

    def print_stats(self):
        print("=============  HUP-MINER ALGORITHM v0.96r18 - STATS =============")
        print(f" Transaction count: {self.transaction_count} Partition count: {self.partition_count}")
        print(f" Partition size: {self.partition_size}")
        print(f" Join count: {len(self.high_utility_itemsets)} Partial join count:{len(self.high_utility_itemsets)}")
        print(f" Total time: {self.total_time} ms")
        print(f" Memory ~ {MemoryLogger().get_max_memory():.2f} MB")
        print(f" High-utility itemsets count: {len(self.high_utility_itemsets)}")
        print("===================================================")

    def write_output(self, filename="output.txt"):
        with open(filename, "w") as f:
            for itemset, utility in self.high_utility_itemsets:
                f.write(f"{' '.join(map(str, itemset))} #UTIL: {utility}\n")

def read_transactions_from_file(file_path):
    transactions = []
    with open(file_path, 'r') as file:
        lines = file.readlines()
        for line in lines:
            parts = line.strip().split(':')
            items = list(map(int, parts[0].split()))
            utilities = list(map(int, parts[2].split()))
            transactions.append(Transaction(items, utilities))
    return transactions

if __name__ == "__main__":
    transactions = read_transactions_from_file("DB_Utility.txt")

    min_utility = 30
    efim = EFIM(transactions, min_utility)
    efim.run()
    efim.print_stats()
    efim.write_output()
