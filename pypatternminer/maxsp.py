#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MaxSP (Maximal Sequential Pattern Mining)
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set


# -----------------------------
# MemoryLogger (best-effort)
# -----------------------------
class MemoryLogger:
    _instance = None

    def __init__(self) -> None:
        self._max_mem_mb = 0.0

    @classmethod
    def getInstance(cls) -> "MemoryLogger":
        if cls._instance is None:
            cls._instance = MemoryLogger()
        return cls._instance

    def reset(self) -> None:
        self._max_mem_mb = 0.0
        self.checkMemory()

    def checkMemory(self) -> None:
        mem_mb = 0.0
        try:
            import resource  # unix/mac
            rusage = resource.getrusage(resource.RUSAGE_SELF)
            rss = float(rusage.ru_maxrss)
            # heuristic: macOS bytes, linux KB
            if rss > 10_000_000:
                mem_mb = rss / (1024.0 * 1024.0)
            else:
                mem_mb = rss / 1024.0
        except Exception:
            mem_mb = 0.0

        if mem_mb > self._max_mem_mb:
            self._max_mem_mb = mem_mb

    def getMaxMemory(self) -> float:
        return self._max_mem_mb


# -----------------------------
# Position
# -----------------------------
@dataclass(frozen=True)
class Position:
    itemset: int
    item: int

    def __str__(self) -> str:
        return f"({self.itemset},{self.item})"


# -----------------------------
# Itemset (matches your Java)
# -----------------------------
class Itemset:
    def __init__(self, item: Optional[int] = None) -> None:
        self._items: List[int] = []
        if item is not None:
            self.addItem(item)

    def addItem(self, value: int) -> None:
        # IMPORTANT: Java does NOT sort or deduplicate here
        self._items.append(int(value))

    def getItems(self) -> List[int]:
        return self._items

    def get(self, index: int) -> int:
        return self._items[index]

    def size(self) -> int:
        return len(self._items)

    def cloneItemSet(self) -> "Itemset":
        it = Itemset()
        it._items.extend(self._items)
        return it

    def __iter__(self):
        return iter(self._items)


# -----------------------------
# Sequence (matches your Java)
# -----------------------------
class Sequence:
    def __init__(self, sid: int) -> None:
        self._id = int(sid)
        self._itemsets: List[List[int]] = []

    def addItemset(self, itemset: List[int]) -> None:
        self._itemsets.append(list(itemset))

    def getId(self) -> int:
        return self._id

    def getItemsets(self) -> List[List[int]]:
        return self._itemsets

    def get(self, index: int) -> List[int]:
        return self._itemsets[index]

    def size(self) -> int:
        return len(self._itemsets)

    def cloneItemsetMinusItems(
        self,
        itemset: List[int],
        mapSequenceID: Dict[int, Set[int]],
        minSupportAbsolute: int,
    ) -> List[int]:
        newItemset: List[int] = []
        for item in itemset:
            sidset = mapSequenceID.get(item)
            if sidset is not None and len(sidset) >= minSupportAbsolute:
                newItemset.append(item)
        return newItemset

    def cloneSequenceMinusItems(
        self,
        mapSequenceID: Dict[int, Set[int]],
        minSupportAbsolute: int,
    ) -> "Sequence":
        seq = Sequence(self.getId())
        for itemset in self._itemsets:
            newItemset = self.cloneItemsetMinusItems(itemset, mapSequenceID, minSupportAbsolute)
            if len(newItemset) != 0:
                seq.addItemset(newItemset)
        return seq


