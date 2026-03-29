#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CloSpan is a sequential pattern mining algorithm that discovers frequent sequences in a sequence database.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
import argparse
import math
import time


# ----------------------------------------------------------------------
# Utilities
# ----------------------------------------------------------------------

def file_to_path(filename: str) -> str:
    """
    Java used getResource() from classpath.
    Here we look next to this file first, then fall back to Java/src/clospan/.
    """
    here = Path(__file__).resolve().parent
    p = here / filename
    if p.exists():
        return str(p)

    alt = Path("Java") / "src" / "clospan" / filename
    if alt.exists():
        return str(alt.resolve())

    # also allow searching one folder up (common project layouts)
    alt2 = here.parent / filename
    if alt2.exists():
        return str(alt2.resolve())

    raise FileNotFoundError(
        f"Could not locate {filename}. Tried:\n- {p}\n- {alt.resolve()}\n- {alt2.resolve()}"
    )


# ----------------------------------------------------------------------
# BitSet (Java-like)
# ----------------------------------------------------------------------

class BitSet:
    """
    Simple Java BitSet-like wrapper using Python set[int].
    Supports:
      - set(i)
      - cardinality()
      - nextSetBit(start)
      - size() (like Java's BitSet.size() is tricky; here we use max_bit+1)
      - iteration over set bits
    """
    __slots__ = ("_bits",)

    def __init__(self) -> None:
        self._bits: Set[int] = set()

    def set(self, i: int) -> None:
        self._bits.add(int(i))

    def clear(self) -> None:
        self._bits.clear()

    def cardinality(self) -> int:
        return len(self._bits)

    def nextSetBit(self, start: int) -> int:
        start = int(start)
        candidates = [b for b in self._bits if b >= start]
        if not candidates:
            return -1
        return min(candidates)

    def size(self) -> int:
        # NOT the same as cardinality. We mimic "logical size" (max index + 1)
        if not self._bits:
            return 0
        return max(self._bits) + 1

    def copy(self) -> "BitSet":
        b = BitSet()
        b._bits = set(self._bits)
        return b

    def __iter__(self):
        for i in sorted(self._bits):
            yield i

    def __contains__(self, i: int) -> bool:
        return int(i) in self._bits

    def __repr__(self) -> str:
        return f"BitSet({sorted(self._bits)})"


# ----------------------------------------------------------------------
# Memory logger (SPMF style)
# ----------------------------------------------------------------------

class MemoryLogger:
    _instance: Optional["MemoryLogger"] = None

    def __init__(self) -> None:
        self.maxMemory = 0.0

    @classmethod
    def getInstance(cls) -> "MemoryLogger":
        if cls._instance is None:
            cls._instance = MemoryLogger()
        return cls._instance

    def reset(self) -> None:
        self.maxMemory = 0.0

    def checkMemory(self) -> float:
        # Lightweight approximation (no psutil). Keep API compatibility.
        # We won't track real RSS without external libs; keep maxMemory as 0.0.
        current = 0.0
        if current > self.maxMemory:
            self.maxMemory = current
        return current

    def getMaxMemory(self) -> float:
        return self.maxMemory


# ----------------------------------------------------------------------
# Core data structures: Item, Itemset, Sequence, Database
# ----------------------------------------------------------------------

class Item:
    def __init__(self, id_: Any):
        self.id = id_

    def getId(self) -> Any:
        return self.id

    def __str__(self) -> str:
        return str(self.id)

    def __repr__(self) -> str:
        return f"Item({self.id!r})"

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Item) and self.id == other.id

    def __lt__(self, other: "Item") -> bool:
        return self.id < other.id

    def compareTo(self, other: "Item") -> int:
        return -1 if self.id < other.id else (1 if self.id > other.id else 0)


class ItemFactory:
    def __init__(self) -> None:
        self.pool: Dict[Any, Item] = {}

    def getItem(self, key: Any) -> Item:
        if key not in self.pool:
            self.pool[key] = Item(key)
        return self.pool[key]


class Itemset:
    def __init__(self) -> None:
        self._items: List[Item] = []
        self._timestamp: int = 0

    def setTimestamp(self, ts: int) -> None:
        self._timestamp = int(ts)

    def getTimestamp(self) -> int:
        return self._timestamp

    def addItem(self, item: Item) -> None:
        # Keep sorted order (binary insert would be faster; list sort is fine here)
        self._items.append(item)
        self._items.sort()

    def addItemAt(self, index: int, item: Item) -> None:
        self._items.insert(index, item)
        self._items.sort()

    def removeItemAt(self, index: int) -> Item:
        return self._items.pop(index)

    def removeItem(self, item: Item) -> None:
        self._items.remove(item)

    def getItems(self) -> List[Item]:
        return self._items

    def get(self, index: int) -> Item:
        return self._items[index]

    def size(self) -> int:
        return len(self._items)

    def cloneItemSet(self) -> "Itemset":
        it = Itemset()
        it._timestamp = self._timestamp
        it._items = list(self._items)
        return it

    def cloneItemSetMinusItems(self, mapSequenceID: Dict[Item, BitSet], minSupportAbsolute: float) -> "Itemset":
        # mapSequenceID already contains only frequent items after DB load.
        it = Itemset()
        it._timestamp = self._timestamp
        for x in self._items:
            if x in mapSequenceID:
                it._items.append(x)
        it._items.sort()
        return it


class Sequence:
    def __init__(self, id_: int) -> None:
        self._itemsets: List[Itemset] = []
        self._id: int = int(id_)
        self._numberOfItems: int = 0

    def setID(self, id_: int) -> None:
        self._id = int(id_)

    def getId(self) -> int:
        return self._id

    def addItemset(self, itemset: Itemset) -> None:
        self._itemsets.append(itemset)
        self._numberOfItems += itemset.size()

    def getItemsets(self) -> List[Itemset]:
        return self._itemsets

    def get(self, index: int) -> Itemset:
        return self._itemsets[index]

    def size(self) -> int:
        return len(self._itemsets)

    def length(self) -> int:
        return self._numberOfItems

    def cloneSequence(self) -> "Sequence":
        s = Sequence(self.getId())
        for it in self._itemsets:
            s.addItemset(it.cloneItemSet())
        return s

    def cloneSequenceMinusItems(self, mapSequenceID: Dict[Item, BitSet], relativeMinSup: float) -> "Sequence":
        s = Sequence(self.getId())
        for it in self._itemsets:
            new_it = it.cloneItemSetMinusItems(mapSequenceID, relativeMinSup)
            if new_it.size() != 0:
                s.addItemset(new_it)
        return s

    def __str__(self) -> str:
        r = []
        for it in self._itemsets:
            part = "{t=" + str(it.getTimestamp()) + ", "
            part += " ".join(str(x) for x in it.getItems()) + " }"
            r.append(part)
        return "".join(r) + "    "


