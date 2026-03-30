import math
import os
import time
import tracemalloc


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


class AbstractItemset:
    def __init__(self):
        pass


class AbstractOrderedItemset(AbstractItemset):
    def __init__(self):
        super().__init__()

    def getAbsoluteSupport(self):
        raise NotImplementedError

    def size(self):
        raise NotImplementedError

    def get(self, position):
        raise NotImplementedError

    def getLastItem(self):
        return self.get(self.size() - 1)

    def __str__(self):
        if self.size() == 0:
            return "EMPTYSET"
        r = []
        for i in range(self.size()):
            r.append(str(self.get(i)))
            r.append(" ")
        return "".join(r)

    def getRelativeSupport(self, nbObject):
        return float(self.getAbsoluteSupport()) / float(nbObject)

    def contains(self, item):
        for i in range(self.size()):
            if self.get(i) == item:
                return True
            if self.get(i) > item:
                return False
        return False

    def containsAll(self, itemset2):
        if self.size() < itemset2.size():
            return False
        i = 0
        for j in range(itemset2.size()):
            found = False
            while not found and i < self.size():
                if self.get(i) == itemset2.get(j):
                    found = True
                elif self.get(i) > itemset2.get(j):
                    return False
                i += 1
            if not found:
                return False
        return True

    def isEqualTo(self, itemset2):
        if self.size() != itemset2.size():
            return False
        for i in range(itemset2.size()):
            if itemset2.get(i) != self.get(i):
                return False
        return True

    def isEqualToArray(self, itemset):
        if self.size() != len(itemset):
            return False
        for i in range(len(itemset)):
            if itemset[i] != self.get(i):
                return False
        return True

    def allTheSameExceptLastItemV2(self, itemset2):
        if itemset2.size() != self.size():
            return False
        for i in range(self.size() - 1):
            if self.get(i) != itemset2.get(i):
                return False
        return True

    def allTheSameExceptLastItem(self, itemset2):
        if itemset2.size() != self.size():
            return None
        for i in range(self.size()):
            if i == self.size() - 1:
                if self.get(i) >= itemset2.get(i):
                    return None
            elif self.get(i) != itemset2.get(i):
                return None
        return itemset2.get(itemset2.size() - 1)


class ItemsetTids(AbstractOrderedItemset):
    def __init__(self, items=None):
        super().__init__()
        self.itemset = items if items is not None else []
        self.transactionsIds = set()

    def getAbsoluteSupport(self):
        return len(self.transactionsIds)

    def getItems(self):
        return self.itemset

    def get(self, index):
        return self.itemset[index]

    def setTIDs(self, tids):
        self.transactionsIds = tids

    def size(self):
        return len(self.itemset)

    def getTransactionsIds(self):
        return self.transactionsIds

    def cloneItemSetMinusAnItemset(self, itemsetToNotKeep):
        newItemset = []
        for item in self.itemset:
            if not itemsetToNotKeep.contains(item):
                newItemset.append(item)
        return ItemsetTids(list(newItemset))

    def cloneItemSetMinusOneItem(self, itemsetToRemove):
        newItemset = []
        for item in self.itemset:
            if item != itemsetToRemove:
                newItemset.append(item)
        return ItemsetTids(list(newItemset))


class ItemsetsTids:
    def __init__(self, name):
        self.name = name
        self.levels = []
        self.itemsetsCount = 0

    def addItemset(self, itemset, k):
        while len(self.levels) <= k:
            self.levels.append([])
        self.levels[k].append(itemset)
        self.itemsetsCount += 1

    def getLevels(self):
        return self.levels

    def getLevel(self, i):
        return self.levels[i]

    def size(self):
        return self.itemsetsCount

    def printItemsets(self, nbObject):
        print(self.toString(nbObject))

    def toString(self, nbObject):
        buffer = []
        buffer.append(self.name)
        buffer.append("\n")
        levelCount = 0
        for level in self.levels:
            buffer.append("  L" + str(levelCount) + " \n")
            for itemset in level:
                buffer.append("  " + str(itemset))
                buffer.append(" #SUP: ")
                buffer.append(str(itemset.getAbsoluteSupport()))
                buffer.append(" #REL: ")
                buffer.append(str(itemset.getRelativeSupport(nbObject)))
                buffer.append("\n")
            levelCount += 1
        return "".join(buffer)


class TransactionDatabase:
    def __init__(self):
        self.transactions = []

    def addTransaction(self, transaction):
        self.transactions.append(transaction)

    def getTransactions(self):
        return self.transactions

    def size(self):
        return len(self.transactions)


