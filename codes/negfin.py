"""
Code by: Tai Dinh
Date: April 5, 2023
Description: This file contains a Python script that perform the NegFIN Algorithm.
https://www.sciencedirect.com/science/article/pii/S095741741830188X
"""

import math
import datetime

# the start time and end time of the last algorithm execution
startTimestamp = 0
endTimestamp = 0

# Tree stuff
bmcTreeRoot = None  # The root of BMC_tree
nlRoot = None  # The root of set enumeration tree.

numOfTrans = 0  # Number of transactions
numOfFItem = 0  # Number of items
outputCount = 0  # number of itemsets found
minSupport = 0  # minimum count
item = []  # list of items sorted by count
itemset = []  # the current itemset
itemsetLen = 0  # the size of the current itemset

sameItems = []

mapItemNodeset = {}  # nodessets of 1-itemsets

writer = None  # object to write the output file

# Comparator to sort items by decreasing order of frequency
comp = lambda a, b: b.num - a.num

class Item:
    def __init__(self, index=None, num=None):
        self.index = index
        self.num = num

class MyBitVector:
    TWO_POWER = [2 ** i for i in range(64)]

    def __init__(self, num_of_bits):
        self.bits = [0] * ((num_of_bits - 1) // 64 + 1)

    def __clone__(self):
        result = MyBitVector(len(self.bits) * 64)
        result.bits = self.bits[:]
        return result

    def set(self, bit_index):
        self.bits[bit_index // 64] |= MyBitVector.TWO_POWER[bit_index % 64]

    def isSet(self, bit_index):
        return (self.bits[bit_index // 64] & MyBitVector.TWO_POWER[bit_index % 64]) != 0
    

class SetEnumerationTreeNode:
    def __init__(self):
        self.label = 0
        self.firstChild = None
        self.next = None
        self.count = 0
        self.nodeset = []
        
class BMCTreeNode:
    def __init__(self):
        self.label = 0
        self.firstChild = None
        self.rightSibling = None
        self.father = None
        self.count = 0
        self.bitmapCode = MyBitVector(0)


def scanDB(filename, minSup):
    global numOfFItem,item,numOfTrans,minSupport
    # (1) Scan the database and count the count of each item.
    # The count of items is stored in map where
    # key = item value = count count
    numOfTrans = 0
    mapItemCount = {}

    # scan the database
    with open(filename, 'r') as reader:
        for line in reader:
            # if the line is a comment, is empty or is a
            # kind of metadata
            if line.strip() == '' or line[0] in ['#', '%', '@']:
                continue

            numOfTrans += 1

            # split the line into items
            lineSplited = line.split()
            # for each item in the transaction
            for itemString in lineSplited:
                # increase the count count of the item by 1
                item = int(itemString)
                count = mapItemCount.get(item)
                if count is None:
                    mapItemCount[item] = 1
                else:
                    mapItemCount[item] += 1

    # close the input file

    if minSup <=1:
        minSupport = int(math.ceil(minSup * numOfTrans))
    else:
        minSupport = minSup

    items = []
    for index, num in mapItemCount.items():
        if num >= minSupport:
            item = Item(index, num)
            items.append(item)

    items.sort(key=lambda x: (-x.num, x.index))
    item = items

    numOfFItem = len(item)


def construct_BMC_tree(filename):
    global bmcTreeRoot, mapItemNodeset
    # bmcTreeNodeCount = 0
    bmcTreeRoot.label = -1
    bmcTreeRoot.bitmapCode = MyBitVector(numOfFItem)

    # READ THE FILE
    with open(filename, 'r') as reader:
        for line in reader:
            # if the line is a comment, is empty or is a kind of metadata
            if line.strip() == '' or line.startswith('#') or line.startswith('%') or line.startswith('@'):
                continue
            
            # split the line into items
            lineSplited = line.strip().split(' ')
            transaction = []
            
            # for each item in the transaction
            for itemString in lineSplited:
                # get the item
                itemX = int(itemString)

                # add each item from the transaction except infrequent item
                for j in range(numOfFItem):
                    # if the item appears in the list of frequent items, we add it
                    if itemX == item[j].index:
                        transaction.append(Item(index=itemX, num=0-j))
                        break
            
            # sort the transaction
            transaction.sort(key=lambda x: (-x.num, x.index))

            curPos = 0
            curRoot = bmcTreeRoot
            rightSibling = None
            
            while curPos != len(transaction):
                child = curRoot.firstChild
                while child is not None:
                    if child.label == 0 - transaction[curPos].num:
                        curPos += 1
                        child.count += 1
                        curRoot = child
                        break
                    if child.rightSibling is None:
                        rightSibling = child
                        child = None
                        break
                    child = child.rightSibling
                if child is None:
                    break
                
            for j in range(curPos, len(transaction)):
                bmcTreeNode = BMCTreeNode()
                bmcTreeNode.label = 0 - transaction[j].num
                if rightSibling is not None:
                    rightSibling.rightSibling = bmcTreeNode
                    rightSibling = None
                else:
                    curRoot.firstChild = bmcTreeNode
                bmcTreeNode.rightSibling = None
                bmcTreeNode.firstChild = None
                bmcTreeNode.father = curRoot
                bmcTreeNode.count = 1
                curRoot = bmcTreeNode
                # bmcTreeNodeCount += 1
                
    # close the input file
    reader.close()
    
    root = bmcTreeRoot.firstChild
    mapItemNodeset = {}
    
    while root is not None:
        root.bitmapCode = root.father.bitmapCode.__clone__()
        root.bitmapCode.set(root.label)
        
        nodeset = mapItemNodeset.get(root.label, [])
        nodeset.append(root)
        mapItemNodeset[root.label] = nodeset
        
        if root.firstChild is not None:
            root = root.firstChild
        else:
            if root.rightSibling is not None:
                root = root.rightSibling
            else:
                root = root.father
                while root is not None:
                    if root.rightSibling is not None:
                        root = root.rightSibling
                        break
                    root = root.father
    print("Finish the construction")

def initializeSetEnumerationTree():
    global nlRoot
    lastChild = None
    for t in range(numOfFItem - 1, -1, -1):
        nlNode = SetEnumerationTreeNode()
        nlNode.label = t
        nlNode.count = 0
        nlNode.nodeset = mapItemNodeset[t]
        nlNode.firstChild = None
        nlNode.next = None
        nlNode.count = item[t].num
        if nlRoot.firstChild == None:
            nlRoot.firstChild = nlNode
            lastChild = nlNode
        else:
            lastChild.next = nlNode
            lastChild = nlNode

def constructing_frequent_itemset_tree(curNode, level, sameCount):
    global itemsetLen, item, itemset, sameItems
    sibling = curNode.next
    lastChild = None
    while sibling is not None:
        child = SetEnumerationTreeNode()
        child.nodeset = []
        countNegNodeset = 0
        if level == 1:
            for i in range(len(curNode.nodeset)):
                ni = curNode.nodeset[i]
                if not ni.bitmapCode.isSet(sibling.label):
                    child.nodeset.append(ni)
                    countNegNodeset += ni.count
        else:
            for j in range(len(sibling.nodeset)):
                nj = sibling.nodeset[j]
                if nj.bitmapCode.isSet(curNode.label):
                    child.nodeset.append(nj)
                    countNegNodeset += nj.count
        child.count = curNode.count - countNegNodeset
        if child.count >= minSupport:
            if curNode.count == child.count:
                sameItems[sameCount] = sibling.label
                sameCount += 1
            else:
                child.label = sibling.label
                child.firstChild = None
                child.next = None
                if curNode.firstChild is None:
                    curNode.firstChild = lastChild = child
                else:
                    lastChild.next = child
                    lastChild = child
        else:
            child.nodeset = None
        sibling = sibling.next

    itemset[itemsetLen] = curNode.label
    itemsetLen += 1

    # Write itemsets to file
    writeItemsetsToFile(curNode, sameCount)

    child = curNode.firstChild
    curNode.firstChild = None

    while child is not None:
        next = child.next
        constructing_frequent_itemset_tree(child, level + 1, sameCount)
        child.next = None
        child = next
    itemsetLen -= 1


def writeItemsetsToFile(curNode, sameCount):
    global outputCount
    buffer = []

    outputCount += 1
    # append items from the itemset to the buffer
    for i in range(itemsetLen):
        buffer.append(str(round(item[itemset[i]].index)))
        buffer.append(' ')
    # append the count of the itemset
    buffer.append("#SUP:")
    buffer.append(str(curNode.count))
    buffer.append(" %:")
    buffer.append(str(round(curNode.count/numOfTrans*100)))
    buffer.append("\n")

    # Write all combination that can be made using the node list of this itemset
    if sameCount > 0:
        # generate all subsets of the node list except the empty set
        for i in range(1, 1 << sameCount):
            for k in range(itemsetLen):
                buffer.append(str(item[itemset[k]].index))
                buffer.append(' ')

            # we create a new subset
            for j in range(sameCount):
                # check if the j bit is set to 1
                isSet = (i & (1 << j))
                if isSet > 0:
                    # if yes, add it to the set
                    buffer.append(str(item[sameItems[j]].index))
                    buffer.append(' ')

            buffer.append("#SUP:")
            buffer.append(str(curNode.count))
            buffer.append(" %:")
            buffer.append(str(round(curNode.count/numOfTrans*100)))
            buffer.append("\n")
            outputCount += 1

    # write the buffer to file and create a new line
    # so that we are ready for writing the next itemset.
    writer.write(''.join(buffer))

def runAlgorithm(filename, minsup, output):
    global itemsetLen, itemset, bmcTreeRoot, nlRoot, sameItems, writer
    bmcTreeRoot = BMCTreeNode()
    nlRoot = SetEnumerationTreeNode()


    # create object for writing the output file
    writer = open(output, "w")

    # record the start time
    startTimestamp = datetime.datetime.now()

    # ==========================
    # Read Dataset
    scanDB(filename, minsup)

    itemsetLen = 0
    itemset = [0] * numOfFItem

    # Build BMC-tree
    construct_BMC_tree(filename)

    nlRoot.label = numOfFItem
    nlRoot.firstChild = None
    nlRoot.next = None

    # Initialize tree
    initializeSetEnumerationTree()
    sameItems = [0] * numOfFItem

    # Recursively constructing_frequent_itemset_tree the tree
    curNode = nlRoot.firstChild
    nlRoot.firstChild = None
    nextNode = None
    while curNode is not None:
        nextNode = curNode.next
        # call the recursive "constructing_frequent_itemset_tree" method
        constructing_frequent_itemset_tree(curNode, 1, 0)
        curNode.next = None
        curNode = nextNode
    writer.close()

    # record the end time
    endTimestamp = datetime.datetime.now()

    # Print statistics about the latest execution of the algorithm
    print("========== negFIN - STATS ============")
    print(" Minsup = {}".format(minSupport))
    print(" Number of transactions: {}".format(numOfTrans))
    print(" Number of frequent  itemsets: {}".format(outputCount))
    print(" Total time ~: {} ms".format(endTimestamp - startTimestamp))
    print("=====================================")

if __name__ == "__main__":
    inputFile= "contextPasquier99.txt"
    outputFile = "negfin_output.txt"
    minSup = 0.1
    runAlgorithm(inputFile, minSup, outputFile)    