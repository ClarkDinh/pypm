from __future__ import annotations

import bisect
import gc
import os
import tracemalloc
import time
from dataclasses import dataclass
from pathlib import Path


class OrderedMultiset:
    def __init__(self, key=lambda value: value):
        self._key = key
        self._entries = []
        self._sequence = 0

    def add(self, value):
        entry = (self._key(value), self._sequence, value)
        bisect.insort_right(self._entries, entry)
        self._sequence += 1

    def remove(self, value):
        key = self._key(value)
        index = bisect.bisect_left(self._entries, (key, -1, None))
        while index < len(self._entries) and self._entries[index][0] == key:
            self._entries.pop(index)
            return

    def size(self):
        return len(self._entries)

    def isEmpty(self):
        return not self._entries

    def minimum(self):
        if not self._entries:
            return None
        return self._entries[0][2]

    def maximum(self):
        if not self._entries:
            return None
        return self._entries[-1][2]

    def popMinimum(self):
        if not self._entries:
            return None
        return self._entries.pop(0)[2]

    def popMaximum(self):
        if not self._entries:
            return None
        return self._entries.pop()[2]


class MemoryLogger:
    _instance = None

    def __init__(self):
        self.maxMemory = 0.0
        self.recordingMode = False
        self.outputFile = None
        self.writer = None
        tracemalloc.start()

    @classmethod
    def getInstance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def getMaxMemory(self):
        return self.maxMemory

    def reset(self):
        self.maxMemory = 0.0
        tracemalloc.stop()
        tracemalloc.start()

    def checkMemory(self):
        current, _ = tracemalloc.get_traced_memory()
        current_memory = current / 1024.0 / 1024.0
        if current_memory > self.maxMemory:
            self.maxMemory = current_memory
        if self.recordingMode and self.writer is not None:
            self.writer.write(f"{current_memory}\n")
        return current_memory

    def startRecordingMode(self, fileName):
        self.recordingMode = True
        self.outputFile = Path(fileName)
        self.writer = self.outputFile.open("w", encoding="utf-8")

    def stopRecordingMode(self):
        if self.recordingMode and self.writer is not None:
            self.writer.close()
            self.writer = None
            self.recordingMode = False


class CalculateDatabaseInfo:
    def __init__(self, inputPath):
        self.inputPath = str(inputPath)
        self.totalUtility = 0
        self.databaseSize = 0
        self.maxID = 0
        self.sumAllLength = 0
        self.avgLength = 0.0
        self.maxLength = 0
        self.allItem = set()

    def runCalculate(self):
        try:
            with open(self.inputPath, "r", encoding="utf-8") as reader:
                for raw_line in reader:
                    line = raw_line.strip()
                    if not line:
                        continue
                    self.databaseSize += 1
                    tokens1 = line.split(":")
                    tokens2 = tokens1[0].split(" ")
                    self.totalUtility += int(tokens1[1])
                    self.sumAllLength += len(tokens2)
                    if self.maxLength < len(tokens2):
                        self.maxLength = len(tokens2)
                    for token in tokens2:
                        num = int(token)
                        if num > self.maxID:
                            self.maxID = num
                        self.allItem.add(num)
            if self.databaseSize > 0:
                self.avgLength = int((self.sumAllLength / self.databaseSize) * 100) / 100.0
            return True
        except Exception as exc:
            print(str(exc))
            return False

    def getMaxID(self):
        return self.maxID

    def getMaxLength(self):
        return self.maxLength

    def getDBSize(self):
        return self.databaseSize


class TKUTriangularMatrix:
    def __init__(self, elementCount):
        self.elementCount = elementCount
        self.matrix = []
        for i in range(elementCount):
            self.matrix.append([0] * (elementCount - i))

    def get(self, i, j):
        return self.matrix[i][j]

    def incrementCount(self, id1, id2, total):
        if id2 < id1:
            self.matrix[id2][self.elementCount - id1 - 1] += total
        else:
            self.matrix[id1][self.elementCount - id2 - 1] += total

    def getSupportForItems(self, id1, id2):
        if id2 < id1:
            return self.matrix[id2][self.elementCount - id1 - 1]
        return self.matrix[id1][self.elementCount - id2 - 1]


@dataclass
class StringPair:
    x: str
    y: int


