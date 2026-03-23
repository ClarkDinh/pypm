# This is a Python implementation of the CORI algorithm for mining rare correlated itemsets.
from __future__ import annotations
import math
import os
import sys
from typing import List, Optional, Set, Dict


# -------------------------------
# MemoryLogger
# -------------------------------
class MemoryLogger:
    """Equivalent to MemoryLogger.java (singleton to record max memory)."""

    _instance = None

    def __init__(self) -> None:
        self._max_mb = 0.0

    @staticmethod
    def getInstance() -> "MemoryLogger":
        if MemoryLogger._instance is None:
            MemoryLogger._instance = MemoryLogger()
        return MemoryLogger._instance

    def getMaxMemory(self) -> float:
        # Portable placeholder (Python stdlib lacks cross-platform RSS).
        return float(f"{self._max_mb:.6f}")

    def reset(self) -> None:
        self._max_mb = 0.0

    def checkMemory(self) -> float:
        # Keep contract but avoid non-portable calls.
        return self._max_mb


# -------------------------------
# AbstractItemset / AbstractOrderedItemset (interfaces)
# -------------------------------
class AbstractItemset:
    """Equivalent to AbstractItemset.java (interface-like base)."""

    def size(self) -> int:
        raise NotImplementedError

    def __str__(self) -> str:
        raise NotImplementedError

    def getAbsoluteSupport(self) -> int:
        raise NotImplementedError

    def getRelativeSupport(self, nb_object: int) -> float:
        raise NotImplementedError

    def contains(self, item: int) -> bool:
        raise NotImplementedError

    def print(self) -> None:
        sys.stdout.write(str(self))


class AbstractOrderedItemset(AbstractItemset):
    """Equivalent to AbstractOrderedItemset.java (ordered, unique items)."""

    def get(self, position: int) -> int:
        raise NotImplementedError

    def getLastItem(self) -> int:
        return self.get(self.size() - 1)

    def __str__(self) -> str:
        if self.size() == 0:
            return "EMPTYSET"
        return " ".join(str(self.get(i)) for i in range(self.size()))

    def getRelativeSupport(self, nb_object: int) -> float:
        return float(self.getAbsoluteSupport()) / float(nb_object)

    def contains(self, item: int) -> bool:
        for i in range(self.size()):
            gi = self.get(i)
            if gi == item:
                return True
            if gi > item:
                return False
        return False

    def containsAll(self, other: "AbstractOrderedItemset") -> bool:
        if self.size() < other.size():
            return False
        i = 0
        for j in range(other.size()):
            found = False
            while not found and i < self.size():
                if self.get(i) == other.get(j):
                    found = True
                elif self.get(i) > other.get(j):
                    return False
                i += 1
            if not found:
                return False
        return True

    def isEqualTo(self, other: "AbstractOrderedItemset") -> bool:
        if self.size() != other.size():
            return False
        for i in range(self.size()):
            if self.get(i) != other.get(i):
                return False
        return True

    def isEqualToArray(self, arr: List[int]) -> bool:
        if self.size() != len(arr):
            return False
        for i in range(len(arr)):
            if self.get(i) != arr[i]:
                return False
        return True

    def allTheSameExceptLastItemV2(self, other: "AbstractOrderedItemset") -> bool:
        if self.size() != other.size():
            return False
        for i in range(self.size() - 1):
            if self.get(i) != other.get(i):
                return False
        return True

    def allTheSameExceptLastItem(self, other: "AbstractOrderedItemset") -> Optional[int]:
        if self.size() != other.size():
            return None
        for i in range(self.size()):
            if i == self.size() - 1:
                if not (self.get(i) < other.get(i)):
                    return None
            else:
                if self.get(i) != other.get(i):
                    return None
        return other.get(other.size() - 1)


