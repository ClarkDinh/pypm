import math
import time
import sys
import os
from collections import defaultdict

# =========================
# MemoryLogger (Singleton)
# =========================
class MemoryLogger:
    _instance = None

    def __init__(self):
        self.maxMemory = 0.0

    @staticmethod
    def getInstance():
        if MemoryLogger._instance is None:
            MemoryLogger._instance = MemoryLogger()
        return MemoryLogger._instance

    def reset(self):
        self.maxMemory = 0.0

    def checkMemory(self):
        try:
            import psutil
            process = psutil.Process(os.getpid())
            currentMemory = process.memory_info().rss / 1024 / 1024
        except:
            currentMemory = 0.0
        if currentMemory > self.maxMemory:
            self.maxMemory = currentMemory
        return currentMemory

    def getMaxMemory(self):
        return self.maxMemory


# =========================
# BitSet equivalent
# =========================
class BitSet:
    def __init__(self):
        self.bits = set()

    def set(self, i):
        self.bits.add(i)

    def clone(self):
        b = BitSet()
        b.bits = set(self.bits)
        return b

    def andNot(self, other):
        self.bits -= other.bits

    def cardinality(self):
        return len(self.bits)


# =========================
# MyBitVector
# =========================
class MyBitVector:
    TWO_POWER = [(1 << i) for i in range(64)]

    def __init__(self, itemset, last):
        length = itemset[0]
        self.bits = [0] * ((length // 64) + 1)
        self.cardinality = last
        for i in range(last):
            item = itemset[i]
            self.bits[item // 64] |= MyBitVector.TWO_POWER[item % 64]

    def isSubSet(self, q):
        if self.cardinality >= q.cardinality:
            return False
        for i in range(len(self.bits)):
            if (self.bits[i] & (~q.bits[i])) != 0:
                return False
        return True


# =========================
# CPStorage
# =========================
class CPStorage:
    def __init__(self):
        self.mapSupportMyBitVector = {}

    def insertIfClose(self, itemsetBitVector, support):
        result = True
        lst = self.mapSupportMyBitVector.get(support)
        if lst is None:
            self.mapSupportMyBitVector[support] = [itemsetBitVector]
        else:
            index = 0
            for q in lst:
                if itemsetBitVector.cardinality >= q.cardinality:
                    break
                if itemsetBitVector.isSubSet(q):
                    result = False
                    break
                index += 1
            if result:
                lst.insert(index, itemsetBitVector)
        return result


# =========================
# AlgoNEclatClosed
# =========================
class AlgoNEclatClosed:

    class Item:
        def __init__(self):
            self.index = 0
            self.num = 0

    class SetEnumerationTreeNode:
        def __init__(self):
            self.label = 0
            self.firstChild = None
            self.next = None
            self.tidSET = None
            self.count = 0

    def __init__(self):
        self.startTimestamp = 0
        self.endTimestamp = 0
        self.outputCount = 0
        self.writer = None

        self.numOfFItem = 0
        self.minSupport = 0
        self.item = []

        self.itemsetX = []
        self.itemsetXLen = 0

        self.nlRoot = None
        self.mapItemTIDS = {}
        self.cpStorage = None
        self.numOfTrans = 0

    def runAlgorithm(self, input_dataset, minsup, output):
        self.nlRoot = self.SetEnumerationTreeNode()
        MemoryLogger.getInstance().reset()

        self.writer = open(output, "w")
        self.startTimestamp = int(time.time() * 1000)

        self.getData(input_dataset, minsup)
        self.itemsetX = [0] * self.numOfFItem
        self.itemsetXLen = 0

        self.buildTree(input_dataset)
        self.initializeTree()

        self.cpStorage = CPStorage()

        curNode = self.nlRoot.firstChild
        self.nlRoot.firstChild = None

        while curNode:
            self.traverse(curNode, 1)
            nxt = curNode.next
            curNode.next = None
            curNode = nxt

        self.writer.close()
        MemoryLogger.getInstance().checkMemory()
        self.endTimestamp = int(time.time() * 1000)

    def getData(self, filename, minSupport):
        self.numOfTrans = 0
        mapItemCount = defaultdict(int)

        with open(filename, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in "#%@":
                    continue
                self.numOfTrans += 1
                for item in line.split():
                    mapItemCount[int(item)] += 1

        self.minSupport = math.ceil(minSupport * self.numOfTrans)

        tempItems = []
        for k, v in mapItemCount.items():
            if v >= self.minSupport:
                it = self.Item()
                it.index = k
                it.num = v
                tempItems.append(it)

        tempItems.sort(key=lambda x: x.num, reverse=True)
        self.item = tempItems
        self.numOfFItem = len(self.item)

    def buildTree(self, filename):
        self.mapItemTIDS = {}
        tid = 1

        with open(filename, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in "#%@":
                    continue
                for itemStr in line.split():
                    itemX = int(itemStr)
                    for j in range(self.numOfFItem):
                        if itemX == self.item[j].index:
                            if j not in self.mapItemTIDS:
                                self.mapItemTIDS[j] = BitSet()
                            self.mapItemTIDS[j].set(tid)
                            break
                tid += 1

    def initializeTree(self):
        lastChild = None
        for t in range(self.numOfFItem - 1, -1, -1):
            node = self.SetEnumerationTreeNode()
            node.label = t
            node.tidSET = self.mapItemTIDS.get(t)
            node.count = node.tidSET.cardinality()
            if self.nlRoot.firstChild is None:
                self.nlRoot.firstChild = node
                lastChild = node
            else:
                lastChild.next = node
                lastChild = node

    def traverse(self, curNode, level):
        MemoryLogger.getInstance().checkMemory()

        prev = curNode
        sibling = prev.next
        lastChild = None
        sameCount = 0

        self.itemsetX[self.itemsetXLen] = curNode.label
        self.itemsetXLen += 1

        while sibling:
            child = self.SetEnumerationTreeNode()
            if level == 1:
                if sibling.tidSET.cardinality() != 0:
                    child.tidSET = curNode.tidSET.clone()
                    child.tidSET.andNot(sibling.tidSET)
            else:
                if curNode.tidSET.cardinality() != 0:
                    child.tidSET = sibling.tidSET.clone()
                    child.tidSET.andNot(curNode.tidSET)

            child.count = curNode.count - child.tidSET.cardinality()
            if child.count >= self.minSupport:
                if curNode.count == child.count:
                    self.itemsetX[self.itemsetXLen] = sibling.label
                    self.itemsetXLen += 1
                    sameCount += 1
                else:
                    child.label = sibling.label
                    if curNode.firstChild is None:
                        curNode.firstChild = child
                        lastChild = child
                    else:
                        lastChild.next = child
                        lastChild = child
            sibling = sibling.next

        bitvector = MyBitVector(self.itemsetX, self.itemsetXLen)
        if self.cpStorage.insertIfClose(bitvector, curNode.count):
            self.writeItemsetsToFile(curNode.count)

        child = curNode.firstChild
        curNode.firstChild = None
        while child:
            self.traverse(child, level + 1)
            nxt = child.next
            child.next = None
            child = nxt

        self.itemsetXLen -= (1 + sameCount)

    def writeItemsetsToFile(self, support):
        self.outputCount += 1
        buffer = []
        for i in range(self.itemsetXLen):
            buffer.append(str(self.item[self.itemsetX[i]].index))
        buffer.append("#SUP: " + str(support))
        self.writer.write(" ".join(buffer) + "\n")


# =========================
# Main (equivalent to MainTestNECLATClosed)
# =========================
if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    input_file = os.path.join(BASE_DIR, "contextPasquier99.txt")
    output_file = os.path.join(BASE_DIR, "neclatclosed_outputs.txt")
    minsup = 0.7

    algo = AlgoNEclatClosed()
    algo.runAlgorithm(input_file, minsup, output_file)