@dataclass
class HeapEntry:
    count: int = 0
    priority: int = 0


class AlgoPhase2OfTKU:
    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self.minUtility = 0
        self.theCurrentK = 0
        self.numberOfTransactions = 0
        self.inputFilePath = ""
        self.sortedCandidatePath = ""
        self.temporaryFilePathWHUIs = str(self.base_dir / "HUI.txt")
        self.outputTopKHUIsFilePath = ""
        self.delimiter = ":"
        self.numTopKHUI = 0

    def runAlgorithm(self, minUtil, transactionCount, currentK, inputPath, sortedCandidateFile, outputFile):
        self.minUtility = minUtil
        self.theCurrentK = currentK
        self.numberOfTransactions = transactionCount
        self.inputFilePath = str(inputPath)
        self.sortedCandidatePath = str(sortedCandidateFile)
        self.outputTopKHUIsFilePath = str(outputFile)

        with open(self.temporaryFilePathWHUIs, "w", encoding="utf-8") as hui_writer:
            HDB = [[] for _ in range(self.numberOfTransactions)]
            BNF = [[] for _ in range(self.numberOfTransactions)]
            self.initialization(HDB, BNF, len(HDB))
            self.readDatabase(HDB, BNF, len(HDB), self.inputFilePath)
            self.readCandidateItemsets(HDB, BNF, len(HDB), self.sortedCandidatePath, hui_writer)

        self.setNumberOfTopKHUIs(0)
        with open(self.temporaryFilePathWHUIs, "r", encoding="utf-8") as hui_reader, open(
            self.outputTopKHUIsFilePath, "w", encoding="utf-8"
        ) as output_writer:
            for record in hui_reader:
                record = record.strip()
                if not record:
                    continue
                temp = record.split(":")
                if int(temp[1]) >= self.minUtility:
                    output_writer.write(record.replace(":", " #UTIL: "))
                    output_writer.write("\n")
                    self.setNumberOfTopKHUIs(self.getNumberOfTopKHUIs() + 1)

        Path(self.temporaryFilePathWHUIs).unlink(missing_ok=True)
        Path(sortedCandidateFile).unlink(missing_ok=True)

    def readCandidateItemsets(self, HDB, BNF, num_trans, CIPath, writer):
        heap = OrderedMultiset(key=lambda pair: pair.y)
        num_HU = 0

        with open(CIPath, "r", encoding="utf-8") as reader:
            for candidate_record in reader:
                candidate_record = candidate_record.strip()
                if not candidate_record:
                    continue
                candidate_info = candidate_record.split(self.delimiter)
                match_count = 0
                estimated_utility = 0
                candidate = candidate_info[0].split(" ")

                if int(candidate_info[1]) >= self.minUtility:
                    for i in range(num_trans):
                        if HDB[i]:
                            match_count = 0
                            pattern_utility = 0

                            for token in candidate:
                                item = int(token)
                                if item in HDB[i]:
                                    match_count += 1
                                    index = HDB[i].index(item)
                                    pattern_utility += BNF[i][index]
                                else:
                                    pattern_utility = 0
                                    break

                            if match_count == len(candidate):
                                estimated_utility += pattern_utility

                    if estimated_utility >= self.minUtility:
                        writer.write(f"{candidate_info[0]}:{estimated_utility}\n")
                        self.updateHeap(heap, candidate_info[0], estimated_utility)
                        num_HU += 1

        writer.flush()
        return num_HU

    @staticmethod
    def readDatabase(HDB, BNF, num_trans, DBPath):
        transaction_count = 0
        with open(DBPath, "r", encoding="utf-8") as reader:
            for record in reader:
                record = record.strip()
                if not record:
                    continue
                data = record.split(":")
                transaction = data[0].split(" ")
                benefit = data[2].split(" ")
                for i in range(len(transaction)):
                    HDB[transaction_count].append(int(transaction[i]))
                    BNF[transaction_count].append(int(benefit[i]))
                transaction_count += 1

    def initialization(self, HDB, BNF, num_trans):
        for i in range(num_trans):
            HDB[i] = []
            BNF[i] = []

    def updateHeap(self, NCH, HUI, utility):
        if NCH.size() < self.theCurrentK:
            NCH.add(StringPair(HUI, utility))
        elif NCH.size() >= self.theCurrentK:
            if utility > self.minUtility:
                NCH.add(StringPair(HUI, utility))
                NCH.popMinimum()

        minimum = NCH.minimum()
        if minimum is not None and minimum.y > self.minUtility and NCH.size() >= self.theCurrentK:
            self.minUtility = minimum.y

    def getNumberOfTopKHUIs(self):
        return self.numTopKHUI

    def setNumberOfTopKHUIs(self, numTopKHUI):
        self.numTopKHUI = numTopKHUI