# -----------------------------
# SequenceDatabase (matches your Java)
# -----------------------------
class SequenceDatabase:
    def __init__(self) -> None:
        self._sequences: List[Sequence] = []

    def loadFile(self, path: str) -> None:
        self._sequences.clear()
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                ch0 = line[0]
                if ch0 in ("#", "%", "@"):
                    continue
                tokens = line.split(" ")
                self._addSequence(tokens)

    def _addSequence(self, tokens: List[str]) -> None:
        # Java: new Sequence(sequences.size())
        seq = Sequence(len(self._sequences))
        itemset: List[int] = []
        for tok in tokens:
            if not tok:
                continue
            if tok[0] == "<":
                continue
            if tok == "-1":
                # IMPORTANT: Java adds itemset even if empty
                seq.addItemset(itemset)
                itemset = []
            elif tok == "-2":
                self._sequences.append(seq)
            else:
                itemset.append(int(tok))

    def size(self) -> int:
        return len(self._sequences)

    def getSequences(self) -> List[Sequence]:
        return self._sequences


# -----------------------------
# Pair and PairBIDE (matches your Java behavior)
# -----------------------------
class Pair:
    __slots__ = ("item", "postfix", "_sequenceIDs")

    def __init__(self, postfix: bool, item: int) -> None:
        self.postfix = bool(postfix)
        self.item = int(item)
        self._sequenceIDs: Set[int] = set()

    def isPostfix(self) -> bool:
        return self.postfix

    def getItem(self) -> int:
        return self.item

    def getCount(self) -> int:
        return len(self._sequenceIDs)

    def getSequenceIDs(self) -> Set[int]:
        return self._sequenceIDs

    def __hash__(self) -> int:
        return hash((self.postfix, self.item))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Pair):
            return False
        return (self.postfix, self.item) == (other.postfix, other.item)


class PairBIDE(Pair):
    __slots__ = ("prefix",)

    def __init__(self, prefix: bool, postfix: bool, item: int) -> None:
        super().__init__(postfix, item)
        self.prefix = bool(prefix)

    def isPrefix(self) -> bool:
        return self.prefix

    def __hash__(self) -> int:
        return hash((self.postfix, self.prefix, self.item))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PairBIDE):
            return False
        return (self.postfix, self.prefix, self.item) == (other.postfix, other.prefix, other.item)


# -----------------------------
# SequentialPattern (matches your Java)
# -----------------------------
class SequentialPattern:
    def __init__(self) -> None:
        self._itemsets: List[Itemset] = []
        self._sequenceIDs: Optional[Set[int]] = None
        self._itemCountCache: int = -1

    def setSequenceIDs(self, sids: Set[int]) -> None:
        self._sequenceIDs = sids

    def getSequenceIDs(self) -> Set[int]:
        return self._sequenceIDs if self._sequenceIDs is not None else set()

    def addItemset(self, itemset: Itemset) -> None:
        self._itemsets.append(itemset)
        self._itemCountCache = -1

    def cloneSequence(self) -> "SequentialPattern":
        # IMPORTANT: Java cloneSequence does NOT copy sequencesIds
        seq = SequentialPattern()
        for it in self._itemsets:
            seq.addItemset(it.cloneItemSet())
        return seq

    def getItemsets(self) -> List[Itemset]:
        return self._itemsets

    def size(self) -> int:
        return len(self._itemsets)

    def get(self, index: int) -> Itemset:
        return self._itemsets[index]

    def getIthItem(self, i: int) -> Optional[int]:
        for itset in self._itemsets:
            if i < itset.size():
                return itset.get(i)
            i -= itset.size()
        return None

    def getItemOccurencesTotalCount(self) -> int:
        if self._itemCountCache == -1:
            self._itemCountCache = sum(it.size() for it in self._itemsets)
        return self._itemCountCache

    def getAbsoluteSupport(self) -> int:
        return len(self.getSequenceIDs())


