# AlgoMFFIMiner.py
# Python port of the MFFI-Miner implementation (original Java by Ting Li, 2016).
# The algorithm mines Multiple Fuzzy Frequent Itemsets (L/M/H) from a transactional dataset.

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import time
import tracemalloc
import argparse
import sys
import struct
import functools


def _f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def _format_float32(value: float) -> str:
    text = format(_f32(value), ".8g")
    if "." not in text and "e" not in text and "E" not in text:
        text += ".0"
    return text


def _java_hash(key: int) -> int:
    h = key & 0xFFFFFFFF
    return (h ^ (h >> 16)) & 0xFFFFFFFF


def _java_hashmap_iteration_order(keys: List[int]) -> List[int]:
    capacity = 16
    load_factor = 0.75
    threshold = int(capacity * load_factor)
    table: List[List[int]] = [[] for _ in range(capacity)]
    size = 0

    def put(k: int) -> None:
        nonlocal capacity, threshold, table, size
        idx = _java_hash(k) & (capacity - 1)
        bucket = table[idx]
        if k in bucket:
            return
        bucket.append(k)
        size += 1
        if size > threshold:
            old_table = table
            capacity *= 2
            threshold = int(capacity * load_factor)
            table = [[] for _ in range(capacity)]
            for old_bucket in old_table:
                for key in old_bucket:
                    idx2 = _java_hash(key) & (capacity - 1)
                    table[idx2].append(key)

    for key in keys:
        put(key)

    order: List[int] = []
    for bucket in table:
        order.extend(bucket)
    return order


# -------------------------------
# MemoryLogger (singleton style)
# -------------------------------

class MemoryLogger:
    """Simple memory logger using tracemalloc to approximate Java's Runtime memory checks."""
    _instance: "MemoryLogger" | None = None

    def __init__(self) -> None:
        self._max_mb: float = 0.0
        self._tracing: bool = False

    @classmethod
    def getInstance(cls) -> "MemoryLogger":
        if cls._instance is None:
            cls._instance = MemoryLogger()
        return cls._instance

    def reset(self) -> None:
        self._max_mb = 0.0
        if not self._tracing:
            tracemalloc.start()
            self._tracing = True

    def checkMemory(self) -> float:
        if not self._tracing:
            tracemalloc.start()
            self._tracing = True
        current, peak = tracemalloc.get_traced_memory()
        current_mb = current / 1024.0 / 1024.0
        peak_mb = peak / 1024.0 / 1024.0
        if peak_mb > self._max_mb:
            self._max_mb = peak_mb
        return current_mb

    def getMaxMemory(self) -> float:
        return self._max_mb


# -------------------------------
# Core data classes
# -------------------------------

@dataclass(frozen=True)
class Element:
    """Element of a fuzzy list."""
    tid: int          # transaction id
    iutils: float     # itemset utility (here: fuzzy value of the itemset)
    rutils: float     # remaining utility (max fuzzy value to the right)


@dataclass
class MFFIList:
    """Represents a fuzzy list for one (fuzzy) item."""
    item: int
    sumIutils: float = 0.0
    sumRutils: float = 0.0
    elements: List[Element] | None = None

    def __post_init__(self) -> None:
        self.sumIutils = _f32(self.sumIutils)
        self.sumRutils = _f32(self.sumRutils)
        if self.elements is None:
            self.elements = []

    def addElement(self, element: Element) -> None:
        self.sumIutils = _f32(self.sumIutils + element.iutils)
        self.sumRutils = _f32(self.sumRutils + element.rutils)
        self.elements.append(element)


class MFFIRegions:
    """Triangular membership (low, middle, high) exactly as in the original Java code."""
    def __init__(self, quantity: int) -> None:
        if 0 <= quantity <= 1:
            self.low = _f32(1.0)
            self.middle = _f32(0.0)
            self.high = _f32(0.0)
        elif quantity == 2:
            self.low = _f32(0.5)
            self.middle = _f32(0.6666667)
            self.high = _f32(0.0)
        elif quantity == 3:
            self.low = _f32(0.0)
            self.middle = _f32(0.6666667)
            self.high = _f32(0.5)
        else:
            self.low = _f32(0.0)
            self.middle = _f32(0.0)
            self.high = _f32(1.0)


@dataclass
class _Pair:
    item: int = 0
    quantity: float = 0.0


# -------------------------------
# Algorithm
# -------------------------------

