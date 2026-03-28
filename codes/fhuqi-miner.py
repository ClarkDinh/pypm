# fhuqi_miner_single.py
# ------------------------------------------------------------
# Single-file Python port of SPMF FHUQI-Miner (Nouioua et al.)
#
# INPUT  : dbHUQI.txt   (same folder as this script)
#          dbHUQI_p.txt (same folder as this script)
# OUTPUT : output_py.txt (same folder as this script)
#
# Run:
#   /usr/bin/python3 fhuqi_miner_single.py
# ------------------------------------------------------------

import os
import math
import time
from bisect import bisect_left


# -----------------------------
# MemoryLogger (SPMF-like)
# -----------------------------
class MemoryLogger:
    _instance = None

    def __init__(self):
        self.maxMemory = 0.0
        self.recordingMode = False
        self._writer = None

    @classmethod
    def getInstance(cls):
        if cls._instance is None:
            cls._instance = MemoryLogger()
        return cls._instance

    def getMaxMemory(self):
        return self.maxMemory

    def reset(self):
        self.maxMemory = 0.0

    def checkMemory(self):
        current = self._get_current_memory_mb()
        if current > self.maxMemory:
            self.maxMemory = current
        if self.recordingMode and self._writer is not None:
            try:
                self._writer.write(str(current) + "\n")
                self._writer.flush()
            except Exception:
                pass
        return current

    @staticmethod
    def _get_current_memory_mb():
        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # macOS bytes, Linux KB heuristic
            if usage > 10_000_000:
                return usage / 1024.0 / 1024.0
            return usage / 1024.0
        except Exception:
            return 0.0


# -----------------------------
# EnumCombination (Java-like)
# -----------------------------
class EnumCombination:
    COMBINEMIN = "COMBINEMIN"
    COMBINEMAX = "COMBINEMAX"
    COMBINEALL = "COMBINEALL"


# -----------------------------
# Qitem
# -----------------------------
class Qitem:
    __slots__ = ("item", "qteMin", "qteMax")

    def __init__(self, i=0, qMin=0, qMax=None):
        self.item = int(i)
        self.qteMin = int(qMin)
        self.qteMax = int(qMin if qMax is None else qMax)

    def getItem(self):
        return self.item

    def getQteMin(self):
        return self.qteMin

    def getQteMax(self):
        return self.qteMax

    def setItem(self, i):
        self.item = int(i)

    def setQteMin(self, q):
        self.qteMin = int(q)

    def setQteMax(self, q):
        self.qteMax = int(q)

    def copy(self, q):
        self.item = q.item
        self.qteMin = q.qteMin
        self.qteMax = q.qteMax

    def isRange(self):
        return self.qteMin != self.qteMax

    def __str__(self):
        if not self.isRange():
            return f"({self.item},{self.qteMin})"
        return f"({self.item},{self.qteMin},{self.qteMax})"

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        if other is self:
            return True
        if not isinstance(other, Qitem):
            return False
        return (self.item == other.item and
                self.qteMin == other.qteMin and
                self.qteMax == other.qteMax)

    def __hash__(self):
        return hash((self.item, self.qteMin, self.qteMax))


# -----------------------------
# QItemTrans
# -----------------------------
class QItemTrans:
    __slots__ = ("tid", "eu", "ru")

    def __init__(self, tid, eu, ru):
        self.tid = int(tid)
        self.eu = int(eu)
        self.ru = int(ru)

    def getTid(self):
        return self.tid

    def getEu(self):
        return self.eu

    def getRu(self):
        return self.ru

    def sum(self):
        return self.eu + self.ru

    def __str__(self):
        # Java uses a TAB between eu and ru
        return f"{self.tid} {self.eu}\t{self.ru}"

    def __repr__(self):
        return str(self)