class SequenceDatabase:
    def __init__(self) -> None:
        self.frequentItems: Dict[Item, BitSet] = {}
        self.sequences: List[Sequence] = []
        self.itemFactory = ItemFactory()

    def loadFile(self, path: str, minSupRelative: float) -> None:
        seq_id = 1
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                c0 = line[0]
                if c0 in ("#", "%", "@"):
                    continue
                self.addSequence(line.split(), seq_id)
                seq_id += 1

        minSupAbsolute = int(math.ceil(minSupRelative * len(self.sequences)))
        if minSupAbsolute <= 0:
            minSupAbsolute = 1

        to_remove = []
        for item, bs in self.frequentItems.items():
            if bs.cardinality() < minSupAbsolute:
                to_remove.append(item)
        for item in to_remove:
            self.frequentItems.pop(item, None)

    def addSequence(self, tokens: List[str], sequenceID: int) -> None:
        timestamp = -1
        seq = Sequence(len(self.sequences))
        seq.setID(sequenceID)

        itemset = Itemset()
        counted: Dict[Item, bool] = {}

        for tok in tokens:
            if tok and tok[0] == "<":  # timestamp token like <1>
                value = tok[1:-1]
                timestamp = int(value)
                itemset.setTimestamp(timestamp)
            elif tok == "-1":  # end itemset
                time_ = itemset.getTimestamp() + 1
                seq.addItemset(itemset)
                itemset = Itemset()
                itemset.setTimestamp(time_)
            elif tok == "-2":  # end sequence
                self.sequences.append(seq)
            else:
                item = self.itemFactory.getItem(int(tok))
                if item not in counted:
                    counted[item] = True
                    bs = self.frequentItems.get(item)
                    if bs is None:
                        bs = BitSet()
                        self.frequentItems[item] = bs
                    bs.set(seq.getId())
                itemset.addItem(item)

    def size(self) -> int:
        return len(self.sequences)

    def getSequences(self) -> List[Sequence]:
        return self.sequences

    def getFrequentItems(self) -> Dict[Item, BitSet]:
        return self.frequentItems

    def clear(self) -> None:
        self.frequentItems.clear()
        self.sequences.clear()


# ----------------------------------------------------------------------
# Abstractions
# ----------------------------------------------------------------------

class Abstraction_Generic:
    def toStringToFile(self) -> str:
        raise NotImplementedError

    def compute(self, sequence: "PseudoSequence", projection: int, itemsetIndex: int) -> bool:
        raise NotImplementedError

    def compareTo(self, other: "Abstraction_Generic") -> int:
        raise NotImplementedError


class Abstraction_Qualitative(Abstraction_Generic):
    def __init__(self, equalRelation: bool) -> None:
        self.equalRelation = bool(equalRelation)

    @staticmethod
    def crear(equalRelation: bool) -> "Abstraction_Qualitative":
        return Abstraction_Qualitative(equalRelation)

    def hasEqualRelation(self) -> bool:
        return self.equalRelation

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Abstraction_Qualitative) and self.equalRelation == other.equalRelation

    def __hash__(self) -> int:
        return 1 if self.equalRelation else 0

    def compareTo(self, other: Abstraction_Generic) -> int:
        if not isinstance(other, Abstraction_Qualitative):
            return 0
        if self.equalRelation == other.equalRelation:
            return 0
        # Java logic: if !equalRelation then 1 else -1
        return 1 if (not self.equalRelation) else -1

    def __str__(self) -> str:
        return " ->" if (not self.equalRelation) else ""

    def toStringToFile(self) -> str:
        return " -1" if (not self.equalRelation) else ""

    def compute(self, sequence: "PseudoSequence", projection: int, indexItemset: int) -> bool:
        return sequence.isPostfix(projection, indexItemset) == self.hasEqualRelation()


# ----------------------------------------------------------------------
# Pair + ItemAbstractionPair
# ----------------------------------------------------------------------

class ItemAbstractionPair:
    def __init__(self, item: Item, abstraction: Abstraction_Generic) -> None:
        self.item = item
        self.abstraction = abstraction

    def getItem(self) -> Item:
        return self.item

    def getAbstraction(self) -> Abstraction_Generic:
        return self.abstraction

    def __hash__(self) -> int:
        return hash(self.item) * 9 + hash(self.abstraction)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, ItemAbstractionPair)
            and self.item == other.item
            and self.abstraction == other.abstraction
        )

    def compareTo(self, other: "ItemAbstractionPair") -> int:
        ci = self.item.compareTo(other.item)
        if ci == 0:
            return self.abstraction.compareTo(other.abstraction)
        return ci

    def __lt__(self, other: "ItemAbstractionPair") -> bool:
        return self.compareTo(other) < 0

    def __str__(self) -> str:
        if isinstance(self.abstraction, Abstraction_Qualitative):
            return f"{self.abstraction} {self.item}"
        return f"{self.item}{self.abstraction} "

    def toStringToFile(self) -> str:
        if isinstance(self.abstraction, Abstraction_Qualitative):
            return f"{self.abstraction.toStringToFile()} {self.item}"
        return f"{self.item}{self.abstraction} "


class ItemAbstractionPairCreator:
    _instance: Optional["ItemAbstractionPairCreator"] = None

    @classmethod
    def getInstance(cls) -> "ItemAbstractionPairCreator":
        if cls._instance is None:
            cls._instance = ItemAbstractionPairCreator()
        return cls._instance

    def getItemAbstractionPair(self, item: Item, abstraction: Abstraction_Generic) -> ItemAbstractionPair:
        return ItemAbstractionPair(item, abstraction)


class Pair:
    def __init__(self, postfix: bool, pair: ItemAbstractionPair) -> None:
        self.postfix = bool(postfix)
        self.pair = pair
        self.sequencesID = BitSet()

    def isPostfix(self) -> bool:
        return self.postfix

    def getPar(self) -> ItemAbstractionPair:
        return self.pair

    def getSupport(self) -> int:
        return self.sequencesID.cardinality()

    def getSequencesID(self) -> BitSet:
        return self.sequencesID

    def setSequencesID(self, bs: BitSet) -> None:
        self.sequencesID = bs

    def __hash__(self) -> int:
        return (1 if self.postfix else 0) * 59 + hash(self.pair) * 59

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Pair) and self.postfix == other.postfix and self.pair == other.pair

    def compareTo(self, other: "Pair") -> int:
        c = self.pair.compareTo(other.pair)
        if c != 0:
            return c
        if self.postfix == other.postfix:
            return 0
        return -1 if self.postfix else 1

    def __lt__(self, other: "Pair") -> bool:
        return self.compareTo(other) < 0

    def __str__(self) -> str:
        post = "*" if self.postfix else ""
        return f"{post}{self.pair}[{self.sequencesID.size()}]"


# ----------------------------------------------------------------------
# Pattern + creators
# ----------------------------------------------------------------------

