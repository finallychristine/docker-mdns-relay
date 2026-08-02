docker-mdns-relay
=================

`docker-mdns-relay` bridges mDNS between a macOS LAN and Docker Desktop networks.
It relays raw IPv4 and IPv6 mDNS packets in both directions and suppresses packets
it just replayed to prevent loops.

## Install the host service

Install the personal tap and start the service:

```sh
brew tap finallychristine/docker-mdns-relay git@github.com:finallychristine/docker-mdns-relay.git
brew install finallychristine/docker-mdns-relay/docker-mdns-relay
brew services start docker-mdns-relay
```

The service reads its settings from Homebrew's default configuration file:

```sh
$(brew --prefix)/etc/docker-mdns-relay.conf
```

It starts in host mode on `en0`, the usual Wi-Fi/Ethernet LAN interface on macOS.
To use another interface, edit the `interface` value under `[host]`, then restart:

```sh
brew services restart docker-mdns-relay
```

Check status and logs with:

```sh
brew services info docker-mdns-relay
tail -f "$(brew --prefix)/var/log/docker-mdns-relay.log"
```

The same config-file format can be used outside Homebrew, including in a container:

```sh
docker-mdns-relay client --config /app/docker-mdns-relay.conf
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
    command: ["client", "--config", "/app/docker-mdns-relay.conf"]
    extra_hosts:
      - "host.docker.internal:host-gateway"
    networks:
      - network-discovery
```

By default, the image starts the client relay with its included `[client]` settings
(`eth0` inside the container). The `[host]` section remains for the macOS
Homebrew service. The client and the services it supports should share the same
Docker network.
