import bisect
import os
import random
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


IDENTITY_HASH_SEED = int(os.environ.get("TKS_HASH_SEED", "6"))
_identity_rng = random.Random(IDENTITY_HASH_SEED)


def _reset_identity_hash():
    global _identity_rng
    _identity_rng = random.Random(IDENTITY_HASH_SEED)


def _next_identity_hash():
    return _identity_rng.getrandbits(31)


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


class PatternTKS:
    def __init__(self, prefix, support):
        self.prefix = prefix
        self.support = support
        self.bitmap = None
        self._hash = _next_identity_hash()


class Candidate:
    def __init__(self, prefix, bitmap, sn, in_items, hasToBeGreaterThanForIStep, candidateLength):
        self.prefix = prefix
        self.bitmap = bitmap
        self.sn = sn
        self.in_items = in_items
        self.hasToBeGreaterThanForIStep = hasToBeGreaterThanForIStep
        self.candidateLength = candidateLength
        self._hash = _next_identity_hash()


class JavaPriorityQueue:
    def __init__(self, compare_func):
        self.queue = []
        self._compare = compare_func

    def size(self):
        return len(self.queue)

    def isEmpty(self):
        return len(self.queue) == 0

    def peek(self):
        return self.queue[0] if self.queue else None

    def add(self, element):
        self.queue.append(element)
        self._sift_up(len(self.queue) - 1)

    def poll(self):
        if not self.queue:
            return None
        last = self.queue.pop()
        if not self.queue:
            return last
        result = self.queue[0]
        self.queue[0] = last
        self._sift_down(0)
        return result

    def __iter__(self):
        return iter(self.queue)

    def _sift_up(self, idx):
        e = self.queue[idx]
        while idx > 0:
            parent = (idx - 1) // 2
            if self._compare(e, self.queue[parent]) >= 0:
                break
            self.queue[idx] = self.queue[parent]
            idx = parent
        self.queue[idx] = e

    def _sift_down(self, idx):
        size = len(self.queue)
        e = self.queue[idx]
        half = size // 2
        while idx < half:
            left = idx * 2 + 1
            right = left + 1
            smallest = left
            if right < size and self._compare(self.queue[right], self.queue[left]) < 0:
                smallest = right
            if self._compare(self.queue[smallest], e) >= 0:
                break
            self.queue[idx] = self.queue[smallest]
            idx = smallest
        self.queue[idx] = e


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


