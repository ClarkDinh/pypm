# ============================================================
# UFH Algorithm - Python Implementation
# ============================================================

import time
from collections import defaultdict

# ============================================================
# Data Structures
# ============================================================

class Element:
    def __init__(self, tid, iutils, rutils):
        self.tid = tid
        self.iutils = iutils
        self.rutils = rutils


class UtilityList:
    def __init__(self, item):
        self.item = item
        self.elements = []
        self.sumIutils = 0
        self.sumRutils = 0

    def addElement(self, e):
        self.elements.append(e)
        self.sumIutils += e.iutils
        self.sumRutils += e.rutils


class Transaction:
    def __init__(self, items, utils, tu):
        self.items = items
        self.utilities = utils
        self.transactionUtility = tu


class Dataset:
    def __init__(self, path):
        self.transactions = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in "#%@":
                    continue
                left, tu, right = line.split(":")
                items = list(map(int, left.split()))
                utils = list(map(int, right.split()))
                self.transactions.append(
                    Transaction(items, utils, int(tu))
                )

    def getTransactions(self):
        return self.transactions


# ============================================================
# UFH Algorithm
# ============================================================

class AlgoUFH:
    def __init__(self):
        self.min_utility = 0
        self.huiCount = 0
        self.dataset = None
        self.output = None
        self.start = 0
        self.end = 0

    # --------------------------------------------------------
    # Main algorithm
    # --------------------------------------------------------

    def runAlgorithm(self, input_file, output_file, min_utility):
        self.start = time.time()
        self.min_utility = min_utility
        self.huiCount = 0

        dataset = Dataset(input_file)
        self.dataset = dataset.getTransactions()

        # ---- TWU calculation ----
        mapItemToTWU = defaultdict(int)
        for t in self.dataset:
            for item in t.items:
                mapItemToTWU[item] += t.transactionUtility

        # ---- Build initial utility lists ----
        mapItemToUL = {}
        for item, twu in mapItemToTWU.items():
            if twu >= min_utility:
                mapItemToUL[item] = UtilityList(item)

        # ---- Populate utility lists ----
        for tid, t in enumerate(self.dataset):
            ru = t.transactionUtility
            for item, util in zip(t.items, t.utilities):
                ru -= util
                if item in mapItemToUL:
                    mapItemToUL[item].addElement(
                        Element(tid, util, ru)
                    )

        # ---- Sort by TWU (ascending) ----
        items = sorted(mapItemToUL.keys(), key=lambda x: mapItemToTWU[x])
        ULs = [mapItemToUL[i] for i in items]

        self.output = open(output_file, "w")

        # ---- Start mining ----
        self._fhm([], None, ULs)

        self.output.close()
        self.end = time.time()

    # --------------------------------------------------------
    # Recursive mining (UFH / FHM core)
    # --------------------------------------------------------

    def _fhm(self, prefix, pUL, ULs):
        for i in range(len(ULs)):
            X = ULs[i]
            new_prefix = prefix + [X.item]

            # ---- Exact utility (UFH correction step) ----
            exact_util = self._computeExactUtility(new_prefix)
            if exact_util >= self.min_utility:
                self._writeOut(new_prefix, exact_util)

            # ---- NO sumIutils + sumRutils pruning in UFH ----
            exULs = []
            for j in range(i + 1, len(ULs)):
                Y = ULs[j]
                XY = self._construct(pUL, X, Y)
                if XY:
                    exULs.append(XY)
            if exULs:
                self._fhm(new_prefix, X, exULs)


    # --------------------------------------------------------
    # Utility-list join (Java construct())
    # --------------------------------------------------------

    def _construct(self, P, px, py):
        ul = UtilityList(py.item)
        ey = {e.tid: e for e in py.elements}

        if P is None:
            for ex in px.elements:
                if ex.tid in ey:
                    e = ey[ex.tid]
                    ul.addElement(
                        Element(ex.tid,
                                ex.iutils + e.iutils,
                                e.rutils)
                    )
        else:
            ep = {e.tid: e for e in P.elements}
            for ex in px.elements:
                if ex.tid in ey and ex.tid in ep:
                    e = ey[ex.tid]
                    p = ep[ex.tid]
                    ul.addElement(
                        Element(ex.tid,
                                ex.iutils + e.iutils - p.iutils,
                                e.rutils)
                    )

        return ul if ul.elements else None

    # --------------------------------------------------------
    # Exact utility recomputation (CRITICAL for UFH)
    # --------------------------------------------------------

    def _computeExactUtility(self, itemset):
        itemset = set(itemset)
        total = 0

        for t in self.dataset:
            if itemset.issubset(t.items):
                util = 0
                for it, u in zip(t.items, t.utilities):
                    if it in itemset:
                        util += u
                total += util

        return total

    # --------------------------------------------------------
    # Output
    # --------------------------------------------------------

    def _writeOut(self, itemset, utility):
        self.huiCount += 1
        self.output.write(
            " ".join(map(str, itemset)) +
            " #UTIL: " + str(utility) + "\n"
        )

    # --------------------------------------------------------
    # Stats
    # --------------------------------------------------------

    def printStats(self):
        print("============= UFH STATS =============")
        print(f"Total time ~ {(self.end - self.start)*1000:.2f} ms")
        print(f"HUI count : {self.huiCount}")
        print("====================================")


# ============================================================
# MAIN (ONLY ONCE, MUST BE LAST)
# ============================================================

if __name__ == "__main__":
    INPUT = "DB_Utility.txt"
    OUTPUT = "output_UFH.txt"
    MIN_UTILITY = 30

    algo = AlgoUFH()
    algo.runAlgorithm(INPUT, OUTPUT, MIN_UTILITY)
    algo.printStats()
