from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import sys
import time
import math
import tracemalloc
import pathlib
import os


# ---------------------------
# MemoryLogger (Python)
# ---------------------------

class MemoryLogger:
    """Tracks peak memory usage (MB) using tracemalloc (Python standard)."""
    _instance: "MemoryLogger" | None = None

    def __init__(self) -> None:
        self._max_mb = 0.0
        self._started = False

    @classmethod
    def getInstance(cls) -> "MemoryLogger":
        if cls._instance is None:
            cls._instance = MemoryLogger()
        return cls._instance

    def reset(self) -> None:
        self._max_mb = 0.0
        if self._started:
            tracemalloc.stop()
        tracemalloc.start()
        self._started = True

    def getMaxMemory(self) -> float:
        return self._max_mb

    def checkMemory(self) -> float:
        if not self._started:
            return 0.0
        current, peak = tracemalloc.get_traced_memory()
        cur_mb = current / 1024.0 / 1024.0
        peak_mb = peak / 1024.0 / 1024.0
        if peak_mb > self._max_mb:
            self._max_mb = peak_mb
        return cur_mb


# ---------------------------
# Regions (membership functions)
# ---------------------------

class Regions:
    """Compute low / middle / high fuzzy membership for a quantity."""
    def __init__(self, quantity: int, regionsNumber: int) -> None:
        self.low: float = 0.0
        self.middle: float = 0.0
        self.high: float = 0.0

        if regionsNumber == 3:
            if 0 < quantity <= 1:
                self.low, self.middle, self.high = 1.0, 0.0, 0.0
            elif 1 <= quantity < 6:
                self.low = -0.2 * quantity + 1.2
                self.middle = 0.2 * quantity - 0.2
                self.high = 0.0
            elif 6 <= quantity < 11:
                self.low = 0.0
                self.middle = -0.2 * quantity + 2.2
                self.high = 0.2 * quantity - 1.2
            else:
                self.low, self.middle, self.high = 0.0, 0.0, 1.0
        elif regionsNumber == 2:
            self.middle = 0.0
            if 0 < quantity <= 1:
                self.low, self.high = 1.0, 0.0
            elif 1 < quantity <= 11:
                self.low = -0.1 * quantity + 1.1
                self.high = 0.1 * quantity - 0.1
            else:
                self.low, self.high = 0.0, 1.0


# ---------------------------
# Element & FFIList
# ---------------------------

@dataclass(frozen=True)
class Element:
    tid: int
    iutils: float
    rutils: float


class FFIList:
    """Fuzzy list as used by the FFI-Miner algorithm."""
    def __init__(self, item: int) -> None:
        self.item: int = item
        self.sumIutils: float = 0.0
        self.sumRutils: float = 0.0
        self.elements: List[Element] = []

    def addElement(self, element: Element) -> None:
        self.sumIutils += element.iutils
        self.sumRutils += element.rutils
        self.elements.append(element)


# ---------------------------
# AlgoFFIMiner
# ---------------------------

@dataclass
class _Pair:
    item: int
    quantity: float


