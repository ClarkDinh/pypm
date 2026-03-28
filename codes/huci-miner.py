import os
import time
import tracemalloc
from functools import total_ordering


class AlgoFHIM_and_HUCI:
    class Pair:
        def __init__(self):
            self.item = 0
            self.utility = 0

        def __str__(self):
            return "[" + str(self.item) + "," + str(self.utility) + "]"

    def __init__(self):
        self.maxMemory = 0.0
        self.startTimestamp = 0
        self.endTimestamp = 0
        self.hui = 0
        self.candidate = 0
        self.chui = 0
        self.ghui = 0
        self.maxlength = 0
        self.tableHUI = None
        self.tableHUCI = None
        self.minUtility = 0
        self.input = None
        self.writer = None
        self.algo = 0
        self.HG = None
        self.mapFMAP = {}
        self.mapItemToUtilityList = {}
        self.mapLLFMAP = {}
        self.dontOutputClosedItemsets = False
        self.dontOutputGeneratorItemsets = False
        if not tracemalloc.is_tracing():
            tracemalloc.start()

    def setDontOutputClosedItemsets(self, dont_output_closed_itemsets):
        self.dontOutputClosedItemsets = dont_output_closed_itemsets

    def setDontOutputGeneratorItemsets(self, dont_output_generator_itemsets):
        self.dontOutputGeneratorItemsets = dont_output_generator_itemsets

    def runAlgorithmFHIM(self, input_path, output, min_util):
        self.runAlgo(input_path, output, min_util, 0)

    def runAlgorithmHUCIMiner(self, input_path, output, min_uti):
        return self.runAlgo(input_path, output, min_uti, 1)

    def runAlgo(self, input_path, output, min_utility, alg):
        self.maxMemory = 0.0
        self.ghui = 0
        self.chui = 0
        self.hui = 0
        self.candidate = 0
        self.maxlength = 0
        self.startTimestamp = int(time.time() * 1000)

        if output is not None:
            self.writer = open(output, "w", encoding="utf-8")
        else:
            self.writer = None

        MemoryLogger.getInstance().reset()
        self.algo = alg
        map_item_to_twu = {}
        self.mapFMAP = {}
        self.HG = []
        self.tableHUI = HUTable()
        self.tableHUCI = HUClosedTable()

        my_input = None
        this_line = None
        try:
            my_input = open(input_path, "r", encoding="utf-8")
            while True:
                this_line = my_input.readline()
                if this_line == "":
                    break
                this_line = this_line.strip()
                if (
                    this_line == ""
                    or this_line[0] == "#"
                    or this_line[0] == "%"
                    or this_line[0] == "@"
                ):
                    continue
                split = this_line.split(":")
                items = split[0].split(" ")
                transaction_utility = int(split[1])
                for token in items:
                    item = int(token)
                    twu = map_item_to_twu.get(item)
                    twu = transaction_utility if twu is None else twu + transaction_utility
                    map_item_to_twu[item] = twu
        except Exception:
            pass
        finally:
            if my_input is not None:
                my_input.close()

        self.minUtility = min_utility
        print("Absolute utility threshold = " + str(self.minUtility))

        list_of_utility_lists = []
        self.mapItemToUtilityList = {}
        for item in map_item_to_twu.keys():
            if map_item_to_twu[item] >= min_utility:
                ulist = UtilityList(item)
                self.mapItemToUtilityList[item] = ulist
                list_of_utility_lists.append(ulist)

        list_of_utility_lists.sort(key=lambda ul: (map_item_to_twu[ul.item], ul.item))

        try:
            my_input = open(input_path, "r", encoding="utf-8")
            tid = 0
            while True:
                this_line = my_input.readline()
                if this_line == "":
                    break
                this_line = this_line.strip()
                if (
                    this_line == ""
                    or this_line[0] == "#"
                    or this_line[0] == "%"
                    or this_line[0] == "@"
                ):
                    continue

                split = this_line.split(":")
                items = split[0].split(" ")
                utility_values = split[2].split(" ")
                remaining_utility = 0
                new_twu = 0
                revised_transaction = []
                for i in range(len(items)):
                    pair = AlgoFHIM_and_HUCI.Pair()
                    pair.item = int(items[i])
                    pair.utility = int(utility_values[i])
                    if map_item_to_twu.get(pair.item, 0) >= min_utility:
                        revised_transaction.append(pair)
                        remaining_utility += pair.utility
                        new_twu += pair.utility

                revised_transaction.sort(key=lambda p: (map_item_to_twu[p.item], p.item))

                for i in range(len(revised_transaction)):
                    pair = revised_transaction[i]
                    remaining_utility = remaining_utility - pair.utility
                    utility_list_of_item = self.mapItemToUtilityList[pair.item]
                    element = Element(tid, pair.utility, remaining_utility)
                    utility_list_of_item.addElement(element)

                    map_fmap_item = self.mapFMAP.get(pair.item)
                    if map_fmap_item is None:
                        map_fmap_item = {}
                        self.mapFMAP[pair.item] = map_fmap_item

                    for j in range(i + 1, len(revised_transaction)):
                        pair_after = revised_transaction[j]
                        twu_sum = map_fmap_item.get(pair_after.item)
                        if twu_sum is None:
                            map_fmap_item[pair_after.item] = new_twu
                        else:
                            map_fmap_item[pair_after.item] = twu_sum + new_twu
                tid += 1
        except Exception:
            pass
        finally:
            if my_input is not None:
                my_input.close()

        MemoryLogger.getInstance().checkMemory()
        self.maxMemory = MemoryLogger.getInstance().getMaxMemory()

        self.mapLLFMAP = {}
        prefix = Itemset()
        for i in range(len(list_of_utility_lists)):
            x = list_of_utility_lists[i]
            if x.sumIutils >= min_utility:
                self.store(prefix, x)
            if x.sumIutils + x.sumRutils >= min_utility:
                ex_uls = []
                for j in range(i + 1, len(list_of_utility_lists)):
                    y = list_of_utility_lists[j]
                    map_twuf = self.mapFMAP.get(x.item)
                    if map_twuf is not None:
                        twu_f = map_twuf.get(y.item)
                        if twu_f is not None and twu_f < min_utility:
                            continue
                    self.candidate += 1
                    ex_uls.append(self.construct(None, x, y))

                new_prefix = prefix.clone()
                new_prefix.addItem(x.item)
                lmap_fmap = self.mapLLFMAP.get(x.item)
                if lmap_fmap is None:
                    lmap_fmap = {}
                    self.mapLLFMAP[x.item] = lmap_fmap

                self.huiMiner(x.item, True, new_prefix, x, ex_uls)
                self.mapLLFMAP[x.item] = None

        if self.algo == 1:
            self.huciMiner()

        MemoryLogger.getInstance().checkMemory()
        self.maxMemory = MemoryLogger.getInstance().getMaxMemory()
        self.endTimestamp = int(time.time() * 1000)

        if output is not None:
            buffer = []
            for itemsets in self.tableHUCI.levels:
                for itemset in itemsets:
                    if not self.dontOutputGeneratorItemsets and not self.dontOutputClosedItemsets:
                        buffer.append("CLOSED: ")
                    if not self.dontOutputClosedItemsets:
                        buffer.append(self.itemsetToOutputString(itemset))

                    generators = self.tableHUCI.mapGenerators.get(itemset)
                    if (
                        not self.dontOutputGeneratorItemsets
                        and generators is not None
                        and len(generators) > 0
                    ):
                        if not self.dontOutputClosedItemsets:
                            buffer.append("GENERATOR: ")
                        for generator in generators:
                            buffer.append(self.itemsetToOutputString(generator))
                            self.ghui += 1

            self.writer.write("\n".join(buffer))

        if self.writer is not None:
            self.writer.close()

        return self.tableHUCI

    def itemsetToOutputString(self, itemset):
        parts = []
        for value in itemset.getItems():
            parts.append(str(value))
        result = " ".join(parts)
        result += " #UTIL: " + str(itemset.acutility)
        result += " #SUP: " + str(itemset.support)
        return result

    def store(self, prefix, x):
        self.hui += 1
        if self.algo == 1:
            new_prefix = prefix.clone()
            new_prefix.addItem(x.item)
            k1 = new_prefix.size()
            if self.maxlength < k1:
                self.maxlength = k1
            new_prefix.acutility = x.sumIutils
            new_prefix.support = len(x.elements)
            new_prefix.sort()
            self.utilityunitarray(new_prefix, x)
            self.tableHUI.addHuighUtilityItemset(new_prefix)
            self.tableHUI.mapKey[new_prefix] = True
            self.tableHUI.mapSupp[new_prefix] = new_prefix.support
            self.tableHUI.mapClosed[new_prefix] = True
        elif self.algo == 0 and self.writer is not None:
            temp_array = [0] * (prefix.size() + 1)
            pos = 0
            for pos in range(prefix.size()):
                temp_array[pos] = prefix.get(pos)
            temp_array[prefix.size()] = x.item
            temp_array.sort()

            buffer = ""
            for value in temp_array:
                buffer += str(value) + " "

            if self.maxlength < len(temp_array):
                self.maxlength = len(temp_array)

            buffer += " #UTIL: " + str(x.sumIutils)
            buffer += " #SUP: " + str(len(x.elements))
            self.writer.write(buffer + "\n")

    def getTableHU(self):
        return self.tableHUI

    def getminutil(self):
        return self.minUtility

    def huciMiner(self):
        for iter_idx in range(2, self.maxlength + 1):
            if self.tableHUI.getLevelFor(iter_idx) is not None:
                if self.tableHUI.getLevelFor(iter_idx - 1) is not None:
                    for l_itemset in self.tableHUI.getLevelFor(iter_idx):
                        for s_itemset in self.subset(self.tableHUI.getLevelFor(iter_idx - 1), l_itemset):
                            if s_itemset.support == l_itemset.support:
                                self.tableHUI.mapClosed[s_itemset] = False
                                self.tableHUI.mapKey[l_itemset] = False
                    for l_itemset in self.tableHUI.getLevelFor(iter_idx - 1):
                        if self.tableHUI.mapClosed.get(l_itemset) is True:
                            self.tableHUCI.addHighUtilityClosedItemset(l_itemset)
                            self.chui += 1
                            s = self.subset(self.HG, l_itemset)
                            self.tableHUCI.mapGenerators[l_itemset] = s
                            for r in s:
                                if r in self.HG:
                                    self.HG.remove(r)
                        if (
                            self.tableHUI.mapKey.get(l_itemset) is True
                            and self.tableHUI.mapClosed.get(l_itemset) is False
                        ):
                            self.HG.append(l_itemset)
            elif self.tableHUI.getLevelFor(iter_idx - 1) is not None:
                for l_itemset in self.tableHUI.getLevelFor(iter_idx - 1):
                    if self.tableHUI.mapClosed.get(l_itemset) is True:
                        self.tableHUCI.addHighUtilityClosedItemset(l_itemset)
                        self.chui += 1
                        s = self.subset(self.HG, l_itemset)
                        self.tableHUCI.mapGenerators[l_itemset] = s
                        for r in s:
                            if r in self.HG:
                                self.HG.remove(r)
                    if (
                        self.tableHUI.mapKey.get(l_itemset) is True
                        and self.tableHUI.mapClosed.get(l_itemset) is False
                    ):
                        self.HG.append(l_itemset)

        if self.tableHUI.getLevelFor(self.maxlength) is not None:
            for l_itemset in self.tableHUI.getLevelFor(self.maxlength):
                if self.tableHUI.mapClosed.get(l_itemset) is True:
                    self.tableHUCI.addHighUtilityClosedItemset(l_itemset)
                    self.chui += 1
                    s = self.subset(self.HG, l_itemset)
                    self.tableHUCI.mapGenerators[l_itemset] = s
                    for r in s:
                        if r in self.HG:
                            self.HG.remove(r)

    def utilityunitarray(self, l_itemset, z_ul):
        for it in range(l_itemset.size()):
            ite = l_itemset.get(it)
            jk = self.mapItemToUtilityList.get(ite)
            v = 0
            for e in z_ul.elements:
                ey = self.findElementWithTID(jk, e.tid)
                if ey is not None:
                    v += ey.iutils
            l_itemset.addutility(v)

    def huiMiner(self, k, ft, prefix, p_ul, uls):
        lmap_fmap = self.mapLLFMAP.get(k)
        for i in range(len(uls) - 1, -1, -1):
            x = uls[i]
            if x.sumIutils >= self.minUtility:
                self.store(prefix, x)
            if x.sumIutils + x.sumRutils >= self.minUtility:
                ex_uls = []
                for j in range(i + 1, len(uls)):
                    y = uls[j]
                    if y.exutil >= self.minUtility:
                        if prefix.size() < 2:
                            map_twuf = self.mapFMAP.get(x.item)
                            if map_twuf is not None:
                                twu_f = map_twuf.get(y.item)
                                if twu_f is not None and twu_f < self.minUtility:
                                    continue
                        elif y.exutil < self.minUtility:
                            continue
                        else:
                            map_twuf = lmap_fmap.get(x.item) if lmap_fmap is not None else None
                            if map_twuf is not None:
                                twu_f = map_twuf.get(y.item)
                                if twu_f is not None and twu_f < self.minUtility:
                                    continue
                        self.candidate += 1
                        if ft and prefix.size() == 1:
                            ex_uls.append(self.constructL(p_ul, x, y, k))
                        else:
                            ex_uls.append(self.construct(p_ul, x, y))

                new_prefix = prefix.clone()
                new_prefix.addItem(x.item)
                self.huiMiner(k, True, new_prefix, x, ex_uls)

    def construct(self, p, px, py):
        pxy_ul = UtilityList(py.item)
        new_twu = 0
        for ex in px.elements:
            ey = self.findElementWithTID(py, ex.tid)
            if ey is not None:
                if p is None:
                    exy = Element(ex.tid, ex.iutils + ey.iutils, ey.rutils)
                    pxy_ul.addElement(exy)
                    new_twu += ex.iutils + ex.rutils
                else:
                    e = self.findElementWithTID(p, ex.tid)
                    if e is not None:
                        exy = Element(ex.tid, ex.iutils + ey.iutils - e.iutils, ey.rutils)
                        pxy_ul.addElement(exy)
                        new_twu += ex.iutils + ex.rutils
        pxy_ul.setexutil(new_twu)
        return pxy_ul

    def constructL(self, p, px, py, k):
        pxy_ul = UtilityList(py.item)
        new_twu = 0
        newex = 0
        for ex in px.elements:
            ey = self.findElementWithTID(py, ex.tid)
            if ey is None:
                continue
            if p is None:
                exy = Element(ex.tid, ex.iutils + ey.iutils, ey.rutils)
                pxy_ul.addElement(exy)
            else:
                e = self.findElementWithTID(p, ex.tid)
                if e is not None:
                    exy = Element(ex.tid, ex.iutils + ey.iutils - e.iutils, ey.rutils)
                    new_twu = new_twu + e.iutils + e.rutils
                    newex = newex + ex.iutils + ex.rutils
                    pxy_ul.addElement(exy)

        lmap_fmap = self.mapLLFMAP.get(k)
        if lmap_fmap.get(px.item) is None:
            lmap_fmap[px.item] = {}

        lmap_fmap[px.item][py.item] = new_twu
        pxy_ul.setexutil(newex)
        return pxy_ul

    def findElementWithTID(self, ulist, tid):
        data = ulist.elements
        first = 0
        last = len(data) - 1
        while first <= last:
            middle = (first + last) >> 1
            if data[middle].tid < tid:
                first = middle + 1
            elif data[middle].tid > tid:
                last = middle - 1
            else:
                return data[middle]
        return None

    def printStats(self):
        if self.algo == 0:
            print("=============  FHIM ALGORITHM - STATS =============")
        else:
            print("=============  HUCI-Miner ALGORITHM - STATS =============")
        print(" Total time ~ " + str(self.endTimestamp - self.startTimestamp) + " ms")
        print(" Memory ~ " + str(self.maxMemory) + " MB")
        print(" Candidate count : " + str(self.candidate))
        print(" High-utility itemsets count : " + str(self.hui))
        if self.algo == 1 and not self.dontOutputClosedItemsets:
            print(" Closed High-utility itemsets count : " + str(self.chui))
        if self.algo == 1 and not self.dontOutputGeneratorItemsets and self.writer is not None:
            print(" Generator High-utility itemsets count : " + str(self.ghui))
        print("===================================================")

    def subset(self, s_list, l_itemset):
        result = []
        for itemset_s in s_list:
            all_included = True
            for item_s in itemset_s.getItems():
                if not l_itemset.contains(item_s):
                    all_included = False
            if all_included:
                result.append(itemset_s)
        return result


