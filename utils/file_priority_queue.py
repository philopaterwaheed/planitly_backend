import os
import fcntl
import pickle
import threading
import tempfile
import time
import uuid
import shutil
import heapq
from typing import Any, TypeVar, Generic, List, Tuple, Optional, Dict

T = TypeVar('T')  # Type for the priority key
V = TypeVar('V')  # Type for the value


class FilePriorityQueue(Generic[T, V]):
    """A fully crash-safe file-based priority queue implementation with thread safety and heap optimization."""

    def __init__(self, directory: str = None, max_memory_items: int = 100,
                 flush_threshold: int = 10, recovery_check: bool = True):
        self.directory = directory or tempfile.mkdtemp()
        self.max_memory_items = max_memory_items
        self.flush_threshold = flush_threshold
        self.lock = threading.RLock()

        # Ensure directory exists
        os.makedirs(self.directory, exist_ok=True)

        # Directory structure
        self.index_path = os.path.join(self.directory, "index.pkl")
        self.temp_index_path = os.path.join(self.directory, "index.tmp.pkl")
        self.buffer_path = os.path.join(self.directory, "buffer.pkl")
        self.temp_buffer_path = os.path.join(self.directory, "buffer.tmp.pkl")
        self.data_dir = os.path.join(self.directory, "data")
        self.temp_dir = os.path.join(self.directory, "temp")
        self.lock_dir = os.path.join(self.directory, "locks")

        # Create necessary directories
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.lock_dir, exist_ok=True)

        # Counter for tie-breaking equal priorities
        self.counter = 0

        # In-memory buffer using a heap instead of a sorted list
        self.buffer: List[Tuple[T, int, V]] = []

        # Count of items added to buffer since last persistence
        self.buffer_count = 0

        # Initialize or load existing data
        if recovery_check:
            self._perform_recovery()
        self._initialize_index()
        self._load_buffer()

    def _get_lock_file(self, operation: str, chunk_id: Optional[str] = None) -> str:
        """Get a lock file path for a specific operation and chunk."""
        if chunk_id is not None:
            return os.path.join(self.lock_dir, f"{operation}_{chunk_id}.lock")
        return os.path.join(self.lock_dir, f"{operation}.lock")

    def _create_operation_lock(self, operation: str, chunk_id: Optional[str] = None) -> None:
        """Create a lock file for a specific operation to track incomplete operations."""
        lock_file = self._get_lock_file(operation, chunk_id)
        with open(lock_file, 'w') as f:
            f.write(str(time.time()))

    def _remove_operation_lock(self, operation: str, chunk_id: Optional[str] = None) -> None:
        lock_file = self._get_lock_file(operation, chunk_id)
        if os.path.exists(lock_file):
            os.remove(lock_file)

    def _perform_recovery(self) -> None:
        """Check for and recover from crashes during previous operations."""
        with self.lock:
            # Check for interrupted index updates
            if os.path.exists(self.temp_index_path):
                if os.path.exists(self.index_path):
                    # Temp is likely corrupt, use existing
                    os.remove(self.temp_index_path)
                else:
                    # Attempt to recover the temp index file
                    try:
                        shutil.move(self.temp_index_path, self.index_path)
                    except Exception:
                        # If recovery fails, create a new index
                        if os.path.exists(self.temp_index_path):
                            os.remove(self.temp_index_path)

            # Check for interrupted buffer updates
            if os.path.exists(self.temp_buffer_path):
                if os.path.exists(self.buffer_path):
                    # Use existing buffer file
                    os.remove(self.temp_buffer_path)
                else:
                    # Attempt to recover the temp buffer file
                    try:
                        shutil.move(self.temp_buffer_path, self.buffer_path)
                    except Exception:
                        if os.path.exists(self.temp_buffer_path):
                            os.remove(self.temp_buffer_path)

            # Check for interrupted chunk operations
            for filename in os.listdir(self.lock_dir):
                if filename.startswith("flush_"):
                    # Interrupted flush operation
                    chunk_id = filename.split("_")[1].split(".")[0]
                    temp_chunk_path = os.path.join(
                        self.temp_dir, f"chunk_{chunk_id}.pkl")
                    final_chunk_path = os.path.join(
                        self.data_dir, f"chunk_{chunk_id}.pkl")

                    if os.path.exists(temp_chunk_path):
                        if os.path.exists(final_chunk_path):
                            # Final file exists, discard temp
                            os.remove(temp_chunk_path)
                        else:
                            # Move temp to final
                            try:
                                shutil.move(temp_chunk_path, final_chunk_path)
                            except Exception:
                                if os.path.exists(temp_chunk_path):
                                    os.remove(temp_chunk_path)

                    lock_file = os.path.join(self.lock_dir, filename)
                    os.remove(lock_file)
                elif filename.startswith("pop_") or filename.startswith("push_"):
                    # Interrupted operations - clean up the lock
                    lock_file = os.path.join(self.lock_dir, filename)
                    os.remove(lock_file)

            # Clean up any remaining temp files
            for filename in os.listdir(self.temp_dir):
                temp_file = os.path.join(self.temp_dir, filename)
                if os.path.isfile(temp_file):
                    os.remove(temp_file)

    def _safe_read_pickle(self, filepath: str, default=None):
        """Safely read a pickle file with error handling."""
        if not os.path.exists(filepath):
            return default

        try:
            with open(filepath, 'rb') as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    return pickle.load(f)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
        except (pickle.PickleError, EOFError, AttributeError):
            # File might be corrupted
            return default

    def _safe_write_pickle(self, data, filepath: str, temp_filepath: str = None) -> bool:
        use_temp = temp_filepath is not None
        temp_path = temp_filepath if use_temp else f"{filepath}.tmp"

        try:
            # Write to temp file first
            with open(temp_path, 'wb') as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    pickle.dump(data, f)
                    f.flush()
                    os.fsync(f.fileno())  # Ensure data is written to disk
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)

            # Move temp file to final destination (atomic on most file systems)
            if os.path.exists(filepath):
                os.replace(temp_path, filepath)  # Atomic replace
            else:
                shutil.move(temp_path, filepath)

            return True
        except Exception as e:
            # If an error occurs, remove the temp file if it exists
            if os.path.exists(temp_path) and not use_temp:
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            return False

    def _initialize_index(self):
        """Initialize or load the index file that tracks chunk information."""
        with self.lock:
            index_data = self._safe_read_pickle(self.index_path, default={
                'chunk_files': [],
                'counter': 0,
                'min_priorities': []
            })

            self.chunk_files = index_data.get('chunk_files', [])
            self.counter = index_data.get('counter', 0)
            self.min_priorities = index_data.get('min_priorities', [])

            # Validate that all chunk files in the index actually exist
            valid_chunks = []
            valid_priorities = []

            for i, chunk_path in enumerate(self.chunk_files):
                if os.path.exists(chunk_path):
                    # Verify chunk file is readable
                    chunk_data = self._safe_read_pickle(chunk_path)
                    if chunk_data:
                        valid_chunks.append(chunk_path)
                        # Update min priority based on actual data
                        valid_priorities.append(
                            chunk_data[0][0] if chunk_data else None)
                    else:
                        try:
                            os.remove(chunk_path)
                        except Exception:
                            pass

            # Update with only valid chunks
            self.chunk_files = valid_chunks
            self.min_priorities = valid_priorities

            # Save corrected index
            self._save_index()

    def _load_buffer(self):
        """Load the persisted buffer from disk and heapify it."""
        with self.lock:
            if os.path.exists(self.buffer_path):
                buffer_data = self._safe_read_pickle(
                    self.buffer_path, default=[])
                self.buffer = buffer_data
                # Heapify the loaded buffer
                heapq.heapify(self.buffer)
            else:
                self.buffer = []

            self.buffer_count = 0

    def _save_buffer(self):
        """Save the buffer to disk with crash safety."""
        with self.lock:
            # Create operation lock
            self._create_operation_lock("save_buffer")

            # Write buffer to temp file then move
            success = self._safe_write_pickle(
                self.buffer, self.buffer_path, self.temp_buffer_path)

            # Reset buffer count after successful save
            if success:
                self.buffer_count = 0

            self._remove_operation_lock("save_buffer")
            return success

    def _save_index(self):
        """Save the index file with updated information using atomic operations."""
        with self.lock:
            index_data = {
                'chunk_files': self.chunk_files,
                'counter': self.counter,
                'min_priorities': self.min_priorities
            }

            # Create operation lock
            self._create_operation_lock("save_index")

            # Write to temp file then move
            success = self._safe_write_pickle(
                index_data, self.index_path, self.temp_index_path)

            self._remove_operation_lock("save_index")
            return success

    def push(self, priority: T, value: V) -> None:
        """Add an item to the priority queue with the given priority."""
        with self.lock:
            # Create operation lock
            self._create_operation_lock("push")

            # Add to buffer as a heap entry
            entry = (priority, self.counter, value)
            self.counter += 1
            heapq.heappush(self.buffer, entry)
            self.buffer_count += 1

            # Immediately persist the buffer
            self._save_buffer()

            # If buffer exceeds threshold, consolidate into chunks
            if len(self.buffer) >= self.max_memory_items:
                self._consolidate_buffer()

            self._remove_operation_lock("push")

    def _get_new_chunk_id(self) -> str:
        """Generate a unique chunk ID based on timestamp and UUID."""
        return f"{int(time.time())}_{uuid.uuid4().hex[:8]}"

    def _consolidate_buffer(self) -> None:
        """Consolidate buffer items into chunk files when buffer gets too large."""
        if not self.buffer:
            return

        with self.lock:
            # Copy the buffer as-is (heap order, no sort)
            buffer_copy = list(self.buffer)

            # Create a unique chunk ID
            chunk_id = self._get_new_chunk_id()
            temp_chunk_path = os.path.join(
                self.temp_dir, f"chunk_{chunk_id}.pkl")
            final_chunk_path = os.path.join(
                self.data_dir, f"chunk_{chunk_id}.pkl")

            # Create operation lock
            self._create_operation_lock("flush", chunk_id)

            # Write buffer to temp file
            success = self._safe_write_pickle(
                buffer_copy, final_chunk_path, temp_chunk_path)

            if success:
                # Update index information
                self.chunk_files.append(final_chunk_path)
                # The buffer is a heap, so the min is always at index 0
                self.min_priorities.append(
                    buffer_copy[0][0] if buffer_copy else None)

                # Clear buffer only if successfully written
                self.buffer = []

                # Save updated index and empty buffer
                self._save_index()
                self._save_buffer()

            self._remove_operation_lock("flush", chunk_id)

    def pop(self) -> Optional[Tuple[T, V]]:
        """Remove and return the highest priority item (lowest numeric value)."""
        with self.lock:
            # Create operation lock
            self._create_operation_lock("pop")

            # Find the overall highest priority item (either in buffer or chunks)
            best_in_buffer = self.buffer[0] if self.buffer else None

            # Find best chunk
            best_chunk_idx = self._find_best_chunk()
            best_in_chunk = None

            if best_chunk_idx is not None:
                chunk_path = self.chunk_files[best_chunk_idx]
                chunk_data = self._safe_read_pickle(chunk_path, default=[])
                if chunk_data:
                    # Heapify chunk data before popping
                    heapq.heapify(chunk_data)
                    best_in_chunk = chunk_data[0]

            # Compare best from buffer and chunks
            if best_in_buffer is not None and (best_in_chunk is None or best_in_buffer[0] <= best_in_chunk[0]):
                # Best item is in buffer
                priority, _, value = heapq.heappop(self.buffer)
                self._save_buffer()  # Persist buffer change
                self._remove_operation_lock("pop")
                return (priority, value)
            elif best_in_chunk is not None:
                # Best item is in chunk
                chunk_path = self.chunk_files[best_chunk_idx]
                chunk_id = os.path.basename(chunk_path).replace(
                    "chunk_", "").replace(".pkl", "")

                # Create chunk-specific lock
                self._create_operation_lock("pop_chunk", chunk_id)

                # Read the chunk again (might have changed)
                chunk_data = self._safe_read_pickle(chunk_path, default=[])
                if not chunk_data:
                    self._remove_chunk(best_chunk_idx)
                    self._remove_operation_lock("pop_chunk", chunk_id)
                    self._remove_operation_lock("pop")
                    return self.pop()  # Try again

                # Heapify before popping
                heapq.heapify(chunk_data)
                # Get highest priority item
                priority, _, value = heapq.heappop(chunk_data)

                # Update the file
                if chunk_data:
                    temp_chunk_path = os.path.join(
                        self.temp_dir, f"chunk_{chunk_id}_updated.pkl")
                    success = self._safe_write_pickle(
                        chunk_data, chunk_path, temp_chunk_path)

                    if success:
                        # Update min priority for this chunk
                        self.min_priorities[best_chunk_idx] = chunk_data[0][0]
                        self._save_index()
                else:
                    self._remove_chunk(best_chunk_idx)

                self._remove_operation_lock("pop_chunk", chunk_id)
                self._remove_operation_lock("pop")
                return (priority, value)
            else:
                # Queue is empty
                self._remove_operation_lock("pop")
                return None

    def _find_best_chunk(self) -> Optional[int]:
        """Find the index of the chunk with the highest priority item."""
        if not self.min_priorities or not self.chunk_files:
            return None

        # Find chunk with minimum priority (highest priority item)
        min_priority = None
        min_idx = None

        for i, priority in enumerate(self.min_priorities):
            if priority is not None and (min_priority is None or priority < min_priority):
                min_priority = priority
                min_idx = i

        return min_idx

    def _remove_chunk(self, chunk_idx: int) -> None:
        with self.lock:
            if chunk_idx < 0 or chunk_idx >= len(self.chunk_files):
                return

            chunk_path = self.chunk_files[chunk_idx]
            chunk_id = os.path.basename(chunk_path).replace(
                "chunk_", "").replace(".pkl", "")

            # Create operation lock for chunk removal
            self._create_operation_lock("remove", chunk_id)

            if os.path.exists(chunk_path):
                try:
                    os.remove(chunk_path)
                except Exception:
                    pass

            # Update index
            self.chunk_files.pop(chunk_idx)
            self.min_priorities.pop(chunk_idx)
            self._save_index()

            self._remove_operation_lock("remove", chunk_id)

    def peek(self) -> Optional[Tuple[T, V]]:
        """Look at the highest priority item without removing it."""
        with self.lock:
            # Find the overall highest priority item (either in buffer or chunks)
            best_in_buffer = self.buffer[0] if self.buffer else None

            # Find best chunk
            best_chunk_idx = self._find_best_chunk()
            best_in_chunk = None

            if best_chunk_idx is not None:
                chunk_path = self.chunk_files[best_chunk_idx]
                chunk_data = self._safe_read_pickle(chunk_path, default=[])
                if chunk_data:
                    heapq.heapify(chunk_data)
                    best_in_chunk = chunk_data[0]

            # Compare best from buffer and chunks
            if best_in_buffer is not None and (best_in_chunk is None or best_in_buffer[0] <= best_in_chunk[0]):
                # Best item is in buffer
                priority, _, value = best_in_buffer
                return (priority, value)
            elif best_in_chunk is not None:
                # Best item is in chunk
                priority, _, value = best_in_chunk
                return (priority, value)
            else:
                return None

    def is_empty(self) -> bool:
        """Check if the queue is empty."""
        with self.lock:
            if self.buffer:
                return False

            for chunk_path in self.chunk_files:
                if os.path.exists(chunk_path):
                    chunk_data = self._safe_read_pickle(chunk_path, default=[])
                    if chunk_data:
                        return False

            return True

    def size(self) -> int:
        """Get the total number of items in the queue."""
        with self.lock:
            size = len(self.buffer)
            valid_chunks = []
            valid_priorities = []

            for i, chunk_path in enumerate(self.chunk_files):
                if os.path.exists(chunk_path):
                    chunk_data = self._safe_read_pickle(chunk_path, default=[])
                    size += len(chunk_data)
                    if chunk_data:
                        valid_chunks.append(chunk_path)
                        valid_priorities.append(chunk_data[0][0])

            # If we found inconsistencies, update the index
            if len(valid_chunks) != len(self.chunk_files):
                self.chunk_files = valid_chunks
                self.min_priorities = valid_priorities
                self._save_index()

            return size

    def clear(self) -> None:
        """Remove all items from the queue."""
        with self.lock:
            # Create operation lock for clear operation
            self._create_operation_lock("clear")

            self.buffer = []
            self._save_buffer()

            for chunk_path in self.chunk_files:
                if os.path.exists(chunk_path):
                    try:
                        os.remove(chunk_path)
                    except Exception:
                        pass

            # Reset index
            self.chunk_files = []
            self.min_priorities = []
            self._save_index()

            self._remove_operation_lock("clear")

    def checkpoint(self) -> None:
        """Save current state to disk."""
        with self.lock:
            self._save_buffer()
            self._save_index()

    def optimize(self) -> Dict[str, int]:
        """Optimize the storage by consolidating chunks."""
        with self.lock:
            stats = {
                "chunks_before": len(self.chunk_files),
                "items_processed": 0,
                "chunks_after": 0
            }

            # First, gather all items
            all_items = list(self.buffer)  # Start with buffer items

            # Add items from all chunks
            for chunk_path in self.chunk_files:
                if os.path.exists(chunk_path):
                    chunk_data = self._safe_read_pickle(chunk_path, default=[])
                    all_items.extend(chunk_data)
                    stats["items_processed"] += len(chunk_data)
                    try:
                        os.remove(chunk_path)
                    except Exception:
                        pass

            # Clear current data structures
            self.buffer = []
            self.chunk_files = []
            self.min_priorities = []

            # Sort all items in one go
            all_items.sort()

            # Split into optimal sized chunks
            chunk_size = self.max_memory_items * 2  # Use larger chunks for efficiency
            for i in range(0, len(all_items), chunk_size):
                chunk_items = all_items[i:i+chunk_size]
                if chunk_items:
                    # Create a new chunk
                    chunk_id = self._get_new_chunk_id()
                    temp_chunk_path = os.path.join(
                        self.temp_dir, f"chunk_{chunk_id}.pkl")
                    final_chunk_path = os.path.join(
                        self.data_dir, f"chunk_{chunk_id}.pkl")

                    success = self._safe_write_pickle(
                        chunk_items, final_chunk_path, temp_chunk_path)

                    if success:
                        self.chunk_files.append(final_chunk_path)
                        self.min_priorities.append(
                            chunk_items[0][0] if chunk_items else None)
                        stats["chunks_after"] += 1

            # Keep some items in memory buffer if there are any left
            if all_items and chunk_size > self.max_memory_items:
                remaining = len(all_items) % chunk_size
                if remaining > 0 and remaining <= self.max_memory_items:
                    self.buffer = all_items[-remaining:]
                    # Heapify the buffer
                    heapq.heapify(self.buffer)

            # Save the updated index and buffer
            self._save_index()
            self._save_buffer()

            return stats

    def repair(self) -> Dict[str, int]:
        """Repair the queue by fixing inconsistencies."""
        with self.lock:
            stats = {
                "corrupted_files_removed": 0,
                "orphaned_files_recovered": 0,
                "lock_files_cleaned": 0,
                "temp_files_cleaned": 0,
                "buffer_items_recovered": 0
            }

            # Clean up lock files
            for filename in os.listdir(self.lock_dir):
                if filename.endswith(".lock"):
                    lock_file = os.path.join(self.lock_dir, filename)
                    os.remove(lock_file)
                    stats["lock_files_cleaned"] += 1

            # Clean up temp files
            for filename in os.listdir(self.temp_dir):
                temp_file = os.path.join(self.temp_dir, filename)
                if os.path.isfile(temp_file):
                    os.remove(temp_file)
                    stats["temp_files_cleaned"] += 1

            # Check for orphaned chunk files
            known_chunks = set(self.chunk_files)
            for filename in os.listdir(self.data_dir):
                if filename.startswith("chunk_") and filename.endswith(".pkl"):
                    chunk_path = os.path.join(self.data_dir, filename)
                    if chunk_path not in known_chunks:
                        # Check if the file is valid
                        chunk_data = self._safe_read_pickle(
                            chunk_path, default=None)
                        if chunk_data:
                            self.chunk_files.append(chunk_path)
                            self.min_priorities.append(
                                chunk_data[0][0] if chunk_data else None)
                            stats["orphaned_files_recovered"] += 1
                        else:
                            os.remove(chunk_path)
                            stats["corrupted_files_removed"] += 1

            # Verify all chunks in the index
            valid_chunks = []
            valid_priorities = []

            for chunk_path in self.chunk_files:
                if os.path.exists(chunk_path):
                    chunk_data = self._safe_read_pickle(
                        chunk_path, default=None)
                    if chunk_data:
                        valid_chunks.append(chunk_path)
                        valid_priorities.append(
                            chunk_data[0][0] if chunk_data else None)
                    else:
                        os.remove(chunk_path)
                        stats["corrupted_files_removed"] += 1

            # Update the index with valid chunks
            self.chunk_files = valid_chunks
            self.min_priorities = valid_priorities

            # Check buffer file
            if os.path.exists(self.buffer_path):
                buffer_data = self._safe_read_pickle(
                    self.buffer_path, default=None)
                if buffer_data:
                    self.buffer = buffer_data
                    # Ensure buffer is a valid heap
                    heapq.heapify(self.buffer)
                    stats["buffer_items_recovered"] = len(buffer_data)

            self._save_index()
            self._save_buffer()

            return stats

    def __del__(self):
        try:
            self.checkpoint()
        except Exception:
            pass