class Pattern:
    def __init__(self, elements: Optional[Any] = None) -> None:
        # IMPORTANT FIX (your crash): accept ItemAbstractionPair directly
        if elements is None:
            self.elements: List[ItemAbstractionPair] = []
        elif isinstance(elements, ItemAbstractionPair):
            self.elements = [elements]
        elif isinstance(elements, list):
            self.elements = elements
        else:
            raise TypeError(
                f"Pattern(elements) must be None, ItemAbstractionPair, or list; got {type(elements)}"
            )

        self.appearingIn: BitSet = BitSet()
        self.support: int = 0
        self.sumIdSequences: int = -1

    def size(self) -> int:
        return len(self.elements)

    def getElements(self) -> List[ItemAbstractionPair]:
        return self.elements

    def getIthElement(self, i: int) -> ItemAbstractionPair:
        return self.elements[i]

    def getLastElement(self) -> Optional[ItemAbstractionPair]:
        return self.elements[-1] if self.elements else None

    def add(self, pair: ItemAbstractionPair) -> None:
        self.elements.append(pair)

    def clonePatron(self) -> "Pattern":
        return PatternCreator.getInstance().createPattern(list(self.elements))

    def concatenate(self, pair: ItemAbstractionPair) -> "Pattern":
        r = self.clonePatron()
        r.add(pair)
        return r

    def setAppearingIn(self, bs: BitSet) -> None:
        self.appearingIn = bs
        self.setSupport(bs.cardinality())
        self.sumIdSequences = -1

    def getAppearingIn(self) -> BitSet:
        return self.appearingIn

    def setSupport(self, support: int) -> None:
        self.support = int(support)

    def getSupport(self) -> int:
        return self.support

    def getSumIdSequences(self) -> int:
        if self.sumIdSequences < 0:
            s = 0
            for i in self.appearingIn:
                s += i
            self.sumIdSequences = s
        return self.sumIdSequences

    def isSubpattern(self, abstractionCreator: "AbstractionCreator", p: "Pattern") -> bool:
        positions = [0 for _ in range(self.size())]
        return abstractionCreator.isSubpattern(self, p, 0, positions)

    def compareTo(self, other: "Pattern") -> int:
        a = self.elements
        b = other.elements
        smaller = a if len(a) < len(b) else b
        larger = b if smaller is a else a
        for i in range(len(smaller)):
            c = smaller[i].compareTo(larger[i])
            if c != 0:
                return c
        if len(a) == len(b):
            return 0
        return -1 if len(a) < len(b) else 1

    def __lt__(self, other: "Pattern") -> bool:
        return self.compareTo(other) < 0

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Pattern) and self.compareTo(other) == 0

    def __hash__(self) -> int:
        return hash(tuple(self.elements))

    def toStringToFile(self, outputSequenceIdentifiers: bool) -> str:
        # replicate Java logic for qualitative abstraction printing
        out = []
        for i, el in enumerate(self.elements):
            if i == len(self.elements) - 1:
                if i != 0:
                    out.append(el.toStringToFile())
                else:
                    out.append(str(el.getItem()))
                out.append(" -1")
            elif i == 0:
                out.append(str(el.getItem()))
            else:
                out.append(el.toStringToFile())

        out.append(" #SUP: ")
        out.append(str(self.getSupport()))

        if outputSequenceIdentifiers:
            out.append(" #SID: ")
            for sid in self.appearingIn:
                out.append(str(sid - 1))  # match Java bugfix comment
                out.append(" ")

        return "".join(out)

    def __str__(self) -> str:
        s = "".join(str(e) for e in self.elements)
        s += f"\t({self.appearingIn.size()})\t[{self.getSupport()}]"
        return s


class PatternCreator:
    _instance: Optional["PatternCreator"] = None

    @classmethod
    def getInstance(cls) -> "PatternCreator":
        if cls._instance is None:
            cls._instance = PatternCreator()
        return cls._instance

    def createPattern(self, elements: Optional[Any] = None) -> Pattern:
        return Pattern(elements)

    def concatenate(self, p1: Optional[Pattern], pair: Optional[ItemAbstractionPair]) -> Optional[Pattern]:
        if p1 is None:
            if pair is None:
                return None
            return self.createPattern(pair)
        if pair is None:
            return p1
        return p1.concatenate(pair)


# ----------------------------------------------------------------------
# Sequences container (SaverIntoMemory)
# ----------------------------------------------------------------------

class Sequences:
    def __init__(self, name: str) -> None:
        self.name = name
        self.levels: List[List[Pattern]] = [[]]  # level 0 empty
        self.nbSequeencesFrequentes = 0

    def addSequence(self, seq: Pattern, k: int) -> None:
        while len(self.levels) <= k:
            self.levels.append([])
        self.levels[k].append(seq)
        self.nbSequeencesFrequentes += 1

    def sort(self) -> None:
        for lvl in self.levels:
            lvl.sort()

    def toStringToFile(self, outputSequenceIdentifiers: bool) -> str:
        r = []
        for levelCount, level in enumerate(self.levels):
            r.append(f"\n***Level {levelCount}***\n\n")
            for seq in level:
                r.append(seq.toStringToFile(outputSequenceIdentifiers))
                r.append("\n")
        return "".join(r)

    def clear(self) -> None:
        for lvl in self.levels:
            lvl.clear()
        self.levels.clear()


# ----------------------------------------------------------------------
# Saver interface + implementations
# ----------------------------------------------------------------------

class Saver:
    def savePattern(self, p: Pattern) -> None:
        raise NotImplementedError

    def finish(self) -> None:
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError

    def print(self) -> str:
        raise NotImplementedError


class SaverIntoFile(Saver):
    def __init__(self, outputFilePath: str, outputSequenceIdentifiers: bool) -> None:
        self.path = outputFilePath
        self.outputSequenceIdentifiers = outputSequenceIdentifiers
        self._fh = open(outputFilePath, "w", encoding="utf-8")

    def savePattern(self, p: Pattern) -> None:
        self._fh.write(p.toStringToFile(self.outputSequenceIdentifiers) + "\n")

    def finish(self) -> None:
        if self._fh:
            self._fh.close()

    def clear(self) -> None:
        self._fh = None

    def print(self) -> str:
        return f"Content at file {self.path}"


class SaverIntoMemory(Saver):
    def __init__(self, outputSequenceIdentifiers: bool, name: str = "FREQUENT SEQUENTIAL PATTERNS") -> None:
        self.patterns = Sequences(name)
        self.outputSequenceIdentifiers = outputSequenceIdentifiers

    def savePattern(self, p: Pattern) -> None:
        self.patterns.addSequence(p, p.size())

    def finish(self) -> None:
        self.patterns.sort()

    def clear(self) -> None:
        self.patterns.clear()

    def print(self) -> str:
        return self.patterns.toStringToFile(self.outputSequenceIdentifiers)


