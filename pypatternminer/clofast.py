#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import math
import sys
import time
import tracemalloc
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, Iterator, List, Optional


# ======================================================================
# MemoryLogger (SPMF-like)
# ======================================================================
class MemoryLogger:
    _instance: Optional["MemoryLogger"] = None

    def __init__(self) -> None:
        self._max_bytes = 0

    @classmethod
    def getInstance(cls) -> "MemoryLogger":
        if cls._instance is None:
            cls._instance = MemoryLogger()
        return cls._instance

    def reset(self) -> None:
        self._max_bytes = 0

    def checkMemory(self) -> None:
        if tracemalloc.is_tracing():
            _cur, peak = tracemalloc.get_traced_memory()
            self._max_bytes = max(self._max_bytes, peak)

    def getMaxMemory(self) -> float:
        return self._max_bytes / (1024.0 * 1024.0)


# ======================================================================
# Enums
# ======================================================================
class NodeType(Enum):
    toCheck = "toCheck"
    closed = "closed"
    notClosed = "notClosed"
    pruned = "pruned"


class ItemsetNodeType(Enum):
    closed = "closed"
    notClosed = "notClosed"
    intermediate = "intermediate"
    notPromising = "notPromising"
    toCheck = "toCheck"
    notExplore = "notExplore"


# ======================================================================
# ListNode (fixed __slots__ + exact Java behavior)
# ======================================================================
class ListNode:
    """
    Exact port of Java ListNode, but with Python-safe field name `_next`.
    """
    __slots__ = ("_next", "column")

    def __init__(self, c: int, next_node: Optional["ListNode"] = None):
        self.column = int(c)
        self._next: Optional["ListNode"] = next_node

    def getColumn(self) -> int:
        return self.column

    def setNext(self, node: Optional["ListNode"]) -> None:
        self._next = node

    def next(self) -> Optional["ListNode"]:
        return self._next

    def before(self, succ: Optional["ListNode"]) -> Optional["ListNode"]:
        # Java: return first succ where this.column < succ.column
        while succ is not None:
            if self.column < succ.column:
                return succ
            succ = succ._next
        return None

    def before_succs(self, succsNodes: Any, i: int) -> Optional["ListNode"]:
        """
        Java: before(LinkedList<ClosedSequenceNode> succsNodes, Integer i)
        succsNodes is iterable of nodes where node.getVerticalIdList().getElements()[i] exists.
        """
        curr: Optional["ListNode"] = self
        for node in succsNodes:
            if curr is None:
                break
            vil_elem = node.getVerticalIdList().getElements()[i]
            curr = curr.before(vil_elem)
        return curr

    def equal(self, succ: Optional["ListNode"]) -> Optional["ListNode"]:
        # Java: return first succ where this.column == succ.column
        while succ is not None:
            if self.column == succ.column:
                return succ
            succ = succ._next
        return None

    def __str__(self) -> str:
        return f"[ : {self.column}]"


# ======================================================================
# VerticalIdList (exact port)
# ======================================================================
class VerticalIdList:
    __slots__ = ("elements",)

    def __init__(self, elements: List[Optional[ListNode]], absoluteSupport: int):
        # absoluteSupport unused in Java
        self.elements = elements

    def getElements(self) -> List[Optional[ListNode]]:
        return self.elements


