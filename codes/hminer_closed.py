import os
import time
import tracemalloc


class AlgoHMiner_Closed:
    merging_flag = False
    eucs_flag = False

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
        self.construct_time = 0
        self.huiCount = 0
        self.candidateCount = 0
        self.construct_calls = 0
        self.numberRecursions = 0
        self.closure_time = 0
        self.temp_closure_time = 0
        self.p_laprune = 0
        self.p_cprune = 0
        self.recursive_calls = 0
        self.merging_time = 0
        self.temp_merging_time = 0
        self.mapItemToTWU = {}
        self.CHUIs = CItemsets("Chuis")
        self.writer = None
        self.jumpnum1 = 0
        self.jumpnum2 = 0
        self.nojumpnum = 0
        self.time_Test = 0
        self.temp_Test = 0
        self.outputFile = ""
        self.mapFMAP = {}
        self.debug = False
        self.stats_time = 0

    def getRealCHUICount(self):
        count = 0
        for entryHash in self.CHUIs.getLevels():
            if entryHash is None:
                continue
            count += len(entryHash)
        return count

    def writeCHUIsToFile(self, output):
        with open(output, "w", encoding="utf-8") as writer:
            for entryHash in self.CHUIs.getLevels():
                if entryHash is None:
                    continue
                for itemset in entryHash:
                    writer.write(str(itemset) + "\n")

    def runAlgorithm(self, transactionFile, outputFile, minUtility, merging, EUCS):
        MemoryLogger.getInstance().reset()
        AlgoHMiner_Closed.merging_flag = merging
        AlgoHMiner_Closed.eucs_flag = EUCS
        self.mapFMAP = {}
        self.startTimestamp = int(time.time() * 1000)
        self.mapItemToTWU = {}

        try:
            with open(transactionFile, "r", encoding="utf-8") as myInput:
                for thisLine in myInput:
                    thisLine = thisLine.strip()
                    if (
                        thisLine == ""
                        or thisLine[0] == "#"
                        or thisLine[0] == "%"
                        or thisLine[0] == "@"
                    ):
                        continue
                    split = thisLine.split(":")
                    items = split[0].split(" ")
                    transactionUtility = int(split[1])
                    for token in items:
                        item = int(token)
                        twu = self.mapItemToTWU.get(item)
                        twu = transactionUtility if twu is None else twu + transactionUtility
                        self.mapItemToTWU[item] = twu
        except Exception:
            import traceback

            traceback.print_exc()

        listOfCULLists = []
        HT = {}
        mapItemToCULList = {}
        for item in self.mapItemToTWU.keys():
            if self.mapItemToTWU[item] >= minUtility:
                uList = MCUL_List(item)
                mapItemToCULList[item] = uList
                listOfCULLists.append(uList)

        listOfCULLists.sort(key=lambda ul: (self.mapItemToTWU[ul.item], ul.item))

        time_EUCS = 0
        temp_EUCS = 0
        try:
            with open(transactionFile, "r", encoding="utf-8") as myInput:
                tid = 1
                for thisLine in myInput:
                    thisLine = thisLine.strip()
                    if (
                        thisLine == ""
                        or thisLine[0] == "#"
                        or thisLine[0] == "%"
                        or thisLine[0] == "@"
                    ):
                        continue

                    split = thisLine.split(":")
                    items = split[0].split(" ")
                    utilityValues = split[2].split(" ")

                    remainingUtility = 0
                    newTWU = 0
                    tx_key = []
                    revisedTransaction = []
                    for i in range(len(items)):
                        pair = AlgoHMiner_Closed.Pair()
                        pair.item = int(items[i])
                        pair.utility = int(utilityValues[i])

                        if self.mapItemToTWU.get(pair.item, 0) >= minUtility:
                            revisedTransaction.append(pair)
                            tx_key.append(pair.item)
                            newTWU += pair.utility

                    revisedTransaction.sort(key=lambda p: (self.mapItemToTWU[p.item], p.item))

                    if len(revisedTransaction) > 0:
                        if AlgoHMiner_Closed.merging_flag:
                            tx_key_tuple = tuple(tx_key)
                            if tx_key_tuple not in HT:
                                self.temp_merging_time = int(time.time() * 1000)
                                HT[tx_key_tuple] = len(
                                    mapItemToCULList[revisedTransaction[len(revisedTransaction) - 1].item].elements
                                )
                                self.merging_time += int(time.time() * 1000) - self.temp_merging_time

                                for i in range(len(revisedTransaction) - 1, -1, -1):
                                    pair = revisedTransaction[i]
                                    CULListOfItem = mapItemToCULList[pair.item]
                                    element = Element_MCUL_List(tid, pair.utility, remainingUtility, 0, 1, 0)

                                    if i > 0:
                                        element.Ppos = len(
                                            mapItemToCULList[revisedTransaction[i - 1].item].elements
                                        )
                                    else:
                                        element.Ppos = -1

                                    CULListOfItem.addElement(element)
                                    CULListOfItem.NSupport += 1
                                    remainingUtility += pair.utility
                            else:
                                self.temp_merging_time = int(time.time() * 1000)
                                pos = HT[tx_key_tuple]
                                remainingUtility = 0
                                for i in range(len(revisedTransaction) - 1, -1, -1):
                                    CULListOfItem = mapItemToCULList[revisedTransaction[i].item]

                                    CULListOfItem.elements[pos].Nu += revisedTransaction[i].utility
                                    CULListOfItem.elements[pos].Nru += remainingUtility
                                    CULListOfItem.sumNu += revisedTransaction[i].utility
                                    CULListOfItem.sumNru += remainingUtility
                                    CULListOfItem.elements[pos].WXTj += 1
                                    CULListOfItem.NSupport += 1
                                    remainingUtility += revisedTransaction[i].utility
                                    pos = CULListOfItem.elements[pos].Ppos

                                self.merging_time += int(time.time() * 1000) - self.temp_merging_time
                        else:
                            for i in range(len(revisedTransaction) - 1, -1, -1):
                                pair = revisedTransaction[i]
                                CULListOfItem = mapItemToCULList[pair.item]
                                element = Element_MCUL_List(tid, pair.utility, remainingUtility, 0, 1, 0)

                                if i > 0:
                                    element.Ppos = len(
                                        mapItemToCULList[revisedTransaction[i - 1].item].elements
                                    )
                                else:
                                    element.Ppos = -1

                                CULListOfItem.addElement(element)
                                CULListOfItem.NSupport += 1
                                remainingUtility += pair.utility

                    if AlgoHMiner_Closed.eucs_flag:
                        temp_EUCS = int(time.time() * 1000)
                        for i in range(len(revisedTransaction) - 1, -1, -1):
                            pair = revisedTransaction[i]
                            mapFMAPItem = self.mapFMAP.get(pair.item)
                            if mapFMAPItem is None:
                                mapFMAPItem = {}
                                self.mapFMAP[pair.item] = mapFMAPItem

                            for j in range(i + 1, len(revisedTransaction)):
                                pairAfter = revisedTransaction[j]
                                twuSum = mapFMAPItem.get(pairAfter.item)
                                if twuSum is None:
                                    mapFMAPItem[pairAfter.item] = newTWU
                                else:
                                    mapFMAPItem[pairAfter.item] = twuSum + newTWU

                        time_EUCS += int(time.time() * 1000) - temp_EUCS

                    tid += 1
        except Exception:
            import traceback

            traceback.print_exc()

        self.checkMemory()
        initial_time = int(time.time() * 1000) - self.startTimestamp
        if self.debug:
            print("Initial time taken before mining: " + str(initial_time))
            print("EUCS time taken before mining: " + str(time_EUCS))
            print("Initial merging time: " + str(self.merging_time))

        MemoryLogger.getInstance().checkMemory()
        self.Search_CHUI([], listOfCULLists, minUtility)

        if self.debug:
            print("Closure time: " + str(self.closure_time))
            print("Final merging time: " + str(self.merging_time))
            print("#recursive calls: " + str(self.recursive_calls))
            print("#LA prune successful: " + str(self.p_laprune))
            print("#C prune + LA prune successful: " + str(self.p_cprune))

        self.endTimestamp = int(time.time() * 1000)
        MemoryLogger.getInstance().checkMemory()

    def sortCHUIs(self, level):
        level.sort(key=lambda it: it.support)

    def compareItemsbysupport(self, o1, o2):
        return o1.support - o2.support

    def compareItems(self, item1, item2):
        compare = int(self.mapItemToTWU[item1] - self.mapItemToTWU[item2])
        return item1 - item2 if compare == 0 else compare

    def Search_CHUI(self, prefix, MCULs, minUtility):
        self.recursive_calls += 1
        for i in range(len(MCULs)):
            X = self.appendItem(prefix, MCULs[i].item)
            UL_X = MCULs[i]
            support = UL_X.getSupport()

            if (
                UL_X.sumNu + UL_X.sumCu + UL_X.sumNru + UL_X.sumCru >= minUtility
                and not self.HasBackwardExtension(X, support, self.CHUIs.getLevels())
            ):
                self.candidateCount += 1
                if len(MCULs[i].elements) == 0:
                    Xy = list(X)
                    utilityOfJumpingCLosure = UL_X.sumNu + UL_X.sumCu
                    for j in range(i + 1, len(MCULs)):
                        Xy = self.appendItem(Xy, MCULs[j].item)
                        utilityOfJumpingCLosure += MCULs[j].sumCu - MCULs[j].sumCpu

                    if utilityOfJumpingCLosure >= minUtility:
                        self.jumpnum1 += 1
                        self.CHUIs.addItemset(Itemset(Xy, utilityOfJumpingCLosure, UL_X.getSupport()), len(Xy))
                        self.sortCHUIs(self.CHUIs.getLevels()[len(Xy)])
                else:
                    self.temp_Test = int(time.time() * 1000)
                    exULs = self.Construct_MCUL(UL_X, MCULs, i, minUtility, len(X))
                    self.time_Test += int(time.time() * 1000) - self.temp_Test

                    count = 0
                    for ml in exULs:
                        if ml.getSupport() == UL_X.getSupport():
                            count += 1

                    if count == (len(MCULs) - (i + 1)) and count != 0:
                        Xy = list(X)
                        utilityOfJumpingCLosure = 0
                        for j in range(i + 1, len(MCULs)):
                            Xy = self.appendItem(Xy, MCULs[j].item)
                        utilityOfJumpingCLosure += self.utilityOfJumpingClosure(exULs)

                        if utilityOfJumpingCLosure >= minUtility:
                            self.jumpnum2 += 1
                            self.CHUIs.addItemset(Itemset(Xy, utilityOfJumpingCLosure, UL_X.getSupport()), len(Xy))
                            self.sortCHUIs(self.CHUIs.getLevels()[len(Xy)])
                    else:
                        if count == 0 and UL_X.sumNu + UL_X.sumCu >= minUtility:
                            self.nojumpnum += 1
                            self.CHUIs.addItemset(Itemset(X, UL_X.sumNu + UL_X.sumCu, UL_X.getSupport()), len(X))
                            self.sortCHUIs(self.CHUIs.getLevels()[len(X)])
                        self.Search_CHUI(X, exULs, minUtility)

        MemoryLogger.getInstance().checkMemory()

    def HasBackwardExtension(self, X, sup, CHUIs):
        k = len(X)
        n = len(CHUIs) - 1
        if k >= n:
            return False
        for i in range(k + 1, n + 1):
            vt = self.binarySearchOverCHUIs(sup, CHUIs[i])
            if vt != -1:
                prev = vt
                while prev >= 0 and CHUIs[i][prev].support == sup:
                    if CHUIs[i][prev].contains(Itemset(X, 0, 0)):
                        return True
                    prev -= 1
                next_idx = vt + 1
                while next_idx < len(CHUIs[i]) and CHUIs[i][next_idx].support == sup:
                    if CHUIs[i][next_idx].contains(Itemset(X, 0, 0)):
                        return True
                    next_idx += 1
        return False

    def binarySearchOverCHUIs(self, support, CHUIs):
        first = 0
        last = len(CHUIs) - 1
        while first <= last:
            middle = (first + last) >> 1
            if CHUIs[middle].support < support:
                first = middle + 1
            elif CHUIs[middle].support > support:
                last = middle - 1
            else:
                return middle
        return -1

    def appendItem(self, itemset, item):
        newgen = [0] * (len(itemset) + 1)
        newgen[0 : len(itemset)] = itemset
        newgen[len(itemset)] = item
        return newgen

    def utilityOfJumpingClosure(self, exULs):
        utilityOfRemainingItemsJumpingClosure = 0
        utilityOfRemainingItemsJumpingClosure += exULs[0].sumNu + exULs[0].sumCu
        for st in range(1, len(exULs)):
            utilityOfRemainingItemsJumpingClosure += (
                exULs[st].sumNu
                - exULs[st].sumNpu
                + exULs[st].sumCu
                - exULs[st].sumCpu
            )
        return utilityOfRemainingItemsJumpingClosure

    def binarySearchtid(self, tid, elements):
        first = 0
        last = len(elements) - 1
        while first <= last:
            middle = (first + last) >> 1
            if elements[middle].tid < tid:
                first = middle + 1
            elif elements[middle].tid > tid:
                last = middle - 1
            else:
                return middle
        return -1

    def Construct_MCUL(self, X, MCULs, st, minutil, length):
        exCULs = []
        LAU = []
        CUTIL = []
        ey_tid = []
        for i in range(0, len(MCULs)):
            uList = MCUL_List(MCULs[i].item)
            exCULs.append(uList)
            LAU.append(0)
            CUTIL.append(0)
            ey_tid.append(0)

        sz = len(MCULs) - (st + 1)
        extSz = sz
        for j in range(st + 1, len(MCULs)):
            if AlgoHMiner_Closed.eucs_flag:
                mapTWUF = self.mapFMAP.get(X.item)
                if mapTWUF is not None:
                    twuF = mapTWUF.get(MCULs[j].item)
                    if twuF is not None and twuF < minutil:
                        exCULs[j] = None
                        extSz = sz - 1
                    else:
                        uList = MCUL_List(MCULs[j].item)
                        exCULs[j] = uList
                        ey_tid[j] = 0
                        LAU[j] = X.sumCu + X.sumCru + X.sumNu + X.sumNru
                        CUTIL[j] = X.sumCu + X.sumCru
            else:
                uList = MCUL_List(MCULs[j].item)
                exCULs[j] = uList
                ey_tid[j] = 0
                LAU[j] = X.sumCu + X.sumCru + X.sumNu + X.sumNru
                CUTIL[j] = X.sumCu + X.sumCru

        HT = {}
        for ex in X.elements:
            newT = []
            for j in range(st + 1, len(MCULs)):
                if exCULs[j] is None:
                    continue
                eylist = MCULs[j].elements

                while ey_tid[j] < len(eylist) and eylist[ey_tid[j]].tid < ex.tid:
                    ey_tid[j] = ey_tid[j] + 1

                if ey_tid[j] < len(eylist) and eylist[ey_tid[j]].tid == ex.tid:
                    newT.append(j)
                else:
                    LAU[j] = LAU[j] - ex.Nu - ex.Nru
                    if LAU[j] < minutil:
                        exCULs[j] = None
                        extSz = extSz - 1
                        self.p_laprune += 1

            if len(newT) == extSz:
                self.temp_closure_time = int(time.time() * 1000)
                self.UpdateClosed(X, MCULs, st, exCULs, newT, ex, ey_tid, length)
                self.closure_time += int(time.time() * 1000) - self.temp_closure_time
            else:
                if len(newT) == 0:
                    continue
                remainingUtility = 0

                if AlgoHMiner_Closed.merging_flag:
                    newT_key = tuple(newT)
                    if newT_key not in HT:
                        self.temp_merging_time = int(time.time() * 1000)
                        HT[newT_key] = len(exCULs[newT[len(newT) - 1]].elements)
                        self.merging_time += int(time.time() * 1000) - self.temp_merging_time

                        for i in range(len(newT) - 1, -1, -1):
                            CULListOfItem = exCULs[newT[i]]
                            Y = MCULs[newT[i]].elements[ey_tid[newT[i]]]

                            element = Element_MCUL_List(
                                ex.tid,
                                ex.Nu + Y.Nu - ex.Npu,
                                remainingUtility,
                                ex.Nu,
                                ex.WXTj,
                                0,
                            )

                            if i > 0:
                                element.Ppos = len(exCULs[newT[i - 1]].elements)
                            else:
                                element.Ppos = -1

                            CULListOfItem.addElement(element)
                            CULListOfItem.NSupport += ex.WXTj
                            CULListOfItem.sumNpu += ex.Nu
                            remainingUtility += Y.Nu - ex.Npu
                    else:
                        self.temp_merging_time = int(time.time() * 1000)
                        dupPos = HT[newT_key]
                        self.UpdateElement(X, MCULs, st, exCULs, newT, ex, dupPos, ey_tid)
                        self.merging_time += int(time.time() * 1000) - self.temp_merging_time
                else:
                    for i in range(len(newT) - 1, -1, -1):
                        CULListOfItem = exCULs[newT[i]]
                        Y = MCULs[newT[i]].elements[ey_tid[newT[i]]]

                        element = Element_MCUL_List(
                            ex.tid,
                            ex.Nu + Y.Nu - ex.Npu,
                            remainingUtility,
                            ex.Nu,
                            1,
                            0,
                        )

                        if i > 0:
                            element.Ppos = len(exCULs[newT[i - 1]].elements)
                        else:
                            element.Ppos = -1

                        CULListOfItem.addElement(element)
                        remainingUtility += Y.Nu - ex.Npu

            for j in range(st + 1, len(MCULs)):
                CUTIL[j] = CUTIL[j] + ex.Nu + ex.Nru

        filter_CULs = []
        for j in range(st + 1, len(MCULs)):
            if CUTIL[j] < minutil or exCULs[j] is None:
                self.p_cprune += 1
                continue
            else:
                if length > 1:
                    exCULs[j].sumCu += MCULs[j].sumCu + X.sumCu - X.sumCpu
                    exCULs[j].sumCru += MCULs[j].sumCru
                    exCULs[j].sumCpu += X.sumCu
                    exCULs[j].CSupport += X.CSupport
                filter_CULs.append(exCULs[j])

        return filter_CULs

    def UpdateClosed(self, X, MCULs, st, exCULs, newT, ex, ey_tid, length):
        del st, length
        nru = 0
        for j in range(len(newT) - 1, -1, -1):
            ey = MCULs[newT[j]]
            eyy = ey.elements[ey_tid[newT[j]]]
            exCULs[newT[j]].sumCu += ex.Nu + eyy.Nu - ex.Npu
            exCULs[newT[j]].sumCru += nru
            exCULs[newT[j]].sumCpu += ex.Nu
            nru = nru + eyy.Nu - ex.Npu
            exCULs[newT[j]].CSupport += eyy.WXTj

    def UpdateElement(self, X, MCULs, st, exCULs, newT, ex, dupPos, ey_tid):
        del X, st
        nru = 0
        pos = dupPos
        for j in range(len(newT) - 1, -1, -1):
            ey = MCULs[newT[j]]
            eyy = ey.elements[ey_tid[newT[j]]]
            exCULs[newT[j]].elements[pos].Nu += ex.Nu + eyy.Nu - ex.Npu
            exCULs[newT[j]].sumNu += ex.Nu + eyy.Nu - ex.Npu
            exCULs[newT[j]].elements[pos].Nru += nru
            exCULs[newT[j]].sumNru += nru
            exCULs[newT[j]].elements[pos].Npu += ex.Nu
            exCULs[newT[j]].sumNpu += ex.Npu
            nru = nru + eyy.Nu - ex.Npu
            exCULs[newT[j]].elements[pos].WXTj += eyy.WXTj
            exCULs[newT[j]].NSupport += eyy.WXTj
            pos = exCULs[newT[j]].elements[pos].Ppos

    def checkMemory(self):
        currentMemory = MemoryLogger.getInstance().checkMemory()
        if currentMemory > self.maxMemory:
            self.maxMemory = currentMemory

    def printStats(self):
        print("=============  HMINER-Closed ALGORITHM v.1.0 - STATS =============")
        print(" Total time ~ " + str(self.endTimestamp - self.startTimestamp) + " ms")
        print(" Max Memory ~ " + str(MemoryLogger.getInstance().getMaxMemory()) + " MB")
        print(" High-utility Closed itemsets count : " + str(self.getRealCHUICount()))
        print(" CandidateCount:" + str(self.recursive_calls))
        print(" Test time taken before mining: " + str(self.time_Test))
        print(
            " jump1 || jump2 || nojump: "
            + str(self.jumpnum1)
            + "||"
            + str(self.jumpnum2)
            + "||"
            + str(self.nojumpnum)
        )
        print("================================================")


