# clasp.py (single file) - ClaSP port (Tin version)
# Output: Java/src/clasp/output_py.txt

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set
import math
import time

# ----------------------------------------------------------------------
# MemoryLogger (minimal placeholder)
# ----------------------------------------------------------------------

class MemoryLogger:
    _instance: Optional["MemoryLogger"] = None

    def __init__(self) -> None:
        self._max_mem_mb = 0.0

    @classmethod
    def getInstance(cls) -> "MemoryLogger":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def reset(self) -> None:
        self._max_mem_mb = 0.0

    def checkMemory(self) -> None:
        self._max_mem_mb = max(self._max_mem_mb, 0.0)

    def getMaxMemory(self) -> float:
        return self._max_mem_mb


# ----------------------------------------------------------------------
# Item (port of Item.java for Integer ids)
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class Item:
    value: int

    def getId(self) -> int:
        return self.value

    def __lt__(self, other: "Item") -> bool:
        return self.value < other.value

    def __str__(self) -> str:
        return str(self.value)


class ItemFactory:
    def __init__(self) -> None:
        self._cache: Dict[int, Item] = {}

    def getItem(self, v: int) -> Item:
        if v not in self._cache:
            self._cache[v] = Item(v)
        return self._cache[v]


# ----------------------------------------------------------------------
# Abstractions (exact ports)
# ----------------------------------------------------------------------

class Abstraction_Generic:
    def toStringToFile(self) -> str:
        return str(self)

    def compare_key(self) -> tuple:
        raise NotImplementedError

    def __lt__(self, other: "Abstraction_Generic") -> bool:
        return self.compare_key() < other.compare_key()


class Abstraction_Qualitative(Abstraction_Generic):
    _pool: Dict[bool, "Abstraction_Qualitative"] = {}

    def __init__(self, equalRelation: bool):
        self._hasEqualRelation = bool(equalRelation)

    @classmethod
    def create(cls, hasEqualRelation: bool) -> "Abstraction_Qualitative":
        if hasEqualRelation not in cls._pool:
            cls._pool[hasEqualRelation] = cls(hasEqualRelation)
        return cls._pool[hasEqualRelation]

    def hasEqualRelation(self) -> bool:
        return self._hasEqualRelation

    # Java compareTo: false < true
    def compare_key(self) -> tuple:
        return (1 if self._hasEqualRelation else 0,)

    def __str__(self) -> str:
        # Java toString: if NOT equal => " ->"
        return "" if self._hasEqualRelation else " ->"

    def toStringToFile(self) -> str:
        # Java toStringToFile: if NOT equal => " -1"
        return "" if self._hasEqualRelation else " -1"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Abstraction_Qualitative) and self._hasEqualRelation == other._hasEqualRelation

    def __hash__(self) -> int:
        return hash(self._hasEqualRelation)


class AbstractionCreator:
    def createDefaultAbstraction(self) -> Abstraction_Generic:
        raise NotImplementedError


class AbstractionCreator_Qualitative(AbstractionCreator):
    _instance: Optional["AbstractionCreator_Qualitative"] = None

    @classmethod
    def getInstance(cls) -> "AbstractionCreator_Qualitative":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def createDefaultAbstraction(self) -> Abstraction_Generic:
        return Abstraction_Qualitative.create(False)

    def crearAbstraccion(self, same_itemset: bool) -> Abstraction_Generic:
        # same_itemset=True => equal relation
        return Abstraction_Qualitative.create(bool(same_itemset))


# ----------------------------------------------------------------------
# ItemAbstractionPair (exact compareTo + toStringToFile behavior)
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class ItemAbstractionPair:
    item: Item
    abstraction: Abstraction_Generic

    def getAbstraction(self) -> Abstraction_Generic:
        return self.abstraction

    def getItem(self) -> Item:
        return self.item

    def __str__(self) -> str:
        if isinstance(self.abstraction, Abstraction_Qualitative):
            a = str(self.abstraction)
            return f"{a}{' ' if a else ''}{self.item}"
        return f"{self.item}{self.abstraction} "

    def toStringToFile(self) -> str:
        if isinstance(self.abstraction, Abstraction_Qualitative):
            return f"{self.abstraction.toStringToFile()} {self.item}".rstrip()
        return f"{self.item}{self.abstraction} "

    # Java compareTo: item first then abstraction
    def __lt__(self, other: "ItemAbstractionPair") -> bool:
        if self.item.value != other.item.value:
            return self.item.value < other.item.value
        return self.abstraction < other.abstraction


class ItemAbstractionPairCreator:
    _instance: Optional["ItemAbstractionPairCreator"] = None

    @classmethod
    def getInstance(cls) -> "ItemAbstractionPairCreator":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def getItemAbstractionPair(self, item: Item, abstraction: Abstraction_Generic) -> ItemAbstractionPair:
        return ItemAbstractionPair(item=item, abstraction=abstraction)


# ----------------------------------------------------------------------
# Position (port)
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class Position:
    itemsetIndex: int
    itemIndex: int

    def getItemIndex(self) -> int:
        return self.itemIndex

    def getItemsetIndex(self) -> int:
        return self.itemsetIndex