class AlgoFFIMiner:
    def __init__(self) -> None:
        # stats
        self.startTimestamp: int = 0
        self.endTimestamp: int = 0
        self.FFICount: int = 0
        self._joinCount: int = 0

        # maps
        self.mapItemLowSUM: Dict[int, float] = {}
        self.mapItemMiddleSUM: Dict[int, float] = {}
        self.mapItemHighSUM: Dict[int, float] = {}
        self.mapItemSUM: Dict[int, float] = {}
        self.mapItemRegion: Dict[int, str] = {}

        # buffers
        self._itemsetBufferSize = 200
        self._itemsetBuffer: List[int] = [0] * self._itemsetBufferSize

        # writer (set during mining)
        self._writer = None

    # ---------- API ----------

    def runAlgorithm(self, input_path: str, output_path: str, minSupport: float) -> None:
        MemoryLogger.getInstance().reset()
        self._itemsetBuffer = [0] * self._itemsetBufferSize
        self.startTimestamp = int(time.time() * 1000)

        # pass 1: compute low/middle/high sums
        self._first_pass(input_path)

        # prepare frequent 1-item fuzzy lists
        listOfFFILists, mapItemToFFIList = self._prepare_lists(minSupport)

        # pass 2: build utility lists for promising items
        self._second_pass(input_path, mapItemToFFIList, minSupport)

        MemoryLogger.getInstance().checkMemory()

        # mine recursively and write out
        with open(output_path, "w", encoding="utf-8") as f:
            self._writer = f
            self._FFIMiner(self._itemsetBuffer, 0, listOfFFILists, minSupport)

        MemoryLogger.getInstance().checkMemory()
        self.endTimestamp = int(time.time() * 1000)

    def printStats(self) -> None:
        print("=============  FFI-MINER (Python) - STATS =============")
        print(f" Total time ~ {self.endTimestamp - self.startTimestamp} ms")
        print(f" Memory ~ {MemoryLogger.getInstance().getMaxMemory():.2f} MB")
        print(f" FFI count : {self.FFICount}")
        print(f" Join count : {self._joinCount}")
        print("=======================================================")

    # ---------- internal ----------

    def _first_pass(self, input_path: str) -> None:
        self.mapItemLowSUM.clear()
        self.mapItemMiddleSUM.clear()
        self.mapItemHighSUM.clear()

        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in ("#", "%", "@"):
                    continue
                split = line.split(":")
                if len(split) < 3:
                    # skip malformed lines safely
                    continue
                items = split[0].split()
                quantities = split[2].split()
                if len(items) != len(quantities):
                    # skip if counts mismatch
                    continue

                for i in range(len(items)):
                    item = int(items[i])
                    regions = Regions(int(quantities[i]), 3)
                    self.mapItemLowSUM[item] = self.mapItemLowSUM.get(item, 0.0) + regions.low
                    self.mapItemMiddleSUM[item] = self.mapItemMiddleSUM.get(item, 0.0) + regions.middle
                    self.mapItemHighSUM[item] = self.mapItemHighSUM.get(item, 0.0) + regions.high

    def _prepare_lists(self, minSupport: float) -> Tuple[List[FFIList], Dict[int, FFIList]]:
        self.mapItemSUM.clear()
        self.mapItemRegion.clear()

        listOfFFILists: List[FFIList] = []
        mapItemToFFIList: Dict[int, FFIList] = {}

        for item in self.mapItemLowSUM.keys():
            low = self.mapItemLowSUM.get(item, 0.0)
            middle = self.mapItemMiddleSUM.get(item, 0.0)
            high = self.mapItemHighSUM.get(item, 0.0)

            if low >= middle and low >= high:
                self.mapItemSUM[item] = low
                self.mapItemRegion[item] = "L"
            elif middle >= low and middle >= high:
                self.mapItemSUM[item] = middle
                self.mapItemRegion[item] = "M"
            else:
                self.mapItemSUM[item] = high
                self.mapItemRegion[item] = "H"

            if self.mapItemSUM[item] >= minSupport:
                ul = FFIList(item)
                mapItemToFFIList[item] = ul
                listOfFFILists.append(ul)

        # sort ascending by SUM then item id (lexical), like Java compareItems
        listOfFFILists.sort(key=lambda ul: (self.mapItemSUM[ul.item], ul.item))
        return listOfFFILists, mapItemToFFIList

    def _second_pass(self, input_path: str, mapItemToFFIList: Dict[int, FFIList], minSupport: float) -> 4:
        tid = 0
        with open(input_path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line[0] in ("#", "%", "@"):
                    continue
                split = line.split(":")
                if len(split) < 3:
                    continue
                items = split[0].split()
                quantities = split[2].split()
                if len(items) != len(quantities):
                    continue

                revised: List[_Pair] = []
                for i in range(len(items)):
                    item = int(items[i])
                    regions = Regions(int(quantities[i]), 3)
                    if self.mapItemSUM.get(item, 0.0) >= minSupport:
                        region = self.mapItemRegion[item]
                        qty = regions.low if region == "L" else (regions.middle if region == "M" else regions.high)
                        if qty > 0.0:
                            revised.append(_Pair(item=item, quantity=qty))

                # ascending order by (SUM, item id)
                revised.sort(key=lambda p: (self.mapItemSUM[p.item], p.item))

                remainingUtility = -math.inf
                for idx in range(len(revised) - 1, -1, -1):
                    pair = revised[idx]
                    remainingUtility = max(pair.quantity, remainingUtility)
                    ulist = mapItemToFFIList[pair.item]
                    ulist.addElement(Element(tid=tid, iutils=pair.quantity, rutils=remainingUtility))

                tid += 1

    def _FFIMiner(self, prefix: List[int], prefixLength: int, FFILs: List[FFIList], minSupport: float) -> None:
        for i in range(len(FFILs)):
            X = FFILs[i]

            if X.sumIutils >= minSupport:
                self._writeOut(prefix, prefixLength, X.item, X.sumIutils)

            if X.sumRutils >= minSupport:
                extensions: List[FFIList] = []
                for j in range(i + 1, len(FFILs)):
                    Y = FFILs[j]
                    extensions.append(self._construct(X, Y))
                    self._joinCount += 1

                self._itemsetBuffer[prefixLength] = X.item
                self._FFIMiner(self._itemsetBuffer, prefixLength + 1, extensions, minSupport)

    def _construct(self, px: FFIList, py: FFIList) -> FFIList:
        pxy = FFIList(py.item)
        for ex in px.elements:
            ey = self._find_by_tid(py, ex.tid)
            if ey is None:
                continue
            eXY = Element(tid=ex.tid, iutils=min(ex.iutils, ey.iutils), rutils=ey.rutils)
            pxy.addElement(eXY)
        return pxy

    def _find_by_tid(self, ulist: FFIList, tid: int) -> Optional[Element]:
        lst = ulist.elements
        lo, hi = 0, len(lst) - 1
        while lo <= hi:
            mid = (lo + hi) >> 1
            mt = lst[mid].tid
            if mt < tid:
                lo = mid + 1
            elif mt > tid:
                hi = mid - 1
            else:
                return lst[mid]
        return None

    def _writeOut(self, prefix: List[int], prefixLength: int, item: int, sumIutils: float) -> None:
        self.FFICount += 1
        parts: List[str] = []
        for i in range(prefixLength):
            pi = prefix[i]
            parts.append(f"{pi}.{self.mapItemRegion[pi]}")
        parts.append(f"{item}.{self.mapItemRegion[item]}")
        line = f"{' '.join(parts)} #FVL: {sumIutils}"
        assert self._writer is not None, "Writer not initialized"
        self._writer.write(line + "\n")


# ---------------------------
# CLI (uses script directory as default)
# ---------------------------

def _default_paths_for_demo() -> Tuple[str, str, float]:
    """Defaults relative to the script location (not CWD)."""
    here = pathlib.Path(__file__).resolve().parent
    input_path = str(here / "contextFFIMiner.txt")
    output_path = str(here / "output_python.txt")
    return input_path, output_path, 1.0


def main(argv: List[str]) -> None:
    if len(argv) == 1:
        input_path, output_path, min_support_str = argv
        min_support = float(min_support_str)
    else:
        input_path, output_path, min_support = _default_paths_for_demo()
        print("Usage: python AlgoFFIMiner.py <input_file> <output_file> <min_support>")
        print(f"(no args given; running with defaults)\n  input  = {input_path}\n  output = {output_path}\n  minsup = {min_support}\n")

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    algo = AlgoFFIMiner()
    algo.runAlgorithm(input_path, output_path, 1.0)
    algo.printStats()


if __name__ == "__main__":
    main(sys.argv[1:])
