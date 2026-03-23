import time

# ------------------------------
# Itemset class
# ------------------------------
class Itemset:
    def __init__(self, items=None, support=0):
        if items is None:
            self.items = []
        else:
            self.items = sorted(items)  # keep items sorted like Java
        self.support = support

    def get_items(self):
        return self.items

    def size(self):
        return len(self.items)

    def get_absolute_support(self):
        return self.support

    def set_absolute_support(self, support):
        self.support = support

    def increase_transaction_count(self):
        self.support += 1

    def intersection(self, other):
        i, j = 0, 0
        result = []
        while i < len(self.items) and j < len(other.items):
            if self.items[i] == other.items[j]:
                result.append(self.items[i])
                i += 1
                j += 1
            elif self.items[i] < other.items[j]:
                i += 1
            else:
                j += 1
        return Itemset(result)

    def is_equal_to(self, other):
        return self.items == other.items

    def __str__(self):
        return ' '.join(map(str, self.items))


# ------------------------------
# CloStream class
# ------------------------------
class CloStream:
    def __init__(self):
        self.table_closed = []
        self.cid_list_map = {}  # item -> list of closed itemset indices
        # initialize with empty set (like Java)
        empty = Itemset()
        empty.set_absolute_support(0)
        self.table_closed.append(empty)

    def process_new_transaction(self, transaction):
        # temporary table for intersections
        table_temp = [(transaction, 0)]

        # collect cid indices in **insertion order**, no set()
        cid_list = []
        for item in transaction.get_items():
            if item in self.cid_list_map:
                for cid in self.cid_list_map[item]:
                    if cid not in cid_list:
                        cid_list.append(cid)

        # process intersections in exact order
        for cid in cid_list:
            cti = self.table_closed[cid]
            intersection_s = transaction.intersection(cti)
            found = False
            for idx, (t_item, t_cid) in enumerate(table_temp):
                if t_item.is_equal_to(intersection_s):
                    found = True
                    ctt = self.table_closed[t_cid]
                    if cti.get_absolute_support() > ctt.get_absolute_support():
                        table_temp[idx] = (t_item, cid)
                    break
            if not found:
                table_temp.append((intersection_s, cid))

        # update table_closed and cid_list_map
        for x, c in table_temp:
            ctc = self.table_closed[c]
            if x.is_equal_to(ctc):
                ctc.increase_transaction_count()
            else:
                self.table_closed.append(x)
                x.set_absolute_support(ctc.get_absolute_support() + 1)
                for item in transaction.get_items():
                    if item not in self.cid_list_map:
                        self.cid_list_map[item] = []
                    self.cid_list_map[item].append(len(self.table_closed) - 1)

    def get_closed_itemsets(self):
        if self.table_closed and self.table_closed[0].size() == 0:
            self.table_closed.pop(0)
        return self.table_closed


# ------------------------------
# Read transactions
# ------------------------------
def read_transactions(file_path):
    transactions = []
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                transactions.append(list(map(int, line.split())))
    return transactions


# ------------------------------
# Main
# ------------------------------
if __name__ == "__main__":
    input_file = "clostream.txt"
    output_file = "clostream_outputs.txt"
    relative_minsup = 0.4  # relative support threshold

    clo_stream = CloStream()
    transactions = read_transactions(input_file)
    num_transactions = len(transactions)

    # compute absolute min_count from relative support
    min_count = max(1, int(relative_minsup * num_transactions))

    start_time = time.time()
    for t in transactions:
        clo_stream.process_new_transaction(Itemset(t))
    end_time = time.time()

    closed_itemsets = clo_stream.get_closed_itemsets()

    # filter frequent itemsets by min_count, **preserve Java discovery order**
    frequent_itemsets = [i for i in closed_itemsets if i.get_absolute_support() >= min_count]

    # write output
    with open(output_file, 'w') as f:
        for itemset in frequent_itemsets:
            sup = itemset.get_absolute_support() / num_transactions
            line = f"{itemset}  #SUP: {sup:.1f}"
            f.write(line + "\n")
            print(line)

    # stats
    print("============= CLO-STREAM - STATS =============")
    print("Number of nodes           :", len(closed_itemsets))
    print("Frequent itemsets count   :", len(frequent_itemsets))
    print("Number of transactions    :", num_transactions)
    print("Total insertion time      : {:.2f} ms".format((end_time - start_time) * 1000))
    print("Insertion time per txn    : {:.2f} ms".format((end_time - start_time) * 1000 / num_transactions))
    print("=============================================")