# ----------------------------------------------------------------------
# PseudoSequence + PseudoSequenceDatabase
# ----------------------------------------------------------------------

class PseudoSequenceDatabase:
    def __init__(self) -> None:
        self.pseudoSequences: List["PseudoSequence"] = []
        self.cumulativeSum: int = 0
        self.cumulativeSumNumberOfProjections: int = 0
        self.numberOfElementsProjectedDatabase: int = 0
        self.elementsProjectedDatabase: int = 0

    def addSequence(self, ps: "PseudoSequence") -> None:
        self.pseudoSequences.append(ps)

    def getPseudoSequences(self) -> List["PseudoSequence"]:
        return self.pseudoSequences

    def size(self) -> int:
        return len(self.pseudoSequences)

    def setCumulativeSum(self, v: int) -> None:
        self.cumulativeSum = int(v)

    def getCumulativeSum(self) -> int:
        return self.cumulativeSum

    def setCumulativeSumNumberOfProjections(self, v: int) -> None:
        self.cumulativeSumNumberOfProjections = int(v)

    def getCumulativeSumNumberOfProjections(self) -> int:
        return self.cumulativeSumNumberOfProjections

    def setNumberOfElementsProjectedDatabase(self, v: int) -> None:
        self.numberOfElementsProjectedDatabase = int(v)

    def getNumberOfElementsProjectedDatabase(self) -> int:
        return self.numberOfElementsProjectedDatabase

    def setElementsProjectedDatabase(self, s: str) -> None:
        # Java had this disabled. Keep as 0.
        self.elementsProjectedDatabase = 0 if not s else 0

    def getElementsProjectedDatabase(self) -> int:
        return self.elementsProjectedDatabase

    def clear(self) -> None:
        self.pseudoSequences.clear()


class PseudoSequence:
    def __init__(self, timeShift: int, sequence: Sequence, itemsetIndex: int, itemIndex: int) -> None:
        self.timeShift: List[int] = [int(timeShift)]
        self.sequence: Sequence = sequence
        self.firstItemset: List[int] = [int(itemsetIndex)]
        self.firstItem: List[int] = [int(itemIndex)]

    @classmethod
    def fromPseudo(cls, timeShift: int, pseudoseq: "PseudoSequence", itemsetIndex: int, itemIndex: int, firstItemsetIdx: int) -> "PseudoSequence":
        obj = cls.__new__(cls)  # bypass __init__
        obj.sequence = pseudoseq.sequence
        newTimeShift = int(timeShift) + int(pseudoseq.timeShift[firstItemsetIdx])
        obj.timeShift = [newTimeShift]

        obj.firstItemset = [int(itemsetIndex) + int(pseudoseq.firstItemset[firstItemsetIdx])]
        if obj.firstItemset[0] == pseudoseq.firstItemset[firstItemsetIdx]:
            obj.firstItem = [int(itemIndex) + int(pseudoseq.firstItem[firstItemsetIdx])]
        else:
            obj.firstItem = [int(itemIndex)]
        return obj

    def addProjectionPoint(self, firstItemsetIdx: int, timeShift: int, pseudoseq: "PseudoSequence", itemsetIndex: int, itemIndex: int) -> None:
        newTimeShift = int(timeShift) + int(pseudoseq.timeShift[firstItemsetIdx])
        self.timeShift.append(newTimeShift)

        self.firstItemset.append(int(itemsetIndex) + int(pseudoseq.firstItemset[firstItemsetIdx]))

        if self.firstItemset[-1] == pseudoseq.firstItemset[firstItemsetIdx]:
            self.firstItem.append(int(itemIndex) + int(pseudoseq.firstItem[firstItemsetIdx]))
        else:
            self.firstItem.append(int(itemIndex))

    def getFirstItemset(self, index: int) -> int:
        return self.firstItemset[index]

    def size(self, proj: int) -> int:
        return self.sequence.size() - self.firstItemset[proj]

    def numberOfProjectionsIncluded(self) -> int:
        return len(self.firstItemset)

    def length(self, firstItemsetIdx: int) -> int:
        itemsBefore = 0
        for i in range(self.firstItemset[firstItemsetIdx]):
            itemsBefore += self.sequence.get(i).size()
        itemsBefore += self.firstItem[firstItemsetIdx]
        return self.sequence.length() - itemsBefore

    def isFirstItemset(self, index: int) -> bool:
        return index == 0

    def getItemset(self, itemsetIndex: int, proj: int) -> Itemset:
        return self.sequence.get(itemsetIndex + self.firstItemset[proj])

    def getSizeOfItemsetAt(self, proj: int, index: int) -> int:
        size = self.sequence.getItemsets()[index + self.firstItemset[proj]].size()
        if self.isFirstItemset(index):
            size -= self.firstItem[proj]
        return size

    def getBeginningOfItemset(self, proj: int, itemsetIndex: int) -> int:
        if self.isFirstItemset(itemsetIndex):
            return self.firstItem[proj]
        return 0

    def isPostfix(self, proj: int, itemsetIndex: int) -> bool:
        return self.isFirstItemset(itemsetIndex) and self.firstItem[proj] != 0

    def getItemAtInItemsetAt(self, proj: int, itemIndex: int, itemsetIndex: int) -> Item:
        if self.isFirstItemset(itemsetIndex):
            return self.getItemset(itemsetIndex, proj).get(itemIndex + self.firstItem[proj])
        return self.getItemset(itemsetIndex, proj).get(itemIndex)

    def getId(self) -> int:
        return self.sequence.getId()

    def getAbsoluteTimeStamp(self, itemsetIndex: int, proj: int) -> int:
        return self.getItemset(itemsetIndex, proj).getTimestamp()

    def getTimeShift(self, proj: int) -> int:
        return self.timeShift[proj]

    def _getTimeStamp(self, itemsetIndex: int, proj: int) -> int:
        return self.getItemset(itemsetIndex, proj).getTimestamp() - self.timeShift[proj]

    def getRelativeTimeStamp(self, itemsetIndex: int, proj: int) -> int:
        return self._getTimeStamp(itemsetIndex, proj)

    def indexOf(self, proj: int, itemsetIndex: int, item: Item) -> int:
        it = self.getItemset(itemsetIndex, proj)
        beginning = self.getBeginningOfItemset(proj, itemsetIndex)
        items = it.getItems()
        # binary search
        lo, hi = 0, len(items)
        while lo < hi:
            mid = (lo + hi) // 2
            if items[mid] < item:
                lo = mid + 1
            else:
                hi = mid
        idx = lo
        if idx < len(items) and items[idx] == item and idx >= beginning:
            return idx - beginning
        return -1

    def __str__(self) -> str:
        r = []
        for k in range(len(self.firstItemset)):
            for i in range(self.size(k)):
                part = "{t=" + str(self._getTimeStamp(i, k)) + ", "
                for j in range(self.getSizeOfItemsetAt(k, i)):
                    part += str(self.getItemAtInItemsetAt(k, j, i))
                    if self.isPostfix(k, i):
                        part += "*"
                    part += " "
                part += "}"
                r.append(part)
            r.append("\n")
        return "".join(r)


