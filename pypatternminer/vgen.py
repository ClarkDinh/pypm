import bisect
import math
import os
import time
import tracemalloc

MAX_INT = (1 << 31) - 1


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


class SimpleBitSet:
    def __init__(self):
        self._bits = set()
        self._sorted_cache = None

    def set(self, pos, value=True):
        if value:
            if pos not in self._bits:
                self._bits.add(pos)
                self._sorted_cache = None
        else:
            if pos in self._bits:
                self._bits.remove(pos)
                self._sorted_cache = None

    def get(self, pos):
        return pos in self._bits

    def next_set_bit(self, start):
        if not self._bits:
            return -1
        if self._sorted_cache is None:
            self._sorted_cache = sorted(self._bits)
        idx = bisect.bisect_left(self._sorted_cache, start)
        if idx >= len(self._sorted_cache):
            return -1
        return self._sorted_cache[idx]


class Bitmap:
    INTERSECTION_COUNT = 0

    def __init__(self, last_bit_index=None, bitset=None):
        self.bitmap = bitset if bitset is not None else SimpleBitSet()
        self.lastSID = -1
        self.firstItemsetID = -1
        self.support = 0
        self.sidsum = 0
        self.supportWithoutGapTotal = 0

    def registerBit(self, sid, tid, sequencesSize):
        pos = sequencesSize[sid] + tid
        self.bitmap.set(pos, True)
        if sid != self.lastSID:
            self.support += 1
            self.sidsum += sid
        if self.firstItemsetID == -1 or tid < self.firstItemsetID:
            self.firstItemsetID = tid
        self.lastSID = sid

    def bitToSID(self, bit, sequencesSize):
        idx = bisect.bisect_left(sequencesSize, bit)
        if idx < len(sequencesSize) and sequencesSize[idx] == bit:
            return idx
        return idx - 1

    def getSupport(self):
        return self.support

    def createNewBitmapSStep(self, bitmapItem, sequencesSize, lastBitIndex, maxGap):
        newBitmap = Bitmap(bitset=SimpleBitSet())
        if maxGap == MAX_INT:
            bitK = self.bitmap.next_set_bit(0)
            while bitK >= 0:
                sid = self.bitToSID(bitK, sequencesSize)
                lastBitOfSID = self.lastBitOfSID(sid, sequencesSize, lastBitIndex)
                match = False
                bit = bitmapItem.bitmap.next_set_bit(bitK + 1)
                while bit >= 0 and bit <= lastBitOfSID:
                    newBitmap.bitmap.set(bit)
                    match = True
                    tid = bit - sequencesSize[sid]
                    if self.firstItemsetID == -1 or tid < self.firstItemsetID:
                        self.firstItemsetID = tid
                    bit = bitmapItem.bitmap.next_set_bit(bit + 1)
                if match:
                    if sid != newBitmap.lastSID:
                        newBitmap.support += 1
                        newBitmap.supportWithoutGapTotal += 1
                        newBitmap.sidsum += sid
                        newBitmap.lastSID = sid
                bitK = self.bitmap.next_set_bit(lastBitOfSID + 1)
        else:
            previousSid = -1
            bitK = self.bitmap.next_set_bit(0)
            while bitK >= 0:
                sid = self.bitToSID(bitK, sequencesSize)
                lastBitOfSID = self.lastBitOfSID(sid, sequencesSize, lastBitIndex)
                match = False
                matchWithoutGap = False
                bit = bitmapItem.bitmap.next_set_bit(bitK + 1)
                while bit >= 0 and bit <= lastBitOfSID:
                    matchWithoutGap = True
                    if bit - bitK > maxGap:
                        break
                    newBitmap.bitmap.set(bit)
                    match = True
                    tid = bit - sequencesSize[sid]
                    if self.firstItemsetID == -1 or tid < self.firstItemsetID:
                        self.firstItemsetID = tid
                    bit = bitmapItem.bitmap.next_set_bit(bit + 1)
                if matchWithoutGap and previousSid != sid:
                    newBitmap.supportWithoutGapTotal += 1
                    previousSid = sid
                if match:
                    if sid != newBitmap.lastSID:
                        newBitmap.support += 1
                        newBitmap.sidsum += sid
                    newBitmap.lastSID = sid
                bitK = self.bitmap.next_set_bit(bitK + 1)
        return newBitmap

    def getSupportWithoutGapTotal(self):
        return self.supportWithoutGapTotal

    def lastBitOfSID(self, sid, sequencesSize, lastBitIndex):
        if sid + 1 >= len(sequencesSize):
            return lastBitIndex
        return sequencesSize[sid + 1] - 1

    def createNewBitmapIStep(self, bitmapItem, sequencesSize, lastBitIndex):
        newBitmap = Bitmap(bitset=SimpleBitSet())
        bit = self.bitmap.next_set_bit(0)
        while bit >= 0:
            if bitmapItem.bitmap.get(bit):
                newBitmap.bitmap.set(bit)
                sid = self.bitToSID(bit, sequencesSize)
                if sid != newBitmap.lastSID:
                    newBitmap.sidsum += sid
                    newBitmap.support += 1
                newBitmap.lastSID = sid
                tid = bit - sequencesSize[sid]
                if self.firstItemsetID == -1 or tid < self.firstItemsetID:
                    self.firstItemsetID = tid
            bit = self.bitmap.next_set_bit(bit + 1)
        return newBitmap

    def setSupport(self, support):
        self.support = support

    def getSIDs(self, sequencesSize):
        builder = []
        lastSidSeen = -1
        bitK = self.bitmap.next_set_bit(0)
        while bitK >= 0:
            sid = self.bitToSID(bitK, sequencesSize)
            if sid != lastSidSeen:
                if lastSidSeen != -1:
                    builder.append(" ")
                builder.append(str(sid))
                lastSidSeen = sid
            bitK = self.bitmap.next_set_bit(bitK + 1)
        return "".join(builder)


