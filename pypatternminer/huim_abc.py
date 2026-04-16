from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import List, Optional, Set


class JavaRandom:
    def __init__(self, seed: int = 0):
        self.set_seed(seed)

    def set_seed(self, seed: int) -> None:
        self.seed = (seed ^ 0x5DEECE66D) & ((1 << 48) - 1)

    def next(self, bits: int) -> int:
        self.seed = (self.seed * 25214903917 + 11) & ((1 << 48) - 1)
        return self.seed >> (48 - bits)

    def next_double(self) -> float:
        return ((self.next(26) << 27) + self.next(27)) / float(1 << 53)


@dataclass
class Pair:
    item: int = 0
    utility: int = 0
    rutil: int = 0


@dataclass
class BeeGroup:
    X: List[int] = field(default_factory=list)
    fitness: int = 0
    rutil: int = 0
    trail: int = 0
    rfitness: float = 0.0

    def __init__(self, length: Optional[int] = None):
        self.X = [] if length is None else [0] * length
        self.fitness = 0
        self.rutil = 0
        self.trail = 0
        self.rfitness = 0.0

    def addtrail(self, k: int) -> None:
        self.trail += k


@dataclass
class HUI:
    itemset: str
    fitness: int


class Item:
    def __init__(self, item: int = 0):
        self.item = item
        self.TIDS: Set[int] = set()


