import os
import time
import tracemalloc


class AlgoCHUIMiner:
    def __init__(self, use_eucp_strategy):
        self.startTimestamp = 0
        self.endTimestamp = 0
        self.chuidCount = 0
        self.candidateCount = 0
        self.mapItemToTWU = {}
        self.writer = None
        self.minUtility = 0
        self.mapFMAP = {}
        self.listItemsetsBySize = None
        self.setOfItemsInClosedItemsets = None
        self.useEUCPstrategy = use_eucp_strategy

    def saveToMemory(self, itemset, sum_iutils, support):
        if len(itemset) >= len(self.listItemsetsBySize):
            i = len(self.listItemsetsBySize)
            while i <= len(itemset):
                self.listItemsetsBySize.append([])
                i += 1
        list_to_add = self.listItemsetsBySize[len(itemset)]
        list_to_add.append(Itemset(itemset, sum_iutils, support))
        for item in itemset:
            self.setOfItemsInClosedItemsets.add(item)

    def runAlgorithm(self, input_path, min_utility, output):
        MemoryLogger.getInstance().reset()
        self.minUtility = min_utility

        if output is not None:
            self.writer = open(output, "w", encoding="utf-8")
        else:
            self.listItemsetsBySize = []
            self.setOfItemsInClosedItemsets = set()

        if self.useEUCPstrategy:
            self.mapFMAP = {}

        self.startTimestamp = int(time.time() * 1000)
        self.mapItemToTWU = {}

        try:
            with open(input_path, "r", encoding="utf-8") as my_input:
                for this_line in my_input:
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
                        twu = self.mapItemToTWU.get(item)
                        twu = transaction_utility if twu is None else twu + transaction_utility
                        self.mapItemToTWU[item] = twu
        except Exception:
            import traceback

            traceback.print_exc()

        list_of_utility_lists = []
        map_item_to_utility_list = {}
        for item in self.mapItemToTWU.keys():
            if self.mapItemToTWU[item] >= min_utility:
                ulist = UtilityList(item)
                map_item_to_utility_list[item] = ulist
                list_of_utility_lists.append(ulist)

        list_of_utility_lists.sort(key=lambda ul: (self.mapItemToTWU[ul.item], ul.item))

        try:
            with open(input_path, "r", encoding="utf-8") as my_input:
                tid = 0
                for this_line in my_input:
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

                    new_tu = 0
                    revised_transaction = []
                    for i in range(len(items)):
                        pair = PairItemUtility()
                        pair.item = int(items[i])
                        pair.utility = int(utility_values[i])
                        if self.mapItemToTWU.get(pair.item, 0) >= min_utility:
                            revised_transaction.append(pair)
                            new_tu += pair.utility

                    revised_transaction.sort(key=lambda p: (self.mapItemToTWU[p.item], p.item))

                    remaining_utility = new_tu
                    for i in range(len(revised_transaction)):
                        pair = revised_transaction[i]
                        remaining_utility -= pair.utility

                        utility_list_of_item = map_item_to_utility_list[pair.item]
                        element = Element(tid, pair.utility, remaining_utility)
                        utility_list_of_item.addElement(element)

                        if self.useEUCPstrategy:
                            map_fmap_item = self.mapFMAP.get(pair.item)
                            if map_fmap_item is None:
                                map_fmap_item = {}
                                self.mapFMAP[pair.item] = map_fmap_item

                            for j in range(i + 1, len(revised_transaction)):
                                pair_after = revised_transaction[j]
                                twu_sum = map_fmap_item.get(pair_after.item)
                                if twu_sum is None:
                                    map_fmap_item[pair_after.item] = new_tu
                                else:
                                    map_fmap_item[pair_after.item] = twu_sum + new_tu

                    tid += 1
        except Exception:
            import traceback

            traceback.print_exc()

        MemoryLogger.getInstance().checkMemory()
        self.chuimineClosed_eucp(True, [], None, [], list_of_utility_lists)
        MemoryLogger.getInstance().checkMemory()

        if self.writer is not None:
            self.writer.close()

        self.endTimestamp = int(time.time() * 1000)
        return self.listItemsetsBySize

    def chuimineClosed_eucp(self, first_time, closed_set, closed_set_ul, preset, postset):
        for i_ul in postset:
            if first_time:
                newgen_tids = i_ul
            else:
                newgen_tids = self.construct(closed_set_ul, i_ul)

            if self.isPassingHUIPruning(newgen_tids):
                new_gen = self.appendItem(closed_set, i_ul.item)

                if not self.is_dup(newgen_tids, preset):
                    closed_set_new = list(new_gen)
                    closedset_new_tids = newgen_tids
                    postset_new = []
                    passed_hui_pruning = True
                    for j_ul in postset:
                        if j_ul.item == i_ul.item or self.compareItems(j_ul.item, i_ul.item) < 0:
                            continue

                        should_prune = self.useEUCPstrategy and self.checkEUCPStrategy(i_ul.item, j_ul.item)
                        if should_prune:
                            continue
                        self.candidateCount += 1

                        if self.containsAllTIDS(j_ul, newgen_tids):
                            closed_set_new = self.appendItem(closed_set_new, j_ul.item)
                            closedset_new_tids = self.construct(closedset_new_tids, j_ul)
                            if not self.isPassingHUIPruning(closedset_new_tids):
                                passed_hui_pruning = False
                                break
                        else:
                            postset_new.append(j_ul)

                    if passed_hui_pruning:
                        if closedset_new_tids.sumIutils >= self.minUtility:
                            self.saveCHUI(closed_set_new, closedset_new_tids.sumIutils, len(closedset_new_tids.elements))

                        preset_new = list(preset)
                        self.chuimineClosed_eucp(False, closed_set_new, closedset_new_tids, preset_new, postset_new)

                    preset.append(i_ul)

    def isPassingHUIPruning(self, utilitylist):
        return utilitylist.sumIutils + utilitylist.sumRutils >= self.minUtility

    def containsAllTIDS(self, ul1, ul2):
        for elm_x in ul2.elements:
            elm_e = self.findElementWithTID(ul1, elm_x.tid)
            if elm_e is None:
                return False
        return True

    def checkEUCPStrategy(self, item_x, item_y):
        map_twuf = self.mapFMAP.get(item_x)
        if map_twuf is not None:
            twu_f = map_twuf.get(item_y)
            if twu_f is None or twu_f < self.minUtility:
                return True
        return False

    def appendItem(self, itemset, item):
        newgen = [0] * (len(itemset) + 1)
        newgen[0 : len(itemset)] = itemset
        newgen[len(itemset)] = item
        return newgen

    def is_dup(self, newgen_tids, preset):
        for j in preset:
            contains_all = True
            for elm_x in newgen_tids.elements:
                elm_e = self.findElementWithTID(j, elm_x.tid)
                if elm_e is None:
                    contains_all = False
                    break
            if contains_all:
                return True
        return False

    def construct(self, u_x, u_e):
        u_xe = UtilityList(u_e.item)
        for elm_x in u_x.elements:
            elm_e = self.findElementWithTID(u_e, elm_x.tid)
            if elm_e is None:
                continue
            elm_xe = Element(elm_x.tid, elm_x.iutils + elm_e.iutils, elm_x.rutils - elm_e.iutils)
            u_xe.addElement(elm_xe)
        return u_xe

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

    def saveCHUI(self, itemset, sum_iutils, support):
        self.chuidCount += 1
        if self.writer is None:
            self.saveToMemory(itemset, sum_iutils, support)
        else:
            buffer = ""
            for value in itemset:
                buffer += str(value) + " "
            buffer += " #SUP: " + str(support)
            buffer += " #UTIL: " + str(sum_iutils)
            self.writer.write(buffer + "\n")

    def printStats(self):
        print("=============  CHUIMiner ALGORITHM SPMF 0.97e - STATS =============")
        print(" Total time ~ " + str(self.endTimestamp - self.startTimestamp) + " ms")
        print(" Memory ~ " + str(MemoryLogger.getInstance().getMaxMemory()) + " MB")
        print(" Closed High-utility itemsets count : " + str(self.chuidCount))
        print(" Candidate count : " + str(self.candidateCount))
        print("=====================================================")

    def compareItems(self, item1, item2):
        compare = self.mapItemToTWU[item1] - self.mapItemToTWU[item2]
        return item1 - item2 if compare == 0 else compare


