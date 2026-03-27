from __future__ import annotations

import argparse
import os
import time
from typing import Dict, List, Set, Tuple


# ---------------------------
# Minimal abstract structures
# ---------------------------

class AbstractItemset:
    def size(self) -> int: raise NotImplementedError
    def __str__(self) -> str: raise NotImplementedError
    def print(self) -> None: print(str(self), end="")
    def get_absolute_support(self) -> int: raise NotImplementedError
    def get_relative_support(self, nb_object: int) -> float: raise NotImplementedError
    def contains(self, item: int) -> bool: raise NotImplementedError
    # Java alias
    getAbsoluteSupport = get_absolute_support


class AbstractOrderedItemset(AbstractItemset):
    def get(self, position: int) -> int: raise NotImplementedError
    def get_last_item(self) -> int: return self.get(self.size() - 1)
    def __str__(self) -> str:
        if self.size() == 0: return "EMPTYSET"
        # Java prints a trailing space after each item
        return "".join(f"{self.get(i)} " for i in range(self.size()))
    def get_relative_support(self, nb_object: int) -> float:
        return float(self.get_absolute_support()) / float(nb_object)
    def contains(self, item: int) -> bool:
        for i in range(self.size()):
            v = self.get(i)
            if v == item: return True
            if v > item: return False
        return False
    # Java aliases
    getLastItem = get_last_item
    getRelativeSupport = get_relative_support


# ---------------------------
# Itemset with TID set
# ---------------------------

class Itemset(AbstractOrderedItemset):
    def __init__(self, items: List[int] | None = None):
        self.itemset: List[int] = list(items) if items is not None else []
        self.transactions_ids: Set[int] = set()

    @classmethod
    def from_single(cls, item: int) -> "Itemset":
        return cls([item])

    def getItems(self) -> List[int]: return self.itemset
    def get(self, index: int) -> int: return self.itemset[index]
    def size(self) -> int: return len(self.itemset)
    def get_absolute_support(self) -> int: return len(self.transactions_ids)
    def setTIDs(self, tids: Set[int]) -> None: self.transactions_ids = tids
    def getTransactionsIds(self) -> Set[int]: return self.transactions_ids

    def cloneItemSetMinusAnItemset(self, itemset_to_not_keep: "Itemset") -> "Itemset":
        drop = set(itemset_to_not_keep.itemset)
        return Itemset([v for v in self.itemset if v not in drop])

    def cloneItemSetMinusOneItem(self, item_to_remove: int) -> "Itemset":
        removed = False
        out: List[int] = []
        for v in self.itemset:
            if not removed and v == item_to_remove:
                removed = True
            else:
                out.append(v)
        return Itemset(out)


# ---------------------------
# VME algorithm
# ---------------------------