class AlgoAprioriTID:
    def __init__(self):
        self.k = 0
        self.mapItemTIDS = {}
        self.minSuppRelative = 0
        self.maxItemsetSize = 2147483647
        self.startTimestamp = 0
        self.endTimeStamp = 0
        self.writer = None
        self.patterns = None
        self.itemsetCount = 0
        self.databaseSize = 0
        self.database = None
        self.emptySetIsRequired = False
        self.showTransactionIdentifiers = False

    def runAlgorithm(self, database, minsup):
        self.database = database
        result = self._runAlgorithm(None, None, minsup)
        self.database = None
        return result

    def _runAlgorithm(self, inputPath, outputPath, minsup):
        self.startTimestamp = int(time.time() * 1000)
        self.itemsetCount = 0
        if outputPath is None:
            self.writer = None
            self.patterns = ItemsetsTids("FREQUENT ITEMSETS")
        else:
            self.patterns = None
            self.writer = open(outputPath, "w")

        self.mapItemTIDS = {}
        self.databaseSize = 0
        if self.database is not None:
            for transaction in self.database.getTransactions():
                for item in transaction:
                    tids = self.mapItemTIDS.get(item)
                    if tids is None:
                        tids = set()
                        self.mapItemTIDS[item] = tids
                    tids.add(self.databaseSize)
                self.databaseSize += 1
        else:
            reader = open(inputPath, "r")
            for line in reader:
                line = line.strip()
                if not line:
                    continue
                if line[0] == '#' or line[0] == '%' or line[0] == '@':
                    continue
                lineSplited = line.split(" ")
                for token in lineSplited:
                    item = int(token)
                    tids = self.mapItemTIDS.get(item)
                    if tids is None:
                        tids = set()
                        self.mapItemTIDS[item] = tids
                    tids.add(self.databaseSize)
                self.databaseSize += 1
            reader.close()

        if self.emptySetIsRequired and self.patterns is not None:
            self.patterns.addItemset(ItemsetTids([]), 0)

        self.minSuppRelative = int(math.ceil(minsup * self.databaseSize))

        self.k = 1
        level = []
        for item, tids in list(self.mapItemTIDS.items()):
            MemoryLogger.getInstance().checkMemory()
            if len(tids) >= self.minSuppRelative and self.maxItemsetSize >= 1:
                itemset = ItemsetTids([item])
                itemset.setTIDs(tids)
                level.append(itemset)
                self.saveItemset(itemset)
            else:
                self.mapItemTIDS.pop(item, None)

        level.sort(key=lambda x: x.get(0))

        self.k = 2
        while level and self.k <= self.maxItemsetSize:
            level = self.generateCandidateSizeK(level)
            self.k += 1

        if self.writer is not None:
            self.writer.close()
        self.endTimeStamp = int(time.time() * 1000)
        return self.patterns

    def generateCandidateSizeK(self, levelK_1):
        candidates = []
        for i in range(len(levelK_1)):
            itemset1 = levelK_1[i]
            for j in range(i + 1, len(levelK_1)):
                itemset2 = levelK_1[j]
                for k in range(itemset1.size()):
                    if k == itemset1.size() - 1:
                        if itemset1.getItems()[k] >= itemset2.get(k):
                            break
                    elif itemset1.getItems()[k] < itemset2.getItems()[k]:
                        continue
                    elif itemset1.getItems()[k] > itemset2.getItems()[k]:
                        break
                else:
                    list_tids = set()
                    for val1 in itemset1.getTransactionsIds():
                        if val1 in itemset2.getTransactionsIds():
                            list_tids.add(val1)
                    if len(list_tids) >= self.minSuppRelative:
                        newItemset = list(itemset1.itemset)
                        newItemset.append(itemset2.getItems()[itemset2.size() - 1])
                        candidate = ItemsetTids(newItemset)
                        candidate.setTIDs(list_tids)
                        candidates.append(candidate)
                        self.saveItemset(candidate)
        return candidates

    def saveItemset(self, itemset):
        self.itemsetCount += 1
        if self.writer is not None:
            self.writer.write(str(itemset) + " #SUP: " + str(len(itemset.getTransactionsIds())))
            if self.showTransactionIdentifiers:
                self.writer.write(" #TID:")
                for tid in itemset.getTransactionsIds():
                    self.writer.write(" " + str(tid))
            self.writer.write("\n")
        else:
            self.patterns.addItemset(itemset, itemset.size())

    def setEmptySetIsRequired(self, emptySetIsRequired):
        self.emptySetIsRequired = emptySetIsRequired

    def setShowTransactionIdentifiers(self, showTransactionIdentifiers):
        self.showTransactionIdentifiers = showTransactionIdentifiers

    def printStats(self):
        print("=============  APRIORI TID v2.12 - STATS =============")
        print(" Transactions count from database : " + str(self.databaseSize))
        print(" Frequent itemsets count : " + str(self.itemsetCount))
        print(" Maximum memory usage : " + str(MemoryLogger.getInstance().getMaxMemory()) + " mb")
        print(" Total time ~ " + str(self.endTimeStamp - self.startTimestamp) + " ms")
        print("===================================================")

    def getDatabaseSize(self):
        return self.databaseSize

    def setMaximumPatternLength(self, length):
        self.maxItemsetSize = length

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
        return hash(self.id)

    def __lt__(self, other):
        return self.id < other.id


