FROM python:3.13-alpine
COPY docker_mdns_relay.py /usr/local/bin/mdns-relay
COPY docker-mdns-relay.conf /etc/docker-mdns-relay.conf
ENTRYPOINT ["python3", "/usr/local/bin/mdns-relay"]
CMD ["server", "--config", "/etc/docker-mdns-relay.conf"]
