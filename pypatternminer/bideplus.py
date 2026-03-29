#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BIDE+ - BI-Directional Extension based frequent closed sequence mining algorithm
"""

from __future__ import annotations
from typing import Dict, List, Optional, Set, Any, Tuple
import argparse, os


# ----------------------------------------------------------------------
# Utilities: Java-like String.hashCode() for stable Pair hashing
# ----------------------------------------------------------------------

def _java_string_hashcode(s: str) -> int:
    """Replicates Java's String.hashCode() with 32-bit signed overflow."""
    h = 0
    for ch in s:
        h = (31 * h + ord(ch)) & 0xFFFFFFFF
    # convert to signed 32-bit
    if h & 0x80000000:
        h = -((~h + 1) & 0xFFFFFFFF)
    return h


# ----------------------------------------------------------------------
# MemoryLogger
# ----------------------------------------------------------------------

class MemoryLogger:
    """
    Converted from MemoryLogger.java (singleton).
    Tracks max memory usage (MB). Python uses tracemalloc for an approximate peak.
    """
    _instance: Optional["MemoryLogger"] = None

    def __init__(self) -> None:
        self.maxMemory: float = 0.0

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
        try:
            import tracemalloc
            if not tracemalloc.is_tracing():
                tracemalloc.start()
            current, _peak = tracemalloc.get_traced_memory()
            currentMB = current / 1024.0 / 1024.0
            if currentMB > self.maxMemory:
                self.maxMemory = currentMB
            return currentMB
        except Exception:
            return self.maxMemory


# ----------------------------------------------------------------------
# SequenceDatabase
# ----------------------------------------------------------------------

class SequenceDatabase:
    """
    Converted from SequenceDatabase.java.

    Stores sequences as list of int arrays (Python list[int]).
    Lines starting with #, %, @ or empty are ignored.
    """
    def __init__(self) -> None:
        self.sequences: List[Optional[List[int]]] = []
        self.itemOccurrenceCount: int = 0

    def loadFile(self, path: str) -> None:
        self.itemOccurrenceCount = 0
        self.sequences = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                thisLine = line.strip()
                if not thisLine:
                    continue
                if thisLine[0] in ("#", "%", "@"):
                    continue
                tokens = thisLine.split()
                seq = [int(tok) for tok in tokens]
                self.sequences.append(seq)

    def print(self) -> None:
        print("============  SEQUENCE DATABASE ==========")
        print(str(self))

    def printDatabaseStats(self) -> None:
        print("============  STATS ==========")
        print(f"Number of sequences : {len(self.sequences)}")
        meansize = (float(self.itemOccurrenceCount) / float(len(self.sequences))) if self.sequences else 0.0
        print("mean size" + str(meansize))

    def __str__(self) -> str:
        lines: List[str] = []
        self.itemOccurrenceCount = 0
        for i, seq in enumerate(self.sequences):
            if seq is None:
                lines.append(f"{i}:  <null>")
                continue
            out: List[str] = [f"{i}:  "]
            startingANewItemset = True
            for token in seq:
                if token >= 0:
                    if startingANewItemset:
                        startingANewItemset = False
                        out.append("(")
                    else:
                        out.append(" ")
                    out.append(str(token))
                    self.itemOccurrenceCount += 1
                elif token == -1:
                    out.append(")")
                    startingANewItemset = True
                elif token == -2:
                    break
            lines.append("".join(out))
        return "\n".join(lines)

    def size(self) -> int:
        return len(self.sequences)

    def getSequences(self) -> List[Optional[List[int]]]:
        return self.sequences


# ----------------------------------------------------------------------
# PseudoSequence
# ----------------------------------------------------------------------

class PseudoSequence:
    """
    Converted from PseudoSequence.java.
    References an original sequence and a starting index.
    """
    def __init__(self, sequenceID: int, indexFirstItem: int) -> None:
        self.sequenceID: int = sequenceID
        self.indexFirstItem: int = indexFirstItem

    def getOriginalSequenceID(self) -> int:
        return self.sequenceID

    def getIndexFirstItem(self) -> int:
        return self.indexFirstItem

    def getSequenceID(self) -> int:
        return self.sequenceID


# ----------------------------------------------------------------------
# Pair
# ----------------------------------------------------------------------

class Pair:
    """
    Converted from Pair.java.

    Equality and hashing depend ONLY on item (like Java).
    Java hashCode: (item + "").hashCode()  => we replicate using Java String.hashCode.
    """
    def __init__(self, item: int) -> None:
        self.item: int = int(item)
        self.pseudoSequences: List[PseudoSequence] = []

    def getItem(self) -> int:
        return self.item

    def getCount(self) -> int:
        return len(self.pseudoSequences)

    def getPseudoSequences(self) -> List[PseudoSequence]:
        return self.pseudoSequences

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Pair) and self.item == other.item

    def __hash__(self) -> int:
        return _java_string_hashcode(str(self.item))


# ----------------------------------------------------------------------
# Itemset
# ----------------------------------------------------------------------

class Itemset:
    """
    Converted from Itemset.java.

    Note: Java code does NOT enforce ordering or uniqueness in addItem().
    So this Python version keeps the same behavior.
    """
    def __init__(self, item: Optional[int] = None) -> None:
        self.items: List[int] = []
        if item is not None:
            self.addItem(item)

    def addItem(self, value: int) -> None:
        self.items.append(int(value))

    def getItems(self) -> List[int]:
        return self.items

    def get(self, index: int) -> int:
        return self.items[index]

    def __str__(self) -> str:
        return "".join(f"{it} " for it in self.items)

    def size(self) -> int:
        return len(self.items)

    def cloneItemSetMinusItems(self, mapSequenceID: Dict[int, Set[int]], relativeMinsup: float) -> "Itemset":
        new_itemset = Itemset()
        for item in self.items:
            s = mapSequenceID.get(item)
            if s is not None and len(s) >= relativeMinsup:
                new_itemset.addItem(item)
        return new_itemset

    def cloneItemSet(self) -> "Itemset":
        new_itemset = Itemset()
        new_itemset.items.extend(self.items)
        return new_itemset

    def containsAll(self, itemset2: "Itemset") -> bool:
        i = 0
        for item in itemset2.getItems():
            found = False
            while (not found) and i < self.size():
                if self.get(i) == item:
                    found = True
                elif self.get(i) > item:
                    return False
                i += 1
            if not found:
                return False
        return True


# ----------------------------------------------------------------------
# SequentialPattern
# ----------------------------------------------------------------------

