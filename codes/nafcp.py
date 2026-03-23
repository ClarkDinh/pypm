import os
import math
from collections import defaultdict

# ============================
# MemoryLogger (Singleton)
# ============================

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
            mem = process.memory_info().rss / 1024 / 1024
        except:
            import resource
            mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        if mem > self.maxMemory:
            self.maxMemory = mem
        return mem


# ============================
# Helper Classes
# ============================

class IntegerByRef:
    def __init__(self, value=0):
        self.value = value


class Item:
    def __init__(self, name=0, frequency=0):
        self.name = name
        self.frequency = frequency


class Product:
    def __init__(self):
        self.items = []

    def Sort(self):
        self.items.sort(key=lambda x: (-x.frequency, x.name))


class ProductDb:
    def __init__(self):
        self.products = []


class NC:
    def __init__(self):
        self.preOrder = 0
        self.postOrder = 0
        self.frequency = 0


class WPPC_Node:
    def __init__(self):
        self.item = Item()
        self.childNodes = []
        self.preOrder = 0
        self.postOrder = 0


class FCI:
    def __init__(self):
        self.items = []
        self.frequency = 0
        self.nCs = []

    def __str__(self):
        return " ".join(str(i) for i in self.items) + " #SUP: " + str(self.frequency)


# ============================
# AlgoNAFCP
# ============================