# -----------------------------
# UtilityListFHUQIMiner
# -----------------------------
class UtilityListFHUQIMiner:
    __slots__ = ("itemsetName", "sumIutils", "sumRutils", "twu", "qItemTrans")

    def __init__(self, name=None, twu=None):
        # Mirrors Java constructors:
        #  - UtilityListFHUQIMiner(ArrayList<Qitem> qitemset, long twu)
        #  - UtilityListFHUQIMiner(ArrayList<Qitem> qitemset)
        #  - UtilityListFHUQIMiner(Qitem name)
        #  - UtilityListFHUQIMiner(Qitem name, long twu)
        #  - UtilityListFHUQIMiner()
        self.itemsetName = []
        self.sumIutils = 0
        self.sumRutils = 0
        self.twu = 0
        self.qItemTrans = []

        if name is None:
            return

        if isinstance(name, list):
            self.itemsetName = name
            self.twu = 0 if twu is None else int(twu)
            self.qItemTrans = []
            return

        if isinstance(name, Qitem):
            self.itemsetName = [name]
            self.twu = 0 if twu is None else int(twu)
            self.qItemTrans = []
            return

        raise TypeError("Unsupported constructor args for UtilityListFHUQIMiner")

    def addTWU(self, twu):
        self.twu += int(twu)

    def setTWUtoZero(self):
        self.twu = 0

    def addTrans(self, qTid, twu=None):
        # Java overloaded addTrans(qTid) and addTrans(qTid, twu)
        self.sumIutils += qTid.getEu()
        self.sumRutils += qTid.getRu()
        self.qItemTrans.append(qTid)
        if twu is not None:
            self.twu += int(twu)

    def getSumIutils(self):
        return self.sumIutils

    def getSumRutils(self):
        return self.sumRutils

    def setSumIutils(self, x):
        self.sumIutils = int(x)

    def setSumRutils(self, x):
        self.sumRutils = int(x)

    def getTwu(self):
        return self.twu

    def setTwu(self, twu):
        self.twu = int(twu)

    def getItemsetName(self):
        return self.itemsetName

    def getSingleItemsetName(self):
        return self.itemsetName[0]

    def getQItemTrans(self):
        return self.qItemTrans

    def setQItemTrans(self, elements):
        self.qItemTrans = elements

    def QitemTransAdd(self, a, b):
        return QItemTrans(a.getTid(), a.getEu() + b.getEu(), a.getRu() + b.getRu())

    def addUtilityList2(self, nxt):
        temp = nxt.getQItemTrans()
        mainlist = []
        self.sumIutils += nxt.getSumIutils()
        self.sumRutils += nxt.getSumRutils()
        self.twu += nxt.getTwu()

        if len(self.qItemTrans) == 0:
            for e in temp:
                self.qItemTrans.append(e)
        else:
            i = 0
            j = 0
            while i < len(self.qItemTrans) and j < len(temp):
                t1 = self.qItemTrans[i].getTid()
                t2 = temp[j].getTid()
                if t1 > t2:
                    mainlist.append(temp[j])
                    j += 1
                elif t1 < t2:
                    mainlist.append(self.qItemTrans[i])
                    i += 1
                else:
                    # Java code is odd here: mainlist.add(t1, ...)
                    # We'll approximate by appending combined trans.
                    mainlist.append(self.QitemTransAdd(self.qItemTrans[i], temp[j]))
                    i += 1
                    j += 1

            if i == len(self.qItemTrans):
                while j < len(temp):
                    mainlist.append(temp[j])
                    j += 1
            elif j == len(temp):
                while i < len(self.qItemTrans):
                    mainlist.append(self.qItemTrans[i])
                    i += 1

            self.qItemTrans = mainlist

    def __str__(self):
        s = "\n=================================\n"
        s += str(self.itemsetName) + "\r\n"
        s += f"sumEU={self.sumIutils} sumRU={self.sumRutils} twu={self.twu}\r\n"
        for e in self.qItemTrans:
            s += str(e) + "\r\n"
        s += "=================================\n"
        return s

    def getqItemTransLength(self):
        return 0 if self.qItemTrans is None else len(self.qItemTrans)


