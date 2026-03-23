# estDec_full.py
import math
import psutil
from collections import defaultdict

class MemoryLogger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MemoryLogger, cls).__new__(cls)
            cls._instance.max_memory = 0
        return cls._instance

    def get_max_memory(self):
        return self.max_memory

    def reset(self):
        self.max_memory = 0

    def check_memory(self):
        mem = psutil.Process().memory_info().rss / 1024 / 1024
        if mem > self.max_memory:
            self.max_memory = mem
        return mem

class EstNode:
    def __init__(self, item=None, count=0, tid=0):
        self.itemID = item if item is not None else -1
        self.counter = count
        self.tid = tid
        self.children = []

    def get_child_with_id(self, item):
        for child in self.children:
            if child.itemID == item:
                return child
        return None

    def get_child_index_with_id(self, item):
        for i, child in enumerate(self.children):
            if child.itemID == item:
                return i
        return -1

    def update(self, k, value, d):
        self.counter = self.counter * (d ** (k - self.tid)) + value
        self.tid = k

    def compute_support(self, N):
        return self.counter / N if N != 0 else 0

class EstTree:
    def __init__(self, minsup, minsig):
        self.N = 0
        self.k = 0
        self.minSup = minsup
        self.minSig = minsig
        self.d = math.pow(2, -1/10000)  # default decay rate
        self.root = EstNode()
        self.patternCount = 0
        self.itemsetBuffer = [0]*500
        self.patterns = None

    def set_decay_rate(self, b, h):
        self.d = math.pow(b, -1/h)

    def update_params(self, transaction):
        self.N = self.N * self.d + 1
        self.k += 1
        self._update_nodes(self.root, transaction, 0)

    def _update_nodes(self, node, transaction, ind):
        if ind >= len(transaction):
            return
        item = transaction[ind]
        child = node.get_child_with_id(item)
        if child:
            child.update(self.k, 1, self.d)
            if child.compute_support(self.N) >= self.minSig:
                self._update_nodes(child, transaction, ind+1)
        self._update_nodes(node, transaction, ind+1)

    def insert_item(self, item):
        self.root.children.append(EstNode(item, 0, self.k))

    def insert_itemset(self, transaction):
        transaction2 = []
        for item in transaction:
            child = self.root.get_child_with_id(item)
            if child is None:
                self.insert_item(item)
            elif child.compute_support(self.N) >= self.minSig:
                transaction2.append(item)
        for i, it in enumerate(transaction2):
            self.itemsetBuffer[0] = it
            self._insert_n_itemsets(self.root.get_child_with_id(it), transaction2, i+1, self.itemsetBuffer, 1)

    def _insert_n_itemsets(self, node, transaction, ind, itemset, length):
        if ind >= len(transaction):
            return
        for i in range(ind, len(transaction)):
            item = transaction[i]
            itemset[length] = item
            child = node.get_child_with_id(item)
            if child is None:
                c = self._estimate_count(itemset, length+1)
                if c/self.N >= self.minSig:
                    child = EstNode(item, c, self.k)
                    node.children.append(child)
            elif child.counter/self.N < self.minSig:
                if node.itemID != -1:
                    node.children.pop(node.get_child_index_with_id(item))
            else:
                self._insert_n_itemsets(child, transaction, i+1, itemset, length+1)

    def _get_count_without_item_at_pos(self, itemset, length, pos):
        node = self.root
        for i in range(length):
            if i != pos:
                child = node.get_child_with_id(itemset[i])
                if child is None:
                    return 0
                node = child
        return node.counter

    def _estimate_count(self, itemset, length):
        min_count = float('inf')
        for i in range(length):
            c = self._get_count_without_item_at_pos(itemset, length, i)
            if c < min_count:
                min_count = c
        C_upper = self.minSig * self._get_N(self.k-(length-1)) * (self.d**(length-1)) + (1 - self.d**(length-1))/(1-self.d)
        if min_count > C_upper:
            min_count = C_upper
        return min_count

    def _get_N(self, k):
        return (1 - self.d**k)/(1-self.d)

    def pattern_mining(self, node, pattern, pattern_len):
        new_len = pattern_len+1
        for child in node.children:
            child.update(self.k, 0, self.d)
            s = child.compute_support(self.N)
            if s > self.minSup:
                pattern[pattern_len] = child.itemID
                self.patternCount += 1
                if self.patterns is None:
                    self._write_itemset(pattern, new_len)
                else:
                    self.patterns[tuple(pattern[:new_len])] = s
                self.pattern_mining(child, pattern, new_len)

    def pattern_mining_save_to_memory(self):
        self.patterns = dict()
        self.patternCount = 0
        self.pattern_mining(self.root, self.itemsetBuffer, 0)
        return self.patterns

    def pattern_mining_save_to_file(self, output_file):
        self.patterns = None
        self.writer = open(output_file, 'w')
        self.patternCount = 0
        self.pattern_mining(self.root, self.itemsetBuffer, 0)
        self.writer.close()

    def _write_itemset(self, pattern, pattern_len):
        line = ' '.join(str(pattern[i]) for i in range(pattern_len))
        line += f' #SUP: {self._get_count(pattern, pattern_len)/self.N}'
        self.writer.write(line+'\n')

    def _get_count(self, pattern, length):
        node = self.root
        for i in range(length):
            node = node.get_child_with_id(pattern[i])
            if node is None:
                return 0
        return node.counter

    def node_count(self, node):
        s = 1
        for c in node.children:
            s += self.node_count(c)
        return s

class AlgoEstDec:
    def __init__(self, minsup, minsig):
        self.tree = EstTree(minsup, minsig)

    def set_decay_rate(self, b, h):
        self.tree.set_decay_rate(b, h)

    def processTransaction(self, transaction):
        self.tree.update_params(transaction)
        self.tree.insert_itemset(transaction)

    def processTransactionFromFile(self, file_path):
        with open(file_path, 'r') as f:
            for line in f:
                if line.strip():
                    trans = [int(x) for x in line.strip().split()]
                    self.processTransaction(trans)

    def performMining_saveResultToMemory(self):
        return self.tree.pattern_mining_save_to_memory()

    def performMining_saveResultToFile(self, output_file):
        self.tree.pattern_mining_save_to_file(output_file)

    def printStats(self):
        print(f'Pattern count: {self.tree.patternCount}')
        print(f'Tree nodes: {self.tree.node_count(self.tree.root)}')

# === Main program equivalent to Java MainTest_estDec_saveToFile ===
if __name__ == '__main__':
    database = 'contextIGB.txt'
    output = 'estdec_outputs.txt'
    minsup = 0.3
    minsig = 0.4*minsup

    algo = AlgoEstDec(minsup, minsig)
    algo.processTransactionFromFile(database)
    algo.performMining_saveResultToFile(output)
    algo.printStats()