# ----------------------------------------------------------------------
# Trie
# ----------------------------------------------------------------------

class TrieNode:
    def __init__(self, pair: Optional[ItemAbstractionPair] = None, child: Optional["Trie"] = None, alreadyExplored: bool = False) -> None:
        self.pair = pair
        self.child = child
        self.alreadyExplored = alreadyExplored

    def getChild(self) -> Optional["Trie"]:
        return self.child

    def setChild(self, child: Optional["Trie"]) -> None:
        self.child = child

    def getPair(self) -> Optional[ItemAbstractionPair]:
        return self.pair

    def setPair(self, pair: Optional[ItemAbstractionPair]) -> None:
        self.pair = pair

    def compareTo(self, o: Any) -> int:
        if isinstance(o, TrieNode):
            return self.pair.compareTo(o.pair)
        if isinstance(o, ItemAbstractionPair):
            return self.pair.compareTo(o)
        if isinstance(o, Item):
            return self.pair.getItem().compareTo(o)
        raise RuntimeError("Error comparing TrieNode with unsupported object")

    def __lt__(self, other: "TrieNode") -> bool:
        return self.compareTo(other) < 0

    def __str__(self) -> str:
        return f"{{{self.pair}}}, [{self.child if self.child else 'NULL'}]"


class Trie:
    _intId = 1

    def __init__(self, nodes: Optional[List[TrieNode]] = None) -> None:
        self.nodes: List[TrieNode] = nodes if nodes is not None else []
        self.appearingIn: BitSet = BitSet()
        self.support: int = -1
        self.sumSequencesIDs: int = -1
        self.id: int = Trie._intId
        Trie._intId += 1

    def addNode(self, node: TrieNode) -> None:
        self.nodes.append(node)

    def getNodes(self) -> List[TrieNode]:
        return self.nodes

    def setNodes(self, nodes: List[TrieNode]) -> None:
        self.nodes = nodes

    def levelSize(self) -> int:
        return len(self.nodes) if self.nodes is not None else 0

    def getChild(self, index: int) -> Optional["Trie"]:
        return self.nodes[index].getChild()

    def getNode(self, index: int) -> TrieNode:
        return self.nodes[index]

    def setAppearingIn(self, bs: BitSet) -> None:
        self.appearingIn = bs
        self.support = -1
        self.sumSequencesIDs = -1

    def getAppearingIn(self) -> BitSet:
        return self.appearingIn

    def getSupport(self) -> int:
        if self.support < 0:
            self.support = self.appearingIn.cardinality()
        return self.support

    def getSumIdSequences(self) -> int:
        if self.sumSequencesIDs < 0:
            s = 0
            for i in self.appearingIn:
                s += i
            self.sumSequencesIDs = s
        return self.sumSequencesIDs

    def removeAll(self) -> None:
        for node in self.nodes:
            child = node.getChild()
            if child is not None:
                child.removeAll()
            node.setChild(None)
            node.setPair(None)
        self.nodes.clear()

    def preorderTraversal(self, p: Optional[Pattern]) -> List[Pattern]:
        result: List[Pattern] = []
        for node in self.nodes:
            child = node.getChild()
            newPattern = PatternCreator.getInstance().concatenate(p, node.getPair())
            if child is not None:
                newPattern.setAppearingIn(child.getAppearingIn())
            result.append(newPattern)
            if child is not None:
                result.extend(child.preorderTraversal(newPattern))
        return result

    def __str__(self) -> str:
        if self.nodes is None:
            return ""
        pairs = ",".join(str(n.getPair()) for n in self.nodes) if self.nodes else "NULL"
        return f"ID={self.id}[{pairs}]"


# ----------------------------------------------------------------------
# AbstractionCreator (Qualitative)
# ----------------------------------------------------------------------

class AbstractionCreator:
    def CreateDefaultAbstraction(self) -> Abstraction_Generic:
        raise NotImplementedError

    def findAllFrequentPairs(self, sequences: List[PseudoSequence]) -> Set[Pair]:
        raise NotImplementedError

    def createAbstractionFromAPrefix(self, prefix: Pattern, abstraction: Abstraction_Generic) -> Abstraction_Generic:
        raise NotImplementedError

    def isSubpattern(self, aThis: Pattern, p: Pattern, i: int, positions: List[int]) -> bool:
        raise NotImplementedError


