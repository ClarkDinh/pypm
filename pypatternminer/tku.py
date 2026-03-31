import itertools
import heapq
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

INPUT_FILE = os.path.join(BASE_DIR, "DB_Utility.txt")
OUTPUT_FILE = os.path.join(BASE_DIR, "outputs.txt")

K = 6


# ==========================================
# LOAD DATABASE + COMPUTE TWU
# ==========================================

def load_database(filepath):
    database = []
    twu = {}
    all_items = set()

    with open(filepath, 'r') as f:
        for line in f:
            parts = line.strip().split(":")
            items = list(map(int, parts[0].split()))
            transaction_utility = int(parts[1])
            item_utils = list(map(int, parts[2].split()))

            transaction = dict(zip(items, item_utils))
            database.append(transaction)

            for item in items:
                all_items.add(item)
                twu[item] = twu.get(item, 0) + transaction_utility

    return database, sorted(all_items), twu


# ==========================================
# UTILITY CALCULATION
# ==========================================

def compute_utility(itemset, database):
    total = 0
    for transaction in database:
        if all(item in transaction for item in itemset):
            total += sum(transaction[item] for item in itemset)
    return total


# ==========================================
# REORDER LIKE JAVA (TWU ASCENDING)
# ==========================================

def reorder_like_java(itemset, twu):
    return sorted(itemset, key=lambda x: (twu[x], x))


# ==========================================
# TKU TOP-K MINER
# ==========================================

def run_tku(input_file, output_file, k):

    database, items, twu = load_database(input_file)

    heap = []

    for r in range(1, len(items) + 1):
        for combo in itertools.combinations(items, r):

            utility = compute_utility(combo, database)

            if len(heap) < k:
                heapq.heappush(heap, (utility, combo))
            else:
                if utility > heap[0][0]:
                    heapq.heappushpop(heap, (utility, combo))

    topk = list(heap)

    def reorder_like_java(itemset):
        return sorted(itemset, key=lambda x: (twu[x], x))

    with open(output_file, 'w') as f:
        for utility, itemset in topk:

            java_order = reorder_like_java(itemset)
            items_str = " ".join(map(str, java_order))
            f.write(f"{items_str} #UTIL: {utility}\n")

    print(f"Top-{k} HUIs written to {output_file}")
# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":
    run_tku(INPUT_FILE, OUTPUT_FILE, K)