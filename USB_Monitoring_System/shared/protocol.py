"""
Communication protocol shared by the server and the clients.

Every message is ONE JSON object followed by a newline character ("\n").
TCP is a byte *stream* - it does not keep message boundaries - so the
newline tells the receiver where one message ends and the next begins.

Example message on the wire:
    {"event": "USB_INSERTED", "pc_name": "LAB-PC-07", "ip": "192.168.1.107",
     "drive": "E:", "timestamp": "2026-10-19 16:24:31"}\n

After every message the server replies with the line "ACK\n" so the client
knows the event really reached the server.
"""

import json
import socket
from datetime import datetime

# ---- Event types ---------------------------------------------------------
USB_INSERTED = "USB_INSERTED"          # a USB storage drive appeared
USB_REMOVED = "USB_REMOVED"            # a USB storage drive disappeared
CLIENT_CONNECTED = "CLIENT_CONNECTED"  # first message after connecting (identifies the PC)
HEARTBEAT = "HEARTBEAT"                # periodic "I am still here" message
TEST_MESSAGE = "TEST_MESSAGE"          # plain test text (Phase 3/4 connectivity test)

VALID_EVENTS = {USB_INSERTED, USB_REMOVED, CLIENT_CONNECTED, HEARTBEAT, TEST_MESSAGE}
USB_EVENTS = {USB_INSERTED, USB_REMOVED}

# Fields every message must contain
REQUIRED_FIELDS = ("event", "pc_name", "ip", "timestamp")

ACK = b"ACK\n"

# Automatic server discovery (UDP broadcast). A client that does not know the
# server IP broadcasts DISCOVER_REQUEST on the LAN; the server answers with a
# small JSON reply containing its TCP port. The reply's source IP = server IP.
DISCOVER_REQUEST = b"USB_MONITOR_DISCOVER"
DISCOVER_SERVICE = "USB_MONITOR_SERVER"
ENCODING = "utf-8"
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class ProtocolError(ValueError):
    """Raised when a received message is not valid."""


def get_local_ip():
    """
    Find this PC's LAN IP address (used by both server and client).
    "Connecting" a UDP socket sends no packets - it only makes Windows pick the
    network interface it would use, and we read that interface's address.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return socket.gethostbyname(socket.gethostname())
    finally:
        s.close()


def now():
    """Current local time as text, e.g. '2026-10-19 16:24:31'."""
    return datetime.now().strftime(TIME_FORMAT)


def make_event(event, pc_name, ip, drive=None, **extra):
    """Build an event dictionary with all required fields filled in."""
    message = {
        "event": event,
        "pc_name": pc_name,
        "ip": ip,
        "timestamp": now(),
    }
    if drive is not None:
        message["drive"] = drive
    message.update(extra)
    return message


def encode(message):
    """Dictionary -> bytes ready to send through the socket."""
    return (json.dumps(message) + "\n").encode(ENCODING)


def decode(line):
    """
    One received line (bytes or str) -> validated dictionary.
    Raises ProtocolError if the line is not valid JSON or a field is missing.
    """
    if isinstance(line, bytes):
        line = line.decode(ENCODING, errors="replace")
    try:
        message = json.loads(line)
    except json.JSONDecodeError as err:
        raise ProtocolError(f"not valid JSON: {err}") from None

    if not isinstance(message, dict):
        raise ProtocolError("message must be a JSON object")

    missing = [field for field in REQUIRED_FIELDS if not message.get(field)]
    if missing:
        raise ProtocolError(f"missing required field(s): {', '.join(missing)}")

    if message["event"] not in VALID_EVENTS:
        raise ProtocolError(f"unknown event type: {message['event']}")

    return message