# ======================================================================
# SparseIdList (exact port)
# ======================================================================
class SparseIdList:
    class TransactionIds(list):
        def add(self, e: ListNode) -> None:
            if len(self) != 0:
                self[-1].setNext(e)
            self.append(e)

        def __str__(self) -> str:
            return "".join(str(x) for x in self)

    def __init__(self, rows: int):
        self.vector: List[Optional[SparseIdList.TransactionIds]] = [None] * int(rows)
        self.absoluteSupport: int = 0

    def length(self) -> int:
        return len(self.vector)

    def addElement(self, row: int, value: int) -> None:
        if self.vector[row] is None:
            self.vector[row] = SparseIdList.TransactionIds()
            self.absoluteSupport += 1
        self.vector[row].add(ListNode(value))

    def getElement(self, row: int, col: int) -> Optional[ListNode]:
        lst = self.vector[row]
        if lst is not None and col < len(lst):
            return lst[col]
        return None

    @staticmethod
    def IStep(a: "SparseIdList", b: "SparseIdList") -> "SparseIdList":
        sparse = SparseIdList(a.length())
        for i in range(a.length()):
            aNode = a.getElement(i, 0)
            bNode = b.getElement(i, 0)

            while aNode is not None and bNode is not None:
                if aNode.getColumn() == bNode.getColumn():
                    sparse.addElement(i, bNode.getColumn())
                    aNode = aNode.next()
                    bNode = bNode.next()
                elif aNode.getColumn() > bNode.getColumn():
                    bNode = bNode.next()
                else:
                    aNode = aNode.next()
        return sparse

    def getStartingVIL(self) -> VerticalIdList:
        vil_elements: List[Optional[ListNode]] = [None] * self.length()
        for i in range(len(vil_elements)):
            vil_elements[i] = self.getElement(i, 0)
        return VerticalIdList(vil_elements, self.absoluteSupport)

    def getAbsoluteSupport(self) -> int:
        return self.absoluteSupport

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        if not isinstance(other, SparseIdList):
            return False

        for i in range(len(self.vector)):
            these = self.vector[i]
            those = other.vector[i]

            if these is None and those is None:
                continue
            if these is None or those is None:
                return False
            if len(these) != len(those):
                return False
            for j in range(len(these)):
                if these[j].getColumn() != those[j].getColumn():
                    return False
        return True

    def __hash__(self) -> int:
        rows = []
        for lst in self.vector:
            if lst is None:
                rows.append(None)
            else:
                rows.append(tuple(node.getColumn() for node in lst))
        return hash(tuple(rows))

    def __str__(self) -> str:
        out_lines: List[str] = []
        for i in range(len(self.vector)):
            curr = self.vector[i]
            if curr is not None:
                out_lines.append(" ".join(str(curr[j]) for j in range(len(curr))))
            else:
                out_lines.append("null")
        return "\n".join(out_lines) + "\n"


# ======================================================================
# FastDataset (exact port)
# ======================================================================
class FastDataset:
    ITEMSET_SEPARATOR = "-1"
    SEQUENCE_SEPARATOR = "-2"

    def __init__(self, numRows: int, minSup: float, maxSup: float = 1.0):
        self.itemSILMap: Dict[str, SparseIdList] = {}
        self.numRows = int(numRows)
        self.minSup = float(minSup)
        self.maxSup = float(maxSup)

        self.absMinSup = self.absoluteSupport(self.minSup, self.numRows)
        if self.absMinSup == 0:
            self.absMinSup = 1

        # Java sometimes passes Float.MAX_VALUE => no upper bound in practice
        if math.isinf(self.maxSup) or self.maxSup > 1e20:
            self.absMaxSup = self.numRows
        else:
            self.absMaxSup = self.absoluteSupport(self.maxSup, self.numRows)
            if self.absMaxSup == 0:
                self.absMaxSup = 1

    def computeFrequentItems(self) -> None:
        new_map: Dict[str, SparseIdList] = {}
        for item, sil in self.itemSILMap.items():
            supp = sil.getAbsoluteSupport()
            if supp >= self.absMinSup and supp <= self.absMaxSup:
                new_map[item] = sil
        # TreeMap ordering by key
        self.itemSILMap = dict(sorted(new_map.items(), key=lambda kv: kv[0]))

    def getFrequentItemsets(self) -> Dict[str, SparseIdList]:
        return self.itemSILMap

    def getSparseIdList(self, item: str) -> Optional[SparseIdList]:
        return self.itemSILMap.get(item)

    def getNumRows(self) -> int:
        return self.numRows

    def getAbsMinSup(self) -> int:
        return self.absMinSup

    def getAbsMaxSup(self) -> int:
        return self.absMaxSup

    @staticmethod
    def fromPrefixspanSource(path: str, relativeMinSupport: float, relativeMaxSupport: float) -> "FastDataset":
        # count rows (skip comments/metadata/empty)
        num_rows = 0
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.strip()
                if (not line) or line.startswith("#") or line[0] in ("%","@"):
                    continue
                num_rows += 1

        ds = FastDataset(num_rows, relativeMinSupport, relativeMaxSupport)

        lineNumber = 0
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.strip()
                if (not line) or line.startswith("#") or line[0] in ("%","@"):
                    continue
                if len(line) == 0:
                    continue

                transID = 1
                for token in line.split():
                    if token == FastDataset.ITEMSET_SEPARATOR:
                        transID += 1
                        continue
                    if token == FastDataset.SEQUENCE_SEPARATOR:
                        break

                    if token not in ds.itemSILMap:
                        ds.itemSILMap[token] = SparseIdList(ds.numRows)
                    ds.itemSILMap[token].addElement(lineNumber, transID)

                lineNumber += 1

        ds.computeFrequentItems()
        return ds

    def absoluteSupport(self, relativeSupport: float, totalCount: int) -> int:
        return int(math.ceil(relativeSupport * totalCount))