# -------------------------------
# ArraysAlgos
# -------------------------------
class ArraysAlgos:
    """Equivalent to ArraysAlgos.java."""

    @staticmethod
    def intersectTwoSortedArrays(a1: List[int], a2: List[int]) -> List[int]:
        temp: List[int] = []
        i = j = 0
        while i < len(a1) and j < len(a2):
            if a1[i] == a2[j]:
                temp.append(a1[i])
                i += 1
                j += 1
            elif a1[i] < a2[j]:
                i += 1
            else:
                j += 1
        return temp


# -------------------------------
# Itemset / ItemsetCORI / ItemsetsCORI
# -------------------------------
class Itemset(AbstractOrderedItemset):
    """Equivalent to Itemset.java."""

    def __init__(self, items: Optional[List[int]] = None, support: int = 0) -> None:
        self.itemset: List[int] = list(items) if items else []
        self.support: int = support

    def getItems(self) -> List[int]:
        return self.itemset

    def size(self) -> int:
        return len(self.itemset)

    def get(self, position: int) -> int:
        return self.itemset[position]

    def getAbsoluteSupport(self) -> int:
        return self.support

    def setAbsoluteSupport(self, support: int) -> None:
        self.support = support

    def increaseTransactionCount(self) -> None:
        self.support += 1

    def cloneItemSetMinusOneItem(self, item_to_remove: int) -> "Itemset":
        return Itemset([x for x in self.itemset if x != item_to_remove])

    def cloneItemSetMinusAnItemset(self, to_not_keep: "Itemset") -> "Itemset":
        banned = set(to_not_keep.getItems())
        return Itemset([x for x in self.itemset if x not in banned])

    def intersection(self, other: "Itemset") -> "Itemset":
        inter = ArraysAlgos.intersectTwoSortedArrays(self.getItems(), other.getItems())
        return Itemset(inter)


class ItemsetCORI(Itemset):
    """Equivalent to ItemsetCORI.java (adds bond field)."""

    def __init__(self, items: List[int]) -> None:
        super().__init__(items)
        self.bond: float = 0.0

    def getBond(self) -> float:
        return self.bond

    def setBond(self, bond: float) -> None:
        self.bond = float(bond)


