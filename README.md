docker-mdns-relay
=================

`docker-mdns-relay` bridges mDNS between a macOS LAN and Docker Desktop networks.
It relays raw IPv4 and IPv6 mDNS packets in both directions and suppresses packets
it just replayed to prevent loops.

## Install the host service

Install the personal tap and start the service:

```sh
brew tap christine/docker-mdns-relay
brew install docker-mdns-relay
brew services start docker-mdns-relay
```

The Homebrew service starts in host mode on `en0`, the usual Wi-Fi/Ethernet LAN
interface on macOS. Check status and logs with:

```sh
brew services info docker-mdns-relay
tail -f "$(brew --prefix)/var/log/docker-mdns-relay.log"
```

For a different LAN interface, run the relay manually with the interface you need:

```sh
brew services stop docker-mdns-relay
docker-mdns-relay host --interface en1
```

The service listens on UDP port `15354`. Restrict access with a macOS PF rule
before exposing it beyond the Docker Desktop network.

## Docker setup

Build the included image and run it as a client on the Docker network that needs
discovery. In Compose, use `host.docker.internal` to reach the macOS host relay:

```yaml
services:
  mdns-relay:
    build: .
    command: ["client", "--interface", "eth0", "--server", "host.docker.internal"]
    networks:
      - network-discovery
```

The client and the services it supports should share the same Docker network.
```

The host relay listens on UDP 15354. Restrict access with the macOS PF rule
before exposing this setup beyond the Docker Desktop network.