# ======================================================================
# Itemset (exact port)
# ======================================================================
class Itemset:
    __slots__ = ("elements",)

    def __init__(self, *items: str, collection: Optional[Iterable[str]] = None):
        self.elements: List[str] = []
        if collection is not None:
            self.elements.extend(list(collection))
        if items:
            self.elements.extend(list(items))

    def addItem(self, *items: str) -> None:
        for item in items:
            self.elements.append(item)

    def clone(self) -> "Itemset":
        other = Itemset()
        other.elements.extend(self.elements)
        return other

    def contains(self, item_or_itemset) -> bool:
        if isinstance(item_or_itemset, Itemset):
            other: Itemset = item_or_itemset
            for s in other:
                if s not in self.elements:
                    return False
            return True
        else:
            return str(item_or_itemset) in self.elements

    def size(self) -> int:
        return len(self.elements)

    def concatenate(self) -> str:
        return " ".join(self.elements).strip()

    def __iter__(self) -> Iterator[str]:
        return iter(self.elements)

    def getLast(self) -> str:
        return self.elements[-1]

    def getElements(self) -> List[str]:
        return self.elements

    def compareTo(self, other: "Itemset") -> int:
        a = self.concatenate()
        b = other.concatenate()
        if a < b:
            return -1
        if a > b:
            return 1
        return 0

    def __lt__(self, other: "Itemset") -> bool:
        return self.concatenate() < other.concatenate()

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        if not isinstance(other, Itemset):
            return False
        return self.elements == other.elements

    def __hash__(self) -> int:
        return hash(tuple(self.elements))

    def __str__(self) -> str:
        return self.concatenate()


# ======================================================================
# Sequence (exact port)
# ======================================================================
class Sequence:
    __slots__ = ("elements",)

    def __init__(self, *itemsets: Itemset):
        self.elements: List[Itemset] = []
        for it in itemsets:
            self.elements.append(it)

    def add(self, element: Itemset) -> None:
        self.elements.append(element)

    def getLastItemset(self) -> Itemset:
        return self.elements[-1]

    def getLastItem(self) -> str:
        return self.getLastItemset().getLast()

    def length(self) -> int:
        return len(self.elements)

    def clone(self) -> "Sequence":
        other = Sequence()
        for it in self.elements:
            other.add(it.clone())
        return other

    def __iter__(self) -> Iterator[Itemset]:
        return iter(self.elements)

    def getElements(self) -> List[Itemset]:
        return self.elements

    def containsItemset(self, itemset: Itemset) -> bool:
        return any(it.contains(itemset) for it in self.elements)

    def contains(self, other: "Sequence") -> bool:
        if len(self.elements) < len(other.elements):
            return False
        matchIndex = 0
        for other_it in other:
            nextIndex = -1
            for i in range(matchIndex, len(self.elements)):
                if self.elements[i].contains(other_it):
                    nextIndex = i
                    break
            if nextIndex == -1:
                return False
            matchIndex = nextIndex + 1
        return True

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        if not isinstance(other, Sequence):
            return False
        return self.elements == other.elements

    def __hash__(self) -> int:
        return hash(tuple(self.elements))

    def __str__(self) -> str:
        parts: List[str] = []
        for it in self.elements:
            parts.append(it.concatenate())
            parts.append(" -1 ")
        return "".join(parts) + "-2"


