#!/usr/bin/env python3
"""Bidirectional mDNS tunnel for Docker Desktop on macOS.

The host mode joins the LAN mDNS multicast groups and serves one or more
Docker clients over a UDP tunnel. Client mode joins the
container network's multicast groups and connects to that host relay.
"""

import argparse
import configparser
import hashlib
import logging
import select
import socket
import struct
import subprocess
import sys
import time
from collections import OrderedDict


MDNS_PORT = 5353
TUNNEL_PORT = 15354
IPV4_GROUP = "224.0.0.251"
IPV6_GROUP = "ff02::fb"
MAGIC = b"MDR1"
HELLO = 1
MDNS_IPV4 = 2
MDNS_IPV6 = 3
FRAME_HEADER = struct.Struct("!4sB")
CACHE_TTL_SECONDS = 3
CLIENT_TTL_SECONDS = 45
HELLO_INTERVAL_SECONDS = 15


class RecentPackets:
    def __init__(self):
        self._entries = OrderedDict()

    def seen(self, packet_type, payload):
        now = time.monotonic()
        while self._entries and next(iter(self._entries.values())) < now:
            self._entries.popitem(last=False)
        fingerprint = hashlib.sha256(bytes([packet_type]) + payload).digest()
        if fingerprint in self._entries:
            return True
        self._entries[fingerprint] = now + CACHE_TTL_SECONDS
        return False


def set_reuse(socket_handle):
    socket_handle.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):
        try:
            socket_handle.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except OSError:
            pass


def interface_ipv4(interface):
    if sys.platform != "darwin":
        import fcntl

        request = struct.pack("256s", interface.encode("utf-8")[:15])
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            response = fcntl.ioctl(probe, 0x8915, request)
        finally:
            probe.close()
        return socket.inet_ntoa(response[20:24])

    try:
        return subprocess.check_output(
            ["/usr/sbin/ipconfig", "getifaddr", interface], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise RuntimeError(f"Unable to determine IPv4 address for {interface}: {error}") from error


def make_mdns_ipv4_socket(interface, interface_address):
    socket_handle = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    set_reuse(socket_handle)
    socket_handle.bind(("", MDNS_PORT))
    membership = socket.inet_aton(IPV4_GROUP) + socket.inet_aton(interface_address)
    socket_handle.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
    socket_handle.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(interface_address))
    socket_handle.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
    socket_handle.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 0)
    logging.info("Joined IPv4 mDNS on %s (%s)", interface, interface_address)
    return socket_handle


def make_mdns_ipv6_socket(interface):
    interface_index = socket.if_nametoindex(interface)
    socket_handle = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    set_reuse(socket_handle)
    socket_handle.bind(("::", MDNS_PORT))
    membership = socket.inet_pton(socket.AF_INET6, IPV6_GROUP) + struct.pack("@I", interface_index)
    socket_handle.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, membership)
    socket_handle.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_IF, interface_index)
    socket_handle.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_HOPS, 255)
    socket_handle.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_LOOP, 0)
    logging.info("Joined IPv6 mDNS on %s", interface)
    return socket_handle, interface_index


def encode_frame(packet_type, payload=b""):
    return FRAME_HEADER.pack(MAGIC, packet_type) + payload


def decode_frame(frame):
    if len(frame) < FRAME_HEADER.size:
        return None
    magic, packet_type = FRAME_HEADER.unpack(frame[: FRAME_HEADER.size])
    if magic != MAGIC:
        return None
    return packet_type, frame[FRAME_HEADER.size :]


def send_to_mdns(packet_type, payload, ipv4_socket, ipv6_socket, ipv6_interface_index):
    if packet_type == MDNS_IPV4:
        ipv4_socket.sendto(payload, (IPV4_GROUP, MDNS_PORT))
    elif packet_type == MDNS_IPV6:
        ipv6_socket.sendto(payload, (IPV6_GROUP, MDNS_PORT, 0, ipv6_interface_index))


def run_host(arguments):
    interface_address = interface_ipv4(arguments.interface)
    ipv4_socket = make_mdns_ipv4_socket(arguments.interface, interface_address)
    ipv6_socket, ipv6_interface_index = make_mdns_ipv6_socket(arguments.interface)
    tunnel_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tunnel_socket.bind((arguments.bind_address, arguments.port))
    logging.info("Listening for Docker clients on %s:%s", arguments.bind_address, arguments.port)

    clients = {}
    recently_reflected = RecentPackets()
    while True:
        readable, _, _ = select.select([ipv4_socket, ipv6_socket, tunnel_socket], [], [], 1)
        now = time.monotonic()
        clients = {client: expiry for client, expiry in clients.items() if expiry > now}

        for socket_handle in readable:
            if socket_handle is tunnel_socket:
                frame, client = tunnel_socket.recvfrom(65535)
                decoded = decode_frame(frame)
                if not decoded:
                    logging.warning("Discarded invalid tunnel packet from %s:%s", *client)
                    continue
                packet_type, payload = decoded
                clients[client] = now + CLIENT_TTL_SECONDS
                if packet_type in (MDNS_IPV4, MDNS_IPV6) and not recently_reflected.seen(packet_type, payload):
                    send_to_mdns(packet_type, payload, ipv4_socket, ipv6_socket, ipv6_interface_index)
                    logging.debug("Reflected %s from Docker client %s:%s to LAN", packet_type, *client)
                continue

            payload, _ = socket_handle.recvfrom(65535)
            packet_type = MDNS_IPV4 if socket_handle is ipv4_socket else MDNS_IPV6
            if recently_reflected.seen(packet_type, payload):
                continue
            frame = encode_frame(packet_type, payload)
            for client in clients:
                tunnel_socket.sendto(frame, client)