class CItemsets:
    def __init__(self, name):
        self.levels = []
        self.itemsetsCount = 0
        self.name = name
        self.levels.append([])

    def printItemsets(self):
        print(" ------- " + self.name + " -------")
        patternCount = 0
        levelCount = 0
        for level in self.levels:
            print("  L" + str(levelCount) + " ")
            for itemset in level:
                itemset.itemset.sort()
                print("  pattern " + str(patternCount) + ":  " + str(itemset), end="")
                print("Utility :  " + str(itemset.getUtility()))
                patternCount += 1
                print(" ")
            levelCount += 1
        print(" --------------------------------")

    def addItemset(self, itemset, k):
        while len(self.levels) <= k:
            self.levels.append([])
        self.levels[k].append(itemset)
        self.itemsetsCount += 1

    def getLevels(self):
        return self.levels

    def getItemsetsCount(self):
        return self.itemsetsCount

    def setName(self, newName):
        self.name = newName

    def decreaseItemsetCount(self):
        self.itemsetsCount -= 1


class Element_MCUL_List:
    def __init__(self, tid, nu, nru, Npu, WXTj=0, ppos=0):
        self.tid = tid
        self.Nu = nu
        self.Nru = nru
        self.Npu = Npu
        self.WXTj = WXTj
        self.Ppos = ppos