class ItemValued(ItemSimple):
    def __init__(self, item_id, value):
        super().__init__(item_id)
        self.value = value

    def getValue(self):
        return self.value

    def __str__(self):
        return str(self.id) + "(" + str(self.value) + ")"


class ItemsetSeq:
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
        for attribute in self.items:
            r.append(str(attribute))
            r.append(" ")
        return "".join(r)

    def toPrettyString(self):
        r = []
        for attribute in self.items:
            if isinstance(attribute, ItemValued):
                r.append(str(attribute.getId()))
                r.append("(value=")
                r.append(str(attribute.getValue()))
                r.append(") ")
            else:
                r.append(str(attribute))
                r.append(" ")
        return "".join(r)

    def cloneItemSetMinusItems(self, mapSequenceID, relativeMinsup):
        itemset = ItemsetSeq()
        itemset.timestamp = self.timestamp
        for item in self.items:
            if len(mapSequenceID.get(item, set())) >= relativeMinsup:
                itemset.addItem(item)
        return itemset

    def cloneItemSet(self):
        itemset = ItemsetSeq()
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
        self.sequencesID = set()

    def addItemset(self, itemset):
        self.itemsets.append(itemset)

    def getItemsets(self):
        return self.itemsets

    def get(self, index):
        return self.itemsets[index]

    def size(self):
        return len(self.itemsets)

    def getId(self):
        return self.id

    def setSequencesID(self, seqIds):
        self.sequencesID = set(seqIds)

    def getSequencesID(self):
        return self.sequencesID

    def __str__(self):
        sb = []
        for itemset in self.itemsets:
            sb.append("{")
            sb.append(str(itemset))
            sb.append("}")
        return "".join(sb)

    def toStringShort(self):
        sb = []
        for itemset in self.itemsets:
            sb.append("{t=")
            sb.append(str(itemset.getTimestamp()))
            sb.append(", ")
            for item in itemset.getItems():
                sb.append(str(item))
                sb.append(" ")
            sb.append("}")
        sb.append("    ")
        return "".join(sb)

    def print(self):
        print(self.__str__())

    def cloneSequence(self):
        sequence = Sequence(self.id)
        for itemset in self.itemsets:
            sequence.addItemset(itemset.cloneItemSet())
        return sequence

    def cloneSequenceMinusItems(self, mapSequenceID, relativeMinsup):
        sequence = Sequence(self.id)
        for itemset in self.itemsets:
            newItemset = itemset.cloneItemSetMinusItems(mapSequenceID, relativeMinsup)
            if newItemset.size() > 0:
                sequence.addItemset(newItemset)
        return sequence


class SequenceDatabase:
    def __init__(self):
        self.sequences = []

    def loadFile(self, path):
        myInput = None
        try:
            myInput = open(path, "r")
            for thisLine in myInput:
                thisLine = thisLine.strip()
                if not thisLine:
                    continue
                if thisLine[0] == '#' or thisLine[0] == '%' or thisLine[0] == '@':
                    continue
                self.addSequence(thisLine.split(" "))
        finally:
            if myInput is not None:
                myInput.close()

    def addSequence(self, sequence_or_tokens):
        if isinstance(sequence_or_tokens, Sequence):
            self.sequences.append(sequence_or_tokens)
            return
        tokens = sequence_or_tokens
        sequence = Sequence(len(self.sequences))
        itemset = ItemsetSeq()
        for token in tokens:
            if token and token[0] == '<':
                value = token[1:len(token) - 1]
                itemset.setTimestamp(int(value))
            elif token == "-1":
                sequence.addItemset(itemset)
                itemset = ItemsetSeq()
            elif token == "-2":
                self.sequences.append(sequence)
            else:
                indexLeftParenthesis = token.find("(")
                if indexLeftParenthesis != -1:
                    indexRightParenthesis = token.find(")")
                    value = int(token[indexLeftParenthesis + 1:indexRightParenthesis])
                    token = token[0:indexLeftParenthesis]
                    item = ItemValued(int(token), value)
                    itemset.addItem(item)
                else:
                    item = ItemSimple(int(token))
                    itemset.addItem(item)

    def __str__(self):
        r = []
        for sequence in self.sequences:
            r.append(str(sequence.getId()))
            r.append(":  ")
            r.append(str(sequence))
            r.append("\n")
        return "".join(r)

    def size(self):
        return len(self.sequences)

    def getSequences(self):
        return self.sequences


