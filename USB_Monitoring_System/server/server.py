"""
CENTRAL USB MONITORING SERVER (runs on the invigilator PC)

    python server\\server.py              (uses PORT from server/config.py)
    python server\\server.py --port 6000

How it works:
  1. Create a TCP socket, bind it to 0.0.0.0:<port> and listen.
  2. accept() waits for a lab PC to connect.
  3. Each connected PC gets its own thread, so many PCs can be served at once.
  4. The thread reads newline-terminated JSON messages, validates them,
     shows an alert for USB events, logs them to CSV and replies "ACK".
"""

import argparse
import json
import os
import socket
import sys
import threading

# Make the "shared" folder importable when running "python server\server.py"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402  (server/config.py)
from event_logger import EventLogger  # noqa: E402
from shared import protocol  # noqa: E402

LINE = "=" * 52


class MonitoringServer:
    def __init__(self, host=config.HOST, port=config.PORT, log_file=config.LOG_FILE,
                 client_timeout=config.CLIENT_TIMEOUT):
        self.host = host
        self.port = port
        self.client_timeout = client_timeout
        self.logger = EventLogger(log_file)
        self.clients = {}                     # (ip, port) -> pc_name
        self._clients_lock = threading.Lock()
        self._print_lock = threading.Lock()   # stop threads printing on top of each other
        self._running = False
        self.sock = None
        self.udp_sock = None
        self.discovery_port = None

    # ---------------------------------------------------------------- output
    def show(self, text):
        with self._print_lock:
            print(text, flush=True)

    def client_count(self):
        with self._clients_lock:
            return len(self.clients)

    def show_alert(self, msg, peer_ip):
        removed = msg["event"] == protocol.USB_REMOVED
        title = "USB REMOVED" if removed else "USB ALERT"
        time_only = msg["timestamp"].split(" ")[-1]
        lines = [
            "",
            LINE,
            title.center(52),
            LINE,
            f"PC Name    : {msg['pc_name']}",
            f"IP Address : {msg['ip']}   (socket peer: {peer_ip})",
            f"Event      : {msg['event'].replace('_', ' ')}",
            f"Drive      : {msg.get('drive', 'unknown')}",
        ]
        if msg.get("note"):
            lines.append(f"Note       : {msg['note']}")
        lines += [
            f"Time       : {time_only}",
            f"Connected clients: {self.client_count()}",
            LINE,
        ]
        self.show("\n".join(lines))

    # --------------------------------------------------------------- network
    def start(self):
        """Create the listening socket (Phase 2)."""
        # AF_INET = IPv4, SOCK_STREAM = TCP
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Windows: refuse to share the port, so two server windows cannot both
        # "listen" on 5000. Linux/macOS: allow restarting immediately.
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.port = self.sock.getsockname()[1]   # real port (matters if port 0 was used)
        self.sock.listen()                       # start accepting TCP handshakes
        # Wake up every second so Ctrl+C works on Windows
        self.sock.settimeout(1.0)
        self._running = True

    def serve_forever(self):
        """Accept clients until stop() is called (Phase 5: one thread per client)."""
        while self._running:
            try:
                conn, addr = self.sock.accept()   # blocks until a client connects
            except socket.timeout:
                continue
            except OSError:
                break                              # socket closed by stop()
            thread = threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True)
            thread.start()

    def stop(self):
        self._running = False
        for s in (self.sock, self.udp_sock):
            if s:
                s.close()

    def start_discovery(self, discovery_port=config.DISCOVERY_PORT):
        """
        Answer clients' UDP broadcast "where is the server?" in a background
        thread, so clients find this PC without anyone typing its IP.
        Returns False (server still works, clients then need --server) if the
        UDP port cannot be opened.
        """
        try:
            self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   # UDP
            self.udp_sock.bind((self.host, discovery_port))
            self.udp_sock.settimeout(1.0)
        except OSError as err:
            self.show(f"[WARNING] Auto-discovery disabled (UDP port {discovery_port}: {err})")
            self.udp_sock = None
            return False
        self.discovery_port = self.udp_sock.getsockname()[1]
        threading.Thread(target=self._discovery_loop, daemon=True).start()
        return True

    def _discovery_loop(self):
        reply = json.dumps({"service": protocol.DISCOVER_SERVICE, "port": self.port}).encode()
        while self._running:
            try:
                data, addr = self.udp_sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                break
            if data.strip() == protocol.DISCOVER_REQUEST:
                try:
                    self.udp_sock.sendto(reply, addr)   # unicast reply to the asking client
                except OSError:
                    pass

    def handle_client(self, conn, addr):
        """Runs in its own thread for ONE connected lab PC."""
        peer_ip = addr[0]
        conn.settimeout(self.client_timeout)
        name = None
        try:
            # makefile() lets us read the TCP stream line by line
            reader = conn.makefile("rb")
            for raw_line in reader:
                if not raw_line.strip():
                    continue
                try:
                    msg = protocol.decode(raw_line)
                except protocol.ProtocolError as err:
                    self.show(f"[INVALID] from {peer_ip}: {err}")
                    continue

                if name is None:
                    name = msg["pc_name"]
                    with self._clients_lock:
                        self.clients[addr] = name
                    self.show(f"[CONNECTED] {name} ({peer_ip})   "
                              f"Connected clients: {self.client_count()}")

                self.process(msg, peer_ip)
                conn.sendall(protocol.ACK)   # tell the client we got it
        except socket.timeout:
            self.show(f"[TIMEOUT] {name or peer_ip} sent nothing for {self.client_timeout}s")
        except (ConnectionResetError, ConnectionAbortedError, OSError):
            pass   # client vanished (cable pulled, PC shut down...)
        finally:
            conn.close()
            with self._clients_lock:
                self.clients.pop(addr, None)
            self.show(f"[DISCONNECTED] {name or peer_ip}   "
                      f"Connected clients: {self.client_count()}")

    def process(self, msg, peer_ip):
        event = msg["event"]
        if event in protocol.USB_EVENTS:
            self.show_alert(msg, peer_ip)
            self.logger.log(msg)
        elif event == protocol.TEST_MESSAGE:
            self.show(f"Received from {msg['pc_name']} ({peer_ip}): {msg.get('message', '')}")
        # CLIENT_CONNECTED and HEARTBEAT need no extra output


def main():
    parser = argparse.ArgumentParser(description="Central USB monitoring server")
    parser.add_argument("--port", type=int, default=config.PORT, help="TCP port to listen on")
    args = parser.parse_args()

    server = MonitoringServer(port=args.port)
    try:
        server.start()
    except OSError as err:
        print(f"Could not start server on port {args.port}: {err}")
        print("Is another server window already open? Close it, or use --port 6000.")
        sys.exit(1)

    print(LINE)
    print("  CENTRAL USB MONITORING SERVER")
    print(LINE)
    print()
    discovery = server.start_discovery()
    print(f"Server IP : {protocol.get_local_ip()}")
    print(f"Port      : {server.port}")
    if discovery:
        print(f"Discovery : ON (UDP {server.discovery_port}) - clients find this server automatically")
    print(f"Log file  : {config.LOG_FILE}")
    print()
    print("Waiting for clients...  (Ctrl+C to stop)")
    print(flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.stop()


if __name__ == "__main__":
    main()
