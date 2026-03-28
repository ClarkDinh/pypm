import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

INPUT_FILE = os.path.join(BASE_DIR, "contextHAUIMiner.txt")
OUTPUT_FILE = os.path.join(BASE_DIR, "outputs.txt")

DELTA = 24   # change threshold here

# =========================
# DATA STRUCTURES
# =========================

class MAUEntry:
    def __init__(self, tid, utility, rmu, remu):
        self.tid = tid
        self.utility = utility
        self.rmu = rmu
        self.remu = remu


class MAUList:
    def __init__(self, item):
        self.item = item
        self.sumutils = 0
        self.sumOfRemu = 0
        self.sumOfRmu = 0
        self.entries = []

    def add_element(self, e):
        self.sumutils += e.utility
        self.sumOfRmu += e.rmu
        self.sumOfRemu += e.remu
        self.entries.append(e)


# =========================
# ALGORITHM
# =========================

class EHAUPM:

    def __init__(self):
        self.items2auub = {}
        self.EAUCM = {}
        self.nhauis = 0

    def compare_items(self, item1, item2):
        compare = self.items2auub[item1] - self.items2auub[item2]
        return item1 - item2 if compare == 0 else compare

    # ---------------------------------

    def run_algorithm(self, db_path, output_path, delta):

        start = time.time()

        self.items2auub = {}
        self.EAUCM = {}
        self.nhauis = 0

        # FIRST PASS (AUUB)
        database = []

        with open(db_path, "r") as f:
            for line in f:
                if not line.strip() or line[0] in "#%@":
                    continue

                parts = line.strip().split(":")
                items = list(map(int, parts[0].split()))
                utils = list(map(int, parts[2].split()))
                maxU = max(utils)

                for item in items:
                    self.items2auub[item] = \
                        self.items2auub.get(item, 0) + maxU

                database.append((items, utils))

        minUtility = delta

        # CREATE MAU LISTS
        listOfMAULists = []
        mapItemToMAUList = {}

        for item, auub in self.items2auub.items():
            if auub >= minUtility:
                ulist = MAUList(item)
                mapItemToMAUList[item] = ulist
                listOfMAULists.append(ulist)

        listOfMAULists.sort(
            key=lambda x: (self.items2auub[x.item], x.item)
        )

        # SECOND PASS
        tid = 0
        for items, utils in database:

            revised = []
            maxU = 0

            for i in range(len(items)):
                if self.items2auub[items[i]] >= minUtility:
                    revised.append((items[i], utils[i]))
                    maxU = max(maxU, utils[i])

            revised.sort(
                key=lambda x: (self.items2auub[x[0]], x[0])
            )

            remu = 0
            rmu = 0

            for item, utility in reversed(revised):
                rmu = max(rmu, utility)

                entry = MAUEntry(tid, utility, rmu, remu)
                mapItemToMAUList[item].add_element(entry)

                remu = max(remu, utility)

            # Build EAUCM
            for i in range(len(revised)):
                item_i = revised[i][0]
                if item_i not in self.EAUCM:
                    self.EAUCM[item_i] = {}
                for j in range(i+1, len(revised)):
                    item_j = revised[j][0]
                    self.EAUCM[item_i][item_j] = \
                        self.EAUCM[item_i].get(item_j, 0) + maxU

            tid += 1

        # SEARCH
        self.writer = open(output_path, "w")
        self.search([], 0, None, listOfMAULists, minUtility)
        self.writer.close()

        end = time.time()

        print("============= EHAUPM PYTHON =============")
        print("Total time ~", round((end-start)*1000,2), "ms")
        print("High-utility itemsets count:", self.nhauis)
        print("==========================================")

    # ---------------------------------

    def search(self, prefix, prefixLength, ULOfPxy, ULs, minUtility):

        for i in range(len(ULs)):

            X = ULs[i]
            avg = X.sumutils / (prefixLength+1)

            if avg >= minUtility:
                self.nhauis += 1
                self.write_out(prefix, prefixLength, X.item, avg)

            if (avg + X.sumOfRemu) < minUtility:
                continue

            if X.sumOfRmu >= minUtility:

                extensions = []

                for j in range(i+1, len(ULs)):
                    Y = ULs[j]

                    if X.item in self.EAUCM:
                        if self.EAUCM[X.item].get(Y.item,0) < minUtility:
                            continue

                    pxy = self.construct_opt(
                        prefixLength+1, ULOfPxy, X, Y, minUtility
                    )

                    if pxy:
                        extensions.append(pxy)

                self.search(prefix+[X.item],
                            prefixLength+1,
                            X,
                            extensions,
                            minUtility)

    # ---------------------------------

    def construct_opt(self, prefixLen, P, Px, Py, minUtility):

        pxy = MAUList(Py.item)

        sumOfRmu = Px.sumOfRmu
        sumOfRemu = Px.sumutils/prefixLen + Px.sumOfRemu

        idxPx = 0
        idxPy = 0

        while idxPx < len(Px.entries) and idxPy < len(Py.entries):

            ex = Px.entries[idxPx]
            ey = Py.entries[idxPy]

            if ex.tid == ey.tid:

                if P:
                    e = next((e for e in P.entries if e.tid==ex.tid), None)
                    if e:
                        newUtil = ex.utility + ey.utility - e.utility
                        pxy.add_element(
                            MAUEntry(ex.tid, newUtil, ex.rmu, ey.remu)
                        )
                else:
                    pxy.add_element(
                        MAUEntry(ex.tid,
                                 ex.utility + ey.utility,
                                 ex.rmu,
                                 ey.remu)
                    )
                idxPx += 1
                idxPy += 1

            elif ex.tid > ey.tid:
                idxPy += 1
            else:
                sumOfRmu -= ex.rmu
                sumOfRemu -= (ex.utility/prefixLen + ex.remu)
                if min(sumOfRmu, sumOfRemu) < minUtility:
                    return None
                idxPx += 1

        return pxy if pxy.entries else None

    # ---------------------------------

    def write_out(self, prefix, prefixLength, item, utility):

        line = ""
        for p in prefix:
            line += str(p) + " "
        line += str(item)
        line += " #AUTIL: "
        line += str(utility)

        self.writer.write(line + "\n")


# =========================
# MAIN
# =========================

if __name__ == "__main__":

    miner = EHAUPM()
    miner.run_algorithm(INPUT_FILE, OUTPUT_FILE, DELTA)