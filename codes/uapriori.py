from decimal import Decimal, ROUND_HALF_UP
import time


# Define ItemUApriori class
class ItemUApriori:
    def __init__(self, item_id, probability=None):
        self.id = item_id
        self.probability = probability

    def get_id(self):
        return self.id

    def get_probability(self):
        return self.probability

    def __eq__(self, other):
        if isinstance(other, ItemUApriori):
            return self.id == other.id
        return False

    def __hash__(self):
        return hash(self.id)

    def __str__(self):
        return f"{self.id} ({self.probability})"


# Define ItemsetUApriori class
class ItemsetUApriori:
    def __init__(self):
        self.items = []
        self.expected_support = 0.0

    def get_expected_support(self):
        return self.expected_support

    def increase_support_by(self, supp):
        self.expected_support += supp

    def add_item(self, item):
        self.items.append(item)

    def get_items(self):
        return self.items

    def __str__(self):
        return ' '.join(str(item) for item in self.items)

    def is_equal_to(self, other):
        return sorted(self.items, key=lambda x: x.get_id()) == sorted(
            other.get_items(), key=lambda x: x.get_id()
        )


# Define UncertainTransactionDatabase class
class UncertainTransactionDatabase:
    def __init__(self):
        self.all_items = set()
        self.transactions = []

    def load_file(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as file:
                for line in file:
                    line = line.strip()
                    if not line or line[0] in ('#', '%', '@'):
                        continue
                    self.process_transaction(line.split())
        except Exception as e:
            print(f"Error loading file: {e}")

    def process_transaction(self, items):
        transaction = ItemsetUApriori()
        for item_string in items:
            left_paren = item_string.index('(')
            right_paren = item_string.index(')')
            item_id = int(item_string[:left_paren])
            probability = float(item_string[left_paren + 1:right_paren])
            item = ItemUApriori(item_id, probability)
            transaction.add_item(item)
            self.all_items.add(item)
        self.transactions.append(transaction)

    def print_database(self):
        print("===================  UNCERTAIN DATABASE ===================")
        for idx, transaction in enumerate(self.transactions):
            print(f"{idx:02}:  {transaction}")

    def size(self):
        return len(self.transactions)

    def get_transactions(self):
        return self.transactions

    def get_all_items(self):
        return self.all_items


# Define AlgoUApriori class
class AlgoUApriori:
    def __init__(self, database):
        self.database = database
        self.k = 0
        self.total_candidate_count = 0
        self.database_scan_count = 0
        self.start_timestamp = None
        self.end_timestamp = None
        self.itemset_count = 0

    def run_algorithm(self, minsupp):
        self.start_timestamp = time.time()
        self.k = 1
        candidates = self.generate_candidate_size1()
        self.total_candidate_count += len(candidates)
        self.calculate_support_for_each_candidate(candidates)
        level = self.filter_candidates(candidates, minsupp)

        while True:
            self.k += 1
            candidates = self.generate_candidate_size_k(level)
            if not candidates:  # If no candidates generated, perform a final scan
                self.database_scan_count += 1  # Final empty scan
                break
            self.total_candidate_count += len(candidates)
            self.calculate_support_for_each_candidate(candidates)
            level = self.filter_candidates(candidates, minsupp)

        self.end_timestamp = time.time()
        self.print_stats()

    def generate_candidate_size1(self):
        candidates = []
        for item in self.database.get_all_items():
            itemset = ItemsetUApriori()
            itemset.add_item(item)
            candidates.append(itemset)
        return candidates

    def generate_candidate_size_k(self, prev_level):
        candidates = []
        prev_itemsets = list(prev_level)
        for i in range(len(prev_itemsets)):
            for j in range(i + 1, len(prev_itemsets)):
                itemset1 = prev_itemsets[i].get_items()
                itemset2 = prev_itemsets[j].get_items()

                if itemset1[:-1] == itemset2[:-1]:
                    candidate = ItemsetUApriori()
                    for item in itemset1:
                        candidate.add_item(item)
                    candidate.add_item(itemset2[-1])

                    if self.all_subsets_of_size_k_minus_1_are_frequent(candidate, prev_level):
                        candidates.append(candidate)
        return candidates

    def all_subsets_of_size_k_minus_1_are_frequent(self, candidate, prev_level):
        candidate_items = candidate.get_items()
        for i in range(len(candidate_items)):
            subset = ItemsetUApriori()
            for j, item in enumerate(candidate_items):
                if i != j:
                    subset.add_item(item)

            if not any(subset.is_equal_to(itemset) for itemset in prev_level):
                return False
        return True

    def calculate_support_for_each_candidate(self, candidates):
        self.database_scan_count += 1
        for transaction in self.database.get_transactions():
            for candidate in candidates:
                expected_support = 1.0
                for item in candidate.get_items():
                    found = False
                    for transaction_item in transaction.get_items():
                        if item.get_id() == transaction_item.get_id():
                            expected_support *= transaction_item.get_probability()
                            found = True
                            break
                    if not found:
                        expected_support = 0
                        break
                candidate.increase_support_by(expected_support)

    def filter_candidates(self, candidates, minsupp):
        frequent = []
        for candidate in candidates:
            if candidate.get_expected_support() >= minsupp:
                frequent.append(candidate)
                self.itemset_count += 1
        return frequent

    def print_stats(self):
        print("=============  U-APRIORI - STATS =============")
        print(f" Transactions count from database : {self.database.size()}")
        print(f" Candidates count : {self.total_candidate_count}")
        print(f" Database scan count : {self.database_scan_count}")
        print(f" The algorithm stopped at size {self.k}, because there is no candidate")
        print(f" Uncertain itemsets count : {self.itemset_count}")
        print(f" Total time ~ {int((self.end_timestamp - self.start_timestamp) * 1000)} ms")
        print("===================================================")

if __name__ == "__main__":
    context = UncertainTransactionDatabase()
    try:
        context.load_file("contextUncertain.txt")
    except Exception as e:
        print(f"Error loading database: {e}")

    context.print_database()

    algo = AlgoUApriori(context)
    algo.run_algorithm(minsupp=0.1)

