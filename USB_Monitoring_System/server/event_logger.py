"""Appends USB events to a CSV file (no database needed)."""

import csv
import os
import threading

COLUMNS = ["timestamp", "pc_name", "ip", "event", "drive"]


class EventLogger:
    def __init__(self, path):
        self.path = path
        # Several client threads may log at the same moment -> use a lock
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def log(self, message):
        """Append one event as a CSV row. Never overwrites earlier rows."""
        row = {column: message.get(column, "") for column in COLUMNS}
        with self._lock:
            write_header = not os.path.exists(self.path) or os.path.getsize(self.path) == 0
            # mode "a" = append
            with open(self.path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=COLUMNS)
                if write_header:
                    writer.writeheader()
                writer.writerow(row)