# ======================================================================
# ClosedItemsetNode / Tree (exact ports)
# ======================================================================
@dataclass
class ClosedItemsetNode:
    position: int = -1
    children: List["ClosedItemsetNode"] = field(default_factory=list)
    parent: Optional["ClosedItemsetNode"] = None
    itemset: Optional[Itemset] = None
    type: ItemsetNodeType = None
    sil: Optional[SparseIdList] = None

    def __post_init__(self) -> None:
        if self.type is None:
            self.type = ItemsetNodeType.toCheck

    @classmethod
    def make(cls, parent: "ClosedItemsetNode", itemset: Itemset, sil: SparseIdList, position: int) -> "ClosedItemsetNode":
        return cls(position=position, parent=parent, itemset=itemset, sil=sil)

    def getChildren(self) -> List["ClosedItemsetNode"]:
        return self.children

    def getParent(self) -> Optional["ClosedItemsetNode"]:
        return self.parent

    def getPosition(self) -> int:
        return self.position

    def getAbsoluteSupport(self) -> int:
        return self.sil.getAbsoluteSupport() if self.sil is not None else 0

    def getItemset(self) -> Itemset:
        return self.itemset

    def getType(self) -> ItemsetNodeType:
        return self.type

    def setType(self, t: ItemsetNodeType) -> None:
        self.type = t

    def getIdList(self) -> SparseIdList:
        return self.sil

    def __lt__(self, other: "ClosedItemsetNode") -> bool:
        return self.itemset < other.itemset

    def __str__(self) -> str:
        return str(self.itemset) if self.itemset is not None else ""


class ClosedItemsetTree:
    def __init__(self) -> None:
        self.root: ClosedItemsetNode = ClosedItemsetNode()
        self.closedTable: Dict[int, List[Itemset]] = {}

    def addChild(self, parent: ClosedItemsetNode, itemset: Itemset, sil: SparseIdList, position: int) -> ClosedItemsetNode:
        newNode = ClosedItemsetNode.make(parent=parent, itemset=itemset, sil=sil, position=position)
        parent.getChildren().append(newNode)
        return newNode

    def getRoot(self) -> ClosedItemsetNode:
        return self.root


# ======================================================================
# ClosedSequenceNode / Tree (exact ports)
# ======================================================================
@dataclass
class ClosedSequenceNode:
    vil: Optional[VerticalIdList] = None
    children: List["ClosedSequenceNode"] = field(default_factory=list)
    parent: Optional["ClosedSequenceNode"] = None
    sequence: Optional[Sequence] = None
    type: NodeType = NodeType.toCheck
    absoluteSupport: int = 0

    @classmethod
    def make_root(cls, sizePositionList: int) -> "ClosedSequenceNode":
        return cls(vil=None, parent=None, sequence=Sequence(), type=NodeType.toCheck, absoluteSupport=int(sizePositionList))

    @classmethod
    def make(cls, parent: "ClosedSequenceNode", sequence: Sequence, vil: VerticalIdList, absoluteSupport: int) -> "ClosedSequenceNode":
        return cls(vil=vil, parent=parent, sequence=sequence, type=NodeType.toCheck, absoluteSupport=int(absoluteSupport))

    def getChildren(self) -> List["ClosedSequenceNode"]:
        return self.children

    def getParent(self) -> Optional["ClosedSequenceNode"]:
        return self.parent

    def getVerticalIdList(self) -> VerticalIdList:
        return self.vil

    def getSequence(self) -> Sequence:
        return self.sequence

    def getType(self) -> NodeType:
        return self.type

    def setType(self, t: NodeType) -> None:
        self.type = t

    def getAbsoluteSupport(self) -> int:
        return self.absoluteSupport

    def containsLastItemset(self, n: "ClosedSequenceNode") -> bool:
        if self.sequence.getLastItemset() == n.sequence.getLastItemset():
            return False
        return self.sequence.getLastItemset().contains(n.getSequence().getLastItemset())

    def __str__(self) -> str:
        return f"{self.sequence} #SUP: {self.absoluteSupport}"


class ClosedSequenceTree:
    def __init__(self, sizePosList: int):
        self.root: ClosedSequenceNode = ClosedSequenceNode.make_root(sizePosList)

    def addChild(self, parent: ClosedSequenceNode, sequence: Sequence, vil: VerticalIdList, support: int) -> ClosedSequenceNode:
        newNode = ClosedSequenceNode.make(parent=parent, sequence=sequence, vil=vil, absoluteSupport=support)
        parent.getChildren().append(newNode)
        return newNode

    def getRoot(self) -> ClosedSequenceNode:
        return self.root

    @staticmethod
    def visit(closedTree: "ClosedSequenceTree") -> List[ClosedSequenceNode]:
        q: Deque[ClosedSequenceNode] = deque()
        res: List[ClosedSequenceNode] = []
        q.extend(closedTree.getRoot().getChildren())
        while q:
            current = q.popleft()
            res.append(current)
            q.extend(current.getChildren())
        return res


