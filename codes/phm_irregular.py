#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Single-file Python implementation of SPMF AlgoPHM (PHM / PHM_irregular).

Includes:
- AlgoPHM
- UtilityListPHM
- Element
- MemoryLogger

Default main reproduces MainTestPHM_irregular.java:
- input: DB_UtilityPerHUIs.txt
- output: output_py.txt
- min_utility = 20
- regularityThreshold = 2
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
import os
import time


# -----------------------------
# Memory Logger (lightweight)
# -----------------------------
class MemoryLogger:
    _instance = None

    def __init__(self) -> None:
        self._max_mb: float = 0.0

    @classmethod
    def getInstance(cls) -> "MemoryLogger":
        if cls._instance is None:
            cls._instance = MemoryLogger()
        return cls._instance

    def reset(self) -> None:
        self._max_mb = 0.0

    def checkMemory(self) -> None:
        # Best-effort cross-platform memory usage.
        try:
            import resource  # type: ignore
            usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # Linux: KB, macOS: bytes (often)
            mb = usage / 1024.0 if usage < 10_000_000 else usage / 1024.0 / 1024.0
            if mb > self._max_mb:
                self._max_mb = mb
        except Exception:
            pass

    def getMaxMemory(self) -> float:
        return self._max_mb


# -----------------------------
# Core data structures
# -----------------------------
@dataclass(order=True)
class Element:
    tid: int
    iutils: int
    rutils: int


class UtilityListPHM:
    def __init__(self, item: int) -> None:
        self.item: int = item
        self.sumIutils: int = 0
        self.sumRutils: int = 0
        self.elements: List[Element] = []
        self.largestPeriodicity: int = 0
        self.smallestPeriodicity: int = 2**31 - 1  # Integer.MAX_VALUE

    def addElement(self, element: Element) -> None:
        self.sumIutils += element.iutils
        self.sumRutils += element.rutils
        self.elements.append(element)

    def getSupport(self) -> int:
        return len(self.elements)