# ----------------------------------------------------------------------
# IDListStandard_Map (Tin port)
# ----------------------------------------------------------------------

class IDListStandard_Map:
    originalSizeOfSequences: Dict[int, int] = {}

    def __init__(self, sequencePositionsEntries: Optional[Dict[int, List[Position]]] = None):
        self.sequencePositionsEntries: Dict[int, List[Position]] = sequencePositionsEntries or {}
        self.sequences: Set[int] = set(self.sequencePositionsEntries.keys())
        self.totalElementsAfterPrefixes: int = 0

    def join(self, idList: "IDListStandard_Map", equals: bool, minSupport: int) -> "IDListStandard_Map":
        intersection: Dict[int, List[Position]] = {}
        newSequences: Set[int] = set()
        dif = [0]

        for sid, pos_other in idList.sequencePositionsEntries.items():
            if equals:
                positions = self._equalOperation(sid, pos_other, dif)
            else:
                positions = self._laterOperation(sid, pos_other, dif)

            if positions is not None:
                intersection[sid] = positions
                newSequences.add(sid)

        output = IDListStandard_Map(intersection)
        output.sequences = newSequences
        output.setTotalElementsAfterPrefixes(dif[0])
        return output

    def getSupport(self) -> int:
        return len(self.sequences)

    def addAppearance(self, sid: int, positionItem: Position) -> None:
        eids = self.sequencePositionsEntries.get(sid)
        if eids is None:
            eids = []
        if positionItem not in eids:
            eids.append(positionItem)
            self.sequencePositionsEntries[sid] = eids
            self.sequences.add(sid)

    def setAppearingIn(self, obj: Any) -> None:
        name = obj.__class__.__name__
        if name == "Trie":
            obj.setAppearingIn(set(self.sequences))
        elif name == "Pattern":
            obj.setAppearingIn(set(self.sequences))

    def getTotalElementsAfterPrefixes(self) -> int:
        return self.totalElementsAfterPrefixes

    def setTotalElementsAfterPrefixes(self, i: int) -> None:
        self.totalElementsAfterPrefixes = int(i)

    def SetOriginalSequenceLengths(self, mp: Dict[int, int]) -> None:
        IDListStandard_Map.originalSizeOfSequences = mp

    def _laterOperation(self, sid: int, pos_other: List[Position], dif: List[int]) -> Optional[List[Position]]:
        pos_mine = self.sequencePositionsEntries.get(sid)
        if not pos_mine:
            return None

        result: List[Position] = []
        index = -1
        mine_first_eid = pos_mine[0].getItemsetIndex()

        for i in range(len(pos_other)):
            if mine_first_eid < pos_other[i].getItemsetIndex():
                index = i
                break

        if index >= 0:
            for i in range(index, len(pos_other)):
                pos = pos_other[i]
                result.append(pos)
                if i == index:
                    orig = IDListStandard_Map.originalSizeOfSequences.get(sid, 0)
                    dif[0] += (orig - pos.getItemIndex())

        return result if result else None

    def _equalOperation(self, sid: int, pos_other: List[Position], dif: List[int]) -> Optional[List[Position]]:
        pos_mine = self.sequencePositionsEntries.get(sid)
        if not pos_mine:
            return None

        result: List[Position] = []
        beginningIndex = 0

        if len(pos_mine) <= len(pos_other):
            listToExplore = pos_mine
            listToSearch = pos_other
        else:
            listToExplore = pos_other
            listToSearch = pos_mine

        twoFirstEventsEqual = False

        for eid in listToExplore:
            for i in range(beginningIndex, len(listToSearch)):
                cur = listToSearch[i]
                comp = cur.getItemsetIndex() - eid.getItemsetIndex()
                if comp >= 0:
                    if comp == 0:
                        chosen = eid if eid.getItemIndex() > cur.getItemIndex() else cur
                        result.append(chosen)
                        if not twoFirstEventsEqual:
                            orig = IDListStandard_Map.originalSizeOfSequences.get(sid, 0)
                            dif[0] += (orig - chosen.getItemIndex())
                        twoFirstEventsEqual = True
                        beginningIndex = i + 1
                    break

        return result if result else None


# ----------------------------------------------------------------------
# Pattern (UPDATED isSubpattern() to match ClaSP qualitative semantics)
# ----------------------------------------------------------------------