# ======================================================================
# AlgoCloFast (ported from your Java AlgoCloFast.java)
# ======================================================================
class AlgoCloFast:
    def __init__(self) -> None:
        self.ds: Optional[FastDataset] = None
        self.outputTree: Optional[ClosedSequenceTree] = None

        self.startTimestamp = 0
        self.endTimestamp = 0

        self.patternCount = 0
        self.closedPatternCount = 0
        self.prunedPatternCount = 0

    def run(self) -> None:
        closedNodes = self.generateClosedItemsets()
        MemoryLogger.getInstance().checkMemory()
        self.outputTree = self.generateClosedSequences(closedNodes)

    # ---------------- Closed itemsets ----------------
    def generateClosedItemsets(self) -> List[ClosedItemsetNode]:
        tree = ClosedItemsetTree()
        closedTable: Dict[int, List[ClosedItemsetNode]] = {}

        queue: Deque[ClosedItemsetNode] = deque()
        pos = 0

        for item_str, sil in self.ds.getFrequentItemsets().items():
            node = tree.addChild(tree.getRoot(), Itemset(item_str), sil, pos)
            pos += 1
            queue.append(node)

        while queue:
            node = queue.popleft()
            self.closedItemsetExtension(tree, node, closedTable)
            queue.extend(node.getChildren())

        result: List[ClosedItemsetNode] = []
        for lst in closedTable.values():
            result.extend(lst)

        result.sort()
        return result

    def closedItemsetExtension(self, tree: ClosedItemsetTree, node: ClosedItemsetNode,
                               closedTable: Dict[int, List[ClosedItemsetNode]]) -> None:
        sentinel = False
        pos = 0

        siblings = node.getParent().getChildren()

        for i in range(node.getPosition() + 1, len(siblings)):
            rightBrother = siblings[i]
            sil = SparseIdList.IStep(node.getIdList(), rightBrother.getIdList())

            if sil.getAbsoluteSupport() >= self.ds.getAbsMinSup():
                if sil.getAbsoluteSupport() == node.getIdList().getAbsoluteSupport() and sil == node.getIdList():
                    node.setType(ItemsetNodeType.intermediate)
                    sentinel = True

                itemset = node.getItemset().clone()
                itemset.addItem(rightBrother.getItemset().getLast())
                tree.addChild(node, itemset, sil, pos)
                pos += 1

        if not sentinel:
            if not self.leftcheck(node, closedTable):
                node.setType(ItemsetNodeType.closed)
                supp = node.getAbsoluteSupport()
                closedTable.setdefault(supp, []).append(node)

    def leftcheck(self, nodeToCheck: ClosedItemsetNode, closedTable: Dict[int, List[ClosedItemsetNode]]) -> bool:
        nodeSupp = nodeToCheck.getIdList().getAbsoluteSupport()
        toRemove: List[ClosedItemsetNode] = []

        lst = closedTable.get(nodeSupp, [])

        if nodeSupp in closedTable:
            for candidateClosed in lst:
                if candidateClosed.getItemset().contains(nodeToCheck.getItemset()):
                    return True

                if nodeToCheck.getItemset().contains(candidateClosed.getItemset()) and nodeToCheck.getIdList() == candidateClosed.getIdList():
                    toRemove.append(candidateClosed)
                    candidateClosed.setType(ItemsetNodeType.notClosed)

        for r in toRemove:
            if r in lst:
                lst.remove(r)

        return False

    # ---------------- Closed sequences ----------------
    def generateClosedSequences(self, closedNodes: List[ClosedItemsetNode]) -> ClosedSequenceTree:
        tree = ClosedSequenceTree(self.ds.getAbsMinSup())

        for node in closedNodes:
            tree.addChild(
                tree.getRoot(),
                Sequence(node.getItemset()),
                node.getIdList().getStartingVIL(),
                node.getAbsoluteSupport()
            )

        for csn in tree.getRoot().getChildren():
            self.closedSequenceExtension(tree, csn)

        return tree

    def closedSequenceExtension(self, tree: ClosedSequenceTree, csn: ClosedSequenceNode) -> None:
        if csn.getType() == NodeType.toCheck:
            if self.closedByBackwardExtension(tree, csn):
                if csn.getType() != NodeType.pruned:
                    csn.setType(NodeType.notClosed)
            else:
                csn.setType(NodeType.closed)

        if csn.getType() == NodeType.pruned:
            return

        csnListNode = csn.getVerticalIdList().getElements()
        brothers = csn.getParent().getChildren()
        count = 0

        for b in brothers:
            newPosList: List[Optional[ListNode]] = [None] * len(csnListNode)
            bListNode = b.getVerticalIdList().getElements()

            for i in range(len(csnListNode)):
                listNode = csnListNode[i]
                listNodeBrother = bListNode[i]

                if listNode is None or listNodeBrother is None:
                    continue

                if listNodeBrother.getColumn() > listNode.getColumn():
                    newPosList[i] = listNodeBrother
                    count += 1
                else:
                    while listNodeBrother is not None and listNodeBrother.getColumn() <= listNode.getColumn():
                        listNodeBrother = listNodeBrother.next()
                    if listNodeBrother is not None:
                        newPosList[i] = listNodeBrother
                        count += 1

            if count >= self.ds.getAbsMinSup():
                sequence = csn.getSequence().clone()
                sequence.add(b.getSequence().getLastItemset())
                tree.addChild(csn, sequence, VerticalIdList(newPosList, count), count)

                if count == csn.getAbsoluteSupport():
                    csn.setType(NodeType.notClosed)

            count = 0

        for n in csn.getChildren():
            self.closedSequenceExtension(tree, n)

    def closedByBackwardExtension(self, tree: ClosedSequenceTree, csn: ClosedSequenceNode) -> bool:
        validRows: List[int] = []
        elems = csn.getVerticalIdList().getElements()
        for i in range(len(elems)):
            if elems[i] is not None:
                validRows.append(i)

        succsNodes: List[ClosedSequenceNode] = [csn]
        currentNode = csn

        while currentNode.getParent() != tree.getRoot():
            predNode = currentNode.getParent()
            betweenNodes = predNode.getChildren()

            for betweenNode in betweenNodes:
                if betweenNode.getType() == NodeType.pruned:
                    continue
                if betweenNode is csn:
                    continue

                if betweenNode.containsLastItemset(succsNodes[0]):
                    if self.itemsetClosure(betweenNode, succsNodes, validRows, csn):
                        return True

                if self.sequenceClosure(predNode, betweenNode, succsNodes, validRows, csn):
                    return True

            succsNodes.insert(0, predNode)
            currentNode = predNode

        predNodes = currentNode.getParent().getChildren()
        for pred in predNodes:
            if pred.containsLastItemset(succsNodes[0]):
                if self.itemsetClosure(pred, succsNodes, validRows, csn):
                    return True
            if self.sequenceClosure_head(pred, succsNodes, validRows, csn):
                return True

        return False

    def sequenceClosure_head(self, predNode: ClosedSequenceNode, succsNodes: List[ClosedSequenceNode],
                            validRows: List[int], csn: ClosedSequenceNode) -> bool:
        predVil = predNode.getVerticalIdList().getElements()
        candidateClosureVil: List[Optional[ListNode]] = [None] * len(predVil)

        for i in validRows:
            if predVil[i] is None:
                return False

            closureNode = predVil[i].before_succs(succsNodes, i)
            if closureNode is None:
                return False
            candidateClosureVil[i] = closureNode

        if self.sameVil(candidateClosureVil, csn.getVerticalIdList().getElements(), validRows):
            csn.setType(NodeType.pruned)

        return True

    def sequenceClosure(self, predNode: ClosedSequenceNode, backwardNode: ClosedSequenceNode,
                        succsNodes: List[ClosedSequenceNode], validRows: List[int], csn: ClosedSequenceNode) -> bool:
        predVil = predNode.getVerticalIdList().getElements()
        backwardVil = backwardNode.getVerticalIdList().getElements()

        candidateClosureVil: List[Optional[ListNode]] = [None] * len(predVil)

        for i in validRows:
            if backwardVil[i] is None:
                return False
            if predVil[i].getColumn() > backwardVil[i].getColumn():
                return False

            closureNode = backwardVil[i].before_succs(succsNodes, i)
            if closureNode is None:
                return False
            candidateClosureVil[i] = closureNode

        if self.sameVil(candidateClosureVil, csn.getVerticalIdList().getElements(), validRows):
            csn.setType(NodeType.pruned)

        return True

    def sameVil(self, candidateClosureVil: List[Optional[ListNode]],
                positionsList: List[Optional[ListNode]], validColumns: List[int]) -> bool:
        for i in validColumns:
            if candidateClosureVil[i].getColumn() != positionsList[i].getColumn():
                return False
        return True

    def itemsetClosure(self, backwardNode: ClosedSequenceNode, succsNodes: List[ClosedSequenceNode],
                       validRows: List[int], csn: ClosedSequenceNode) -> bool:
        backwardVil = backwardNode.getVerticalIdList().getElements()
        candidateClosureVil: List[Optional[ListNode]] = [None] * len(backwardVil)

        for i in validRows:
            if backwardVil[i] is None:
                return False

            closureNode = self.equal(backwardVil[i], succsNodes, i)
            if closureNode is None:
                return False
            candidateClosureVil[i] = closureNode

        if self.sameVil(candidateClosureVil, csn.getVerticalIdList().getElements(), validRows):
            csn.setType(NodeType.pruned)

        return True

    def equal(self, node: ListNode, succNodes: List[ClosedSequenceNode], i: int) -> Optional[ListNode]:
        curr = node

        succ = succNodes[0].getVerticalIdList().getElements()[i]
        succ = curr.equal(succ)
        if succ is None:
            return None

        for n in succNodes[1:]:
            succ = succ.before(n.getVerticalIdList().getElements()[i])
            if succ is None:
                return None
        return succ

    # ---------------- Output / API ----------------
    def getClosedFrequentNodes(self) -> List[ClosedSequenceNode]:
        return ClosedSequenceTree.visit(self.outputTree)

    def writePatterns(self, outputFile: Path) -> None:
        outputFile.parent.mkdir(parents=True, exist_ok=True)
        with outputFile.open("w", encoding="utf-8") as out:
            nodes = self.getClosedFrequentNodes()

            countClosed = 0
            countPruned = 0

            for node in nodes:
                if node.getType() == NodeType.closed:
                    out.write(str(node) + "\n")
                    countClosed += 1
                elif node.getType() == NodeType.pruned:
                    countPruned += 1

        self.closedPatternCount = countClosed
        self.prunedPatternCount = countPruned
        self.patternCount = len(nodes)

    def runAlgorithm(self, inputFile: str, outputPath: str, minsup: float) -> None:
        self.startTimestamp = int(time.time() * 1000)
        MemoryLogger.getInstance().reset()
        tracemalloc.start()

        self.ds = FastDataset.fromPrefixspanSource(inputFile, minsup, float("inf"))
        self.run()
        self.writePatterns(Path(outputPath))

        MemoryLogger.getInstance().checkMemory()
        self.endTimestamp = int(time.time() * 1000)
        tracemalloc.stop()

    def printStatistics(self) -> None:
        r = []
        r.append("=============  Algorithm CloFast v2.29 - STATISTICS =============")
        r.append(f"Number of closed Patterns found : {self.closedPatternCount}")
        r.append(f"  Pattern count : {self.patternCount}")
        r.append(f"  Pruned Pattern count : {self.prunedPatternCount}")
        r.append(f"Total time: {(self.endTimestamp - self.startTimestamp) / 1000.0:.3f} s")
        r.append(f"Max memory (mb) : {MemoryLogger.getInstance().getMaxMemory():.3f}")
        r.append("===================================================")
        print("\n".join(r))