class AbstractionCreator_Qualitative(AbstractionCreator):
    _instance: Optional["AbstractionCreator_Qualitative"] = None

    @classmethod
    def getInstance(cls) -> "AbstractionCreator_Qualitative":
        if cls._instance is None:
            cls._instance = AbstractionCreator_Qualitative()
        return cls._instance

    def CreateDefaultAbstraction(self) -> Abstraction_Generic:
        return Abstraction_Qualitative.crear(False)

    def createAbstraction(self, equalRelation: bool) -> Abstraction_Generic:
        return Abstraction_Qualitative.crear(equalRelation)

    def _addPair(
        self,
        pairMap: Dict[Pair, Pair],
        alreadyCountedForSequenceID: Set[Pair],
        sid: int,
        item: Item,
        postfix: bool,
    ) -> None:
        pair = Pair(postfix, ItemAbstractionPairCreator.getInstance().getItemAbstractionPair(item, self.createAbstraction(postfix)))
        old = pairMap.get(pair)
        if pair in alreadyCountedForSequenceID:
            return
        alreadyCountedForSequenceID.add(pair)
        if old is None:
            pairMap[pair] = pair
        else:
            pair = old
        pair.getSequencesID().set(sid)

    def findAllFrequentPairs(self, sequences: List[PseudoSequence]) -> Set[Pair]:
        pairMap: Dict[Pair, Pair] = {}
        alreadyCounted: Set[Pair] = set()

        for seq in sequences:
            alreadyCounted.clear()
            # emulate Java labeled loop behavior
            for k in range(seq.numberOfProjectionsIncluded()):
                for i in range(seq.size(k)):
                    if k > 0 and i > 0:
                        # continue outer "loop1" (next projection)
                        break
                    itemset = seq.getItemset(i, k)
                    beginning = seq.getBeginningOfItemset(k, i)
                    for j in range(beginning, itemset.size()):
                        item = itemset.get(j)
                        postfix = seq.isPostfix(k, i)
                        self._addPair(pairMap, alreadyCounted, seq.getId(), item, postfix)

        sorted_pairs = sorted(pairMap.keys())
        return set(sorted_pairs)

    def createAbstractionFromAPrefix(self, prefix: Pattern, abstraction: Abstraction_Generic) -> Abstraction_Generic:
        return abstraction

    # ---- subpattern checking (ported from your Java)
    def isSubpattern(self, shorter: Pattern, larger: Pattern, index: int, positions: List[int]) -> bool:
        pair = shorter.getIthElement(index)
        itemPair = pair.getItem()
        absPair = pair.getAbstraction()
        previousAbs = shorter.getIthElement(index - 1).getAbstraction() if index > 0 else None
        cancelled = False

        while positions[index] < larger.size():
            if index == 0:
                pos = self.searchForFirstAppearance(larger, positions[index], itemPair)
            else:
                pos = self.findItemPositionInPattern(larger, itemPair, absPair, previousAbs, positions[index], positions[index - 1])

            if pos is not None:
                positions[index] = pos
                if index + 1 < shorter.size():
                    positions[index + 1] = self.increasePosition(positions[index])
                    if self.isSubpattern(shorter, larger, index + 1, positions):
                        return True
                else:
                    return True
            else:
                if index > 0:
                    positions[index - 1] = self.increaseItemset(larger, positions[index - 1])
                cancelled = True
                break

        if index > 0 and not cancelled:
            positions[index - 1] = self.increaseItemset(larger, positions[index - 1])
        return False

    def searchForFirstAppearance(self, p: Pattern, beginning: int, itemPair: Item) -> Optional[int]:
        for i in range(beginning, p.size()):
            if p.getIthElement(i).getItem() == itemPair:
                return i
        return None

    def findItemPositionInPattern(
        self,
        p: Pattern,
        itemPair: Item,
        currentAbs: Abstraction_Generic,
        previousAbs: Abstraction_Generic,
        currentPosition: int,
        previousPosition: int,
    ) -> Optional[int]:
        absq = currentAbs  # should be Abstraction_Qualitative
        if isinstance(absq, Abstraction_Qualitative) and absq.hasEqualRelation():
            return self.searchForInTheSameItemset(p, itemPair, currentPosition)
        else:
            posToSearch = currentPosition
            if not self.areInDifferentItemsets(p, previousPosition, currentPosition):
                posToSearch = self.increaseItemset(p, currentPosition)
            return self.searchForFirstAppearance(p, posToSearch, itemPair)

    def increasePosition(self, beginning: int) -> int:
        return beginning + 1

    def increaseItemset(self, p: Pattern, beginning: int) -> int:
        for i in range(beginning + 1, p.size()):
            qabs = p.getIthElement(i).getAbstraction()
            if isinstance(qabs, Abstraction_Qualitative) and (not qabs.hasEqualRelation()):
                return i
        return p.size()

    def searchForInTheSameItemset(self, pattern: Pattern, itemPair: Item, beginning: int) -> Optional[int]:
        for i in range(beginning, pattern.size()):
            qabs = pattern.getIthElement(i).getAbstraction()
            if isinstance(qabs, Abstraction_Qualitative) and (not qabs.hasEqualRelation()):
                return None
            if pattern.getIthElement(i).getItem() == itemPair:
                return i
        return None

    def areInDifferentItemsets(self, pattern: Pattern, p1: int, p2: int) -> bool:
        for i in range(p1 + 1, min(p2 + 1, pattern.size())):
            qabs = pattern.getIthElement(i).getAbstraction()
            if isinstance(qabs, Abstraction_Qualitative) and (not qabs.hasEqualRelation()):
                return True
        return False


# ----------------------------------------------------------------------
# RecursionCloSpan (main mining loop + pruning + postprocessing)
# ----------------------------------------------------------------------