@dataclass
class Pattern:
    _elements: List[ItemAbstractionPair] = field(default_factory=list)
    _appearing_in: Set[int] = field(default_factory=set)
    support: int = 0

    def __init__(self, elements: Optional[Any] = None):
        if elements is None:
            self._elements = []
        elif isinstance(elements, ItemAbstractionPair):
            self._elements = [elements]
        else:
            self._elements = list(elements)
        self._appearing_in = set()
        self.support = 0

    def clonePatron(self) -> "Pattern":
        p = Pattern(list(self._elements))
        p._appearing_in = set(self._appearing_in)
        p.support = self.support
        return p

    def add(self, pair: ItemAbstractionPair) -> None:
        self._elements.append(pair)

    def concatenate(self, pair: ItemAbstractionPair) -> "Pattern":
        newp = self.clonePatron()
        newp.add(pair)
        return newp

    def size(self) -> int:
        return len(self._elements)

    def getIthElement(self, i: int) -> ItemAbstractionPair:
        return self._elements[i]

    def getElements(self) -> List[ItemAbstractionPair]:
        return self._elements

    def setAppearingIn(self, sids: Set[int]) -> None:
        self._appearing_in = set(sids)

    def getAppearingIn(self) -> Set[int]:
        return set(self._appearing_in)

    # --- NEW: itemset conversion for subpattern check ---
    def _to_itemsets(self) -> List[Set[int]]:
        """
        Convert pattern elements into a list of itemsets (each itemset is a set of item ids),
        using Abstraction_Qualitative semantics:
          equalRelation=True  -> same itemset
          equalRelation=False -> new itemset (a "-1" boundary)
        """
        if not self._elements:
            return []

        itemsets: List[Set[int]] = []
        cur: Set[int] = set()
        cur.add(self._elements[0].getItem().getId())

        for pair in self._elements[1:]:
            absq = pair.getAbstraction()
            is_equal = isinstance(absq, Abstraction_Qualitative) and absq.hasEqualRelation()
            if not is_equal:
                itemsets.append(cur)
                cur = set()
            cur.add(pair.getItem().getId())

        itemsets.append(cur)
        return itemsets

    # --- UPDATED: ClaSP-style subpattern check ---
    def isSubpattern(self, abstractionCreator: AbstractionCreator, other: "Pattern") -> bool:
        """
        True if self is a sequential subpattern of other (qualitative abstraction).
        Each itemset of self must be included in some later/equal-position itemset of other, in order.
        """
        a_sets = self._to_itemsets()
        b_sets = other._to_itemsets()

        if not a_sets:
            return True
        if len(a_sets) > len(b_sets):
            return False

        j = 0
        for a in a_sets:
            found = False
            while j < len(b_sets):
                if a.issubset(b_sets[j]):
                    found = True
                    j += 1
                    break
                j += 1
            if not found:
                return False
        return True

    def __str__(self) -> str:
        if not self._elements:
            return ""
        parts: List[str] = []
        parts.append(str(self._elements[0].getItem()))
        for pair in self._elements[1:]:
            abs_part = pair.getAbstraction().toStringToFile()
            if abs_part:
                parts.append(abs_part.strip())  # "-1"
            parts.append(str(pair.getItem()))
        parts.append("-1")
        return " ".join(parts)


# ----------------------------------------------------------------------
# PatternCreator (exact port)
# ----------------------------------------------------------------------

class PatternCreator:
    _instance: Optional["PatternCreator"] = None

    @classmethod
    def sclear(cls) -> None:
        cls._instance = None

    @classmethod
    def getInstance(cls) -> "PatternCreator":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def createPattern(self, elements: Optional[List[ItemAbstractionPair]] = None) -> Pattern:
        return Pattern(elements)

    def concatenate(self, p1: Optional[Pattern], pair: Optional[ItemAbstractionPair]) -> Optional[Pattern]:
        if p1 is None:
            if pair is None:
                return None
            return Pattern([pair])
        if pair is None:
            return p1
        return p1.concatenate(pair)


# ----------------------------------------------------------------------
# TrieNode + Trie (Tin port)
# ----------------------------------------------------------------------

@dataclass
class TrieNode:
    pair: Optional[ItemAbstractionPair] = None
    child: Optional["Trie"] = None
    alreadyExplored: bool = False

    def getChild(self) -> "Trie":
        assert self.child is not None
        return self.child

    def setChild(self, child: Optional["Trie"]) -> None:
        self.child = child

    def getPair(self) -> ItemAbstractionPair:
        assert self.pair is not None
        return self.pair

    def setPair(self, pair: Optional[ItemAbstractionPair]) -> None:
        self.pair = pair

    def clear(self) -> None:
        if self.child is not None:
            self.child.removeAll()
            self.child.setIdList(None)
        self.child = None
        self.pair = None

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, TrieNode):
            return self.getPair() < other.getPair()
        if isinstance(other, ItemAbstractionPair):
            return self.getPair() < other
        if isinstance(other, Item):
            return self.getPair().getItem() < other
        raise TypeError("Bad comparison for TrieNode")