class SequentialPattern:
    """
    Converted from SequentialPattern.java.
    """
    def __init__(self) -> None:
        self.itemsets: List[Itemset] = []
        self.sequencesIds: Optional[List[int]] = None
        self.isFoundFlag: bool = False
        self.additionalSupport: int = 0

    def setSequenceIDs(self, sequencesIds: List[int]) -> None:
        self.sequencesIds = sequencesIds

    def getSequenceIDs(self) -> Optional[List[int]]:
        return self.sequencesIds

    def getRelativeSupportFormated(self, sequencecount: int) -> str:
        if sequencecount <= 0:
            return "0"
        relSupport = float(self.getAbsoluteSupport()) / float(sequencecount)
        s = f"{relSupport:.5f}".rstrip("0").rstrip(".")
        return s if s else "0"

    def getAbsoluteSupport(self) -> int:
        return 0 if self.sequencesIds is None else len(self.sequencesIds)

    def addItemset(self, itemset: Itemset) -> None:
        self.itemsets.append(itemset)

    def copy(self) -> "SequentialPattern":
        clone = SequentialPattern()
        for it in self.itemsets:
            clone.addItemset(it.cloneItemSet())
        clone.additionalSupport = self.additionalSupport
        clone.sequencesIds = list(self.sequencesIds) if self.sequencesIds is not None else None
        clone.isFoundFlag = self.isFoundFlag
        return clone

    def __str__(self) -> str:
        parts: List[str] = []
        for itemset in self.itemsets:
            parts.append("(")
            for item in itemset.getItems():
                parts.append(str(item))
                parts.append(" ")
            parts.append(")")
        parts.append("    ")
        return "".join(parts)

    def itemsetsToString(self) -> str:
        parts: List[str] = []
        for itemset in self.itemsets:
            parts.append("{")
            for item in itemset.getItems():
                parts.append(str(item))
                parts.append(" ")
            parts.append("}")
        parts.append("    ")
        return "".join(parts)

    def getItemsets(self) -> List[Itemset]:
        return self.itemsets

    def get(self, index: int) -> Itemset:
        return self.itemsets[index]

    def size(self) -> int:
        return len(self.itemsets)

    def compareTo(self, o: "SequentialPattern") -> int:
        if o is self:
            return 0
        compare = self.getAbsoluteSupport() - o.getAbsoluteSupport()
        if compare != 0:
            return compare
        return hash(self) - hash(o)

    # Java bug kept: setIsFound does not set the flag in your code; it just returns it.
    def setIsFound(self, b: bool) -> bool:
        return self.isFoundFlag

    def isFound(self) -> bool:
        return self.isFoundFlag

    def addAdditionalSupport(self, additionalSupport: int) -> None:
        self.additionalSupport += int(additionalSupport)


# ----------------------------------------------------------------------
# SequentialPatterns
# ----------------------------------------------------------------------

class SequentialPatterns:
    """
    Converted from SequentialPatterns.java.
    """
    def __init__(self, name: str) -> None:
        self.levels: List[List[SequentialPattern]] = []
        self.sequenceCount: int = 0
        self.name: str = name
        self.levels.append([])

    def printFrequentPatterns(self, nbObject: int, showSequenceIdentifiers: bool) -> None:
        print(self.toString(nbObject, showSequenceIdentifiers))

    def copy(self) -> "SequentialPatterns":
        k = 0
        clone = SequentialPatterns(self.name)
        for level in self.getLevels():
            for pattern in level:
                clone.addSequence(pattern.copy(), k)
            k += 1
        return clone

    def toString(self, nbObject: int, showSequenceIdentifiers: bool) -> str:
        r: List[str] = []
        r.append(" ----------")
        r.append(self.name)
        r.append(" -------\n")
        levelCount = 0
        patternCount = 0
        for level in self.levels:
            r.append("  L")
            r.append(str(levelCount))
            r.append(" \n")
            for sequence in level:
                patternCount += 1
                r.append("  pattern ")
                r.append(str(patternCount))
                r.append(":  ")
                r.append(str(sequence))
                r.append("support :  ")
                r.append(sequence.getRelativeSupportFormated(nbObject))
                r.append(" (")
                r.append(str(sequence.getAbsoluteSupport()))
                r.append("/")
                r.append(str(nbObject))
                r.append(")")
                if showSequenceIdentifiers:
                    r.append(" sequence ids: ")
                    sids = sequence.getSequenceIDs() or []
                    for sid in sids:
                        r.append(str(sid))
                        r.append(" ")
                r.append("\n")
            levelCount += 1
        r.append(" -------------------------------- Patterns count : ")
        r.append(str(self.sequenceCount))
        return "".join(r)

    def addSequence(self, sequence: SequentialPattern, k: int) -> None:
        while len(self.levels) <= k:
            self.levels.append([])
        self.levels[k].append(sequence)
        self.sequenceCount += 1

    def getLevel(self, index: int) -> List[SequentialPattern]:
        return self.levels[index]

    def getLevelCount(self) -> int:
        return len(self.levels)

    def getLevels(self) -> List[List[SequentialPattern]]:
        return self.levels

    def getSequenceCount(self) -> int:
        return self.sequenceCount


# ----------------------------------------------------------------------
# AlgoBIDEPlus (full, single-file)
# ----------------------------------------------------------------------

