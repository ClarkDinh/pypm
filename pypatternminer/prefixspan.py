from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

try:
    import psutil
    _psutil_available = True
except Exception:
    _psutil_available = False


SequenceType = List[List[int]]
Position = Tuple[int, int]  # (itemset_idx, item_idx)
ProjectedEntry = Tuple[SequenceType, List[Position]]


class SequenceDatabase:
    def __init__(self, path: Path) -> None:
        self.sequences: List[SequenceType] = []
        self._load(path)

    def __str__(self) -> str:
        lines: List[str] = []
        for idx, seq in enumerate(self.sequences, start=1):
            parts: List[str] = []
            for t, itemset in enumerate(seq):
                parts.append("{t=" + str(t) + ", " + " ".join(str(i) for i in itemset) + " }")
            lines.append(f"{idx}:  " + "".join(parts))
        return "\n".join(lines)

    def _load(self, path: Path) -> None:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line[0] in "#%@":
                continue
            self.sequences.append(parse_sequence(line))


def parse_sequence(line: str) -> SequenceType:
    itemsets: List[List[int]] = []
    current: List[int] = []
    for token in line.split():
        if token == "-1":
            if current:
                itemsets.append(current)
                current = []
        elif token == "-2":
            break
        else:
            current.append(int(token))
    if current:
        itemsets.append(current)
    return itemsets


def pattern_to_str(pattern: SequenceType) -> str:
    parts: List[str] = []
    for itemset in pattern:
        parts.extend(str(i) for i in itemset)
        parts.append("-1")
    return " ".join(parts)


class PrefixSpan:
    def __init__(self, minsup_rel: float) -> None:
        self.minsup_rel = minsup_rel
        self.patterns: Dict[Tuple[Tuple[int, ...], ...], int] = {}
        self.abs_minsup = 0
        self.total_time_ms: float = 0.0

    def run(self, sequences: List[SequenceType]) -> None:
        start = time.time()
        self.abs_minsup = max(1, math.ceil(self.minsup_rel * len(sequences)))
        projected_db: List[ProjectedEntry] = [(seq, [(-1, -1)]) for seq in sequences]
        self._prefixspan([], projected_db)
        self.total_time_ms = (time.time() - start) * 1000

    def _prefixspan(self, prefix: SequenceType, projected_db: List[ProjectedEntry]) -> None:
        # collect frequent i-extensions
        i_counts: Dict[int, Set[int]] = {}
        for sid, (seq, positions) in enumerate(projected_db):
            for iset_idx, item_idx in positions:
                if iset_idx == -1:
                    continue
                itemset = seq[iset_idx]
                for pos in range(item_idx + 1, len(itemset)):
                    item = itemset[pos]
                    i_counts.setdefault(item, set()).add(sid)
        # collect frequent s-extensions
        s_counts: Dict[int, Set[int]] = {}
        for sid, (seq, positions) in enumerate(projected_db):
            seen_items: Set[int] = set()
            for iset_idx, _ in positions:
                start_iset = iset_idx + 1
                for idx in range(start_iset, len(seq)):
                    for item in seq[idx]:
                        seen_items.add(item)
                # no break; gather all reachable items
            for item in seen_items:
                s_counts.setdefault(item, set()).add(sid)

        # process i-extensions
        for item, sids in sorted(i_counts.items()):
            sup = len(sids)
            if sup < self.abs_minsup:
                continue
            new_prefix = [iset[:] for iset in prefix]
            new_prefix[-1].append(item)
            key = tuple(tuple(iset) for iset in new_prefix)
            self.patterns[key] = sup
            new_projected = self._project(projected_db, item, same_itemset=True)
            self._prefixspan(new_prefix, new_projected)

        # process s-extensions
        for item, sids in sorted(s_counts.items()):
            sup = len(sids)
            if sup < self.abs_minsup:
                continue
            new_prefix = [iset[:] for iset in prefix]
            new_prefix.append([item])
            key = tuple(tuple(iset) for iset in new_prefix)
            self.patterns[key] = sup
            new_projected = self._project(projected_db, item, same_itemset=False)
            self._prefixspan(new_prefix, new_projected)

    def _project(self, projected_db: List[ProjectedEntry], item: int, same_itemset: bool) -> List[ProjectedEntry]:
        new_db: List[ProjectedEntry] = []
        for seq, positions in projected_db:
            new_positions: List[Position] = []
            for iset_idx, item_idx in positions:
                if same_itemset:
                    if iset_idx == -1:
                        continue
                    itemset = seq[iset_idx]
                    for pos in range(item_idx + 1, len(itemset)):
                        if itemset[pos] == item:
                            new_positions.append((iset_idx, pos))
                            break
                else:
                    start_iset = iset_idx + 1
                    found = False
                    for idx in range(start_iset, len(seq)):
                        for pos, val in enumerate(seq[idx]):
                            if val == item:
                                new_positions.append((idx, pos))
                                found = True
                                break
                        if found:
                            # continue searching for other occurrences to allow more i-extensions
                            continue
            if new_positions:
                new_db.append((seq, new_positions))
        return new_db


def main() -> None:
    base = Path(__file__).resolve().parent
    input_path = base / "contextPrefixSpan.txt"
    output_path = base / "outputs.txt"

    db = SequenceDatabase(input_path)
    algo = PrefixSpan(minsup_rel=0.3)

    print(db)
    algo.run(db.sequences)

    # sort patterns for deterministic output
    sorted_patterns = sorted(
        algo.patterns.items(),
        key=lambda kv: pattern_to_str([list(iset) for iset in kv[0]])
    )
    lines = [f"{pattern_to_str([list(iset) for iset in pat])} #SUP: {sup}" for pat, sup in sorted_patterns]
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n{len(lines)} patterns found.")
    print("=============  Algorithm - STATISTICS =============")
    print(f" Total time ~ {int(algo.total_time_ms)} ms")
    print(f" Frequent sequences count : {len(lines)}")
    max_mem = 0.0
    if _psutil_available:
        try:
            process = psutil.Process()
            max_mem = process.memory_info().rss / 1024 / 1024
        except Exception:
            max_mem = 0.0
    print(f" Max memory (mb):{max_mem}")
    print(f"Content at file {output_path}")
    print("===================================================")


if __name__ == "__main__":
    main()