class AlgoVME:
    def __init__(self) -> None:
        self.mapItemTIDs: Dict[int, Set[int]] = {}         # item -> TIDs
        self.mapTransactionProfit: Dict[int, int] = {}     # tid -> profit
        self.startTimestamp: int = 0
        self.endTimeStamp: int = 0
        self.maxProfitLoss: float = 0.0
        self.overallProfit: float = 0.0
        self.erasableItemsetCount: int = 0
        self.maxItemsetSize: int = (1 << 31) - 1           # Integer.MAX_VALUE
        self._writer = None

    # Java alias
    def setMaximumPatternLength(self, length: int) -> None:
        self.maxItemsetSize = length

    def runAlgorithm(self, input_path: str, output_path: str, threshold: float) -> None:
        self.startTimestamp = int(time.time() * 1000)
        self.erasableItemsetCount = 0
        self.mapItemTIDs.clear()
        self.mapTransactionProfit.clear()
        self.overallProfit = 0.0

        # 1) first scan: sum overall profit and record each transaction profit
        with open(input_path, "r", encoding="utf-8") as f:
            tid = 0
            for raw in f:
                if not raw or raw == "\n": continue
                line = raw.strip()
                if not line or line[0] in "#%@": continue
                toks = line.split()
                profit = int(toks[0])
                self.overallProfit += profit
                self.mapTransactionProfit[tid] = profit
                tid += 1

        # 2) compute max acceptable loss
        self.maxProfitLoss = self.overallProfit * threshold

        # 3) second scan: build item -> tidset
        with open(input_path, "r", encoding="utf-8") as f:
            tid = 0
            for raw in f:
                if not raw or raw == "\n": continue
                line = raw.strip()
                if not line or line[0] in "#%@": continue
                toks = line.split()
                for j in range(1, len(toks)):
                    item = int(toks[j])
                    s = self.mapItemTIDs.get(item)
                    if s is None:
                        s = set()
                        self.mapItemTIDs[item] = s
                    s.add(tid)
                tid += 1

        # 4) prepare output file
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        self._writer = open(output_path, "w", encoding="utf-8", newline="\n")

        # 5) size-1 erasable itemsets (write in lexicographic order)
        level: List[Itemset] = []
        singles_to_write: List[Tuple[Itemset, int]] = []

        for item in sorted(self.mapItemTIDs.keys()):
            tids = self.mapItemTIDs[item]
            loss = sum(self.mapTransactionProfit[tid] for tid in tids)
            if loss <= self.maxProfitLoss and self.maxItemsetSize >= 1:
                iset = Itemset.from_single(item)
                iset.setTIDs(tids)
                level.append(iset)
                singles_to_write.append((iset, loss))

        for iset, loss in singles_to_write:
            self._save_itemset_to_file(iset, loss)

        # Keep lexical order by first item for joining
        level.sort(key=lambda it: it.get(0))

        # 6) generate candidates for k > 1
        k = 2
        while level and k <= self.maxItemsetSize:
            level = self._generate_candidate_size_k(level)
            k += 1

        self._writer.close()
        self._writer = None
        self.endTimeStamp = int(time.time() * 1000)

    def _generate_candidate_size_k(self, levelK_1: List[Itemset]) -> List[Itemset]:
        candidates: List[Itemset] = []
        n = len(levelK_1)

        for i in range(n):
            iset1 = levelK_1[i]
            for j in range(i + 1, n):
                iset2 = levelK_1[j]

                # join condition: same prefix and last1 < last2 (lexical)
                ok = True
                for p in range(iset1.size()):
                    if p == iset1.size() - 1:
                        if iset1.getItems()[p] >= iset2.get(p):
                            ok = False
                            break
                    else:
                        if iset1.getItems()[p] < iset2.get(p):
                            ok = None  # different prefix; try next j
                            break
                        elif iset1.getItems()[p] > iset2.get(p):
                            ok = False  # order prevents later matches
                            break
                if ok is None:      # different prefix
                    continue
                if not ok:          # not joinable
                    continue

                # join
                new_items = list(iset1.getItems()) + [iset2.get(iset2.size() - 1)]
                union_tids = set(iset1.getTransactionsIds())
                union_tids.update(iset2.getTransactionsIds())
                loss = sum(self.mapTransactionProfit[tid] for tid in union_tids)

                if loss <= self.maxProfitLoss:
                    cand = Itemset(new_items)
                    cand.setTIDs(union_tids)
                    candidates.append(cand)
                    self._save_itemset_to_file(cand, loss)

        candidates.sort(key=lambda it: it.get(0))
        return candidates

    def _save_itemset_to_file(self, itemset: Itemset, loss: int) -> None:
        # EXACT Java format: itemset string ends with a space
        # and we add another leading space before "#LOSS:", hence TWO spaces.
        self._writer.write(f"{str(itemset)} #LOSS: {loss}\n")
        self.erasableItemsetCount += 1

    def printStats(self) -> None:
        print("=============  VME - STATS =============")
        dur = self.endTimeStamp - self.startTimestamp
        print(f"Overall profit: {self.overallProfit}")
        print(f"Maximum profit loss (over. profit x treshold): {self.maxProfitLoss}")
        print(f" Erasable itemset count : {self.erasableItemsetCount}")
        print(f" Total time ~ {dur} ms")
        print("========================================")


# ---------------------------
# CLI (auto I/O like Java)
# ---------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="VME erasable itemsets (SPMF) – Python")
    p.add_argument("input", nargs="?", help="Input file (default: contextVME.txt beside script)")
    p.add_argument("output", nargs="?", help="Output file (default: output.txt beside script)")
    p.add_argument("--threshold", type=float, default=0.15, help="Threshold (default: 0.15)")
    p.add_argument("--maxlen", type=int, default=None, help="Max itemset size (optional)")
    return p


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # default to files next to this script (Java-style)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = args.input or os.path.join(script_dir, "contextVME.txt")
    output_path = args.output or os.path.join(script_dir, "output_py.txt")

    algo = AlgoVME()
    if args.maxlen is not None:
        algo.setMaximumPatternLength(args.maxlen)

    algo.runAlgorithm(input_path, output_path, args.threshold)
    algo.printStats()
    print(f"Wrote: {output_path}")


if __name__ == "__main__":
    main()
