import time
import psutil
import os
from collections import defaultdict
from urllib.parse import unquote
from typing import List, Dict

class Item:
    def __init__(self, name, utility=0):
        self.name = name  # item
        self.utility = utility  # utility of item

    def get_utility(self):
        return self.utility

    def set_utility(self, utility):
        self.utility = utility

    def get_name(self):
        return self.name
    
class Itemset:
    def __init__(self, itemset):
        self.itemset = itemset
        self.utility = 0

    def get_exact_utility(self):
        return self.utility

    def increase_utility(self, utility):
        self.utility += utility

    def get(self, pos):
        return self.itemset[pos]

    def size(self):
        return len(self.itemset)
    
class UPNode:
    def __init__(self):
        self.itemID = -1
        self.count = 1
        self.nodeUtility = 0
        self.parent = None
        self.childs = []
        self.nodeLink = None  # link to next node with the same item id (for the header table)

    def get_child_with_id(self, name):
        for child in self.childs:
            if child.itemID == name:
                return child
        return None

    def __str__(self):
        return f"(i={self.itemID} count={self.count} nu={self.nodeUtility})"
    
class UPTree:
    def __init__(self):
        self.headerList = None
        self.hasMoreThanOnePath = False
        self.mapItemNodes = {}
        self.root = UPNode()  # null node
        self.mapItemLastNode = {}

    def add_transaction(self, transaction, RTU):
        current_node = self.root
        size = len(transaction)

        for i in range(size):
            remaining_utility = sum(transaction[k].get_utility() for k in range(i + 1, size))
            item = transaction[i].get_name()

            child = current_node.get_child_with_id(item)

            if child is None:
                node_utility = RTU - remaining_utility
                remaining_utility = 0
                current_node = self.insert_new_node(current_node, item, node_utility)
            else:
                current_NU = child.nodeUtility
                node_utility = current_NU + (RTU - remaining_utility)
                remaining_utility = 0
                child.count += 1
                child.nodeUtility = node_utility
                current_node = child

    def add_local_transaction(self, local_path, path_utility, map_minimum_item_utility, path_count):
        current_local_node = self.root
        size = len(local_path)

        for i in range(size):
            remaining_utility = sum(map_minimum_item_utility[local_path[k]] * path_count for k in range(i + 1, size))
            item = local_path[i]

            child = current_local_node.get_child_with_id(item)

            if child is None:
                node_utility = path_utility - remaining_utility
                remaining_utility = 0
                current_local_node = self.insert_new_node(current_local_node, item, node_utility)
            else:
                current_NU = child.nodeUtility
                node_utility = current_NU + (path_utility - remaining_utility)
                remaining_utility = 0
                child.count += 1
                child.nodeUtility = node_utility
                current_local_node = child

    def insert_new_node(self, current_node, item, node_utility):
        new_node = UPNode()
        new_node.itemID = item
        new_node.nodeUtility = node_utility
        new_node.count = 1
        new_node.parent = current_node
        current_node.childs.append(new_node)

        if not self.hasMoreThanOnePath and len(current_node.childs) > 1:
            self.hasMoreThanOnePath = True

        local_header_node = self.mapItemNodes.get(item)
        if local_header_node is None:
            self.mapItemNodes[item] = new_node
            self.mapItemLastNode[item] = new_node
        else:
            last_node = self.mapItemLastNode[item]
            last_node.nodeLink = new_node
            self.mapItemLastNode[item] = new_node

        return new_node

    def create_header_list(self, map_item_to_estimated_utility):
        self.headerList = list(self.mapItemNodes.keys())

        self.headerList.sort(key=lambda id: (map_item_to_estimated_utility[id], id), reverse=True)

    def __str__(self):
        output = "HEADER TABLE: {}\n".format(self.mapItemNodes)
        output += "hasMoreThanOnePath: {}\n".format(self.hasMoreThanOnePath)
        return output + self._to_string("", self.root)

    def _to_string(self, indent, node):
        output = indent + str(node) + "\n"
        childs_output = ""
        for child in node.childs:
            childs_output += self._to_string(indent + " ", child)
        return output + childs_output
    