class AlgoTKU:
    class TreeNode:
        def __init__(self, item, twu, count):
            self.item = item
            self.count = count
            self.twu = twu
            self.hlink = None
            self.parentlink = None
            self.childlink = []

    class FPTree:
        def __init__(self, algo):
            self.algo = algo
            self.root = AlgoTKU.TreeNode(-1, 0, 0)
            self.HeaderTable = [None] * algo.itemCount

        def insPatternBase(self, tran, tranlen, L1, TWU, IC, SumBNF):
            parent = self.root
            for i in range(tranlen):
                target = tran[i]
                child_count = len(parent.childlink)

                if child_count == 0:
                    value = TWU - (SumBNF - self.algo.arrayMIU[target] * IC)
                    SumBNF = SumBNF - (self.algo.arrayMIU[target] * IC)
                    new_node = AlgoTKU.TreeNode(target, value, IC)
                    parent.childlink.append(new_node)
                    new_node.parentlink = parent
                    if self.HeaderTable[target] is None:
                        self.HeaderTable[target] = new_node
                    else:
                        new_node.hlink = self.HeaderTable[target]
                        self.HeaderTable[target] = new_node
                    parent = new_node
                else:
                    for j in range(child_count):
                        comp = parent.childlink[j]
                        if target == comp.item:
                            value = TWU - (SumBNF - self.algo.arrayMIU[target] * IC)
                            SumBNF = SumBNF - self.algo.arrayMIU[target] * IC
                            comp.twu += value
                            comp.count += IC
                            parent = comp
                            break
                        if L1[target] > L1[comp.item]:
                            value = TWU - (SumBNF - self.algo.arrayMIU[target] * IC)
                            SumBNF = SumBNF - (self.algo.arrayMIU[target] * IC)
                            new_node = AlgoTKU.TreeNode(target, value, IC)
                            parent.childlink.insert(j, new_node)
                            new_node.parentlink = parent
                            if self.HeaderTable[target] is None:
                                self.HeaderTable[target] = new_node
                            else:
                                new_node.hlink = self.HeaderTable[target]
                                self.HeaderTable[target] = new_node
                            parent = new_node
                            break
                        if L1[target] == L1[comp.item] and target < comp.item:
                            value = TWU - (SumBNF - self.algo.arrayMIU[target] * IC)
                            SumBNF = SumBNF - (self.algo.arrayMIU[target] * IC)
                            new_node = AlgoTKU.TreeNode(target, value, IC)
                            parent.childlink.insert(j, new_node)
                            new_node.parentlink = parent
                            if self.HeaderTable[target] is None:
                                self.HeaderTable[target] = new_node
                            else:
                                new_node.hlink = self.HeaderTable[target]
                                self.HeaderTable[target] = new_node
                            parent = new_node
                            break
                        if j == child_count - 1:
                            value = TWU - (SumBNF - self.algo.arrayMIU[target] * IC)
                            SumBNF = SumBNF - (self.algo.arrayMIU[target] * IC)
                            new_node = AlgoTKU.TreeNode(target, value, IC)
                            parent.childlink.append(new_node)
                            new_node.parentlink = parent
                            if self.HeaderTable[target] is None:
                                self.HeaderTable[target] = new_node
                            else:
                                new_node.hlink = self.HeaderTable[target]
                                self.HeaderTable[target] = new_node
                            parent = new_node

        def instrans2(self, tran, bran, tranlen, L1, IC):
            TWU = 0
            parent = self.root

            for i in range(tranlen):
                TWU += bran[i]
                target = tran[i]
                child_count = len(parent.childlink)

                if child_count == 0:
                    new_node = AlgoTKU.TreeNode(target, TWU, IC)
                    parent.childlink.append(new_node)
                    new_node.parentlink = parent
                    if self.HeaderTable[target] is None:
                        self.HeaderTable[target] = new_node
                    else:
                        new_node.hlink = self.HeaderTable[target]
                        self.HeaderTable[target] = new_node
                    parent = new_node
                else:
                    for j in range(child_count):
                        comp = parent.childlink[j]
                        if target == comp.item:
                            comp.twu += TWU
                            comp.count += IC
                            parent = comp
                            break
                        if L1[target] > L1[comp.item]:
                            new_node = AlgoTKU.TreeNode(target, TWU, IC)
                            parent.childlink.insert(j, new_node)
                            new_node.parentlink = parent
                            if self.HeaderTable[target] is None:
                                self.HeaderTable[target] = new_node
                            else:
                                new_node.hlink = self.HeaderTable[target]
                                self.HeaderTable[target] = new_node
                            parent = new_node
                            break
                        if L1[target] == L1[comp.item] and target < comp.item:
                            new_node = AlgoTKU.TreeNode(target, TWU, IC)
                            parent.childlink.insert(j, new_node)
                            new_node.parentlink = parent
                            if self.HeaderTable[target] is None:
                                self.HeaderTable[target] = new_node
                            else:
                                new_node.hlink = self.HeaderTable[target]
                                self.HeaderTable[target] = new_node
                            parent = new_node
                            break
                        if j == child_count - 1:
                            new_node = AlgoTKU.TreeNode(target, TWU, IC)
                            parent.childlink.append(new_node)
                            new_node.parentlink = parent
                            if self.HeaderTable[target] is None:
                                self.HeaderTable[target] = new_node
                            else:
                                new_node.hlink = self.HeaderTable[target]
                                self.HeaderTable[target] = new_node
                            parent = new_node

        def instrans3(self, tran, bran, tranlen, L1, IC, NodeCountHeap):
            TWU = 0
            parent = self.root

            for i in range(tranlen):
                TWU += bran[i]
                target = tran[i]
                child_count = len(parent.childlink)

                if child_count == 0:
                    new_node = AlgoTKU.TreeNode(target, TWU, IC)
                    parent.childlink.append(new_node)
                    if new_node.twu > self.algo.globalMinUtil:
                        self.algo.UpdateNodeCountHeap(NodeCountHeap, new_node.twu)
                    new_node.parentlink = parent
                    if self.HeaderTable[target] is None:
                        self.HeaderTable[target] = new_node
                    else:
                        new_node.hlink = self.HeaderTable[target]
                        self.HeaderTable[target] = new_node
                    parent = new_node
                else:
                    for j in range(child_count):
                        comp = parent.childlink[j]
                        if target == comp.item:
                            NodeCountHeap.remove(comp.twu)
                            self.algo.UpdateNodeCountHeap(NodeCountHeap, comp.twu + TWU)
                            comp.twu += TWU
                            comp.count += IC
                            parent = comp
                            break
                        if L1[target] > L1[comp.item]:
                            if comp.twu > self.algo.globalMinUtil:
                                self.algo.UpdateNodeCountHeap(NodeCountHeap, TWU)
                            new_node = AlgoTKU.TreeNode(target, TWU, IC)
                            parent.childlink.insert(j, new_node)
                            new_node.parentlink = parent
                            if self.HeaderTable[target] is None:
                                self.HeaderTable[target] = new_node
                            else:
                                new_node.hlink = self.HeaderTable[target]
                                self.HeaderTable[target] = new_node
                            parent = new_node
                            break
                        if L1[target] == L1[comp.item] and target < comp.item:
                            if comp.twu > self.algo.globalMinUtil:
                                self.algo.UpdateNodeCountHeap(NodeCountHeap, TWU)
                            new_node = AlgoTKU.TreeNode(target, TWU, IC)
                            parent.childlink.insert(j, new_node)
                            new_node.parentlink = parent
                            if self.HeaderTable[target] is None:
                                self.HeaderTable[target] = new_node
                            else:
                                new_node.hlink = self.HeaderTable[target]
                                self.HeaderTable[target] = new_node
                            parent = new_node
                            break
                        if j == child_count - 1:
                            if comp.twu > self.algo.globalMinUtil:
                                self.algo.UpdateNodeCountHeap(NodeCountHeap, TWU)
                            new_node = AlgoTKU.TreeNode(target, TWU, IC)
                            parent.childlink.append(new_node)
                            new_node.parentlink = parent
                            if self.HeaderTable[target] is None:
                                self.HeaderTable[target] = new_node
                            else:
                                new_node.hlink = self.HeaderTable[target]
                                self.HeaderTable[target] = new_node
                            parent = new_node

        def UPGrowth(self, tree2, flist2, prefix, writer, ISNodeCountHeap, LP1):
            for i in range(len(flist2)):
                current = flist2[i]
                if LP1[current] >= self.algo.globalMinUtil:
                    if prefix == "":
                        nprefix = prefix + str(current)
                    else:
                        nprefix = prefix + " " + str(current)

                    citem = current
                    chlink = tree2.HeaderTable[citem]
                    CPB = []
                    CPBW = []
                    CPBC = []
                    LocalF1 = [0] * self.algo.itemCount
                    LocalCount = [0] * self.algo.itemCount

                    while chlink is not None:
                        path = []
                        cptr = chlink
                        while cptr.parentlink is not None:
                            path.append(cptr.item)
                            LocalF1[cptr.item] += chlink.twu
                            LocalCount[cptr.item] += chlink.count
                            cptr = cptr.parentlink
                        if path:
                            del path[0]
                        CPB.append(path)
                        CPBW.append(chlink.twu)
                        CPBC.append(chlink.count)
                        chlink = chlink.hlink

                    localflist = []
                    for j in range(len(LocalF1)):
                        if LocalF1[j] < self.algo.globalMinUtil:
                            LocalF1[j] = -1
                        else:
                            if j != citem:
                                self.algo.InsertItem(localflist, j, LocalF1)
                                uti = f"{nprefix} {j}"
                                temp_items = uti.split(" ")
                                sum_mau = 0
                                sum_miu = 0

                                for token in temp_items:
                                    item = int(token)
                                    sum_mau += self.algo.arrayMAU[item]
                                    sum_miu += self.algo.arrayMIU[item]

                                mau = sum_mau * LocalCount[j]
                                if mau >= self.algo.globalMinUtil:
                                    miu = sum_miu * LocalCount[j]
                                    writer.write(f"{nprefix} {j}:{LocalF1[j]}\n")
                                    if miu > self.algo.globalMinUtil:
                                        self.algo.UpdateNodeCountHeap(ISNodeCountHeap, miu)

                    if CPB:
                        conditional_tree = AlgoTKU.FPTree(self.algo)
                        for k in range(len(CPB)):
                            ltran = CPB[k]
                            sum_min_bnf = 0
                            tran = [0] * len(ltran)
                            tranlen = 0

                            for h in range(len(ltran)):
                                if LocalF1[ltran[h]] >= self.algo.globalMinUtil:
                                    sum_min_bnf += CPBC[k] * self.algo.arrayMIU[ltran[h]]
                                    tran[tranlen] = ltran[h]
                                    tranlen += 1
                                else:
                                    CPBW[k] = CPBW[k] - CPBC[k] * self.algo.arrayMIU[ltran[h]]

                            self.algo.sorttrans(tran, 0, tranlen, LocalF1)
                            conditional_tree.insPatternBase(tran, tranlen, LocalF1, CPBW[k], CPBC[k], sum_min_bnf)

                        conditional_tree.UPGrowth_MinBNF(
                            conditional_tree, localflist, nprefix, writer, ISNodeCountHeap, LocalF1
                        )

            MemoryLogger.getInstance().checkMemory()
            writer.flush()

        def UPGrowth_MinBNF(self, tree2, flist2, prefix, writer, ISNodeCountHeap, LP1):
            for i in range(len(flist2)):
                current = flist2[i]
                if LP1[current] >= self.algo.globalMinUtil:
                    if prefix == "":
                        nprefix = prefix + str(current)
                    else:
                        nprefix = prefix + " " + str(current)

                    citem = current
                    chlink = tree2.HeaderTable[citem]
                    CPB = []
                    CPBW = []
                    CPBC = []
                    LocalF1 = [0] * self.algo.itemCount
                    LocalCount = [0] * self.algo.itemCount

                    while chlink is not None:
                        path = []
                        cptr = chlink
                        while cptr.parentlink is not None:
                            path.append(cptr.item)
                            LocalF1[cptr.item] += chlink.twu
                            LocalCount[cptr.item] += chlink.count
                            cptr = cptr.parentlink
                        if path:
                            del path[0]
                        CPB.append(path)
                        CPBW.append(chlink.twu)
                        CPBC.append(chlink.count)
                        chlink = chlink.hlink

                    localflist = []
                    for j in range(len(LocalF1)):
                        if LocalF1[j] < self.algo.globalMinUtil:
                            LocalF1[j] = -1
                        else:
                            if j != citem:
                                self.algo.InsertItem(localflist, j, LocalF1)
                                uti = f"{nprefix} {j}"
                                temp_items = uti.split(" ")
                                sum_mau = 0
                                sum_miu = 0

                                for token in temp_items:
                                    item = int(token)
                                    sum_mau += self.algo.arrayMAU[item]
                                    sum_miu += self.algo.arrayMIU[item]

                                mau = sum_mau * LocalCount[j]
                                if mau >= self.algo.globalMinUtil:
                                    miu = sum_miu * LocalCount[j]
                                    writer.write(f"{nprefix} {j}:{LocalF1[j]}\n")
                                    if miu > self.algo.globalMinUtil:
                                        self.algo.UpdateNodeCountHeap(ISNodeCountHeap, miu)

                    if CPB:
                        conditional_tree = AlgoTKU.FPTree(self.algo)
                        for k in range(len(CPB)):
                            ltran = CPB[k]
                            sum_min_bnf = 0
                            tran = [0] * len(ltran)
                            tranlen = 0

                            for h in range(len(ltran)):
                                if LocalF1[ltran[h]] >= self.algo.globalMinUtil:
                                    sum_min_bnf += CPBC[k] * self.algo.arrayMIU[ltran[h]]
                                    tran[tranlen] = ltran[h]
                                    tranlen += 1
                                else:
                                    CPBW[k] = CPBW[k] - CPBC[k] * self.algo.arrayMIU[ltran[h]]

                            self.algo.sorttrans(tran, 0, tranlen, LocalF1)
                            conditional_tree.insPatternBase(tran, tranlen, LocalF1, CPBW[k], CPBC[k], sum_min_bnf)

                        conditional_tree.UPGrowth_MinBNF(
                            conditional_tree, localflist, nprefix, writer, ISNodeCountHeap, LocalF1
                        )

            MemoryLogger.getInstance().checkMemory()
            writer.flush()

        def traverse_tree(self, cNode, level):
            level += 1
            if cNode is not None:
                for child in cNode.childlink:
                    self.traverse_tree(child, level)

        def SumDescendent(self, cNode, ds_sum_table):
            if cNode is not None:
                ds_sum_table[cNode.item] += cNode.count
                for child in cNode.childlink:
                    self.SumDescendent(child, ds_sum_table)

    def __init__(self, base_dir=None):
        if base_dir is None:
            base_dir = Path(__file__).resolve().parent
        self.base_dir = Path(base_dir)
        self.theInputFile = ""
        self.theCandidateFile = ""
        self.kValue = 0
        self.itemCount = 0
        self.globalMinUtil = 0
        self.arrayTWUItems = []
        self.arrayMIU = []
        self.arrayMAU = []
        self.totalTime = 0.0
        self.patternCount = 0

    def runAlgorithm(self, inputFile, outputFile, k):
        MemoryLogger.getInstance().reset()
        self.totalTime = time.time()
        self.globalMinUtil = 0

        tool = CalculateDatabaseInfo(inputFile)
        tool.runCalculate()

        ulist = []
        self.kValue = k
        self.theInputFile = str(inputFile)
        self.theCandidateFile = str(self.base_dir / "topKcandidate.txt")
        self.itemCount = tool.getMaxID() + 1
        self.arrayTWUItems = [0] * self.itemCount
        self.arrayMIU = [0] * self.itemCount
        self.arrayMAU = [0] * self.itemCount

        with open(self.theCandidateFile, "w", encoding="utf-8") as candidate_writer:
            self.globalMinUtil = self.preEvaluation(
                self.theInputFile,
                self.arrayTWUItems,
                self.itemCount,
                self.arrayMIU,
                self.arrayMAU,
                self.globalMinUtil,
                self.kValue,
            )

            tree = self.BuildUPTree(self.arrayTWUItems, self.theInputFile)
            tree.traverse_tree(tree.root, 0)

            ds_node_count_heap = OrderedMultiset()
            for i in range(len(tree.root.childlink)):
                sum_ds = [0] * self.itemCount
                ds_item = tree.root.childlink[i].item
                tree.SumDescendent(tree.root.childlink[i], sum_ds)
                for j in range(len(sum_ds)):
                    if sum_ds[j] != 0 and j != ds_item:
                        ds_value = (self.arrayMIU[j] + self.arrayMIU[ds_item]) * sum_ds[j]
                        self.UpdateNodeCountHeap(ds_node_count_heap, ds_value)

            ds_node_count_heap = OrderedMultiset()
            is_node_count_heap = OrderedMultiset()

            self.getUlist(self.arrayTWUItems, ulist)
            tree.UPGrowth(tree, ulist, "", candidate_writer, is_node_count_heap, self.arrayTWUItems)

            for i in range(len(self.arrayTWUItems)):
                if self.arrayTWUItems[i] >= self.globalMinUtil:
                    candidate_writer.write(f"{i}:{self.arrayTWUItems[i]}\n")

        MemoryLogger.getInstance().checkMemory()

        sorted_top_k_candidate_file = self.base_dir / "sortedTopKcandidate.txt"
        self.runSortHUIAlgorithm(self.theCandidateFile, sorted_top_k_candidate_file)
        Path(self.theCandidateFile).unlink(missing_ok=True)

        MemoryLogger.getInstance().checkMemory()

        algoPhase2 = AlgoPhase2OfTKU(self.base_dir)
        algoPhase2.runAlgorithm(
            int(self.globalMinUtil), tool.getDBSize(), k, inputFile, sorted_top_k_candidate_file, outputFile
        )

        self.patternCount = algoPhase2.getNumberOfTopKHUIs()
        MemoryLogger.getInstance().checkMemory()
        self.totalTime = time.time() - self.totalTime

    def runSortHUIAlgorithm(self, theCandidateFile, sortedTopKcandidateFile):
        heap = OrderedMultiset(key=lambda pair: pair.y)
        with open(theCandidateFile, "r", encoding="utf-8") as reader:
            for record in reader:
                record = record.strip()
                if not record:
                    continue
                temp = record.split(":")
                heap.add(StringPair(temp[0], int(temp[1])))

        with open(sortedTopKcandidateFile, "w", encoding="utf-8") as writer:
            n_elements = heap.size()
            for _ in range(n_elements):
                maximum = heap.maximum()
                writer.write(f"{maximum.x}:{maximum.y}\n")
                heap.popMaximum()

    def printStats(self):
        print("=============  TKU - v.2.26  =============")
        print(f" Total execution time : {self.totalTime} s")
        print(f" Number of top-k high utility patterns : {self.patternCount}")
        print(f" Max memory usage : {MemoryLogger.getInstance().getMaxMemory()} MB")
        print("===================================================")

    def preEvaluation(self, HDB, TWU1, num_Item, MinBNF, MaxBNF, mini_utility, pK):
        triangular_matrix = TKUTriangularMatrix(num_Item)

        with open(HDB, "r", encoding="utf-8") as reader:
            for transaction in reader:
                transaction = transaction.strip()
                if not transaction:
                    continue
                temp1 = transaction.split(":")
                temp2 = temp1[0].split(" ")
                temp3 = temp1[2].split(" ")

                for s in range(len(temp2)):
                    item = int(temp2[s])
                    utility = int(temp3[s])

                    if MinBNF[item] == 0:
                        if utility > 0:
                            MinBNF[item] = utility
                    elif MinBNF[item] > utility:
                        MinBNF[item] = utility

                    if MaxBNF[item] < utility:
                        MaxBNF[item] = utility

                    TWU1[item] += int(temp1[1])

                    if s > 0:
                        triangular_matrix.incrementCount(int(temp2[0]), item, int(temp3[0]) + utility)

        MemoryLogger.getInstance().checkMemory()
        return self.getInitialUtility(triangular_matrix, num_Item, pK)

    def getInitialUtility(self, TM, nItem, K):
        topKList = OrderedMultiset(key=lambda entry: -entry.priority)
        count = 0

        for i in range(nItem):
            for j in range(len(TM.matrix[i])):
                if TM.matrix[i][j] != 0:
                    if topKList.size() < K:
                        count += 1
                        topKList.add(HeapEntry(count=count, priority=TM.matrix[i][j]))
                    elif topKList.size() >= K:
                        peek = topKList.minimum()
                        if TM.matrix[i][j] > peek.priority:
                            count += 1
                            topKList.add(HeapEntry(count=count, priority=TM.matrix[i][j]))
                            topKList.popMinimum()

        peek = topKList.minimum()
        return 0 if peek is None else peek.priority

    def getUlist(self, P1, values):
        for i in range(len(P1)):
            if P1[i] > 0 and P1[i] >= self.globalMinUtil:
                self.InsertItem(values, i, P1)

    def InsertItem(self, values, target, order):
        if len(values) == 0:
            values.append(target)
        elif len(values) > 0:
            for i in range(len(values)):
                if order[target] > order[values[i]]:
                    values.insert(i, target)
                    return 0
                if order[target] == order[values[i]] and target < values[i]:
                    values.insert(i, target)
                    return 0
                if i == len(values) - 1:
                    values.append(target)
                    return 0
        return -1

    def sorttrans(self, tran, pre, tranlen, P1):
        for i in range(pre, tranlen - 1):
            for j in range(pre, tranlen - 1):
                if P1[tran[j]] < P1[tran[j + 1]]:
                    tran[j], tran[j + 1] = tran[j + 1], tran[j]
                elif P1[tran[j]] == P1[tran[j + 1]]:
                    if tran[j] > tran[j + 1]:
                        tran[j], tran[j + 1] = tran[j + 1], tran[j]

    def sorttrans2(self, tran, bran, pre, tranlen, P1):
        for i in range(pre, tranlen - 1):
            for j in range(pre, tranlen - 1):
                if P1[tran[j]] < P1[tran[j + 1]]:
                    tran[j], tran[j + 1] = tran[j + 1], tran[j]
                    bran[j], bran[j + 1] = bran[j + 1], bran[j]
                elif P1[tran[j]] == P1[tran[j + 1]]:
                    if tran[j] > tran[j + 1]:
                        tran[j], tran[j + 1] = tran[j + 1], tran[j]
                        bran[j], bran[j + 1] = bran[j + 1], bran[j]

    def UpdateNodeCountHeap(self, NCH, NewValue):
        if NCH.size() < self.kValue:
            NCH.add(NewValue)
        elif NCH.size() >= self.kValue:
            if NewValue > self.globalMinUtil:
                NCH.add(NewValue)
                NCH.popMinimum()

        minimum = NCH.minimum()
        if minimum is not None and minimum > self.globalMinUtil and NCH.size() >= self.kValue:
            self.globalMinUtil = minimum

    def BuildUPTree(self, P1, HDB):
        node_count_heap = OrderedMultiset()
        tree = AlgoTKU.FPTree(self)

        with open(HDB, "r", encoding="utf-8") as reader:
            for transaction in reader:
                transaction = transaction.strip()
                if not transaction:
                    continue
                temp1 = transaction.split(":")
                temp2 = temp1[0].split(" ")
                bran = [int(value) for value in temp1[2].split(" ")]
                bran2 = [0] * len(bran)

                tranlen = 0
                tran = [0] * len(temp2)
                for m in range(len(temp2)):
                    item = int(temp2[m])
                    if P1[item] >= self.globalMinUtil:
                        bran2[tranlen] = bran[m]
                        tran[tranlen] = item
                        tranlen += 1

                self.sorttrans2(tran, bran2, 0, tranlen, P1)
                tree.instrans3(tran, bran2, tranlen, P1, 1, node_count_heap)

        MemoryLogger.getInstance().checkMemory()
        return tree


def main():
    base_dir = Path(__file__).resolve().parent

    # --------------------------------------------------
    # Set parameters directly here
    # --------------------------------------------------
    input_path = str(base_dir / "DB_Utility.txt")
    output_path = str(base_dir / "outputs.txt")
    k = 20
    # --------------------------------------------------

    if not Path(input_path).exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    algo = AlgoTKU(base_dir)
    algo.runAlgorithm(input_path, output_path, k)
    algo.printStats()

    print(f"\nInput file : {Path(input_path).resolve()}")
    print(f"Output file: {Path(output_path).resolve()}\n")


if __name__ == "__main__":
    main()