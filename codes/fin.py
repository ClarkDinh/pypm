import time
import tracemalloc
from collections import defaultdict

class Node:
    def __init__(self, item, support):
        self.item = item
        self.support = support
        self.children = []

    def add_child(self, child_node):
        self.children.append(child_node)

class Nodeset:
    def __init__(self):
        self.nodes = []

    def add_node(self, node):
        self.nodes.append(node)

    def get_support(self):
        return sum(node.support for node in self.nodes)

class FIN:
    def __init__(self, transactions, minsup):
        self.transactions = transactions
        self.minsup = minsup
        self.frequent_itemsets = []
        self.num_transactions = len(transactions)

    def run(self):
        item_counts = self.count_single_items()
        root_nodes = self.create_initial_nodes(item_counts)
        self.mine_nodes(root_nodes, [])

    def count_single_items(self):
        item_counts = defaultdict(int)
        for transaction in self.transactions:
            for item in transaction:
                item_counts[item] += 1
        return item_counts

    def create_initial_nodes(self, item_counts):
        nodes = []
        for item, count in item_counts.items():
            if count / self.num_transactions >= self.minsup:
                nodes.append(Node(item, count))
        return nodes

    def mine_nodes(self, nodes, prefix):
        for node in nodes:
            new_prefix = prefix + [node.item]
            support = self.calculate_support(new_prefix)
            if support / self.num_transactions >= self.minsup:
                self.frequent_itemsets.append((new_prefix, support))
            new_nodes = self.extend_nodes(node, nodes)
            self.mine_nodes(new_nodes, new_prefix)

    def extend_nodes(self, current_node, nodes):
        new_nodes = []
        for node in nodes:
            if node.item > current_node.item:
                new_node = Node(node.item, current_node.support)  # Extend logic as per FIN specifics
                new_nodes.append(new_node)
        return new_nodes

    def calculate_support(self, itemset):
        support = 0
        for transaction in self.transactions:
            if all(item in transaction for item in itemset):
                support += 1
        return support

def load_data(file_path):
    with open(file_path, 'r') as file:
        transactions = []
        for line in file:
            transaction = list(map(int, line.split()))
            transactions.append(transaction)
    return transactions

# Parameters
minsup = 0.4
transactions = load_data('contextPasquier99.txt')

# Start tracking time and memory usage
start_time = time.time()
tracemalloc.start()

# Run FIN algorithm
fin = FIN(transactions, minsup)
fin.run()

# Stop tracking time and memory usage
end_time = time.time()
current, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()

# Output results
for itemset, support in fin.frequent_itemsets:
    print(f"{' '.join(map(str, itemset))} #SUP: {support}")

# Print statistics
print("\n========== FIN - STATS ============")
print(f" Minsup = {minsup * len(transactions)}")
print(f" Number of transactions: {len(transactions)}")
print(f" Number of frequent itemsets: {len(fin.frequent_itemsets)}")
print(f" Total time ~: {int((end_time - start_time) * 1000)} ms")
print(f" Max memory: {peak / 1024 / 1024} MB")
print("=====================================")
