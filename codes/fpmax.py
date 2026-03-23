import collections
import math
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix


class FPNode:
    def __init__(self, item, count=0, parent=None):
        self.item = item
        self.count = count
        self.parent = parent
        self.children = {}

        if parent is not None:
            parent.children[item] = self

    def itempath_from_root(self):
        path = []
        node = self.parent
        while node.item is not None:
            path.append(node.item)
            node = node.parent

        path.reverse()
        return path


class FPTree:
    def __init__(self, rank=None):
        self.root = FPNode(None)
        self.nodes = collections.defaultdict(list)
        self.cond_items = []
        self.rank = rank

    def conditional_tree(self, cond_item, minsup):
        branches = []
        count = collections.defaultdict(int)
        for node in self.nodes[cond_item]:
            branch = node.itempath_from_root()
            branches.append(branch)
            for item in branch:
                count[item] += node.count

        items = [item for item in count if count[item] >= minsup]
        items.sort(key=count.get)
        rank = {item: i for i, item in enumerate(items)}

        cond_tree = FPTree(rank)
        for idx, branch in enumerate(branches):
            branch = sorted([i for i in branch if i in rank], key=rank.get, reverse=True)
            cond_tree.insert_itemset(branch, self.nodes[cond_item][idx].count)
        cond_tree.cond_items = self.cond_items + [cond_item]

        return cond_tree

    def insert_itemset(self, itemset, count=1):
        node = self.root
        node.count += count

        for item in itemset:
            if item in node.children:
                child = node.children[item]
                child.count += count
                node = child
            else:
                child_node = FPNode(item, count, node)
                self.nodes[item].append(child_node)
                node = child_node

    def is_path(self):
        return len(self.root.children) <= 1 and all(
            len(self.nodes[i]) <= 1 and not self.nodes[i][0].children for i in self.nodes
        )

    def print_status(self, count, colnames):
        cond_items = [str(colnames[i]) for i in self.cond_items]
        cond_items = ", ".join(cond_items)
        print(
            f"\r{count} itemset(s) from tree conditioned on items ({cond_items})",
            end="\n",
        )


class MFITree:
    class Node:
        def __init__(self, item, count=1, parent=None):
            self.item = item
            self.parent = parent
            self.children = {}

            if parent is not None:
                parent.children[item] = self

    def __init__(self, rank):
        self.root = self.Node(None)
        self.nodes = collections.defaultdict(list)
        self.cache = []
        self.rank = rank

    def insert_itemset(self, itemset, count=1):
        node = self.root
        for item in itemset:
            if item in node.children:
                node = node.children[item]
            else:
                child_node = self.Node(item, count, node)
                self.nodes[item].append(child_node)
                node = child_node

    def contains(self, itemset):
        i = 0
        for item in reversed(self.cache):
            if self.rank[itemset[i]] < self.rank[item]:
                break
            if itemset[i] == item:
                i += 1
            if i == len(itemset):
                return True

        for basenode in self.nodes[itemset[0]]:
            i = 0
            node = basenode
            while node.item is not None:
                if self.rank[itemset[i]] < self.rank[node.item]:
                    break
                if itemset[i] == node.item:
                    i += 1
                if i == len(itemset):
                    return True
                node = node.parent

        return False


def setup_fptree(df, min_support):
    num_itemsets = len(df)
    is_sparse = hasattr(df, "sparse")
    if is_sparse:
        itemsets = df.sparse.to_coo().tocsr()
    else:
        itemsets = df.values

    item_support = np.array(np.sum(itemsets, axis=0) / num_itemsets).reshape(-1)
    items = np.nonzero(item_support >= min_support)[0]
    indices = item_support[items].argsort()
    rank = {item: i for i, item in enumerate(items[indices])}

    if is_sparse:
        itemsets.eliminate_zeros()

    tree = FPTree(rank)
    for i in range(num_itemsets):
        nonnull = (
            itemsets.indices[itemsets.indptr[i] : itemsets.indptr[i + 1]]
            if is_sparse
            else np.where(itemsets[i, :])[0]
        )
        itemset = [item for item in nonnull if item in rank]
        itemset.sort(key=rank.get, reverse=True)
        tree.insert_itemset(itemset)

    return tree, rank


