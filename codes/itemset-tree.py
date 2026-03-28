# itemsettree.py

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


# ----------------------------------------------------------------------
# Utilities (Java-like fileToPath behavior)
# ----------------------------------------------------------------------

def file_to_path(filename: str) -> str:
    """
    Java used getResource() from the classpath. Here we try:
    1) next to this .py file
    2) Java/src/itemsettree/<filename>
    """
    here = Path(__file__).resolve().parent

    p1 = here / filename
    if p1.exists():
        return str(p1)

    p2 = Path("Java") / "src" / "itemsettree" / filename
    if p2.exists():
        return str(p2.resolve())

    raise FileNotFoundError(
        f"Could not locate {filename}. Tried:\n"
        f"- {p1}\n"
        f"- {p2.resolve()}"
    )


def read_transactions(file_path: str) -> List[List[int]]:
    transactions: List[List[int]] = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            t = [int(x) for x in parts]
            transactions.append(t)
    return transactions


# ----------------------------------------------------------------------
# Core classes (matching your Java embedded classes)
# ----------------------------------------------------------------------

@dataclass
class Itemset:
    items: List[int]
    support: int = 1

    @classmethod
    def from_transaction(cls, arr: List[int]) -> "Itemset":
        items = list(arr)
        items.sort()  # matches Java constructor sorting
        return cls(items=items, support=1)

    def contains_all(self, query: List[int]) -> bool:
        # matches Java containsAll(int[] query) using List.contains
        # (O(n*m), same behavior)
        for q in query:
            if q not in self.items:
                return False
        return True

    def increase_support(self) -> None:
        self.support += 1

    def __str__(self) -> str:
        return " ".join(str(x) for x in self.items)


class ItemsetTree:
    def __init__(self) -> None:
        self.tree: List[Itemset] = []

    def add_transaction(self, t: List[int]) -> None:
        """
        Matches your Java logic EXACTLY:

        for (Itemset is : tree) {
            if (is.items.equals(Arrays.stream(t).boxed().toList())) { ... }
        }
        tree.add(new Itemset(t));  // where Itemset sorts items internally

        Important detail:
        - Itemset stored items are SORTED.
        - Comparison is done against t in its ORIGINAL order.
        So duplicates only match if t is already sorted the same way.
        """
        t_list_original_order = list(t)

        for iset in self.tree:
            if iset.items == t_list_original_order:
                iset.increase_support()
                return

        self.tree.append(Itemset.from_transaction(t))

    def get_all_itemsets(self) -> List[Itemset]:
        return self.tree


# ----------------------------------------------------------------------
# Main (direct parameters, no argparse)
# ----------------------------------------------------------------------

# ====== SET PARAMETERS HERE ======
INPUT_FILE = "contextItemsetTree.txt"
RELATIVE_MIN_SUP = 0.2
OUTPUT_FILE = "output_py.txt"
# =================================


def main() -> None:
    input_file = INPUT_FILE if INPUT_FILE is not None else file_to_path("contextItemsetTree.txt")
    transactions = read_transactions(input_file)

    relative_min_sup = float(RELATIVE_MIN_SUP)
    tree = ItemsetTree()
    transaction_count = len(transactions)

    start_insertion = time.time()
    for t in transactions:
        tree.add_transaction(t)
    end_insertion = time.time()

    insertion_time_ms = (end_insertion - start_insertion) * 1000.0

    # Convert relative support to absolute minimum count (same as Java)
    minsup = max(1, int(math.ceil(relative_min_sup * transaction_count)))

    all_itemsets = tree.get_all_itemsets()
    frequent_itemsets_count = sum(1 for iset in all_itemsets if iset.support >= minsup)

    # Output path
    if OUTPUT_FILE is not None:
        output_file = Path(OUTPUT_FILE)
    else:
        output_file = Path("Java") / "src" / "itemsettree" / "output_py.txt"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Save frequent itemsets to file (same format as Java)
    with open(output_file, "w", encoding="utf-8") as w:
        for iset in all_itemsets:
            if iset.support >= minsup:
                rel_sup = iset.support / transaction_count
                w.write(f"{iset}  #SUP: {rel_sup}")
                w.write("\n")

    # Print stats
    print("============= ITEMSET-TREE - STATS =============")
    print(f"Number of nodes           : {len(all_itemsets)}")
    print(f"Frequent itemsets count   : {frequent_itemsets_count}")
    print(f"Number of transactions    : {transaction_count}")
    print(f"Total insertion time      : {insertion_time_ms} ms")
    print(f"Insertion time per txn    : {insertion_time_ms / transaction_count} ms")
    print(f"Minimum support threshold : {minsup} transactions ({relative_min_sup * 100}%)")
    print("=================================================")


if __name__ == "__main__":
    main()