# -----------------------------
# PseudoSequence (matches your Java)
# -----------------------------
class PseudoSequence:
    def __init__(
        self,
        sequence: Optional[Sequence] = None,
        indexItemset: int = 0,
        indexItem: int = 0,
        fromPseudo: Optional["PseudoSequence"] = None,
    ) -> None:
        if fromPseudo is not None:
            self.sequence: Sequence = fromPseudo.sequence
            self.firstItemset = indexItemset + fromPseudo.firstItemset
            if self.firstItemset == fromPseudo.firstItemset:
                self.firstItem = indexItem + fromPseudo.firstItem
            else:
                self.firstItem = indexItem
        else:
            if sequence is None:
                raise ValueError("PseudoSequence needs sequence or fromPseudo")
            self.sequence = sequence
            self.firstItemset = indexItemset
            self.firstItem = indexItem

    def size(self) -> int:
        size = self.sequence.size() - self.firstItemset
        if size == 1 and len(self.sequence.getItemsets()[self.firstItemset]) == 0:
            return 0
        return size

    def isFirstItemset(self, index: int) -> bool:
        return index == 0

    def isLastItemset(self, index: int) -> bool:
        return (index + self.firstItemset) == (len(self.sequence.getItemsets()) - 1)

    def isPostfix(self, indexItemset: int) -> bool:
        return indexItemset == 0 and self.firstItem != 0

    def getSizeOfItemsetAt(self, index: int) -> int:
        size = len(self.sequence.getItemsets()[index + self.firstItemset])
        if self.isFirstItemset(index):
            size -= self.firstItem
        return size

    def getItemset(self, index: int) -> List[int]:
        return self.sequence.get(index + self.firstItemset)

    def getItemAtInItemsetAt(self, indexItem: int, indexItemset: int) -> int:
        if self.isFirstItemset(indexItemset):
            return self.getItemset(indexItemset)[indexItem + self.firstItem]
        return self.getItemset(indexItemset)[indexItem]

    def getId(self) -> int:
        return self.sequence.getId()

    def indexOf(self, sizeOfItemsetAti: int, indexItemset: int, idItem: int) -> int:
        # IMPORTANT: match your Java (uses continue, not break)
        for i in range(sizeOfItemsetAti):
            v = self.getItemAtInItemsetAt(i, indexItemset)
            if v == idItem:
                return i
            elif v > idItem:
                continue
        return -1