class AlgoMFFIMiner:
    """
    Python translation of the MFFI-Miner algorithm.
    Input file format (per line):
        "i1 i2 i3 : (ignored middle) : q1 q2 q3"
    Comments/metadata lines starting with #, %, @ are ignored.
    """

    def __init__(self) -> None:
        self.startTimestamp: int = 0
        self.endTimestamp: int = 0
        self.MFFICount: int = 0
        self.joinCount: int = 0

        self.mapItemLowSUM: Dict[int, float] = {}
        self.mapItemMiddleSUM: Dict[int, float] = {}
        self.mapItemHighSUM: Dict[int, float] = {}
        self.mapItemSUM: Dict[int, float] = {}
        self._item_insert_order: List[int] = []

        self._buffer_size = 200
        self.itemsetBuffer: List[int] = [0] * self._buffer_size

        self._out_file = None  # set when writing

    # ---------- Public API ----------

    def runAlgorithm(self, input_path: str, output_path: str, minSupport: float) -> None:
        """Run the miner end-to-end."""
        minSupport = _f32(minSupport)
        MemoryLogger.getInstance().reset()
        self.startTimestamp = int(time.time() * 1000)

        # 1) First pass: compute (low, middle, high) sums per raw item
        self._first_pass(input_path)

        # 2) Build fuzzy items (L/M/H encodings) that meet minSupport
        listOfFFILists, mapItemToFFIList = self._prepare_fuzzy_items(minSupport)

        # 3) Second pass: construct the fuzzy lists (1-itemsets)
        self._second_pass(input_path, listOfFFILists, mapItemToFFIList)

        MemoryLogger.getInstance().checkMemory()

        # 4) Recursive mining
        with open(output_path, "w", encoding="utf-8") as f:
            self._out_file = f
            self.MFFIMiner(self.itemsetBuffer, 0, listOfFFILists, minSupport)

        MemoryLogger.getInstance().checkMemory()
        self.endTimestamp = int(time.time() * 1000)

    def printStats(self) -> None:
        print("=============  MFFI-MINER ALGORITHM - STATS =============")
        print(f" Total time ~ {self.endTimestamp - self.startTimestamp} ms")
        print(f" Memory ~ {MemoryLogger.getInstance().getMaxMemory():.2f} MB")
        print(f" MFFI count : {self.MFFICount}")
        print(f" Join count : {self.joinCount}")
        print("===================================================")

    # ---------- Internal steps ----------

    def _first_pass(self, input_path: str) -> None:
        self.mapItemLowSUM.clear()
        self.mapItemMiddleSUM.clear()
        self.mapItemHighSUM.clear()
        self._item_insert_order = []

        with open(input_path, "r", encoding="utf-8") as fin:
            for raw_line in fin:
                line = raw_line.strip()
                if not line or line[0] in "#%@":
                    continue
                split = line.split(":")
                if len(split) < 3:
                    # Skip malformed lines safely
                    continue
                items = split[0].split()
                quantities = split[2].split()
                if len(items) != len(quantities):
                    # Skip inconsistent lines
                    continue

                for i in range(len(items)):
                    item = int(items[i])
                    regions = MFFIRegions(int(quantities[i]))

                    if item not in self.mapItemLowSUM:
                        self._item_insert_order.append(item)

                    self.mapItemLowSUM[item] = _f32(self.mapItemLowSUM.get(item, 0.0) + regions.low)
                    self.mapItemMiddleSUM[item] = _f32(self.mapItemMiddleSUM.get(item, 0.0) + regions.middle)
                    self.mapItemHighSUM[item] = _f32(self.mapItemHighSUM.get(item, 0.0) + regions.high)

    def _prepare_fuzzy_items(self, minSupport: float) -> Tuple[List[MFFIList], Dict[int, MFFIList]]:
        listOfFFILists: List[MFFIList] = []
        mapItemToFFIList: Dict[int, MFFIList] = {}
        self.mapItemSUM.clear()

        items_in_order = _java_hashmap_iteration_order(self._item_insert_order)
        for item in items_in_order:
            if item not in self.mapItemLowSUM:
                continue
            low = self.mapItemLowSUM[item]
            mid = self.mapItemMiddleSUM.get(item, _f32(0.0))
            high = self.mapItemHighSUM.get(item, _f32(0.0))

            if low >= minSupport:
                code = item * 100 + 12
                self.mapItemSUM[code] = _f32(low)
                ful = MFFIList(code)
                mapItemToFFIList[code] = ful
                listOfFFILists.append(ful)

            if mid >= minSupport:
                code = item * 1000 + 123
                self.mapItemSUM[code] = _f32(mid)
                ful = MFFIList(code)
                mapItemToFFIList[code] = ful
                listOfFFILists.append(ful)

            if high >= minSupport:
                code = item * 10000 + 1234
                self.mapItemSUM[code] = _f32(high)
                ful = MFFIList(code)
                mapItemToFFIList[code] = ful
                listOfFFILists.append(ful)

        listOfFFILists.sort(
            key=functools.cmp_to_key(lambda a, b: self._compare_item_codes(a.item, b.item))
        )
        return listOfFFILists, mapItemToFFIList

    def _second_pass(
        self,
        input_path: str,
        listOfFFILists: List[MFFIList],
        mapItemToFFIList: Dict[int, MFFIList],
    ) -> None:
        with open(input_path, "r", encoding="utf-8") as fin:
            tid = 0
            for raw_line in fin:
                line = raw_line.strip()
                if not line or line[0] in "#%@":
                    continue

                split = line.split(":")
                if len(split) < 3:
                    tid += 1
                    continue
                items = split[0].split()
                quantities = split[2].split()
                if len(items) != len(quantities):
                    tid += 1
                    continue

                revised: List[_Pair] = []
                for i in range(len(items)):
                    item = int(items[i])
                    reg = MFFIRegions(int(quantities[i]))

                    code = item * 100 + 12
                    if code in self.mapItemSUM and reg.low > 0:
                        revised.append(_Pair(code, reg.low))

                    code = item * 1000 + 123
                    if code in self.mapItemSUM and reg.middle > 0:
                        revised.append(_Pair(code, reg.middle))

                    code = item * 10000 + 1234
                    if code in self.mapItemSUM and reg.high > 0:
                        revised.append(_Pair(code, reg.high))

                # sort by compareItems (ascending)
                revised.sort(
                    key=functools.cmp_to_key(
                        lambda p1, p2: self._compare_item_codes(p1.item, p2.item)
                    )
                )

                remaining_utility = _f32(-2147483648.0)
                # iterate from right to left
                for idx in range(len(revised) - 1, -1, -1):
                    pair = revised[idx]
                    if pair.quantity > remaining_utility:
                        remaining_utility = pair.quantity
                    remaining_utility = _f32(remaining_utility)
                    ulist = mapItemToFFIList[pair.item]
                    element = Element(tid, pair.quantity, remaining_utility)
                    ulist.addElement(element)

                tid += 1

    # ---------- Mining ----------

    def MFFIMiner(self, prefix: List[int], prefixLength: int,
                  FFILs: List[MFFIList], minSupport: float) -> None:
        for i in range(len(FFILs)):
            X = FFILs[i]

            # If pX is a fuzzy frequent itemset, output it
            if X.sumIutils >= minSupport:
                self._writeOut(prefix, prefixLength, X.item, X.sumIutils)

            xitem = self._decode_base_item(X.item)

            # Prune using remaining utility
            if X.sumRutils >= minSupport:
                exULs: List[MFFIList] = []
                for j in range(i + 1, len(FFILs)):
                    Y = FFILs[j]
                    yitem = self._decode_base_item(Y.item)
                    if xitem == yitem:
                        continue
                    exULs.append(self._construct(X, Y))
                    self.joinCount += 1

                self.itemsetBuffer[prefixLength] = X.item
                self.MFFIMiner(self.itemsetBuffer, prefixLength + 1, exULs, minSupport)

    # ---------- Helpers ----------

    def _compare_item_codes(self, item1: int, item2: int) -> int:
        compare = _f32(self.mapItemSUM[item1] - self.mapItemSUM[item2])
        if compare == 0.0:
            return item1 - item2
        return int(compare)

    def _decode_base_item(self, code: int) -> int:
        if code % 10000 == 1234:
            return code // 10000
        elif code % 1000 == 123:
            return code // 1000
        elif code % 100 == 12:
            return code // 100
        return code  # fallback (shouldn't happen)

    def _construct(self, px: MFFIList, py: MFFIList) -> MFFIList:
        pxy = MFFIList(py.item)
        # py.elements are sorted by tid because we added in ascending tid order
        for ex in px.elements:
            ey = self._findElementWithTID(py, ex.tid)
            if ey is None:
                continue
            eXY = Element(ex.tid, _f32(min(ex.iutils, ey.iutils)), ey.rutils)
            pxy.addElement(eXY)
        return pxy

    def _findElementWithTID(self, ulist: MFFIList, tid: int) -> Optional[Element]:
        lst = ulist.elements
        first, last = 0, len(lst) - 1
        while first <= last:
            mid = (first + last) >> 1
            mid_tid = lst[mid].tid
            if mid_tid < tid:
                first = mid + 1
            elif mid_tid > tid:
                last = mid - 1
            else:
                return lst[mid]
        return None

    def _writeOut(self, prefix: List[int], prefixLength: int, item: int, sumIutils: float) -> None:
        self.MFFICount += 1
        parts: List[str] = []
        for i in range(prefixLength):
            parts.append(self._format_item(prefix[i]))
        parts.append(self._format_item(item))
        line = "{} #SUP: {}".format(" ".join(parts), _format_float32(sumIutils))
        assert self._out_file is not None, "Output file handle not set"
        self._out_file.write(line + "\n")

    def _format_item(self, code: int) -> str:
        if code % 10000 == 1234:
            return f"{code // 10000}.H"
        elif code % 1000 == 123:
            return f"{code // 1000}.M"
        elif code % 100 == 12:
            return f"{code // 100}.L"
        return str(code)


# -------------------------------
# CLI entry point
# -------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="MFFI-Miner (Python). Mines Multiple Fuzzy Frequent Itemsets from a dataset."
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default=None,
        help="Path to input dataset file (default: contextMFFIMiner.txt next to this script).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Path to output file (default: output_python.txt next to the script).",
    )
    parser.add_argument(
        "--min-support",
        "-s",
        type=float,
        default=1.0,
        help="Minimum support threshold (float). Default: 1.0",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    input_path = Path(args.input) if args.input else (script_dir / "contextMFFIMiner.txt")
    output_path = Path(args.output) if args.output else (script_dir / "output_python.txt")

    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    miner = AlgoMFFIMiner()
    miner.runAlgorithm(str(input_path), str(output_path), float(args.min_support))
    miner.printStats()
    print(f"Output written to: {output_path}")

if __name__ == "__main__":
    main()
