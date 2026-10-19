"""Client settings. Edit these values instead of changing client.py."""

# IP address of the central server (invigilator PC).
# "auto" = find the server automatically with a UDP broadcast on the LAN.
# If your network blocks broadcasts, put the real IP here (see "ipconfig" on
# the server) or give it on the command line:  --server 192.168.1.100
SERVER_IP = "auto"

# TCP port of the server. Must match PORT in server/config.py.
# (In "auto" mode the server tells the client its port.)
SERVER_PORT = 5000

# UDP port used for automatic discovery. Must match server/config.py.
DISCOVERY_PORT = 5001

# How long (seconds) to wait for the server to answer a discovery broadcast
DISCOVERY_TIMEOUT = 2

# Name shown on the server. None = use this PC's Windows hostname automatically.
# Can also be given on the command line:  --name LAB-PC-01
PC_NAME = None

# How often (seconds) to check for USB drive changes
POLL_INTERVAL = 1

# How often (seconds) to send a heartbeat so the server knows we are alive
HEARTBEAT_INTERVAL = 10

# How long (seconds) to wait before trying to reconnect to the server
RETRY_INTERVAL = 5

# How long (seconds) to wait for the server when connecting / waiting for ACK
SOCKET_TIMEOUT = 5
