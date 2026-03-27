# AlgoDFIList.py
# Python of DFI-List (AlgoDFIList + MainTestDFIList).
# Input line format: "i1 i2 ... ik #SUP: N"

from __future__ import annotations
import argparse
import os
import sys
import time
import tracemalloc
from typing import List, Tuple

# Accept both "#SUP: " and "#SUP:" styles. The parser will handle trailing space.
SUP_TAG = "#SUP:"

def split_sup(line: str) -> Tuple[str, int]:
    """Split 'items #SUP: N' into (items_str, support_int)."""
    if SUP_TAG not in line:
        raise ValueError(f"Invalid line (missing {SUP_TAG}): {line!r}")
    left, right = line.split(SUP_TAG, 1)
    # right may start with a space; strip then parse int
    sup = int(right.strip())
    return left.strip(), sup

class AlgoDFIList:
    def __init__(self):
        self.storageAfterFCI = "SortFCI.txt"

        # stats/state
        self.itemMax: int = -1
        self.line_count: int = 0
        self.frequentItemsetCount: int = 0

        # timings
        self.startTimestampSortFCI: float = 0.0
        self.endTimeSortFCI: float = 0.0
        self.startTimestampBuildCidList: float = 0.0
        self.endTimeBuildCidList: float = 0.0
        self.startTimestampDerive: float = 0.0
        self.endTimeDerive: float = 0.0

        # memory (MB)
        self.currentMemory: float = 0.0
        self.maxMemory: float = 0.0

    def runAlgorithm(self, input_path: str, output_path: str) -> None:
        """Read FCIs, sort, build CID, derive FIs, and write output."""
        tracemalloc.start()

        # Phase 0: find max item + number of lines
        self.startTimestampSortFCI = time.perf_counter()
        self._findMax(input_path)
        self.itemMax += 1  # parity with Java

        # Phase 1: read FCIs, sort by support (desc), compute supports from SORTED array
        closed_itemsets = self._readFCI(input_path)
        self._sortFCI(closed_itemsets)     # writes SortFCI.txt
        self.endTimeSortFCI = time.perf_counter()

        supports = self._supportCount(closed_itemsets)  # aligned with sorted array
        closed_itemsets = None

        # Phase 2: build CID lists from the sorted file
        self.startTimestampBuildCidList = time.perf_counter()
        items_l, cid_list = self._buildCIDList()
        self.endTimeBuildCidList = time.perf_counter()

        # Phase 3: write output (1-itemsets + derived)
        with open(output_path, "w", encoding="utf-8") as fw:
            # 1-itemsets
            for i in range(len(items_l)):
                z = str(items_l[i])
                self._checkMemoryUsage()
                fw.write(f"{z} {SUP_TAG} {supports[cid_list[i][0]]}\n")

            # higher-order
            self.startTimestampDerive = time.perf_counter()
            self._deriveFI("", items_l, cid_list, supports, fw)
            self.endTimeDerive = time.perf_counter()

        # Clean temp file (best-effort)
        try:
            os.remove(self.storageAfterFCI)
        except FileNotFoundError:
            pass

        # finalize memory
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.maxMemory = max(self.maxMemory, peak / (1024 * 1024))

    def printStats(self) -> None:
        sortFCI = (self.endTimeSortFCI - self.startTimestampSortFCI) * 1000.0
        buildCidList = (self.endTimeBuildCidList - self.startTimestampBuildCidList) * 1000.0
        deriving = (self.endTimeDerive - self.startTimestampDerive) * 1000.0
        total = (self.endTimeDerive - self.startTimestampSortFCI) * 1000.0

        print("===================  DFI - STATS ==================")
        print(f" Frequent itemsets count : {self.frequentItemsetCount}")
        print(f" Max memory usage: {self.maxMemory:.3f} MB")
        print(f" SortFCI time ~ {sortFCI:.0f} ms")
        print(f" BuildCidList time ~ {buildCidList:.0f} ms")
        print(f" Deriving time ~ {deriving:.0f} ms")
        print(f" Total time ~ {total:.0f} ms")
        print("===================================================")

    # ------------ internals ------------

    def _checkMemoryUsage(self) -> None:
        current, peak = tracemalloc.get_traced_memory()
        self.currentMemory = current / (1024 * 1024)
        if self.currentMemory > self.maxMemory:
            self.maxMemory = self.currentMemory

    def _readFCI(self, input_path: str) -> List[str]:
        """Return lines exactly as read (without trailing newline)."""
        closed_itemsets = [None] * self.line_count
        with open(input_path, "r", encoding="utf-8") as f:
            i = 0
            for line in f:
                closed_itemsets[i] = line.rstrip("\n")
                i += 1
        return closed_itemsets

    def _sortFCI(self, closed_itemsets: List[str]) -> None:
        """Sort by support (descending) and persist to SortFCI.txt."""
        def sup_of(rec: str) -> int:
            _, sup = split_sup(rec)
            return sup
        closed_itemsets.sort(key=sup_of, reverse=True)
        with open(self.storageAfterFCI, "w", encoding="utf-8") as fw:
            for rec in closed_itemsets:
                fw.write(rec + "\n")

    def _supportCount(self, closed_itemsets: List[str]) -> List[int]:
        """Extract supports from the (already SORTED) list."""
        s = [0] * len(closed_itemsets)
        for i, rec in enumerate(closed_itemsets):
            self._checkMemoryUsage()
            _, sup = split_sup(rec)
            s[i] = sup
        return s

    def _buildCIDList(self) -> Tuple[List[int], List[List[int]]]:
        """Return (l, cid_list) where:
           - l: list of unique items
           - cid_list[i]: sorted line indices (in SortFCI.txt) where item l[i] occurs
        """
        l: List[int] = []
        cid_list: List[List[int]] = []

        i = 0
        with open(self.storageAfterFCI, "r", encoding="utf-8") as f:
            for raw in f:
                items_part, _ = split_sup(raw)
                tokens = items_part.strip().split()
                for tok in tokens:
                    self._checkMemoryUsage()
                    idx = int(tok)
                    if idx in l:
                        cid_list[l.index(idx)].append(i)
                    else:
                        l.append(idx)
                        cid_list.append([i])
                        self.frequentItemsetCount += 1
                i += 1

        # bubble sort by frequency asc (Java parity)
        sizes = [len(c) for c in cid_list]
        self._bubbleSort(sizes, l, cid_list)
        return l, cid_list

    def _bubbleSort(self, sizes: List[int], l: List[int], cid_list: List[List[int]]) -> None:
        n = len(sizes)
        for i in range(n - 1):
            for j in range(i + 1, n):
                if sizes[i] > sizes[j]:
                    sizes[i], sizes[j] = sizes[j], sizes[i]
                    l[i], l[j] = l[j], l[i]
                    cid_list[i], cid_list[j] = cid_list[j], cid_list[i]

    @staticmethod
    def _intersection(cidseq1: List[int], cidseq2: List[int]) -> List[int]:
        """Intersection of two sorted lists; returns [-1] if empty (Java behavior)."""
        p1 = p2 = 0
        out: List[int] = []
        while p1 < len(cidseq1) and p2 < len(cidseq2):
            if cidseq1[p1] > cidseq2[p2]:
                p2 += 1
            elif cidseq1[p1] < cidseq2[p2]:
                p1 += 1
            else:
                out.append(cidseq1[p1])
                p1 += 1
                p2 += 1
        return out if out else [-1]

    def _deriveFI(self, p: str, l: List[int], h: List[List[int]], s: List[int], fw) -> None:
        """Recursive derivation. Writes '<itemset> #SUP: N' just like Java."""
        i = 0
        while i < len(h):
            self._checkMemoryUsage()
            newP = f"{l[i]}" if p == "" else f"{p} {l[i]}"
            newL: List[int] = []
            newH: List[List[int]] = []

            for j in range(i + 1, len(h)):
                z = f"{newP} {l[j]}"
                tempValue = self._intersection(h[i], h[j])
                if -1 not in tempValue:
                    newH.append(tempValue)
                    newL.append(l[j])
                    fw.write(f"{z} {SUP_TAG} {s[tempValue[0]]}\n")
                    self.frequentItemsetCount += 1
                self._checkMemoryUsage()

            # emulate Java's in-place shrinking inside the loop
            h.pop(0)
            l.pop(0)

            # recurse with the extended prefix
            self._deriveFI(newP, newL, newH, s, fw)
            # after popping 0, keep i=0 (like i-- in Java for-loop)

    def _findMax(self, input_path: str) -> None:
        """Scan once to determine max item id and number of lines."""
        self.itemMax = -1
        self.line_count = 0
        with open(input_path, "r", encoding="utf-8") as f:
            for rec in f:
                rec = rec.rstrip("\n")
                if not rec:
                    continue
                items_part, _ = split_sup(rec)
                if items_part:
                    for tok in items_part.split():
                        self._checkMemoryUsage()
                        t = int(tok)
                        if t > self.itemMax:
                            self.itemMax = t
                self.line_count += 1

# ---------------- CLI ----------------

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_input = os.path.join(script_dir, "contextMushroom_FCI90.txt")
    default_output = os.path.join(script_dir, "output_python.txt")

    parser = argparse.ArgumentParser(
        description="DFI-List (Python). Reads FCIs and derives frequent itemsets."
    )
    parser.add_argument("--input", "-i",
                        help=f"Path to input FCI file (default: {default_input} if it exists).",
                        default=None)
    parser.add_argument("--output", "-o",
                        help=f"Output file path (default: {default_output}).",
                        default=default_output)
    args = parser.parse_args()

    if args.input is None:
        if os.path.isfile(default_input):
            input_path = default_input
        else:
            print(f"Error: --input not provided and default '{default_input}' not found.",
                  file=sys.stderr)
            parser.print_help(sys.stderr)
            sys.exit(2)
    else:
        input_path = args.input

    algo = AlgoDFIList()
    algo.runAlgorithm(input_path, args.output)
    algo.printStats()
    print(f"\nDone. Results written to: {os.path.abspath(args.output)}")

if __name__ == "__main__":
    main()