class Element:
    def __init__(self, tid, iutils, rutils):
        self.tid = tid
        self.iutils = iutils
        self.rutils = rutils


class HUClosedTable:
    def __init__(self):
        self.levels = []
        self.mapGenerators = {}

    def addHighUtilityClosedItemset(self, itemset):
        while len(self.levels) <= itemset.size():
            self.levels.append([])
        tmp = self.levels[itemset.size()]
        for e in tmp:
            if e.includedIn(itemset):
                return
        self.levels[itemset.size()].append(itemset)

    def getLevelFor(self, i):
        if i + 1 == len(self.levels):
            new_list = []
            self.levels.append(new_list)
            return new_list
        if i + 1 < len(self.levels):
            return self.levels[i + 1]
        return None

    def getLevels1(self):
        return self.levels


class HUTable:
    def __init__(self):
        self.levels = []
        self.mapSupp = {}
        self.mapKey = {}
        self.mapClosed = {}

    def addHuighUtilityItemset(self, itemset):
        while len(self.levels) <= itemset.size():
            self.levels.append([])
        self.levels[itemset.size()].append(itemset)

    def getLevelFor(self, i):
        if i + 1 == len(self.levels):
            new_list = []
            self.levels.append(new_list)
            return new_list
        if i < len(self.levels):
            return self.levels[i]
        return None

    def getLevels(self):
        return self.levels