# -----------------------------
# PseudoSequenceBIDE (from your Java)
# -----------------------------
class PseudoSequenceBIDE(PseudoSequence):
    class PseudoSequencePair:
        def __init__(self, pseudoSequence: "PseudoSequenceBIDE", lst: List[Position]) -> None:
            self.pseudoSequence = pseudoSequence
            self.list = lst

    def __init__(
        self,
        sequence: Optional[Sequence] = None,
        indexItemset: int = 0,
        indexItem: int = 0,
        fromPseudoBIDE: Optional["PseudoSequenceBIDE"] = None,
        lastItemset: Optional[int] = None,
        lastItem: Optional[int] = None,
    ) -> None:
        if fromPseudoBIDE is not None:
            self.sequence = fromPseudoBIDE.sequence
            self.firstItemset = indexItemset + fromPseudoBIDE.firstItemset
            if self.firstItemset == fromPseudoBIDE.firstItemset:
                self.firstItem = indexItem + fromPseudoBIDE.firstItem
            else:
                self.firstItem = indexItem

            if lastItemset is None or lastItem is None:
                self.lastItemset = fromPseudoBIDE.lastItemset
                self.lastItem = fromPseudoBIDE.lastItem
            else:
                self.lastItemset = lastItemset
                self.lastItem = lastItem
        else:
            if sequence is None:
                raise ValueError("PseudoSequenceBIDE needs sequence or fromPseudoBIDE")
            self.sequence = sequence
            self.firstItemset = indexItemset
            self.firstItem = indexItem
            self.lastItemset = sequence.size() - 1
            self.lastItem = len(sequence.getItemsets()[self.lastItemset]) - 1

    def size(self) -> int:
        size = self.sequence.size() - self.firstItemset - ((self.sequence.size() - 1) - self.lastItemset)
        if size == 1 and len(self.sequence.getItemsets()[self.firstItemset]) == 0:
            return 0
        return size

    def isLastItemset(self, index: int) -> bool:
        return (index + self.firstItemset) == self.lastItemset

    def getSizeOfItemsetAt(self, index: int) -> int:
        size = len(self.sequence.getItemsets()[index + self.firstItemset])
        if self.isLastItemset(index):
            size = 1 + self.lastItem
        if self.isFirstItemset(index):
            size -= self.firstItem
        return size

    def isCutAtRight(self, index: int) -> bool:
        if not self.isLastItemset(index):
            return False
        return (len(self.sequence.getItemsets()[index + self.firstItemset]) - 1) != self.lastItem

    # ---- helper: prefix item count / ith item (same as Java) ----
    @staticmethod
    def _getItemOccurencesTotalCount(prefix: List[Itemset]) -> int:
        return sum(it.size() for it in prefix)

    @staticmethod
    def _getIthItem(prefix: List[Itemset], i: int) -> Optional[int]:
        for it in prefix:
            if i < it.size():
                return it.get(i)
            i -= it.size()
        return None

    # ---- NEW instance finders from your Java ----
    def getLastInstanceOfPrefixSequenceNEW(self, prefix: List[Itemset], i: int) -> Optional["PseudoSequenceBIDE.PseudoSequencePair"]:
        remaining = i
        positions: List[Position] = []
        prefix_itemset_pos = len(prefix) - 1

        for j in range(self.size() - 1, -1, -1):
            item_in_prefix_pos = prefix[prefix_itemset_pos].size() - 1
            allMatched = False
            searched = prefix[prefix_itemset_pos].get(item_in_prefix_pos)
            temp: List[Position] = []

            for k in range(self.getSizeOfItemsetAt(j) - 1, -1, -1):
                cur = self.getItemAtInItemsetAt(k, j)
                if cur == searched:
                    temp.append(Position(j, k))
                    item_in_prefix_pos -= 1
                    if item_in_prefix_pos == -1 or len(temp) == remaining:
                        allMatched = True
                        break
                    searched = prefix[prefix_itemset_pos].get(item_in_prefix_pos)
                elif cur < searched:
                    break

            if allMatched:
                remaining -= len(temp)
                positions.extend(temp)
                prefix_itemset_pos -= 1
                if prefix_itemset_pos == -1:
                    return PseudoSequenceBIDE.PseudoSequencePair(self, positions)
        return None

    def getFirstInstanceOfPrefixSequenceNEW(self, prefix: List[Itemset], i: int) -> Optional["PseudoSequenceBIDE.PseudoSequencePair"]:
        remaining = i
        positions: List[Position] = []
        prefix_itemset_pos = 0

        for j in range(0, self.size()):
            item_in_prefix_pos = 0
            allMatched = False
            searched = prefix[prefix_itemset_pos].get(item_in_prefix_pos)
            temp: List[Position] = []

            k = 0
            while k < self.getSizeOfItemsetAt(j) and not allMatched:
                cur = self.getItemAtInItemsetAt(k, j)
                if cur == searched:
                    temp.append(Position(j, k))
                    item_in_prefix_pos += 1
                    if item_in_prefix_pos == prefix[prefix_itemset_pos].size() or len(temp) == remaining:
                        allMatched = True
                        break
                    searched = prefix[prefix_itemset_pos].get(item_in_prefix_pos)
                elif cur > searched:
                    break
                k += 1

            if allMatched:
                remaining -= len(temp)
                positions.extend(temp)
                prefix_itemset_pos += 1
                if prefix_itemset_pos == len(prefix):
                    cutpos = positions[i - 1]
                    newSeq = PseudoSequenceBIDE(
                        fromPseudoBIDE=self,
                        indexItemset=self.firstItemset,
                        indexItem=self.firstItem,
                        lastItemset=cutpos.itemset,
                        lastItem=cutpos.item,
                    )
                    return PseudoSequenceBIDE.PseudoSequencePair(newSeq, positions)
        return None

    def getIthLastInLastApearanceWithRespectToPrefix(
        self,
        prefix: List[Itemset],
        i: int,
        lastInstancePair: Optional["PseudoSequenceBIDE.PseudoSequencePair"],
    ) -> Optional[Position]:
        iditem = self._getIthItem(prefix, i)
        if iditem is None or lastInstancePair is None:
            return None

        if i == self._getItemOccurencesTotalCount(prefix) - 1:
            for j in range(lastInstancePair.pseudoSequence.size() - 1, -1, -1):
                sizeJ = len(lastInstancePair.pseudoSequence.getItemset(j))
                for k in range(sizeJ - 1, -1, -1):
                    item = lastInstancePair.pseudoSequence.getItemAtInItemsetAt(k, j)
                    if item == iditem:
                        return Position(j, k)
                    elif item < iditem:
                        break
        else:
            LLiplus1 = self.getIthLastInLastApearanceWithRespectToPrefix(prefix, i + 1, lastInstancePair)
            if LLiplus1 is None:
                return None
            for j in range(LLiplus1.itemset, -1, -1):
                sizeJ = len(lastInstancePair.pseudoSequence.getItemset(j))
                for k in range(sizeJ - 1, -1, -1):
                    if j == LLiplus1.itemset and k >= LLiplus1.item:
                        continue
                    if lastInstancePair.pseudoSequence.getItemAtInItemsetAt(k, j) == iditem:
                        return Position(j, k)
        return None

    def trimBeginingAndEnd(self, positionStart: Optional[Position], positionEnd: Optional[Position]) -> Optional["PseudoSequenceBIDE"]:
        itemsetStart = 0
        itemStart = 0
        itemsetEnd = self.lastItemset
        itemEnd = self.lastItem

        if positionStart is not None:
            itemsetStart = positionStart.itemset
            itemStart = positionStart.item + 1
            if itemStart == self.getSizeOfItemsetAt(itemsetStart):
                itemsetStart += 1
                itemStart = 0
            if itemsetStart == self.size():
                return None

        if positionEnd is not None:
            itemEnd = positionEnd.item - 1
            itemsetEnd = positionEnd.itemset
            if itemEnd < 0:
                itemsetEnd = positionEnd.itemset - 1
                if itemsetEnd < itemsetStart:
                    return None
                itemEnd = self.getSizeOfItemsetAt(itemsetEnd) - 1

        if itemsetEnd == itemsetStart and itemEnd < itemStart:
            return None

        return PseudoSequenceBIDE(
            fromPseudoBIDE=self,
            indexItemset=itemsetStart,
            indexItem=itemStart,
            lastItemset=itemsetEnd,
            lastItem=itemEnd,
        )

    def getIthMaximumPeriodOfAPrefix(self, prefix: List[Itemset], i: int) -> Optional["PseudoSequenceBIDE"]:
        lastInstancePair = self.getLastInstanceOfPrefixSequenceNEW(prefix, self._getItemOccurencesTotalCount(prefix))
        ithlastlast = self.getIthLastInLastApearanceWithRespectToPrefix(prefix, i, lastInstancePair)
        if ithlastlast is None:
            return None

        if i == 0:
            return self.trimBeginingAndEnd(None, ithlastlast)

        firstInstance = self.getFirstInstanceOfPrefixSequenceNEW(prefix, i)

        # Bugfix from your Java
        if firstInstance is None or not firstInstance.list:
            return self.trimBeginingAndEnd(None, ithlastlast)

        lastOfFirstInstance = firstInstance.list[i - 1]
        return self.trimBeginingAndEnd(lastOfFirstInstance, ithlastlast)