class Trie:
    _intId = 1

    def __init__(self, nodes: Optional[List[TrieNode]] = None, idList: Optional[IDListStandard_Map] = None):
        self.nodes: List[TrieNode] = nodes if nodes is not None else []
        self.nodei: List[TrieNode] = []
        self.idList: Optional[IDListStandard_Map] = idList

        self.appearingIn: Set[int] = set()
        self.support: int = -1
        self.sumSequencesIDs: int = -1

        self.id = Trie._intId
        Trie._intId += 1

    def getIdList(self) -> IDListStandard_Map:
        assert self.idList is not None
        return self.idList

    def setIdList(self, idList: Optional[IDListStandard_Map]) -> None:
        self.idList = idList

    def getNodes(self) -> List[TrieNode]:
        return self.nodes

    def setNodes(self, nodes: List[TrieNode]) -> None:
        self.nodes = nodes

    def getNode(self, index: int) -> TrieNode:
        return self.nodes[index]

    def levelSize(self) -> int:
        return 0 if self.nodes is None else len(self.nodes)

    def levelSize_i(self) -> int:
        return 0 if self.nodei is None else len(self.nodei)

    def removeAll(self) -> None:
        if self.levelSize() == 0 or self.levelSize_i() == 0:
            return

        for node in self.nodes:
            child = node.child
            if child is not None:
                child.removeAll()
            node.setChild(None)
            node.setPair(None)

        for node in self.nodei:
            child = node.child
            if child is not None:
                child.removeAll()
            node.setChild(None)
            node.setPair(None)

        self.setIdList(None)
        self.nodes.clear()
        self.nodei.clear()
        self.idList = None
        self.appearingIn = set()

    def mergeWithTrie(self, trieNode: TrieNode) -> None:
        self.nodes.append(trieNode)

    def mergeWithTrie_i(self, trieNode: TrieNode) -> None:
        self.nodei.append(trieNode)

    def sort(self) -> None:
        self.nodes.sort()
        self.nodei.sort()

    def setAppearingIn(self, appearingIn: Set[int]) -> None:
        self.appearingIn = set(appearingIn)
        self.support = -1
        self.sumSequencesIDs = -1

    def getAppearingIn(self) -> Set[int]:
        return set(self.appearingIn)

    def getSupport(self) -> int:
        if self.support < 0:
            self.support = len(self.appearingIn)
        return self.support

    def getSumIdSequences(self) -> int:
        if self.sumSequencesIDs < 0:
            self.sumSequencesIDs = sum(self.appearingIn)
        return self.sumSequencesIDs

    def preorderTraversal(self, p: Optional[Pattern]) -> List[Tuple[Pattern, Trie]]:
        result: List[Tuple[Pattern, Trie]] = []
        pc = PatternCreator.getInstance()

        if self.nodes is not None:
            for node in self.nodes:
                newPattern = pc.concatenate(p, node.getPair())
                child = node.child
                if newPattern is not None and child is not None:
                    result.append((newPattern, child))
                    result.extend(child.preorderTraversal(newPattern))

        if self.nodei is not None:
            for node in self.nodei:
                newPattern = pc.concatenate(p, node.getPair())
                child = node.child
                if newPattern is not None and child is not None:
                    result.append((newPattern, child))
                    result.extend(child.preorderTraversal(newPattern))

        return result


# ----------------------------------------------------------------------
# Sequence / Itemset
# ----------------------------------------------------------------------

@dataclass
class Itemset:
    _items: List[Item] = field(default_factory=list)
    _timestamp: int = -1

    def setTimestamp(self, ts: int) -> None:
        self._timestamp = int(ts)

    def getTimestamp(self) -> int:
        return self._timestamp

    def addItem(self, item: Item) -> None:
        self._items.append(item)

    def size(self) -> int:
        return len(self._items)

    def get(self, j: int) -> Item:
        return self._items[j]

    def remove(self, j: int) -> None:
        del self._items[j]


@dataclass
class Sequence:
    _internal_index: int
    _id: int = -1
    _itemsets: List[Itemset] = field(default_factory=list)

    def setID(self, sid: int) -> None:
        self._id = int(sid)

    def getId(self) -> int:
        return self._id

    def addItemset(self, itemset: Itemset) -> None:
        self._itemsets.append(itemset)

    def size(self) -> int:
        return len(self._itemsets)

    def length(self) -> int:
        return sum(iset.size() for iset in self._itemsets)

    def get(self, i: int) -> Itemset:
        return self._itemsets[i]

    def remove_itemset(self, i: int) -> None:
        del self._itemsets[i]

    def remove_item(self, i: int, j: int) -> None:
        self._itemsets[i].remove(j)


# ----------------------------------------------------------------------
# Saver
# ----------------------------------------------------------------------

class Saver:
    def __init__(self, outputSequenceIdentifiers: bool) -> None:
        self.outputSequenceIdentifiers = outputSequenceIdentifiers

    def savePattern(self, pattern: Pattern) -> None:
        raise NotImplementedError

    def finish(self) -> None:
        pass


class SaverIntoFile(Saver):
    def __init__(self, outputFilePath: str, outputSequenceIdentifiers: bool) -> None:
        super().__init__(outputSequenceIdentifiers)
        self.path = Path(outputFilePath)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._f = self.path.open("w", encoding="utf-8")

    def savePattern(self, pattern: Pattern) -> None:
        line = f"{pattern} #SUP: {pattern.support}"
        if self.outputSequenceIdentifiers:
            sids = sorted(pattern.getAppearingIn())
            if sids:
                line += " #SID: " + " ".join(map(str, sids))
        self._f.write(line + "\n")

    def finish(self) -> None:
        try:
            self._f.flush()
            self._f.close()
        except Exception:
            pass


class SaverIntoMemory(Saver):
    def __init__(self, outputSequenceIdentifiers: bool) -> None:
        super().__init__(outputSequenceIdentifiers)
        self.patterns: List[Pattern] = []

    def savePattern(self, pattern: Pattern) -> None:
        self.patterns.append(pattern)


