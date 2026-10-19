"""Client tests: protocol, test message, PC info, event delivery, reconnection."""

import io
import os
import socket
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout

from helpers import free_port, load

server_module = load("server", "server")
client_module = load("client", "client")
from shared import protocol  # noqa: E402


def wait_for(condition, timeout):
    end = time.time() + timeout
    while time.time() < end:
        if condition():
            return True
        time.sleep(0.05)
    return False


class FakeMonitor:
    """Pretend USB monitor: tests push (event, drive) pairs into it."""

    def __init__(self):
        self.queue = []

    def initial_scan(self):
        return []

    def poll(self):
        events, self.queue = self.queue, []
        return events


class ProtocolTests(unittest.TestCase):
    def test_round_trip(self):
        msg = protocol.make_event(protocol.USB_INSERTED, "LAB-PC-01", "192.168.1.101", "E:")
        data = protocol.encode(msg)
        self.assertTrue(data.endswith(b"\n"))
        self.assertEqual(protocol.decode(data), msg)

    def test_required_fields(self):
        for field in protocol.REQUIRED_FIELDS:
            msg = protocol.make_event(protocol.USB_INSERTED, "PC", "1.1.1.1", "E:")
            del msg[field]
            with self.assertRaises(protocol.ProtocolError):
                protocol.decode(protocol.encode(msg))

    def test_bad_json_and_unknown_event(self):
        with self.assertRaises(protocol.ProtocolError):
            protocol.decode(b"hello")
        with self.assertRaises(protocol.ProtocolError):
            protocol.decode(protocol.encode(protocol.make_event("FORMAT_DISK", "PC", "1.1.1.1")))


class ClientTests(unittest.TestCase):
    def start_server(self, port=0):
        server = server_module.MonitoringServer(host="127.0.0.1", port=port, log_file=self.log_file)
        server.show = lambda text: self.output.write(text + "\n")
        server.start()
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.servers.append(server)
        return server

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log_file = os.path.join(self.tmp.name, "events.csv")
        self.output = io.StringIO()
        self.servers = []

    def tearDown(self):
        for s in self.servers:
            s.stop()
        self.tmp.cleanup()

    def test_automatic_pc_info(self):
        client = client_module.MonitoringClient("127.0.0.1", 1, monitor=FakeMonitor())
        self.assertEqual(client.pc_name, socket.gethostname())
        msg = client.event(protocol.USB_INSERTED, "E:")
        for field in ("event", "pc_name", "ip", "timestamp", "drive"):
            self.assertTrue(msg[field])
        socket.inet_aton(msg["ip"])   # raises if not a valid IPv4 address

    def test_send_test_message(self):
        server = self.start_server()
        client = client_module.MonitoringClient("127.0.0.1", server.port, "LAB-PC-01", FakeMonitor())
        with redirect_stdout(io.StringIO()) as out:
            self.assertTrue(client.send_test_message())
        self.assertIn("Message sent successfully.", out.getvalue())
        self.assertIn("Hello from examination PC", self.output.getvalue())

    def test_test_message_server_down(self):
        client = client_module.MonitoringClient("127.0.0.1", free_port(), "LAB-PC-01", FakeMonitor())
        with redirect_stdout(io.StringIO()):
            self.assertFalse(client.send_test_message())

    def test_reconnection_and_queued_events(self):
        """Server is down at first; USB event is queued and delivered once the server starts."""
        client_module.config.RETRY_INTERVAL = 0.2
        client_module.config.POLL_INTERVAL = 0.05
        port = free_port()
        monitor = FakeMonitor()
        client = client_module.MonitoringClient("127.0.0.1", port, "LAB-PC-07", monitor)
        client_out = io.StringIO()

        def run():
            with redirect_stdout(client_out):
                try:
                    client.run()
                except Exception:
                    pass

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        monitor.queue.append(("USB_INSERTED", "E:"))
        # Windows retries a refused connection for ~2 seconds before failing
        self.assertTrue(wait_for(lambda: "Server unavailable" in client_out.getvalue(), 6))

        self.start_server(port)
        try:
            self.assertTrue(wait_for(lambda: "USB ALERT" in self.output.getvalue(), 8))
            self.assertIn("LAB-PC-07", self.output.getvalue())
            self.assertIn("Connected to server.", client_out.getvalue())
        finally:
            client.running = False
            thread.join(5)
            client.disconnect()

    def test_auto_discovery_finds_server(self):
        """Client with no server IP finds the server by UDP broadcast and connects."""
        server = self.start_server()
        self.assertTrue(server.start_discovery(0))
        self.assertEqual(client_module.discover_server(server.discovery_port, 2),
                         ("127.0.0.1", server.port))

        client_module.config.DISCOVERY_PORT = server.discovery_port
        client = client_module.MonitoringClient("auto", 9, "LAB-PC-09", FakeMonitor())
        with redirect_stdout(io.StringIO()) as out:
            self.assertTrue(client.send_test_message())
        self.assertIn("Found server at 127.0.0.1", out.getvalue())
        self.assertIn("LAB-PC-09", self.output.getvalue())

    def test_auto_discovery_no_server(self):
        self.assertIsNone(client_module.discover_server(free_port(), 0.5))


if __name__ == "__main__":
    unittest.main()