# ======================================================================
# Main (LAPIN vibe: no args runs default dataset)
# ======================================================================
def file_to_path(filename: str) -> str:
    here = Path(__file__).resolve().parent
    p1 = here / filename
    if p1.exists():
        return str(p1)
    p2 = Path("Java") / "src" / "clofast" / filename
    if p2.exists():
        return str(p2.resolve())
    p3 = Path.cwd() / filename
    if p3.exists():
        return str(p3.resolve())
    raise FileNotFoundError(f"Could not locate {filename}")


def main() -> None:
    # Default run if no args (no CLI error)
    if len(sys.argv) == 1:
        inputFile = file_to_path("contextPrefixSpan.txt")
        outputPath = str(Path(__file__).resolve().parent / "output_py.txt")
        minsup = 0.5
        algo = AlgoCloFast()
        algo.runAlgorithm(inputFile, outputPath, minsup)
        algo.printStatistics()
        return

    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", required=True, help="SPMF input file")
    ap.add_argument("-o", "--output", required=True, help="output file")
    ap.add_argument("-s", "--support", required=True, type=float, help="minsup (relative)")
    args = ap.parse_args()

    algo = AlgoCloFast()
    algo.runAlgorithm(args.input, args.output, args.support)
    algo.printStatistics()


if __name__ == "__main__":
    main()
