"""Server settings. Edit these values instead of changing server.py."""

import os

# 0.0.0.0 = listen on every network interface of this PC (Wi-Fi, Ethernet...)
HOST = "0.0.0.0"

# TCP port the clients connect to. Must match PORT in client/config.py.
PORT = 5000

# UDP port where the server answers "where is the server?" broadcasts from
# clients, so nobody has to type the server IP. Must match client/config.py.
DISCOVERY_PORT = 5001

# A client that sends nothing for this many seconds is treated as disconnected.
# Clients send a heartbeat every 10 seconds, so 30 seconds allows a few misses.
CLIENT_TIMEOUT = 30

# CSV file where USB events are appended
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(_ROOT, "logs", "events.csv")
