import math
import os
import time
import tracemalloc


def _java_string_hash(value):
    h = 0
    for ch in value:
        h = (31 * h + ord(ch)) & 0xFFFFFFFF
    if h >= 0x80000000:
        h -= 0x100000000
    return h


def _java_hash_spread(h):
    h &= 0xFFFFFFFF
    return h ^ (h >> 16)


def _java_hashmap_iteration_order(keys_in_insertion_order, hash_func):
    capacity = 16
    threshold = int(capacity * 0.75)
    buckets = [[] for _ in range(capacity)]
    present = set()
    size = 0

    def rehash(new_capacity, old_buckets):
        new_buckets = [[] for _ in range(new_capacity)]
        for bucket in old_buckets:
            for key in bucket:
                h = _java_hash_spread(hash_func(key))
                idx = (new_capacity - 1) & h
                new_buckets[idx].append(key)
        return new_buckets

    for key in keys_in_insertion_order:
        if key in present:
            continue
        h = _java_hash_spread(hash_func(key))
        idx = (capacity - 1) & h
        buckets[idx].append(key)
        present.add(key)
        size += 1
        if size > threshold:
            capacity *= 2
            threshold = int(capacity * 0.75)
            buckets = rehash(capacity, buckets)

    ordered = []
    for bucket in buckets:
        ordered.extend(bucket)
    return ordered


def _java_hash_for_int(value):
    return int(value)


def _java_hash_for_item_simple(item):
    return _java_string_hash(str(item.getId()))


def _java_hash_for_pair(pair):
    s = str(pair.timestamp)
    s += 'P' if pair.postfix else 'N'
    s += 'X' if pair.prefix else 'Z'
    s += str(pair.item.getId())
    return _java_string_hash(s)


class BitSet:
    def __init__(self):
        self._bits = set()

    def set(self, index):
        self._bits.add(index)

    def get(self, index):
        return index in self._bits

    def clear(self):
        self._bits.clear()

    def clone(self):
        copy = BitSet()
        copy._bits = set(self._bits)
        return copy

    def and_(self, other):
        self._bits.intersection_update(other._bits)

    def cardinality(self):
        return len(self._bits)

    def nextSetBit(self, start):
        candidates = [b for b in self._bits if b >= start]
        if not candidates:
            return -1
        return min(candidates)

    def length(self):
        if not self._bits:
            return 0
        return max(self._bits) + 1


class MemoryLogger:
    _instance = None

    def __init__(self):
        self.maxMemory = 0.0

    @classmethod
    def getInstance(cls):
        if cls._instance is None:
            cls._instance = MemoryLogger()
        return cls._instance

    def getMaxMemory(self):
        return self.maxMemory

    def reset(self):
        self.maxMemory = 0.0
        if not tracemalloc.is_tracing():
            tracemalloc.start()

    def checkMemory(self):
        if tracemalloc.is_tracing():
            current, _peak = tracemalloc.get_traced_memory()
            currentMemory = current / 1024.0 / 1024.0
        else:
            currentMemory = 0.0
        if currentMemory > self.maxMemory:
            self.maxMemory = currentMemory
        return currentMemory


class ItemSimple:
    def __init__(self, item_id):
        self.id = item_id

    def getId(self):
        return self.id

    def __str__(self):
        return str(self.id)

    def __eq__(self, other):
        return isinstance(other, ItemSimple) and other.id == self.id

    def __hash__(self):
        return _java_string_hash(str(self.id))


class ItemValued(ItemSimple):
    def __init__(self, item_id, value, lower=None, higher=None):
        super().__init__(item_id)
        self.value = value
        self.lower = lower
        self.higher = higher
        self.cluster = None
        self.sequenceID = None

    def getValue(self):
        return self.value

    def setCluster(self, cluster):
        self.cluster = cluster

    def getCluster(self):
        return self.cluster

    def setSequenceID(self, seq_id):
        self.sequenceID = seq_id

    def getSequenceID(self):
        return self.sequenceID

    def __str__(self):
        return str(self.id) + "(" + str(self.value) + ")"


class Itemset:
    def __init__(self, item=None, timestamp=0):
        self.items = []
        self.timestamp = 0
        if item is not None:
            self.addItem(item)
        self.timestamp = timestamp

    def addItem(self, item):
        self.items.append(item)

    def getItems(self):
        return self.items

    def get(self, index):
        return self.items[index]

    def __str__(self):
        r = []
        for item in self.items:
            r.append(str(item))
            r.append(' ')
        return "".join(r)

    def cloneItemSetMinusItems(self, mapSequenceID, relativeMinsup):
        itemset = Itemset()
        itemset.timestamp = self.timestamp
        for item in self.items:
            if len(mapSequenceID.get(item, set())) >= relativeMinsup:
                itemset.addItem(item)
        return itemset

    def cloneItemSet(self):
        itemset = Itemset()
        itemset.timestamp = self.timestamp
        itemset.getItems().extend(self.items)
        return itemset

    def getTimestamp(self):
        return self.timestamp

    def setTimestamp(self, timestamp):
        self.timestamp = timestamp

    def size(self):
        return len(self.items)