class RecursionCloSpan:
    def __init__(
        self,
        abstractionCreator: AbstractionCreator,
        saver: Saver,
        minSupportAbsolute: int,
        pseudoDatabase: PseudoSequenceDatabase,
        mapSequenceID: Dict[Item, BitSet],
        findClosedPatterns: bool,
        executePruningMethods: bool,
    ) -> None:
        self.abstractionCreator = abstractionCreator
        self.saver = saver
        self.minSupportAbsolute = int(minSupportAbsolute)
        self.pseudoDatabase = pseudoDatabase
        self.mapSequenceID = mapSequenceID
        self.numberOfFrequentPatterns_ = 0
        self.matchingMap: Dict[int, Dict[int, List[Tuple[Pattern, Trie]]]] = {}
        self.generalTrie = Trie()
        self.findClosedPatterns = findClosedPatterns
        self.executePruningMethods = executePruningMethods

    def execute(self, verbose: bool) -> None:
        keySetList = sorted(list(self.mapSequenceID.keys()))
        if verbose:
            print(f"{len(keySetList)} frequent items")

        for idx, item in enumerate(keySetList, start=1):
            if verbose:
                print(f"Projecting item = {item} ({idx}/{len(keySetList)})")

            projected = self.makePseudoProjections(item, self.pseudoDatabase, self.abstractionCreator.CreateDefaultAbstraction(), True)

            pair = ItemAbstractionPair(item, self.abstractionCreator.CreateDefaultAbstraction())
            prefix = Pattern(pair)
            prefix.setAppearingIn(self.mapSequenceID[item])

            newTrie = Trie()
            newTrie.setAppearingIn(prefix.getAppearingIn())

            prefixNode = TrieNode(pair, newTrie)
            self.generalTrie.addNode(prefixNode)

            if projected is not None:
                self.cloSpanLoop(prefix, prefixNode, 2, projected, verbose)

    def getFrequentPatterns(self) -> List[Pattern]:
        return self.generalTrie.preorderTraversal(None)

    def numberOfFrequentPatterns(self) -> int:
        return self.numberOfFrequentPatterns_

    def clear(self) -> None:
        self.pseudoDatabase.clear()
        self.mapSequenceID.clear()
        self.matchingMap.clear()
        self.generalTrie.removeAll()

    # ---- projection
    def makePseudoProjections(
        self,
        item: Item,
        database: PseudoSequenceDatabase,
        abstraction: Abstraction_Generic,
        firstTime: bool,
    ) -> PseudoSequenceDatabase:
        newDB = PseudoSequenceDatabase()
        numberOfProjectionsSum = 0
        cumulativeSum = 0
        totalElements = 0
        sb = []

        for seq in database.getPseudoSequences():
            alreadyProjected = False
            newSeq: Optional[PseudoSequence] = None
            numberOfProjections = 0
            usedPoints: Set[int] = set()

            for k in range(seq.numberOfProjectionsIncluded()):
                seqSize = seq.size(k)
                for i in range(seqSize):
                    index = seq.indexOf(k, i, item)
                    if index != -1 and (firstTime or abstraction.compute(seq, k, i)):
                        itemsetSize = seq.getSizeOfItemsetAt(k, i)

                        if index != itemsetSize - 1:
                            if not alreadyProjected:
                                newSeq = PseudoSequence.fromPseudo(seq.getRelativeTimeStamp(i, k), seq, i, index + 1, k)
                                usedPoints.add(seq.getFirstItemset(k) + i)
                                if newSeq.size(numberOfProjections) > 0:
                                    numberOfProjections += 1
                                    newDB.addSequence(newSeq)
                                    cumulativeSum += newSeq.size(0)
                                    remaining = newSeq.length(newSeq.numberOfProjectionsIncluded() - 1)
                                    totalElements += remaining
                                    sb.append(str(remaining))
                                alreadyProjected = True
                            else:
                                if (seq.getFirstItemset(k) + i) not in usedPoints:
                                    usedPoints.add(seq.getFirstItemset(k) + i)
                                    newSeq.addProjectionPoint(k, seq.getRelativeTimeStamp(i, k), seq, i, index + 1)
                                    cumulativeSum += newSeq.size(newSeq.numberOfProjectionsIncluded() - 1)
                                    remaining = newSeq.length(newSeq.numberOfProjectionsIncluded() - 1)
                                    totalElements += remaining
                                    sb.append(str(remaining))

                        elif i != seqSize - 1:
                            if not alreadyProjected:
                                newSeq = PseudoSequence.fromPseudo(seq.getRelativeTimeStamp(i, k), seq, i + 1, 0, k)
                                usedPoints.add(seq.getFirstItemset(k) + i)
                                if itemsetSize > 0 and newSeq.size(numberOfProjections) > 0:
                                    numberOfProjections += 1
                                    newDB.addSequence(newSeq)
                                    cumulativeSum += newSeq.size(0)
                                    remaining = newSeq.length(newSeq.numberOfProjectionsIncluded() - 1)
                                    totalElements += remaining
                                    sb.append(str(remaining))
                                alreadyProjected = True
                            else:
                                if (seq.getFirstItemset(k) + i) not in usedPoints:
                                    usedPoints.add(seq.getFirstItemset(k) + i)
                                    newSeq.addProjectionPoint(k, seq.getRelativeTimeStamp(i, k), seq, i + 1, 0)
                                    cumulativeSum += newSeq.size(newSeq.numberOfProjectionsIncluded() - 1)
                                    remaining = newSeq.length(newSeq.numberOfProjectionsIncluded() - 1)
                                    totalElements += remaining
                                    sb.append(str(remaining))

            if newSeq is not None:
                numberOfProjectionsSum += newSeq.numberOfProjectionsIncluded()

        newDB.setCumulativeSum(cumulativeSum)
        newDB.setCumulativeSumNumberOfProjections(numberOfProjectionsSum)
        newDB.setNumberOfElementsProjectedDatabase(totalElements)
        newDB.setElementsProjectedDatabase("".join(sb))
        return newDB

    # ---- main loop
    def cloSpanLoop(self, prefix: Pattern, prefixNode: TrieNode, k: int, context: PseudoSequenceDatabase, verbose: bool) -> None:
        if self.findClosedPatterns and self.executePruningMethods:
            if self.pruneByCheckingProjectedDBSize(prefix, context, prefixNode):
                return

        currentTrie = prefixNode.getChild()
        self.numberOfFrequentPatterns_ += 1

        if context is None or context.size() < self.minSupportAbsolute:
            return

        pairs = self.abstractionCreator.findAllFrequentPairs(context.getPseudoSequences())

        if verbose:
            tab = "\t" * (k - 2)
            print(f"{tab}Projecting prefix = {prefix}")
            print(f"{tab}\tFound {len(pairs)} frequent items in this projection")

        for pair in pairs:
            if pair.getSupport() >= self.minSupportAbsolute:
                newPrefix = prefix.clonePatron()
                newPair = ItemAbstractionPairCreator.getInstance().getItemAbstractionPair(
                    pair.getPar().getItem(),
                    self.abstractionCreator.createAbstractionFromAPrefix(prefix, pair.getPar().getAbstraction()),
                )
                newPrefix.add(newPair)

                projection = self.makePseudoProjections(pair.getPar().getItem(), context, pair.getPar().getAbstraction(), False)
                if projection is not None:
                    newTrie = Trie()
                    newTrie.setAppearingIn(pair.getSequencesID())
                    newNode = TrieNode(newPair, newTrie)
                    currentTrie.addNode(newNode)
                    self.cloSpanLoop(newPrefix, newNode, k + 1, projection, verbose)

    # ---- pruning (ported)
    def pruneByCheckingProjectedDBSize(self, prefix: Pattern, projection: PseudoSequenceDatabase, trieNode: TrieNode) -> bool:
        prefixTrie = trieNode.getChild()
        support = prefixTrie.getSupport()

        key1 = prefixTrie.getSumIdSequences()
        prefixSize = prefix.size()

        key2 = self.key_standardAndSupport(projection, prefixTrie)

        associatedMap = self.matchingMap.get(key1)
        newEntry = (prefix, prefixTrie)

        if associatedMap is None:
            associatedMap = {}
            associatedMap[key2] = [newEntry]
            self.matchingMap[key1] = associatedMap
            return False

        associatedList = associatedMap.get(key2)
        if associatedList is None:
            associatedMap[key2] = [newEntry]
            return False

        superPattern = 0
        i = 0
        while i < len(associatedList):
            p, t = associatedList[i]
            if support == t.getSupport():
                pSize = p.size()
                if pSize != prefixSize:
                    if prefixSize < pSize:
                        if prefix.isSubpattern(self.abstractionCreator, p):
                            prefixTrie.setNodes(t.getNodes())
                            return True
                    else:
                        if p.isSubpattern(self.abstractionCreator, prefix):
                            superPattern += 1
                            prefixTrie.setNodes(t.getNodes())
                            associatedList.pop(i)
                            continue
            i += 1

        associatedList.append(newEntry)
        return superPattern > 0

    @staticmethod
    def key_standardAndSupport(projection: PseudoSequenceDatabase, prefixTrie: Trie) -> int:
        return projection.getNumberOfElementsProjectedDatabase() + prefixTrie.getSupport()

    # ---- postprocessing: remove non-closed patterns
    def removeNonClosedPatterns(self, frequentPatterns: List[Pattern], keepPatterns: bool) -> None:
        print(f"Before removing NonClosed patterns there are {self.numberOfFrequentPatterns_} patterns", file=None)
        self.numberOfFrequentPatterns_ = 0

        grouped: Dict[int, List[Pattern]] = {}
        for p in frequentPatterns:
            grouped.setdefault(p.getSumIdSequences(), []).append(p)

        for lst in grouped.values():
            i = 0
            while i < len(lst):
                j = i + 1
                while j < len(lst):
                    p1 = lst[i]
                    p2 = lst[j]
                    if p1.getSupport() == p2.getSupport() and p1.size() != p2.size():
                        if p1.size() < p2.size():
                            if p1.isSubpattern(self.abstractionCreator, p2):
                                lst.pop(i)
                                i -= 1
                                break
                        else:
                            if p2.isSubpattern(self.abstractionCreator, p1):
                                lst.pop(j)
                                j -= 1
                    j += 1
                i += 1

        for lst in grouped.values():
            self.numberOfFrequentPatterns_ += len(lst)
            if keepPatterns:
                for p in lst:
                    self.saver.savePattern(p)