class AlgoTKS:
    def __init__(self):
        self.startTime = 0
        self.startMiningTime = 0
        self.endTime = 0
        self.minsup = 0
        self.minsupAfterPreProcessing = 0
        self.k = 0
        self.verticalDB = {}
        self.sequencesSize = None
        self.lastBitIndex = 0
        self.kPatterns = JavaPriorityQueue(self._compare_pattern)
        self.candidates = JavaPriorityQueue(self._compare_candidate)
        self.maxCandidateCount = 0
        self.candidateExplored = 0
        self.discardedItems = set()
        self.useDiscardedItemsPruningStrategy = True
        self.usePruneBranchesInsideDFSPruning = True
        self.rebuildCandidateTreeWhenTooLarge = False
        self.addedCandidatesSinceLastRebuilt = 0
        self.MIN_CANDIDATES_COUNT_BEFORE_REBUILD = 1500
        self.MIN_ADDED_CANDIDATE_COUNT_SINCE_LAST_REBUILD_BEFORE_REBUILD = 400
        self.useCooccurrenceInformation = True
        self.coocMapAfter = None
        self.coocMapEquals = None
        self.minimumPatternLength = 0
        self.maximumPatternLength = 1000
        self.mustAppearItems = None
        self.maxGap = MAX_INT
        self.outputSequenceIdentifiers = False

    def runAlgorithm(self, input_path, outputFilePath, k):
        MemoryLogger.getInstance().reset()
        _reset_identity_hash()
        self.tks(input_path, k)
        self.endTime = int(time.time() * 1000)
        return self.kPatterns

    def _compare_pattern(self, a, b):
        if a is b:
            return 0
        compare = a.support - b.support
        if compare != 0:
            return compare
        return a._hash - b._hash

    def _compare_candidate(self, a, b):
        if a is b:
            return 0
        compare = b.bitmap.getSupport() - a.bitmap.getSupport()
        if compare != 0:
            return compare
        compare = a._hash - b._hash
        if compare != 0:
            return compare
        compare = a.prefix.size() - b.prefix.size()
        if compare != 0:
            return compare
        return a.hasToBeGreaterThanForIStep - b.hasToBeGreaterThanForIStep

    def tks(self, input_path, k):
        self.k = k
        self.minsup = 1
        self.candidateExplored = 0
        self.kPatterns = JavaPriorityQueue(self._compare_pattern)
        self.candidates = JavaPriorityQueue(self._compare_candidate)
        self.discardedItems = set()
        self.verticalDB = {}
        inMemoryDB = []

        self.sequencesSize = []
        self.lastBitIndex = 0
        try:
            bitIndex = 0
            with open(input_path, "r", encoding="utf-8") as reader:
                for line in reader:
                    line = line.strip()
                    if not line or line.startswith("#") or line[0] in "%@":
                        continue

                    tokens = line.split(" ")
                    transactionArray = [0] * len(tokens)
                    containsAMustAppearItem = False

                    self.sequencesSize.append(bitIndex)
                    for i, tok in enumerate(tokens):
                        item = int(tok)
                        transactionArray[i] = item
                        if item == -1:
                            bitIndex += 1
                        if self.itemMustAppearInPatterns(item):
                            containsAMustAppearItem = True

                    if containsAMustAppearItem:
                        inMemoryDB.append(transactionArray)

            self.lastBitIndex = bitIndex - 1
        except Exception as e:
            print(e)

        self.startTime = int(time.time() * 1000)

        sid = 0
        tid = 0
        for transaction in inMemoryDB:
            for item in transaction:
                if item == -1:
                    tid += 1
                elif item == -2:
                    sid += 1
                    tid = 0
                else:
                    bitmapItem = self.verticalDB.get(item)
                    if bitmapItem is None:
                        bitmapItem = Bitmap(self.lastBitIndex)
                        self.verticalDB[item] = bitmapItem
                    bitmapItem.registerBit(sid, tid, self.sequencesSize)

        frequentItems = []
        verticalDBOrder = _java_hashmap_iteration_order(list(self.verticalDB.keys()), _java_hash_for_int)
        for item in verticalDBOrder:
            bitmap = self.verticalDB.get(item)
            if bitmap is None:
                continue
            support = bitmap.getSupport()
            if support < self.minsup:
                del self.verticalDB[item]
            else:
                frequentItems.append(item)
                prefix = Prefix()
                prefix.addItemset(Itemset(item))
                pattern = PatternTKS(prefix, support)
                if self.outputSequenceIdentifiers:
                    pattern.bitmap = bitmap

                if 1 >= self.minimumPatternLength and 1 <= self.maximumPatternLength:
                    self.save(pattern)

        if self.maximumPatternLength > 1:
            if self.useCooccurrenceInformation:
                self.coocMapEquals = {}
                self.coocMapAfter = {}

                for transaction in inMemoryDB:
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

            if self.useCooccurrenceInformation:
                verticalDBOrder = _java_hashmap_iteration_order(list(self.verticalDB.keys()), _java_hash_for_int)
                for item in verticalDBOrder:
                    bitmap = self.verticalDB.get(item)
                    if bitmap is None:
                        continue
                    if bitmap.getSupport() >= self.minsup:
                        self.candidateExplored += 1
                        prefix = Prefix()
                        prefix.addItemset(Itemset(item))
                        if self.coocMapAfter.get(item) is not None:
                            afterItems = _java_hashmap_iteration_order(
                                list(self.coocMapAfter[item].keys()),
                                _java_hash_for_int
                            )
                            self.registerAsCandidate(Candidate(prefix, bitmap, afterItems, afterItems, item, 1))
            else:
                for item in list(frequentItems):
                    if self.verticalDB[item].getSupport() < self.minsup:
                        frequentItems.remove(item)
                        del self.verticalDB[item]
                    else:
                        self.candidateExplored += 1
                        prefix = Prefix()
                        prefix.addItemset(Itemset(item))
                        self.registerAsCandidate(
                            Candidate(prefix, self.verticalDB[item], frequentItems, frequentItems, item, 1)
                        )

            self.minsupAfterPreProcessing = self.minsup
            self.startMiningTime = int(time.time() * 1000)

            while not self.candidates.isEmpty():
                cand = self.candidates.poll()
                if cand.bitmap.getSupport() < self.minsup:
                    break

                self.candidateExplored += 1
                self.dfsPruning(cand.prefix, cand.bitmap, cand.sn, cand.in_items, cand.hasToBeGreaterThanForIStep,
                                cand.candidateLength)

                if (self.rebuildCandidateTreeWhenTooLarge
                        and self.candidates.size() > self.MIN_CANDIDATES_COUNT_BEFORE_REBUILD
                        and self.addedCandidatesSinceLastRebuilt
                        > self.MIN_ADDED_CANDIDATE_COUNT_SINCE_LAST_REBUILD_BEFORE_REBUILD):
                    temp = []
                    for candidate in self.candidates:
                        if candidate.bitmap.getSupport() >= self.minsup:
                            temp.append(candidate)
                    newQueue = JavaPriorityQueue(self._compare_candidate)
                    for candidate in temp:
                        newQueue.add(candidate)
                    self.candidates = newQueue

        MemoryLogger.getInstance().checkMemory()
        return self.kPatterns

    def save(self, pattern):
        if self.mustAppearItems is not None:
            itemsFound = set()
            for itemset in pattern.prefix.getItemsets():
                for item in itemset.getItems():
                    if self.itemMustAppearInPatterns(item):
                        itemsFound.add(item)
                        if len(itemsFound) == len(self.mustAppearItems):
                            break
                if len(itemsFound) == len(self.mustAppearItems):
                    break
            if len(itemsFound) != len(self.mustAppearItems):
                return

        self.kPatterns.add(pattern)

        if self.kPatterns.size() > self.k:
            if pattern.support > self.minsup:
                while self.kPatterns.size() > self.k:
                    pat = self.kPatterns.poll()
                    if (self.useDiscardedItemsPruningStrategy
                            and pat.prefix.size() == 1
                            and pat.prefix.get(0).size() == 1):
                        self.discardedItems.add(pat.prefix.get(0).get(0))
            if not self.kPatterns.isEmpty():
                self.minsup = self.kPatterns.peek().support

    def registerAsCandidate(self, candidate):
        self.candidates.add(candidate)
        self.addedCandidatesSinceLastRebuilt += 1
        if self.candidates.size() >= self.maxCandidateCount:
            self.maxCandidateCount = self.candidates.size()

    def dfsPruning(self, prefix, prefixBitmap, sn, in_items, hasToBeGreaterThanForIStep, prefixLength):
        newCandidatesLength = prefixLength + 1

        sTemp = []
        sTempBitmaps = []

        for i in sn:
            if self.useDiscardedItemsPruningStrategy and i in self.discardedItems:
                continue

            if self.useCooccurrenceInformation:
                blocked = False
                for itemset in prefix.getItemsets():
                    for itemX in itemset.getItems():
                        mapSupportItemsAfter = self.coocMapAfter.get(itemX)
                        if mapSupportItemsAfter is None:
                            blocked = True
                            break
                        support = mapSupportItemsAfter.get(i)
                        if support is None or support < self.minsup:
                            blocked = True
                            break
                    if blocked:
                        break
                if blocked:
                    continue

            newBitmap = prefixBitmap.createNewBitmapSStep(self.verticalDB.get(i), self.sequencesSize,
                                                         self.lastBitIndex, self.maxGap)
            if newBitmap.getSupportWithoutGapTotal() >= self.minsup:
                sTemp.append(i)
                sTempBitmaps.append(newBitmap)

        for k in range(len(sTemp)):
            newBitmap = sTempBitmaps[k]
            if self.usePruneBranchesInsideDFSPruning and newBitmap.getSupport() < self.minsup:
                continue

            item = sTemp[k]
            prefixSStep = prefix.cloneSequence()
            prefixSStep.addItemset(Itemset(item))

            if newBitmap.getSupport() >= self.minsup:
                if newCandidatesLength >= self.minimumPatternLength and newCandidatesLength <= self.maximumPatternLength:
                    pattern = PatternTKS(prefixSStep, newBitmap.getSupport())
                    if self.outputSequenceIdentifiers:
                        pattern.bitmap = newBitmap
                    self.save(pattern)

                if newCandidatesLength + 1 <= self.maximumPatternLength:
                    self.registerAsCandidate(Candidate(prefixSStep, newBitmap, sTemp, sTemp, item, newCandidatesLength))

        iTemp = []
        iTempBitmaps = []

        for i in in_items:
            if i <= hasToBeGreaterThanForIStep:
                continue

            if self.useDiscardedItemsPruningStrategy and i in self.discardedItems:
                continue

            if self.useCooccurrenceInformation:
                blocked = False
                for itemset in prefix.getItemsets():
                    for itemX in itemset.getItems():
                        mapSupportItemsAfter = self.coocMapEquals.get(itemX)
                        if mapSupportItemsAfter is None:
                            blocked = True
                            break
                        support = mapSupportItemsAfter.get(i)
                        if support is None or support < self.minsup:
                            blocked = True
                            break
                    if blocked:
                        break
                if blocked:
                    continue

            newBitmap = prefixBitmap.createNewBitmapIStep(self.verticalDB.get(i), self.sequencesSize, self.lastBitIndex)
            if newBitmap.getSupport() >= self.minsup:
                iTemp.append(i)
                iTempBitmaps.append(newBitmap)

        for k in range(len(iTemp)):
            newBitmap = iTempBitmaps[k]
            if self.usePruneBranchesInsideDFSPruning and newBitmap.getSupport() < self.minsup:
                continue

            item = iTemp[k]
            prefixIStep = prefix.cloneSequence()
            prefixIStep.getItemsets()[prefixIStep.size() - 1].addItem(item)

            if newCandidatesLength >= self.minimumPatternLength and newCandidatesLength <= self.maximumPatternLength:
                self.save(PatternTKS(prefixIStep, newBitmap.getSupport()))

            if newCandidatesLength + 1 <= self.maximumPatternLength:
                self.registerAsCandidate(Candidate(prefixIStep, newBitmap, sTemp, iTemp, item, newCandidatesLength))

        MemoryLogger.getInstance().checkMemory()

    def printStatistics(self):
        r = []
        r.append("=============  Algorithm TKS v0.97 - STATISTICS =============")
        r.append("Minsup after preprocessing : " + str(self.minsupAfterPreProcessing))
        r.append("Max candidates: " + str(self.maxCandidateCount) + " Candidates explored  : " + str(self.candidateExplored))
        r.append("Pattern found count : " + str(self.kPatterns.size()))
        r.append("Time preprocessing: " + str(self.startMiningTime - self.startTime) + " ms ")
        r.append("Total time: " + str(self.endTime - self.startTime) + " ms ")
        r.append("Max memory (mb) : " + str(MemoryLogger.getInstance().getMaxMemory()))
        r.append("Final minsup value: " + str(self.minsup))
        r.append("Intersection count " + str(Bitmap.INTERSECTION_COUNT) + " ")
        r.append("===================================================")
        print("\n".join(r))

    def writeResultTofile(self, path):
        with open(path, "w", encoding="utf-8") as writer:
            for pattern in self.kPatterns:
                buffer = []
                buffer.append(pattern.prefix.toString())
                buffer.append("#SUP: ")
                buffer.append(str(pattern.support))
                if self.outputSequenceIdentifiers:
                    buffer.append(" #SID: ")
                    buffer.append(pattern.bitmap.getSIDs(self.sequencesSize))
                writer.write("".join(buffer))
                writer.write("\n")

    def setMaximumPatternLength(self, maximumPatternLength):
        self.maximumPatternLength = maximumPatternLength

    def setMinimumPatternLength(self, minimumPatternLength):
        self.minimumPatternLength = minimumPatternLength

    def setMustAppearItems(self, mustAppearItems):
        if mustAppearItems is None:
            self.mustAppearItems = None
        else:
            self.mustAppearItems = list(mustAppearItems)

    def itemMustAppearInPatterns(self, item):
        if self.mustAppearItems is None:
            return True
        idx = bisect.bisect_left(self.mustAppearItems, item)
        return idx < len(self.mustAppearItems) and self.mustAppearItems[idx] == item

    def setMaxGap(self, maxGap):
        self.maxGap = maxGap

    def showSequenceIdentifiersInOutput(self, showSequenceIdentifiers):
        self.outputSequenceIdentifiers = showSequenceIdentifiers

def main_save_to_file():
    input_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contextPrefixSpan.txt")
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs.txt")

    k = 5
    algo = AlgoTKS()
    algo.runAlgorithm(input_path, output_path, k)
    algo.writeResultTofile(output_path)
    algo.printStatistics()


if __name__ == "__main__":
    main_save_to_file()
