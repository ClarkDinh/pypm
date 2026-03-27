#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from typing import List, Optional


# =========================
# MemoryLogger (singleton)
# =========================
class MemoryLogger:
    _instance: Optional["MemoryLogger"] = None

    def __init__(self) -> None:
        self.maxMemory = 0.0  # MB

    @classmethod
    def getInstance(cls) -> "MemoryLogger":
        if cls._instance is None:
            cls._instance = MemoryLogger()
        return cls._instance

    def getMaxMemory(self) -> float:
        return self.maxMemory

    def reset(self) -> None:
        self.maxMemory = 0.0

    def checkMemory(self) -> float:
        """
        Approximate current RSS memory and update maxMemory.
        Uses psutil if available; otherwise uses resource.getrusage (Unix).
        """
        current_mb = 0.0
        # Try psutil first
        try:
            import psutil  # type: ignore

            proc = psutil.Process(os.getpid())
            current_mb = proc.memory_info().rss / 1024.0 / 1024.0
        except Exception:
            # Fallback: resource (Linux/macOS)
            try:
                import resource  # type: ignore

                ru_max = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                # On Linux ru_maxrss is KB, on macOS it's bytes.
                # Heuristic: if it's huge, treat as bytes.
                if ru_max > 10_000_000:  # likely bytes
                    current_mb = ru_max / 1024.0 / 1024.0
                else:  # likely KB
                    current_mb = ru_max / 1024.0
            except Exception:
                current_mb = 0.0

        if current_mb > self.maxMemory:
            self.maxMemory = current_mb
        return current_mb


# =========================
# Itemset / Itemsets
# =========================
class Itemset:
    def __init__(self, itemset: Optional[List[int]] = None, utility: float = 0.0) -> None:
        self.itemset: List[int] = list(itemset) if itemset is not None else []
        self.utility: float = utility

    def getItems(self) -> List[int]:
        return self.itemset

    def getUtility(self) -> float:
        return self.utility

    def size(self) -> int:
        return len(self.itemset)

    def get(self, position: int) -> int:
        return self.itemset[position]

    def setUtility(self, utility: float) -> None:
        self.utility = utility

    def cloneItemSetMinusOneItem(self, itemToRemove: int) -> "Itemset":
        new_items = [x for x in self.itemset if x != itemToRemove]
        return Itemset(new_items, 0.0)

    def __str__(self) -> str:
        # Java Itemset.toString() ends with trailing space
        return (" ".join(str(x) for x in self.itemset) + " ") if self.itemset else ""