def run_client(arguments):
    interface_address = interface_ipv4(arguments.interface)
    ipv4_socket = make_mdns_ipv4_socket(arguments.interface, interface_address)
    ipv6_socket, ipv6_interface_index = make_mdns_ipv6_socket(arguments.interface)
    tunnel_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tunnel_destination = (arguments.server, arguments.port)
    logging.info("Relaying to host at %s:%s", *tunnel_destination)

    recently_reflected = RecentPackets()
    next_hello = 0
    while True:
        now = time.monotonic()
        if now >= next_hello:
            tunnel_socket.sendto(encode_frame(HELLO), tunnel_destination)
            next_hello = now + HELLO_INTERVAL_SECONDS

        readable, _, _ = select.select([ipv4_socket, ipv6_socket, tunnel_socket], [], [], 1)
        for socket_handle in readable:
            if socket_handle is tunnel_socket:
                frame, _ = tunnel_socket.recvfrom(65535)
                decoded = decode_frame(frame)
                if not decoded:
                    continue
                packet_type, payload = decoded
                if packet_type in (MDNS_IPV4, MDNS_IPV6) and not recently_reflected.seen(packet_type, payload):
                    send_to_mdns(packet_type, payload, ipv4_socket, ipv6_socket, ipv6_interface_index)
                    logging.debug("Reflected %s from LAN to Docker mDNS", packet_type)
                continue

            payload, _ = socket_handle.recvfrom(65535)
            packet_type = MDNS_IPV4 if socket_handle is ipv4_socket else MDNS_IPV6
            if not recently_reflected.seen(packet_type, payload):
                tunnel_socket.sendto(encode_frame(packet_type, payload), tunnel_destination)


def parse_arguments():
    bootstrap_parser = argparse.ArgumentParser(add_help=False)
    bootstrap_parser.add_argument("mode", choices=("host", "server", "client"), nargs="?")
    bootstrap_parser.add_argument("--config")
    bootstrap_arguments, _ = bootstrap_parser.parse_known_args()

    configuration = {}
    config_section = "host" if bootstrap_arguments.mode == "server" else bootstrap_arguments.mode
    if bootstrap_arguments.config and config_section:
        config = configparser.ConfigParser()
        try:
            with open(bootstrap_arguments.config, encoding="utf-8") as config_file:
                config.read_file(config_file)
        except (OSError, configparser.Error) as error:
            bootstrap_parser.error(f"Unable to read configuration file: {error}")

        if not config.has_section(config_section):
            bootstrap_parser.error(
                f"Configuration file has no [{config_section}] section"
            )
        configuration = dict(config.items(config_section))

    try:
        port = int(configuration.get("port", TUNNEL_PORT))
    except ValueError:
        bootstrap_parser.error("Configuration value 'port' must be an integer")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("host", "server", "client"))
    parser.add_argument("--config", help="INI file containing a [host] or [client] section")
    parser.add_argument(
        "--interface",
        default=configuration.get("interface"),
        help="network interface, for example en0 or eth0",
    )
    parser.add_argument("--port", type=int, default=port)
    parser.add_argument(
        "--log-level",
        default=configuration.get("log_level", "INFO").upper(),
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    parser.add_argument(
        "--bind-address",
        default=configuration.get("bind_address", "0.0.0.0"),
        help="host-mode tunnel bind address",
    )
    parser.add_argument(
        "--server",
        default=configuration.get("server"),
        help="host-mode tunnel address for client mode",
    )
    arguments = parser.parse_args()
    if not arguments.interface:
        parser.error("--interface is required unless it is set in the configuration file")
    if arguments.mode == "client" and not arguments.server:
        parser.error("--server is required in client mode unless it is set in the configuration file")
    if arguments.mode == "server":
        arguments.mode = "host"
    return arguments


def main():
    arguments = parse_arguments()
    logging.basicConfig(level=arguments.log_level, format="%(asctime)s %(levelname)s %(message)s")
    if arguments.mode == "host":
        run_host(arguments)
    else:
        run_client(arguments)


if __name__ == "__main__":
    main()