class AlgoGHUIMINER:
    def __init__(self):
        self.startTimestamp = 0
        self.endTimestamp = 0
        self.ghuiCount = 0
        self.candidateCount = 0
        self.candidateAvoidedbyFHM = 0
        self.closureRetrievals = 0
        self.generatorChecks = 0
        self.partiallyAvoidedOrAvoidedGeneratorChecks = 0
        self.mapItemToTWU = {}
        self.writer = None
        self.mapFMAP = {}
        self.transactionCount = 0
        self.debug = False
        self.mapItemToUtilityList = {}
        self.listOfUtilityLists = []
        self.emptySetIsGHUIs = False
        self.minUtility = 0
        self.BUFFERS_SIZE = 200
        self.itemsetBuffer = None
        self.enableLAPrune = True
        self.closedItemsetsBySize = None

    def getClosure(self, itemset_x, prefix_length, support):
        self.closureRetrievals += 1
        for i in range(prefix_length, len(self.closedItemsetsBySize)):
            itemsets = self.closedItemsetsBySize[i]
            if itemsets is not None:
                for itemset_in_list in itemsets:
                    if support < itemset_in_list.support:
                        break
                    if support == itemset_in_list.support and ArraysAlgos.includedIn_length(
                        itemset_x, prefix_length, itemset_in_list.itemset
                    ):
                        return itemset_in_list
        return None

    def isSubsetOfACHUI(self, itemset_x, prefix_length, support, strict_subset_check):
        min_size = (prefix_length + 1) if strict_subset_check else prefix_length
        for i in range(len(self.closedItemsetsBySize) - 1, min_size - 1, -1):
            itemsets = self.closedItemsetsBySize[i]
            if itemsets is not None:
                for itemset_in_list in itemsets:
                    if support < itemset_in_list.support:
                        break
                    if ArraysAlgos.includedIn_length(itemset_x, prefix_length, itemset_in_list.itemset):
                        return True
        return False

    def sortClosedItemsets(self):
        for itemsets_by_size in self.closedItemsetsBySize:
            itemsets_by_size.sort(key=lambda it: it.support)

    def sortItemsInAllCHUIsByTWU(self):
        for itemsets_by_size in self.closedItemsetsBySize:
            for itemset in itemsets_by_size:
                if itemset.support == self.transactionCount:
                    self.emptySetIsGHUIs = True
                self.insertionSort(itemset.itemset)

    def insertionSort(self, values):
        for j in range(1, len(values)):
            key = values[j]
            i = j - 1
            while i >= 0 and self.compareItems(values[i], key) > 0:
                values[i + 1] = values[i]
                i -= 1
            values[i + 1] = key

    def runAlgorithm(self, input_path, output, min_utility, closed_itemsets, items_in_closed_itemsets):
        self.closureRetrievals = 0
        self.transactionCount = 0
        self.itemsetBuffer = [0] * self.BUFFERS_SIZE
        self.mapFMAP = {}
        self.minUtility = min_utility
        self.startTimestamp = int(time.time() * 1000)
        MemoryLogger.getInstance().reset()
        self.writer = open(output, "w", encoding="utf-8")
        self.mapItemToTWU = {}

        total_utility = 0
        try:
            with open(input_path, "r", encoding="utf-8") as my_input:
                for this_line in my_input:
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
                        if item not in items_in_closed_itemsets:
                            continue
                        twu = self.mapItemToTWU.get(item)
                        twu = transaction_utility if twu is None else twu + transaction_utility
                        self.mapItemToTWU[item] = twu
                    self.transactionCount += 1
                    total_utility += transaction_utility
        except Exception:
            import traceback

            traceback.print_exc()

        self.listOfUtilityLists = []
        self.mapItemToUtilityList = {}

        for item in self.mapItemToTWU.keys():
            if self.mapItemToTWU[item] >= min_utility:
                ulist = UtilityListWithCriticalObjects(item)
                self.mapItemToUtilityList[item] = ulist
                self.listOfUtilityLists.append(ulist)

        self.listOfUtilityLists.sort(key=lambda ul: (self.mapItemToTWU[ul.item], ul.item))

        self.closedItemsetsBySize = closed_itemsets
        self.sortClosedItemsets()
        self.sortItemsInAllCHUIsByTWU()

        try:
            with open(input_path, "r", encoding="utf-8") as my_input:
                tid = 0
                for this_line in my_input:
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
                    transaction_utility = int(split[1])

                    new_tu = 0
                    revised_transaction = []
                    for i in range(len(items)):
                        pair = PairItemUtility()
                        pair.item = int(items[i])
                        pair.utility = int(utility_values[i])
                        utility = self.mapItemToTWU.get(pair.item)
                        if utility is not None and utility >= min_utility:
                            revised_transaction.append(pair)
                            new_tu += pair.utility
                        else:
                            transaction_utility -= pair.utility

                    revised_transaction.sort(key=lambda p: (self.mapItemToTWU[p.item], p.item))

                    for i in range(len(revised_transaction)):
                        pair = revised_transaction[i]
                        remaining_utility = transaction_utility - pair.utility
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
                                map_fmap_item[pair_after.item] = new_tu
                            else:
                                map_fmap_item[pair_after.item] = twu_sum + new_tu
                    tid += 1
        except Exception:
            import traceback

            traceback.print_exc()

        MemoryLogger.getInstance().checkMemory()

        tidset_empty_set = set(range(1, self.transactionCount))
        empty_ul = UtilityListWithCriticalObjects(None)
        empty_ul.tidset = tidset_empty_set
        empty_ul.crit = []
        empty_set = []

        filtered_uls = []
        for ul in self.listOfUtilityLists:
            itemset = [ul.item]
            support = len(ul.elements)
            self.checkIfGeneratorSingleItem(empty_ul, ul)

            keep = True
            if ul.crit is None or (ul.sumIutils + ul.sumRutils < min_utility):
                keep = False
            elif ul.sumIutils >= min_utility:
                self.writeOut(empty_set, 0, ul.item, ul.sumIutils, len(ul.elements))
                if not self.isSubsetOfACHUI(itemset, 1, support, True):
                    keep = False
            elif self.getClosure(itemset, 1, support) is not None:
                self.writeOut(empty_set, 0, ul.item, ul.sumIutils, len(ul.elements))

            if keep:
                filtered_uls.append(ul)

        self.listOfUtilityLists = filtered_uls

        if len(self.closedItemsetsBySize) > 0:
            if self.emptySetIsGHUIs:
                self.writeOutEmptySet(total_utility)
            self.ghuiMinerE(self.itemsetBuffer, 0, empty_ul, self.listOfUtilityLists)

        MemoryLogger.getInstance().checkMemory()
        self.writer.close()
        self.endTimestamp = int(time.time() * 1000)

    def compareItems(self, item1, item2):
        compare = self.mapItemToTWU[item1] - self.mapItemToTWU[item2]
        return item1 - item2 if compare == 0 else compare

    def ghuiMinerE(self, prefix_p, prefix_length, p_ul, extensions_uls):
        MemoryLogger.getInstance().checkMemory()
        for i in range(len(extensions_uls)):
            p_x_ul = extensions_uls[i]
            if p_x_ul.sumIutils + p_x_ul.sumRutils >= self.minUtility:
                self.itemsetBuffer[prefix_length] = p_x_ul.item
                extensions_of_px = []

                for j in range(i + 1, len(extensions_uls)):
                    p_y_ul = extensions_uls[j]
                    should_prune = self.checkEUCPStrategy(self.minUtility, p_x_ul.item, p_y_ul.item)
                    if should_prune:
                        continue

                    self.candidateCount += 1
                    p_xy_ul = self.construct(p_x_ul, p_y_ul, self.minUtility)
                    if p_xy_ul is None or len(p_xy_ul.elements) == 0:
                        continue

                    if (
                        len(p_xy_ul.elements) == len(p_x_ul.elements)
                        or len(p_xy_ul.elements) == len(p_y_ul.elements)
                    ):
                        self.partiallyAvoidedOrAvoidedGeneratorChecks += 1
                        continue

                    self.itemsetBuffer[prefix_length + 1] = p_y_ul.item
                    if not self.isSubsetOfACHUI(
                        self.itemsetBuffer, prefix_length + 2, len(p_xy_ul.elements), False
                    ):
                        continue

                    if p_xy_ul.sumIutils + p_xy_ul.sumRutils < self.minUtility:
                        continue

                    is_generator = self.checkIfGenerator(p_x_ul, p_xy_ul, prefix_length + 1)
                    if is_generator:
                        if p_xy_ul.sumIutils >= self.minUtility:
                            self.writeOut(
                                self.itemsetBuffer,
                                prefix_length + 1,
                                p_xy_ul.item,
                                p_xy_ul.sumIutils,
                                len(p_xy_ul.elements),
                            )
                        elif self.getClosure(self.itemsetBuffer, prefix_length + 2, len(p_xy_ul.elements)) is not None:
                            self.writeOut(
                                self.itemsetBuffer,
                                prefix_length + 1,
                                p_xy_ul.item,
                                p_xy_ul.sumIutils,
                                len(p_xy_ul.elements),
                            )
                        extensions_of_px.append(p_xy_ul)

                if len(extensions_of_px) > 1:
                    self.ghuiMinerE(self.itemsetBuffer, prefix_length + 1, p_x_ul, extensions_of_px)

    def checkEUCPStrategy(self, min_utility, item_x, item_y):
        map_twuf = self.mapFMAP.get(item_x)
        if map_twuf is not None:
            twu_f = map_twuf.get(item_y)
            if twu_f is None or twu_f < min_utility:
                self.candidateAvoidedbyFHM += 1
                return True
        return False

    def contains(self, values, integer):
        for item in values:
            if item == integer:
                return True
        return False

    def checkIfGenerator(self, p_ul, p_x_ul, prefix_size):
        self.generatorChecks += 1
        tidset_e = self.mapItemToUtilityList[p_x_ul.item].tidset
        p_x_ul.crit = [None] * (prefix_size + 1)

        crit_e = set(p_ul.tidset)
        crit_e.difference_update(tidset_e)
        p_x_ul.crit[len(p_x_ul.crit) - 1] = crit_e

        if len(crit_e) == 0:
            self.partiallyAvoidedOrAvoidedGeneratorChecks += 1
            return False

        for j in range(prefix_size):
            p_x_ul.crit[j] = set(p_ul.crit[j])
            p_x_ul.crit[j].intersection_update(tidset_e)
            cardinality = len(p_x_ul.crit[j])
            if cardinality == 0:
                if j < prefix_size - 1:
                    self.partiallyAvoidedOrAvoidedGeneratorChecks += 1
                return False
        return True

    def checkIfGeneratorSingleItem(self, empty_set_ul, x_ul):
        if self.transactionCount == len(x_ul.elements):
            self.partiallyAvoidedOrAvoidedGeneratorChecks += 1
            return
        self.generatorChecks += 1
        tidset_e = self.mapItemToUtilityList[x_ul.item].tidset
        crit = set(empty_set_ul.tidset)
        crit.difference_update(tidset_e)
        x_ul.crit = [crit]

    def construct(self, px, py, min_utility):
        pxy_ul = UtilityListWithCriticalObjects(py.item)
        total_utility = px.sumIutils + px.sumRutils
        for ex in px.elements:
            ey = self.findElementWithTID(py, ex.tid)
            if ey is not None:
                exy = Element(ex.tid, ex.iutils + ey.iutils, ex.rutils - ey.iutils)
                pxy_ul.addElement(exy)
            else:
                if self.enableLAPrune:
                    total_utility -= ex.iutils + ex.rutils
                    if total_utility < min_utility:
                        return None
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

    def writeOutEmptySet(self, total_utility):
        self.ghuiCount += 1
        self.writer.write("#SUP: " + str(self.transactionCount) + " #UTIL: " + str(total_utility) + "\n")

    def writeOut(self, prefix, prefix_length, item, sum_iutils, support):
        self.ghuiCount += 1
        buffer = ""
        for i in range(prefix_length):
            buffer += str(prefix[i]) + " "
        buffer += str(item)
        buffer += " #SUP: " + str(support)
        buffer += " #UTIL: " + str(sum_iutils)
        self.writer.write(buffer + "\n")

    def printStats(self):
        print("=============  GHUI-MINER - SPMF 0.97e - STATS =============")
        print(
            "   Candidate count : "
            + str(self.candidateCount)
            + "     (avoided by FHM : "
            + str(self.candidateAvoidedbyFHM)
            + ")\n"
            + "   Closure retrievals : "
            + str(self.closureRetrievals)
            + " \n"
            + "   Genenerator checks: "
            + str(self.generatorChecks)
            + "   (partially avoided : "
            + str(self.partiallyAvoidedOrAvoidedGeneratorChecks)
            + ")"
        )
        print(" Total time ~ " + str(self.endTimestamp - self.startTimestamp) + " ms")
        print(" Memory ~ " + str(MemoryLogger.getInstance().getMaxMemory()) + " MB")
        print(" GHUI count : " + str(self.ghuiCount))
        print("===================================================")