class Sequence:
    def __init__(self, seq_id):
        self.itemsets = []
        self.id = seq_id
        self.sequencesID = None

    def getRelativeSupportFormated(self, databaseSize):
        support = float(len(self.sequencesID)) / float(databaseSize) if self.sequencesID is not None else 0.0
        return ("{0:.5f}".format(support)).rstrip('0').rstrip('.')

    def getAbsoluteSupport(self):
        return len(self.sequencesID) if self.sequencesID is not None else 0

    def addItemset(self, itemset):
        self.itemsets.append(itemset)

    def cloneSequence(self):
        sequence = Sequence(self.getId())
        for itemset in self.itemsets:
            sequence.addItemset(itemset.cloneItemSet())
        return sequence

    def __str__(self):
        return self.toString(True)

    def toString(self, displayTimestamps=True):
        r = []
        for itemset in self.itemsets:
            r.append('{')
            if displayTimestamps:
                r.append('t=')
                r.append(str(itemset.getTimestamp()))
                r.append(', ')
            for item in itemset.getItems():
                r.append(str(item))
                r.append(' ')
            r.append('}')

        if self.getSequencesID() is not None:
            r.append("  Sequence ID: ")
            for seq_id in sorted(self.getSequencesID()):
                r.append(str(seq_id))
                r.append(' ')

        r.append('    ')
        return "".join(r)

    def toStringShort(self):
        r = []
        for itemset in self.itemsets:
            r.append('{t=')
            r.append(str(itemset.getTimestamp()))
            r.append(', ')
            for item in itemset.getItems():
                r.append(str(item))
                r.append(' ')
            r.append('}')
        r.append('    ')
        return "".join(r)

    def getId(self):
        return self.id

    def getItemsets(self):
        return self.itemsets

    def get(self, index):
        return self.itemsets[index]

    def getIthItem(self, i):
        for itemset in self.itemsets:
            if i < itemset.size():
                return itemset.get(i)
            i -= itemset.size()
        return None

    def size(self):
        return len(self.itemsets)

    def getSequencesID(self):
        return self.sequencesID

    def setSequencesID(self, sequencesID):
        self.sequencesID = None if sequencesID is None else set(sequencesID)

    def getItemOccurencesTotalCount(self):
        count = 0
        for itemset in self.itemsets:
            count += itemset.size()
        return count

    def getTimeLength(self):
        return self.itemsets[-1].getTimestamp() - self.itemsets[0].getTimestamp()

    def strictlyContains(self, sequence2):
        retour = self._strictlyContainsHelper(sequence2, 0, 0, 0, 0)
        if retour == 2:
            return 2 if self.size() == sequence2.size() else 1
        return retour

    @staticmethod
    def _contains_all(itemset_items_1, itemset_items_2):
        return all(item in itemset_items_1 for item in itemset_items_2)

    def _strictlyContainsHelper(self, sequence2, index, index2, previousTimeStamp, previousTimeStamp2):
        if index == self.size():
            return 0
        if self.size() - index < sequence2.size() - index2:
            return 0
        returnValue = 0
        for i in range(index, self.size()):
            interval1 = self.get(i).getTimestamp() - previousTimeStamp
            interval2 = sequence2.get(index2).getTimestamp() - previousTimeStamp2
            if Sequence._contains_all(self.get(i).getItems(), sequence2.get(index2).getItems()) and interval1 == interval2:
                sameSize = self.get(i).getItems().__len__() == sequence2.get(index2).size()
                if sequence2.size() - 1 == index2:
                    if sameSize:
                        return 2
                    returnValue = 1
                else:
                    resultat = self._strictlyContainsHelper(sequence2, i + 1, index2 + 1, self.get(i).getTimestamp(), sequence2.get(index2).getTimestamp())
                    if resultat == 2 and sameSize:
                        return 2
                    elif resultat != 0:
                        returnValue = 1
        return returnValue

    def cloneSequenceMinusItems(self, mapSequenceID, relativeMinsup):
        sequence = Sequence(self.getId())
        for itemset in self.itemsets:
            newItemset = itemset.cloneItemSetMinusItems(mapSequenceID, relativeMinsup)
            if newItemset.size() != 0:
                sequence.addItemset(newItemset)
        return sequence


class SequenceDatabase:
    def __init__(self):
        self.sequences = []
        self.cluster = None
        self.maxItemID = 0

    def loadFile(self, path):
        myInput = None
        try:
            myInput = open(path, "r")
            for thisLine in myInput:
                thisLine = thisLine.strip()
                if not thisLine:
                    continue
                if thisLine[0] in ['#', '%', '@']:
                    continue
                self.processSequence(thisLine.split(' '))
        finally:
            if myInput is not None:
                myInput.close()

    def processSequence(self, tokens):
        sequence = Sequence(len(self.sequences))
        itemset = Itemset()
        for integer in tokens:
            if integer and integer[0] == '<':
                value = integer[1:len(integer) - 1]
                itemset.setTimestamp(int(value))
            elif integer == '-1':
                sequence.addItemset(itemset)
                itemset = Itemset()
            elif integer == '-2':
                if itemset.size() > 0:
                    sequence.addItemset(itemset)
                    itemset = Itemset()
                self.sequences.append(sequence)
            else:
                indexLeftParenthesis = integer.find('(')
                if indexLeftParenthesis != -1:
                    indexRightParenthesis = integer.find(')')
                    value = int(integer[indexLeftParenthesis + 1:indexRightParenthesis])
                    integer = integer[0:indexLeftParenthesis]
                    itemAsInteger = int(integer)
                    item = ItemValued(itemAsInteger, value)
                    itemset.addItem(item)
                    if itemAsInteger > self.maxItemID:
                        self.maxItemID = itemAsInteger
                else:
                    itemAsInteger = int(integer)
                    item = ItemSimple(itemAsInteger)
                    if item not in itemset.getItems():
                        itemset.addItem(item)
                    if itemAsInteger > self.maxItemID:
                        self.maxItemID = itemAsInteger

    def addSequence(self, sequence):
        self.sequences.append(sequence)

    def print(self):
        print("============  Context ==========")
        for sequence in self.sequences:
            print(str(sequence.getId()) + ":  ", end="")
            print(sequence.__str__())

    def size(self):
        return len(self.sequences)

    def getSequences(self):
        return self.sequences

    def getSequenceIDs(self):
        return set([seq.getId() for seq in self.sequences])

    def getCluster(self):
        return self.cluster

    def setCluster(self, cluster):
        self.cluster = cluster

    def getMaxItemID(self):
        return self.maxItemID

class Sequences:
    def __init__(self, name):
        self.levels = [[]]
        self.sequenceCount = 0
        self.name = name

    def addSequence(self, sequence, k):
        while len(self.levels) <= k:
            self.levels.append([])
        self.levels[k].append(sequence)
        self.sequenceCount += 1

    def getLevel(self, index):
        return self.levels[index]

    def getLevelCount(self):
        return len(self.levels)

    def getLevels(self):
        return self.levels

    def toString(self, databaseSize):
        r = []
        r.append(" ----------")
        r.append(self.name)
        r.append(" -------\n")
        levelCount = 0
        for level in self.levels:
            r.append("  L")
            r.append(str(levelCount))
            r.append(" \n")
            for sequence in level:
                r.append("  pattern ")
                r.append(str(sequence.getId()))
                r.append(":  ")
                r.append(sequence.toString())
                r.append("support :  ")
                r.append(sequence.getRelativeSupportFormated(databaseSize))
                r.append(" (")
                r.append(str(sequence.getAbsoluteSupport()))
                r.append('/')
                r.append(str(databaseSize))
                r.append(") \n")
            levelCount += 1
        r.append(" -------------------------------- Patterns count : ")
        r.append(str(self.sequenceCount))
        return "".join(r)