class Itemset:
    def __init__(self, item=None):
        self.items = []
        if item is not None:
            self.addItem(item)

    def addItem(self, value):
        self.items.append(value)

    def getItems(self):
        return self.items

    def get(self, index):
        return self.items[index]

    def toString(self):
        return "".join([str(item) + " " for item in self.items])

    def __str__(self):
        return self.toString()

    def size(self):
        return len(self.items)

    def cloneItemSetMinusItems(self, mapSequenceID, relativeMinsup):
        itemset = Itemset()
        for item in self.items:
            if len(mapSequenceID.get(item, [])) >= relativeMinsup:
                itemset.addItem(item)
        return itemset

    def cloneItemSet(self):
        itemset = Itemset()
        itemset.getItems().extend(self.items)
        return itemset

    def containsAll(self, itemset2):
        i = 0
        for item in itemset2.getItems():
            found = False
            while not found and i < self.size():
                if self.get(i) == item:
                    found = True
                elif self.get(i) > item:
                    return False
                i += 1
            if not found:
                return False
        return True


class Prefix:
    def __init__(self):
        self.itemsets = []

    def addItemset(self, itemset):
        self.itemsets.append(itemset)

    def cloneSequence(self):
        sequence = Prefix()
        for itemset in self.itemsets:
            sequence.addItemset(itemset.cloneItemSet())
        return sequence

    def print(self):
        print(self.toString(), end="")

    def toString(self):
        r = []
        for itemset in self.itemsets:
            for item in itemset.getItems():
                r.append(str(item))
                r.append(" ")
            r.append("-1 ")
        return "".join(r)

    def __str__(self):
        return self.toString()

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

    def getItemOccurencesTotalCount(self):
        count = 0
        for itemset in self.itemsets:
            count += itemset.size()
        return count

    def containsItem(self, item):
        for itemset in self.itemsets:
            if item in itemset.getItems():
                return True
        return False


class PrefixVGEN(Prefix):
    def __init__(self):
        super().__init__()
        self.sumOfEvenItems = 0
        self.sumOfOddItems = 0

    def cloneSequence(self):
        sequence = PrefixVGEN()
        for itemset in self.itemsets:
            sequence.addItemset(itemset.cloneItemSet())
        return sequence