class Itemset:
    def __init__(self, itemset, utility, support):
        self.itemset = itemset
        self.utility = utility
        self.support = support

    def getItems(self):
        return self.itemset

    def getUtility(self):
        return self.utility

    def size(self):
        return len(self.itemset)

    def get(self, position):
        return self.itemset[position]

    def contains(self, itemset2):
        hashset = set()
        for value in self.itemset:
            if value not in hashset:
                hashset.add(value)
        for value in itemset2.itemset:
            if value not in hashset:
                return False
        return True

    def __str__(self):
        r = []
        for i in range(self.size()):
            r.append(str(self.get(i)))
        return " ".join(r) + " #SUP: " + str(self.support) + " #UTIL: " + str(self.utility)


class MainTestHMiner_Closed:
    @staticmethod
    def fileToPath(filename):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

    @staticmethod
    def main(args=None):
        del args
        try:
            input_path = MainTestHMiner_Closed.fileToPath("DB_Utility.txt")
            min_utility = 30
            output = MainTestHMiner_Closed.fileToPath("output_python.txt")

            algorithm = AlgoHMiner_Closed()
            applyTransactionMergingOptimization = True
            applyEUCSOptimization = True

            algorithm.runAlgorithm(
                input_path,
                output,
                min_utility,
                applyTransactionMergingOptimization,
                applyEUCSOptimization,
            )
            algorithm.printStats()
            algorithm.writeCHUIsToFile(output)
        except Exception:
            import traceback

            traceback.print_exc()


class MCUL_List:
    def __init__(self, item):
        self.item = item
        self.sumNu = 0
        self.sumNpu = 0
        self.sumNru = 0
        self.sumCu = 0
        self.sumCpu = 0
        self.sumCru = 0
        self.CSupport = 0
        self.NSupport = 0
        self.elements = []

    @classmethod
    def from_mcul(cls, mculList):
        obj = cls(mculList.item)
        obj.sumNu = mculList.sumNu
        obj.sumCu = mculList.sumCu
        obj.sumCru = mculList.sumCru
        obj.sumCpu = mculList.sumCpu
        obj.NSupport = mculList.NSupport
        obj.CSupport = mculList.CSupport
        return obj

    def addElement(self, element):
        self.sumNu += element.Nu
        self.sumNru += element.Nru
        self.elements.append(element)

    def getSupport(self):
        return self.NSupport + self.CSupport


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
        currentMemory, _peak = tracemalloc.get_traced_memory()
        currentMemoryMB = currentMemory / 1024.0 / 1024.0
        if currentMemoryMB > self.maxMemory:
            self.maxMemory = currentMemoryMB
        return currentMemoryMB


if __name__ == "__main__":
    MainTestHMiner_Closed.main()