class Sequences:
    def __init__(self, string):
        self.levels = [[]]
        self.sequenceCount = 0
        self.string = string

    def addSequence(self, sequence, k):
        while len(self.levels) <= k:
            self.levels.append([])
        self.levels[k].append(sequence)
        self.sequenceCount += 1

    def getLevel(self, i):
        return self.levels[i]

    def getLevelCount(self):
        return len(self.levels)

    def getLevels(self):
        return self.levels

    def toString(self, nbObject):
        sb = []
        sb.append(self.string)
        sb.append("\n")
        for level in self.levels:
            for sequence in level:
                sb.append(sequence.toStringShort())
                sb.append(" #SUP: ")
                sb.append(str(len(sequence.getSequencesID())))
                sb.append(" #REL: ")
                sb.append(str(float(len(sequence.getSequencesID())) / float(nbObject)))
                sb.append("\n")
        return "".join(sb)


class Pair:
    def __init__(self, postfix, isPostfixItemset, item):
        self.postfix = postfix
        self.isPostfixItemset = isPostfixItemset
        self.item = item
        self.sequencesID = set()

    def getSequencesID(self):
        return self.sequencesID

    def getCount(self):
        return len(self.sequencesID)

    def isPostfix(self):
        return self.isPostfixItemset

    def getItem(self):
        return self.item

    def getTimestamp(self):
        return 0

    def __hash__(self):
        return hash((self.isPostfixItemset, self.item))

    def __eq__(self, other):
        return isinstance(other, Pair) and self.isPostfixItemset == other.isPostfixItemset and self.item == other.item


class PseudoSequence:
    def __init__(self, absoluteTimeStamp, sequence, firstItemset, firstItem):
        self.absoluteTimeStamp = absoluteTimeStamp
        if isinstance(sequence, PseudoSequence):
            self.sequence = sequence.sequence
            self.firstItemset = firstItemset + sequence.firstItemset
            if self.firstItemset == sequence.firstItemset:
                self.firstItem = firstItem + sequence.firstItem
            else:
                self.firstItem = firstItem
            self.lastItemset = sequence.lastItemset
            self.lastItem = sequence.lastItem
        else:
            self.sequence = sequence
            self.firstItemset = firstItemset
            self.firstItem = firstItem
            self.lastItemset = sequence.size() - 1
            self.lastItem = sequence.get(self.lastItemset).size() - 1

    def size(self):
        size = self.sequence.size() - self.firstItemset - ((self.sequence.size() - 1) - self.lastItemset)
        if size == 1 and self.sequence.get(self.firstItemset).size() == 0:
            return 0
        return size

    def isFirstItemset(self, index):
        return index == 0

    def isLastItemset(self, index):
        return (index + self.firstItemset) == self.lastItemset

    def isCutAtLeft(self, indexItemset):
        return indexItemset == 0 and self.firstItem != 0

    def getSizeOfItemsetAt(self, indexItemset):
        size = self.sequence.get(indexItemset + self.firstItemset).size()
        if self.isLastItemset(indexItemset):
            size -= ((size - 1) - self.lastItem)
        if self.isFirstItemset(indexItemset):
            size -= self.firstItem
        return size

    def getItemAtInItemsetAt(self, indexItem, indexItemset):
        if self.isFirstItemset(indexItemset):
            return self.sequence.get(indexItemset + self.firstItemset).get(indexItem + self.firstItem)
        return self.sequence.get(indexItemset + self.firstItemset).get(indexItem)

    def getAbsoluteTimeStamp(self, indexItemset):
        return self.sequence.get(indexItemset + self.firstItemset).getTimestamp()

    def indexOf(self, indexItemset, itemId):
        for i in range(self.getSizeOfItemsetAt(indexItemset)):
            if self.getItemAtInItemsetAt(i, indexItemset).getId() == itemId:
                return i
        return -1

    def getId(self):
        return self.sequence.getId()


class PseudoSequenceDatabase:
    def __init__(self):
        self.sequences = []

    def addSequence(self, sequence):
        self.sequences.append(sequence)

    def getPseudoSequences(self):
        return self.sequences

class AbstractAlgoPrefixSpan:
    def runAlgorithm(self, database):
        raise NotImplementedError

    def getMinSupp(self):
        raise NotImplementedError