class Pair:
    def __init__(self, timestamp, prefix, postfix, item):
        self.timestamp = timestamp
        self.postfix = postfix
        self.prefix = prefix
        self.item = item
        self.sequencesID = set()

    def __eq__(self, other):
        return isinstance(other, Pair) and self.timestamp == other.timestamp and self.postfix == other.postfix and self.prefix == other.prefix and self.item == other.item

    def __hash__(self):
        return _java_hash_for_pair(self)

    def getTimestamp(self):
        return self.timestamp

    def isPostfix(self):
        return self.postfix

    def isPrefix(self):
        return self.prefix

    def getItem(self):
        return self.item

    def getCount(self):
        return len(self.sequencesID)

    def getSequencesID(self):
        return self.sequencesID

    def setSequencesID(self, sequencesID):
        self.sequencesID = sequencesID


class PseudoSequence:
    def __init__(self, timeShift, sequence, indexItemset, indexItem, lastItemset=None, lastItem=None):
        self.timeShift = timeShift
        if isinstance(sequence, PseudoSequence):
            self.sequence = sequence.sequence
            self.firstItemset = indexItemset + sequence.firstItemset
            if self.firstItemset == sequence.firstItemset:
                self.firstItem = indexItem + sequence.firstItem
            else:
                self.firstItem = indexItem
            self.lastItemset = sequence.lastItemset if lastItemset is None else lastItemset
            self.lastItem = sequence.lastItem if lastItem is None else lastItem
        else:
            self.sequence = sequence
            self.firstItemset = indexItemset
            self.firstItem = indexItem
            self.lastItemset = sequence.size() - 1
            self.lastItem = sequence.get(self.lastItemset).size() - 1

    def size(self):
        size = self.sequence.size() - self.firstItemset - ((self.sequence.size() - 1) - self.lastItemset)
        if size == 1 and self.sequence.get(self.firstItemset).size() == 0:
            return 0
        return size

    def getSizeOfItemsetAt(self, index):
        size = self.sequence.get(index + self.firstItemset).size()
        if self.isLastItemset(index):
            size -= ((size - 1) - self.lastItem)
        if self.isFirstItemset(index):
            size -= self.firstItem
        return size

    def isCutAtRight(self, index):
        if not self.isLastItemset(index):
            return False
        return (self.sequence.get(index + self.firstItemset).size() - 1) != self.lastItem

    def isCutAtLeft(self, indexItemset):
        return indexItemset == 0 and self.firstItem != 0

    def isFirstItemset(self, index):
        return index == 0

    def isLastItemset(self, index):
        return (index + self.firstItemset) == self.lastItemset

    def getItemAtInItemsetAt(self, indexItem, indexItemset):
        if self.isFirstItemset(indexItemset):
            return self.getItemset(indexItemset).get(indexItem + self.firstItem)
        return self.getItemset(indexItemset).get(indexItem)

    def getTimeStamp(self, indexItemset):
        return self.getItemset(indexItemset).getTimestamp() - self.timeShift

    def getAbsoluteTimeStamp(self, indexItemset):
        return self.getItemset(indexItemset).getTimestamp()

    def getItemset(self, index):
        return self.sequence.get(index + self.firstItemset)

    def getId(self):
        return self.sequence.getId()

    def indexOf(self, indexItemset, idItem):
        for i in range(self.getSizeOfItemsetAt(indexItemset)):
            if self.getItemAtInItemsetAt(i, indexItemset).getId() == idItem:
                return i
        return -1

    class PseudoSequencePair:
        def __init__(self, pseudoSequence, list_positions):
            self.pseudoSequence = pseudoSequence
            self.list = list_positions

    class Position:
        def __init__(self, itemset, item):
            self.itemset = itemset
            self.item = item

    def getAllInstancesOfPrefix(self, prefix, i):
        listInstances = self.getAllInstancesOfPrefixHelper(prefix, 0, [], [], 0, 0)
        allPairs = []
        for listPositions in listInstances:
            newSequence = PseudoSequence(0, self, self.firstItemset, self.firstItem,
                                         listPositions[i - 1].itemset, listPositions[i - 1].item)
            allPairs.append(PseudoSequence.PseudoSequencePair(newSequence, listPositions))
        return allPairs

    def getAllInstancesOfPrefixHelper(self, prefix, indexItemset, allInstances, listPositionsTotal, itemsetShift, decalageItemset):
        for i in range(decalageItemset, self.size()):
            firstTime = indexItemset == 0
            if not firstTime and self.getTimeStamp(i) - itemsetShift != prefix.get(indexItemset).getTimestamp():
                continue
            indexItem = 0
            listPositions = []
            iDCourant = prefix.get(indexItemset).get(indexItem).getId()
            for j in range(self.getSizeOfItemsetAt(i)):
                id_val = self.getItemAtInItemsetAt(j, i).getId()
                if id_val == iDCourant:
                    listPositions.append(PseudoSequence.Position(i, j))
                    if len(listPositions) + len(listPositionsTotal) == prefix.getItemOccurencesTotalCount():
                        newList = list(listPositionsTotal)
                        newList.extend(listPositions)
                        allInstances.append(newList)
                    elif indexItem + 1 >= prefix.get(indexItemset).size():
                        decalage = self.getTimeStamp(i) if firstTime else itemsetShift
                        newList = list(listPositionsTotal)
                        newList.extend(listPositions)
                        if indexItemset + 1 < prefix.size():
                            self.getAllInstancesOfPrefixHelper(prefix, indexItemset + 1, allInstances, newList, decalage, i + 1)
                    else:
                        indexItem += 1
                        iDCourant = prefix.get(indexItemset).get(indexItem).getId()
        return allInstances

    def getLastInstanceOfPrefixSequence(self, prefix, i):
        list_pairs = self.getAllInstancesOfPrefix(prefix, i)
        sequenceRetourPair = list_pairs[0]
        for sequencePair in list_pairs:
            sequence = sequencePair.pseudoSequence
            sequenceRetour = sequenceRetourPair.pseudoSequence
            if (sequence.lastItemset > sequenceRetour.lastItemset) or (
                sequenceRetour.lastItemset == sequence.lastItemset and sequence.lastItem > sequenceRetour.lastItem):
                sequenceRetourPair = sequencePair
        return sequenceRetourPair

    def getFirstInstanceOfPrefixSequence(self, prefix, i):
        list_pairs = self.getAllInstancesOfPrefix(prefix, i)
        sequenceRetourPair = list_pairs[0]
        for sequencePair in list_pairs:
            sequence = sequencePair.pseudoSequence
            sequenceRetour = sequenceRetourPair.pseudoSequence
            if (sequence.lastItemset < sequenceRetour.lastItemset) or (
                sequenceRetour.lastItemset == sequence.lastItemset and sequence.lastItem < sequenceRetour.lastItem):
                sequenceRetourPair = sequencePair
        return sequenceRetourPair

    def getIthLastInLastApearanceWithRespectToPrefix(self, prefix, i, withTimeStamps):
        lastInstancePair = self.getLastInstanceOfPrefixSequence(prefix, prefix.getItemOccurencesTotalCount())
        if not withTimeStamps:
            iditem = prefix.getIthItem(i).getId()
            if i == prefix.getItemOccurencesTotalCount() - 1:
                for j in range(lastInstancePair.pseudoSequence.size() - 1, -1, -1):
                    for k in range(lastInstancePair.pseudoSequence.getItemset(j).size() - 1, -1, -1):
                        if lastInstancePair.pseudoSequence.getItemAtInItemsetAt(k, j).getId() == iditem:
                            return PseudoSequence.Position(j, k)
            else:
                LLiplus1 = self.getIthLastInLastApearanceWithRespectToPrefix(prefix, i + 1, False)
                for j in range(LLiplus1.itemset, -1, -1):
                    for k in range(lastInstancePair.pseudoSequence.getItemset(j).size() - 1, -1, -1):
                        if j == LLiplus1.itemset and k >= LLiplus1.item:
                            continue
                        if lastInstancePair.pseudoSequence.getItemAtInItemsetAt(k, j).getId() == iditem:
                            return PseudoSequence.Position(j, k)
            return None
        return lastInstancePair.list[i]

    def getIthMaximumPeriodOfAPrefix(self, prefix, i, withTimeStamps):
        if i == 0:
            ithlastlast = self.getIthLastInLastApearanceWithRespectToPrefix(prefix, 0, withTimeStamps)
            return self.trimBeginingAndEnd(None, ithlastlast)
        firstInstance = self.getFirstInstanceOfPrefixSequence(prefix, i)
        lastOfFirstInstance = firstInstance.list[i - 1]
        ithlastlast = self.getIthLastInLastApearanceWithRespectToPrefix(prefix, i, withTimeStamps)
        return self.trimBeginingAndEnd(lastOfFirstInstance, ithlastlast)

    def getAllIthMaxPeriodOfAPrefix(self, prefix, i, withTimeStamps):
        if i == 0:
            periods = []
            for instance in self.getAllInstancesOfPrefix(prefix, prefix.getItemOccurencesTotalCount()):
                period = self.trimBeginingAndEnd(None, instance.list[0])
                periods.append(period)
            return periods
        periods = []
        for instance in self.getAllInstancesOfPrefix(prefix, i):
            period = self.trimBeginingAndEnd(instance.list[i - 1], instance.list[i])
            periods.append(period)
        return periods

    def trimBeginingAndEnd(self, positionStart, positionEnd):
        itemsetStart = 0
        itemStart = 0
        itemsetEnd = self.lastItemset
        itemEnd = self.lastItem
        newTimeStamp = 0
        if positionStart is not None:
            itemsetStart = positionStart.itemset
            itemStart = positionStart.item + 1
            if itemStart == self.getSizeOfItemsetAt(itemsetStart):
                itemsetStart += 1
                itemStart = 0
            if itemsetStart == self.size():
                return None
            newTimeStamp = self.getTimeStamp(itemsetStart)
        if positionEnd is not None:
            itemsetEnd = positionEnd.itemset
            itemEnd = positionEnd.item - 1
            if itemEnd < 0:
                itemsetEnd -= 1
                if itemsetEnd < itemsetStart:
                    return None
                itemEnd = self.getSizeOfItemsetAt(itemsetEnd) - 1
        if itemsetEnd == itemsetStart and itemEnd < itemStart:
            return None
        return PseudoSequence(newTimeStamp, self, itemsetStart, itemStart, itemsetEnd, itemEnd)

    def getTimeShift(self):
        return self.timeShift

    def getTimeSucessor(self):
        positionLastElement = self.size() - 1
        absolutePositionLastElement = self.size() - 1 + self.firstItemset
        if self.isCutAtRight(positionLastElement):
            return self.getAbsoluteTimeStamp(positionLastElement)
        if absolutePositionLastElement < self.sequence.size() - 1:
            return self.sequence.get(absolutePositionLastElement + 1).getTimestamp()
        return 0

    def getTimePredecessor(self):
        if self.firstItemset == 0:
            return 0
        if self.firstItem == 0:
            return self.getAbsoluteTimeStamp(-1)
        return self.getAbsoluteTimeStamp(0)

    def getIthLastInFirstApearanceWithRespectToPrefix(self, prefix, i, withTimestamps):
        firstInstancePair = self.getFirstInstanceOfPrefixSequence(prefix, prefix.getItemOccurencesTotalCount())
        if not withTimestamps:
            iditem = prefix.getIthItem(i).getId()
            if i == prefix.getItemOccurencesTotalCount() - 1:
                for j in range(firstInstancePair.pseudoSequence.size() - 1, -1, -1):
                    for k in range(firstInstancePair.pseudoSequence.getItemset(j).size() - 1, -1, -1):
                        if firstInstancePair.pseudoSequence.getItemAtInItemsetAt(k, j).getId() == iditem:
                            return PseudoSequence.Position(j, k)
            else:
                LLiplus1 = self.getIthLastInFirstApearanceWithRespectToPrefix(prefix, i + 1, False)
                for j in range(LLiplus1.itemset, -1, -1):
                    for k in range(firstInstancePair.pseudoSequence.getItemset(j).size() - 1, -1, -1):
                        if j == LLiplus1.itemset and k >= LLiplus1.item:
                            continue
                        if firstInstancePair.pseudoSequence.getItemAtInItemsetAt(k, j).getId() == iditem:
                            return PseudoSequence.Position(j, k)
            return None
        return firstInstancePair.list[i]

    def getIthSemiMaximumPeriodOfAPrefix(self, prefix, i, withTimestamps):
        if i == 0:
            ithlastfirst = self.getIthLastInFirstApearanceWithRespectToPrefix(prefix, 0, withTimestamps)
            return self.trimBeginingAndEnd(None, ithlastfirst)
        firstInstance = self.getFirstInstanceOfPrefixSequence(prefix, i)
        endOfFirstInstance = firstInstance.list[i - 1]
        ithlastfirst = self.getIthLastInFirstApearanceWithRespectToPrefix(prefix, i, withTimestamps)
        return self.trimBeginingAndEnd(endOfFirstInstance, ithlastfirst)