class PatternVGEN:
    def __init__(self, prefix, bitmap):
        self.prefix = prefix
        self.bitmap = bitmap

    def getPrefix(self):
        return self.prefix

    def getBitmap(self):
        return self.bitmap

    def getAbsoluteSupport(self):
        return self.bitmap.getSupport()


class Candidate:
    def __init__(self, prefix, bitmap, sn, in_items, hasToBeGreaterThanForIStep, candidateLength):
        self.prefix = prefix
        self.bitmap = bitmap
        self.sn = sn
        self.in_items = in_items
        self.hasToBeGreaterThanForIStep = hasToBeGreaterThanForIStep
        self.candidateLength = candidateLength

    def compareTo(self, o):
        if o is self:
            return 0
        compare = o.bitmap.getSupport() - self.bitmap.getSupport()
        if compare != 0:
            return compare
        compare = id(self) - id(o)
        if compare != 0:
            return compare
        compare = self.prefix.size() - o.prefix.size()
        if compare != 0:
            return compare
        return self.hasToBeGreaterThanForIStep - o.hasToBeGreaterThanForIStep


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


class AlgoVGEN:
    def __init__(self):
        self.startTime = 0
        self.endTime = 0
        self.patternCount = 0
        self.minsup = 0
        self.writer = None
        self.verticalDB = {}
        self.sequencesSize = None
        self.lastBitIndex = 0
        self.maximumPatternLength = 1000
        self.coocMapAfter = None
        self.coocMapEquals = None
        self.useCMAPPruning = True
        self.generatorPatterns = None
        self.useImmediateBackwardChecking = True
        self.useBackwardPruning = False
        self.DEBUG_MODE = False
        self.transactionCount = 0
        self.maxGap = MAX_INT
        self.outputSequenceIdentifiers = False
        self.maxGapActivated = False

    def runAlgorithm(self, input_path, outputFilePath, minsupRel):
        if self.DEBUG_MODE:
            print(" %%%%%%%%%%  DEBUG MODE %%%%%%%%%%")

        Bitmap.INTERSECTION_COUNT = 0
        self.writer = open(outputFilePath, "w", encoding="utf-8")
        self.patternCount = 0
        MemoryLogger.getInstance().reset()

        self.startTime = int(time.time() * 1000)
        self.vgen(input_path, minsupRel)
        self.endTime = int(time.time() * 1000)

        self.writeResultTofile(outputFilePath)
        self.writer.close()

        if self.DEBUG_MODE:
            print("minsup absolute : " + str(self.minsup))
            listPatterns = []
            for mapSizeI in self.generatorPatterns:
                if mapSizeI is None:
                    continue
                mapSizeIOrder = _java_hashmap_iteration_order(list(mapSizeI.keys()), _java_hash_for_int)
                for sidsum in mapSizeIOrder:
                    listpattern = mapSizeI[sidsum]
                    for pat in listpattern:
                        listPatterns.append(pat)

            for pat1 in listPatterns:
                if pat1.prefix.size() > 0 and pat1.getAbsoluteSupport() == self.transactionCount:
                    print("NOT A GENERATOR !!!!!!!!!  " + str(pat1.prefix) + "    sup: "
                          + str(pat1.bitmap.getSupport()) + " because of empty set")

                for pat2 in listPatterns:
                    if pat1 is pat2:
                        continue
                    if pat1.getAbsoluteSupport() == pat2.getAbsoluteSupport():
                        if self.strictlyContains(pat1.prefix, pat2.prefix):
                            print("NOT A GENERATOR !!!!!!!!!  " + str(pat1.prefix) + " "
                                  + str(pat2.prefix) + "   sup: " + str(pat1.bitmap.getSupport()))
                            print(str(pat1.bitmap.sidsum) + " " + str(pat2.bitmap.sidsum))

        return self.generatorPatterns

    def vgen(self, input_path, minsupRel):
        self.generatorPatterns = [{}, {}]
        self.verticalDB = {}
        inMemoryDB = []

        self.sequencesSize = []
        self.lastBitIndex = 0
        try:
            bitIndex = 0
            with open(input_path, "r", encoding="utf-8") as reader:
                for line in reader:
                    line = line.strip()
                    if not line or line[0] in "#%@":
                        continue
                    self.sequencesSize.append(bitIndex)
                    tokens = line.split(" ")
                    transactionArray = [int(tok) for tok in tokens]
                    inMemoryDB.append(transactionArray)
                    for item in transactionArray:
                        if item == -1:
                            bitIndex += 1
            self.lastBitIndex = bitIndex - 1
        except Exception as e:
            print(e)

        self.minsup = int(math.ceil(minsupRel * len(self.sequencesSize)))
        if self.minsup == 0:
            self.minsup = 1

        self.transactionCount = 0

        try:
            with open(input_path, "r", encoding="utf-8") as reader:
                sid = 0
                tid = 0
                for line in reader:
                    line = line.strip()
                    if not line or line[0] in "#%@":
                        continue
                    for token in line.split(" "):
                        if token == "-1":
                            tid += 1
                        elif token == "-2":
                            sid += 1
                            tid = 0
                        else:
                            item = int(token)
                            bitmapItem = self.verticalDB.get(item)
                            if bitmapItem is None:
                                bitmapItem = Bitmap(self.lastBitIndex)
                                self.verticalDB[item] = bitmapItem
                            bitmapItem.registerBit(sid, tid, self.sequencesSize)
                    self.transactionCount += 1
        except Exception as e:
            print(e)

        frequentItems = []
        verticalDBOrder = _java_hashmap_iteration_order(list(self.verticalDB.keys()), _java_hash_for_int)
        for item in verticalDBOrder:
            bitmap = self.verticalDB.get(item)
            if bitmap is None:
                continue
            if bitmap.getSupport() < self.minsup:
                del self.verticalDB[item]
            else:
                frequentItems.append(item)

        frequentItems.sort(key=lambda x: self.verticalDB[x].getSupport())

        self.coocMapEquals = {}
        self.coocMapAfter = {}

        for transaction in inMemoryDB:
            itemsetCount = 0
            alreadyProcessed = set()
            equalProcessed = {}
            i = 0
            while i < len(transaction):
                itemI = transaction[i]
                equalSet = equalProcessed.get(itemI)
                if equalSet is None:
                    equalSet = set()
                    equalProcessed[itemI] = equalSet

                if itemI < 0:
                    itemsetCount += 1
                    i += 1
                    continue

                bitmapOfItem = self.verticalDB.get(itemI)
                if bitmapOfItem is None or bitmapOfItem.getSupport() < self.minsup:
                    i += 1
                    continue

                alreadyProcessedB = set()
                sameItemset = True
                skipI = False
                j = i + 1
                while j < len(transaction):
                    itemJ = transaction[j]

                    if itemJ < 0:
                        sameItemset = False
                        j += 1
                        continue

                    bitmapOfItemJ = self.verticalDB.get(itemJ)
                    if bitmapOfItemJ is None or bitmapOfItemJ.getSupport() < self.minsup:
                        j += 1
                        continue

                    if sameItemset:
                        if itemJ not in equalSet:
                            mapEq = self.coocMapEquals.get(itemI)
                            if mapEq is None:
                                mapEq = {}
                                self.coocMapEquals[itemI] = mapEq
                            mapEq[itemJ] = mapEq.get(itemJ, 0) + 1
                            equalSet.add(itemJ)
                    elif itemJ not in alreadyProcessedB:
                        if itemI in alreadyProcessed:
                            skipI = True
                            break
                        mapAfter = self.coocMapAfter.get(itemI)
                        if mapAfter is None:
                            mapAfter = {}
                            self.coocMapAfter[itemI] = mapAfter
                        mapAfter[itemJ] = mapAfter.get(itemJ, 0) + 1
                        alreadyProcessedB.add(itemJ)
                    j += 1

                if skipI:
                    i += 1
                    continue

                alreadyProcessed.add(itemI)
                i += 1

        if self.DEBUG_MODE:
            print("transaction count = " + str(self.transactionCount))

        prefixSingleItems = []
        verticalDBOrder = _java_hashmap_iteration_order(list(self.verticalDB.keys()), _java_hash_for_int)
        for item in verticalDBOrder:
            bitmap = self.verticalDB[item]
            prefix = PrefixVGEN()
            prefix.addItemset(Itemset(item))
            itemIsEven = item % 2 == 0
            if itemIsEven:
                prefix.sumOfEvenItems = item
                prefix.sumOfOddItems = 0
            else:
                prefix.sumOfEvenItems = 0
                prefix.sumOfOddItems = item
            pattern = PatternVGEN(prefix, bitmap)
            prefixSingleItems.append(pattern)

            if self.transactionCount != bitmap.getSupport():
                listPatterns = self.generatorPatterns[1].get(pattern.bitmap.sidsum)
                if listPatterns is None:
                    listPatterns = []
                    self.generatorPatterns[1][pattern.bitmap.sidsum] = listPatterns
                listPatterns.append(pattern)
                self.patternCount += 1

        for pattern in prefixSingleItems:
            item = pattern.prefix.get(0).get(0)
            if self.maximumPatternLength > 1:
                self.dfsPruning(pattern.prefix, pattern.bitmap, frequentItems, frequentItems, item, 2, item)

        bitmap = Bitmap(0)
        bitmap.setSupport(self.transactionCount)
        pat = PatternVGEN(PrefixVGEN(), bitmap)
        self.generatorPatterns[0][0] = [pat]
        self.patternCount += 1

    def dfsPruning(self, prefix, prefixBitmap, sn, in_items, hasToBeGreaterThanForIStep, m, lastAppendedItem):
        sTemp = []
        sTempBitmaps = []

        mapSupportItemsAfter = self.coocMapAfter.get(lastAppendedItem)

        for i in sn:
            if self.useCMAPPruning:
                if mapSupportItemsAfter is None:
                    continue
                support = mapSupportItemsAfter.get(i)
                if support is None or support < self.minsup:
                    continue

            Bitmap.INTERSECTION_COUNT += 1
            newBitmap = prefixBitmap.createNewBitmapSStep(self.verticalDB.get(i), self.sequencesSize, self.lastBitIndex, self.maxGap)
            if newBitmap.getSupportWithoutGapTotal() >= self.minsup:
                sTemp.append(i)
                sTempBitmaps.append(newBitmap)

        for k in range(len(sTemp)):
            item = sTemp[k]
            prefixSStep = prefix.cloneSequence()
            prefixSStep.addItemset(Itemset(item))
            if item % 2 == 0:
                prefixSStep.sumOfEvenItems = item + prefix.sumOfEvenItems
                prefixSStep.sumOfOddItems = prefix.sumOfOddItems
            else:
                prefixSStep.sumOfEvenItems = prefix.sumOfEvenItems
                prefixSStep.sumOfOddItems = item + prefix.sumOfOddItems

            newBitmap = sTempBitmaps[k]

            if newBitmap.getSupport() >= self.minsup:
                hasNoImmediateBackwardExtension = (self.useImmediateBackwardChecking
                                                   or prefixBitmap.getSupport() != newBitmap.getSupport())

                if self.maximumPatternLength > m and hasNoImmediateBackwardExtension:
                    hasBackWardExtension = self.savePatternMultipleItems(prefixSStep, newBitmap, m)
                    if not hasBackWardExtension:
                        self.dfsPruning(prefixSStep, newBitmap, sTemp, sTemp, item, m + 1, item)

        mapSupportItemsEquals = self.coocMapEquals.get(lastAppendedItem)

        iTemp = []
        iTempBitmaps = []

        for i in in_items:
            if i > hasToBeGreaterThanForIStep:
                if self.useCMAPPruning:
                    if mapSupportItemsEquals is None:
                        continue
                    support = mapSupportItemsEquals.get(i)
                    if support is None or support < self.minsup:
                        continue

                Bitmap.INTERSECTION_COUNT += 1
                newBitmap = prefixBitmap.createNewBitmapIStep(self.verticalDB.get(i), self.sequencesSize, self.lastBitIndex)
                if newBitmap.getSupport() >= self.minsup:
                    iTemp.append(i)
                    iTempBitmaps.append(newBitmap)

        for k in range(len(iTemp)):
            item = iTemp[k]
            prefixIStep = prefix.cloneSequence()
            prefixIStep.getItemsets()[prefixIStep.size() - 1].addItem(item)
            if item % 2 == 0:
                prefixIStep.sumOfEvenItems = item + prefix.sumOfEvenItems
                prefixIStep.sumOfOddItems = prefix.sumOfOddItems
            else:
                prefixIStep.sumOfEvenItems = prefix.sumOfEvenItems
                prefixIStep.sumOfOddItems = item + prefix.sumOfOddItems

            newBitmap = iTempBitmaps[k]

            hasNoImmediateBackwardExtension = (self.useImmediateBackwardChecking
                                               or prefixBitmap.getSupport() == newBitmap.getSupport())

            if self.maximumPatternLength > m and hasNoImmediateBackwardExtension:
                hasBackWardExtension = self.savePatternMultipleItems(prefixIStep, newBitmap, m)
                if not hasBackWardExtension:
                    self.dfsPruning(prefixIStep, newBitmap, sTemp, iTemp, item, m + 1, item)

        MemoryLogger.getInstance().checkMemory()

    def savePatternMultipleItems(self, prefix, bitmap, length):
        sidsum = bitmap.sidsum

        if bitmap.getSupport() == self.transactionCount:
            return False

        mayBeAGenerator = True
        for i in range(1, min(length, len(self.generatorPatterns))):
            level = self.generatorPatterns[i].get(sidsum)
            if level is None:
                continue
            for pPrime in level:
                if (prefix.sumOfEvenItems >= pPrime.prefix.sumOfEvenItems
                        and prefix.sumOfOddItems >= pPrime.prefix.sumOfOddItems
                        and bitmap.getSupport() == pPrime.getAbsoluteSupport()
                        and self.strictlyContains(prefix, pPrime.prefix)):
                    if self.useBackwardPruning:
                        if self.isThereBackwardExtension(bitmap, pPrime.bitmap):
                            return True
                        mayBeAGenerator = False
                    else:
                        return False

        if not mayBeAGenerator:
            return False

        for i in range(len(self.generatorPatterns) - 1, length, -1):
            level = self.generatorPatterns[i].get(sidsum)
            if level is None:
                continue
            idx = 0
            while idx < len(level):
                pPrime = level[idx]
                if (prefix.sumOfEvenItems <= pPrime.prefix.sumOfEvenItems
                        and prefix.sumOfOddItems <= pPrime.prefix.sumOfOddItems
                        and bitmap.getSupport() == pPrime.getAbsoluteSupport()
                        and self.strictlyContains(pPrime.prefix, prefix)):
                    self.patternCount -= 1
                    del level[idx]
                    continue
                idx += 1

        while len(self.generatorPatterns) - 1 < length:
            self.generatorPatterns.append({})

        listPatterns = self.generatorPatterns[length].get(sidsum)
        if listPatterns is None:
            listPatterns = []
            self.generatorPatterns[length][sidsum] = listPatterns

        self.patternCount += 1
        listPatterns.append(PatternVGEN(prefix, bitmap))

        return False

    def isThereBackwardExtension(self, bitmap1, bitmap2):
        currentBit1 = bitmap1.bitmap.next_set_bit(0)
        currentBit2 = bitmap2.bitmap.next_set_bit(0)

        while True:
            if currentBit1 > currentBit2:
                return False

            currentBit1 = bitmap1.bitmap.next_set_bit(currentBit1 + 1)
            currentBit2 = bitmap2.bitmap.next_set_bit(currentBit2 + 1)

            if not (currentBit1 > 0):
                break

        return True

    def strictlyContains(self, pattern1, pattern2):
        if self.maxGapActivated and self.maxGap < 100:
            return self.strictlyContainsWithMaxgap(pattern1, pattern2)
        return self.strictlyContainsWithoutMaxgap(pattern1, pattern2)

    def strictlyContainsWithoutMaxgap(self, pattern1, pattern2):
        i = 0
        j = 0
        while True:
            if pattern1.get(j).containsAll(pattern2.get(i)):
                i += 1
                if i == pattern2.size():
                    return True

            j += 1
            if j >= pattern1.size():
                return False
            if (pattern1.size() - j) < pattern2.size() - i:
                return False

    def strictlyContainsWithMaxgap(self, pattern1, pattern2):
        for pos1 in range(pattern1.size()):
            result = self.strictlyContainsWithMaxGapHelper(pattern1, pattern2, pos1, 0, -1)
            if result:
                return True
        return False

    def strictlyContainsWithMaxGapHelper(self, pattern1, pattern2, pos1, pos2, lastMatchingPositionOfPattern1):
        maxPos1 = pattern1.size() - 1
        if lastMatchingPositionOfPattern1 >= 0:
            if maxPos1 > (lastMatchingPositionOfPattern1 + self.maxGap):
                maxPos1 = (lastMatchingPositionOfPattern1 + self.maxGap)

        for i in range(pos1, maxPos1 + 1):
            if pattern1.get(i).containsAll(pattern2.get(pos2)):
                nextPos2 = pos2 + 1
                if nextPos2 == pattern2.size():
                    return True
                if (pattern1.size() - i) < pattern2.size() - nextPos2:
                    return False
                result = self.strictlyContainsWithMaxGapHelper(pattern1, pattern2, i + 1, nextPos2, i)
                if result:
                    return True
        return False

    def printStatistics(self):
        r = []
        r.append("=============  VGEN v0.97- STATISTICS =============")
        r.append(" Total time ~ " + str(self.endTime - self.startTime) + " ms")
        r.append(" Frequent sequences count : " + str(self.patternCount))
        r.append(" Max memory (mb) : " + str(MemoryLogger.getInstance().getMaxMemory()) + str(self.patternCount))
        r.append("minsup " + str(self.minsup))
        r.append("Intersection count " + str(Bitmap.INTERSECTION_COUNT) + " ")
        r.append("===================================================")
        print("\n".join(r))

    def getMaximumPatternLength(self):
        return self.maximumPatternLength

    def setMaximumPatternLength(self, maximumPatternLength):
        self.maximumPatternLength = maximumPatternLength

    def writeResultTofile(self, path):
        for level in self.generatorPatterns:
            levelOrder = _java_hashmap_iteration_order(list(level.keys()), _java_hash_for_int)
            for sidsum in levelOrder:
                patterns = level[sidsum]
                for pattern in patterns:
                    r = []
                    for itemset in pattern.prefix.getItemsets():
                        for item in itemset.getItems():
                            r.append(str(item))
                            r.append(" ")
                        r.append("-1 ")

                    r.append("#SUP: ")
                    r.append(str(pattern.getAbsoluteSupport()))
                    if self.outputSequenceIdentifiers:
                        r.append(" #SID: ")
                        r.append(pattern.bitmap.getSIDs(self.sequencesSize))

                    self.writer.write("".join(r))
                    self.writer.write("\n")

    def setMaxGap(self, maxGap):
        self.maxGap = maxGap
        self.maxGapActivated = True

    def showSequenceIdentifiersInOutput(self, showSequenceIdentifiers):
        self.outputSequenceIdentifiers = showSequenceIdentifiers


def main_save_to_file():
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(script_dir, "contextPrefixSpan.txt")
    output_path = os.path.join(script_dir, "output_py.txt")

    algo = AlgoVGEN()
    algo.runAlgorithm(input_path, output_path, 0.5)
    algo.printStatistics()


def main_save_to_memory():
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(script_dir, "contextPrefixSpan.txt")
    output_path = os.path.join(script_dir, "output_py.txt")

    algo = AlgoVGEN()

    generatorPatterns = algo.runAlgorithm(input_path, output_path, 0.5)
    algo.printStatistics()

    for map_level in generatorPatterns:
        if map_level is None:
            continue
        for patterns in map_level.values():
            for pattern in patterns:
                print(" " + str(pattern.getPrefix()) + "  support : " + str(pattern.bitmap.getSupport()))


if __name__ == "__main__":
    main_save_to_file()
