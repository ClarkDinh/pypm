#!/usr/bin/env python3

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple


# -----------------------------
# ElementFOSHU (inferred from Java usage)
# -----------------------------
@dataclass(frozen=True)
class ElementFOSHU:
    tid: int
    iputils: int  # positive part
    inutils: int  # negative part (negative number)
    rutils: int   # remaining utility (upper bound)


# -----------------------------
# UtilityListFOSHU (matches your Java exactly)
# -----------------------------
class UtilityListFOSHU:
    def __init__(self, item: Optional[int] = None, periodCount: int = 0,
                 pUL: Optional["UtilityListFOSHU"] = None,
                 x: Optional["UtilityListFOSHU"] = None,
                 y: Optional["UtilityListFOSHU"] = None) -> None:
        # if called as join constructor: UtilityListFOSHU(periodCount, pUL, X, Y)
        if x is not None and y is not None:
            self.item = y.item
            self.sumIutilP = 0
            self.sumIutilN = 0
            self.periodsElements: List[Optional[List[ElementFOSHU]]] = [None] * periodCount
            self.periodsSumIutilRutil: List[int] = [0] * periodCount

            if pUL is None:
                for i in range(periodCount):
                    if x.periodsElements[i] is not None and y.periodsElements[i] is not None:
                        self._construct_xy(i, x.periodsElements[i], y.periodsElements[i])
            else:
                for i in range(periodCount):
                    if x.periodsElements[i] is not None and y.periodsElements[i] is not None:
                        self._construct_pxy(i, pUL.periodsElements[i], x.periodsElements[i], y.periodsElements[i])
            return

        # normal constructor for 1-item utility list
        self.item = item
        self.sumIutilP = 0
        self.sumIutilN = 0
        self.periodsElements: List[Optional[List[ElementFOSHU]]] = [None] * periodCount
        self.periodsSumIutilRutil: List[int] = [0] * periodCount

    def addElement(self, element: ElementFOSHU, period: int) -> None:
        if self.periodsElements[period] is None:
            self.periodsElements[period] = []
        self.periodsElements[period].append(element)
        self.sumIutilP += element.iputils
        self.sumIutilN += element.inutils
        self.periodsSumIutilRutil[period] += element.iputils + element.rutils

    @staticmethod
    def _findElementWithTID(lst: List[ElementFOSHU], tid: int) -> Optional[ElementFOSHU]:
        first, last = 0, len(lst) - 1
        while first <= last:
            mid = (first + last) >> 1
            mtid = lst[mid].tid
            if mtid < tid:
                first = mid + 1
            elif mtid > tid:
                last = mid - 1
            else:
                return lst[mid]
        return None

    def _construct_pxy(self, period: int,
                       pElements: Optional[List[ElementFOSHU]],
                       pXElements: List[ElementFOSHU],
                       pYElements: List[ElementFOSHU]) -> None:
        if pElements is None:
            return
        self.periodsElements[period] = []
        for ex in pXElements:
            ey = self._findElementWithTID(pYElements, ex.tid)
            if ey is None:
                continue
            e = self._findElementWithTID(pElements, ex.tid)
            if e is not None:
                eXY = ElementFOSHU(
                    ex.tid,
                    ex.iputils + ey.iputils - e.iputils,
                    ex.inutils + ey.inutils - e.inutils,
                    ey.rutils
                )
                self.addElement(eXY, period)

    def _construct_xy(self, period: int,
                      pXElements: List[ElementFOSHU],
                      pYElements: List[ElementFOSHU]) -> None:
        self.periodsElements[period] = []
        for ex in pXElements:
            ey = self._findElementWithTID(pYElements, ex.tid)
            if ey is None:
                continue
            eXY = ElementFOSHU(
                ex.tid,
                ex.iputils + ey.iputils,
                ex.inutils + ey.inutils,
                ey.rutils
            )
            self.addElement(eXY, period)

    def getSumIRUtilsInPeriod(self, period: int) -> float:
        return self.periodsSumIutilRutil[period]

    def appearsInPeriod(self, period: int) -> bool:
        return self.periodsElements[period] is not None and len(self.periodsElements[period]) != 0

    def getElementsOfPeriod(self, period: int) -> Optional[List[ElementFOSHU]]:
        return self.periodsElements[period]