class AlgoPrefixSpanMDSPM(AbstractAlgoPrefixSpan):
    def __init__(self, minsup):
        self.patterns = None
        self.startTime = 0
        self.endTime = 0
        self.minsup = minsup
        self.minsuppRelative = 0

    def getMinSupp(self):
        return self.minsup

    def runAlgorithm(self, database):
        self.patterns = Sequences("FREQUENT SEQUENTIAL PATTERNS")
        self.minsuppRelative = int(math.ceil(self.minsup * database.size()))
        if self.minsuppRelative == 0:
            self.minsuppRelative = 1
        self.startTime = int(time.time() * 1000)
        self.prefixSpan(database)
        self.endTime = int(time.time() * 1000)
        return self.patterns

    def prefixSpan(self, database):
        mapSequenceID = self.calculateSupportOfItems(database)
        initialDatabase = PseudoSequenceDatabase()
        for sequence in database.getSequences():
            optimizedSequence = sequence.cloneSequenceMinusItems(mapSequenceID, self.minsuppRelative)
            if optimizedSequence.size() != 0:
                initialDatabase.addSequence(PseudoSequence(0, optimizedSequence, 0, 0))
        for item, seqIds in mapSequenceID.items():
            if len(seqIds) >= self.minsuppRelative:
                projectedDatabase = self.buildProjectedContext(item, initialDatabase, False)
                prefix = Sequence(0)
                prefix.addItemset(ItemsetSeq(item, 0))
                prefix.setSequencesID(seqIds)
                self.patterns.addSequence(prefix, 1)
                self.recursion(prefix, 2, projectedDatabase)

    def calculateSupportOfItems(self, database):
        alreadyCounted = set()
        lastSequence = None
        mapSequenceID = {}
        for sequence in database.getSequences():
            if lastSequence is None or lastSequence.getId() != sequence.getId():
                alreadyCounted.clear()
                lastSequence = sequence
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

    def buildProjectedContext(self, item, database, inSuffix):
        sequenceDatabase = PseudoSequenceDatabase()
        for sequence in database.getPseudoSequences():
            for i in range(sequence.size()):
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
        return sequenceDatabase

    def recursion(self, prefix, k, database):
        pairs = self.findAlllPairsAndCountTheirSupport(database.getPseudoSequences())
        for pair in pairs:
            if pair.getCount() >= self.minsuppRelative:
                if pair.isPostfix():
                    newPrefix = self.appendItemToPrefixOfSequence(prefix, pair.getItem())
                else:
                    newPrefix = self.appendItemToSequence(prefix, pair.getItem(), pair.getTimestamp())
                projectedContext = self.buildProjectedContext(pair.getItem(), database, pair.isPostfix())
                prefix2 = newPrefix.cloneSequence()
                prefix2.setSequencesID(pair.getSequencesID())
                self.patterns.addSequence(prefix2, prefix2.size())
                self.recursion(prefix2, k + 1, projectedContext)

    def findAlllPairsAndCountTheirSupport(self, sequences):
        mapPairs = {}
        lastSequence = None
        alreadyCounted = set()
        for sequence in sequences:
            if sequence != lastSequence:
                alreadyCounted.clear()
                lastSequence = sequence
            for i in range(sequence.size()):
                for j in range(sequence.getSizeOfItemsetAt(i)):
                    item = sequence.getItemAtInItemsetAt(j, i)
                    pair = Pair(False, sequence.isCutAtLeft(i), item)
                    if pair not in alreadyCounted:
                        oldPair = mapPairs.get(pair)
                        if oldPair is None:
                            mapPairs[pair] = pair
                        else:
                            pair = oldPair
                        alreadyCounted.add(pair)
                        pair.getSequencesID().add(sequence.getId())
        return set(mapPairs.keys())

    def appendItemToSequence(self, prefix, item, timestamp):
        newPrefix = prefix.cloneSequence()
        newPrefix.addItemset(ItemsetSeq(item, 0))
        return newPrefix

    def appendItemToPrefixOfSequence(self, prefix, item):
        newPrefix = prefix.cloneSequence()
        itemset = newPrefix.get(newPrefix.size() - 1)
        itemset.addItem(item)
        return newPrefix


class MDPattern:
    WILDCARD = 9999

    def __init__(self, pattern_id):
        self.id = pattern_id
        self.values = []
        self.patternsID = set()

    def addInteger(self, value):
        self.values.append(value)

    def addWildCard(self):
        self.values.append(MDPattern.WILDCARD)

    def size(self):
        return len(self.values)

    def getId(self):
        return self.id

    def getPatternsID(self):
        return self.patternsID

    def setPatternsIDList(self, patternsID):
        self.patternsID = set(patternsID)

    def getAbsoluteSupport(self):
        return len(self.patternsID)

    def __str__(self):
        r = ["[ " ]
        for v in self.values:
            if v == MDPattern.WILDCARD:
                r.append("* ")
            else:
                r.append(str(v))
                r.append(" ")
        r.append("]")
        return "".join(r)

    def toStringShort(self):
        r = ["[ " ]
        for v in self.values:
            if v == MDPattern.WILDCARD:
                r.append("* ")
            else:
                r.append(str(v))
                r.append(" ")
        r.append("]")
        return "".join(r)