class PseudoSequenceDatabase:
    def __init__(self):
        self.sequences = []
        self.cluster = None

    def addSequence(self, sequence):
        self.sequences.append(sequence)

    def getPseudoSequences(self):
        return self.sequences

    def size(self):
        return len(self.sequences)

    def setCluster(self, cluster):
        self.cluster = cluster

    def getCluster(self):
        return self.cluster

    def getSequenceIDs(self):
        return set([seq.getId() for seq in self.sequences])

class Cluster:
    def __init__(self, items=None, items2=None, average=None):
        self.items = []
        self.average = 0.0
        self.higher = 0.0
        self.lower = float("inf")
        self.sum = 0.0
        self.sequenceIDs = None
        if average is not None:
            self.average = average
        if items is not None:
            self.addItems(items)
        if items2 is not None:
            self.addItems(items2)
        if items is not None or items2 is not None:
            self.recomputeClusterAverage()

    def addItemsFromCluster(self, cluster2):
        for item in cluster2.getItems():
            self.addItem(item)

    def addItem(self, item):
        self.items.append(item)
        self.sum += item.getValue()

    def addItems(self, newItems):
        for item in newItems:
            self.addItem(item)

    def getItems(self):
        return self.items

    def size(self):
        return len(self.items)

    def getaverage(self):
        return self.average

    def recomputeClusterAverage(self):
        if not self.items:
            return
        if len(self.items) == 1:
            self.average = self.items[0].getValue()
            return
        self.average = self.sum / float(len(self.items))

    def computeHigherAndLower(self):
        for item in self.items:
            if item.getValue() > self.higher:
                self.higher = item.getValue()
            if item.getValue() < self.lower:
                self.lower = item.getValue()

    def containsItem(self, item2):
        return any(item is item2 for item in self.items)

    def getHigher(self):
        return self.higher

    def getLower(self):
        return self.lower

    def getItemId(self):
        return self.items[0].getId()

    def getSequenceIDs(self):
        return self.sequenceIDs

    def setSequenceIDs(self, sequenceIDs):
        self.sequenceIDs = sequenceIDs


