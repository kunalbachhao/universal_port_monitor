"""
USB MONITORING CLIENT (runs on every lab PC)

    python client\\client.py                                   (find server automatically)
    python client\\client.py --test                            (send one test message)
    python client\\client.py --server 192.168.1.100            (use a fixed server IP)
    python client\\client.py --name LAB-PC-01

How it works:
  1. Open ONE TCP connection to the server and keep it open.
  2. Every second, check for USB drives being inserted or removed.
  3. Each change becomes a JSON event (PC name, IP, drive, timestamp)
     that is sent to the server. The server answers "ACK".
  4. Every 10 seconds a HEARTBEAT is sent so a dead connection is noticed.
  5. If the server cannot be reached, events are queued and the client keeps
     retrying - it never crashes, and queued events are sent after reconnecting.
"""

import argparse
import json
import os
import socket
import sys
import time
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402  (client/config.py)
from usb_monitor import UsbMonitor  # noqa: E402
from shared import protocol  # noqa: E402

TEST_TEXT = "Hello from examination PC"

DISCOVERY_HELP = """
  No server answered. Check:
    1. start_server.bat is running on the server laptop.
    2. Both laptops are on the SAME Wi-Fi / hotspot / LAN.
    3. On the server laptop, allow_firewall.bat has been run (or Python was
       allowed in the Windows Firewall popup).
    4. If it still fails, the network blocks broadcasts. On the server run
       "ipconfig", then on this laptop open client\\config.py and set
       SERVER_IP = "<server IPv4 address>"
"""


def broadcast_addresses():
    """
    Broadcast address of every network adapter, using its real subnet mask
    (e.g. 192.168.1.255 for a /24 LAN, 172.20.10.15 for an iPhone hotspot /28).
    Sending to each one makes sure the broadcast leaves through Wi-Fi/Ethernet
    and not through some virtual adapter.
    """
    result = set()
    if sys.platform == "win32":
        import ctypes
        import struct
        from ctypes import wintypes

        class MIB_IPADDRROW(ctypes.Structure):
            _fields_ = [("dwAddr", wintypes.DWORD), ("dwIndex", wintypes.DWORD),
                        ("dwMask", wintypes.DWORD), ("dwBCastAddr", wintypes.DWORD),
                        ("dwReasmSize", wintypes.DWORD), ("unused1", ctypes.c_ushort),
                        ("wType", ctypes.c_ushort)]

        try:
            iphlpapi = ctypes.WinDLL("iphlpapi")
            size = wintypes.ULONG(0)
            iphlpapi.GetIpAddrTable(None, ctypes.byref(size), False)   # ask for buffer size
            buf = ctypes.create_string_buffer(size.value)
            if iphlpapi.GetIpAddrTable(buf, ctypes.byref(size), False) == 0:
                count = wintypes.DWORD.from_buffer(buf).value
                rows = (MIB_IPADDRROW * count).from_buffer(buf, ctypes.sizeof(wintypes.DWORD))
                for row in rows:
                    # values are in network byte order: broadcast = address OR (NOT mask)
                    bcast = (row.dwAddr | ~row.dwMask) & 0xFFFFFFFF
                    ip = socket.inet_ntoa(struct.pack("<I", bcast))
                    if not ip.startswith("127."):
                        result.add(ip)
        except (OSError, AttributeError, ValueError):
            pass
    if not result:   # fallback: assume a /24 network
        local_ip = protocol.get_local_ip()
        if local_ip.count(".") == 3 and not local_ip.startswith("127."):
            result.add(local_ip.rsplit(".", 1)[0] + ".255")
    return result


def discover_server(discovery_port=config.DISCOVERY_PORT, timeout=config.DISCOVERY_TIMEOUT):
    """
    Find the server automatically: broadcast a UDP "where is the server?"
    packet to the whole LAN and wait for the server's reply.
    Returns (server_ip, tcp_port), or None if nobody answered.
    """
    # every adapter's subnet broadcast + general broadcast + this PC itself
    targets = broadcast_addresses() | {"255.255.255.255", "127.0.0.1"}

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)
    try:
        for target in targets:
            try:
                sock.sendto(protocol.DISCOVER_REQUEST, (target, discovery_port))
            except OSError:
                pass
        end = time.time() + timeout
        while time.time() < end:
            try:
                data, addr = sock.recvfrom(1024)
            except (socket.timeout, ConnectionResetError):
                continue
            try:
                reply = json.loads(data)
                if reply.get("service") == protocol.DISCOVER_SERVICE:
                    return addr[0], int(reply["port"])
            except (ValueError, KeyError, TypeError, AttributeError):
                continue
        return None
    finally:
        sock.close()