class AlgoBIDEPlus:
    def __init__(self) -> None:
        self.startTime: int = 0
        self.endTime: int = 0
        self.patternCount: int = 0
        self.minsuppAbsolute: int = 0

        self.writer = None  # file object or None
        self.patterns: Optional[SequentialPatterns] = None

        self.maximumPatternLength: int = 1000
        self.showSequenceIdentifiers: bool = False

        self.BUFFERS_SIZE: int = 2000
        self.patternBuffer: List[int] = [0] * self.BUFFERS_SIZE

        self.sequenceCount: int = 0
        self.sequenceDatabase: Optional[SequenceDatabase] = None
        self.containsItemsetsWithMultipleItems: bool = False

        self.alreadySeen: Set[int] = set()
        self.alreadySeenPostfix: Set[int] = set()
        self.alreadySeenSuffix: Set[int] = set()

        self.mapItemSupport: Dict[int, int] = {}
        self.mapsItemSupportPostfix: Dict[int, int] = {}
        self.mapsItemSupportSuffix: Dict[int, int] = {}

    # --- Java: runAlgorithm(inputfile, outputfile, minsup)
    def runAlgorithm(self, inputFile: str, outputFilePath: Optional[str], minsup: int) -> Optional[SequentialPatterns]:
        import time
        self.patternCount = 0
        MemoryLogger.getInstance().reset()

        self.minsuppAbsolute = minsup
        self.startTime = int(time.time() * 1000)

        self.sequenceDatabase = SequenceDatabase()
        self.sequenceDatabase.loadFile(inputFile)
        self._bide(self.sequenceDatabase, outputFilePath)

        self.sequenceDatabase = None
        self.endTime = int(time.time() * 1000)

        if self.writer is not None:
            self.writer.close()
            self.writer = None

        return self.patterns

    def _bide(self, sequenceDatabase: SequenceDatabase, outputFilePath: Optional[str]) -> None:
        if outputFilePath is None:
            self.writer = None
            self.patterns = SequentialPatterns("FREQUENT SEQUENTIAL PATTERNS")
        else:
            self.patterns = None
            self.writer = open(outputFilePath, "w", encoding="utf-8")

        self.sequenceCount = sequenceDatabase.size()

        mapSequenceID = self._findSequencesContainingItems()

        if self.containsItemsetsWithMultipleItems:
            self._bideWithMultipleItems(mapSequenceID)
        else:
            self._bideWithSingleItems(mapSequenceID)

    # ------------------------------------------------------------------
    # Scan DB
    # ------------------------------------------------------------------

    def _findSequencesContainingItems(self) -> Dict[int, List[int]]:
        mapSequenceID: Dict[int, List[int]] = {}
        assert self.sequenceDatabase is not None
        for i in range(self.sequenceDatabase.size()):
            seq = self.sequenceDatabase.getSequences()[i]
            if seq is None:
                continue
            itemCountInCurrentItemset = 0
            for token in seq:
                if token > 0:
                    sequenceIDs = mapSequenceID.get(token)
                    if sequenceIDs is None:
                        sequenceIDs = []
                        mapSequenceID[token] = sequenceIDs
                    if len(sequenceIDs) == 0 or sequenceIDs[-1] != i:
                        sequenceIDs.append(i)
                    itemCountInCurrentItemset += 1
                    if itemCountInCurrentItemset > 1:
                        self.containsItemsetsWithMultipleItems = True
                elif token == -1:
                    itemCountInCurrentItemset = 0
        return mapSequenceID

    # ------------------------------------------------------------------
    # Save patterns
    # ------------------------------------------------------------------

    def _savePattern_single_item(self, item: int, support: int, sequenceIDs: List[int]) -> None:
        self.patternCount += 1
        if self.writer is not None:
            r: List[str] = [str(item), "-1", "#SUP:", str(support)]
            if self.showSequenceIdentifiers:
                r.append("#SID:")
                r.extend(str(sid) for sid in sequenceIDs)
            self.writer.write(" ".join(r) + "\n")
        else:
            assert self.patterns is not None
            pattern = SequentialPattern()
            pattern.addItemset(Itemset(item))
            pattern.setSequenceIDs(sequenceIDs)
            self.patterns.addSequence(pattern, 1)

    def _savePattern_buffer(self, lastBufferPosition: int, pseudoSequences: List[PseudoSequence]) -> None:
        self.patternCount += 1
        if self.writer is not None:
            r: List[str] = []
            for i in range(0, lastBufferPosition + 1):
                r.append(str(self.patternBuffer[i]))
                if i != lastBufferPosition and (not self.containsItemsetsWithMultipleItems):
                    r.append("-1")
            # bugfix in Java: ensure some -1 are not missing
            if self.patternBuffer[lastBufferPosition] != -1:
                r.append("-1")
            r.append("#SUP:")
            r.append(str(len(pseudoSequences)))
            if self.showSequenceIdentifiers:
                r.append("#SID:")
                for ps in pseudoSequences:
                    r.append(str(ps.sequenceID))
            self.writer.write(" ".join(r) + "\n")
        else:
            assert self.patterns is not None
            pattern = SequentialPattern()
            itemsetCount = 0
            current = Itemset()
            for i in range(0, lastBufferPosition + 1):
                token = self.patternBuffer[i]
                if token > 0:
                    current.addItem(token)
                elif token == -1:
                    pattern.addItemset(current)
                    current = Itemset()
                    itemsetCount += 1
            pattern.addItemset(current)
            itemsetCount += 1
            sids = [ps.sequenceID for ps in pseudoSequences]
            pattern.setSequenceIDs(sids)
            self.patterns.addSequence(pattern, itemsetCount)

    # ------------------------------------------------------------------
    # Single-item per itemset branch
    # ------------------------------------------------------------------

    def _bideWithSingleItems(self, mapSequenceID: Dict[int, List[int]]) -> None:
        assert self.sequenceDatabase is not None
        # remove infrequent items
        for i in range(self.sequenceDatabase.size()):
            seq = self.sequenceDatabase.getSequences()[i]
            if seq is None:
                continue
            currentPosition = 0
            for j in range(len(seq)):
                token = seq[j]
                if token > 0:
                    isFrequent = len(mapSequenceID.get(token, [])) >= self.minsuppAbsolute
                    if isFrequent:
                        seq[currentPosition] = token
                        currentPosition += 1
                elif token == -2:
                    if currentPosition > 0:
                        seq[currentPosition] = -2
                        self.sequenceDatabase.getSequences()[i] = seq[: currentPosition + 1]
                    else:
                        self.sequenceDatabase.getSequences()[i] = None
                    break

        for item, sids in mapSequenceID.items():
            support = len(sids)
            if support >= self.minsuppAbsolute:
                if self._checkBackscanPruningSingleItemsFirstTime(item, sids):
                    self.patternBuffer[0] = item
                    projected = self._buildProjectedDatabaseSingleItems(item, sids)

                    maxSupportExtensions = 0
                    if self.maximumPatternLength > 1:
                        maxSupportExtensions = self._recursionSingleItems(projected, 2, 0)

                    if support != maxSupportExtensions:
                        if self._checkBackwardExtensionSingleItemsFirstTime(item, sids):
                            self._savePattern_single_item(item, support, sids)

    def _buildProjectedDatabaseSingleItems(self, item: int, sequenceIDs: List[int]) -> List[PseudoSequence]:
        assert self.sequenceDatabase is not None
        projected: List[PseudoSequence] = []
        for sid in sequenceIDs:
            seq = self.sequenceDatabase.getSequences()[sid]
            if seq is None:
                continue
            j = 0
            while seq[j] != -2:
                if seq[j] == item:
                    if seq[j + 1] != -2:
                        projected.append(PseudoSequence(sid, j + 1))
                    break
                j += 1
        return projected

    def _checkBackscanPruningSingleItemsFirstTime(self, item: int, sequenceIDs: List[int]) -> bool:
        assert self.sequenceDatabase is not None
        localSupport: Dict[int, int] = {}
        highestSupportUntilNow = 0

        for k, sid in enumerate(sequenceIDs):
            seq = self.sequenceDatabase.getSequences()[sid]
            if seq is None:
                continue
            self.alreadySeen.clear()

            j = 0
            while seq[j] != -2:
                token = seq[j]
                if token > 0:
                    if token == item:
                        break
                    if token not in self.alreadySeen:
                        cnt = localSupport.get(token, 0) + 1
                        localSupport[token] = cnt
                        if cnt > highestSupportUntilNow:
                            highestSupportUntilNow = cnt
                        if cnt == len(sequenceIDs):
                            return False
                        self.alreadySeen.add(token)
                j += 1

            if highestSupportUntilNow + (len(sequenceIDs) - k - 1) < len(sequenceIDs):
                return True

        return True

    def _checkBackwardExtensionSingleItemsFirstTime(self, item: int, sequenceIDs: List[int]) -> bool:
        assert self.sequenceDatabase is not None
        localSupport: Dict[int, int] = {}
        highestSupportUntilNow = 0

        for k, sid in enumerate(sequenceIDs):
            seq = self.sequenceDatabase.getSequences()[sid]
            if seq is None:
                continue
            self.alreadySeen.clear()

            found = False
            for j in range(len(seq) - 1, -1, -1):
                token = seq[j]
                if token > 0:
                    if token == item:
                        found = True
                        continue
                    if found and token not in self.alreadySeen:
                        cnt = localSupport.get(token, 0) + 1
                        localSupport[token] = cnt
                        if cnt > highestSupportUntilNow:
                            highestSupportUntilNow = cnt
                        if cnt == len(sequenceIDs):
                            return False
                        self.alreadySeen.add(token)

            if highestSupportUntilNow + (len(sequenceIDs) - k - 1) < len(sequenceIDs):
                return True

        return True

    def findAllFrequentPairsSingleItems(self, sequences: List[PseudoSequence], lastBufferPosition: int) -> Dict[int, List[PseudoSequence]]:
        assert self.sequenceDatabase is not None
        mapItemsPseudo: Dict[int, List[PseudoSequence]] = {}
        for pseudo in sequences:
            sid = pseudo.getOriginalSequenceID()
            seq = self.sequenceDatabase.getSequences()[sid]
            if seq is None:
                continue
            i = pseudo.indexFirstItem
            while seq[i] != -2:
                token = seq[i]
                if token > 0:
                    lst = mapItemsPseudo.get(token)
                    if lst is None:
                        lst = []
                        mapItemsPseudo[token] = lst
                    ok = True
                    if lst:
                        ok = (lst[-1].sequenceID != sid)
                    if ok:
                        lst.append(PseudoSequence(sid, i + 1))
                i += 1
        MemoryLogger.getInstance().checkMemory()
        return mapItemsPseudo

    def _recursionSingleItems(self, database: List[PseudoSequence], k: int, lastBufferPosition: int) -> int:
        maxSupport = 0
        itemsPseudo = self.findAllFrequentPairsSingleItems(database, lastBufferPosition)
        database = None  # free reference

        for item, pseudos in itemsPseudo.items():
            support = len(pseudos)
            if support >= self.minsuppAbsolute:
                if support > maxSupport:
                    maxSupport = support

                self.patternBuffer[lastBufferPosition + 1] = item

                if self._checkBackscanPruningSingleItems(lastBufferPosition + 1, pseudos):
                    maxSupportExtensions = 0
                    if k < self.maximumPatternLength:
                        maxSupportExtensions = self._recursionSingleItems(pseudos, k + 1, lastBufferPosition + 1)

                    if support != maxSupportExtensions:
                        if self._checkBackwardExtensionSingleItems(lastBufferPosition + 1, pseudos):
                            self._savePattern_buffer(lastBufferPosition + 1, pseudos)

        MemoryLogger.getInstance().checkMemory()
        return maxSupport

    def _checkBackscanPruningSingleItems(self, lastBufferPosition: int, projectedDatabase: List[PseudoSequence]) -> bool:
        assert self.sequenceDatabase is not None
        for i in range(0, lastBufferPosition + 1):
            highestSupportUntilNow = 0
            self.mapItemSupport.clear()

            for k, pseudo in enumerate(projectedDatabase):
                sid = pseudo.getOriginalSequenceID()
                seq = self.sequenceDatabase.getSequences()[sid]
                if seq is None:
                    continue

                currentPositionToMatch = 0
                self.alreadySeen.clear()

                j = 0
                while seq[j] != -2:
                    token = seq[j]
                    if token > 0:
                        if token == self.patternBuffer[currentPositionToMatch]:
                            if i == currentPositionToMatch:
                                break  # continue loopSeq
                            currentPositionToMatch += 1
                        else:
                            if (currentPositionToMatch == i) and (token not in self.alreadySeen):
                                cnt = self.mapItemSupport.get(token, 0) + 1
                                self.mapItemSupport[token] = cnt
                                if cnt > highestSupportUntilNow:
                                    highestSupportUntilNow = cnt
                                if cnt == len(projectedDatabase):
                                    return False
                                self.alreadySeen.add(token)
                    j += 1

                if highestSupportUntilNow + (len(projectedDatabase) - k - 1) < len(projectedDatabase):
                    break
        return True

    def _checkBackwardExtensionSingleItems(self, lastBufferPosition: int, projectedDatabase: List[PseudoSequence]) -> bool:
        assert self.sequenceDatabase is not None
        for i in range(0, lastBufferPosition + 1):
            highestSupportUntilNow = 0
            self.mapItemSupport.clear()

            for k, pseudo in enumerate(projectedDatabase):
                sid = pseudo.getOriginalSequenceID()
                seq = self.sequenceDatabase.getSequences()[sid]
                if seq is None:
                    continue

                # pos after first instance of e1..ei-1
                currentPositionToMatch1 = 0
                posAfterFirstInstance = 0
                if i != 0:
                    for j in range(len(seq)):
                        token = seq[j]
                        if token > 0 and token == self.patternBuffer[currentPositionToMatch1]:
                            if currentPositionToMatch1 == i - 1:
                                posAfterFirstInstance = j + 1
                                break
                            currentPositionToMatch1 += 1

                currentPositionToMatch = lastBufferPosition
                self.alreadySeen.clear()

                for j in range(len(seq) - 1, posAfterFirstInstance - 1, -1):
                    token = seq[j]
                    if token > 0:
                        if currentPositionToMatch >= i and token == self.patternBuffer[currentPositionToMatch]:
                            currentPositionToMatch -= 1
                        else:
                            if currentPositionToMatch == i - 1 and token not in self.alreadySeen:
                                cnt = self.mapItemSupport.get(token, 0) + 1
                                self.mapItemSupport[token] = cnt
                                if cnt > highestSupportUntilNow:
                                    highestSupportUntilNow = cnt
                                if cnt == len(projectedDatabase):
                                    return False
                                self.alreadySeen.add(token)

                if highestSupportUntilNow + (len(projectedDatabase) - k - 1) < len(projectedDatabase):
                    break

        return True

    # ------------------------------------------------------------------
    # Multiple items per itemset branch
    # ------------------------------------------------------------------

    def _bideWithMultipleItems(self, mapSequenceID: Dict[int, List[int]]) -> None:
        assert self.sequenceDatabase is not None
        # remove infrequent items while preserving -1/-2 properly
        for i in range(self.sequenceDatabase.size()):
            seq = self.sequenceDatabase.getSequences()[i]
            if seq is None:
                continue
            currentPosition = 0
            currentItemsetItemCount = 0

            for j in range(len(seq)):
                token = seq[j]
                if token > 0:
                    isFrequent = len(mapSequenceID.get(token, [])) >= self.minsuppAbsolute
                    if isFrequent:
                        seq[currentPosition] = token
                        currentPosition += 1
                        currentItemsetItemCount += 1
                elif token == -1:
                    if currentItemsetItemCount > 0:
                        seq[currentPosition] = -1
                        currentPosition += 1
                        currentItemsetItemCount = 0
                elif token == -2:
                    if currentPosition > 0:
                        seq[currentPosition] = -2
                        self.sequenceDatabase.getSequences()[i] = seq[: currentPosition + 1]
                    else:
                        self.sequenceDatabase.getSequences()[i] = None
                    break

        for item, sids in mapSequenceID.items():
            support = len(sids)
            if support >= self.minsuppAbsolute:
                if self._checkBackscanPruningMultipleItemsFirstTime(item, sids):
                    self.patternBuffer[0] = item
                    projected = self._buildProjectedDatabaseFirstTimeMultipleItems(item, sids)

                    maxSupportExtensions = 0
                    if self.maximumPatternLength > 1:
                        maxSupportExtensions = self._recursionMultipleItems(projected, 2, 0)

                    if support != maxSupportExtensions:
                        if self._checkBackwardExtensionMultipleItemsFirstTime(item, sids):
                            self._savePattern_single_item(item, support, sids)

    def _buildProjectedDatabaseFirstTimeMultipleItems(self, item: int, sequenceIDs: List[int]) -> List[PseudoSequence]:
        assert self.sequenceDatabase is not None
        projected: List[PseudoSequence] = []
        for sid in sequenceIDs:
            seq = self.sequenceDatabase.getSequences()[sid]
            if seq is None:
                continue
            j = 0
            while seq[j] != -2:
                if seq[j] == item:
                    isEnd = (seq[j + 1] == -1 and seq[j + 2] == -2)
                    if not isEnd:
                        projected.append(PseudoSequence(sid, j + 1))
                    break
                j += 1
        return projected

    def _checkBackscanPruningMultipleItemsFirstTime(self, item: int, sequenceIDs: List[int]) -> bool:
        assert self.sequenceDatabase is not None
        self.mapItemSupport.clear()
        self.mapsItemSupportPostfix.clear()
        highestSupportUntilNow = 0

        for k, sid in enumerate(sequenceIDs):
            seq = self.sequenceDatabase.getSequences()[sid]
            if seq is None:
                continue

            posItem = 0
            posItemset = 0
            j = 0
            while True:
                token = seq[j]
                if token == item:
                    posItem = j
                    break
                if token == -1:
                    posItemset = j + 1
                j += 1

            self.alreadySeen.clear()
            self.alreadySeenPostfix.clear()

            for i in range(0, posItem):
                token = seq[i]
                if token > 0:
                    if i < posItemset:
                        if token not in self.alreadySeen:
                            cnt = self.mapItemSupport.get(token, 0) + 1
                            self.mapItemSupport[token] = cnt
                            highestSupportUntilNow = max(highestSupportUntilNow, cnt)
                            if cnt == len(sequenceIDs):
                                return False
                            self.alreadySeen.add(token)
                    else:
                        if token not in self.alreadySeenPostfix:
                            cnt = self.mapsItemSupportPostfix.get(token, 0) + 1
                            self.mapsItemSupportPostfix[token] = cnt
                            highestSupportUntilNow = max(highestSupportUntilNow, cnt)
                            if cnt == len(sequenceIDs):
                                return False
                            self.alreadySeenPostfix.add(token)

            if highestSupportUntilNow + (len(sequenceIDs) - k - 1) < len(sequenceIDs):
                return True

        return True

    def _checkBackwardExtensionMultipleItemsFirstTime(self, item: int, sequenceIDs: List[int]) -> bool:
        assert self.sequenceDatabase is not None
        self.mapItemSupport.clear()
        self.mapsItemSupportPostfix.clear()
        highestSupportUntilNow = 0

        for k, sid in enumerate(sequenceIDs):
            seq = self.sequenceDatabase.getSequences()[sid]
            if seq is None:
                continue

            # find last pos of item
            posItem = 0
            for j in range(len(seq) - 1, -1, -1):
                if seq[j] == item:
                    posItem = j
                    break

            self.alreadySeen.clear()
            self.alreadySeenPostfix.clear()

            itemsetContainsItem = True
            firstTimeContainsItem = (posItem > 0) and (seq[posItem - 1] != -1)

            for i in range(posItem - 1, -1, -1):
                token = seq[i]

                if token == -1:
                    itemsetContainsItem = False
                    firstTimeContainsItem = False

                if token > 0:
                    couldBeExtension = False
                    couldBePostfixExtension = False

                    if token == item:
                        itemsetContainsItem = True
                        couldBeExtension = True
                    else:
                        couldBeExtension = not firstTimeContainsItem
                        couldBePostfixExtension = itemsetContainsItem

                    if couldBePostfixExtension and token not in self.alreadySeenPostfix:
                        cnt = self.mapsItemSupportPostfix.get(token, 0) + 1
                        self.mapsItemSupportPostfix[token] = cnt
                        highestSupportUntilNow = max(highestSupportUntilNow, cnt)
                        if cnt == len(sequenceIDs):
                            return False
                        self.alreadySeenPostfix.add(token)

                    if couldBeExtension and token not in self.alreadySeen:
                        cnt = self.mapItemSupport.get(token, 0) + 1
                        self.mapItemSupport[token] = cnt
                        highestSupportUntilNow = max(highestSupportUntilNow, cnt)
                        if cnt == len(sequenceIDs):
                            return False
                        self.alreadySeen.add(token)

            if highestSupportUntilNow + (len(sequenceIDs) - k - 1) < len(sequenceIDs):
                return True

        return True

    # Frequent pairs structure for multi-items
    class MapFrequentPairs:
        def __init__(self) -> None:
            self.mapPairs: Dict[Pair, Pair] = {}
            self.mapPairsInPostfix: Dict[Pair, Pair] = {}

    def findAllFrequentPairs(self, sequences: List[PseudoSequence], lastBufferPosition: int) -> "AlgoBIDEPlus.MapFrequentPairs":
        assert self.sequenceDatabase is not None
        mapsPairs = AlgoBIDEPlus.MapFrequentPairs()

        # find position of first item in last itemset in buffer
        firstPos = lastBufferPosition
        while lastBufferPosition > 0:
            firstPos -= 1
            if firstPos < 0 or self.patternBuffer[firstPos] == -1:
                firstPos += 1
                break

        positionToBeMatched = firstPos

        for pseudo in sequences:
            sequenceID = pseudo.getOriginalSequenceID()
            seq = self.sequenceDatabase.getSequences()[sequenceID]
            if seq is None:
                continue

            previousItem = seq[pseudo.indexFirstItem - 1]
            currentItemsetIsPostfix = (previousItem != -1)
            isFirstItemset = True

            i = pseudo.indexFirstItem
            while seq[i] != -2:
                token = seq[i]
                if token > 0:
                    pair = Pair(token)
                    if currentItemsetIsPostfix:
                        old = mapsPairs.mapPairsInPostfix.get(pair)
                        if old is None:
                            mapsPairs.mapPairsInPostfix[pair] = pair
                        else:
                            pair = old
                    else:
                        old = mapsPairs.mapPairs.get(pair)
                        if old is None:
                            mapsPairs.mapPairs[pair] = pair
                        else:
                            pair = old

                    ok = True
                    pseudos = pair.getPseudoSequences()
                    if pseudos:
                        ok = (pseudos[-1].sequenceID != sequenceID)
                    if ok:
                        pseudos.append(PseudoSequence(sequenceID, i + 1))

                    # IMPORTANT section from Java
                    if currentItemsetIsPostfix and (not isFirstItemset):
                        pair2 = Pair(token)
                        old2 = mapsPairs.mapPairs.get(pair2)
                        if old2 is None:
                            mapsPairs.mapPairs[pair2] = pair2
                        else:
                            pair2 = old2
                        ok2 = True
                        pseudos2 = pair2.getPseudoSequences()
                        if pseudos2:
                            ok2 = (pseudos2[-1].sequenceID != sequenceID)
                        if ok2:
                            pseudos2.append(PseudoSequence(sequenceID, i + 1))

                    # try to match last itemset in prefix
                    if (not currentItemsetIsPostfix) and self.patternBuffer[positionToBeMatched] == token:
                        positionToBeMatched += 1
                        if positionToBeMatched > lastBufferPosition:
                            currentItemsetIsPostfix = True

                elif token == -1:
                    isFirstItemset = False
                    currentItemsetIsPostfix = False
                    positionToBeMatched = firstPos

                i += 1

        MemoryLogger.getInstance().checkMemory()
        return mapsPairs

    def _recursionMultipleItems(self, database: List[PseudoSequence], k: int, lastBufferPosition: int) -> int:
        maxSupport = 0
        mapsPairs = self.findAllFrequentPairs(database, lastBufferPosition)
        database = None

        # First: pairs in postfix
        for pairKey, pairVal in list(mapsPairs.mapPairsInPostfix.items()):
            pair = pairKey
            support = pair.getCount()
            if support >= self.minsuppAbsolute:
                maxSupport = max(maxSupport, support)

                newBufferPos = lastBufferPosition + 1
                self.patternBuffer[newBufferPos] = pair.item

                if self._checkBackscanPruningMultipleItems(newBufferPos, pairVal.getPseudoSequences()):
                    maxSupportExtensions = 0
                    if k < self.maximumPatternLength:
                        maxSupportExtensions = self._recursionMultipleItems(pair.getPseudoSequences(), k + 1, newBufferPos)

                    if support != maxSupportExtensions:
                        if self._checkBackwardExtensionMultipleItems(newBufferPos, pairVal.getPseudoSequences()):
                            self._savePattern_buffer(newBufferPos, pair.getPseudoSequences())

        # Second: normal pairs (s-extension)
        for pairKey, pairVal in list(mapsPairs.mapPairs.items()):
            pair = pairKey
            support = pair.getCount()
            if support >= self.minsuppAbsolute:
                maxSupport = max(maxSupport, support)

                newBufferPos = lastBufferPosition + 1
                self.patternBuffer[newBufferPos] = -1
                newBufferPos += 1
                self.patternBuffer[newBufferPos] = pair.item

                if self._checkBackscanPruningMultipleItems(newBufferPos, pairVal.getPseudoSequences()):
                    maxSupportExtensions = 0
                    if k < self.maximumPatternLength:
                        maxSupportExtensions = self._recursionMultipleItems(pair.getPseudoSequences(), k + 1, newBufferPos)

                    if support != maxSupportExtensions:
                        if self._checkBackwardExtensionMultipleItems(newBufferPos, pairVal.getPseudoSequences()):
                            self._savePattern_buffer(newBufferPos, pair.getPseudoSequences())

        MemoryLogger.getInstance().checkMemory()
        return maxSupport

    def _checkBackwardExtensionMultipleItems(self, lastBufferPosition: int, sequences: List[PseudoSequence]) -> bool:
        assert self.sequenceDatabase is not None

        # This method is long and delicate; this is a direct translation of your Java code.
        for i in range(0, lastBufferPosition + 1):
            # skip separators
            if self.patternBuffer[i] == -1:
                continue

            self.mapItemSupport.clear()
            self.mapsItemSupportPostfix.clear()
            self.mapsItemSupportSuffix.clear()

            for pseudo in sequences:
                sid = pseudo.getOriginalSequenceID()
                seq = self.sequenceDatabase.getSequences()[sid]
                if seq is None:
                    continue

                self.alreadySeen.clear()
                self.alreadySeenPostfix.clear()
                self.alreadySeenSuffix.clear()

                # ---- FIRST: match e1..ei-1 forward
                currentPositionToMatch = 0
                positionToMatchAtBeginingOfCurrentItemset = 0
                posItemFirst = 0
                posItemsetFirst = 0

                if i > 0:
                    j = 0
                    while True:
                        token = seq[j]
                        if token == -1:
                            if self.patternBuffer[currentPositionToMatch] == -1:
                                positionToMatchAtBeginingOfCurrentItemset = currentPositionToMatch
                            else:
                                currentPositionToMatch = positionToMatchAtBeginingOfCurrentItemset
                            posItemsetFirst = j
                        if token == self.patternBuffer[currentPositionToMatch]:
                            if currentPositionToMatch == i - 1:
                                posItemFirst = j + 1
                                break
                            if currentPositionToMatch == i - 2 and self.patternBuffer[currentPositionToMatch + 1] == -1:
                                posItemFirst = j + 1
                                break
                            currentPositionToMatch += 1
                        j += 1

                # ---- SECOND: match ei.. backward to find last occurrence region
                posItemLast = len(seq) - 1
                posLastItemset = 99999
                currentPositionToMatch = lastBufferPosition
                positionToMatchAtBeginingOfCurrentItemset = lastBufferPosition

                j = posItemLast
                while True:
                    token = seq[j]
                    if token == -1:
                        if self.patternBuffer[currentPositionToMatch] == -1:
                            positionToMatchAtBeginingOfCurrentItemset = currentPositionToMatch
                        else:
                            currentPositionToMatch = positionToMatchAtBeginingOfCurrentItemset

                    if token == self.patternBuffer[currentPositionToMatch]:
                        if currentPositionToMatch == i:
                            posItemLast = j - 1
                            while j >= 0 and seq[j] != -1:
                                j -= 1
                            posLastItemset = j + 1
                            break
                        currentPositionToMatch -= 1
                    j -= 1

                # ---- UPDATE support in [posItemFirst, posItemLast]
                firstItemstIsCut = (i != 0) and (seq[posItemFirst] != -1)
                lastItemsetIsCut = (posItemLast >= 0) and (seq[posItemLast] != -1)

                inFirstPostfix = firstItemstIsCut
                if lastItemsetIsCut:
                    posToMatch = posItemLast + 1
                    inFirstPostfix = False
                    for w in range(posItemFirst, posItemLast + 1):
                        if seq[posItemFirst] == seq[posToMatch]:
                            posToMatch += 1
                            if seq[posToMatch] == -1:
                                inFirstPostfix = True
                                break
                else:
                    inFirstPostfix = True

                inAnotherPostfix = False
                postfixItemToMatch = posItemsetFirst

                for j in range(posItemFirst, posItemLast + 1):
                    token = seq[j]

                    if token == -1:
                        inFirstPostfix = False
                        inAnotherPostfix = False
                        postfixItemToMatch = posItemsetFirst
                        if self.patternBuffer[postfixItemToMatch] == -1:
                            postfixItemToMatch += 1

                    if token > 0:
                        justMatched = False

                        if (not inAnotherPostfix) and i != 0 and self.patternBuffer[postfixItemToMatch] == token:
                            postfixItemToMatch -= 1
                            if postfixItemToMatch < 0 or self.patternBuffer[postfixItemToMatch] == -1:
                                inAnotherPostfix = True
                                if lastItemsetIsCut:
                                    posToMatch = posItemLast + 1
                                    inFirstPostfix = False
                                    for w in range(j, posItemLast + 1):
                                        if seq[w] == seq[posToMatch]:
                                            posToMatch += 1
                                            if seq[posToMatch] == -1:
                                                inAnotherPostfix = True
                                                break
                                justMatched = True

                        if inFirstPostfix or (inAnotherPostfix and (not justMatched)):
                            if token not in self.alreadySeenPostfix:
                                cnt = self.mapsItemSupportPostfix.get(token, 0) + 1
                                self.mapsItemSupportPostfix[token] = cnt
                                if cnt == len(sequences):
                                    return False
                                self.alreadySeenPostfix.add(token)

                        if j >= posLastItemset:
                            if token not in self.alreadySeenSuffix:
                                cnt = self.mapsItemSupportSuffix.get(token, 0) + 1
                                self.mapsItemSupportSuffix[token] = cnt
                                if cnt == len(sequences):
                                    return False
                                self.alreadySeenSuffix.add(token)

                        if (not inFirstPostfix) and j < posLastItemset:
                            if token not in self.alreadySeen:
                                cnt = self.mapItemSupport.get(token, 0) + 1
                                self.mapItemSupport[token] = cnt
                                if cnt == len(sequences):
                                    return False
                                self.alreadySeen.add(token)

        return True

    def _checkBackscanPruningMultipleItems(self, lastBufferPosition: int, sequences: List[PseudoSequence]) -> bool:
        assert self.sequenceDatabase is not None

        for i in range(0, lastBufferPosition + 1):
            if self.patternBuffer[i] == -1:
                continue

            highestSupportUntilNow = 0
            self.mapItemSupport.clear()
            self.mapsItemSupportPostfix.clear()
            self.mapsItemSupportSuffix.clear()

            for k, pseudo in enumerate(sequences):
                sid = pseudo.getOriginalSequenceID()
                seq = self.sequenceDatabase.getSequences()[sid]
                if seq is None:
                    continue

                self.alreadySeen.clear()
                self.alreadySeenPostfix.clear()
                self.alreadySeenSuffix.clear()

                # FIRST: match e1..ei-1 forward
                currentPositionToMatch = 0
                positionToMatchAtBeginingOfCurrentItemset = 0
                posItemFirst = 0
                posItemsetFirst = 0

                if i > 0:
                    j = 0
                    while True:
                        token = seq[j]
                        if token == -1:
                            if self.patternBuffer[currentPositionToMatch] == -1:
                                positionToMatchAtBeginingOfCurrentItemset = currentPositionToMatch
                            else:
                                currentPositionToMatch = positionToMatchAtBeginingOfCurrentItemset
                            posItemsetFirst = j
                        if token == self.patternBuffer[currentPositionToMatch]:
                            if currentPositionToMatch == i - 1:
                                if self.patternBuffer[currentPositionToMatch] != -1:
                                    posItemFirst = j + 1
                                break
                            if token != -1:
                                posItemFirst = j + 1
                            currentPositionToMatch += 1
                        j += 1

                # SECOND: match ei.. forward until an itemset end
                currentPositionToMatch = i
                posItemLast = -999
                posLastItemset = posItemFirst

                j = posItemFirst
                while True:
                    token = seq[j]
                    if token == -1:
                        currentPositionToMatch = i
                        posLastItemset = j + 1
                        posItemLast = -999
                    if token > 0 and token == self.patternBuffer[currentPositionToMatch]:
                        if posItemLast == -999:
                            posItemLast = j - 1
                        if currentPositionToMatch == lastBufferPosition:
                            break
                        currentPositionToMatch += 1
                        if self.patternBuffer[currentPositionToMatch] == -1:
                            break
                    j += 1

                # UPDATE supports in [posItemFirst, posItemLast]
                firstItemstIsCut = (i != 0) and (seq[posItemFirst] != -1)
                lastItemsetIsCut = (posItemLast >= 0) and (seq[posItemLast] != -1)

                inFirstPostfix = firstItemstIsCut
                if lastItemsetIsCut:
                    posToMatch = posItemLast + 1
                    inFirstPostfix = False
                    for w in range(posItemFirst, posItemLast + 1):
                        if seq[posItemFirst] == seq[posToMatch]:
                            posToMatch += 1
                            if seq[posToMatch] == -1:
                                inFirstPostfix = True
                                break
                else:
                    inFirstPostfix = True

                inAnotherPostfix = False
                postfixItemToMatch = posItemsetFirst

                for j in range(posItemFirst, posItemLast + 1):
                    token = seq[j]
                    if token == -1:
                        inFirstPostfix = False
                        inAnotherPostfix = False
                        postfixItemToMatch = posItemsetFirst
                    if token > 0:
                        justMatched = False
                        if (not inAnotherPostfix) and i != 0 and self.patternBuffer[postfixItemToMatch] == token:
                            postfixItemToMatch -= 1
                            if postfixItemToMatch < 0 or self.patternBuffer[postfixItemToMatch] == -1:
                                inAnotherPostfix = True
                                if lastItemsetIsCut:
                                    posToMatch = posItemLast + 1
                                    inFirstPostfix = False
                                    for w in range(j, posItemLast + 1):
                                        if seq[w] == seq[posToMatch]:
                                            posToMatch += 1
                                            if seq[posToMatch] == -1:
                                                inAnotherPostfix = True
                                                break
                                justMatched = True

                        if inFirstPostfix or (inAnotherPostfix and (not justMatched)):
                            if token not in self.alreadySeenPostfix:
                                cnt = self.mapsItemSupportPostfix.get(token, 0) + 1
                                self.mapsItemSupportPostfix[token] = cnt
                                highestSupportUntilNow = max(highestSupportUntilNow, cnt)
                                if cnt == len(sequences):
                                    return False
                                self.alreadySeenPostfix.add(token)

                        if j >= posLastItemset:
                            if token not in self.alreadySeenSuffix:
                                cnt = self.mapsItemSupportSuffix.get(token, 0) + 1
                                self.mapsItemSupportSuffix[token] = cnt
                                highestSupportUntilNow = max(highestSupportUntilNow, cnt)
                                if cnt == len(sequences):
                                    return False
                                self.alreadySeenSuffix.add(token)

                        if (not inFirstPostfix) and j < posLastItemset:
                            if token not in self.alreadySeen:
                                cnt = self.mapItemSupport.get(token, 0) + 1
                                self.mapItemSupport[token] = cnt
                                highestSupportUntilNow = max(highestSupportUntilNow, cnt)
                                if cnt == len(sequences):
                                    return False
                                self.alreadySeen.add(token)

                if highestSupportUntilNow + (len(sequences) - k - 1) < len(sequences):
                    break

        return True

    # ------------------------------------------------------------------
    # Stats and settings
    # ------------------------------------------------------------------

    def printStatistics(self) -> None:
        r: List[str] = []
        r.append("============  BIDE+ - SPMF 0.99c - 2016 - STATISTICS =====")
        r.append(f" Total time ~ {self.endTime - self.startTime} ms")
        r.append(f" Frequent sequences count : {self.patternCount}")
        r.append(f" Max memory (mb) : {MemoryLogger.getInstance().getMaxMemory()}")
        r.append(f" minsup = {self.minsuppAbsolute} sequences.")
        r.append(f" Pattern count : {self.patternCount}")
        r.append("==========================================================")
        print("\n".join(r))

    def setMaximumPatternLength(self, maximumPatternLength: int) -> None:
        self.maximumPatternLength = int(maximumPatternLength)

    def setShowSequenceIdentifiers(self, showSequenceIdentifiers: bool) -> None:
        self.showSequenceIdentifiers = bool(showSequenceIdentifiers)


