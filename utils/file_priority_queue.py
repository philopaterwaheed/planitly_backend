import os
import pickle
import hashlib


class FilePriorityQueue:
    def __init__(self, path, num_buckets=10):
        self.path = path
        self.num_buckets = num_buckets
        os.makedirs(self.path, exist_ok=True)

    def _bucket_name(self, key):
        h = int(hashlib.md5(pickle.dumps(key)).hexdigest(), 16)
        return f"bucket_{h % self.num_buckets}.pq"

    def push(self, key, value):
        bucket_path = os.path.join(self.path, self._bucket_name(key))
        with open(bucket_path, 'ab') as f:
            pickle.dump((key, value), f)

    def _scan_extreme(self, find_min=True):
        extreme = None
        for bucket in os.listdir(self.path):
            bucket_path = os.path.join(self.path, bucket)
            if os.path.getsize(bucket_path) == 0:
                continue
            with open(bucket_path, 'rb') as f:
                try:
                    item = pickle.load(f)
                    if (extreme is None or
                        (find_min and item[0] < extreme[0]) or
                        (not find_min and item[0] > extreme[0])):
                        extreme = item
                except EOFError:
                    continue
        return extreme

    def head(self):
        result = self._scan_extreme(find_min=True)
        if result is None:
            raise IndexError("Head from empty queue")
        return result

    def tail(self):
        result = self._scan_extreme(find_min=False)
        if result is None:
            raise IndexError("Tail from empty queue")
        return result

    def pop(self):
        smallest = self.head()
        bucket_path = os.path.join(self.path, self._bucket_name(smallest[0]))
        temp_path = bucket_path + '.tmp'

        removed = False
        with open(bucket_path, 'rb') as src, open(temp_path, 'wb') as dst:
            try:
                while True:
                    item = pickle.load(src)
                    if not removed and item == smallest:
                        removed = True
                        continue  # skip it
                    pickle.dump(item, dst)
            except EOFError:
                pass

        if os.path.getsize(temp_path) == 0:
            os.remove(temp_path)
            os.remove(bucket_path)
        else:
            os.replace(temp_path, bucket_path)

        return smallest

    def empty(self):
        return all(os.path.getsize(os.path.join(self.path, bucket)) == 0
                   for bucket in os.listdir(self.path))