class MDPatterns:
    def __init__(self, name):
        self.name = name
        self.levels = []
        self.patternCount = 0

    def addPattern(self, pattern, k):
        while len(self.levels) <= k:
            self.levels.append([])
        self.levels[k].append(pattern)
        self.patternCount += 1

    def getLevel(self, i):
        return self.levels[i]

    def getLevelCount(self):
        return len(self.levels)

    def getLevels(self):
        return self.levels

    def size(self):
        return self.patternCount

    def printPatterns(self, nbObject):
        print(self.toString(nbObject))

    def toString(self, nbObject):
        buffer = []
        buffer.append(self.name)
        buffer.append("\n")
        levelCount = 0
        for level in self.levels:
            buffer.append("  L" + str(levelCount) + " \n")
            for pattern in level:
                buffer.append("  " + str(pattern))
                buffer.append(" #SUP: ")
                buffer.append(str(pattern.getAbsoluteSupport()))
                buffer.append(" #REL: ")
                buffer.append(str(float(pattern.getAbsoluteSupport()) / float(nbObject)))
                buffer.append("\n")
            levelCount += 1
        return "".join(buffer)


class MDPatternsDatabase:
    def __init__(self):
        self.patterns = []

    def addMDPattern(self, pattern):
        self.patterns.append(pattern)

    def getMDPatterns(self):
        return self.patterns

    def size(self):
        return len(self.patterns)


class MDSequence:
    def __init__(self, sequence_id, mdpattern, sequence):
        self.id = sequence_id
        self.mdpattern = mdpattern
        self.sequence = sequence
        self.support = 0

    def getId(self):
        return self.id

    def getMdpattern(self):
        return self.mdpattern

    def getSequence(self):
        return self.sequence

    def setSupport(self, support):
        self.support = support

    def getAbsoluteSupport(self):
        return self.support

    def contains(self, mdsequence):
        return False

    def __str__(self):
        return str(self.mdpattern) + " -3 " + str(self.sequence)


class MDSequences:
    def __init__(self, string):
        self.levels = [[]]
        self.sequenceCount = 0
        self.string = string

    def addSequence(self, sequence, k):
        while len(self.levels) <= k:
            self.levels.append([])
        self.levels[k].append(sequence)
        self.sequenceCount += 1

    def getLevel(self, i):
        return self.levels[i]

    def getLevels(self):
        return self.levels


class MDSequenceDatabase:
    def __init__(self):
        self.sequences = []
        self.sequenceDatabase = SequenceDatabase()
        self.patternDatabase = MDPatternsDatabase()
        self.itemIDs = set()
        self.sequenceNumber = 0
        self.maxItemID = 0

    def getItemCount(self):
        return len(self.itemIDs)

    def loadFile(self, path):
        myInput = None
        try:
            myInput = open(path, "r")
            for thisLine in myInput:
                thisLine = thisLine.strip()
                if not thisLine:
                    continue
                if thisLine[0] == '#' or thisLine[0] == '%' or thisLine[0] == '@':
                    continue
                self.processMDSequence(thisLine.split(" "))
        finally:
            if myInput is not None:
                myInput.close()

    def processMDSequence(self, tokens):
        mdpattern = MDPattern(self.sequenceNumber)
        i = 0
        for i in range(len(tokens)):
            if tokens[i] == "-3":
                break
            elif tokens[i] == "*":
                mdpattern.addInteger(MDPattern.WILDCARD)
            else:
                mdpattern.addInteger(int(tokens[i]))
        sequence = Sequence(self.sequenceNumber)
        itemset = ItemsetSeq()
        i += 1
        while i < len(tokens):
            token = tokens[i]
            if token and token[0] == '<':
                value = token[1:len(token) - 1]
                itemset.setTimestamp(int(value))
            elif token == "-1":
                sequence.addItemset(itemset)
                itemset = ItemsetSeq()
            elif token == "-2":
                mdsequence = MDSequence(self.sequenceNumber, mdpattern, sequence)
                self.sequences.append(mdsequence)
                self.sequenceDatabase.addSequence(sequence)
                self.patternDatabase.addMDPattern(mdpattern)
                self.sequenceNumber += 1
            else:
                indexLeftParenthesis = token.find("(")
                if indexLeftParenthesis != -1:
                    indexRightParenthesis = token.find(")")
                    value = int(token[indexLeftParenthesis + 1:indexRightParenthesis])
                    token = token[0:indexLeftParenthesis]
                    itemAsInteger = int(token)
                    item = ItemValued(itemAsInteger, value)
                    itemset.addItem(item)
                    if itemAsInteger > self.maxItemID:
                        self.maxItemID = itemAsInteger
                else:
                    itemAsInteger = int(token)
                    item = ItemSimple(itemAsInteger)
                    itemset.addItem(item)
                    if itemAsInteger > self.maxItemID:
                        self.maxItemID = itemAsInteger
            i += 1

    def addSequence(self, sequence):
        self.sequences.append(sequence)
        self.sequenceDatabase.addSequence(sequence.getSequence())
        self.patternDatabase.addMDPattern(sequence.getMdpattern())

    def size(self):
        return len(self.sequences)

    def getSequences(self):
        return self.sequences

    def getSequenceDatabase(self):
        return self.sequenceDatabase

    def getPatternDatabase(self):
        return self.patternDatabase

    def getMaxItemID(self):
        return self.maxItemID


