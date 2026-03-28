import heapq
from collections import defaultdict

# -----------------------------
# Element (same as Java)
# -----------------------------
class Element:
    def __init__(self, tid, iutils, rutils):
        self.tid = tid
        self.iutils = iutils
        self.rutils = rutils


# -----------------------------
# UtilityList (same as Java)
# -----------------------------
class UtilityList:
    def __init__(self, item):
        self.item = item
        self.sumIutils = 0
        self.sumRutils = 0
        self.elements = []

    def add_element(self, element):
        self.sumIutils += element.iutils
        self.sumRutils += element.rutils
        self.elements.append(element)

    def get_utils(self):
        return self.sumIutils


# -----------------------------
# PatternTHUI (same logic)
# -----------------------------
class PatternTHUI:
    def __init__(self, prefix, item, utility):
        self.prefix = prefix
        self.item = item
        self.utility = utility

    def __lt__(self, other):
        return self.utility < other.utility


# -----------------------------
# THUI Algorithm
# -----------------------------
class THUI:

    def __init__(self, k):
        self.k = k
        self.minUtility = 0
        self.kPatterns = []

    def run(self, input_file, output_file):

        # -----------------------------
        # First DB scan (compute TWU)
        # -----------------------------
        mapItemToTWU = defaultdict(int)
        RIU = defaultdict(int)

        transactions = []

        with open(input_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                split = line.split(":")
                items = list(map(int, split[0].split()))
                tu = int(split[1])
                utils = list(map(int, split[2].split()))

                transactions.append((items, utils))

                for item in items:
                    mapItemToTWU[item] += tu

                for i in range(len(items)):
                    RIU[items[i]] += utils[i]

        # -----------------------------
        # Raise threshold by RIU
        # -----------------------------
        sorted_riu = sorted(RIU.values(), reverse=True)
        if len(sorted_riu) >= self.k:
            self.minUtility = sorted_riu[self.k - 1]
        else:
            self.minUtility = 0

        # -----------------------------
        # Build Utility Lists
        # -----------------------------
        items = [item for item in mapItemToTWU if mapItemToTWU[item] >= self.minUtility]
        items.sort(key=lambda x: (mapItemToTWU[x], x))

        utility_lists = {item: UtilityList(item) for item in items}

        for tid, (trans_items, trans_utils) in enumerate(transactions):

            revised = []
            for i in range(len(trans_items)):
                if trans_items[i] in utility_lists:
                    revised.append((trans_items[i], trans_utils[i]))

            revised.sort(key=lambda x: (mapItemToTWU[x[0]], x[0]))

            remaining_utility = 0
            for item, util in reversed(revised):
                element = Element(tid, util, remaining_utility)
                utility_lists[item].add_element(element)
                remaining_utility += util

        # -----------------------------
        # Recursive mining
        # -----------------------------
        self.search([], None, list(utility_lists.values()))

        # -----------------------------
        # Write output (same order as Java)
        # -----------------------------
        patterns = sorted(self.kPatterns, key=lambda x: x.utility)

        with open(output_file, "w") as f:
            for p in patterns:
                f.write(f"{p.prefix} #UTIL: {p.utility}\n")

        print("Execution finished successfully.")

    # -----------------------------
    # Recursive Search
    # -----------------------------
    def search(self, prefix, pUL, ULs):

        for i in range(len(ULs)):
            X = ULs[i]

            if X.sumIutils >= self.minUtility:
                self.save(prefix, X)

            if X.sumIutils + X.sumRutils >= self.minUtility:

                exULs = []
                for j in range(i + 1, len(ULs)):
                    Y = ULs[j]
                    newUL = self.construct(pUL, X, Y)
                    if newUL is not None:
                        exULs.append(newUL)

                newPrefix = prefix + [X.item]
                self.search(newPrefix, X, exULs)

    # -----------------------------
    # Construct utility list
    # -----------------------------
    def construct(self, P, px, py):

        pxyUL = UtilityList(py.item)
        ei = 0
        ej = 0

        while ei < len(px.elements) and ej < len(py.elements):

            ex = px.elements[ei]
            ey = py.elements[ej]

            if ex.tid == ey.tid:

                if P is None:
                    new_iutils = ex.iutils + ey.iutils
                else:
                    e = next((e for e in P.elements if e.tid == ex.tid), None)
                    if e is None:
                        ei += 1
                        ej += 1
                        continue
                    new_iutils = ex.iutils + ey.iutils - e.iutils

                element = Element(ex.tid, new_iutils, ey.rutils)
                pxyUL.add_element(element)

                ei += 1
                ej += 1

            elif ex.tid < ey.tid:
                ei += 1
            else:
                ej += 1

        if pxyUL.sumIutils == 0:
            return None

        return pxyUL

    # -----------------------------
    # Save pattern (Top-k logic)
    # -----------------------------
    def save(self, prefix, X):

        pattern_str = " ".join(map(str, prefix + [X.item]))
        pattern = PatternTHUI(pattern_str, X.item, X.sumIutils)

        heapq.heappush(self.kPatterns, pattern)

        if len(self.kPatterns) > self.k:
            heapq.heappop(self.kPatterns)

        if len(self.kPatterns) == self.k:
            self.minUtility = self.kPatterns[0].utility


# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":

    input_file = "DB_Utility.txt"
    output_file = "outputs.txt"
    k = 8

    algo = THUI(k)
    algo.run(input_file, output_file)