# ----------------------------------------------------------------------
# IdListCreatorStandard_Map
# ----------------------------------------------------------------------

class IdListCreatorStandard_Map:
    _instance: Optional["IdListCreatorStandard_Map"] = None

    @classmethod
    def getInstance(cls) -> "IdListCreatorStandard_Map":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def create(self) -> IDListStandard_Map:
        return IDListStandard_Map()

    def addAppearance(self, idlist: IDListStandard_Map, sid: int, timestamp: int, position: int) -> None:
        idlist.addAppearance(sid, Position(timestamp, position))

    def updateProjectionDistance(self, projectingDistance, item, sid, sequence_itemset_count, position) -> None:
        mp = projectingDistance.setdefault(item, {})
        lst = mp.setdefault(sid, [])
        lst.append(int(position))

    def initializeMaps(self, frequentItems, projectingDistance, sequencesLengths, sequenceItemsetSize) -> None:
        IDListStandard_Map.originalSizeOfSequences = sequencesLengths
        for node in frequentItems.values():
            node.getChild().getIdList().SetOriginalSequenceLengths(sequencesLengths)


# ----------------------------------------------------------------------
# SequenceDatabase
# ----------------------------------------------------------------------

class SequenceDatabase:
    def __init__(self, abstractionCreator: AbstractionCreator, idListCreator: IdListCreatorStandard_Map):
        self.abstractionCreator = abstractionCreator
        self.idListCreator = idListCreator
        self.frequentItems: Dict[Item, TrieNode] = {}
        self.sequences: List[Sequence] = []
        self.itemFactory = ItemFactory()
        self.nSequences = 1

        self.sequencesLengths: Dict[int, int] = {}
        self.sequenceItemsetSize: Dict[int, List[int]] = {}
        self.projectingDistance: Dict[Item, Dict[int, List[int]]] = {}

    def loadFile(self, path: str, minSupport: float) -> int:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Input file not found: {path}")

        with p.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                if s[0] in ("#", "%", "@"):
                    continue
                self.addSequence(s.split(" "))

        support_abs = int(math.ceil(minSupport * len(self.sequences)))

        items_to_remove: List[Item] = []
        for it, node in self.frequentItems.items():
            if node.getChild().getIdList().getSupport() < support_abs:
                items_to_remove.append(it)
            else:
                node.getChild().getIdList().setAppearingIn(node.getChild())

        for it in items_to_remove:
            self.frequentItems.pop(it, None)

        self._reduceDatabase(set(self.frequentItems.keys()))
        self.idListCreator.initializeMaps(self.frequentItems, self.projectingDistance, self.sequencesLengths, self.sequenceItemsetSize)
        return support_abs

    def addSequence(self, tokens: List[str]) -> None:
        pairCreator = ItemAbstractionPairCreator.getInstance()
        timestamp = -1

        sequence = Sequence(_internal_index=len(self.sequences))
        itemset = Itemset()
        sequence.setID(self.nSequences)
        sizeItemsetsList: List[int] = []

        for tok in tokens:
            if not tok:
                continue
            if tok[0] == "<":
                timestamp = int(tok[1:-1])
                itemset.setTimestamp(timestamp)
            elif tok == "-1":
                timestamp = itemset.getTimestamp() + 1
                sequence.addItemset(itemset)
                itemset = Itemset()
                itemset.setTimestamp(timestamp)
                sizeItemsetsList.append(sequence.length())
            elif tok == "-2":
                self.sequences.append(sequence)
                self.nSequences += 1
                self.sequencesLengths[sequence.getId()] = sequence.length()
                self.sequenceItemsetSize[sequence.getId()] = sizeItemsetsList
            else:
                if "(" in tok:
                    continue
                item = self.itemFactory.getItem(int(tok))
                node = self.frequentItems.get(item)
                if node is None:
                    idlist = self.idListCreator.create()
                    pair = pairCreator.getItemAbstractionPair(item, self.abstractionCreator.createDefaultAbstraction())
                    node = TrieNode(pair=pair, child=Trie(None, idlist))
                    self.frequentItems[item] = node

                idlist = node.getChild().getIdList()
                if timestamp < 0:
                    timestamp = 1
                    itemset.setTimestamp(timestamp)

                itemset.addItem(item)
                self.idListCreator.addAppearance(idlist, sequence.getId(), int(timestamp), sequence.length() + itemset.size())
                self.idListCreator.updateProjectionDistance(self.projectingDistance, item, sequence.getId(), sequence.size(), sequence.length() + itemset.size())

    def frequentItemsTrie(self) -> Trie:
        t = Trie()
        t.setNodes(list(self.frequentItems.values()))
        t.sort()
        return t

    def _reduceDatabase(self, keySet: Set[Item]) -> None:
        k = 0
        while k < len(self.sequences):
            seq = self.sequences[k]
            i = 0
            while i < seq.size():
                iset = seq.get(i)
                j = 0
                while j < iset.size():
                    it = iset.get(j)
                    if it not in keySet:
                        seq.remove_item(i, j)
                    else:
                        j += 1
                if iset.size() == 0:
                    seq.remove_itemset(i)
                else:
                    i += 1
            if seq.size() == 0:
                del self.sequences[k]
            else:
                k += 1

    def clear(self) -> None:
        self.sequences.clear()
        self.frequentItems.clear()
        self.sequences = None  # type: ignore
        self.frequentItems = None  # type: ignore
        self.itemFactory = None  # type: ignore
        self.projectingDistance = None  # type: ignore
        self.sequenceItemsetSize = None  # type: ignore
        self.sequencesLengths = None  # type: ignore