class Itemset:
    def __init__(self, items=None, items_utilities=None, transaction_utility=0):
        self.items = [] if items is None else list(items)
        self.itemsUtilities = [] if items_utilities is None else list(items_utilities)
        self.acutility = transaction_utility
        self.support = 0

    def contains(self, item):
        return item in self.items

    def sort(self):
        self.items.sort()

    def contains1(self, item):
        if self.contains(item):
            return self.items.index(item)
        return -1

    def incrementUtility(self, au):
        self.acutility += au

    def isEqualTo(self, itemset2):
        if len(self.items) != len(itemset2.items):
            return False
        return set(self.items) == set(itemset2.items)

    def getItemsUtilities(self):
        return self.itemsUtilities

    def setItemsUtilities(self, items_u):
        self.itemsUtilities = items_u

    def addItem(self, value):
        self.items.append(value)

    def addutility(self, value):
        self.itemsUtilities.append(value)

    def getItems(self):
        return self.items

    def get(self, index):
        return self.items[index]

    def print(self):
        print(self.__str__(), end="")

    def __str__(self):
        r = []
        for attribute in self.items:
            r.append(str(attribute))
        out = " ".join(r)
        out += ":" + str(self.acutility) + ":" + str(self.support) + ": [ "
        for k in self.itemsUtilities:
            out += str(k) + " "
        out += "] "
        return out

    def size(self):
        return len(self.items)

    def setItemset(self, lis):
        self.items = lis

    def includedIn(self, itemset2):
        return all(it in itemset2.getItems() for it in self.items)

    def cloneItemSetMinusAnItemset(self, itemset_to_not_keep):
        itemset = Itemset()
        for item in self.items:
            if not itemset_to_not_keep.contains(item):
                itemset.addItem(item)
        itemset.sort()
        return itemset

    def clone(self):
        temp = Itemset()
        for item in self.items:
            temp.addItem(item)
        return temp

    def union(self, itemset):
        union_itemset = Itemset()
        union_itemset.getItems().extend(self.items)
        for item in itemset.getItems():
            if item not in self.items:
                union_itemset.addItem(item)
        union_itemset.sort()
        return union_itemset

    def unionU(self, itemset):
        union_itemset = Itemset()
        union_itemset.getItems().extend(self.items)
        union_itemset.getItemsUtilities().extend(self.itemsUtilities)
        for l in range(len(itemset.getItems())):
            if itemset.getItems()[l] not in self.items:
                union_itemset.addItem(itemset.getItems()[l])
                union_itemset.addutility(itemset.getItemsUtilities()[l])
        union_itemset.bubbleSort()
        return union_itemset

    def bubbleSort(self):
        for i in range(len(self.items)):
            for j in range(len(self.items) - 1, i, -1):
                if self.items[j] < self.items[j - 1]:
                    self.items[j], self.items[j - 1] = self.items[j - 1], self.items[j]
                    self.itemsUtilities[j], self.itemsUtilities[j - 1] = (
                        self.itemsUtilities[j - 1],
                        self.itemsUtilities[j],
                    )

    def __eq__(self, other):
        if not isinstance(other, Itemset):
            return False
        return self.items == other.items

    def __hash__(self):
        return hash(tuple(self.items))