# -----------------------------
# AlgoFOSHU (matches your Java logic)
# -----------------------------
class AlgoFOSHU:
    def __init__(self) -> None:
        self.maxMemory = 0.0
        self.startTimestamp = 0.0
        self.endTimestamp = 0.0
        self.huiCount = 0
        self.joinCount = 0
        self.input = ""

        self.mapItemToTWU: Dict[int, int] = {}
        self.transactionsTU: List[int] = []

        self.debug = False
        self.maxSEQUENCECOUNT = 2**31 - 1

        self.negativeItems: Set[int] = set()
        self.minUtilityRatio: float = 0.0
        self.periodUtilities: List[int] = []

        self._writer = None

    def _checkMemory(self) -> None:
        cur = 0.0
        try:
            import resource
            r = resource.getrusage(resource.RUSAGE_SELF)
            v = float(r.ru_maxrss)
            cur = v / (1024.0 * 1024.0) if v > 10_000_000 else v / 1024.0
        except Exception:
            cur = 0.0
        if cur > self.maxMemory:
            self.maxMemory = cur

    def _incrementPeriodUtility(self, period: int, tu: int) -> None:
        notSeenBefore = len(self.periodUtilities) < (period + 1)
        if notSeenBefore:
            while len(self.periodUtilities) < period:
                self.periodUtilities.append(0)
            self.periodUtilities.append(tu)
        else:
            self.periodUtilities[period] = self.periodUtilities[period] + tu

    def _calculateRelativeUtilityInPeriod(self, z: int, utility: float) -> float:
        denom = abs(float(self.periodUtilities[z]))
        if denom == 0:
            return 0.0
        return utility / denom

    @staticmethod
    def _calculateRelativeUtility(sumPeriodUtility: int, utility: float) -> float:
        if sumPeriodUtility == 0:
            return 0.0
        return utility / abs(float(sumPeriodUtility))

    def _compareItems(self, item1: int, item2: int) -> int:
        item1neg = item1 in self.negativeItems
        item2neg = item2 in self.negativeItems
        if (not item1neg) and item2neg:
            return -1
        if item1neg and (not item2neg):
            return 1
        # compare TWU then lexical
        c = self.mapItemToTWU[item1] - self.mapItemToTWU[item2]
        return (item1 - item2) if c == 0 else c

    def runAlgorithm(self, input_path: str, output_path: str, minUtilityRatio: float) -> None:
        self.maxMemory = 0.0
        self.input = input_path
        self.minUtilityRatio = minUtilityRatio

        self.startTimestamp = time.time()

        self.negativeItems = set()
        self.periodUtilities = []
        self.mapItemToTWU = {}

        self._writer = open(output_path, "w", encoding="utf-8")

        transactionCount = 0

        # -------- 1st pass: TWU + negative items + period utilities --------
        with open(input_path, "r", encoding="utf-8") as f:
            for raw in f:
                if transactionCount > self.maxSEQUENCECOUNT:
                    break
                line = raw.strip()
                if not line or line[0] in ("#", "%", "@"):
                    continue

                transactionCount += 1
                split = line.split(":")
                items = split[0].split()
                utilityValues = split[2].split()

                # BUG FIX 2016 logic: recompute TU
                util_int = [int(x) for x in utilityValues]
                tu_with_neg_pos = sum(util_int)
                tu_positive_only = sum(u for u in util_int if u > 0)

                period = int(split[3])

                # TWU uses positive-only TU
                for it_s, u in zip(items, util_int):
                    it = int(it_s)
                    if u < 0:
                        self.negativeItems.add(it)
                    self.mapItemToTWU[it] = self.mapItemToTWU.get(it, 0) + tu_positive_only

                # period utility uses TU with negative+positive
                self._incrementPeriodUtility(period, tu_with_neg_pos)

        # -------- create utility lists for all items --------
        periodCount = len(self.periodUtilities)
        listOfULs: List[UtilityListFOSHU] = []
        mapItemToUL: Dict[int, UtilityListFOSHU] = {}

        self.transactionsTU = [0] * transactionCount

        for item in self.mapItemToTWU.keys():
            ul = UtilityListFOSHU(item=item, periodCount=periodCount)
            mapItemToUL[item] = ul
            listOfULs.append(ul)

        listOfULs.sort(key=lambda ul: (1 if ul.item in self.negativeItems else 0, self.mapItemToTWU[ul.item], ul.item))

        # -------- 2nd pass: build UL elements by period --------
        tid = 0
        with open(input_path, "r", encoding="utf-8") as f:
            for raw in f:
                if tid > self.maxSEQUENCECOUNT:
                    break
                line = raw.strip()
                if not line or line[0] in ("#", "%", "@"):
                    continue

                split = line.split(":")
                items = split[0].split()
                utilityValues = split[2].split()
                period = int(split[3])

                # revisedTransaction keeps all items (Java removed pruning)
                revised: List[Tuple[int, int]] = []
                remainingUtility = 0

                for it_s, u_s in zip(items, utilityValues):
                    it = int(it_s)
                    u = int(u_s)
                    revised.append((it, u))
                    # remaining utility counts only positive utilities for positive-profit items
                    if it not in self.negativeItems:
                        remainingUtility += u

                self.transactionsTU[tid] = remainingUtility

                # sort by compareItems (negatives last, then TWU)
                revised.sort(key=lambda p: (1 if p[0] in self.negativeItems else 0, self.mapItemToTWU[p[0]], p[0]))

                for (it, u) in revised:
                    if remainingUtility != 0:
                        remainingUtility -= u

                    ul = mapItemToUL[it]
                    if u > 0:
                        e = ElementFOSHU(tid, u, 0, remainingUtility)
                    else:
                        e = ElementFOSHU(tid, 0, u, remainingUtility)
                    ul.addElement(e, period)

                tid += 1

        self._checkMemory()

        # -------- remove unpromising items based on TWU per period --------
        filtered: List[UtilityListFOSHU] = []
        for X in listOfULs:
            promising = False
            for z in range(periodCount):
                if X.appearsInPeriod(z):
                    twuX = 0
                    elems = X.getElementsOfPeriod(z) or []
                    for e in elems:
                        twuX += self.transactionsTU[e.tid]
                    if self._calculateRelativeUtilityInPeriod(z, twuX) >= self.minUtilityRatio:
                        promising = True
                        break
            if promising:
                filtered.append(X)

        # -------- mine recursively --------
        self._foshu(prefix=[], pUL=None, ULs=filtered)

        self._checkMemory()
        self._writer.close()
        self._writer = None

        self.endTimestamp = time.time()

    def _foshu(self, prefix: List[int], pUL: Optional[UtilityListFOSHU], ULs: List[UtilityListFOSHU]) -> None:
        periodCount = len(self.periodUtilities)

        for i in range(len(ULs)):
            X = ULs[i]

            sumPeriodUtility = 0
            promising_in_one_period = False

            for z in range(periodCount):
                if X.appearsInPeriod(z):
                    sumPeriodUtility += self.periodUtilities[z]
                    if self._calculateRelativeUtilityInPeriod(z, X.getSumIRUtilsInPeriod(z)) >= self.minUtilityRatio:
                        promising_in_one_period = True

            ru = self._calculateRelativeUtility(sumPeriodUtility, (X.sumIutilP + X.sumIutilN))

            if ru >= self.minUtilityRatio:
                self._writeOut(prefix, X.item, X.sumIutilP + X.sumIutilN, ru)

            if not promising_in_one_period:
                continue

            exULs: List[UtilityListFOSHU] = []
            newPrefix = prefix + [X.item]

            for j in range(i + 1, len(ULs)):
                Y = ULs[j]
                self.joinCount += 1

                pXY = UtilityListFOSHU(periodCount=periodCount, pUL=pUL, x=X, y=Y)

                promising = False
                for z in range(periodCount):
                    if pXY.appearsInPeriod(z):
                        twuXY = 0
                        elems = pXY.getElementsOfPeriod(z) or []
                        for e in elems:
                            twuXY += self.transactionsTU[e.tid]
                        if self._calculateRelativeUtilityInPeriod(z, twuXY) >= self.minUtilityRatio:
                            promising = True
                            break
                if promising:
                    exULs.append(pXY)

            self._foshu(newPrefix, X, exULs)

    def _writeOut(self, prefix: List[int], item: int, utility: int, rutil: float) -> None:
        self.huiCount += 1
        s = ""
        if prefix:
            s += " ".join(str(x) for x in prefix) + " "
        s += str(item)
        s += " #UTIL: " + str(utility)
        s += " #RUTIL: " + str(rutil)
        self._writer.write(s + "\n")

    def printStats(self) -> None:
        print("=============  FOSHU ALGORITHM v2.02 - STATS =============")
        print("Dataset : " + self.input)
        total_ms = int((self.endTimestamp - self.startTimestamp) * 1000.0)
        print(" Total time ~ " + str(total_ms) + " ms")
        print(" Memory ~ " + str(self.maxMemory) + " MB")
        print(" HOU count : " + str(self.huiCount))
        print(" Join count : " + str(self.joinCount))
        print("===================================================")


# -----------------------------
# MainTestFOSHU_saveToFile.java equivalent
# -----------------------------
def main() -> None:
    input_path = "DB_FOSHU.txt"
    min_utility_ratio = 0.8
    output_path = "output_py.txt"

    algo = AlgoFOSHU()
    algo.runAlgorithm(input_path, output_path, min_utility_ratio)
    # algo.maxSEQUENCECOUNT = 9196  # if you want like Java comment
    algo.printStats()


if __name__ == "__main__":
    main()