# ----------------------------------------------------------------------
# FrequentPatternEnumeration_ClaSP
# ----------------------------------------------------------------------

class FrequentPatternEnumeration_ClaSP:
    def __init__(self, abstractionCreator: AbstractionCreator, minSupAbsolute: float, saver: Saver,
                 findClosedPatterns: bool, executePruningMethods: bool):
        self.joinCount = 0
        self.abstractionCreator = abstractionCreator
        self.minSupAbsolute = float(minSupAbsolute)
        self.numberOfFrequentPatterns = 0
        self.numberOfFrequentClosedPatterns = 0
        self.matchingMap: Dict[int, Dict[int, List[Tuple[Pattern, Trie]]]] = {}
        self.saver = saver
        self.findClosedPatterns = bool(findClosedPatterns)
        self.executePruningMethods = bool(executePruningMethods)
        self.firstSequenceExtensions: List[TrieNode] = []

    def dfsPruning(self, patron: Pattern, trie: Trie, verbose: bool,
                  coocMapAfter: Optional[Dict[int, Dict[int, int]]],
                  coocMapEquals: Optional[Dict[int, Dict[int, int]]]) -> None:
        self.firstSequenceExtensions = trie.getNodes()
        for i in range(trie.levelSize()):
            eq = trie.getNode(i)
            self.exploreChildren(
                Pattern(eq.getPair()),
                eq,
                trie.getNodes(),
                trie.getNodes(),
                i + 1,
                coocMapAfter,
                coocMapEquals,
                eq.getPair().getItem(),
            )

    def exploreChildren(self, pattern: Pattern, currentNode: TrieNode,
                        sequenceExtensions: List[TrieNode],
                        itemsetsExtensions: List[TrieNode],
                        beginning: int,
                        coocMapAfter: Optional[Dict[int, Dict[int, int]]],
                        coocMapEquals: Optional[Dict[int, Dict[int, int]]],
                        lastAppendedItem: Item) -> None:

        currentTrie = currentNode.getChild()

        isAvoidable = False
        if self.findClosedPatterns and self.executePruningMethods:
            isAvoidable = self.isAvoidable(pattern, currentTrie)

        self.numberOfFrequentPatterns += 1

        new_sequenceExtension: List[TrieNode] = []
        new_itemsetExtension: List[TrieNode] = []
        newPatterns: List[Pattern] = []
        newNodesToExtends: List[TrieNode] = []

        clone = pattern.clonePatron()

        # s-extensions
        if not isAvoidable:
            for node in sequenceExtensions:
                if coocMapAfter is not None:
                    mp = coocMapAfter.get(lastAppendedItem.getId())
                    if mp is None:
                        continue
                    c = mp.get(node.getPair().getItem().getId())
                    if c is None or c < self.minSupAbsolute:
                        continue

                extension = Pattern(list(clone.getElements()))
                newPair = node.getPair()
                extension.add(newPair)

                self.joinCount += 1
                newIdList = currentTrie.getIdList().join(node.getChild().getIdList(), False, int(self.minSupAbsolute))
                if newIdList.getSupport() >= self.minSupAbsolute:
                    newTrie = Trie(None, newIdList)
                    newIdList.setAppearingIn(newTrie)

                    newTrieNode = TrieNode(newPair, newTrie)
                    currentTrie.mergeWithTrie(newTrieNode)

                    newPatterns.append(extension)
                    newNodesToExtends.append(newTrieNode)
                    new_sequenceExtension.append(newTrieNode)

            for i in range(len(new_sequenceExtension)):
                newPattern = newPatterns[i]
                nodeToExtend = newNodesToExtends.pop(0)
                last = newPattern.getIthElement(newPattern.size() - 1).getItem()
                self.exploreChildren(newPattern, nodeToExtend, new_sequenceExtension, new_sequenceExtension, i + 1,
                                     coocMapAfter, coocMapEquals, last)

        newPatterns.clear()
        newNodesToExtends.clear()

        # i-extensions
        for k in range(beginning, len(itemsetsExtensions)):
            eq = itemsetsExtensions[k]
            if coocMapEquals is not None:
                mp = coocMapEquals.get(lastAppendedItem.getId())
                if mp is None:
                    continue
                c = mp.get(eq.getPair().getItem().getId())
                if c is None or c < self.minSupAbsolute:
                    continue

            extension = Pattern(list(clone.getElements()))
            newPair = ItemAbstractionPairCreator.getInstance().getItemAbstractionPair(
                eq.getPair().getItem(),
                AbstractionCreator_Qualitative.getInstance().crearAbstraccion(True),
            )
            extension.add(newPair)

            self.joinCount += 1
            newIdList = currentTrie.getIdList().join(eq.getChild().getIdList(), True, int(self.minSupAbsolute))
            if newIdList.getSupport() >= self.minSupAbsolute:
                newTrie = Trie(None, newIdList)
                newIdList.setAppearingIn(newTrie)

                newTrieNode = TrieNode(newPair, newTrie)
                currentTrie.mergeWithTrie_i(newTrieNode)

                newPatterns.append(extension)
                newNodesToExtends.append(newTrieNode)
                new_itemsetExtension.append(newTrieNode)

        for i in range(len(new_itemsetExtension)):
            newPattern = newPatterns[i]
            nodeToExtend = newNodesToExtends.pop(0)
            last = newPattern.getIthElement(newPattern.size() - 1).getItem()

            seq_ext = self.firstSequenceExtensions if isAvoidable else new_sequenceExtension
            self.exploreChildren(newPattern, nodeToExtend, seq_ext, new_itemsetExtension, i + 1,
                                 coocMapAfter, coocMapEquals, last)

            nodeToExtend.getChild().setIdList(None)

    def getFrequentPatterns(self) -> int:
        return self.numberOfFrequentPatterns

    def getFrequentClosedPatterns(self) -> int:
        return self.numberOfFrequentClosedPatterns

    def key2(self, idlist: IDListStandard_Map, t: Trie) -> int:
        return idlist.getTotalElementsAfterPrefixes() + t.getSupport()

    def isAvoidable(self, prefix: Pattern, trie: Trie) -> bool:
        support = trie.getSupport()
        idList = trie.getIdList()

        key1 = trie.getSumIdSequences()
        prefixSize = prefix.size()
        key2 = self.key2(idList, trie)

        newEntry: Tuple[Pattern, Trie] = (prefix, trie)

        associatedMap = self.matchingMap.get(key1)
        if associatedMap is None:
            self.matchingMap[key1] = {key2: [newEntry]}
            return False

        associatedList = associatedMap.get(key2)
        if associatedList is None:
            associatedMap[key2] = [newEntry]
            return False

        i = 0
        superPattern = 0
        while i < len(associatedList):
            p, t = associatedList[i]
            if support == t.getSupport():
                pSize = p.size()
                if pSize != prefixSize:
                    if prefixSize < pSize:
                        if prefix.isSubpattern(self.abstractionCreator, p):
                            trie.setNodes(t.getNodes())
                            return True
                    else:
                        if p.isSubpattern(self.abstractionCreator, prefix):
                            superPattern += 1
                            trie.setNodes(t.getNodes())
                            associatedList.pop(i)
                            continue
            i += 1

        associatedList.append(newEntry)
        return superPattern > 0

    def removeNonClosedPatterns(self, frequentPatterns: List[Tuple[Pattern, Trie]], keepPatterns: bool) -> None:
        print(f"Before removing NonClosed patterns there are {self.numberOfFrequentPatterns} patterns")
        self.numberOfFrequentClosedPatterns = 0

        totalPatterns: Dict[int, List[Pattern]] = {}
        for (p, t) in frequentPatterns:
            p.setAppearingIn(t.getAppearingIn())
            totalPatterns.setdefault(t.getSumIdSequences(), []).append(p)

        for lista in totalPatterns.values():
            i = 0
            while i < len(lista):
                j = i + 1
                while j < len(lista):
                    p1 = lista[i]
                    p2 = lista[j]
                    if len(p1.getAppearingIn()) == len(p2.getAppearingIn()):
                        if p1.size() != p2.size():
                            if p1.size() < p2.size():
                                if p1.isSubpattern(self.abstractionCreator, p2):
                                    lista.pop(i)
                                    i -= 1
                                    break
                            else:
                                if p2.isSubpattern(self.abstractionCreator, p1):
                                    lista.pop(j)
                                    j -= 1
                    j += 1
                i += 1

        for lst in totalPatterns.values():
            self.numberOfFrequentClosedPatterns += len(lst)
            if keepPatterns:
                for p in lst:
                    p.support = len(p.getAppearingIn())
                    self.saver.savePattern(p)

    def clear(self) -> None:
        if self.matchingMap is not None:
            self.matchingMap.clear()
            self.matchingMap = None  # type: ignore


