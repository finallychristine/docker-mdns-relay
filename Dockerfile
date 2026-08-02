FROM python:3.13-alpine
COPY docker_mdns_relay.py /usr/local/bin/mdns-relay
ENTRYPOINT ["python3", "/usr/local/bin/mdns-relay"]
