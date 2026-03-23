import time
import math
import tracemalloc
from abc import ABC, abstractmethod

tracemalloc.start()


# ===============================================================
# MEMORY LOGGER  (Java equivalent)
# ===============================================================
class MemoryLogger:
    _instance = None

    def __init__(self):
        self.maxMemory = 0.0

    @staticmethod
    def getInstance():
        if MemoryLogger._instance is None:
            MemoryLogger._instance = MemoryLogger()
        return MemoryLogger._instance

    def getMaxMemory(self):
        return self.maxMemory

    def reset(self):
        self.maxMemory = 0.0

    def checkMemory(self):
        current, peak = tracemalloc.get_traced_memory()
        current_mb = current / 1024.0 / 1024.0
        if current_mb > self.maxMemory:
            self.maxMemory = current_mb
        return current_mb


# ===============================================================
# ARRAYS ALGOS
# ===============================================================
class ArraysAlgos:

    @staticmethod
    def sameAs(itemset1, itemsets2, posRemoved):
        j = 0
        for i in range(len(itemset1)):
            if j == posRemoved:
                j += 1
            if itemset1[i] == itemsets2[j]:
                j += 1
            elif itemset1[i] > itemsets2[j]:
                return 1
            else:
                return -1
        return 0


# ===============================================================
# ABSTRACT ITEMSET CLASSES
# ===============================================================
class AbstractItemset(ABC):
    @abstractmethod
    def size(self): pass

    @abstractmethod
    def __str__(self): pass

    def print(self):
        print(str(self), end="")

    @abstractmethod
    def getAbsoluteSupport(self): pass

    @abstractmethod
    def getRelativeSupport(self, nbObject): pass

    def getRelativeSupportAsString(self, nbObject):
        freq = self.getRelativeSupport(nbObject)
        s = f"{freq:.5f}".rstrip("0").rstrip(".")
        return s if s != "" else "0"

    @abstractmethod
    def contains(self, item): pass


class AbstractOrderedItemset(AbstractItemset):

    @abstractmethod
    def get(self, position): pass

    def getLastItem(self):
        return self.get(self.size() - 1)

    def __str__(self):
        if self.size() == 0:
            return "EMPTYSET"
        return " ".join(str(self.get(i)) for i in range(self.size()))

    def getRelativeSupport(self, nbObject):
        return float(self.getAbsoluteSupport()) / float(nbObject)

    def contains(self, item):
        for i in range(self.size()):
            v = self.get(i)
            if v == item:
                return True
            elif v > item:
                return False
        return False


# ===============================================================
# ITEMSET CLASS
# ===============================================================
class Itemset(AbstractOrderedItemset):
    def __init__(self, items=None, support=0):
        self.itemset = list(items) if items is not None else []
        self.support = support

    def getItems(self):
        return self.itemset

    def getAbsoluteSupport(self):
        return self.support

    def size(self):
        return len(self.itemset)

    def get(self, position):
        return self.itemset[position]

    def setAbsoluteSupport(self, support):
        self.support = support

    def increaseTransactionCount(self):
        self.support += 1

    def __hash__(self):
        return hash(tuple(self.itemset))


# ===============================================================
# ITEMSETS CONTAINER
# ===============================================================
class Itemsets:
    def __init__(self, name):
        self.levels = [[]]
        self.name = name
        self.itemsetsCount = 0

    def addItemset(self, itemset, k):
        while len(self.levels) <= k:
            self.levels.append([])
        self.levels[k].append(itemset)
        self.itemsetsCount += 1

    def printItemsets(self, nbObject):
        print(" ------- " + self.name + " -------")
        patternCount = 0
        for idx, level in enumerate(self.levels):
            print(f"  L{idx} ")
            for itemset in level:
                print(f"  pattern {patternCount}:  {itemset} support : {itemset.getAbsoluteSupport()}")
                patternCount += 1
        print(" --------------------------------")