class AlgoHUIM_ABC:
    def __init__(self, seed: int = 0):
        self.maxMemory = 0.0
        self.startTimestamp = 0
        self.endTimestamp = 0
        self.transactionCount = 0

        self.pop_size = 10
        self.limit = 5
        self.iterations = 2000
        self.changeBitNO = 2
        self.times = 5
        self.prunetimes = 50
        self.estiTransCount = 10000
        self.m = 0
        self.bucketNum = 120

        self.ScoutBeesBucket = [0] * self.bucketNum
        self.RScoutBeesiniBit = [0.0] * self.bucketNum

        self.iniBitNO = 0
        self.mapItemToTWU = {}
        self.mapItemToTWU0 = {}
        self.twuPattern: List[int] = []
        self.writer = None

        self.Items: List[Item] = []
        self.NectarSource: List[BeeGroup] = []
        self.EmployedBee: List[BeeGroup] = []
        self.OnLooker: List[BeeGroup] = []

        self.sumTwu = 0
        self.huiSets: List[HUI] = []
        self.huiBeeGroup = set()
        self.database: List[List[Pair]] = []
        self.databaseTran: List[List[int]] = []
        self.percentage: List[float] = []

        self.rng = JavaRandom(seed)

    def java_random(self) -> float:
        return self.rng.next_double()

    def runAlgorithm(self, input_file: str, output_file: str, minUtility: int) -> None:
        self.maxMemory = 0.0
        self.startTimestamp = int(time.time() * 1000)
        output_dir = os.path.dirname(output_file)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        self.writer = open(output_file, "w", encoding="utf-8", newline="")

        self.mapItemToTWU = {}
        self.mapItemToTWU0 = {}
        self.twuPattern = []
        self.Items = []
        self.NectarSource = []
        self.EmployedBee = []
        self.OnLooker = []
        self.sumTwu = 0
        self.huiSets = []
        self.huiBeeGroup = set()
        self.database = []
        self.databaseTran = []
        self.percentage = []
        self.transactionCount = 0

        with open(input_file, "r", encoding="utf-8") as f:
            for raw_line in f:
                thisLine = raw_line.strip()
                if not thisLine or thisLine[0] in "#%@":
                    continue
                split = thisLine.split(":")
                items = split[0].split(" ")
                transactionUtility = int(split[1])
                self.sumTwu += transactionUtility
                for token in items:
                    item = int(token)
                    twu = self.mapItemToTWU.get(item)
                    twu0 = self.mapItemToTWU0.get(item)
                    twu = transactionUtility if twu is None else twu + transactionUtility
                    twu0 = transactionUtility if twu0 is None else twu0 + transactionUtility
                    self.mapItemToTWU[item] = twu
                    self.mapItemToTWU0[item] = twu0

        with open(input_file, "r", encoding="utf-8") as f:
            for raw_line in f:
                thisLine = raw_line.strip()
                if not thisLine or thisLine[0] in "#%@":
                    continue
                split = thisLine.split(":")
                items = split[0].split(" ")
                utilityValues = split[2].split(" ")

                revisedTransaction: List[Pair] = []
                pattern: List[int] = []
                remainingUtility = 0

                for i in range(len(items)):
                    pair = Pair()
                    pair.item = int(items[i])
                    pair.utility = int(utilityValues[i])
                    if self.mapItemToTWU[pair.item] >= minUtility:
                        revisedTransaction.append(pair)
                        pattern.append(pair.item)
                        remainingUtility += pair.utility
                    else:
                        self.mapItemToTWU0.pop(pair.item, None)

                for pair in revisedTransaction:
                    remainingUtility -= pair.utility
                    pair.rutil = remainingUtility

                self.database.append(revisedTransaction)
                self.databaseTran.append(pattern)
                self.transactionCount += 1

        self.twuPattern = sorted(self.mapItemToTWU0.keys())
        self.m = int(len(self.twuPattern) / self.bucketNum) if self.bucketNum != 0 else 0
        self.Items = [Item(tempitem) for tempitem in self.twuPattern]

        for i in range(len(self.database)):
            for j in range(len(self.Items)):
                for k in range(len(self.database[i])):
                    if self.Items[j].item == self.database[i][k].item:
                        self.Items[j].TIDS.add(i)

        for i in range(len(self.ScoutBeesBucket)):
            self.ScoutBeesBucket[i] = 1

        self.checkMemory()

        if len(self.twuPattern) > 0:
            self.Initialization(minUtility)
            for _ in range(self.iterations):
                self.iniBitNO = 33
                self.Employed_bees(minUtility)
                self.calculateRfitness()
                self.OnLooker_bees(minUtility)
                self.calScoutBees()
                self.Scout_bees(self.iniBitNO, minUtility)

        self.writeOut()
        self.checkMemory()
        self.writer.close()
        self.endTimestamp = int(time.time() * 1000)

    def isRBeeGroup(self, tempBeeGroup: BeeGroup, out_list: List[int]) -> bool:
        templist: List[int] = []
        for i in range(len(tempBeeGroup.X)):
            if tempBeeGroup.X[i] != 0:
                templist.append(i)
        if len(templist) == 0:
            return False

        tempBitSet = set(self.Items[templist[0]].TIDS)
        for i in range(1, len(templist)):
            if len(tempBitSet) == 0:
                break
            tempBitSet &= self.Items[templist[i]].TIDS

        if len(tempBitSet) == 0:
            return False

        for m in range(max(tempBitSet) + 1 if tempBitSet else 0):
            if m in tempBitSet:
                out_list.append(m)
        return True

    def Initialization(self, minUtility: int) -> None:
        i = 0
        self.percentage = self.roulettePercent()

        while i < self.pop_size:
            besttempNode = BeeGroup(len(self.twuPattern))
            j = 0
            k = 0
            while True:
                while True:
                    templist: List[int] = []
                    while True:
                        k = int(self.java_random() * len(self.twuPattern))
                        if k != 0:
                            break
                    tempNode = BeeGroup(len(self.twuPattern))
                    self.iniBeeGroup(tempNode, k)
                    if self.isRBeeGroup(tempNode, templist) and tuple(tempNode.X) not in self.huiBeeGroup:
                        break
                self.fitCalculate(tempNode, k, templist)
                if tempNode.fitness >= besttempNode.fitness:
                    self.copyBeeGroup(besttempNode, tempNode)
                j += 1
                if not (besttempNode.fitness < minUtility and j < self.times):
                    break

            besttempNode.trail = 0
            self.OnLooker.append(BeeGroup(len(self.twuPattern)))
            self.EmployedBee.append(BeeGroup(len(self.twuPattern)))
            self.NectarSource.append(besttempNode)

            if besttempNode.fitness >= minUtility:
                if tuple(besttempNode.X) not in self.huiBeeGroup:
                    self.updateScoutBeesBucket(besttempNode.X.count(1))
                self.addlist(self.huiBeeGroup, besttempNode.X)
                self.insert(besttempNode)
            i += 1

        self.copylistBeeGroup(self.EmployedBee, self.NectarSource)

    def copylistBeeGroup(self, list1BeeGroup: List[BeeGroup], list2BeeGroup: List[BeeGroup]) -> None:
        for i in range(len(list1BeeGroup)):
            self.copyBeeGroup(list1BeeGroup[i], list2BeeGroup[i])

    def copyBeeGroup(self, beeG1: BeeGroup, beeG2: BeeGroup) -> None:
        self.copyList(beeG1.X, beeG2.X)
        beeG1.fitness = beeG2.fitness
        beeG1.rfitness = beeG2.rfitness
        beeG1.rutil = beeG2.rutil
        beeG1.trail = beeG2.trail

    def copyList(self, list1: List[int], list2: List[int]) -> None:
        for i in range(len(list1)):
            list1[i] = int(list2[i])

    def addlist(self, huiBeeGroup: set, values: List[int]) -> None:
        huiBeeGroup.add(tuple(int(v) for v in values))

    def Employed_bees(self, minUtility: int) -> None:
        self.copylistBeeGroup(self.EmployedBee, self.NectarSource)
        for i in range(self.pop_size):
            temp = self.meetReqBeeGroup(self.EmployedBee[i], minUtility, "sendEmployedBees")
            self.EmployedBee[i] = temp
            if self.EmployedBee[i].fitness > self.NectarSource[i].fitness:
                self.copyBeeGroup(self.NectarSource[i], self.EmployedBee[i])
            else:
                self.NectarSource[i].addtrail(1)

    def OnLooker_bees(self, minUtility: int) -> None:
        for i in range(self.pop_size):
            temp = self.selectNectarSource()
            self.copyBeeGroup(self.OnLooker[i], self.NectarSource[temp])
            tempBeeGroup = self.meetReqBeeGroup(self.OnLooker[i], minUtility, "sendOnLookerBees")
            self.OnLooker[i] = tempBeeGroup
            if self.OnLooker[i].fitness > self.NectarSource[temp].fitness:
                self.copyBeeGroup(self.NectarSource[temp], self.OnLooker[i])
            else:
                self.NectarSource[temp].addtrail(1)

    def Scout_bees(self, iniBitNO: int, minUtility: int) -> None:
        for i in range(self.pop_size):
            if self.NectarSource[i].trail > self.limit:
                besttempNode = BeeGroup(len(self.twuPattern))
                j = 0
                k = 0
                local_times = 5
                while True:
                    while True:
                        templist: List[int] = []
                        while True:
                            k = self.selectScoutIniBit() * self.m + int(self.java_random() * self.m) if self.m != 0 else 0
                            if k != 0:
                                break
                        tempNode = BeeGroup(len(self.twuPattern))
                        self.iniBeeGroup(tempNode, k)
                        if self.isRBeeGroup(tempNode, templist) and tuple(tempNode.X) not in self.huiBeeGroup:
                            break
                    self.fitCalculate(tempNode, k, templist)
                    if tempNode.fitness >= besttempNode.fitness:
                        self.copyBeeGroup(besttempNode, tempNode)
                    j += 1
                    if not (besttempNode.fitness < minUtility and j < local_times):
                        break

                besttempNode.trail = 0
                self.NectarSource[i] = besttempNode
                if besttempNode.fitness >= minUtility:
                    if tuple(besttempNode.X) not in self.huiBeeGroup:
                        self.updateScoutBeesBucket(besttempNode.X.count(1))
                    self.addlist(self.huiBeeGroup, besttempNode.X)
                    self.insert(besttempNode)

    def selectScoutIniBit(self) -> int:
        temp = 0
        randNum = self.java_random()
        for i in range(len(self.RScoutBeesiniBit)):
            if i == 0:
                if 0 <= randNum <= self.RScoutBeesiniBit[0]:
                    temp = 0
                    break
            elif self.RScoutBeesiniBit[i - 1] < randNum <= self.RScoutBeesiniBit[i]:
                temp = i
                break
        return temp

    def updateScoutBeesBucket(self, k: int) -> None:
        temp = k // self.m if self.m > 0 else 0
        if k >= 50:
            self.ScoutBeesBucket[self.bucketNum - 1] += 1
            return
        if temp >= self.bucketNum:
            temp = self.bucketNum - 1
        self.ScoutBeesBucket[temp] += 1

    def calScoutBees(self) -> None:
        total = 0
        tempSum = 0
        for value in self.ScoutBeesBucket:
            total += value
        for i in range(len(self.ScoutBeesBucket)):
            tempSum += self.ScoutBeesBucket[i]
            self.RScoutBeesiniBit[i] = tempSum / (total + 0.0)

    def selectNectarSource(self) -> int:
        temp = 0
        randNum = self.java_random()
        for i in range(len(self.NectarSource)):
            if i == 0:
                if 0 <= randNum <= self.NectarSource[0].rfitness:
                    temp = 0
                    break
            elif self.NectarSource[i - 1].rfitness < randNum <= self.NectarSource[i].rfitness:
                temp = i
                break
        return temp

    def calculateRfitness(self) -> None:
        total = 0
        temp = 0
        for source in self.NectarSource:
            total += source.fitness
        for i in range(len(self.NectarSource)):
            temp += self.NectarSource[i].fitness
            self.NectarSource[i].rfitness = temp / (total + 0.0)

    def changeKBit(self, tempGroup: BeeGroup) -> None:
        templist: List[int] = []
        for _ in range(self.changeBitNO):
            while True:
                k = int(self.java_random() * len(self.twuPattern))
                if k not in templist:
                    break
            templist.append(k)
            tempGroup.X[k] = 0 if tempGroup.X[k] == 1 else 1

    def meetReqBeeGroup(self, tempGroup: BeeGroup, minUtility: int, flag: str) -> BeeGroup:
        j = 0
        self.changeBitNO = 1
        self.times = 5
        besttempNode = BeeGroup(len(self.twuPattern))
        self.copyBeeGroup(besttempNode, tempGroup)

        while True:
            while True:
                templist: List[int] = []
                self.changeKBit(tempGroup)
                if self.isRBeeGroup(tempGroup, templist) and tuple(tempGroup.X) not in self.huiBeeGroup:
                    break

            k = tempGroup.X.count(1)
            self.fitCalculate(tempGroup, k, templist)
            if tempGroup.fitness > besttempNode.fitness:
                self.copyBeeGroup(besttempNode, tempGroup)
            else:
                self.copyBeeGroup(tempGroup, besttempNode)
            j += 1
            if not (besttempNode.fitness < minUtility and j < self.times):
                break

        if besttempNode.fitness >= minUtility:
            if tuple(besttempNode.X) not in self.huiBeeGroup:
                self.updateScoutBeesBucket(besttempNode.X.count(1))
            self.addlist(self.huiBeeGroup, besttempNode.X)
            self.insert(besttempNode)
        return besttempNode

    def delete0(self, values: List[int]) -> Optional[List[int]]:
        if len(values) > 0 and values.count(1) > 0:
            i = len(values) - 1
            while i >= 0 and values[i] == 0:
                i -= 1
            templist: List[int] = []
            j = 0
            while j <= i:
                templist.append(int(values[j]))
                j += 1
            return templist
        return None

    def iniBeeGroup(self, tempNode: BeeGroup, k: int) -> None:
        j = 0
        while j < k:
            temp = self.select(self.percentage)
            if tempNode.X[temp] == 0:
                j += 1
                tempNode.X[temp] = 1

    def roulettePercent(self) -> List[float]:
        total = 0
        tempSum = 0
        percentage: List[float] = []
        for item in self.twuPattern:
            total += self.mapItemToTWU[item]
        for item in self.twuPattern:
            tempSum += self.mapItemToTWU[item]
            percentage.append(tempSum / (total + 0.0))
        return percentage

    def select(self, percentage: List[float]) -> int:
        temp = 0
        randNum = self.java_random()
        for i in range(len(percentage)):
            if i == 0:
                if 0 <= randNum <= percentage[0]:
                    temp = 0
                    break
            elif percentage[i - 1] < randNum <= percentage[i]:
                temp = i
                break
        return temp

    def fitCalculate(self, tempGroup: BeeGroup, k: int, templist: List[int]) -> None:
        if k == 0:
            return
        fitness = 0
        rutil = 0
        for p in templist:
            i = 0
            j = 0
            q = 0
            temp = 0
            current_sum = 0
            while j < k and q < len(self.database[p]) and i < len(tempGroup.X):
                if tempGroup.X[i] == 1:
                    if self.database[p][q].item < self.twuPattern[i]:
                        q += 1
                    elif self.database[p][q].item == self.twuPattern[i]:
                        current_sum += self.database[p][q].utility
                        j += 1
                        q += 1
                        temp += 1
                        i += 1
                    else:
                        break
                else:
                    i += 1
            if temp == k:
                rutil += self.database[p][q - 1].rutil
                fitness += current_sum
        tempGroup.rutil = rutil + fitness
        tempGroup.fitness = fitness

    def insert(self, tempBeeGroup: BeeGroup) -> None:
        temp = "".join(f"{self.twuPattern[i]} " for i in range(len(self.twuPattern)) if tempBeeGroup.X[i] == 1)
        if len(self.huiSets) == 0:
            self.huiSets.append(HUI(temp, tempBeeGroup.fitness))
        else:
            i = 0
            while i < len(self.huiSets):
                if temp == self.huiSets[i].itemset:
                    break
                i += 1
            if i == len(self.huiSets):
                self.huiSets.append(HUI(temp, tempBeeGroup.fitness))

    def writeOut(self) -> None:
        buffer_parts: List[str] = []
        for hui in self.huiSets:
            buffer_parts.append(hui.itemset)
            buffer_parts.append("#UTIL: ")
            buffer_parts.append(str(hui.fitness))
            buffer_parts.append(os.linesep)
        self.writer.write("".join(buffer_parts))
        self.writer.write(os.linesep)

    def checkMemory(self) -> None:
        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF)
            currentMemory = usage.ru_maxrss / 1024.0
            if currentMemory > 1024 * 1024:
                currentMemory /= 1024.0
        except Exception:
            currentMemory = 0.0
        if currentMemory > self.maxMemory:
            self.maxMemory = currentMemory

    def getBucketNum(self) -> int:
        return self.bucketNum

    def setBucketNum(self, bucketNum: int) -> None:
        self.bucketNum = bucketNum
        self.ScoutBeesBucket = [0] * bucketNum
        self.RScoutBeesiniBit = [0.0] * bucketNum

    def printStats(self) -> None:
        print("=============  HUIM-ABC ALGORITHM v.2.40 - STATS =============")
        print(f" Total time ~ {self.endTimestamp - self.startTimestamp} ms")
        print(f" Memory ~ {self.maxMemory} MB")
        print(f" High-utility itemsets count : {len(self.huiSets)}")
        print("===================================================")


def main() -> None:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(base_dir, "contextHUIM.txt")
    output_dir = os.path.join(base_dir, "huim_abc")
    output_file = os.path.join(output_dir, "output_py.txt")

    min_utility = 10
    random_seed = 0

    algo = AlgoHUIM_ABC(seed=random_seed)
    algo.setBucketNum(2)
    algo.runAlgorithm(input_file, output_file, min_utility)
    algo.printStats()
    print("===================================================")
    print(f"Mining complete! Output saved to: {output_file}")


if __name__ == "__main__":
    main()