class ItemsetsCORI:
    """Equivalent to ItemsetsCORI.java (grouped by itemset length)."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.levels: List[List[ItemsetCORI]] = [[]]  # level 0 empty
        self.itemsetsCount = 0

    def addItemset(self, itemset: ItemsetCORI, k: int) -> None:
        while len(self.levels) <= k:
            self.levels.append([])
        self.levels[k].append(itemset)
        self.itemsetsCount += 1

    def getLevels(self) -> List[List[ItemsetCORI]]:
        return self.levels

    def getItemsetsCount(self) -> int:
        return self.itemsetsCount

    def setName(self, new_name: str) -> None:
        self.name = new_name

    def decreaseItemsetCount(self) -> None:
        self.itemsetsCount -= 1

    def printItemsets(self, nb_object: int) -> None:
        print(f" ------- {self.name} -------")
        pattern_count = 0
        for li, level in enumerate(self.levels):
            print(f"  L{li} ")
            for it in level:
                it.itemset.sort()
                print(f"  pattern {pattern_count}:  ", end="")
                it.print()
                print(f" support :  {it.getAbsoluteSupport()}", end="")
                print(f" bond :  {it.getBond()}")
                pattern_count += 1
        print(" --------------------------------")


# -------------------------------
# TransactionDatabase
# -------------------------------
class TransactionDatabase:
    """Equivalent to TransactionDatabase.java."""

    def __init__(self) -> None:
        self.items: Set[int] = set()
        self.transactions: List[List[int]] = []

    def addTransaction(self, transaction: List[int]) -> None:
        self.transactions.append(transaction)
        for x in transaction:
            self.items.add(x)

    def loadFile(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in ("#", "%", "@"):
                    continue
                parts = line.split()
                self._addTransactionFromStrings(parts)

    def _addTransactionFromStrings(self, items_str: List[str]) -> None:
        trans: List[int] = []
        for token in items_str:
            item = int(token)
            trans.append(item)
            self.items.add(item)
        self.transactions.append(trans)

    def size(self) -> int:
        return len(self.transactions)

    def getTransactions(self) -> List[List[int]]:
        return self.transactions

    def printDatabase(self) -> None:
        print("===================  TRANSACTION DATABASE ===================")
        for idx, t in enumerate(self.transactions):
            print(f"{idx}:  {' '.join(str(x) for x in t)}")


# -------------------------------
# TriangularMatrix
# -------------------------------
class TriangularMatrix:
    """Equivalent to TriangularMatrix.java."""

    def __init__(self, element_count: int) -> None:
        self.elementCount = element_count
        self.matrix: List[List[int]] = []
        for i in range(element_count - 1):
            self.matrix.append([0] * (element_count - i - 1))

    def incrementCount(self, i: int, j: int, value: int = 1) -> None:
        if j < i:
            self.matrix[self.elementCount - i - 1][j] += value
        else:
            self.matrix[self.elementCount - j - 1][i] += value

    def getSupportForItems(self, i: int, j: int) -> int:
        if j < i:
            return self.matrix[self.elementCount - i - 1][j]
        else:
            return self.matrix[self.elementCount - j - 1][i]

    def setSupport(self, i: int, j: int, support: int) -> None:
        if j < i:
            self.matrix[self.elementCount - i - 1][j] = support
        else:
            self.matrix[self.elementCount - j - 1][i] = support


# -------------------------------
# AlgoCORI
# -------------------------------
class AlgoCORI:
    """Equivalent to AlgoCORI.java."""

    class BitSetSupport:
        """Holds a tidset and its cardinality (like BitSet+support in Java)."""
        def __init__(self, bitset: Optional[Set[int]] = None, support: int = 0) -> None:
            self.bitset: Set[int] = bitset if bitset is not None else set()
            self.support: int = support

    def __init__(self) -> None:
        self.minsupRelative: int = 0
        self.minBond: float = 0.0
        self.database: Optional[TransactionDatabase] = None
        self.frequentItemsets: Optional[ItemsetsCORI] = None
        self.writer = None
        self.itemsetCount: int = 0
        self.matrix: Optional[TriangularMatrix] = None
        self.BUFFERS_SIZE = 2000
        self.itemsetBuffer = [0] * self.BUFFERS_SIZE
        self.showTransactionIdentifiers = False
        self.maxItemsetSize = (1 << 31) - 1  # mimic Integer.MAX_VALUE

    # ---------- public API ----------
    def setShowTransactionIdentifiers(self, flag: bool) -> None:
        self.showTransactionIdentifiers = flag

    def setMaximumPatternLength(self, length: int) -> None:
        self.maxItemsetSize = length

    def runAlgorithm(
        self,
        output_path: Optional[str],
        database: TransactionDatabase,
        minsupp: float,
        minBond: float,
        useTriangularMatrixOptimization: bool
    ) -> Optional[ItemsetsCORI]:
        # initialize
        self.itemsetBuffer = [0] * self.BUFFERS_SIZE
        MemoryLogger.getInstance().reset()
        self.itemsetCount = 0
        self.database = database
        self.frequentItemsets = None
        self.writer = None

        if output_path is None:
            self.frequentItemsets = ItemsetsCORI("CORRELATED ITEMSETS")
        else:
            self.writer = open(output_path, "w", encoding="utf-8")

        # Java uses Math.ceil —> use math.ceil
        self.minsupRelative = int(math.ceil(minsupp * database.size()))
        self.minBond = float(minBond)

        # [DEBUG] line (as required)
        print(f"[DEBUG] minsupRelative={self.minsupRelative} | transactions={database.size()}")

        # Build TID sets
        mapItemTIDS: Dict[int, AlgoCORI.BitSetSupport] = {}
        maxItemId = self._calculateSupportSingleItems(database, mapItemTIDS)

        # Optional triangular matrix for 2-itemset supports
        if useTriangularMatrixOptimization and self.maxItemsetSize >= 1:
            self.matrix = TriangularMatrix(maxItemId + 1)
            for trans in database.getTransactions():
                arr = list(trans)
                for i in range(len(arr)):
                    for j in range(i + 1, len(arr)):
                        self.matrix.incrementCount(arr[i], arr[j])

        # Create list of single items
        singleItems: List[int] = []
        for item, tidset in mapItemTIDS.items():
            support = tidset.support
            if self.maxItemsetSize >= 1:
                singleItems.append(item)
                if support < self.minsupRelative:
                    self._saveSingleItem(item, support, tidset.bitset)

        # Sort by increasing support (tie-break by item ID for determinism)
        singleItems.sort(key=lambda it: (mapItemTIDS[it].support, it))

        # Build equivalence classes and recurse
        if self.maxItemsetSize >= 2:
            for idx_i, itemI in enumerate(singleItems):
                tidsetI = mapItemTIDS[itemI]
                eq_items: List[int] = []
                eq_tidsets: List[AlgoCORI.BitSetSupport] = []
                eq_conj: List[AlgoCORI.BitSetSupport] = []

                for j in range(idx_i + 1, len(singleItems)):
                    itemJ = singleItems[j]
                    supportIJ = -1
                    if useTriangularMatrixOptimization and self.matrix is not None:
                        supportIJ = self.matrix.getSupportForItems(itemI, itemJ)

                    tidsetJ = mapItemTIDS[itemJ]

                    if useTriangularMatrixOptimization and self.matrix is not None:
                        bitsetIJ = self._performANDFirstTime(tidsetI, tidsetJ, supportIJ)
                    else:
                        bitsetIJ = self._performAND(tidsetI, tidsetJ)

                    if bitsetIJ.support >= 1:
                        conjIJ = self._performOR(tidsetI, tidsetJ)
                        eq_items.append(itemJ)
                        eq_tidsets.append(bitsetIJ)
                        eq_conj.append(conjIJ)

                if len(eq_items) > 0:
                    self.itemsetBuffer[0] = itemI
                    self._processEquivalenceClass(self.itemsetBuffer, 1, eq_items, eq_tidsets, eq_conj)

        MemoryLogger.getInstance().checkMemory()
        if self.writer:
            self.writer.close()
        return self.frequentItemsets

    # ---------- internals ----------
    def _calculateSupportSingleItems(
        self,
        database: TransactionDatabase,
        mapItemTIDS: Dict[int, "AlgoCORI.BitSetSupport"]
    ) -> int:
        maxItemId = 0
        for tid, trans in enumerate(database.getTransactions()):
            for item in trans:
                tids = mapItemTIDS.get(item)
                if tids is None:
                    tids = AlgoCORI.BitSetSupport(set(), 0)
                    mapItemTIDS[item] = tids
                    if item > maxItemId:
                        maxItemId = item
                if tid not in tids.bitset:  # mirrors BitSet.set(tid) idempotence
                    tids.bitset.add(tid)
                    tids.support += 1
        return maxItemId

    def _performAND(
        self,
        tidsetI: "AlgoCORI.BitSetSupport",
        tidsetJ: "AlgoCORI.BitSetSupport"
    ) -> "AlgoCORI.BitSetSupport":
        inter = tidsetI.bitset & tidsetJ.bitset
        return AlgoCORI.BitSetSupport(set(inter), len(inter))

    def _performOR(
        self,
        tidsetI: "AlgoCORI.BitSetSupport",
        tidsetJ: "AlgoCORI.BitSetSupport"
    ) -> "AlgoCORI.BitSetSupport":
        uni = tidsetI.bitset | tidsetJ.bitset
        return AlgoCORI.BitSetSupport(set(uni), len(uni))

    def _performANDFirstTime(
        self,
        tidsetI: "AlgoCORI.BitSetSupport",
        tidsetJ: "AlgoCORI.BitSetSupport",
        supportIJ: int
    ) -> "AlgoCORI.BitSetSupport":
        inter = tidsetI.bitset & tidsetJ.bitset
        return AlgoCORI.BitSetSupport(set(inter), int(supportIJ))

    def _save(
        self,
        prefix: List[int],
        prefixLength: int,
        suffixItem: int,
        tidset: "AlgoCORI.BitSetSupport",
        bond: float
    ) -> None:
        self.itemsetCount += 1
        if self.writer is None:
            arr = prefix[:prefixLength] + [suffixItem]
            itemset = ItemsetCORI(arr)
            itemset.setAbsoluteSupport(tidset.support)
            itemset.setBond(bond)
            assert self.frequentItemsets is not None
            self.frequentItemsets.addItemset(itemset, len(arr))
        else:
            parts = []
            for i in range(prefixLength):
                parts.append(str(prefix[i]))
                parts.append(" ")
            parts.append(str(suffixItem))
            parts.append(" #SUP: ")
            parts.append(str(tidset.support))
            parts.append(" #BOND: ")
            parts.append(str(bond))
            if self.showTransactionIdentifiers:
                parts.append(" #TID:")
                for tid in sorted(tidset.bitset):
                    parts.append(f" {tid}")
            self.writer.write("".join(parts))
            self.writer.write("\n")

    def _saveSingleItem(self, item: int, support: int, tidset: Set[int]) -> None:
        self.itemsetCount += 1
        if self.writer is None:
            it = ItemsetCORI([item])
            it.setAbsoluteSupport(support)
            it.setBond(1.0)
            assert self.frequentItemsets is not None
            self.frequentItemsets.addItemset(it, 1)
        else:
            parts = [str(item), " #SUP: ", str(support), " #BOND: ", str(1.0)]
            if self.showTransactionIdentifiers:
                parts.append(" #TID:")
                for tid in sorted(tidset):
                    parts.append(f" {tid}")
            self.writer.write("".join(parts))
            self.writer.write("\n")

    def _processEquivalenceClass(
        self,
        prefix: List[int],
        prefixLength: int,
        eqItems: List[int],
        eqTidsets: List["AlgoCORI.BitSetSupport"],
        eqConj: List["AlgoCORI.BitSetSupport"]
    ) -> None:
        # Case: only one suffix
        if len(eqItems) == 1:
            itemI = eqItems[0]
            tidsetI = eqTidsets[0]
            if tidsetI.support < self.minsupRelative:
                conjI = eqConj[0]
                bondI = float(tidsetI.support) / float(conjI.support)
                if bondI >= self.minBond:
                    self._save(prefix, prefixLength, itemI, tidsetI, bondI)
            return

        # Case: exactly two suffixes
        if len(eqItems) == 2:
            itemI = eqItems[0]
            tidsetI = eqTidsets[0]
            conjI = eqConj[0]
            bondI = float(tidsetI.support) / float(conjI.support)
            if tidsetI.support < self.minsupRelative and bondI >= self.minBond:
                self._save(prefix, prefixLength, itemI, tidsetI, bondI)

            itemJ = eqItems[1]
            tidsetJ = eqTidsets[1]
            conjJ = eqConj[1]
            if tidsetJ.support < self.minsupRelative:
                bondJ = float(tidsetJ.support) / float(conjJ.support)
                if bondJ >= self.minBond:
                    self._save(prefix, prefixLength, itemJ, tidsetJ, bondJ)

            bitsetIJ = self._performAND(tidsetI, tidsetJ)
            if bitsetIJ.support < self.minsupRelative and (prefixLength + 2) <= self.maxItemsetSize:
                newPrefixLength = prefixLength + 1
                prefix[prefixLength] = itemI
                if bitsetIJ.support >= 1 and bitsetIJ.support < self.minsupRelative:
                    conjIJ = self._performOR(conjI, conjJ)
                    bondIJ = float(bitsetIJ.support) / float(conjIJ.support)
                    if bondIJ >= self.minBond:
                        self._save(prefix, newPrefixLength, itemJ, bitsetIJ, bondIJ)
            return

        # General case (len >= 3)
        for idx_i, itemI in enumerate(eqItems):
            tidsetI = eqTidsets[idx_i]
            conjI = eqConj[idx_i]

            if tidsetI.support < self.minsupRelative:
                bondI = float(tidsetI.support) / float(conjI.support)
                if bondI >= self.minBond:
                    self._save(prefix, prefixLength, itemI, tidsetI, bondI)

            if (prefixLength + 2) <= self.maxItemsetSize:
                new_eq_items: List[int] = []
                new_eq_tid: List[AlgoCORI.BitSetSupport] = []
                new_eq_conj: List[AlgoCORI.BitSetSupport] = []

                for j in range(idx_i + 1, len(eqItems)):
                    itemJ = eqItems[j]
                    tidsetJ = eqTidsets[j]
                    conjJ = eqConj[j]

                    bitsetIJ = self._performAND(tidsetI, tidsetJ)
                    conjIJ = self._performOR(conjI, conjJ)
                    bondIJ = float(bitsetIJ.support) / float(conjIJ.support)

                    if bitsetIJ.support >= 1 and bondIJ >= self.minBond:
                        new_eq_items.append(itemJ)
                        new_eq_tid.append(bitsetIJ)
                        new_eq_conj.append(conjIJ)

                if len(new_eq_items) > 0:
                    prefix[prefixLength] = itemI
                    newPrefixLen = prefixLength + 1
                    self._processEquivalenceClass(prefix, newPrefixLen, new_eq_items, new_eq_tid, new_eq_conj)

        MemoryLogger.getInstance().checkMemory()

    # ---------- stats ----------
    def printStats(self) -> None:
        print("=============  CORI _py - STATS =============")
        print(f" Minbond = {self.minBond} Minsup = {self.minsupRelative} transactions")
        print(f" Database transaction count: {self.database.size() if self.database else 0}")
        print(f" Rare correlated itemset count : {self.itemsetCount}")
        print(f" Maximum memory usage : {MemoryLogger.getInstance().getMaxMemory()} mb")
        print("=============================================")


# -------------------------------
# MAIN (Manual parameters for “Run” button convenience)
# -------------------------------
def main() -> None:
    """
    Change values below to try different datasets/thresholds.
    """
    # ========== MANUAL PARAMETERS (EDIT THESE 5 LINES) ==========
    # Get the directory where this script is located for input file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(script_dir, "contextPasquier99.txt")
  # Path to dataset (space-separated integers per line)
    minsup = 0.8                          # Relative minsup (e.g., 0.5, 0.6, 0.8, 0.9)
    minbond = 0.2                         # Minimum bond threshold
    output_path = "cori_outputs.txt"     # File to save results (relative to current working directory, set to None to keep in memory)
    use_triangular_matrix = False         # True to enable triangular matrix optimization
    # ============================================================

    db = TransactionDatabase()
    db.loadFile(data_path)

    algo = AlgoCORI()
    # To limit pattern length (like Java's algo.setMaximumPatternLength(3)), uncomment:
    # algo.setMaximumPatternLength(3)

    patterns = algo.runAlgorithm(output_path, db, minsup, minbond, use_triangular_matrix)

    if output_path is None and patterns is not None:
        patterns.printItemsets(db.size())

    algo.printStats()

    out_msg = output_path if output_path is not None else "(saved in memory)"
    print(f"\n[SUCCESS] Mining complete! Output saved to: {out_msg}\n=========================================\n")


if __name__ == "__main__":
    main()