# ----------------------------------------------------------------------
# Main (direct input/output configuration)
# ----------------------------------------------------------------------

def file_to_path(filename: str) -> str:
    """
    Look for the file next to bideplus.py first, then try Java/src/bideplus/.
    """
    here = os.path.dirname(os.path.abspath(__file__))

    p1 = os.path.join(here, filename)
    if os.path.exists(p1):
        return p1

    p2 = os.path.abspath(os.path.join("Java", "src", "bideplus", filename))
    if os.path.exists(p2):
        return p2

    raise FileNotFoundError(
        f"Could not locate {filename}. Tried:\n- {p1}\n- {p2}"
    )


def main() -> None:
    import os

    # --------------------------------------------------
    # Set parameters directly here
    # --------------------------------------------------
    input_path = file_to_path("contextPrefixSpan.txt")
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output_py.txt")

    minsup = 2
    showSequenceIdentifiers = False
    maximumPatternLength = 1000
    # --------------------------------------------------

    algo = AlgoBIDEPlus()
    algo.setShowSequenceIdentifiers(showSequenceIdentifiers)
    algo.setMaximumPatternLength(maximumPatternLength)

    algo.runAlgorithm(input_path, output_path, minsup)
    algo.printStatistics()


if __name__ == "__main__":
    main()