# -----------------------------
# AlgoMaxSP (matches your Java)
# -----------------------------
class AlgoMaxSP:
    def __init__(self) -> None:
        self.startTime = 0.0
        self.endTime = 0.0
        self.patternCount = 0
        self.minsuppAbsolute = 1
        self.showSequenceIdentifiers = False

        self.writer = None  # file handle
        self.initialDatabase: Optional[Dict[int, PseudoSequenceBIDE]] = None

    def setShowSequenceIdentifiers(self, show: bool) -> None:
        self.showSequenceIdentifiers = bool(show)

    def runAlgorithm(self, database: SequenceDatabase, outputPath: str, minsup: int) -> None:
        self.minsuppAbsolute = int(minsup) if minsup > 0 else 1
        self.patternCount = 0
        MemoryLogger.getInstance().reset()
        self.startTime = time.time()
        self._maxSP(database, outputPath)
        self.endTime = time.time()
        if self.writer is not None:
            self.writer.close()
            self.writer = None

    def _maxSP(self, database: SequenceDatabase, outputFilePath: str) -> None:
        self.writer = open(outputFilePath, "w", encoding="utf-8")

        mapSequenceID = self._findSequencesContainingItems(database)

        self.initialDatabase = {}
        for sequence in database.getSequences():
            optimized = sequence.cloneSequenceMinusItems(mapSequenceID, self.minsuppAbsolute)
            if optimized.size() != 0:
                self.initialDatabase[sequence.getId()] = PseudoSequenceBIDE(sequence=optimized, indexItemset=0, indexItem=0)

        for item, sidset in mapSequenceID.items():
            if len(sidset) < self.minsuppAbsolute:
                continue

            projected = self._buildProjectedContextSingleItem(item, self.initialDatabase, False, sidset)

            prefix = SequentialPattern()
            prefix.addItemset(Itemset(item))
            prefix.setSequenceIDs(sidset)

            if len(projected) >= self.minsuppAbsolute:
                successorSupport = self._recursion(prefix, projected)
                if successorSupport < self.minsuppAbsolute:
                    if not self._checkBackwardExtension(prefix, sidset):
                        self._savePattern(prefix)
            else:
                if not self._checkBackwardExtension(prefix, sidset):
                    self._savePattern(prefix)

        MemoryLogger.getInstance().checkMemory()

    def _findSequencesContainingItems(self, database: SequenceDatabase) -> Dict[int, Set[int]]:
        m: Dict[int, Set[int]] = {}
        for sequence in database.getSequences():
            for itemset in sequence.getItemsets():
                for item in itemset:
                    m.setdefault(item, set()).add(sequence.getId())
        return m

    def _buildProjectedContextSingleItem(
        self,
        item: int,
        initialDatabase2: Dict[int, PseudoSequenceBIDE],
        inSuffix: bool,
        sidset: Set[int],
    ) -> List[PseudoSequenceBIDE]:
        out: List[PseudoSequenceBIDE] = []
        for sid in sidset:
            seq = initialDatabase2.get(sid)
            if seq is None:
                continue
            for i in range(seq.size()):
                size_i = seq.getSizeOfItemsetAt(i)
                idx = seq.indexOf(size_i, i, item)
                if idx != -1 and seq.isPostfix(i) == inSuffix:
                    if idx != size_i - 1:
                        out.append(PseudoSequenceBIDE(fromPseudoBIDE=seq, indexItemset=i, indexItem=idx + 1))
                    elif i != seq.size() - 1:
                        out.append(PseudoSequenceBIDE(fromPseudoBIDE=seq, indexItemset=i + 1, indexItem=0))
        return out

    def _buildProjectedDatabase(
        self,
        item: int,
        database: List[PseudoSequenceBIDE],
        inSuffix: bool,
        sidset: Set[int],
    ) -> List[PseudoSequenceBIDE]:
        out: List[PseudoSequenceBIDE] = []
        for seq in database:
            if seq.getId() not in sidset:
                continue
            for i in range(seq.size()):
                size_i = seq.getSizeOfItemsetAt(i)
                idx = seq.indexOf(size_i, i, item)
                if idx != -1 and seq.isPostfix(i) == inSuffix:
                    if idx != size_i - 1:
                        out.append(PseudoSequenceBIDE(fromPseudoBIDE=seq, indexItemset=i, indexItem=idx + 1))
                    elif i != seq.size() - 1:
                        out.append(PseudoSequenceBIDE(fromPseudoBIDE=seq, indexItemset=i + 1, indexItem=0))
        return out

    def _appendItemToSequence(self, prefix: SequentialPattern, item: int) -> SequentialPattern:
        newPrefix = prefix.cloneSequence()
        newPrefix.addItemset(Itemset(item))
        return newPrefix

    def _appendItemToPrefixOfSequence(self, prefix: SequentialPattern, item: int) -> SequentialPattern:
        newPrefix = prefix.cloneSequence()
        last = newPrefix.get(newPrefix.size() - 1)
        last.addItem(item)
        return newPrefix

    def _findAllFrequentPairs(self, sequences: List[PseudoSequenceBIDE]) -> Set[PairBIDE]:
        mp: Dict[PairBIDE, PairBIDE] = {}
        for seq in sequences:
            for i in range(seq.size()):
                for j in range(seq.getSizeOfItemsetAt(i)):
                    item = seq.getItemAtInItemsetAt(j, i)
                    pair = PairBIDE(seq.isCutAtRight(i), seq.isPostfix(i), item)
                    self._addPairWithoutCheck(mp, seq.getId(), pair)
        MemoryLogger.getInstance().checkMemory()
        return set(mp.keys())

    def _addPairWithoutCheck(self, mp: Dict[PairBIDE, PairBIDE], sid: int, pair: PairBIDE) -> None:
        old = mp.get(pair)
        if old is None:
            mp[pair] = pair
            pair.getSequenceIDs().add(sid)
        else:
            old.getSequenceIDs().add(sid)

    def _addPair(self, mp: Dict[PairBIDE, PairBIDE], sid: int, pair: PairBIDE) -> bool:
        old = mp.get(pair)
        if old is None:
            mp[pair] = pair
        else:
            pair = old
        pair.getSequenceIDs().add(sid)
        return pair.getCount() >= self.minsuppAbsolute

    def _findAllFrequentPairsForBackwardExtensionCheck(
        self,
        seqProcessedCount: int,
        maximumPeriod: PseudoSequenceBIDE,
        mapPairs: Dict[PairBIDE, PairBIDE],
        itemI: int,
        itemIm1: Optional[int],
    ) -> bool:
        for i in range(maximumPeriod.size()):
            size_i = maximumPeriod.getSizeOfItemsetAt(i)

            sawI = False
            sawIm1 = False

            for j in range(size_i):
                it = maximumPeriod.getItemAtInItemsetAt(j, i)
                if it == itemI:
                    sawI = True
                elif it > itemI:
                    break

            for j in range(size_i):
                it = maximumPeriod.getItemAtInItemsetAt(j, i)
                if itemIm1 is not None and it == itemIm1:
                    sawIm1 = True

                isPrefix = maximumPeriod.isCutAtRight(i)
                isPostfix = maximumPeriod.isPostfix(i)

                pair = PairBIDE(isPrefix, isPostfix, it)

                if seqProcessedCount >= self.minsuppAbsolute:
                    if self._addPair(mapPairs, maximumPeriod.getId(), pair):
                        return True

                    if sawIm1:
                        pair2 = PairBIDE(isPrefix, not isPostfix, it)
                        if self._addPair(mapPairs, maximumPeriod.getId(), pair2):
                            return True

                    if sawI:
                        pair2 = PairBIDE(not isPrefix, isPostfix, it)
                        if self._addPair(mapPairs, maximumPeriod.getId(), pair2):
                            return True
                else:
                    self._addPairWithoutCheck(mapPairs, maximumPeriod.getId(), pair)
                    if sawIm1:
                        pair2 = PairBIDE(isPrefix, not isPostfix, it)
                        self._addPairWithoutCheck(mapPairs, maximumPeriod.getId(), pair2)
                    if sawI:
                        pair2 = PairBIDE(not isPrefix, isPostfix, it)
                        self._addPairWithoutCheck(mapPairs, maximumPeriod.getId(), pair2)

        return False

    def _checkBackwardExtension(self, prefix: SequentialPattern, sidset: Set[int]) -> bool:
        if self.initialDatabase is None:
            return False

        totalOcc = prefix.getItemOccurencesTotalCount()
        sid_list = list(sidset)

        for i in range(totalOcc):
            alreadyVisited: Set[int] = set()

            itemI = prefix.getIthItem(i)
            itemIm1 = prefix.getIthItem(i - 1) if i > 0 else None
            if itemI is None:
                continue

            mapPairs: Dict[PairBIDE, PairBIDE] = {}
            highestSupportUntilNow = -1

            for sequenceID in sid_list:
                if highestSupportUntilNow != -1 and highestSupportUntilNow + (len(sidset) - len(alreadyVisited)) < self.minsuppAbsolute:
                    break

                alreadyVisited.add(sequenceID)
                sequence = self.initialDatabase.get(sequenceID)
                if sequence is None:
                    continue

                period = sequence.getIthMaximumPeriodOfAPrefix(prefix.getItemsets(), i)
                if period is not None:
                    hasBack = self._findAllFrequentPairsForBackwardExtensionCheck(
                        len(alreadyVisited),
                        period,
                        mapPairs,
                        itemI,
                        itemIm1,
                    )
                    if hasBack:
                        return True

                    if (len(sidset) - len(alreadyVisited)) < self.minsuppAbsolute:
                        for p in mapPairs.values():
                            sup = p.getCount()
                            if sup > highestSupportUntilNow:
                                highestSupportUntilNow = sup

        return False

    def _recursion(self, prefix: SequentialPattern, contexte: List[PseudoSequenceBIDE]) -> int:
        pairs = self._findAllFrequentPairs(contexte)
        maxSupport = 0

        for pair in pairs:
            if pair.getCount() >= self.minsuppAbsolute:
                if pair.isPostfix():
                    newPrefix = self._appendItemToPrefixOfSequence(prefix, pair.getItem())
                else:
                    newPrefix = self._appendItemToSequence(prefix, pair.getItem())

                projected = self._buildProjectedDatabase(pair.getItem(), contexte, pair.isPostfix(), pair.getSequenceIDs())
                newPrefix.setSequenceIDs(pair.getSequenceIDs())

                if len(projected) >= self.minsuppAbsolute:
                    maxSucc = self._recursion(newPrefix, projected)
                    if self.minsuppAbsolute > maxSucc:
                        if not self._checkBackwardExtension(newPrefix, pair.getSequenceIDs()):
                            self._savePattern(newPrefix)
                else:
                    if not self._checkBackwardExtension(newPrefix, pair.getSequenceIDs()):
                        self._savePattern(newPrefix)

                if newPrefix.getAbsoluteSupport() > maxSupport:
                    maxSupport = newPrefix.getAbsoluteSupport()

        return maxSupport

    def _savePattern(self, prefix: SequentialPattern) -> None:
        self.patternCount += 1
        assert self.writer is not None

        parts: List[str] = []
        for itemset in prefix.getItemsets():
            for item in itemset.getItems():
                parts.append(str(item))
                parts.append(" ")
            parts.append("-1 ")
        parts.append(" #SUP: ")
        parts.append(str(len(prefix.getSequenceIDs())))
        if self.showSequenceIdentifiers:
            parts.append(" #SID: ")
            for sid in prefix.getSequenceIDs():
                parts.append(str(sid))
                parts.append(" ")

        self.writer.write("".join(parts) + "\n")

    def printStatistics(self, size: int) -> None:
        ms = int((self.endTime - self.startTime) * 1000.0)
        print("=============  Algorithm MaxSP - STATISTICS =============")
        print(f" Total time ~ {ms} ms")
        print(f" Maximal sequential pattern count : {self.patternCount}")
        print(f" Max memory (mb):{MemoryLogger.getInstance().getMaxMemory()}")
        print("===================================================")


# ----------------------------------------------------------------------
# Main (vibe like MainTestLAPIN_saveToFile.java)
# ----------------------------------------------------------------------

def main() -> None:

    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(script_dir, "contextPrefixSpan.txt")
    output_path = os.path.join(script_dir, "output_py.txt")
    
    db = SequenceDatabase()
    db.loadFile(input_path)

    algo = AlgoMaxSP()
    algo.setShowSequenceIdentifiers(True)  # False if you don't want #SID

    minsup_absolute = 2  # change as needed (integer)
    algo.runAlgorithm(db, str(output_path), minsup_absolute)

    algo.printStatistics(db.size())


if __name__ == "__main__":
    main()
