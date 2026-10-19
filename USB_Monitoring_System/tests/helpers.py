"""
Test helpers. server/ and client/ both have a module called "config", so each
side is imported with its own folder on sys.path and the cache is cleared.
"""

import importlib
import os
import socket
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def load(folder, module_name):
    path = os.path.join(ROOT, folder)
    sys.path.insert(0, path)
    try:
        for name in ("config", "event_logger", "usb_monitor", module_name):
            sys.modules.pop(name, None)
        return importlib.import_module(module_name)
    finally:
        sys.path.remove(path)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