class ArraysAlgos:
    @staticmethod
    def cloneItemSetMinusOneItem(itemset, item_to_remove):
        new_itemset = [0] * (len(itemset) - 1)
        i = 0
        for value in itemset:
            if value != item_to_remove:
                new_itemset[i] = value
                i += 1
        return new_itemset

    @staticmethod
    def cloneItemSetMinusAnItemset(itemset, itemset_to_not_keep):
        itemset_to_not_keep_sorted = sorted(itemset_to_not_keep)
        result = []
        for value in itemset:
            if ArraysAlgos.binarySearch(itemset_to_not_keep_sorted, value) < 0:
                result.append(value)
        return result

    @staticmethod
    def allTheSameExceptLastItem(itemset1, itemset2):
        for i in range(len(itemset1) - 1):
            if itemset1[i] != itemset2[i]:
                return False
        return True

    @staticmethod
    def concatenate(prefix, suffix):
        return list(prefix) + list(suffix)

    @staticmethod
    def intersectTwoSortedArrays(array1, array2):
        pos1 = 0
        pos2 = 0
        result = []
        while pos1 < len(array1) and pos2 < len(array2):
            if array1[pos1] < array2[pos2]:
                pos1 += 1
            elif array2[pos2] < array1[pos1]:
                pos2 += 1
            else:
                result.append(array1[pos1])
                pos1 += 1
                pos2 += 1
        return result

    @staticmethod
    def containsOrEquals(itemset1, itemset2):
        i = 0
        j = 0
        while i < len(itemset1) and j < len(itemset2):
            if itemset1[i] == itemset2[j]:
                j += 1
                i += 1
            elif itemset1[i] > itemset2[j]:
                return False
            else:
                i += 1
        return j == len(itemset2)

    @staticmethod
    def containsLEX(itemset, item, max_item_in_array=None):
        if max_item_in_array is not None and item > max_item_in_array:
            return False
        for value in itemset:
            if value == item:
                return True
            if value > item:
                return False
        return False

    @staticmethod
    def sameAs(itemset1, itemset2, pos_removed):
        j = 0
        for i in range(len(itemset1)):
            if j == pos_removed:
                j += 1
            if itemset1[i] == itemset2[j]:
                j += 1
            elif itemset1[i] > itemset2[j]:
                return 1
            else:
                return -1
        return 0

    @staticmethod
    def includedIn(itemset1, itemset2):
        count = 0
        for value in itemset2:
            if count < len(itemset1) and value == itemset1[count]:
                count += 1
                if count == len(itemset1):
                    return True
        return False

    @staticmethod
    def includedIn_length(itemset1, itemset1_length, itemset2):
        count = 0
        for value in itemset2:
            if count < itemset1_length and value == itemset1[count]:
                count += 1
                if count == itemset1_length:
                    return True
        return False

    @staticmethod
    def containsLEXPlus(itemset, item):
        for value in itemset:
            if value == item:
                return True
            if value > item:
                return True
        return False

    @staticmethod
    def contains(itemset, item):
        for value in itemset:
            if value == item:
                return True
            if value > item:
                return False
        return False

    @staticmethod
    def appendIntegerToArray(array, integer):
        result = [0] * (len(array) + 1)
        result[0 : len(array)] = array
        result[len(array)] = integer
        return result

    @staticmethod
    def convertStringArrayToDoubleArray(tokens):
        return [float(token) for token in tokens]

    @staticmethod
    def isSubsetOf(itemset1, itemset2):
        if itemset1 is None or len(itemset1) == 0:
            return True
        for val in itemset1:
            found = False
            for value in itemset2:
                if value > val:
                    return False
                if val == value:
                    found = True
                    break
            if not found:
                return False
        return True

    @staticmethod
    def comparatorItemsetSameSize(itemset1, itemset2):
        for i in range(len(itemset1)):
            if itemset1[i] < itemset2[i]:
                return -1
            if itemset2[i] < itemset1[i]:
                return 1
        return 0

    @staticmethod
    def binarySearch(values, value):
        first = 0
        last = len(values) - 1
        while first <= last:
            middle = (first + last) >> 1
            if values[middle] < value:
                first = middle + 1
            elif values[middle] > value:
                last = middle - 1
            else:
                return middle
        return -1