class AlgoNAFCP:

    def __init__(self):
        self.pre = 0
        self.post = 0

    # -------- File Reading --------
    def readFile(self, filename):
        pdb = ProductDb()
        with open(filename, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in "#%@":
                    continue
                p = Product()
                for it in line.split():
                    p.items.append(Item(int(it)))
                pdb.products.append(p)
        return pdb

    # -------- Tree Insert --------
    def insertTree(self, p, root):
        if not p.items:
            return
        i = p.items.pop(0)
        for c in root.childNodes:
            if c.item.name == i.name:
                c.item.frequency += 1
                self.insertTree(p, c)
                return
        n = WPPC_Node()
        n.item = i
        n.item.frequency = 1
        root.childNodes.append(n)
        self.insertTree(p, n)

    # -------- Pre/Post Order --------
    def generateOrder(self, root):
        root.preOrder = self.pre
        self.pre += 1
        for c in root.childNodes:
            self.generateOrder(c)
        root.postOrder = self.post
        self.post += 1

    def generateNCSets(self, root):
        if root.item.name != -1:
            idx = self.hashI1[root.item.name]
            nc = NC()
            nc.preOrder = root.preOrder
            nc.postOrder = root.postOrder
            nc.frequency = root.item.frequency
            self.fcis_1[idx].nCs.append(nc)
        for c in root.childNodes:
            self.generateNCSets(c)

    # -------- Core Logic --------
    def N_list_check(self, a, b):
        i = j = 0
        while j < len(b) and i < len(a):
            if a[i].preOrder < b[j].preOrder and a[i].postOrder > b[j].postOrder:
                j += 1
            else:
                i += 1
        return j == len(b)

    # ✅ Java-exact union (NO set)
    def itemUnion(self, a, b):
        result = []
        i = j = 0
        while i < len(a) and j < len(b):
            if a[i] > b[j]:
                result.append(a[i])
                i += 1
            elif a[i] == b[j]:
                result.append(a[i])
                i += 1
                j += 1
            else:
                result.append(b[j])
                j += 1
        while i < len(a):
            result.append(a[i])
            i += 1
        while j < len(b):
            result.append(b[j])
            j += 1
        return result

    # ✅ Java-exact NC combination
    def ncCombination(self, a, b, totalFrequency, g):
        result = []
        i = j = 0
        subFrequency = totalFrequency

        while i < len(a) and j < len(b):
            if a[i].preOrder < b[j].preOrder:
                if a[i].postOrder > b[j].postOrder:
                    if result and result[-1].preOrder == a[i].preOrder:
                        result[-1].frequency += b[j].frequency
                    else:
                        nc = NC()
                        nc.preOrder = a[i].preOrder
                        nc.postOrder = a[i].postOrder
                        nc.frequency = b[j].frequency
                        result.append(nc)
                    g.value += b[j].frequency
                    j += 1
                else:
                    subFrequency -= a[i].frequency
                    i += 1
            else:
                subFrequency -= b[j].frequency
                j += 1

            if subFrequency < self.minSupport:
                return None

        return result

    def subsetCheck(self, a, b):
        if len(a) > len(b):
            return False
        i = j = 0
        while i < len(a) and j < len(b):
            if a[i] > b[j]:
                return False
            elif a[i] == b[j]:
                i += 1
                j += 1
            else:
                j += 1
        return i == len(a)

    def subsumptionCheck(self, f):
        arr = self.hashFCIs.get(f.frequency)
        if arr:
            for idx in arr:
                if self.subsetCheck(f.items, self.fcis[idx].items):
                    return True
        return False

    # ✅ FINAL CORRECT findFCIs
    def findFCIs(self, Is):
        i = len(Is) - 1
        while i >= 0:
            IsI = Is[i]
            FCIs_Next = []

            j = i - 1
            while j >= 0:
                IsJ = Is[j]

                if self.N_list_check(IsJ.nCs, IsI.nCs):
                    IsI.items = self.itemUnion(IsI.items, IsJ.items)

                    if IsI.frequency == IsJ.frequency:
                        Is.pop(j)
                        i -= 1
                    else:
                        for fci in FCIs_Next:
                            fci.items = self.itemUnion(fci.items, IsJ.items)

                    j -= 1
                    continue

                f = FCI()
                f.items = self.itemUnion(IsI.items, IsJ.items)
                g = IntegerByRef(0)
                f.nCs = self.ncCombination(IsJ.nCs, IsI.nCs, IsJ.frequency + IsI.frequency, g)

                if g.value >= self.minSupport:
                    f.frequency = g.value
                    FCIs_Next.insert(0, f)

                j -= 1

            if not self.subsumptionCheck(IsI):
                self.fcis.append(IsI)
                self.writer.write(str(IsI) + "\n")
                self.hashFCIs.setdefault(IsI.frequency, []).append(len(self.fcis) - 1)

            self.findFCIs(FCIs_Next)
            i -= 1

    # -------- Run Algorithm --------
    def runAlgorithm(self, filename, minSupport, output):
        MemoryLogger.getInstance().reset()
        self.writer = open(output, "w", newline="\n")

        self.fcis_1 = []
        self.fcis = []
        self.hashI1 = {}
        self.hashFCIs = {}
        self.pre = 0
        self.post = 0

        pdb = self.readFile(filename)
        self.minSupport = int(math.ceil(len(pdb.products) * minSupport))

        itemCount = defaultdict(int)
        for p in pdb.products:
            for it in p.items:
                itemCount[it.name] += 1

        for k, v in itemCount.items():
            if v >= self.minSupport:
                f = FCI()
                f.items.append(k)
                f.frequency = v
                self.fcis_1.append(f)

        self.fcis_1.sort(key=lambda x: (-x.frequency, x.items[0]))

        for idx, f in enumerate(self.fcis_1):
            self.hashI1[f.items[0]] = idx

        root = WPPC_Node()
        root.item.name = -1

        for p in pdb.products:
            p.items = [it for it in p.items if it.name in self.hashI1]
            for it in p.items:
                it.frequency = self.fcis_1[self.hashI1[it.name]].frequency
            p.Sort()
            self.insertTree(p, root)

        self.generateOrder(root)
        self.generateNCSets(root)
        self.findFCIs(self.fcis_1)

        self.writer.close()
        MemoryLogger.getInstance().checkMemory()


# ============================
# Main (ONLY itemsets output)
# ============================

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(BASE_DIR, "contextPasquier99.txt")
    output_file = os.path.join(BASE_DIR, "nafcp_outputs.txt")

    minsup = 0.6   # change freely

    algo = AlgoNAFCP()
    algo.runAlgorithm(input_file, minsup, output_file)
