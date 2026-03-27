#!/usr/bin/env python3
# mlhui_miner.py

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Set


# -----------------------------
# MemoryLogger (Java-like)
# -----------------------------
class MemoryLogger:
    _instance = None

    def __init__(self) -> None:
        self.maxMemory = 0.0

    @classmethod
    def getInstance(cls) -> "MemoryLogger":
        if cls._instance is None:
            cls._instance = MemoryLogger()
        return cls._instance

    def getMaxMemory(self) -> float:
        return self.maxMemory

    def reset(self) -> None:
        self.maxMemory = 0.0

    def checkMemory(self) -> float:
        """
        Java logic: (totalMemory - freeMemory)/1024/1024.
        In Python we approximate RSS using resource when available.
        """
        current = 0.0
        try:
            import resource
            r = resource.getrusage(resource.RUSAGE_SELF)
            val = float(r.ru_maxrss)
            # ru_maxrss is KB on Linux, bytes on macOS sometimes; normalize.
            current = val / (1024.0 * 1024.0) if val > 10_000_000 else val / 1024.0
        except Exception:
            current = 0.0

        if current > self.maxMemory:
            self.maxMemory = current
        return current


# -----------------------------
# ElementMLHUIMiner
# -----------------------------
@dataclass(frozen=True)
class ElementMLHUIMiner:
    tid: int
    iutils: float
    rutils: float


# -----------------------------
# UtilityListMLHUIMiner (Java-like)
# -----------------------------
class UtilityListMLHUIMiner:
    def __init__(self, item: Optional[List[int]] = None) -> None:
        self.item: List[int] = item if item is not None else []
        self.sumIutils: float = 0.0
        self.sumRutils: float = 0.0
        self.elements: List[ElementMLHUIMiner] = []

    def addElement(self, element: ElementMLHUIMiner) -> None:
        """
        EXACT Java behavior:
        - If an element with same tid already exists, replace it with merged (old+new)
        - Otherwise append
        - Always: sumIutils += element.iutils, sumRutils += element.rutils
        """
        for i, e in enumerate(self.elements):
            if e.tid == element.tid:
                merged = ElementMLHUIMiner(
                    element.tid,
                    e.iutils + element.iutils,
                    e.rutils + element.rutils
                )
                self.elements[i] = merged
                self.sumIutils += element.iutils
                self.sumRutils += element.rutils
                return

        self.elements.append(element)
        self.sumIutils += element.iutils
        self.sumRutils += element.rutils

    def deleteElement(self, element: ElementMLHUIMiner) -> None:
        self.sumIutils -= element.iutils
        self.sumRutils -= element.rutils
        self.elements.remove(element)

    def getSupport(self) -> int:
        return len(self.elements)