class Element:
    def __init__(self, tid, iutils, rutils):
        self.tid = tid
        self.iutils = iutils
        self.rutils = rutils


class Itemset:
    def __init__(self, itemset, utility, support):
        self.itemset = itemset
        self.utility = utility
        self.support = support

    def __str__(self):
        return str(self.itemset) + " utility : " + str(self.utility) + " support:  " + str(self.support)


class MainTestGHUIMiner:
    @staticmethod
    def fileToPath(filename):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

    @staticmethod
    def main(arg=None):
        del arg
        input_path = MainTestGHUIMiner.fileToPath("DB_Utility.txt")
        min_utility = 30
        output = MainTestGHUIMiner.fileToPath("output_python.txt")

        print("Step 1: Mining CHUIs...")
        chui_mine_closed = AlgoCHUIMiner(True)
        closed_itemsets = chui_mine_closed.runAlgorithm(input_path, min_utility, None)
        chui_mine_closed.printStats()
        items_in_closed_itemsets = chui_mine_closed.setOfItemsInClosedItemsets

        print("Step 2: Mining GHUIs...")
        ghui_miner = AlgoGHUIMINER()
        ghui_miner.runAlgorithm(input_path, output, min_utility, closed_itemsets, items_in_closed_itemsets)
        ghui_miner.printStats()


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


class PairItemUtility:
    def __init__(self):
        self.item = 0
        self.utility = 0

    def __str__(self):
        return "[" + str(self.item) + "," + str(self.utility) + "]"


class UtilityList:
    def __init__(self, item):
        self.item = item
        self.sumIutils = 0
        self.sumRutils = 0
        self.elements = []

    def addElement(self, element):
        self.sumIutils += element.iutils
        self.sumRutils += element.rutils
        self.elements.append(element)

    def getSupport(self):
        return len(self.elements)

    def getUtils(self):
        return self.sumIutils


class UtilityListWithCriticalObjects(UtilityList):
    def __init__(self, item):
        super().__init__(item)
        self.tidset = set()
        self.crit = None

    def addElement(self, element):
        self.sumIutils += element.iutils
        self.sumRutils += element.rutils
        self.elements.append(element)
        self.tidset.add(element.tid)


if __name__ == "__main__":
    MainTestGHUIMiner.main()