class AlgoDim:
    def __init__(self, findClosedPatterns, findClosedPatternsWithCharm):
        self.patterns = MDPatterns("Frequent MD Patterns")
        self.dimensionsCount = 0
        self.findClosedPatterns = findClosedPatterns
        self.findClosedPatternsWithCharm = findClosedPatternsWithCharm
        self.mapItemIdIdentifier = {}
        self.mapIdentifierItemId = {}
        self.lastUniqueItemIdGiven = 0

    def runAlgorithm(self, mdPatDatabase, minsupp):
        self.patterns = MDPatterns("FREQUENT MD Patterns")
        self.dimensionsCount = mdPatDatabase.getMDPatterns()[0].size()
        if self.findClosedPatternsWithCharm or self.findClosedPatterns:
            raise NotImplementedError("Closed pattern mining not implemented in this combined port.")
        database = TransactionDatabase()
        for pattern in mdPatDatabase.getMDPatterns():
            database.addTransaction(self.convertPatternToItemset(pattern))
        apriori = AlgoAprioriTID()
        closedItemsets = apriori.runAlgorithm(database, minsupp)
        apriori.setEmptySetIsRequired(True)
        for itemsets in closedItemsets.getLevels():
            for itemset in itemsets:
                pattern = self.convertItemsetToPattern(itemset)
                self.patterns.addPattern(pattern, pattern.size())
        self.patterns.addPattern(self.convertItemsetCharmToPattern(ItemsetTids([])), 0)
        return self.patterns

    def getValueForItemId(self, itemID):
        identifier = self.mapItemIdIdentifier.get(itemID)
        index = identifier.index("-")
        return int(identifier[:index])

    def getDimensionForItemId(self, value):
        identifier = self.mapItemIdIdentifier.get(value)
        index = identifier.index("-")
        return int(identifier[index + 1:])

    def convertDimensionValueToItemId(self, indexDimension, value):
        itemId = self.mapIdentifierItemId.get(str(value) + "-" + str(indexDimension))
        if itemId is None:
            itemId = self.lastUniqueItemIdGiven
            self.lastUniqueItemIdGiven += 1
            identifier = str(value) + "-" + str(indexDimension)
            self.mapIdentifierItemId[identifier] = itemId
            self.mapItemIdIdentifier[itemId] = identifier
        return itemId

    def convertPatternToItemset(self, pattern):
        itemset = []
        for i in range(len(pattern.values)):
            itemset.append(self.convertDimensionValueToItemId(i, pattern.values[i]))
        return itemset

    def convertItemsetToPattern(self, itemset):
        mdpattern = MDPattern(0)
        for i in range(self.dimensionsCount):
            for j in range(itemset.size()):
                dimension = self.getDimensionForItemId(itemset.get(j))
                value = self.getValueForItemId(itemset.get(j))
                if dimension == i:
                    mdpattern.addInteger(value)
            if mdpattern.size() == i:
                mdpattern.addWildCard()
        mdpattern.setPatternsIDList(itemset.getTransactionsIds())
        return mdpattern

    def convertItemsetCharmToPattern(self, itemset):
        mdpattern = MDPattern(0)
        for i in range(self.dimensionsCount):
            for j in range(itemset.size()):
                objects = itemset.getItems()
                dimension = self.getDimensionForItemId(objects[j])
                value = self.getValueForItemId(objects[j])
                if dimension == i:
                    mdpattern.addInteger(value)
            if mdpattern.size() == i:
                mdpattern.addWildCard()
        mdpattern.setPatternsIDList(itemset.getTransactionsIds())
        return mdpattern