# -----------------------------
# AlgoFHUQIMiner
# -----------------------------
class AlgoFHUQIMiner:
    BUFFERS_SIZE = 200
    DEBUG_MODE = False

    def __init__(self):
        self.outputFile = None
        self.inputDatabase = None
        self.writer_hqui = None

        self.mapItemToTwu = {}
        self.mapItemToProfit = {}
        self.mapTransactionToUtility = {}
        self.mapFMAP = {}

        self.minUtil = 0
        self.totalU = 0
        self.coefficient = 0
        self.combiningMethod = EnumCombination.COMBINEALL

        self.startTime = 0
        self.endTime = 0
        self.percent = 0.0

        self.HUQIcount = 0
        self.countUL = 0
        self.countConstruct = 0

        self.currentQitem = Qitem(0, 0)
        self.itemsetBuffer = [None] * self.BUFFERS_SIZE

    def runAlgorithm(self, inputData, inputProfit, percentage, coef, combinationmethod, output):
        # mimic System.gc()
        MemoryLogger.getInstance().reset()
        self.startTime = int(time.time() * 1000)

        self.writer_hqui = open(output, "w", encoding="utf-8", newline="\n")

        self.itemsetBuffer = [None] * self.BUFFERS_SIZE
        self.coefficient = int(coef)
        self.percent = float(percentage)
        self.combiningMethod = combinationmethod

        self.mapItemToProfit = {}
        self.mapTransactionToUtility = {}
        self.totalU = 0
        self.HUQIcount = 0
        self.countUL = 0
        self.countConstruct = 0

        qitemNameList = []
        mapItemToUtilityList = {}

        if self.DEBUG_MODE:
            print("1. Build Initial Q-Utility Lists")
        self.buildInitialQUtilityLists(inputData, inputProfit, qitemNameList, mapItemToUtilityList)
        MemoryLogger.getInstance().checkMemory()

        if self.DEBUG_MODE:
            print("2. Find Initial High Utility Range Q-items")
        candidateList = []
        hwQUI = []
        self.findInitialRHUQIs(qitemNameList, mapItemToUtilityList, candidateList, hwQUI)
        MemoryLogger.getInstance().checkMemory()

        if self.DEBUG_MODE:
            print("3. Recurcive Mining Procedure")
        self.miner(self.itemsetBuffer, 0, None, mapItemToUtilityList, qitemNameList, self.writer_hqui, hwQUI)
        MemoryLogger.getInstance().checkMemory()

        self.endTime = int(time.time() * 1000)
        self.writer_hqui.close()
        self.writer_hqui = None

    def printStatistics(self):
        print("============= FHUQI-MINER v 2.45 Statistical results===============")
        print("HUQIcount: " + str(self.HUQIcount))
        print("Runtime: " + str((self.endTime - self.startTime) / 1000.0) + " (s)")
        print("Memory usage: " + str(MemoryLogger.getInstance().getMaxMemory()) + " (Mb)")
        if self.DEBUG_MODE:
            print("Join opertaion count: " + str(self.countConstruct))
        print("================================================")

    # ---- Core building ----
    def buildInitialQUtilityLists(self, inputData, inputProfit, qitemNameList, mapItemToUtilityList):
        # Profit table
        with open(inputProfit, "r", encoding="utf-8") as br_profit:
            for line in br_profit:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(", ")
                if len(parts) >= 2:
                    item = int(parts[0])
                    profit = int(parts[1])
                    if profit == 0:
                        profit = 1
                    self.mapItemToProfit[item] = profit

        # TWU pass
        self.mapItemToTwu = {}
        tid = 0
        self.currentQitem = Qitem(0, 0)
        with open(inputData, "r", encoding="utf-8") as br_db:
            for line in br_db:
                line = line.strip()
                if not line:
                    continue
                tid += 1
                itemInfo = line.split(" ")
                transactionU = 0

                # compute transaction utility
                for tok in itemInfo:
                    comma = tok.index(",")
                    it = int(tok[:comma])
                    q = int(tok[comma + 1 :])
                    self.currentQitem.setItem(it)
                    self.currentQitem.setQteMin(q)
                    self.currentQitem.setQteMax(q)
                    transactionU += self.currentQitem.getQteMin() * self.mapItemToProfit[self.currentQitem.getItem()]

                # add to TWU for each qitem in trans
                for tok in itemInfo:
                    comma = tok.index(",")
                    it = int(tok[:comma])
                    q = int(tok[comma + 1 :])
                    self.currentQitem.setItem(it)
                    self.currentQitem.setQteMin(q)
                    self.currentQitem.setQteMax(q)

                    Q = Qitem()
                    Q.copy(self.currentQitem)
                    self.mapItemToTwu[Q] = self.mapItemToTwu.get(Q, 0) + transactionU

                self.totalU += transactionU

        self.minUtil = int(self.totalU * self.percent)  # Java (long)(totalU*percent)

        # Build initial ULs for qitems with TWU >= floor(minUtil/coefficient)
        minUtilDivCoef = int(math.floor(self.minUtil / float(self.coefficient))) if self.coefficient != 0 else 0
        for qitem, twu in self.mapItemToTwu.items():
            if twu >= minUtilDivCoef:
                ul = UtilityListFHUQIMiner(qitem, 0)
                mapItemToUtilityList[qitem] = ul
                qitemNameList.append(qitem)

        MemoryLogger.getInstance().checkMemory()

        # Build FMAP + fill utility lists
        self.mapFMAP = {}
        tid = 0
        with open(inputData, "r", encoding="utf-8") as br_db:
            for line in br_db:
                line = line.strip()
                if not line:
                    continue
                tid += 1
                itemInfo = line.split(" ")

                remainingUtility = 0
                newTWU = 0
                revisedTransaction = []

                for tok in itemInfo:
                    comma = tok.index(",")
                    it = int(tok[:comma])
                    q = int(tok[comma + 1 :])
                    Q = Qitem(it, q)

                    if Q in mapItemToUtilityList:
                        revisedTransaction.append(Q)
                        gain = Q.getQteMin() * self.mapItemToProfit[Q.getItem()]
                        remainingUtility += gain
                        newTWU += gain

                # Java does mapTransactionToUtility.put(tid, newTWU) inside the loop,
                # but final value is the same: store once.
                self.mapTransactionToUtility[tid] = newTWU

                revisedTransaction.sort(key=lambda q: self._qitem_sort_key(q))

                for i in range(len(revisedTransaction)):
                    q = revisedTransaction[i]
                    remainingUtility -= q.getQteMin() * self.mapItemToProfit[q.getItem()]

                    ul = mapItemToUtilityList[q]
                    element = QItemTrans(
                        tid,
                        q.getQteMin() * self.mapItemToProfit[q.getItem()],
                        remainingUtility,
                    )
                    ul.addTrans(element)
                    ul.addTWU(self.mapTransactionToUtility[tid])

                    mapFMAPItem = self.mapFMAP.get(q)
                    if mapFMAPItem is None:
                        mapFMAPItem = {}
                        self.mapFMAP[q] = mapFMAPItem

                    for j in range(i + 1, len(revisedTransaction)):
                        qAfter = revisedTransaction[j]
                        twu_prev = mapFMAPItem.get(qAfter)
                        if twu_prev is None:
                            mapFMAPItem[qAfter] = newTWU
                        else:
                            mapFMAPItem[qAfter] = twu_prev + newTWU

        MemoryLogger.getInstance().checkMemory()

        # Sort final qitems list (descending by q*profit, then item)
        qitemNameList.sort(key=lambda q: self._qitem_sort_key(q))
        MemoryLogger.getInstance().checkMemory()

    def _qitem_sort_key(self, q):
        # Java compareQItems:
        # compare = (util2 - util1); then item lexical
        util = q.getQteMin() * self.mapItemToProfit[q.getItem()]
        return (-util, q.getItem())

    def compareCandidateItems(self, q1, q2):
        # Java compareCandidateItems: item, qteMin, qteMax
        if q1.getItem() != q2.getItem():
            return q1.getItem() - q2.getItem()
        if q1.getQteMin() != q2.getQteMin():
            return q1.getQteMin() - q2.getQteMin()
        return q1.getQteMax() - q2.getQteMax()

    # ---- Initial filtering + combining ----
    def findInitialRHUQIs(self, qitemNameList, mapItemToUtilityList, candidateList, hwQUI):
        minUtilDivCoef = int(math.floor(self.minUtil / float(self.coefficient))) if self.coefficient != 0 else 0
        minUtilDiv2 = int(math.floor(self.minUtil / 2.0))

        for q in qitemNameList:
            utility = mapItemToUtilityList[q].getSumIutils()
            if utility >= self.minUtil:
                self.writer_hqui.write(str(q) + " #UTIL: " + str(utility) + "\r\n")
                hwQUI.append(q)
                self.HUQIcount += 1
            else:
                if (self.combiningMethod != EnumCombination.COMBINEMAX and utility >= minUtilDivCoef) or (
                    self.combiningMethod == EnumCombination.COMBINEMAX and utility >= minUtilDiv2
                ):
                    candidateList.append(q)

                if utility + mapItemToUtilityList[q].getSumRutils() >= self.minUtil:
                    hwQUI.append(q)

        MemoryLogger.getInstance().checkMemory()
        # Combine
        self.combineMethod(None, 0, candidateList, qitemNameList, mapItemToUtilityList, hwQUI)

    def combineMethod(self, prefix, prefixLength, candidateList, qItemNameList, mapItemToUtilityList, hwQUI):
        if len(candidateList) > 2:
            # Java sorts candidateList by item then qmin then qmax
            candidateList.sort(key=lambda q: (q.getItem(), q.getQteMin(), q.getQteMax()))

            if self.combiningMethod == EnumCombination.COMBINEALL:
                self.combineAll(prefix, prefixLength, candidateList, qItemNameList, mapItemToUtilityList, hwQUI)
            elif self.combiningMethod == EnumCombination.COMBINEMIN:
                self.combineMin(prefix, prefixLength, candidateList, qItemNameList, mapItemToUtilityList, hwQUI)
            elif self.combiningMethod == EnumCombination.COMBINEMAX:
                self.combineMax(prefix, prefixLength, candidateList, qItemNameList, mapItemToUtilityList, hwQUI)

            MemoryLogger.getInstance().checkMemory()
        return qItemNameList

    def _cleanup_candidates_inplace(self, candidateList):
        # Implements the shared "delete non necessary candidate q-items" logic
        s = 1
        while s < len(candidateList) - 1:
            left = candidateList[s - 1]
            cur = candidateList[s]
            right = candidateList[s + 1]
            cond = (
                (cur.getQteMin() == left.getQteMax() + 1 and cur.getItem() == left.getItem())
                or (cur.getQteMax() == right.getQteMin() - 1 and cur.getItem() == right.getItem())
            )
            if cond:
                s += 1
            else:
                candidateList.pop(s)

        if len(candidateList) > 2:
            last = candidateList[-1]
            prev = candidateList[-2]
            if (last.getQteMin() != prev.getQteMax() + 1) or (prev.getItem() != last.getItem()):
                candidateList.pop()

    def combineAll(self, prefix, prefixLength, candidateList, qItemNameList, mapItemToUtilityList, hwQUI):
        self._cleanup_candidates_inplace(candidateList)

        if len(candidateList) <= 2:
            MemoryLogger.getInstance().checkMemory()
            return

        mapRangeToUtilityList = {}

        for i in range(len(candidateList)):
            currentItem = candidateList[i].getItem()
            mapRangeToUtilityList.clear()
            count = 1

            for j in range(i + 1, len(candidateList)):
                nextItem = candidateList[j].getItem()
                if currentItem != nextItem:
                    break

                if j == i + 1:
                    if candidateList[j].getQteMin() != candidateList[i].getQteMax() + 1:
                        break

                    res = self.constructForCombine(mapItemToUtilityList[candidateList[i]],
                                                   mapItemToUtilityList[candidateList[j]])
                    count += 1
                    if count > self.coefficient:
                        break

                    mapRangeToUtilityList[res.getSingleItemsetName()] = res
                    if res.getSumIutils() > self.minUtil:
                        self.HUQIcount += 1
                        self.writeOut2(prefix, prefixLength, res.getSingleItemsetName(), res.getSumIutils())
                        hwQUI.append(res.getSingleItemsetName())
                        mapItemToUtilityList[res.getSingleItemsetName()] = res

                        site = qItemNameList.index(candidateList[j])
                        qItemNameList.insert(site, res.getSingleItemsetName())
                else:
                    if candidateList[j].getQteMin() != candidateList[j - 1].getQteMax() + 1:
                        break

                    qItem1 = Qitem(currentItem, candidateList[i].getQteMin(), candidateList[j - 1].getQteMax())
                    ulQitem1 = mapRangeToUtilityList.get(qItem1)
                    if ulQitem1 is None:
                        break

                    res = self.constructForCombine(ulQitem1, mapItemToUtilityList[candidateList[j]])
                    count += 1
                    if count > self.coefficient:
                        break

                    mapRangeToUtilityList[res.getSingleItemsetName()] = res
                    if res.getSumIutils() > self.minUtil:
                        self.HUQIcount += 1
                        self.writeOut2(prefix, prefixLength, res.getSingleItemsetName(), res.getSumIutils())
                        hwQUI.append(res.getSingleItemsetName())
                        mapItemToUtilityList[res.getSingleItemsetName()] = res

                        site = qItemNameList.index(candidateList[j])
                        qItemNameList.insert(site, res.getSingleItemsetName())

        MemoryLogger.getInstance().checkMemory()

    def combineMin(self, prefix, prefixLength, candidateList, qItemNameList, mapItemToUtilityList, hwQUI):
        self._cleanup_candidates_inplace(candidateList)
        if len(candidateList) <= 2:
            MemoryLogger.getInstance().checkMemory()
            return

        temporaryArrayList = []
        temporaryMap = {}
        mapRangeToUtilityList = {}

        for i in range(len(candidateList)):
            currentItem = candidateList[i].getItem()
            mapRangeToUtilityList.clear()
            count = 1

            for j in range(i + 1, len(candidateList)):
                nextItem = candidateList[j].getItem()
                if currentItem != nextItem:
                    break

                if j == i + 1:
                    if candidateList[j].getQteMin() != candidateList[i].getQteMax() + 1:
                        break

                    res = self.constructForCombine(mapItemToUtilityList[candidateList[i]],
                                                   mapItemToUtilityList[candidateList[j]])
                    count += 1
                    if count > self.coefficient:
                        break

                    mapRangeToUtilityList[res.getSingleItemsetName()] = res
                    if res.getSumIutils() > self.minUtil:
                        if (not temporaryArrayList) or \
                           (res.getSingleItemsetName().getItem() != temporaryArrayList[-1].getItem()) or \
                           (res.getSingleItemsetName().getQteMax() > temporaryArrayList[-1].getQteMax()):
                            temporaryArrayList.append(res.getSingleItemsetName())
                            temporaryMap[res.getSingleItemsetName()] = res
                        else:
                            last = temporaryArrayList.pop()
                            temporaryMap.pop(last, None)
                            temporaryArrayList.append(res.getSingleItemsetName())
                            temporaryMap[res.getSingleItemsetName()] = res
                        break
                else:
                    if candidateList[j].getQteMin() != candidateList[j - 1].getQteMax() + 1:
                        break

                    qItem1 = Qitem(currentItem, candidateList[i].getQteMin(), candidateList[j - 1].getQteMax())
                    ulQitem1 = mapRangeToUtilityList.get(qItem1)
                    if ulQitem1 is None:
                        break

                    res = self.constructForCombine(ulQitem1, mapItemToUtilityList[candidateList[j]])
                    count += 1
                    if count > self.coefficient:
                        break

                    mapRangeToUtilityList[res.getSingleItemsetName()] = res
                    if res.getSumIutils() > self.minUtil:
                        if (not temporaryArrayList) or \
                           (res.getSingleItemsetName().getItem() != temporaryArrayList[-1].getItem()) or \
                           (res.getSingleItemsetName().getQteMax() > temporaryArrayList[-1].getQteMax()):
                            temporaryArrayList.append(res.getSingleItemsetName())
                            temporaryMap[res.getSingleItemsetName()] = res
                        else:
                            last = temporaryArrayList.pop()
                            temporaryMap.pop(last, None)
                            temporaryArrayList.append(res.getSingleItemsetName())
                            temporaryMap[res.getSingleItemsetName()] = res
                        break

        for currentQitem in temporaryArrayList:
            mapItemToUtilityList[currentQitem] = temporaryMap[currentQitem]
            self.writeOut2(prefix, prefixLength, currentQitem, temporaryMap[currentQitem].getSumIutils())
            self.HUQIcount += 1
            hwQUI.append(currentQitem)

            q = Qitem(currentQitem.getItem(), currentQitem.getQteMax())
            site = qItemNameList.index(q)
            qItemNameList.insert(site, currentQitem)

        temporaryArrayList.clear()
        temporaryMap.clear()
        MemoryLogger.getInstance().checkMemory()

    def combineMax(self, prefix, prefixLength, candidateList, qItemNameList, mapItemToUtilityList, hwQUI):
        self._cleanup_candidates_inplace(candidateList)
        if len(candidateList) <= 2:
            MemoryLogger.getInstance().checkMemory()
            return

        temporaryArrayList = []
        temporaryMap = {}
        mapRangeToUtilityList = {}

        for i in range(len(candidateList)):
            res = UtilityListFHUQIMiner()
            currentItem = candidateList[i].getItem()
            mapRangeToUtilityList.clear()
            count = 1

            for j in range(i + 1, len(candidateList)):
                nextItem = candidateList[j].getItem()
                if currentItem != nextItem:
                    break

                if j == i + 1:
                    if candidateList[j].getQteMin() != candidateList[i].getQteMax() + 1:
                        break
                    res = self.constructForCombine(mapItemToUtilityList[candidateList[i]],
                                                   mapItemToUtilityList[candidateList[j]])
                    count += 1
                    if count > self.coefficient - 1:
                        break
                    mapRangeToUtilityList[res.getSingleItemsetName()] = res
                else:
                    if candidateList[j].getQteMin() != candidateList[j - 1].getQteMax() + 1:
                        break

                    qItem1 = Qitem(currentItem, candidateList[i].getQteMin(), candidateList[j - 1].getQteMax())
                    ulQitem1 = mapRangeToUtilityList.get(qItem1)
                    if ulQitem1 is None:
                        break

                    res = self.constructForCombine(ulQitem1, mapItemToUtilityList[candidateList[j]])
                    count += 1
                    if count >= self.coefficient:
                        break
                    mapRangeToUtilityList[res.getSingleItemsetName()] = res

            if hasattr(res, "getSumIutils") and res.getSumIutils() > self.minUtil:
                if (not temporaryMap) or \
                   (res.getSingleItemsetName().getItem() != temporaryArrayList[-1].getItem()) or \
                   (res.getSingleItemsetName().getQteMax() > temporaryArrayList[-1].getQteMax()):
                    temporaryMap[res.getSingleItemsetName()] = res
                    temporaryArrayList.append(res.getSingleItemsetName())

        for currentQitem in temporaryArrayList:
            mapItemToUtilityList[currentQitem] = temporaryMap[currentQitem]
            self.writeOut2(prefix, prefixLength, currentQitem, temporaryMap[currentQitem].getSumIutils())
            self.HUQIcount += 1
            hwQUI.append(currentQitem)

            q = Qitem(currentQitem.getItem(), currentQitem.getQteMax())
            site = qItemNameList.index(q)
            qItemNameList.insert(site, currentQitem)

        temporaryArrayList.clear()
        temporaryMap.clear()
        MemoryLogger.getInstance().checkMemory()

    # ---- Construct helpers ----
    def constructForCombine(self, ulQitem1, ulQitem2):
        # result name = (item, ul1.qmin, ul2.qmax)
        result_name = Qitem(
            ulQitem1.getSingleItemsetName().getItem(),
            ulQitem1.getSingleItemsetName().getQteMin(),
            ulQitem2.getSingleItemsetName().getQteMax(),
        )
        result = UtilityListFHUQIMiner(result_name)

        temp1 = ulQitem1.getQItemTrans()
        temp2 = ulQitem2.getQItemTrans()
        mainlist = []

        result.setSumIutils(ulQitem1.getSumIutils() + ulQitem2.getSumIutils())
        result.setSumRutils(ulQitem1.getSumRutils() + ulQitem2.getSumRutils())
        result.setTwu(ulQitem1.getTwu() + ulQitem2.getTwu())

        i = 0
        j = 0
        # NOTE: Java does not handle equality explicitly (t1==t2 goes to else, adds temp1)
        while i < len(temp1) and j < len(temp2):
            t1 = temp1[i].getTid()
            t2 = temp2[j].getTid()
            if t1 > t2:
                mainlist.append(temp2[j])
                j += 1
            else:
                mainlist.append(temp1[i])
                i += 1

        if i == len(temp1):
            while j < len(temp2):
                mainlist.append(temp2[j])
                j += 1
        elif j == len(temp2):
            while i < len(temp1):
                mainlist.append(temp1[i])
                i += 1

        result.setQItemTrans(mainlist)
        MemoryLogger.getInstance().checkMemory()
        return result

    def constructForJoin(self, ul1, ul2, ul0):
        if ul1.getSingleItemsetName().getItem() == ul2.getSingleItemsetName().getItem():
            return None

        qT1 = ul1.getQItemTrans()
        qT2 = ul2.getQItemTrans()
        res = UtilityListFHUQIMiner(ul2.getItemsetName())

        if ul0 is None:
            i = 0
            j = 0
            while i < len(qT1) and j < len(qT2):
                tid1 = qT1[i].getTid()
                tid2 = qT2[j].getTid()

                if tid1 == tid2:
                    eu1 = qT1[i].getEu()
                    eu2 = qT2[j].getEu()

                    if qT1[i].getRu() >= qT2[j].getRu():
                        temp = QItemTrans(tid1, eu1 + eu2, qT2[j].getRu())
                        res.addTrans(temp, self.mapTransactionToUtility.get(tid1, 0))
                    i += 1
                    j += 1
                elif tid1 > tid2:
                    j += 1
                else:
                    i += 1
        else:
            preQT = ul0.getQItemTrans()
            i = 0
            j = 0
            k = 0
            while i < len(qT1) and j < len(qT2):
                tid1 = qT1[i].getTid()
                tid2 = qT2[j].getTid()

                if tid1 == tid2:
                    eu1 = qT1[i].getEu()
                    eu2 = qT2[j].getEu()

                    # advance k until preQT[k].tid == tid1
                    while k < len(preQT) and preQT[k].getTid() != tid1:
                        k += 1
                    if k >= len(preQT):
                        break
                    preEU = preQT[k].getEu()

                    if qT1[i].getRu() >= qT2[j].getRu():
                        temp = QItemTrans(tid1, eu1 + eu2 - preEU, qT2[j].getRu())
                        res.addTrans(temp, self.mapTransactionToUtility.get(tid1, 0))
                    i += 1
                    j += 1
                elif tid1 > tid2:
                    j += 1
                else:
                    i += 1

        MemoryLogger.getInstance().checkMemory()
        if res.getQItemTrans():
            return res
        return None

    # ---- Mining ----
    def miner(self, prefix, prefixLength, prefixUL, ULs, qItemNameList, br_writer_hqui, hwQUI):
        t2 = [0] * self.coefficient
        nextNameList = []

        minUtilDivCoef = int(math.floor(self.minUtil / float(self.coefficient))) if self.coefficient != 0 else 0
        minUtilDiv2 = int(math.floor(self.minUtil / 2.0))

        for i in range(len(qItemNameList)):
            nextNameList.clear()
            nextHWQUI = []
            candidateList = []
            nextHUL = {}
            candidateHUL = {}

            if qItemNameList[i] not in hwQUI:
                continue

            if qItemNameList[i].isRange():
                for ii in range(qItemNameList[i].getQteMin(), qItemNameList[i].getQteMax() + 1):
                    t2[ii - qItemNameList[i].getQteMin()] = qItemNameList.index(Qitem(qItemNameList[i].getItem(), ii))

            for j in range(i + 1, len(qItemNameList)):
                if qItemNameList[j].isRange():
                    continue
                if qItemNameList[i].isRange() and j == i + 1:
                    continue

                afterUL = None

                mapTWUF = self.mapFMAP.get(qItemNameList[i])
                if mapTWUF is not None:
                    twuF = mapTWUF.get(qItemNameList[j])
                    if twuF is None or twuF < minUtilDivCoef:
                        continue
                    afterUL = self.constructForJoin(ULs[qItemNameList[i]], ULs[qItemNameList[j]], prefixUL)
                    self.countConstruct += 1
                    if afterUL is None or afterUL.getTwu() < minUtilDivCoef:
                        continue
                else:
                    # range q-itemsets case
                    sumtwu = 0
                    for ii in range(qItemNameList[i].getQteMin(), qItemNameList[i].getQteMax() + 1):
                        idx = t2[ii - qItemNameList[i].getQteMin()]
                        a = qItemNameList[min(idx, j)]
                        b = qItemNameList[max(idx, j)]
                        inner = self.mapFMAP.get(a)
                        if inner is None:
                            continue
                        val = inner.get(b)
                        if val is None:
                            continue
                        sumtwu += val

                    if sumtwu < minUtilDivCoef:
                        continue
                    afterUL = self.constructForJoin(ULs[qItemNameList[i]], ULs[qItemNameList[j]], prefixUL)
                    self.countConstruct += 1
                    if afterUL is None or afterUL.getTwu() < minUtilDivCoef:
                        continue

                if afterUL is not None and afterUL.getTwu() >= minUtilDivCoef:
                    nextNameList.append(afterUL.getSingleItemsetName())
                    nextHUL[afterUL.getSingleItemsetName()] = afterUL
                    self.countUL += 1

                    if afterUL.getSumIutils() >= self.minUtil:
                        self.writeOut1(prefix, prefixLength, qItemNameList[i], qItemNameList[j], afterUL.getSumIutils())
                        self.HUQIcount += 1
                        nextHWQUI.append(afterUL.getSingleItemsetName())
                    else:
                        if (self.combiningMethod != EnumCombination.COMBINEMAX and afterUL.getSumIutils() >= minUtilDivCoef) or (
                            self.combiningMethod == EnumCombination.COMBINEMAX and afterUL.getSumIutils() >= minUtilDiv2
                        ):
                            candidateList.append(afterUL.getSingleItemsetName())
                            candidateHUL[afterUL.getSingleItemsetName()] = afterUL

                        if afterUL.getSumIutils() + afterUL.getSumRutils() >= self.minUtil:
                            nextHWQUI.append(afterUL.getSingleItemsetName())

            if len(candidateList) > 0:
                nextNameList = self.combineMethod(prefix, prefixLength, candidateList, nextNameList, nextHUL, nextHWQUI)
                candidateHUL.clear()
                candidateList.clear()

            MemoryLogger.getInstance().checkMemory()

            if len(nextNameList) >= 1:
                self.itemsetBuffer[prefixLength] = qItemNameList[i]
                self.miner(self.itemsetBuffer, prefixLength + 1, ULs[qItemNameList[i]], nextHUL, nextNameList,
                           br_writer_hqui, nextHWQUI)

    # ---- Output ----
    def writeOut1(self, prefix, prefixLength, x, y, utility):
        buf = []
        for i in range(prefixLength):
            buf.append(str(prefix[i]))
        buf.append(str(x) + " " + str(y) + " #UTIL: " + str(utility))
        self.writer_hqui.write(" ".join(buf) + "\n")

    def writeOut2(self, prefix, prefixLength, x, utility):
        buf = []
        for i in range(prefixLength):
            buf.append(str(prefix[i]))
        buf.append(str(x) + " #UTIL: " + str(utility))
        self.writer_hqui.write(" ".join(buf) + "\n")


# -----------------------------
# Main (like MainTestFHUQIMiner)
# -----------------------------
def main():
    here = os.path.dirname(os.path.abspath(__file__))

    input_profit = os.path.join(here, "dbHUQI_p.txt")
    input_db = os.path.join(here, "dbHUQI.txt")
    output_path = os.path.join(here, "output_py.txt")

    percentage = 0.40
    coef = 3
    combinationmethod = EnumCombination.COMBINEALL

    algo = AlgoFHUQIMiner()
    algo.runAlgorithm(input_db, input_profit, percentage, coef, combinationmethod, output_path)
    algo.printStatistics()


if __name__ == "__main__":
    main()