# -----------------------------
# AlgoMLHUIMiner
# -----------------------------
class AlgoMLHUIMiner:
    def __init__(self) -> None:
        self.startTimeStamp = 0.0
        self.endTimeStamp = 0.0
        self.huiCount = 0

        self.mapItemToGeneralizedItem: Dict[int, int] = {}
        self.mapItemToGWU: Dict[int, float] = {}
        self.mapItemToLevel: Dict[int, int] = {}
        self.mapItemToUtilityList: Dict[int, UtilityListMLHUIMiner] = {}
        self.mapItemsetToUtilityList: Dict[Tuple[int, ...], UtilityListMLHUIMiner] = {}
        self.mapItemToAncestor: Dict[int, List[int]] = {}

        self.transactionTU: List[float] = []
        self._storeResult: Set[Tuple[int, ...]] = set()
        self._writer = None

    @staticmethod
    def _skip(line: str) -> bool:
        return (not line) or line[0] in ("#", "@", "%")

    def _maxLevel(self) -> int:
        return max(self.mapItemToLevel.values()) if self.mapItemToLevel else 0

    def _compareItems(self, item1: int, item2: int) -> int:
        compare = self.mapItemToGWU.get(item1, 0.0) - self.mapItemToGWU.get(item2, 0.0)
        if abs(compare) < 0.01:
            return item1 - item2
        return 1 if compare > 0 else -1

    def runAlgorithm(self, inputTransactions: str, inputTaxonomy: str, output: str, min_utility: float) -> None:
        MemoryLogger.getInstance().reset()
        self.startTimeStamp = time.time()

        self._writer = open(output, "w", encoding="utf-8")

        # ---------- Load taxonomy (child,parent) ----------
        self.mapItemToGeneralizedItem.clear()
        with open(inputTaxonomy, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line[0] in ("#", "@"):
                    continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 2:
                    continue
                child = int(parts[0])
                parent = int(parts[1])
                self.mapItemToGeneralizedItem[child] = parent

        # Build ancestor chain reliably
        def build_chain(item: int) -> List[int]:
            chain = [item]
            cur = item
            seen = {item}
            while cur in self.mapItemToGeneralizedItem:
                p = self.mapItemToGeneralizedItem[cur]
                if p in seen:
                    break
                chain.append(p)
                seen.add(p)
                cur = p
            return chain

        # ---------- First scan: GWU + ancestors + levels ----------
        self.mapItemToGWU.clear()
        self.mapItemToLevel.clear()
        self.mapItemToAncestor.clear()

        tidCount = 0
        with open(inputTransactions, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if self._skip(line) or line[0] in ("#", "@"):
                    continue
                split = line.split(":")
                items = split[0].split()
                transactionUtility = float(split[1])

                ancestantExist: Set[int] = set()

                for s in items:
                    item = int(s)

                    self.mapItemToGWU[item] = self.mapItemToGWU.get(item, 0.0) + transactionUtility

                    if item not in self.mapItemToAncestor:
                        chain = build_chain(item)  # [item, parent, ...]
                        # update GWU for ancestors once per transaction
                        for anc in chain[1:]:
                            if anc not in ancestantExist:
                                ancestantExist.add(anc)
                                self.mapItemToGWU[anc] = self.mapItemToGWU.get(anc, 0.0) + transactionUtility

                        # levels like Java (k downwards)
                        k = len(chain)
                        for j, node in enumerate(chain):
                            self.mapItemToLevel[node] = k - j

                        # store ancestor lists like Java loop
                        for idx, node in enumerate(chain):
                            self.mapItemToAncestor[node] = chain[idx + 1 :]

                    else:
                        for anc in self.mapItemToAncestor.get(item, []):
                            if anc not in ancestantExist:
                                ancestantExist.add(anc)
                                self.mapItemToGWU[anc] = self.mapItemToGWU.get(anc, 0.0) + transactionUtility

                tidCount += 1

        # ---------- Create utility lists for items ----------
        self.mapItemToUtilityList.clear()
        listOfTaxUtilityLists: List[UtilityListMLHUIMiner] = []

        for item, gwu in self.mapItemToGWU.items():
            if gwu >= min_utility:
                ul = UtilityListMLHUIMiner([item])
                self.mapItemToUtilityList[item] = ul
                listOfTaxUtilityLists.append(ul)
            else:
                for anc in self.mapItemToAncestor.get(item, []):
                    if self.mapItemToGWU.get(anc, 0.0) >= min_utility:
                        ul = UtilityListMLHUIMiner([item])
                        self.mapItemToUtilityList[item] = ul
                        listOfTaxUtilityLists.append(ul)
                        break

        # sort high GWU items by compareItems behavior (GWU then lexical)
        listOfTaxUtilityLists.sort(key=lambda ul: (self.mapItemToGWU.get(ul.item[0], 0.0), ul.item[0]))

        # ---------- Second scan: build utility lists ----------
        self.transactionTU = [0.0] * tidCount
        tid = 0
        with open(inputTransactions, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if self._skip(line):
                    continue

                split = line.split(":")
                items = split[0].split()
                self.transactionTU[tid] = float(split[1])
                utilityValues = split[2].split()

                revised: List[Tuple[int, float]] = []
                remainingUtility = 0.0

                for it_s, u_s in zip(items, utilityValues):
                    it = int(it_s)
                    u = float(u_s)

                    keep = False
                    if self.mapItemToGWU.get(it, 0.0) >= min_utility:
                        keep = True
                    else:
                        for anc in self.mapItemToAncestor.get(it, []):
                            if self.mapItemToGWU.get(anc, 0.0) >= min_utility:
                                keep = True
                                break

                    if keep:
                        revised.append((it, u))
                        remainingUtility += u

                revised.sort(key=lambda p: (self.mapItemToGWU.get(p[0], 0.0), p[0]))

                ancestorSeen: Set[int] = set()
                firstChildRemaining: Dict[int, float] = {}

                for (it, u) in revised:
                    remainingUtility -= u

                    ul_item = self.mapItemToUtilityList.get(it)
                    if ul_item is not None:
                        ul_item.addElement(ElementMLHUIMiner(tid, u, remainingUtility))

                    for anc in self.mapItemToAncestor.get(it, []):
                        ul_parent = self.mapItemToUtilityList.get(anc)
                        if ul_parent is None:
                            continue

                        if anc not in ancestorSeen:
                            ancestorSeen.add(anc)
                            firstChildRemaining[anc] = remainingUtility
                            ul_parent.addElement(ElementMLHUIMiner(tid, u, firstChildRemaining[anc]))
                        else:
                            ul_parent.addElement(ElementMLHUIMiner(tid, u, -u))

                tid += 1

        # ---------- Build lists per level ----------
        max_level = self._maxLevel()
        level_lists: List[List[UtilityListMLHUIMiner]] = []
        for level in range(1, max_level + 1):
            lvl: List[UtilityListMLHUIMiner] = []
            for item, gwu in self.mapItemToGWU.items():
                if gwu >= min_utility and self.mapItemToLevel.get(item, 0) == level:
                    ul = self.mapItemToUtilityList.get(item)
                    if ul is not None:
                        lvl.append(ul)
            lvl.sort(key=lambda ul: (self.mapItemToGWU.get(ul.item[0], 0.0), ul.item[0]))
            level_lists.append(lvl)

        print("algorithm is running......")
        MemoryLogger.getInstance().checkMemory()

        # ---------- Mine recursively ----------
        for lvl in level_lists:
            self._mlhuiminer(pUL=None, ULs=lvl, minUtility=min_utility)

        MemoryLogger.getInstance().checkMemory()

        self._writer.close()
        self._writer = None

        self.endTimeStamp = time.time()
        print("finished......")

    def _findElementWithTID(self, tulist: UtilityListMLHUIMiner, tid: int) -> Optional[ElementMLHUIMiner]:
        # Binary search assumes elements roughly ordered by tid;
        # Java's addElement can merge and keeps insertion order,
        # but since we process transactions tid in increasing order, this holds.
        lst = tulist.elements
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

    def _construct(self, P: Optional[UtilityListMLHUIMiner], py: UtilityListMLHUIMiner, px: UtilityListMLHUIMiner) -> UtilityListMLHUIMiner:
        # union preserving insertion order like LinkedHashSet(addAll(py), addAll(px))
        seen: Set[int] = set()
        itemOfPXY: List[int] = []
        for v in py.item:
            if v not in seen:
                seen.add(v)
                itemOfPXY.append(v)
        for v in px.item:
            if v not in seen:
                seen.add(v)
                itemOfPXY.append(v)

        pxyUL = UtilityListMLHUIMiner(itemOfPXY)

        for ex in px.elements:
            ey = self._findElementWithTID(py, ex.tid)
            if ey is None:
                continue

            if P is None:
                eXY = ElementMLHUIMiner(ex.tid, ex.iutils + ey.iutils, ey.rutils)
                pxyUL.addElement(eXY)
            else:
                e = self._findElementWithTID(P, ex.tid)
                if e is not None:
                    eXY = ElementMLHUIMiner(ex.tid, ex.iutils + ey.iutils - e.iutils, ey.rutils)
                    pxyUL.addElement(eXY)

        return pxyUL

    def _mlhuiminer(self, pUL: Optional[UtilityListMLHUIMiner], ULs: List[UtilityListMLHUIMiner], minUtility: float) -> None:
        for i in range(len(ULs)):
            X = ULs[i]

            if X.sumIutils >= minUtility:
                self._writeOut(X.item, X.sumIutils)

            exULs: List[UtilityListMLHUIMiner] = []
            for j in range(i + 1, len(ULs)):
                Y = ULs[j]
                temp = self._construct(pUL, X, Y)
                if temp is not None:
                    exULs.append(temp)

            # Java pruning is commented out, so always recurse
            if exULs:
                self._mlhuiminer(X, exULs, minUtility)

        MemoryLogger.getInstance().checkMemory()

    def _writeOut(self, item: List[int], utility: float) -> None:
        key = tuple(item)
        if key in self._storeResult:
            return

        self._storeResult.add(key)
        self.huiCount += 1

        line = " ".join(str(x) for x in item) + " #UTIL: " + str(utility)
        self._writer.write(line + "\n")

    def printStatistics(self) -> None:
        print("=============  MLHUIMiner ALGORITHM - SPMF 0.97e - STATS =============")
        total_ms = int((self.endTimeStamp - self.startTimeStamp) * 1000.0)
        print(f" Total time ~ {total_ms} ms")
        print(f" Memory ~ {MemoryLogger.getInstance().getMaxMemory()} MB")
        print(f" High-utility itemsets count : {self.huiCount}")
        print("===================================================")


# -----------------------------
# MainTestMLHUIMiner (Python)
# -----------------------------
def main() -> None:
    inputTransaction = "transaction_CLHMiner.txt"
    inputTaxonomy = "taxonomy_CLHMiner.txt"
    minUtil = 40.0

    algo = AlgoMLHUIMiner()
    algo.runAlgorithm(inputTransaction, inputTaxonomy, "output_py.txt", minUtil)
    algo.printStatistics()


if __name__ == "__main__":
    main()