class Itemsets:
    """
    Python equivalent of SPMF Itemsets.java for EFIM-Closed.
    Stores itemsets by levels (size), counts total itemsets,
    and provides a printItemsets() matching the Java behavior.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.levels: List[List[Itemset]] = [[]]  # level 0 exists by default
        self.itemsetsCount = 0

    def printItemsets(self) -> None:
        print(" ------- " + self.name + " -------")
        patternCount = 0
        levelCount = 0
        for level in self.levels:
            print(f"  L{levelCount} ")
            for it in level:
                it.itemset.sort()
                print(f"  pattern {patternCount}:  {str(it)}Utility :  {it.getUtility()} ")
                patternCount += 1
            levelCount += 1
        print(" --------------------------------")

    def addItemset(self, itemset: Itemset, k: int) -> None:
        while len(self.levels) <= k:
            self.levels.append([])
        self.levels[k].append(itemset)
        self.itemsetsCount += 1

    def getLevels(self) -> List[List[Itemset]]:
        return self.levels

    def getItemsetsCount(self) -> int:
        return self.itemsetsCount

    def setName(self, newName: str) -> None:
        self.name = newName

    def decreaseItemsetCount(self) -> None:
        self.itemsetsCount -= 1


# =========================
# Dataset / Transaction
# =========================
class Transaction:
    # Java uses static buffers; Python doesn't need them, but keep attributes similar.
    tempItems: List[int] = [0] * 2000
    tempUtilities: List[int] = [0] * 2000

    def __init__(
        self,
        items: List[int],
        utilities: List[int],
        transactionUtility: int,
        originalTransactions: Optional[List[List[int]]],
    ) -> None:
        self.items: List[int] = items
        self.utilities: List[int] = utilities
        self.transactionUtility: int = transactionUtility
        self.offset: int = 0
        self.prefixUtility: int = 0
        if originalTransactions is not None:
            self.originalTransactions: List[List[int]] = originalTransactions
        else:
            self.originalTransactions = []

    @classmethod
    def projected(cls, transaction: "Transaction", offsetE: int) -> "Transaction":
        # copy references (same as Java style)
        items = transaction.items
        utils = transaction.utilities

        utilityE = utils[offsetE]
        prefixUtility = transaction.prefixUtility + utilityE

        # remaining transaction utility
        transUtil = transaction.transactionUtility - utilityE
        for i in range(transaction.offset, offsetE):
            transUtil -= transaction.utilities[i]

        t = cls(items, utils, transUtil, transaction.originalTransactions)
        t.prefixUtility = prefixUtility
        t.offset = offsetE + 1
        return t

    def getItems(self) -> List[int]:
        return self.items

    def getUtilities(self) -> List[int]:
        return self.utilities

    def getLastPosition(self) -> int:
        return len(self.items) - 1

    def removeUnpromisingItems(self, oldNamesToNewNames: List[int]) -> None:
        kept_items: List[int] = []
        kept_utils: List[int] = []

        for item, util in zip(self.items, self.utilities):
            newName = oldNamesToNewNames[item] if item < len(oldNamesToNewNames) else 0
            if newName != 0:
                kept_items.append(newName)
                kept_utils.append(util)
            else:
                self.transactionUtility -= util

        # Sort by increasing item id (Java insertion sort)
        self._insertionSort(kept_items, kept_utils)

        self.items = kept_items
        self.utilities = kept_utils

        # Java sets originalTransactions = new int[][]{this.items};
        # Make a copy to freeze that snapshot for "originalTransactions"
        self.originalTransactions = [list(self.items)]

    @staticmethod
    def _insertionSort(items: List[int], utils: List[int]) -> None:
        for j in range(1, len(items)):
            itemJ = items[j]
            utilJ = utils[j]
            i = j - 1
            while i >= 0 and items[i] > itemJ:
                items[i + 1] = items[i]
                utils[i + 1] = utils[i]
                i -= 1
            items[i + 1] = itemJ
            utils[i + 1] = utilJ

    def __str__(self) -> str:
        parts = []
        for i in range(self.offset, len(self.items)):
            parts.append(f"{self.items[i]}[{self.utilities[i]}]")
        return " ".join(parts) + f" Remaining Utility:{self.transactionUtility} Prefix Utility:{self.prefixUtility}"

    # Used in AlgoEFIMClosed.hasNoBackwardExtension via originalTransactions
    def containsByBinarySearchOriginalTransaction(self, item: int) -> bool:
        for original in self.originalTransactions:
            low, high = 0, len(original) - 1
            while high >= low:
                mid = (low + high) >> 1
                if original[mid] == item:
                    break
                if original[mid] < item:
                    low = mid + 1
                else:
                    high = mid - 1
            else:
                return False
        return True


class Dataset:
    def __init__(self, datasetPath: str, maximumTransactionCount: int) -> None:
        self.transactions: List[Transaction] = []
        self.maxItem: int = 0

        i = 0
        with open(datasetPath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in ("#", "%", "@"):
                    continue
                i += 1
                self.transactions.append(self._createTransaction(line))
                if i == maximumTransactionCount:
                    break

        print("Transaction count :" + str(len(self.transactions)))

    def _createTransaction(self, line: str) -> Transaction:
        split = line.split(":")
        if len(split) < 3:
            raise ValueError(f"Bad transaction line (need 3 ':'): {line}")

        transactionUtility = int(split[1].strip())
        itemsString = split[0].strip().split()
        utilsString = split[2].strip().split()

        if len(itemsString) != len(utilsString):
            raise ValueError(f"Items/utilities length mismatch: {line}")

        items: List[int] = []
        utils: List[int] = []
        for s_item, s_util in zip(itemsString, utilsString):
            item = int(s_item)
            util = int(s_util)
            items.append(item)
            utils.append(util)
            if item > self.maxItem:
                self.maxItem = item

        return Transaction(items, utils, transactionUtility, None)

    def getTransactions(self) -> List[Transaction]:
        return self.transactions

    def getMaxItem(self) -> int:
        return self.maxItem

    def __str__(self) -> str:
        return "\n".join(str(t) for t in self.transactions)


# =========================
# EFIM-Closed algorithm
# =========================
class AlgoEFIMClosed:
    DEBUG = False

    def __init__(self) -> None:
        self.highUtilityItemsets: Optional[Itemsets] = None
        self.writer = None

        self.patternCount = 0
        self.startTimestamp = 0
        self.endTimestamp = 0
        self.minUtil = 0

        self.utilityBinArraySU: List[int] = []
        self.utilityBinArrayLU: List[int] = []
        self.utilityBinArraySupport: List[int] = []

        self.temp: List[int] = [0] * 500

        self.oldNameToNewNames: List[int] = []
        self.newNamesToOldNames: List[int] = []
        self.newItemCount = 0

        self.activateTransactionMerging = True
        self.MAXIMUM_SIZE_MERGING = 1000

        self.transactionReadingCount = 0
        self.mergeCount = 0
        self.candidateCount = 0

        self.activateSubtreeUtilityPruning = True
        self.activateClosedPatternJumping = True

    def runAlgorithm(
        self,
        minUtil: int,
        inputPath: str,
        outputPath: Optional[str],
        activateTransactionMerging: bool,
        maximumTransactionCount: int,
        activateSubtreeUtilityPruning: bool,
        activateClosedPatternJump: bool,
    ) -> Optional[Itemsets]:

        # reset stats
        self.mergeCount = 0
        self.transactionReadingCount = 0
        self.candidateCount = 0

        self.activateTransactionMerging = activateTransactionMerging
        self.activateSubtreeUtilityPruning = activateSubtreeUtilityPruning
        self.activateClosedPatternJumping = activateClosedPatternJump

        self.startTimestamp = int(time.time() * 1000)

        dataset = Dataset(inputPath, maximumTransactionCount)

        self.minUtil = minUtil

        if outputPath is not None:
            self.writer = open(outputPath, "w", encoding="utf-8")
            self.highUtilityItemsets = None
        else:
            self.writer = None
            self.highUtilityItemsets = Itemsets("Itemsets")

        self.patternCount = 0
        MemoryLogger.getInstance().reset()

        if self.DEBUG:
            print("===== Initial database ===")
            print(str(dataset))

        # TWU / local utility first scan
        self.useUtilityBinArrayToCalculateLocalUtilityFirstTime(dataset)

        # keep promising
        itemsToKeep: List[int] = []
        for j in range(1, len(self.utilityBinArrayLU)):
            if self.utilityBinArrayLU[j] >= minUtil:
                itemsToKeep.append(j)

        # sort by increasing TWU
        self.insertionSort(itemsToKeep, self.utilityBinArrayLU)

        # rename items
        self.oldNameToNewNames = [0] * (dataset.getMaxItem() + 1)
        self.newNamesToOldNames = [0] * (dataset.getMaxItem() + 1)
        currentName = 1
        for idx in range(len(itemsToKeep)):
            old = itemsToKeep[idx]
            self.oldNameToNewNames[old] = currentName
            self.newNamesToOldNames[currentName] = old
            itemsToKeep[idx] = currentName
            currentName += 1

        self.newItemCount = len(itemsToKeep)
        self.utilityBinArraySU = [0] * (self.newItemCount + 1)
        if self.activateClosedPatternJumping:
            self.utilityBinArraySupport = [0] * (self.newItemCount + 1)

        # remove unpromising items + rename + sort each transaction
        for t in dataset.getTransactions():
            t.removeUnpromisingItems(self.oldNameToNewNames)

        # sort transactions for merging (lexicographical backward)
        if self.activateTransactionMerging:
            dataset.transactions.sort(key=self._transaction_sort_key)

            # remove empty transactions at beginning
            emptyCount = 0
            for t in dataset.getTransactions():
                if len(t.items) == 0:
                    emptyCount += 1
                else:
                    break
            if emptyCount > 0:
                dataset.transactions = dataset.transactions[emptyCount:]

        if self.DEBUG:
            print("===== Database without unpromising items and sorted ===")
            print(str(dataset))

        # subtree utility first scan
        self.useUtilityBinArrayToCalculateSubtreeUtilityFirstTime(dataset)

        # items to explore (primary) if SU pruning
        if self.activateSubtreeUtilityPruning:
            itemsToExplore = [it for it in itemsToKeep if self.utilityBinArraySU[it] >= minUtil]
            self.backtrackingEFIM(dataset.getTransactions(), itemsToKeep, itemsToExplore, 0)
        else:
            self.backtrackingEFIM(dataset.getTransactions(), itemsToKeep, itemsToKeep, 0)

        self.endTimestamp = int(time.time() * 1000)

        if self.writer is not None:
            self.writer.close()
            self.writer = None

        MemoryLogger.getInstance().checkMemory()
        return self.highUtilityItemsets

    @staticmethod
    def insertionSort(items: List[int], utilityBinArrayTWU: List[int]) -> None:
        for j in range(1, len(items)):
            itemJ = items[j]
            i = j - 1
            while i >= 0:
                itemI = items[i]
                comparison = utilityBinArrayTWU[itemI] - utilityBinArrayTWU[itemJ]
                if comparison == 0:
                    comparison = itemI - itemJ
                if comparison <= 0:
                    break
                items[i + 1] = itemI
                i -= 1
            items[i + 1] = itemJ

    def backtrackingEFIM(
        self,
        transactionsOfP: List[Transaction],
        itemsToKeep: List[int],
        itemsToExplore: List[int],
        prefixLength: int,
    ) -> int:

        maxSupport = 0

        for j, e in enumerate(itemsToExplore):
            transactionsPe: List[Transaction] = []
            utilityPe = 0
            supportPe = 0
            nowEmptyTransactionsPe: List[Transaction] = []

            previousTransaction: Optional[Transaction] = None
            consecutiveMergeCount = 0

            for transaction in transactionsOfP:
                self.transactionReadingCount += 1

                # binary search for e in transaction.items between offset and end
                positionE = -1
                low = transaction.offset
                high = len(transaction.items) - 1
                while high >= low:
                    middle = (low + high) >> 1
                    if transaction.items[middle] < e:
                        low = middle + 1
                    elif transaction.items[middle] == e:
                        positionE = middle
                        break
                    else:
                        high = middle - 1

                if positionE > -1:
                    supportPe += len(transaction.originalTransactions) if transaction.originalTransactions else 1

                    if transaction.getLastPosition() == positionE:
                        utilityPe += transaction.utilities[positionE] + transaction.prefixUtility
                        nowEmptyTransactionsPe.append(transaction)
                    else:
                        if (
                            self.activateTransactionMerging
                            and self.MAXIMUM_SIZE_MERGING >= (len(transaction.items) - positionE)
                        ):
                            projected = Transaction.projected(transaction, positionE)
                            utilityPe += projected.prefixUtility

                            if previousTransaction is None:
                                previousTransaction = projected
                            elif self.isEqualTo(projected, previousTransaction):
                                self.mergeCount += 1

                                if consecutiveMergeCount == 0:
                                    itemsCount = len(previousTransaction.items) - previousTransaction.offset
                                    items = previousTransaction.items[previousTransaction.offset :].copy()
                                    utils = previousTransaction.utilities[previousTransaction.offset :].copy()

                                    posPrev = 0
                                    posProj = projected.offset
                                    while posPrev < itemsCount:
                                        utils[posPrev] += projected.utilities[posProj]
                                        posPrev += 1
                                        posProj += 1

                                    sumPrefix = previousTransaction.prefixUtility + projected.prefixUtility
                                    mergeOrig = self.mergeOriginalTransactions(previousTransaction, projected)

                                    previousTransaction = Transaction(
                                        items,
                                        utils,
                                        previousTransaction.transactionUtility + projected.transactionUtility,
                                        mergeOrig,
                                    )
                                    previousTransaction.prefixUtility = sumPrefix
                                    previousTransaction.offset = 0
                                else:
                                    # add utilities
                                    posPrev = 0
                                    posProj = projected.offset
                                    itemsCount = len(previousTransaction.items)
                                    while posPrev < itemsCount:
                                        previousTransaction.utilities[posPrev] += projected.utilities[posProj]
                                        posPrev += 1
                                        posProj += 1

                                    mergeOrig = self.mergeOriginalTransactions(previousTransaction, projected)
                                    previousTransaction.transactionUtility += projected.transactionUtility
                                    previousTransaction.prefixUtility += projected.prefixUtility
                                    previousTransaction.originalTransactions = mergeOrig

                                consecutiveMergeCount += 1
                            else:
                                transactionsPe.append(previousTransaction)
                                previousTransaction = projected
                                consecutiveMergeCount = 0
                        else:
                            projected = Transaction.projected(transaction, positionE)
                            utilityPe += projected.prefixUtility
                            transactionsPe.append(projected)

                    transaction.offset = positionE
                else:
                    transaction.offset = low

            if previousTransaction is not None:
                transactionsPe.append(previousTransaction)

            if self.hasNoBackwardExtension(self.temp, prefixLength, transactionsPe, nowEmptyTransactionsPe, e):
                self.temp[prefixLength] = e
                if supportPe > maxSupport:
                    maxSupport = supportPe

                utilityRemainJump = self.useUtilityBinArraysToCalculateUpperBounds(transactionsPe, j, itemsToKeep)

                shouldJumpToClosure = False
                utilityJumpClosure = utilityPe + utilityRemainJump

                if self.activateClosedPatternJumping:
                    if utilityJumpClosure >= self.minUtil:
                        shouldJumpToClosure = True
                        for i2 in range(j + 1, len(itemsToKeep)):
                            item2 = itemsToKeep[i2]
                            if self.utilityBinArraySupport[item2] != supportPe:
                                shouldJumpToClosure = False
                                break

                if shouldJumpToClosure:
                    newLength = prefixLength + 1
                    for i2 in range(j + 1, len(itemsToKeep)):
                        self.temp[newLength] = itemsToKeep[i2]
                        newLength += 1
                    self.output(newLength - 1, utilityJumpClosure)
                    self.candidateCount += 1
                else:
                    newItemsToKeep: List[int] = []
                    newItemsToExplore: List[int] = []

                    for k in range(j + 1, len(itemsToKeep)):
                        itemk = itemsToKeep[k]
                        if self.utilityBinArraySU[itemk] >= self.minUtil:
                            if self.activateSubtreeUtilityPruning:
                                newItemsToExplore.append(itemk)
                            newItemsToKeep.append(itemk)
                        elif self.utilityBinArrayLU[itemk] >= self.minUtil:
                            newItemsToKeep.append(itemk)

                    if self.activateSubtreeUtilityPruning:
                        recursiveSupport = self.backtrackingEFIM(
                            transactionsPe, newItemsToKeep, newItemsToExplore, prefixLength + 1
                        )
                    else:
                        recursiveSupport = self.backtrackingEFIM(
                            transactionsPe, newItemsToKeep, newItemsToKeep, prefixLength + 1
                        )

                    hasNoForwardExtension = supportPe > recursiveSupport
                    if hasNoForwardExtension and utilityPe >= self.minUtil:
                        self.candidateCount += 1
                        self.output(prefixLength, utilityPe)

        MemoryLogger.getInstance().checkMemory()
        return maxSupport

    @staticmethod
    def mergeOriginalTransactions(t1: Transaction, t2: Transaction) -> List[List[int]]:
        a = t1.originalTransactions if t1.originalTransactions else [t1.items.copy()]
        b = t2.originalTransactions if t2.originalTransactions else [t2.items.copy()]
        return a + b

    def hasNoBackwardExtension(
        self,
        prefix: List[int],
        prefixLength: int,
        transactionsPe: List[Transaction],
        nowEmptyTransactions: List[Transaction],
        e: int,
    ) -> bool:

        if len(transactionsPe) == 0:
            firstTrans = nowEmptyTransactions[0].originalTransactions[0]
        else:
            firstTrans = transactionsPe[0].originalTransactions[0]

        for item in firstTrans:
            if item == e:
                break
            if (
                not self.containsByBinarySearch(prefix, prefixLength, item)
                and self.isItemInAllTransactions(transactionsPe, item)
                and self.isItemInAllTransactions(nowEmptyTransactions, item)
            ):
                return False
        return True

    @staticmethod
    def containsByBinarySearch(items: List[int], itemsLength: int, item: int) -> bool:
        if itemsLength == 0:
            return False
        if item > items[itemsLength - 1]:
            return False

        low, high = 0, itemsLength - 1
        while high >= low:
            mid = (low + high) >> 1
            if items[mid] == item:
                return True
            if items[mid] < item:
                low = mid + 1
            else:
                high = mid - 1
        return False

    @staticmethod
    def isItemInAllTransactions(transactions: List[Transaction], item: int) -> bool:
        for merged in transactions:
            origs = merged.originalTransactions if merged.originalTransactions else [merged.items]
            for trans in origs:
                # binary search in trans
                low, high = 0, len(trans) - 1
                while high >= low:
                    mid = (low + high) >> 1
                    if trans[mid] == item:
                        break
                    if trans[mid] < item:
                        low = mid + 1
                    else:
                        high = mid - 1
                else:
                    return False
        return True

    @staticmethod
    def isEqualTo(t1: Transaction, t2: Transaction) -> bool:
        length1 = len(t1.items) - t1.offset
        length2 = len(t2.items) - t2.offset
        if length1 != length2:
            return False
        p1, p2 = t1.offset, t2.offset
        while p1 < len(t1.items):
            if t1.items[p1] != t2.items[p2]:
                return False
            p1 += 1
            p2 += 1
        return True

    def useUtilityBinArrayToCalculateLocalUtilityFirstTime(self, dataset: Dataset) -> None:
        self.utilityBinArrayLU = [0] * (dataset.getMaxItem() + 1)
        for t in dataset.getTransactions():
            for item in t.getItems():
                self.utilityBinArrayLU[item] += t.transactionUtility

    def useUtilityBinArrayToCalculateSubtreeUtilityFirstTime(self, dataset: Dataset) -> None:
        # utilityBinArraySU already sized to newItemCount+1 (items renamed)
        for t in dataset.getTransactions():
            sumSU = 0
            for i in range(len(t.items) - 1, -1, -1):
                item = t.items[i]
                sumSU += t.utilities[i]
                if item < len(self.utilityBinArraySU):
                    self.utilityBinArraySU[item] += sumSU

    def useUtilityBinArraysToCalculateUpperBounds(
        self, transactionsPe: List[Transaction], j: int, itemsToKeep: List[int]
    ) -> int:
        utilityOfRemainingItemsJumpingClosure = 0

        # reset bins for items > e
        for i in range(j + 1, len(itemsToKeep)):
            item = itemsToKeep[i]
            self.utilityBinArraySU[item] = 0
            self.utilityBinArrayLU[item] = 0
            if self.activateClosedPatternJumping:
                self.utilityBinArraySupport[item] = 0

        for t in transactionsPe:
            self.transactionReadingCount += 1
            sumRemainingUtility = 0

            high = len(itemsToKeep) - 1
            for i in range(len(t.items) - 1, t.offset - 1, -1):
                item = t.items[i]

                # binary search in itemsToKeep
                contains = False
                low = 0
                h = high
                while h >= low:
                    mid = (low + h) >> 1
                    itemMid = itemsToKeep[mid]
                    if itemMid == item:
                        contains = True
                        break
                    if itemMid < item:
                        low = mid + 1
                    else:
                        h = mid - 1

                if contains:
                    sumRemainingUtility += t.utilities[i]
                    self.utilityBinArraySU[item] += sumRemainingUtility + t.prefixUtility
                    self.utilityBinArrayLU[item] += t.transactionUtility + t.prefixUtility
                    if self.activateClosedPatternJumping:
                        sup_add = len(t.originalTransactions) if t.originalTransactions else 1
                        self.utilityBinArraySupport[item] += sup_add
                        utilityOfRemainingItemsJumpingClosure += t.utilities[i]

        return utilityOfRemainingItemsJumpingClosure

    def output(self, tempPosition: int, utility: int) -> None:
        self.patternCount += 1

        if self.writer is None:
            assert self.highUtilityItemsets is not None
            copy_items = [self.newNamesToOldNames[self.temp[i]] for i in range(tempPosition + 1)]
            self.highUtilityItemsets.addItemset(Itemset(copy_items, float(utility)), len(copy_items))
        else:
            out_items = [str(self.newNamesToOldNames[self.temp[i]]) for i in range(tempPosition + 1)]
            line = " ".join(out_items) + "#UTIL: " + str(utility)
            self.writer.write(line + "\n")

    def printStats(self) -> None:
        print("========== EFIM-Closed - STATS ============")
        print(" minUtil = " + str(self.minUtil))
        print(" Closed High utility itemsets count: " + str(self.patternCount))
        print(" Total time ~: " + str(self.endTimestamp - self.startTimestamp) + " ms")
        if self.DEBUG:
            print(" Transaction merge count ~: " + str(self.mergeCount))
            print(" Transaction read count ~: " + str(self.transactionReadingCount))
        print(" Max memory:" + str(MemoryLogger.getInstance().getMaxMemory()))
        print(" Visited node count : " + str(self.candidateCount))
        print("=====================================")

    @staticmethod
    def _transaction_sort_key(t: Transaction):
        # Mimic the Java comparator: compare items backward, then by length.
        # Python key: tuple of reversed items and length to simulate.
        return (list(reversed(t.items)), len(t.items))


# =========================
# Main (like MainTestEFIM_Closed_saveToFile)
# =========================
def file_to_path(filename: str) -> str:
    # Similar spirit to Java getResource: assume file is alongside this script.
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, filename)


def main() -> int:
    parser = argparse.ArgumentParser(description="EFIM-Closed (single-file Python port of SPMF-style code)")
    parser.add_argument("--input", "-i", default="DB_Utility.txt", help="Input utility DB file")
    parser.add_argument("--output", "-o", default="Java//src//output_py.txt", help="Output file")
    parser.add_argument("--minutil", "-m", type=int, default=30, help="Minimum utility threshold")
    parser.add_argument("--merge", action="store_true", help="Activate transaction merging (default: ON)")
    parser.add_argument("--no-merge", action="store_true", help="Deactivate transaction merging")
    parser.add_argument("--subtree", action="store_true", help="Activate subtree utility pruning (default: ON)")
    parser.add_argument("--no-subtree", action="store_true", help="Deactivate subtree utility pruning")
    parser.add_argument("--closed-jump", action="store_true", help="Activate closed pattern jump (default: ON)")
    parser.add_argument("--no-closed-jump", action="store_true", help="Deactivate closed pattern jump")
    parser.add_argument("--max-trans", type=int, default=2**31 - 1, help="Maximum number of transactions to read")
    args = parser.parse_args()

    # defaults like Java call: (true, Integer.MAX_VALUE, true, true)
    activate_merge = True
    if args.no_merge:
        activate_merge = False
    elif args.merge:
        activate_merge = True

    activate_subtree = True
    if args.no_subtree:
        activate_subtree = False
    elif args.subtree:
        activate_subtree = True

    activate_closed_jump = True
    if args.no_closed_jump:
        activate_closed_jump = False
    elif args.closed_jump:
        activate_closed_jump = True

    input_path = args.input
    if not os.path.exists(input_path):
        # try beside script
        maybe = file_to_path(args.input)
        if os.path.exists(maybe):
            input_path = maybe

    algo = AlgoEFIMClosed()
    algo.runAlgorithm(
        args.minutil,
        input_path,
        args.output,
        activate_merge,
        args.max_trans,
        activate_subtree,
        activate_closed_jump,
    )
    algo.printStats()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