class AlgoKMeansWithSupport:
    def __init__(self, maxK=1, minsuppRelative=1):
        self.maxK = maxK
        self.minsuppRelative = minsuppRelative

    def runAlgorithm(self, items):
        # Minimal implementation: return a single cluster containing all items.
        if not items:
            return []
        cluster = Cluster(items=items)
        cluster.computeHigherAndLower()
        for item in items:
            item.setCluster(cluster)
        return [cluster]

class AbstractAlgoPrefixSpan:
    def __init__(self, minsupAbsolute):
        self.minsuppAbsolute = minsupAbsolute
        self.minPatternLength = 1
        self.maxPatternLength = float('inf')
        self.showSequenceIdentifiers = False
        self.sequenceIdentifiers = None

    def setMaximumPatternLength(self, maxlen):
        self.maxPatternLength = maxlen

    def setMinimumPatternLength(self, minlen):
        self.minPatternLength = minlen

    def setShowSequenceIdentifiers(self, value):
        self.showSequenceIdentifiers = value

    def getSequenceIdentifiers(self):
        return self.sequenceIdentifiers



class AlgoFournierViger08(AbstractAlgoPrefixSpan):
    def __init__(self, minsupp, minInterval, maxInterval, minWholeInterval, maxWholeInterval, algoClustering, findClosedPatterns, enableBackscanPruning):
        if (minInterval > maxInterval) or (minWholeInterval > maxWholeInterval) or (minInterval > maxWholeInterval) or (maxInterval > maxWholeInterval):
            raise RuntimeError("Parameters are not valid!!!")
        super().__init__(0)
        self.patterns = None
        self.patternCount = 0
        self.startTime = 0
        self.endTime = 0
        self.minInterval = minInterval
        self.maxInterval = maxInterval
        self.minWholeInterval = minWholeInterval
        self.maxWholeInterval = maxWholeInterval
        self.minsupp = minsupp
        self.findClosedPatterns = findClosedPatterns
        self.minsuppRelative = 0
        self.enableBackscanPruning = enableBackscanPruning
        self.algoClustering = algoClustering
        self.initialDatabase = None
        self.writer = None

    def runAlgorithmToFile(self, database, outputFilePath):
        self.writer = open(outputFilePath, "w")
        self.patterns = Sequences("FREQUENT SEQUENCES WITH TIME + CLUSTERING")
        self.runAlgorithm(database)
        self.writer.close()
        self.writer = None

    def runAlgorithm(self, database):
        if self.writer is None:
            self.patterns = Sequences("FREQUENT SEQUENCES WITH TIME + CLUSTERING")
        self.patternCount = 0
        self.minsuppRelative = int(math.ceil(self.minsupp * database.size()))
        if self.minsuppRelative == 0:
            self.minsuppRelative = 1
        self.startTime = int(time.time() * 1000)
        self.isdb(database)
        self.endTime = int(time.time() * 1000)
        return self.patterns

    def isdb(self, originalDatabase):
        mapSequenceID = self.findSequencesContainingItems(originalDatabase)
        self.initialDatabase = PseudoSequenceDatabase()
        for sequence in originalDatabase.getSequences():
            optimizedSequence = sequence.cloneSequenceMinusItems(mapSequenceID, self.minsuppRelative)
            if optimizedSequence.size() != 0:
                self.initialDatabase.addSequence(PseudoSequence(0, optimizedSequence, 0, 0))

        mapSequenceIDOrder = _java_hashmap_iteration_order(list(mapSequenceID.keys()), _java_hash_for_item_simple)
        for item in mapSequenceIDOrder:
            seqIds = mapSequenceID[item]
            if len(seqIds) >= self.minsuppRelative:
                projectedContexts = None
                if isinstance(item, ItemValued):
                    projectedContexts = self.buildProjectedContextItemValued(item, self.initialDatabase, False, -1)
                else:
                    projectedContexts = self.buildProjectedDatabase(item, self.initialDatabase, False, -1)

                for projectedDatabase in projectedContexts:
                    prefix = Sequence(0)
                    if projectedDatabase.getCluster() is None:
                        prefix.addItemset(Itemset(item, 0))
                        prefix.setSequencesID(seqIds)
                    else:
                        cluster = projectedDatabase.getCluster()
                        item2 = ItemValued(item.getId(), cluster.getaverage(), cluster.getLower(), cluster.getHigher())
                        prefix.addItemset(Itemset(item2, 0))
                        prefix.setSequencesID(cluster.getSequenceIDs())

                    maxSuccessorSupport = 0
                    if (not self.findClosedPatterns) or (not self.checkBackScanPruning(prefix)):
                        maxSuccessorSupport = self.projection(prefix, 2, projectedDatabase)

                    if self.isMinWholeIntervalRespected(prefix):
                        noForwardSIExtension = (not self.findClosedPatterns) or (prefix.getAbsoluteSupport() != maxSuccessorSupport)
                        noBackwardExtension = (not self.findClosedPatterns) or (not self.checkBackwardExtension(prefix))
                        if noForwardSIExtension and noBackwardExtension:
                            self.savePattern(prefix)

    def savePattern(self, prefix):
        self.patternCount += 1
        if self.writer is not None:
            r = []
            for itemset in prefix.getItemsets():
                r.append("<")
                r.append(str(itemset.getTimestamp()))
                r.append("> ")
                for item in itemset.getItems():
                    r.append(str(item))
                    r.append(" ")
                r.append("-1 ")
            r.append(" #SUP: ")
            r.append(str(len(prefix.getSequencesID())))
            self.writer.write("".join(r))
            self.writer.write("\n")
            if self.patterns is not None:
                self.patterns.addSequence(prefix, prefix.size())
        else:
            self.patterns.addSequence(prefix, prefix.size())
    def checkBackwardExtension(self, prefix):
        for i in range(prefix.getItemOccurencesTotalCount()):
            maximumPeriods = []
            for sequence in self.initialDatabase.getPseudoSequences():
                if prefix.getSequencesID() and sequence.getId() in prefix.getSequencesID():
                    periods = sequence.getAllIthMaxPeriodOfAPrefix(prefix, i, True)
                    for period in periods:
                        if period is not None:
                            maximumPeriods.append(period)
            for pair in self.findAllFrequentPairsSatisfyingC1andC2ForBackwardExtensionCheck(prefix, maximumPeriods, i):
                if pair.getCount() == prefix.getAbsoluteSupport():
                    return True
        return False

    def checkBackScanPruning(self, prefix):
        if not self.enableBackscanPruning:
            return False
        for i in range(prefix.getItemOccurencesTotalCount()):
            semimaximumPeriods = []
            for sequence in self.initialDatabase.getPseudoSequences():
                if prefix.getSequencesID() and sequence.getId() in prefix.getSequencesID():
                    period = sequence.getIthSemiMaximumPeriodOfAPrefix(prefix, i, True)
                    if period is not None:
                        semimaximumPeriods.append(period)
            paires = self.findAllFrequentPairsSatisfyingC1andC2ForBackwardExtensionCheck(prefix, semimaximumPeriods, i)
            for pair in paires:
                if pair.getCount() == prefix.getAbsoluteSupport():
                    return True
        return False

    def findAllFrequentPairsSatisfyingC1andC2ForBackwardExtensionCheck(self, prefix, maximumPeriods, iPeriod):
        mapPaires = {}
        insertionOrder = []
        alreadyCountedForSequenceID = set()
        lastPeriod = None
        for period in maximumPeriods:
            if period != lastPeriod:
                alreadyCountedForSequenceID.clear()
                lastPeriod = period
            for i in range(period.size()):
                for j in range(period.getSizeOfItemsetAt(i)):
                    item = period.getItemAtInItemsetAt(j, i)
                    successorInterval = period.getTimeSucessor() - period.getAbsoluteTimeStamp(i)
                    totalTime = prefix.getTimeLength() + successorInterval
                    predecessorInterval = period.getAbsoluteTimeStamp(i) - period.getTimePredecessor()

                    checkGapSucessor = (successorInterval >= self.minInterval and successorInterval <= self.maxInterval) or successorInterval == 0
                    checkGapPredecessor = (predecessorInterval >= self.minInterval and predecessorInterval <= self.maxInterval) or iPeriod == 0 or predecessorInterval == 0
                    checkWholeInterval = (totalTime <= self.maxWholeInterval and totalTime >= self.minWholeInterval) or iPeriod != 0

                    if checkGapSucessor and checkGapPredecessor and checkWholeInterval:
                        paire = Pair(successorInterval, period.isCutAtRight(i), period.isCutAtLeft(i), item)
                        if paire not in alreadyCountedForSequenceID:
                            old = mapPaires.get(paire)
                            if old is None:
                                mapPaires[paire] = paire
                                insertionOrder.append(paire)
                            else:
                                paire = old
                            alreadyCountedForSequenceID.add(paire)
                            paire.getSequencesID().add(period.getId())
        return _java_hashmap_iteration_order(insertionOrder, _java_hash_for_pair)

    def findAllFrequentPairsSatisfyingC1andC2(self, prefixe, database):
        mapPaires = {}
        insertionOrder = []
        lastSequence = None
        alreadyCountedForSequenceID = set()
        for sequence in database:
            if lastSequence is None or sequence.getId() != lastSequence.getId():
                alreadyCountedForSequenceID.clear()
                lastSequence = sequence
            for i in range(sequence.size()):
                for j in range(sequence.getSizeOfItemsetAt(i)):
                    item = sequence.getItemAtInItemsetAt(j, i)
                    if self.isTheMinAndMaxIntervalRespected(sequence.getTimeStamp(i)) or sequence.isCutAtLeft(i):
                        paire = Pair(sequence.getTimeStamp(i), sequence.isCutAtRight(i), sequence.isCutAtLeft(i), item)
                        if paire not in alreadyCountedForSequenceID:
                            old = mapPaires.get(paire)
                            if old is None:
                                mapPaires[paire] = paire
                                insertionOrder.append(paire)
                            else:
                                paire = old
                            alreadyCountedForSequenceID.add(paire)
                            paire.getSequencesID().add(sequence.getId())
        return _java_hashmap_iteration_order(insertionOrder, _java_hash_for_pair)

    def buildProjectedDatabase(self, item, contexte, inSuffix, timestamp):
        sequenceDatabase = PseudoSequenceDatabase()
        for sequence in contexte.getPseudoSequences():
            for i in range(sequence.size()):
                if timestamp != -1 and timestamp != sequence.getTimeStamp(i):
                    continue
                index = sequence.indexOf(i, item.getId())
                if index != -1 and sequence.isCutAtLeft(i) == inSuffix:
                    if index != sequence.getSizeOfItemsetAt(i) - 1:
                        newSequence = PseudoSequence(sequence.getAbsoluteTimeStamp(i), sequence, i, index + 1)
                        if newSequence.size() > 0:
                            sequenceDatabase.addSequence(newSequence)
                    elif i != sequence.size() - 1:
                        newSequence = PseudoSequence(sequence.getAbsoluteTimeStamp(i), sequence, i + 1, 0)
                        if newSequence.size() > 0:
                            sequenceDatabase.addSequence(newSequence)
        return [sequenceDatabase]

    def buildProjectedContextItemValued(self, item, database, inSuffix, timestamp):
        sequenceDatabase = PseudoSequenceDatabase()
        removedItems = []
        removedItemsDestroyed = []
        for sequence in database.getPseudoSequences():
            for i in range(sequence.size()):
                if timestamp != -1 and timestamp != sequence.getTimeStamp(i):
                    continue
                index = sequence.indexOf(i, item.getId())
                if index != -1 and sequence.isCutAtLeft(i) == inSuffix:
                    if index != sequence.getSizeOfItemsetAt(i) - 1:
                        newSequence = PseudoSequence(sequence.getAbsoluteTimeStamp(i), sequence, i, index + 1)
                        if newSequence.size() > 0:
                            sequenceDatabase.addSequence(newSequence)
                        removedItems.append(sequence.getItemAtInItemsetAt(index, i))
                    elif i == sequence.size() - 1:
                        removedItemsDestroyed.append(sequence.getItemAtInItemsetAt(index, i))
                    else:
                        newSequence = PseudoSequence(sequence.getAbsoluteTimeStamp(i), sequence, i + 1, 0)
                        if newSequence.size() > 0:
                            sequenceDatabase.addSequence(newSequence)
                        removedItems.append(sequence.getItemAtInItemsetAt(index, i))
        return self.breakInClusters(item, database, sequenceDatabase, removedItems, removedItemsDestroyed)

    def breakInClusters(self, item, database, sequenceDatabase, removedItems, removedItemsDestroyed):
        if len(removedItems) == 0 and len(removedItemsDestroyed) == 0:
            return [sequenceDatabase]
        if sequenceDatabase.getSequenceIDs() and len(sequenceDatabase.getSequenceIDs()) >= (self.minsuppRelative * 2):
            sequenceDatabases = self.createSequenceDatabasesByClusters(sequenceDatabase, removedItems)
        else:
            sequenceDatabases = [sequenceDatabase]
            cluster = Cluster(items=removedItems, items2=removedItemsDestroyed)
            cluster.addItems(removedItemsDestroyed)
            cluster.computeHigherAndLower()
            sequenceDatabase.setCluster(cluster)
        self.findSequencesContainingClusters(database, sequenceDatabases, item)
        return sequenceDatabases

    def findSequencesContainingClusters(self, database, sequenceDatabases, item):
        clusters = []
        for seqDb in sequenceDatabases:
            clusters.append(seqDb.getCluster())
            clusters[-1].setSequenceIDs(set())
        alreadyCounted = set()
        lastSequence = None
        for sequence in database.getPseudoSequences():
            if lastSequence is None or sequence.getId() != lastSequence.getId():
                alreadyCounted.clear()
                lastSequence = sequence
            for i in range(sequence.size()):
                for j in range(sequence.getSizeOfItemsetAt(i)):
                    item2 = sequence.getItemAtInItemsetAt(j, i)
                    if item2.getId() == item.getId():
                        cluster = self.findClusterContainingItem(clusters, item2)
                        if cluster is not None and cluster not in alreadyCounted:
                            cluster.getSequenceIDs().add(sequence.getId())
                            alreadyCounted.add(cluster)

    def findClusterContainingItem(self, clusters, item):
        for cluster in clusters:
            if cluster is not None and cluster.containsItem(item):
                return cluster
        return None

    def createSequenceDatabasesByClusters(self, database, items):
        for i in range(len(items)):
            items[i].setSequenceID(database.getPseudoSequences()[i].getId())
        clusters = self.algoClustering.runAlgorithm(items)
        sequenceDatabases = [None] * len(clusters)
        for i in range(database.size()):
            item = items[i]
            clusterIndex = -1
            for idx, cluster in enumerate(clusters):
                if item.getCluster() == cluster:
                    clusterIndex = idx
                    break
            if clusterIndex == -1:
                continue
            if sequenceDatabases[clusterIndex] is None:
                sequenceDatabases[clusterIndex] = PseudoSequenceDatabase()
                sequenceDatabases[clusterIndex].setCluster(clusters[clusterIndex])
            sequenceDatabases[clusterIndex].addSequence(database.getPseudoSequences()[i])
        return [db for db in sequenceDatabases if db is not None]
    def appendItemToSequence(self, prefix, item, timestamp):
        newPrefix = prefix.cloneSequence()
        decalage = newPrefix.get(newPrefix.size() - 1).getTimestamp()
        newPrefix.addItemset(Itemset(item, timestamp + decalage))
        return newPrefix

    def appendItemToPrefixOfSequence(self, prefix, item):
        newPrefix = prefix.cloneSequence()
        itemset = newPrefix.get(newPrefix.size() - 1)
        itemset.addItem(item)
        return newPrefix

    def projection(self, prefix, k, database):
        maxSupport = 0
        for pair in self.findAllFrequentPairsSatisfyingC1andC2(prefix, database.getPseudoSequences()):
            if pair.getCount() >= self.minsuppRelative:
                if pair.isPostfix():
                    newPrefix = self.appendItemToPrefixOfSequence(prefix, pair.getItem())
                else:
                    newPrefix = self.appendItemToSequence(prefix, pair.getItem(), pair.getTimestamp())
                if self.isMaxWholeIntervalRespected(newPrefix):
                    successorSupport = self.projectionPair(newPrefix, pair, prefix, database, k)
                    if successorSupport > maxSupport:
                        maxSupport = successorSupport
        return maxSupport

    def isTheMinAndMaxIntervalRespected(self, timeInterval):
        return (timeInterval >= self.minInterval) and (timeInterval <= self.maxInterval)

    def isMaxWholeIntervalRespected(self, sequence):
        return sequence.get(sequence.size() - 1).getTimestamp() <= self.maxWholeInterval

    def isMinWholeIntervalRespected(self, sequence):
        return sequence.get(sequence.size() - 1).getTimestamp() >= self.minWholeInterval

    def projectionPair(self, newPrefix, paire, oldPrefix, database, k):
        maxSupport = 0
        if isinstance(paire.getItem(), ItemValued):
            projectedContexts = self.buildProjectedContextItemValued(paire.getItem(), database, paire.isPostfix(), paire.getTimestamp())
        else:
            projectedContexts = self.buildProjectedDatabase(paire.getItem(), database, paire.isPostfix(), paire.getTimestamp())

        for projectedContext in projectedContexts:
            if projectedContext.getCluster() is None:
                prefix = newPrefix.cloneSequence()
                prefix.setSequencesID(paire.getSequencesID())
            else:
                cluster = projectedContext.getCluster()
                item2 = ItemValued(cluster.getItemId(), cluster.getaverage(), cluster.getLower(), cluster.getHigher())
                sequenceIDs = cluster.getSequenceIDs()
                if paire.isPostfix():
                    prefix = self.appendItemToPrefixOfSequence(oldPrefix, item2)
                else:
                    prefix = self.appendItemToSequence(oldPrefix, item2, paire.getTimestamp())
                prefix.setSequencesID(sequenceIDs)

            maxSuccessor = 0
            if (not self.findClosedPatterns) or (not self.checkBackScanPruning(prefix)):
                maxSuccessor = self.projection(prefix, k + 1, projectedContext)

            if self.isMinWholeIntervalRespected(prefix):
                noForwardSIExtension = (not self.findClosedPatterns) or (prefix.getAbsoluteSupport() != maxSuccessor)
                noBackwardExtension = (not self.findClosedPatterns) or (not self.checkBackwardExtension(prefix))
                if noForwardSIExtension and noBackwardExtension:
                    self.savePattern(prefix)
                if prefix.getAbsoluteSupport() > maxSupport:
                    maxSupport = prefix.getAbsoluteSupport()
        return maxSupport
    def findSequencesContainingItems(self, database):
        mapSequenceID = {}
        for sequence in database.getSequences():
            alreadyCounted = set()
            for itemset in sequence.getItemsets():
                for item in itemset.getItems():
                    if item.getId() not in alreadyCounted:
                        sequenceIDs = mapSequenceID.get(item)
                        if sequenceIDs is None:
                            sequenceIDs = set()
                            mapSequenceID[item] = sequenceIDs
                        sequenceIDs.add(sequence.getId())
                        alreadyCounted.add(item.getId())
        return mapSequenceID

    def printStatistics(self):
        r = []
        r.append("=============  Algorithm - STATISTICS =============\n Total time ~ ")
        r.append(str(self.endTime - self.startTime))
        r.append(" ms\n")
        r.append(" Frequent sequences count : ")
        r.append(str(self.patternCount))
        r.append("\n")
        r.append("===================================================\n")
        print("".join(r))

    def printResult(self, databaseSize):
        r = []
        r.append("=============  Algorithm - STATISTICS =============\n Total time ~ ")
        r.append(str(self.endTime - self.startTime))
        r.append(" ms\n")
        r.append(" Frequent sequences count : ")
        r.append(str(self.patternCount))
        r.append("\n")
        r.append(self.patterns.toString(databaseSize))
        r.append("===================================================\n")
        print("".join(r))

    def getMinSupp(self):
        return self.minsupp

    def getMinsuppRelative(self):
        return self.minsuppRelative

def fileToPath(filename):
    base = os.path.dirname(__file__)
    return os.path.join(base, filename)


def main():
    sequenceDatabase = SequenceDatabase()
    sequenceDatabase.loadFile(fileToPath("contextSequencesTimeExtended.txt"))
    sequenceDatabase.print()

    algo = AlgoFournierViger08(0.55, 0, 2, 0, 100, None, True, True)
    outputPath = os.path.join(os.path.dirname(__file__), "outputs.txt")
    algo.runAlgorithmToFile(sequenceDatabase, outputPath)
    algo.printResult(sequenceDatabase.size())


if __name__ == "__main__":
    main()