# ----------------------------------------------------------------------
# AlgoClaSP
# ----------------------------------------------------------------------

class AlgoClaSP:
    def __init__(self, minSupAbsolute: float, abstractionCreator: AbstractionCreator,
                 findClosedPatterns: bool, executePruningMethods: bool):
        self.minSupAbsolute = float(minSupAbsolute)
        self.saver: Optional[Saver] = None

        self.overallStart = 0
        self.overallEnd = 0
        self.mainMethodStart = 0
        self.mainMethodEnd = 0
        self.postProcessingStart = 0
        self.postProcessingEnd = 0

        self.frequentAtomsTrie: Optional[Trie] = None
        self.abstractionCreator = abstractionCreator

        self.numberOfFrequentPatterns = 0
        self.numberOfFrequentClosedPatterns = 0
        self.findClosedPatterns = bool(findClosedPatterns)
        self.executePruningMethods = bool(executePruningMethods)

        self.joinCount = 0

    def runAlgorithm(self, database: SequenceDatabase, keepPatterns: bool, verbose: bool,
                     outputFilePath: Optional[str], outputSequenceIdentifiers: bool) -> None:
        self.saver = SaverIntoMemory(outputSequenceIdentifiers) if outputFilePath is None else SaverIntoFile(outputFilePath, outputSequenceIdentifiers)
        MemoryLogger.getInstance().reset()

        self.overallStart = int(time.time() * 1000)
        self.claSP(database, int(self.minSupAbsolute), keepPatterns, verbose, self.findClosedPatterns, self.executePruningMethods)
        self.overallEnd = int(time.time() * 1000)

        self.saver.finish()

    def claSP(self, database: SequenceDatabase, minSupAbsolute: int, keepPatterns: bool,
              verbose: bool, findClosedPatterns: bool, executePruningMethods: bool) -> None:

        self.frequentAtomsTrie = database.frequentItemsTrie()
        database.clear()

        fpe = FrequentPatternEnumeration_ClaSP(self.abstractionCreator, minSupAbsolute, self.saver, findClosedPatterns, executePruningMethods)  # type: ignore[arg-type]

        self.mainMethodStart = int(time.time() * 1000)
        fpe.dfsPruning(Pattern(), self.frequentAtomsTrie, verbose, None, None)  # type: ignore[arg-type]
        self.mainMethodEnd = int(time.time() * 1000)

        self.numberOfFrequentPatterns = fpe.getFrequentPatterns()

        MemoryLogger.getInstance().checkMemory()
        if verbose:
            print(f"ClaSP: The algorithm takes {self.mainMethodEnd - self.mainMethodStart} ms and finds {self.numberOfFrequentPatterns} patterns")

        if findClosedPatterns:
            out = self.frequentAtomsTrie.preorderTraversal(None)  # type: ignore[union-attr]
            self.postProcessingStart = int(time.time() * 1000)
            fpe.removeNonClosedPatterns(out, keepPatterns)
            self.postProcessingEnd = int(time.time() * 1000)
            self.numberOfFrequentClosedPatterns = fpe.getFrequentClosedPatterns()
            if verbose:
                print(
                    "ClaSP:The post-processing algorithm to remove the non-Closed patterns takes "
                    + str((self.postProcessingEnd - self.postProcessingStart) / 1000)
                    + " seconds and finds "
                    + str(self.numberOfFrequentClosedPatterns)
                    + " Closed patterns"
                )
        else:
            if keepPatterns:
                out = self.frequentAtomsTrie.preorderTraversal(None)  # type: ignore[union-attr]
                for p, t in out:
                    p.setAppearingIn(t.getAppearingIn())
                    p.support = len(p.getAppearingIn())
                    self.saver.savePattern(p)  # type: ignore[union-attr]

        self.joinCount = fpe.joinCount
        fpe.clear()
        MemoryLogger.getInstance().checkMemory()

    def printStatistics(self) -> str:
        return (
            "=============  Algorithm - STATISTICS =============\n"
            f" Total time ~ {self.getRunningTime()} ms\n"
            f" Frequent closed sequences count : {self.numberOfFrequentClosedPatterns}\n"
            f" Join count : {self.joinCount}\n"
            f" Max memory (mb):{MemoryLogger.getInstance().getMaxMemory()}\n"
            "==================================================="
        )

    def getNumberOfFrequentPatterns(self) -> int:
        return self.numberOfFrequentPatterns

    def getRunningTime(self) -> int:
        return int(self.overallEnd - self.overallStart)