class AlgoSeqDim:
    def __init__(self):
        self.sequences = MDSequences("FREQUENT MD-SEQUENCES")
        self.startTime = 0
        self.endTime = 0
        self.mineClosedPatterns = False
        self.writer = None
        self.patternCount = 0
        self.databaseSize = 0

    def runAlgorithm(self, database, algoPrefixSpan, algoDim, mineClosedPatterns, output):
        MemoryLogger.getInstance().reset()
        self.patternCount = 0
        self.startTime = int(time.time() * 1000)
        self.writer = open(output, "w")
        self.databaseSize = database.size()
        self.mineClosedPatterns = mineClosedPatterns
        sequencesFound = algoPrefixSpan.runAlgorithm(database.getSequenceDatabase())
        for j in range(sequencesFound.getLevelCount()):
            sequencesList = sequencesFound.getLevel(j)
            for sequence in sequencesList:
                self.trySequence(sequence, database, algoPrefixSpan.getMinSupp(), algoDim)
        if mineClosedPatterns:
            self.removeRedundancy()
        self.endTime = int(time.time() * 1000)
        MemoryLogger.getInstance().checkMemory()
        self.writer.close()
        return self.sequences

    def trySequence(self, sequence, database, minsupp, algoDim):
        newContexte = self.createProjectedDatabase(sequence.getSequencesID(), database.getPatternDatabase())
        newMinSupp = minsupp * database.size() / newContexte.size()
        patterns = algoDim.runAlgorithm(newContexte, newMinSupp)
        for i in range(patterns.getLevelCount()):
            for pattern in patterns.getLevel(i):
                mdsequence = MDSequence(0, pattern, sequence)
                onlyWildcards = True
                for pid in pattern.getPatternsID():
                    if pid != MDPattern.WILDCARD:
                        onlyWildcards = False
                        break
                if onlyWildcards:
                    mdsequence.setSupport(len(sequence.getSequencesID()))
                else:
                    mdsequence.setSupport(pattern.getAbsoluteSupport())
                self.savePattern(sequence, mdsequence)

    def savePattern(self, sequence, mdsequence):
        if not self.mineClosedPatterns:
            self.writeToFile(mdsequence)
        else:
            self.sequences.addSequence(mdsequence, sequence.size())
        self.patternCount += 1

    def writeToFile(self, mdsequence):
        buffer = []
        buffer.append(mdsequence.getMdpattern().toStringShort())
        buffer.append(mdsequence.getSequence().toStringShort())
        buffer.append(" #SUP: ")
        buffer.append(str(mdsequence.getAbsoluteSupport()))
        self.writer.write("".join(buffer))
        self.writer.write("\n")

    def createProjectedDatabase(self, patternsIds, patternsDatabase):
        projectedDatabase = MDPatternsDatabase()
        for pattern in patternsDatabase.getMDPatterns():
            if pattern.getId() in patternsIds:
                projectedDatabase.addMDPattern(pattern)
        return projectedDatabase

    def printStatistics(self, databaseSize):
        r = []
        r.append("=============  SEQ-DIM - STATISTICS =============\n Total time ~ ")
        r.append(str(self.endTime - self.startTime))
        r.append(" ms\n")
        r.append(" max memory : ")
        r.append(str(MemoryLogger.getInstance().getMaxMemory()))
        r.append("\n Frequent sequences count : ")
        r.append(str(self.patternCount))
        print("".join(r))
        print("===================================================")

    def removeRedundancy(self):
        for i in range(len(self.sequences.getLevels()) - 1, 0, -1):
            for sequence in self.sequences.getLevel(i):
                included = False
                for j in range(i, len(self.sequences.getLevels())):
                    if included:
                        break
                    for sequence2 in self.sequences.getLevel(j):
                        if sequence != sequence2 and sequence2.getAbsoluteSupport() == sequence.getAbsoluteSupport() and sequence2.contains(sequence):
                            included = True
                            break
                if not included:
                    self.writeToFile(sequence)


def main():
    minsupp = 0.5
    inputPath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ContextMDSequenceNoTime.txt")
    outputPath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs.txt")
    contextMDDatabase = MDSequenceDatabase()
    contextMDDatabase.loadFile(inputPath)
    algoDim = AlgoDim(False, False)
    algoSeqDim = AlgoSeqDim()
    prefixSpan = AlgoPrefixSpanMDSPM(minsupp)
    algoSeqDim.runAlgorithm(contextMDDatabase, prefixSpan, algoDim, False, outputPath)
    algoSeqDim.printStatistics(contextMDDatabase.size())


if __name__ == "__main__":
    main()
