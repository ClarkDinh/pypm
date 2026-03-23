import time
from collections import defaultdict
from math import ceil

def read_transactions(file_path):
    transactions = []
    with open(file_path, 'r') as file:
        for line in file:
            transaction = sorted(set(map(int, line.strip().split())))  # Convert each line into a sorted list of unique items
            transactions.append(transaction)
    return transactions

def get_item_support(transactions):
    item_supports = defaultdict(list)
    for transaction in transactions:
        seen_items = set()
        for item in transaction:
            if item not in seen_items:
                item_supports[item].append(transaction)
                seen_items.add(item)
    return item_supports

def hmine(prefix, item_supports, min_support):
    frequent_itemsets = []
    # Filter items based on the minimum support threshold
    valid_items = {item: supports for item, supports in item_supports.items() if len(supports) >= min_support}

    for item, supports in sorted(valid_items.items(), key=lambda x: x[0]):  # Process in sorted item order
        current_itemset = prefix + [item]
        current_support = len(supports)
        frequent_itemsets.append((current_itemset, current_support))
        
        # Project transactions to items greater than 'item'
        projected_transactions = [list(filter(lambda x: x > item, t)) for t in supports]
        if projected_transactions:
            projected_item_supports = get_item_support(projected_transactions)
            frequent_itemsets.extend(hmine(current_itemset, projected_item_supports, min_support))

    return frequent_itemsets

def main():
    start_time = time.time()
    transactions = read_transactions('contextPasquier99.txt')
    total_transactions = len(transactions)
    min_support = ceil(total_transactions * 0.4)  # Use ceil to round up minimum support calculation

    item_supports = get_item_support(transactions)
    frequent_itemsets = hmine([], item_supports, min_support)

    print(f"Total transactions: {total_transactions}, Minimum support: {min_support}")
    print("============= HMine ALGORITHM STATS =============")
    print(f"Total time ~ {int((time.time() - start_time) * 1000)} ms")
    print(f"Frequent itemsets count : {len(frequent_itemsets)}")
    for itemset, support in sorted(frequent_itemsets):
        print(f"{' '.join(map(str, itemset))} #SUP: {support}")
    print("===================================================")

if __name__ == '__main__':
    main()
