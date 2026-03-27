#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DFI-Growth

Input file format (each line):
    "<item> <item> ... #SUP: <count>"

Example run (no args needed if the input file is next to this script):
    python AlgoDFIGrowth.py
or with explicit paths:
    python AlgoDFIGrowth.py --input path/to/contextMushroom_FCI90.txt --output path/to/output_python.txt
"""

from __future__ import annotations
from typing import List, Optional
import os
import sys
import time
import argparse

# -------------------------
# Best-effort memory probe
# -------------------------
def _memory_megabytes() -> float:
    """Return current process memory usage in MB (best-effort; 0.0 on failure)."""
    try:
        import resource
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == "darwin":  # ru_maxrss bytes on macOS
            return rss / (1024.0 * 1024.0)
        return rss / 1024.0          # ru_maxrss KB on Linux
    except Exception:
        return 0.0


# -------------------------
# Data structures
# -------------------------
class TreeNode:
    def __init__(self, name: str = "", count: int = 0):
        self.name: str = name
        self.count: int = count
        self.child: List["TreeNode"] = []
        self.friend: Optional["TreeNode"] = None
        self.parent: Optional["TreeNode"] = None


class LinkNode:
    def __init__(self, n: str):
        self.hname: str = n
        self.friend: Optional[TreeNode] = None


# -------------------------
# Algorithm
# -------------------------
class AlgoDFIGrowth:
    def __init__(self) -> None:
        # working buffers
        self.data: List[List[str]] = []
        self.Intdata: List[List[int]] = []
        self.frequence: List[List[str]] = []
        self.subheaderTable: List[LinkNode] = []
        self.change_treenode: bool = True

        # stats
        self.startTimestamp: float = 0.0   # ms
        self.endTime: float = 0.0          # ms
        self.current_memory: float = 0.0
        self.MaxMemory: float = 0.0
        self.transactionCount: int = 0
        self.itemsetCount: int = 0

    # --- stats helper ---
    def MemoryUsage(self) -> None:
        self.current_memory = _memory_megabytes()
        if self.current_memory > self.MaxMemory:
            self.MaxMemory = self.current_memory

    # --- public API (equivalent to runAlgorithm) ---
    def runAlgorithm(self, input_path: str) -> None:
        self.MemoryUsage()
        self.startTimestamp = time.time() * 1000.0  # ms

        self.readDB(input_path)
        self.frequence = self.filter(self.frequence)
        self.data = self.changeDatabase(self.data, self.frequence)
        self.subheaderTable = self.createHT(self.frequence)
        self.frequence = []  # allow GC
        self.createFPT(self.subheaderTable, self.data)
        self.DFIgrowthReady(self.subheaderTable)

    # --- scan input DB & count items ---
    def readDB(self, input_path: str) -> None:
        self.transactionCount = 0
        self.data = []
        self.frequence = []
        is_firsttime = True

        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                self.transactionCount += 1
                parts = line.split(" #SUP: ")
                items = parts[0].split()
                sup = parts[1].strip()

                # store transaction (items + trailing support)
                row = items[:] + [sup]
                self.data.append(row)

                # update global item frequency (sum of supports from all lines)
                if is_firsttime:
                    # initialize
                    for it in items:
                        self.frequence.append([it, sup])
                    is_firsttime = False
                else:
                    for it in items:
                        found = False
                        for z in range(len(self.frequence)):
                            if self.frequence[z][0] == it:
                                self.frequence[z][1] = str(int(self.frequence[z][1]) + int(sup))
                                found = True
                                break
                        if not found:
                            self.frequence.append([it, sup])

        self.MemoryUsage()

    # --- sort items by (support desc, item id desc) ---
    def filter(self, freq: List[List[str]]) -> List[List[str]]:
        freq.sort(key=lambda o: (int(o[1]), int(o[0])), reverse=True)
        self.MemoryUsage()
        return freq

    # --- reorder database rows by global order ---
    def changeDatabase(self, predata: List[List[str]], frequent: List[List[str]]) -> List[List[str]]:
        newdata: List[List[str]] = []
        for row in predata:
            ordered: List[str] = []
            for name, _cnt in frequent:
                if name in row[:-1]:         # keep only items (exclude last support cell)
                    ordered.append(name)
            ordered.append(row[-1])         # keep support at the end
            newdata.append(ordered)
        self.MemoryUsage()
        return newdata

    # --- header table ---
    def createHT(self, frequent: List[List[str]]) -> List[LinkNode]:
        return [LinkNode(name) for name, _ in frequent]

    # --- build FP-tree (friends linked by header table) ---
    def createFPT(self, newheaderTable: List[LinkNode], datainfo: List[List[str]]) -> None:
        root = TreeNode()
        for row in datainfo:
            ttmp = root
            trans_sup = int(row[-1])
            for j in range(len(row) - 1):  # ignore last support cell
                self.change_treenode = True
                tnode = TreeNode(row[j], trans_sup)
                ttmp = self.createTNode(ttmp, tnode)
                if self.change_treenode:   # new node created -> wire into header list
                    for ln in newheaderTable:
                        if ln.hname == ttmp.name:
                            ttmp.friend = ln.friend
                            ln.friend = ttmp
                            break

    def createTNode(self, begin: TreeNode, tnode: TreeNode) -> TreeNode:
        if not begin.child:
            tnode.parent = begin
            begin.child.append(tnode)
            return tnode
        # try to reuse existing child
        for ch in begin.child:
            if ch.name == tnode.name:
                if tnode.count > ch.count:
                    ch.count = tnode.count
                self.change_treenode = False
                return ch
        # create new child
        tnode.parent = begin
        begin.child.append(tnode)
        return tnode

    # --- prepare conditional bases and start recursion ---
    def DFIgrowthReady(self, linknode: List[LinkNode]) -> None:
        self.data = []              # free input copy
        self.Intdata = []

        for i in range(len(linknode) - 1, -1, -1):
            maxcount = 0
            Hnode = linknode[i].friend
            Vnode = linknode[i].friend
            cond_bases: List[List[str]] = []

            while Hnode is not None:
                if Hnode.count > maxcount:
                    maxcount = Hnode.count

                sublist: List[str] = []
                is_itself = True
                is_first = True
                repeat_num = 0

                while Vnode is not None and Vnode.parent is not None:
                    if is_itself:
                        repeat_num = Vnode.count
                    else:
                        if is_first:
                            sublist.append(Vnode.name)
                            is_first = False
                        else:
                            sublist.insert(0, Vnode.name)
                    if Vnode.parent is None:
                        break
                    Vnode = Vnode.parent
                    is_itself = False

                if sublist:
                    sublist.append(str(repeat_num))
                    cond_bases.append(sublist)

                Hnode = Hnode.friend
                Vnode = Hnode

            self.DFIgrowth(linknode[i].hname, maxcount, cond_bases)

        self.MemoryUsage()
        self.endTime = time.time() * 1000.0  # ms

    # --- recursive DFI-growth ---
    def DFIgrowth(self, strname: str, hcount: int, lst: List[List[str]]) -> None:
        if not lst:
            self.sortoutputS(strname, str(hcount))
            return

        if len(lst) == 1:
            newlist = lst[0][:-1]  # drop trailing support
            self.GenSubset(strname, hcount, newlist)
            return

        # count items within conditional pattern base
        frequ: List[List[str]] = []
        is_firsttime = True
        for trans in lst:
            countnum = int(trans[-1])
            for item in trans[:-1]:
                if is_firsttime:
                    frequ.append([item, str(countnum)])
                else:
                    found = False
                    for z in range(len(frequ)):
                        if frequ[z][0] == item:
                            frequ[z][1] = str(int(frequ[z][1]) + countnum)
                            found = True
                            break
                    if not found:
                        frequ.append([item, str(countnum)])
            is_firsttime = False

        lst2 = self.changeDatabase(lst, frequ)
        newheaderTable = self.createHT(frequ)
        self.createFPT(newheaderTable, lst2)

        maxcount = 0
        for i in range(len(newheaderTable) - 1, -1, -1):
            Hnode = newheaderTable[i].friend
            Vnode = newheaderTable[i].friend
            newlist: List[List[str]] = []

            while Hnode is not None:
                if Hnode.count > maxcount:
                    maxcount = Hnode.count

                sublist: List[str] = []
                is_itself = True
                is_first = True
                repeat_num = 0

                while Vnode is not None and Vnode.parent is not None:
                    if is_itself:
                        repeat_num = Vnode.count
                    else:
                        if is_first:
                            sublist.append(Vnode.name)
                            is_first = False
                        else:
                            sublist.insert(0, Vnode.name)
                    if Vnode.parent is None:
                        break
                    Vnode = Vnode.parent
                    is_itself = False

                if sublist:
                    sublist.append(str(repeat_num))
                    newlist.append(sublist)

                Hnode = Hnode.friend
                Vnode = Hnode

            loopstr = f"{strname} {newheaderTable[i].hname}"
            self.DFIgrowth(loopstr, maxcount, newlist)

        self.MemoryUsage()
        self.sortoutputS(strname, str(hcount))

    # --- single-path subset generation ---
    def GenSubset(self, name: str, count: int, lst: List[str]) -> None:
        self.sortoutputS(name, str(count))
        # recursively append each suffix item (mirrors Java logic)
        for _ in range(len(lst)):
            name2 = f"{name} {lst[-1]}"
            lst = lst[:-1]
            self.GenSubset(name2, count, lst[:])

    # --- record a found itemset (sorted items asc, then keep support) ---
    def sortoutputS(self, s: str, num: str) -> None:
        tokens = s.split()
        ints = sorted(int(t) for t in tokens)
        self.MemoryUsage()
        ints.append(int(num))
        self.Intdata.append(ints)
        self.itemsetCount += 1

    # --- output & stats ---
    def writeOutPut(self, output_path: str) -> None:
        with open(output_path, "w", encoding="utf-8") as f:
            for row in self.Intdata:
                for j, val in enumerate(row):
                    if j < len(row) - 1:
                        f.write(f"{val} ")
                    else:
                        f.write("#SUP: ")
                        f.write(str(val))
                f.write("\n")
        self.Intdata = []

    def printStats(self) -> None:
        print("=============  DFI-GROWTH (Python) - STATS =============")
        temps = self.endTime - self.startTimestamp
        print(f" Transactions count from database : {self.transactionCount}")
        print(f" Max memory usage: {self.MaxMemory:.2f} mb")
        print(f" Frequent itemsets count : {self.itemsetCount}")
        print(f" Total time ~ {int(temps)} ms")
        print("========================================================")


# -------------------------
# CLI (equivalent of MainTestDFIGrowth_saveToFile)
# -------------------------
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    script_dir = os.path.dirname(os.path.abspath(__file__))

    parser.add_argument(
        "--input", "-i",
        default=os.path.join(script_dir, "contextMushroom_FCI90.txt"),
        help="Input file (SPMF style: '1 2 3 #SUP: N')."
    )
    parser.add_argument(
        "--output", "-o",
        default=os.path.join(script_dir, "output_python.txt"),
        help="Output file path."
    )
    args = parser.parse_args(argv)

    if not os.path.exists(args.input):
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 2

    algo = AlgoDFIGrowth()
    algo.runAlgorithm(args.input)
    algo.writeOutPut(args.output)
    algo.printStats()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