class MonitoringClient:
    def __init__(self, server_ip, server_port, pc_name=None, monitor=None):
        # "auto" (or empty) = find the server with a UDP broadcast
        self.auto = server_ip in (None, "", "auto")
        self.server_ip = None if self.auto else server_ip
        self.server_port = server_port
        # Phase 7: identify this PC automatically (Windows hostname)
        self.pc_name = pc_name or socket.gethostname()
        self.monitor = monitor or UsbMonitor()
        self.sock = None
        self.reader = None
        self.pending = deque()        # events waiting to be sent
        self.running = False

    # ------------------------------------------------------------ helpers
    def local_ip(self):
        """IP of the network card used to reach the server."""
        if self.sock:
            try:
                return self.sock.getsockname()[0]
            except OSError:
                pass
        return protocol.get_local_ip()

    def event(self, event, drive=None, **extra):
        return protocol.make_event(event, self.pc_name, self.local_ip(), drive, **extra)

    @property
    def connected(self):
        return self.sock is not None

    # ------------------------------------------------------------ network
    def connect(self):
        """TCP 3-way handshake with the server, then introduce ourselves."""
        if self.server_ip is None:
            found = discover_server(config.DISCOVERY_PORT, config.DISCOVERY_TIMEOUT)
            if found is None:
                raise ConnectionError("no server answered the discovery broadcast")
            self.server_ip, self.server_port = found
            print(f"Found server at {self.server_ip}:{self.server_port}", flush=True)
        try:
            sock = socket.create_connection((self.server_ip, self.server_port),
                                            timeout=config.SOCKET_TIMEOUT)
            self.sock = sock
            self.reader = sock.makefile("rb")
            self.send(self.event(protocol.CLIENT_CONNECTED))
        except OSError:
            if self.auto:
                self.server_ip = None   # look for the server again next time
            raise

    def send(self, message):
        """Send one JSON message and wait for the server's ACK."""
        self.sock.sendall(protocol.encode(message))
        reply = self.reader.readline()
        if reply != protocol.ACK:
            raise ConnectionError("server did not acknowledge the message")

    def disconnect(self):
        for item in (self.reader, self.sock):
            try:
                if item:
                    item.close()
            except OSError:
                pass
        self.sock = None
        self.reader = None

    # ------------------------------------------------------------ main loop
    def run(self):
        print(f"PC name : {self.pc_name}")
        print(f"Server  : {'automatic discovery' if self.auto else f'{self.server_ip}:{self.server_port}'}")

        # USB drives already plugged in at start-up are reported too
        for drive in self.monitor.initial_scan():
            print(f"USB already present at start-up: {drive}")
            self.pending.append(self.event(protocol.USB_INSERTED, drive,
                                           note="already connected when monitoring started"))
        print("Monitoring USB storage devices... (Ctrl+C to stop)", flush=True)

        next_retry = 0
        next_heartbeat = 0
        shown_help = False
        self.running = True
        while self.running:
            # 1. Check USB drives (keeps working even while the server is down)
            for event, drive in self.monitor.poll():
                print(f"{time.strftime('%H:%M:%S')}  {event}  Drive: {drive}", flush=True)
                self.pending.append(self.event(event, drive))

            # 2. (Re)connect if needed - Phase 13
            if not self.connected and time.time() >= next_retry:
                try:
                    self.connect()
                    print("Connected to server.", flush=True)
                except OSError as err:
                    self.disconnect()
                    reason = err.__class__.__name__ if err.errno else err   # our own message, or the OS error name
                    print(f"Server unavailable ({reason}). "
                          f"Retrying in {config.RETRY_INTERVAL}s...", flush=True)
                    if self.auto and not err.errno and not shown_help:
                        print(DISCOVERY_HELP, flush=True)
                        shown_help = True
                    next_retry = time.time() + config.RETRY_INTERVAL

            # 3. Send queued events and the periodic heartbeat
            if self.connected:
                try:
                    while self.pending:
                        self.send(self.pending[0])
                        sent = self.pending.popleft()
                        print(f"  -> sent {sent['event']} {sent.get('drive', '')} to server", flush=True)
                    if time.time() >= next_heartbeat:
                        self.send(self.event(protocol.HEARTBEAT))
                        next_heartbeat = time.time() + config.HEARTBEAT_INTERVAL
                except OSError:
                    print("Connection to server lost.", flush=True)
                    self.disconnect()
                    next_retry = time.time()   # try again straight away

            time.sleep(config.POLL_INTERVAL)

    def send_test_message(self):
        """Phase 3/4: connect, send one test message, close."""
        try:
            self.connect()
            print("Connected to server.")
            self.send(self.event(protocol.TEST_MESSAGE, message=TEST_TEXT))
            print("Message sent successfully.")
            return True
        except OSError as err:
            where = "the server" if self.auto else f"server {self.server_ip}:{self.server_port}"
            print(f"Could not reach {where} - {err}")
            if self.auto:
                print(DISCOVERY_HELP)
            return False
        finally:
            self.disconnect()


def main():
    parser = argparse.ArgumentParser(description="USB monitoring client")
    parser.add_argument("--server", default=config.SERVER_IP,
                        help='server IP address, or "auto" to find it on the LAN (default)')
    parser.add_argument("--port", type=int, default=config.SERVER_PORT, help="server TCP port")
    parser.add_argument("--name", default=config.PC_NAME, help="PC name (default: hostname)")
    parser.add_argument("--test", action="store_true", help="send one test message and exit")
    args = parser.parse_args()

    client = MonitoringClient(args.server, args.port, args.name)
    if args.test:
        sys.exit(0 if client.send_test_message() else 1)
    try:
        client.run()
    except KeyboardInterrupt:
        print("\nClient stopped.")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