class AlgoUPGrowth:
    def __init__(self):
        self.maxMemory = 0
        self.startTimestamp = 0
        self.endTimestamp = 0
        self.huiCount = 0
        self.phuisCount = 0
        self.mapMinimumItemUtility = {}
        self.phuis = []
        self.DEBUG = False

    def run_algorithm(self, input_path: str, output_path: str, minUtility: int):
        self.maxMemory = 0
        self.startTimestamp = time.time()

        mapItemToTWU = defaultdict(int)

        # First database scan to calculate the TWU of each item
        with open(input_path, 'r') as file:
            for line in file:
                if not line.strip() or line.startswith(('#', '%', '@')):
                    continue

                items, transactionUtility, *_ = line.split(':')
                transactionUtility = int(transactionUtility)
                items = map(int, items.split())

                for item in items:
                    mapItemToTWU[item] += transactionUtility

        self.mapMinimumItemUtility = {}

        try:
            tree = UPTree()
            with open(input_path, 'r') as file:
                for line in file:
                    if not line.strip() or line.startswith(('#', '%', '@')):
                        continue

                    items, transactionUtility, utilityValues, *_ = line.split(':')
                    items = list(map(int, items.split()))
                    utilityValues = list(map(int, utilityValues.split()))

                    remainingUtility = 0
                    revisedTransaction = []

                    for itm, utility in zip(items, utilityValues):
                        if mapItemToTWU[itm] >= minUtility:
                            revisedTransaction.append(Item(itm, utility))
                            remainingUtility += utility

                            minItemUtil = self.mapMinimumItemUtility.get(itm)
                            if minItemUtil is None or minItemUtil >= utility:
                                self.mapMinimumItemUtility[itm] = utility

                    revisedTransaction.sort(key=lambda item: -mapItemToTWU[item.name])
                    tree.add_transaction(revisedTransaction, remainingUtility)

            tree.create_header_list(mapItemToTWU)
            self.check_memory()

            if self.DEBUG:
                print(f"GLOBAL TREE\nmapITEM-TWU : {mapItemToTWU}\nmapITEM-MINUTIL : {self.mapMinimumItemUtility}\n{tree}")

            self.upgrowth(tree, minUtility, [])
            self.check_memory()

        except Exception as e:
            print(e)

        self.phuisCount = len(self.phuis)

        self.phuis.sort(key=lambda itemset: itemset.size())
        try:
            with open(input_path, 'r') as file:
                for line in file:
                    if not line.strip() or line.startswith(('#', '%', '@')):
                        continue

                    items, _, utilityValues, *_ = line.split(':')
                    items = list(map(int, items.split()))
                    utilityValues = list(map(int, utilityValues.split()))

                    revisedTransaction = [Item(itm, utility) for itm, utility in zip(items, utilityValues) if mapItemToTWU[itm] >= minUtility]
                    revisedTransaction.sort(key=lambda item: item.name)

                    for itemset in self.phuis:
                        if itemset.size() > len(revisedTransaction):
                            break
                        self.update_exact_utility(revisedTransaction, itemset)

        except Exception as e:
            print(e)

        with open(output_path, 'w') as writer:
            for itemset in self.phuis:
                if itemset.get_exact_utility() >= minUtility:
                    self.write_out(writer, itemset)

        self.check_memory()
        self.endTimestamp = time.time()

        self.phuis.clear()
        self.mapMinimumItemUtility = None

    def compare_items_desc(self, item1, item2, mapItemEstimatedUtility):
        compare = mapItemEstimatedUtility[item2] - mapItemEstimatedUtility[item1]
        return compare if compare != 0 else item1 - item2

    def upgrowth(self, tree, minUtility, prefix):
        for i in range(len(tree.headerList) - 1, -1, -1):
            item = tree.headerList[i]

            localTree = self.create_local_tree(minUtility, tree, item)
            if self.DEBUG:
                print(f"LOCAL TREE for projection by: {','.join(map(str, prefix))},{item}\n{localTree}")
            pathCPB = tree.mapItemNodes.get(item)
            pathCPBUtility = 0
            while pathCPB is not None:
                pathCPBUtility += pathCPB.nodeUtility
                pathCPB = pathCPB.nodeLink

            if pathCPBUtility >= minUtility:
                newPrefix = prefix + [item]
                self.save_PHUI(newPrefix)

                if len(localTree.headerList) > 0:
                    self.upgrowth(localTree, minUtility, newPrefix)

    def create_local_tree(self, minUtility, tree, item):
        prefixPaths = []
        path = tree.mapItemNodes.get(item)
        itemPathUtility = defaultdict(int)

        while path is not None:
            nodeutility = path.nodeUtility
            if path.parent.itemID != -1:
                prefixPath = [path]
                parentnode = path.parent
                while parentnode.itemID != -1:
                    prefixPath.append(parentnode)
                    itemPathUtility[parentnode.itemID] += nodeutility
                    parentnode = parentnode.parent
                prefixPaths.append(prefixPath)
            path = path.nodeLink

        if self.DEBUG:
            print("\n\n\nPREFIXPATHS:")
            for prefixPath in prefixPaths:
                for node in prefixPath:
                    print(f"    {node}")
                print("    --")

        localTree = UPTree()
        for prefixPath in prefixPaths:
            pathCount = prefixPath[0].count
            pathUtility = prefixPath[0].nodeUtility
            localPath = []

            for node in prefixPath[1:]:
                itemValue = 0
                if itemPathUtility[node.itemID] >= minUtility:
                    localPath.append(node.itemID)
                else:
                    minItemUtility = self.mapMinimumItemUtility.get(node.itemID)
                    itemValue = minItemUtility * pathCount
                pathUtility -= itemValue

            if self.DEBUG:
                print(f"  path utility after DGU,DGN,DLU: {pathUtility}")

            localPath.sort(key=lambda o: -itemPathUtility[o])
            localTree.add_local_transaction(localPath, pathUtility, self.mapMinimumItemUtility, pathCount)

        localTree.create_header_list(itemPathUtility)
        return localTree

    def save_PHUI(self, itemset):
        itemsetObj = Itemset(itemset)
        self.phuis.append(itemsetObj)

    def update_exact_utility(self, transaction, itemset):
        utility = 0
        for item in itemset.itemset:
            for trans_item in transaction:
                if trans_item.name == item:
                    utility += trans_item.utility
                    break
                elif trans_item.name > item:
                    return
        itemset.increase_utility(utility)

    def write_out(self, writer, HUI):
        self.huiCount += 1
        buffer = ' '.join(map(str, HUI.itemset)) + f" #UTIL: {HUI.get_exact_utility()}"
        writer.write(buffer + '\n')

    def check_memory(self):
        process = psutil.Process(os.getpid())
        currentMemory = process.memory_info().rss / 1024 / 1024
        if currentMemory > self.maxMemory:
            self.maxMemory = currentMemory

    def print_stats(self):
        print(f"=============  UP-GROWTH ALGORITHM - STATS =============")
        print(f" PHUIs (candidates) count: {self.phuisCount}")
        print(f" Total time ~ {(self.endTimestamp - self.startTimestamp) * 1000:.0f} ms")
        print(f" Memory ~ {self.maxMemory:.2f} MB")
        print(f" HUIs count : {self.huiCount}")
        print(f"===================================================")

def file_to_path(filename):
    url = os.path.join(os.path.dirname(__file__), filename)
    return unquote(url)

def main():
    input_path = file_to_path("DB_Utility.txt")
    output_path = "output_UPGrowth.txt"
    min_utility = 30  # Minimum utility threshold

    # Applying the HUIMiner algorithm
    algo = AlgoUPGrowth()
    algo.run_algorithm(input_path, output_path, min_utility)
    algo.print_stats()

if __name__ == "__main__":
    main()