# -----------------------------
# AlgoPHM (converted)
# -----------------------------
class AlgoPHM:
    class Pair:
        __slots__ = ("item", "utility")

        def __init__(self, item: int, utility: int) -> None:
            self.item = item
            self.utility = utility

    class ItemInfo:
        __slots__ = ("support", "largestPeriodicity", "smallestPeriodicity", "lastSeenTransaction")

        def __init__(self) -> None:
            self.support: int = 0
            self.largestPeriodicity: int = 0
            self.smallestPeriodicity: int = 2**31 - 1
            self.lastSeenTransaction: int = 0

    BUFFERS_SIZE = 200

    def __init__(self) -> None:
        self.phuiCount = 0
        self.candidateCount = 0

        self.mapItemToTWU: Dict[int, int] = {}
        self.mapItemToItemInfo: Dict[int, AlgoPHM.ItemInfo] = {}

        self.mapEUCS: Optional[Dict[int, Dict[int, int]]] = None
        self.mapESCS: Optional[Dict[int, Dict[int, int]]] = None

        self.ENABLE_LA_PRUNE = True
        self.ENABLE_EUCP = True
        self.ENABLE_ESCP = True
        self.DEBUG = False

        self.databaseSize = 0

        self.minPeriodicity = 0
        self.maxPeriodicity = 0
        self.minAveragePeriodicity = 0
        self.maxAveragePeriodicity = 0

        self.minimumLength = 0
        self.maximumLength = 2**31 - 1

        self.supportPruningThreshold = 0.0

        self.totalExecutionTime = 0.0
        self.maximumMemoryUsage = 0.0

        self.findingIrregularItemsets = False

        self._writer = None  # type: ignore

    # ---------- public API ----------
    def runAlgorithmIrregular(self, input_path: str, output_path: str, minUtility: int, regularityThreshold: int) -> None:
        self.findingIrregularItemsets = True
        self.setEnableESCP(False)  # as in Java irregular mode
        self.runAlgorithm(
            input_path,
            output_path,
            minUtility,
            regularityThreshold,
            2**31 - 1,  # Integer.MAX_VALUE
            0,
            2**31 - 1
        )

    def runAlgorithm(
        self,
        input_path: str,
        output_path: str,
        minUtility: int,
        minPeriodicity: int,
        maxPeriodicity: int,
        minAveragePeriodicity: int,
        maxAveragePeriodicity: int
    ) -> None:
        MemoryLogger.getInstance().reset()
        start_ts = time.time()

        self.maxPeriodicity = maxPeriodicity
        self.minPeriodicity = minPeriodicity
        self.minAveragePeriodicity = minAveragePeriodicity
        self.maxAveragePeriodicity = maxAveragePeriodicity

        self.mapEUCS = {} if self.ENABLE_EUCP else None
        self.mapESCS = {} if self.ENABLE_ESCP else None

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        self._writer = open(output_path, "w", encoding="utf-8")

        self.mapItemToTWU = {}
        self.mapItemToItemInfo = {}
        self.databaseSize = 0
        sumOfTransactionLength = 0

        # -------- First pass --------
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in "#%@":
                    continue

                self.databaseSize += 1
                split = line.split(":")
                items = split[0].split()
                transactionUtility = int(split[1])

                sumOfTransactionLength += len(items)

                for it in items:
                    item = int(it)

                    # TWU
                    self.mapItemToTWU[item] = self.mapItemToTWU.get(item, 0) + transactionUtility

                    # Support/periodicity
                    info = self.mapItemToItemInfo.get(item)
                    if info is None:
                        info = AlgoPHM.ItemInfo()
                        self.mapItemToItemInfo[item] = info

                    info.support += 1
                    periodicity = self.databaseSize - info.lastSeenTransaction
                    if info.largestPeriodicity < periodicity:
                        info.largestPeriodicity = periodicity
                    info.lastSeenTransaction = self.databaseSize

                    if info.support != 1 and periodicity < info.smallestPeriodicity:
                        info.smallestPeriodicity = periodicity

        self.supportPruningThreshold = (self.databaseSize / float(self.maxAveragePeriodicity)) - 1.0

        # Finalize last period (only for largestPeriodicity)
        for item, info in self.mapItemToItemInfo.items():
            periodicity = self.databaseSize - info.lastSeenTransaction
            if info.largestPeriodicity < periodicity:
                info.largestPeriodicity = periodicity

            if self.DEBUG:
                avg_per = self.databaseSize / float(info.support + 1)
                print(
                    f" item : {item}"
                    f"\tavgPer: {avg_per}"
                    f"\tminPer: {info.smallestPeriodicity}"
                    f"\tmaxPer: {info.largestPeriodicity}"
                    f"\tTWU: {self.mapItemToTWU.get(item)}"
                    f"\tsup.: {info.support}"
                )

        if self.DEBUG:
            print("Number of transactions :", self.databaseSize)
            print("Average transaction length :", sumOfTransactionLength / float(self.databaseSize))
            print("Number of items :", len(self.mapItemToItemInfo))
            print("Average pruning threshold  (|D| / maxAvg $) - 1):", self.supportPruningThreshold)

        # -------- Build utility lists for promising items --------
        listOfUtilityLists: List[UtilityListPHM] = []
        mapItemToUtilityList: Dict[int, UtilityListPHM] = {}

        for item, twu in self.mapItemToTWU.items():
            info = self.mapItemToItemInfo[item]
            if (
                info.support >= self.supportPruningThreshold
                and info.largestPeriodicity <= self.maxPeriodicity
                and twu >= minUtility
            ):
                ulist = UtilityListPHM(item)
                ulist.largestPeriodicity = info.largestPeriodicity
                ulist.smallestPeriodicity = info.smallestPeriodicity
                mapItemToUtilityList[item] = ulist
                listOfUtilityLists.append(ulist)

        listOfUtilityLists.sort(key=lambda ul: (self.mapItemToTWU[ul.item], ul.item))

        # -------- Second pass --------
        tid = 0
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in "#%@":
                    continue

                split = line.split(":")
                items = split[0].split()
                utilityValues = split[2].split()

                remainingUtility = 0
                newTWU = 0
                revised: List[AlgoPHM.Pair] = []

                for i in range(len(items)):
                    item = int(items[i])
                    util = int(utilityValues[i])
                    info = self.mapItemToItemInfo[item]
                    if (
                        info.support >= self.supportPruningThreshold
                        and info.largestPeriodicity <= self.maxPeriodicity
                        and self.mapItemToTWU[item] >= minUtility
                    ):
                        revised.append(AlgoPHM.Pair(item, util))
                        remainingUtility += util
                        newTWU += util

                revised.sort(key=lambda p: (self.mapItemToTWU[p.item], p.item))

                for i, pair in enumerate(revised):
                    remainingUtility -= pair.utility

                    ulist_item = mapItemToUtilityList[pair.item]
                    ulist_item.addElement(Element(tid, pair.utility, remainingUtility))

                    if self.ENABLE_EUCP and self.mapEUCS is not None:
                        fmap = self.mapEUCS.get(pair.item)
                        if fmap is None:
                            fmap = {}
                            self.mapEUCS[pair.item] = fmap
                        for j in range(i + 1, len(revised)):
                            after = revised[j]
                            fmap[after.item] = fmap.get(after.item, 0) + newTWU

                    if self.ENABLE_ESCP and self.mapESCS is not None:
                        smap = self.mapESCS.get(pair.item)
                        if smap is None:
                            smap = {}
                            self.mapESCS[pair.item] = smap
                        for j in range(i + 1, len(revised)):
                            after = revised[j]
                            smap[after.item] = smap.get(after.item, 0) + 1

                tid += 1

        MemoryLogger.getInstance().checkMemory()

        # -------- Mine recursively --------
        buffer = [0] * self.BUFFERS_SIZE
        self.phm(buffer, 0, None, listOfUtilityLists, minUtility)

        MemoryLogger.getInstance().checkMemory()

        self._writer.close()
        self._writer = None

        self.totalExecutionTime = (time.time() - start_ts) * 1000.0
        self.maximumMemoryUsage = MemoryLogger.getInstance().getMaxMemory()

    def printStats(self) -> None:
        optimizationEUCP = " EUCP: true -" if self.ENABLE_EUCP else " EUCP: false -"
        optimizationESCP = " ESCP: true " if self.ENABLE_ESCP else " ESCP: false "
        name = "PHM"
        patternType = "Periodic"

        if self.findingIrregularItemsets:
            name += "_irregular"
            optimizationESCP = ""
            patternType = "Irregular"

        print(f"=============  {name} v2.38{optimizationEUCP}{optimizationESCP}=====")
        print(f" Database size: {self.databaseSize} transactions")
        print(f" Time : {int(self.totalExecutionTime)} ms")
        print(f" Memory ~ {self.maximumMemoryUsage} MB")
        print(f" {patternType} High-utility itemsets count : {self.phuiCount}")
        print(f" Candidate count : {self.candidateCount}")
        print("===================================================")

    def setEnableEUCP(self, enable: bool) -> None:
        self.ENABLE_EUCP = enable

    def setEnableESCP(self, enable: bool) -> None:
        self.ENABLE_ESCP = enable

    def setMinimumLength(self, minimumLength: int) -> None:
        self.minimumLength = minimumLength

    def setMaximumLength(self, maximumLength: int) -> None:
        self.maximumLength = maximumLength

    # ---------- internal ----------
    def phm(
        self,
        prefix: List[int],
        prefixLength: int,
        pUL: Optional[UtilityListPHM],
        ULs: List[UtilityListPHM],
        minUtility: int
    ) -> None:
        patternSize = prefixLength + 1

        for i in range(len(ULs)):
            X = ULs[i]

            if X.sumIutils + X.sumRutils >= minUtility:
                averagePeriodicity = self.databaseSize / float(X.getSupport() + 1)

                if (
                    X.sumIutils >= minUtility
                    and averagePeriodicity <= self.maxAveragePeriodicity
                    and averagePeriodicity >= self.minAveragePeriodicity
                    and X.smallestPeriodicity >= self.minPeriodicity
                    and X.largestPeriodicity <= self.maxPeriodicity
                ):
                    if self.minimumLength <= patternSize <= self.maximumLength:
                        self.writeOut(prefix, prefixLength, X, averagePeriodicity)

                if patternSize < self.maximumLength:
                    exULs: List[UtilityListPHM] = []
                    for j in range(i + 1, len(ULs)):
                        Y = ULs[j]

                        if self.ENABLE_EUCP and self.mapEUCS is not None:
                            twu_map = self.mapEUCS.get(X.item)
                            if twu_map is not None:
                                twuF = twu_map.get(Y.item)
                                if twuF is None or twuF < minUtility:
                                    continue

                        if self.ENABLE_ESCP and self.mapESCS is not None:
                            sup_map = self.mapESCS.get(X.item)
                            if sup_map is not None:
                                supportF = sup_map.get(Y.item)
                                if supportF is not None and supportF < self.supportPruningThreshold:
                                    continue

                        self.candidateCount += 1
                        temp = self.construct(pUL, X, Y, minUtility)
                        if temp is not None:
                            exULs.append(temp)

                    prefix[prefixLength] = X.item
                    self.phm(prefix, prefixLength + 1, X, exULs, minUtility)

        MemoryLogger.getInstance().checkMemory()

    def construct(self, P: Optional[UtilityListPHM], px: UtilityListPHM, py: UtilityListPHM, minUtility: int) -> Optional[UtilityListPHM]:
        pxyUL = UtilityListPHM(py.item)

        lastTid = -1  # tids start at 0

        totalUtility = px.sumIutils + px.sumRutils
        totalSupport = px.getSupport()

        for ex in px.elements:
            ey = self.findElementWithTID(py, ex.tid)
            if ey is None:
                if self.ENABLE_LA_PRUNE:
                    totalUtility -= (ex.iutils + ex.rutils)
                    if totalUtility < minUtility:
                        return None
                    totalSupport -= 1
                    if totalSupport < self.supportPruningThreshold:
                        return None
                continue

            if P is None:
                periodicity = ex.tid - lastTid
                if periodicity > self.maxPeriodicity:
                    return None
                if periodicity >= pxyUL.largestPeriodicity:
                    pxyUL.largestPeriodicity = periodicity
                lastTid = ex.tid

                if len(pxyUL.elements) > 0 and periodicity < pxyUL.smallestPeriodicity:
                    pxyUL.smallestPeriodicity = periodicity

                pxyUL.addElement(Element(ex.tid, ex.iutils + ey.iutils, ey.rutils))
            else:
                e = self.findElementWithTID(P, ex.tid)
                if e is not None:
                    periodicity = ex.tid - lastTid
                    if periodicity > self.maxPeriodicity:
                        return None
                    if periodicity >= pxyUL.largestPeriodicity:
                        pxyUL.largestPeriodicity = periodicity
                    lastTid = ex.tid

                    if len(pxyUL.elements) > 0 and periodicity < pxyUL.smallestPeriodicity:
                        pxyUL.smallestPeriodicity = periodicity

                    pxyUL.addElement(Element(ex.tid, ex.iutils + ey.iutils - e.iutils, ey.rutils))

        periodicity = (self.databaseSize - 1) - lastTid  # -1 because tid starts at 0
        if periodicity > self.maxPeriodicity:
            return None
        if periodicity >= pxyUL.largestPeriodicity:
            pxyUL.largestPeriodicity = periodicity

        if pxyUL.getSupport() < self.supportPruningThreshold:
            return None

        return pxyUL

    @staticmethod
    def findElementWithTID(ulist: UtilityListPHM, tid: int) -> Optional[Element]:
        arr = ulist.elements
        first, last = 0, len(arr) - 1
        while first <= last:
            mid = (first + last) >> 1
            mtid = arr[mid].tid
            if mtid < tid:
                first = mid + 1
            elif mtid > tid:
                last = mid - 1
            else:
                return arr[mid]
        return None

    def writeOut(self, prefix: List[int], prefixLength: int, utilityList: UtilityListPHM, averagePeriodicity: float) -> None:
        self.phuiCount += 1

        items = [str(prefix[i]) for i in range(prefixLength)] + [str(utilityList.item)]
        line = " ".join(items) + f" #UTIL: {utilityList.sumIutils}"

        if self.findingIrregularItemsets:
            line += f" #REG: {utilityList.largestPeriodicity}"
        else:
            line += f" #SUP: {utilityList.getSupport()}"
            line += f" #MINPER: {utilityList.smallestPeriodicity}"
            line += f" #MAXPER: {utilityList.largestPeriodicity}"
            line += f" #AVGPER: {averagePeriodicity}"

        assert self._writer is not None
        self._writer.write(line + "\n")


# -----------------------------
# Main (like MainTestPHM_irregular)
# -----------------------------
def main() -> None:
    input_file = "DB_UtilityPerHUIs.txt"
    output_file = "output_py.txt"

    min_utility = 25
    regularityThreshold = 2

    algo = AlgoPHM()

    # Optional:
    # algo.setEnableEUCP(False)
    # algo.setMinimumLength(1)
    # algo.setMaximumLength(5)

    algo.runAlgorithmIrregular(input_file, output_file, min_utility, regularityThreshold)
    algo.printStats()


if __name__ == "__main__":
    main()