def generate_itemsets(generator, num_itemsets, colname_map):
    itemsets = [(sup / num_itemsets, frozenset(iset)) for sup, iset in generator]
    res_df = pd.DataFrame(itemsets, columns=["support", "itemsets"])

    if colname_map is not None:
        res_df["itemsets"] = res_df["itemsets"].apply(
            lambda x: frozenset([colname_map[i] for i in x])
        )

    return res_df


def fpmax_step(tree, minsup, mfit, colnames, max_len, verbose):
    count = 0
    items = list(tree.nodes.keys())
    largest_set = sorted(tree.cond_items + items, key=mfit.rank.get)
    if not largest_set:
        return

    if tree.is_path() and not mfit.contains(largest_set):
        count += 1
        largest_set.reverse()
        mfit.cache = largest_set
        mfit.insert_itemset(largest_set)
        if max_len is None or len(largest_set) <= max_len:
            support = (
                min([tree.nodes[i][0].count for i in items])
                if items
                else tree.root.count
            )
            yield support, largest_set

    if verbose:
        tree.print_status(count, colnames)

    if not tree.is_path() and (not max_len or max_len > len(tree.cond_items)):
        items.sort(key=tree.rank.get)
        for item in items:
            if mfit.contains(largest_set):
                return
            largest_set.remove(item)
            cond_tree = tree.conditional_tree(item, minsup)
            for support, mfi in fpmax_step(
                cond_tree, minsup, mfit, colnames, max_len, verbose
            ):
                yield support, mfi


def fpmax(df, min_support=0.5, use_colnames=False, max_len=None, verbose=0):
    if min_support <= 0.0 or min_support > 1.0:
        raise ValueError("Invalid value for `min_support`. It must be in (0, 1].")

    colname_map = None
    if use_colnames:
        colname_map = {idx: item for idx, item in enumerate(df.columns)}

    tree, rank = setup_fptree(df, min_support)

    minsup = math.ceil(min_support * len(df))
    generator = fpmax_step(tree, minsup, MFITree(rank), colname_map, max_len, verbose)

    return generate_itemsets(generator, len(df), colname_map)


def transform_data(X, sparse=False):
    unique_items = sorted(set(item for transaction in X for item in transaction))
    columns_mapping = {item: idx for idx, item in enumerate(unique_items)}

    if sparse:
        indptr = [0]
        indices = []
        for transaction in X:
            for item in set(transaction):
                col_idx = columns_mapping[item]
                indices.append(col_idx)
            indptr.append(len(indices))
        data = [True] * len(indices)
        array = csr_matrix((data, indices, indptr), dtype=bool)
    else:
        array = np.zeros((len(X), len(columns_mapping)), dtype=bool)
        for row_idx, transaction in enumerate(X):
            for item in transaction:
                col_idx = columns_mapping[item]
                array[row_idx, col_idx] = True

    columns = sorted(columns_mapping, key=columns_mapping.get)
    return array, columns


if __name__ == "__main__":
    dataset = [
    ['yellow', 'small', 'stretch', 'adult'],
    ['yellow', 'small', 'stretch', 'child'],
    ['purple', 'small', 'dip', 'adult'],
    ['purple', 'small', 'dip', 'child'],
    ['yellow', 'small', 'stretch', 'adult'],
    ['yellow', 'small', 'stretch', 'child'],
    ['purple', 'small', 'dip', 'adult'],
    ['yellow', 'small', 'dip', 'child'],
    ['yellow', 'large', 'stretch', 'adult'],
    ['yellow', 'large', 'stretch', 'child']]

    transformed_data, columns = transform_data(dataset, sparse=False)
    df = pd.DataFrame(transformed_data, columns=columns)
    print(df)

    result_df = fpmax(df, min_support=0.3, use_colnames=True, max_len=None, verbose=0)
    print(result_df)