"""Server tests: multiple clients, JSON validation, alerts, CSV logging.

Run from the project folder:   python -m unittest discover tests -v
"""

import csv
import io
import os
import socket
import tempfile
import threading
import time
import unittest

from helpers import load

server_module = load("server", "server")
from shared import protocol  # noqa: E402


def wait_for(condition, timeout=3):
    end = time.time() + timeout
    while time.time() < end:
        if condition():
            return True
        time.sleep(0.05)
    return False


class FakeLabPC:
    """A raw TCP client speaking the protocol, standing in for one lab PC."""

    def __init__(self, port, name):
        self.name = name
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=3)
        self.reader = self.sock.makefile("rb")
        assert self.send(protocol.CLIENT_CONNECTED) == protocol.ACK

    def send(self, event, drive=None):
        self.sock.sendall(protocol.encode(protocol.make_event(event, self.name, "127.0.0.1", drive)))
        return self.reader.readline()

    def close(self):
        self.reader.close()
        self.sock.close()


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log_file = os.path.join(self.tmp.name, "events.csv")
        self.output = io.StringIO()
        self.server = server_module.MonitoringServer(host="127.0.0.1", port=0, log_file=self.log_file)
        self.server.show = lambda text: self.output.write(text + "\n")
        self.server.start()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.pcs = []

    def tearDown(self):
        for pc in self.pcs:
            pc.close()
        self.server.stop()
        self.thread.join(3)
        self.tmp.cleanup()

    def connect(self, name):
        pc = FakeLabPC(self.server.port, name)
        self.pcs.append(pc)
        return pc

    def test_three_clients_connect(self):
        for i in range(1, 4):
            self.connect(f"LAB-PC-0{i}")
        self.assertTrue(wait_for(lambda: self.server.client_count() == 3))
        for i in range(1, 4):
            self.assertIn(f"[CONNECTED] LAB-PC-0{i}", self.output.getvalue())

    def test_usb_event_alert_and_log(self):
        pc = self.connect("LAB-PC-02")
        self.assertEqual(pc.send(protocol.USB_INSERTED, "E:"), protocol.ACK)
        self.assertEqual(pc.send(protocol.USB_REMOVED, "E:"), protocol.ACK)

        out = self.output.getvalue()
        self.assertIn("USB ALERT", out)
        self.assertIn("USB REMOVED", out)
        self.assertIn("LAB-PC-02", out)
        self.assertIn("Drive      : E:", out)

        with open(self.log_file, newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual([r["event"] for r in rows], ["USB_INSERTED", "USB_REMOVED"])
        self.assertEqual(rows[0]["pc_name"], "LAB-PC-02")
        self.assertEqual(rows[0]["drive"], "E:")

    def test_log_appends_not_overwrites(self):
        pc = self.connect("LAB-PC-01")
        pc.send(protocol.USB_INSERTED, "E:")
        pc.close()
        self.pcs.remove(pc)
        pc2 = self.connect("LAB-PC-01")
        pc2.send(protocol.USB_INSERTED, "F:")
        with open(self.log_file, newline="") as f:
            lines = f.read().strip().splitlines()
        self.assertEqual(lines[0], "timestamp,pc_name,ip,event,drive")
        self.assertEqual(len(lines), 3)

    def test_one_client_disconnecting_does_not_stop_server(self):
        pc1 = self.connect("LAB-PC-01")
        pc2 = self.connect("LAB-PC-02")
        pc1.close()
        self.pcs.remove(pc1)
        self.assertTrue(wait_for(lambda: self.server.client_count() == 1))
        self.assertEqual(pc2.send(protocol.USB_INSERTED, "F:"), protocol.ACK)
        self.connect("LAB-PC-03")   # new clients still accepted
        self.assertTrue(wait_for(lambda: self.server.client_count() == 2))

    def test_both_clients_events_received(self):
        pc1 = self.connect("LAB-PC-01")
        pc2 = self.connect("LAB-PC-02")
        pc1.send(protocol.USB_INSERTED, "E:")
        pc2.send(protocol.USB_INSERTED, "F:")
        with open(self.log_file, newline="") as f:
            rows = {(r["pc_name"], r["drive"]) for r in csv.DictReader(f)}
        self.assertEqual(rows, {("LAB-PC-01", "E:"), ("LAB-PC-02", "F:")})

    def test_invalid_message_is_rejected_but_connection_survives(self):
        pc = self.connect("LAB-PC-01")
        pc.sock.sendall(b"this is not json\n")
        pc.sock.sendall(b'{"event": "USB_INSERTED"}\n')   # missing fields
        self.assertEqual(pc.send(protocol.USB_INSERTED, "E:"), protocol.ACK)
        out = self.output.getvalue()
        self.assertEqual(out.count("[INVALID]"), 2)
        self.assertIn("missing required field", out)


class EventLoggerTests(unittest.TestCase):
    def test_creates_header_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "logs", "events.csv")
            logger = server_module.EventLogger(path)
            msg = protocol.make_event(protocol.USB_INSERTED, "PC", "1.2.3.4", "E:")
            logger.log(msg)
            logger.log(msg)
            with open(path) as f:
                self.assertEqual(f.read().count("timestamp,pc_name"), 1)


if __name__ == "__main__":
    unittest.main()