# ----------------------------------------------------------------------
# Main (equivalent to MainTestClaSP_saveToFile.java)
# ----------------------------------------------------------------------

def file_to_path(filename: str) -> str:
    """
    Look for the file next to clasp.py first.
    """
    here = Path(__file__).resolve().parent
    p = here / filename
    if p.exists():
        return str(p)
    raise FileNotFoundError(f"Could not locate {filename}. Tried: {p}")


def main() -> None:
    support = 0.5
    keepPatterns = True
    verbose = True
    findClosedPatterns = True
    executePruningMethods = True
    outputSequenceIdentifiers = False

    abstractionCreator = AbstractionCreator_Qualitative.getInstance()
    idListCreator = IdListCreatorStandard_Map.getInstance()

    input_path = file_to_path("contextPrefixSpan.txt")
    output_path = Path(__file__).resolve().parent / "output_py.txt"

    db = SequenceDatabase(abstractionCreator, idListCreator)
    relativeSupport = db.loadFile(input_path, support)

    algo = AlgoClaSP(relativeSupport, abstractionCreator, findClosedPatterns, executePruningMethods)
    algo.runAlgorithm(db, keepPatterns, verbose, str(output_path), outputSequenceIdentifiers)

    print("Minsup (relative) : " + str(support))
    print(str(algo.getNumberOfFrequentPatterns()) + " patterns found.")
    print(f"Output file: {output_path.resolve()}")
    if verbose and keepPatterns:
        print(algo.printStatistics())


if __name__ == "__main__":
    main()