# ===============================================================
# APRIORI ALGORITHM
# ===============================================================
class AlgoApriori:
    def __init__(self):
        self.k = 0
        self.totalCandidateCount = 0
        self.startTimestamp = 0
        self.endTimestamp = 0
        self.itemsetCount = 0
        self.databaseSize = 0
        self.minsupRelative = 0
        self.database = []
        self.patterns = None
        self.writer = None
        self.maxPatternLength = 10000

    # -----------------------------------------------------------
    # MAIN APRIORI METHOD
    # -----------------------------------------------------------
    def runAlgorithm(self, minsup, input_path, output_path):
        if output_path is None:
            self.writer = None
            self.patterns = Itemsets("FREQUENT ITEMSETS")
        else:
            self.patterns = None
            self.writer = open(output_path, "w", encoding="utf-8")

        self.startTimestamp = int(time.time() * 1000)
        MemoryLogger.getInstance().reset()

        mapItemCount = {}
        self.database = []
        self.databaseSize = 0

        with open(input_path, "r", encoding="utf-8") as reader:
            for line in reader:
                line = line.strip()
                if not line or line[0] in ["#", "%", "@"]:
                    continue
                items = list(map(int, line.split()))
                for item in items:
                    mapItemCount[item] = mapItemCount.get(item, 0) + 1
                self.database.append(items)
                self.databaseSize += 1

        self.minsupRelative = int(math.ceil(minsup * self.databaseSize))

        # Frequent 1-itemsets
        frequent1 = []
        for item, support in mapItemCount.items():
            if support >= self.minsupRelative:
                frequent1.append(item)
                self.saveItemsetToFile(item, support)

        frequent1.sort()
        self.k = 2

        if not frequent1:
            return

        level = None

        while True:
            if self.k == 2:
                candidates = self.generateCandidate2(frequent1)
            else:
                candidates = self.generateCandidateSizeK(level)

            for candidate in candidates:
                candidate.support = 0

            for transaction in self.database:
                if len(transaction) < self.k:
                    continue
                for candidate in candidates:
                    pos = 0
                    for item in transaction:
                        if item == candidate.itemset[pos]:
                            pos += 1
                            if pos == len(candidate.itemset):
                                candidate.support += 1
                                break
                        elif item > candidate.itemset[pos]:
                            break

            level = []
            for candidate in candidates:
                if candidate.support >= self.minsupRelative:
                    level.append(candidate)
                    self.saveItemset(candidate)

            if not level:
                break

            self.k += 1

        self.endTimestamp = int(time.time() * 1000)
        if self.writer:
            self.writer.close()

        return self.patterns

    # -----------------------------------------------------------
    # Candidate generation
    # -----------------------------------------------------------
    def generateCandidate2(self, frequent1):
        return [Itemset([frequent1[i], frequent1[j]]) for i in range(len(frequent1)) for j in range(i+1, len(frequent1))]

    def generateCandidateSizeK(self, levelK_1):
        candidates = []
        for i in range(len(levelK_1)):
            for j in range(i+1, len(levelK_1)):
                A = levelK_1[i].itemset
                B = levelK_1[j].itemset

                if A[:-1] == B[:-1] and A[-1] < B[-1]:
                    newItemset = A + [B[-1]]
                    candidates.append(Itemset(newItemset))
        return candidates

    # -----------------------------------------------------------
    # Save patterns
    # -----------------------------------------------------------
    def saveItemset(self, itemset):
        self.itemsetCount += 1
        if self.writer:
            self.writer.write(f"{itemset} #SUP: {itemset.support}\n")
        else:
            self.patterns.addItemset(itemset, itemset.size())

    def saveItemsetToFile(self, item, support):
        self.itemsetCount += 1
        if self.writer:
            self.writer.write(f"{item} #SUP: {support}\n")
        else:
            obj = Itemset([item], support)
            self.patterns.addItemset(obj, 1)

    # -----------------------------------------------------------
    # Print statistics
    # -----------------------------------------------------------
    def printStats(self):
        print("=============  APRIORI - STATS =============")
        print(" Candidates count :", self.totalCandidateCount)
        print(" Frequent itemsets count :", self.itemsetCount)
        print(" Maximum memory usage :", MemoryLogger.getInstance().getMaxMemory(), "mb")
        print(" Total time ~", self.endTimestamp - self.startTimestamp, "ms")
        print("============================================")


# ===============================================================
# MAIN EXECUTION
# ===============================================================
if __name__ == "__main__":
    input_path = "contextPasquier99.txt"
    output_path = "apriori_outputs.txt"

    minsup = 0.4

    algo = AlgoApriori()
    results = algo.runAlgorithm(minsup, input_path, output_path)
    algo.printStats()

    if results is not None:
        results.printItemsets(algo.getDatabaseSize())