# ----------------------------------------------------------------------
# AlgoCloSpan
# ----------------------------------------------------------------------

class AlgoCloSpan:
    def __init__(self, minSupRelative: float, creator: AbstractionCreator, findClosedPatterns: bool, executePruningMethods: bool) -> None:
        self.minSupRelative = float(minSupRelative)
        self.minSupAbsolute = 0.0
        self.originalDataset: Optional[SequenceDatabase] = None
        self.saver: Optional[Saver] = None
        self.overallStart = 0.0
        self.overallEnd = 0.0
        self.mainMethodStart = 0.0
        self.mainMethodEnd = 0.0
        self.postProcessingStart = 0.0
        self.postProcessingEnd = 0.0
        self.abstractionCreator = creator
        self.numberOfFrequentPatterns = 0
        self.findClosedPatterns = bool(findClosedPatterns)
        self.executePruningMethods = bool(executePruningMethods)

    def runAlgorithm(self, database: SequenceDatabase, keepPatterns: bool, verbose: bool, outputFilePath: Optional[str], outputSequenceIdentifiers: bool) -> None:
        self.minSupAbsolute = int(math.ceil(self.minSupRelative * database.size()))
        if self.minSupAbsolute == 0:
            self.minSupAbsolute = 1

        MemoryLogger.getInstance().reset()
        self.overallStart = time.time()
        self._cloSpan(database, keepPatterns, verbose, self.findClosedPatterns, self.executePruningMethods, outputFilePath, outputSequenceIdentifiers)
        self.overallEnd = time.time()
        self.saver.finish()

    def _cloSpan(
        self,
        database: SequenceDatabase,
        keepPatterns: bool,
        verbose: bool,
        findClosedPatterns: bool,
        executePruningMethods: bool,
        outputFilePath: Optional[str],
        outputSequenceIdentifiers: bool,
    ) -> None:
        if outputFilePath is None:
            self.saver = SaverIntoMemory(outputSequenceIdentifiers)
        else:
            self.saver = SaverIntoFile(outputFilePath, outputSequenceIdentifiers)

        mapSequenceID = database.getFrequentItems()
        pseudoDatabase = self._projectInitialDatabase(database, mapSequenceID, int(self.minSupAbsolute))

        algorithm = RecursionCloSpan(
            self.abstractionCreator,
            self.saver,
            int(self.minSupAbsolute),
            pseudoDatabase,
            mapSequenceID,
            findClosedPatterns,
            executePruningMethods,
        )

        self.mainMethodStart = time.time()
        algorithm.execute(verbose)
        self.mainMethodEnd = time.time()

        self.numberOfFrequentPatterns = algorithm.numberOfFrequentPatterns()
        MemoryLogger.getInstance().checkMemory()

        if verbose:
            print(f"CLOSPAN: The algorithm takes {int(self.mainMethodEnd - self.mainMethodStart)} seconds and finds {self.numberOfFrequentPatterns} patterns")

        if findClosedPatterns:
            outputPatterns = algorithm.getFrequentPatterns()
            self.postProcessingStart = time.time()
            algorithm.removeNonClosedPatterns(outputPatterns, keepPatterns)
            self.postProcessingEnd = time.time()
            self.numberOfFrequentPatterns = algorithm.numberOfFrequentPatterns()
            if verbose:
                print(f"CLOSPAN: post-processing takes {int(self.postProcessingEnd - self.postProcessingStart)} seconds and finds {self.numberOfFrequentPatterns} Closed patterns")
        else:
            if keepPatterns:
                for p in algorithm.getFrequentPatterns():
                    self.saver.savePattern(p)

        algorithm.clear()
        pseudoDatabase.clear()
        MemoryLogger.getInstance().checkMemory()

    def _projectInitialDatabase(self, database: SequenceDatabase, mapSequenceID: Dict[Item, BitSet], minSupportAbsolute: int) -> PseudoSequenceDatabase:
        initial = PseudoSequenceDatabase()
        for seq in database.getSequences():
            optimized = seq.cloneSequenceMinusItems(mapSequenceID, minSupportAbsolute)
            if optimized.size() != 0:
                initial.addSequence(PseudoSequence(0, optimized, 0, 0))
        return initial

    def printStatistics(self) -> str:
        sb = []
        sb.append("=============  Algorithm - STATISTICS =============\n Total time ~ ")
        sb.append(str(self.getRunningTime()))
        sb.append(" ms\n")
        sb.append(" Frequent sequences count : ")
        sb.append(str(self.numberOfFrequentPatterns))
        sb.append("\n")
        sb.append(" Max memory (mb):")
        sb.append(str(MemoryLogger.getInstance().getMaxMemory()))
        sb.append("\n")
        sb.append(self.saver.print())
        sb.append("\n\n===================================================\n")
        return "".join(sb)

    def getNumberOfFrequentPatterns(self) -> int:
        return self.numberOfFrequentPatterns

    def getRunningTime(self) -> int:
        return int((self.overallEnd - self.overallStart) * 1000)

    def clear(self) -> None:
        if self.originalDataset is not None:
            self.originalDataset.clear()
            self.originalDataset = None
        if self.saver is not None:
            self.saver.clear()
            self.saver = None
        self.abstractionCreator = None


# ----------------------------------------------------------------------
# Main (like MainTestCloSpan_saveToFile.java)
# ----------------------------------------------------------------------

def main() -> None:
    # --------------------------------------------------
    # Set parameters directly here
    # --------------------------------------------------
    input_path = file_to_path("contextPrefixSpan.txt")
    output_path = Path(__file__).resolve().parent / "output_py.txt"

    support = 0.3
    keepPatterns = True
    verbose = False
    findClosedPatterns = True
    executePruningMethods = True
    outputSequenceIdentifiers = False
    # --------------------------------------------------

    output_path.parent.mkdir(parents=True, exist_ok=True)

    abstractionCreator = AbstractionCreator_Qualitative.getInstance()
    db = SequenceDatabase()
    db.loadFile(input_path, support)

    algo = AlgoCloSpan(support, abstractionCreator, findClosedPatterns, executePruningMethods)
    algo.runAlgorithm(db, keepPatterns, verbose, str(output_path), outputSequenceIdentifiers)

    print(f"{algo.getNumberOfFrequentPatterns()} pattern found.")
    print("Input file :", Path(input_path).resolve())
    print("Output file:", output_path.resolve())
    if keepPatterns:
        print(algo.printStatistics())


if __name__ == "__main__":
    main()