class MainTestHUCIMiner_closed_generators:
    @staticmethod
    def fileToPath(filename):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

    @staticmethod
    def main(arg=None):
        del arg
        input_path = MainTestHUCIMiner_closed_generators.fileToPath("DB_Utility.txt")
        output_path = MainTestHUCIMiner_closed_generators.fileToPath("output_python.txt")
        min_utility = 30

        algorithm = AlgoFHIM_and_HUCI()
        algorithm.runAlgorithmHUCIMiner(input_path, output_path, min_utility)
        algorithm.printStats()


class MemoryLogger:
    _instance = None

    def __init__(self):
        self.maxMemory = 0.0
        if not tracemalloc.is_tracing():
            tracemalloc.start()

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
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        current_memory, _peak = tracemalloc.get_traced_memory()
        current_memory_mb = current_memory / 1024.0 / 1024.0
        if current_memory_mb > self.maxMemory:
            self.maxMemory = current_memory_mb
        return current_memory_mb


@total_ordering
class Rule:
    def __init__(
        self,
        antecedent_itemset,
        consequent_itemset,
        utility,
        utility_confidence,
        parent,
        utility_antecedent,
    ):
        self.antecedentItemset = antecedent_itemset
        self.consequentItemset = consequent_itemset
        self.utility = utility
        self.utility_confidence = utility_confidence
        self.antcon = parent
        self.utilityAntecedent = utility_antecedent

    def getUtility(self):
        return self.utility

    def getParent(self):
        return self.antcon

    def getAntecedentUtility(self):
        return self.utilityAntecedent

    def getConfidence(self):
        return self.utility_confidence

    def print(self):
        print(self.__str__(), end="")

    def __str__(self):
        return str(self.antecedentItemset.getItems()) + " ==> " + str(self.consequentItemset.getItems())

    def getAntecedent(self):
        return self.antecedentItemset

    def getConsequent(self):
        return self.consequentItemset

    def __lt__(self, o):
        compare = self.getUtility() - o.getUtility()
        if compare != 0:
            return compare < 0

        itemset1size_a = 0 if self.antecedentItemset is None else self.antecedentItemset.size()
        itemset1size_b = 0 if o.antecedentItemset is None else o.antecedentItemset.size()
        compare2 = itemset1size_a - itemset1size_b
        if compare2 != 0:
            return compare2 < 0

        compare5 = self.getAntecedentUtility() - o.getAntecedentUtility()
        if compare5 != 0:
            return compare5 < 0

        itemset2size_a = 0 if self.consequentItemset is None else self.consequentItemset.size()
        itemset2size_b = 0 if o.consequentItemset is None else o.consequentItemset.size()
        compare3 = itemset2size_a - itemset2size_b
        if compare3 != 0:
            return compare3 < 0

        compare4 = int(self.getConfidence() - o.getConfidence())
        if compare4 != 0:
            return compare4 < 0
        return hash(self) < hash(o)

    def __eq__(self, o):
        if o is None or not isinstance(o, Rule):
            return False
        if o.antecedentItemset.size() != self.antecedentItemset.size():
            return False
        if o.consequentItemset.size() != self.consequentItemset.size():
            return False
        for i in range(self.antecedentItemset.size()):
            if self.antecedentItemset.get(i) != o.antecedentItemset.get(i):
                return False
        for i in range(self.consequentItemset.size()):
            if self.consequentItemset.get(i) != o.consequentItemset.get(i):
                return False
        return True

    def __hash__(self):
        return hash(
            (
                tuple(self.antecedentItemset.getItems()),
                tuple(self.consequentItemset.getItems()),
                self.utility,
                self.utility_confidence,
                self.utilityAntecedent,
            )
        )


class Rules:
    def __init__(self, name):
        self.rules = []
        self.name = name
        self.count = 0

    def printRules(self):
        print(" ------- " + self.name + " -------")
        print("Total number of Rules = " + str(self.count))
        print(" --------------------------------")

    def addRule(self, rule):
        while len(self.rules) <= rule.getParent().size():
            self.rules.append([])
        self.rules[rule.getParent().size()].append(rule)
        self.count += 1

    def getLevelCount(self):
        return len(self.rules)


class UtilityList:
    def __init__(self, item):
        self.item = item
        self.sumIutils = 0
        self.sumRutils = 0
        self.exutil = 0
        self.elements = []

    def addElement(self, element):
        self.sumIutils += element.iutils
        self.sumRutils += element.rutils
        self.elements.append(element)

    def setexutil(self, ext):
        self.exutil = ext


if __name__ == "__main__":
    MainTestHUCIMiner_closed_generators.main()
