FROM python:3.13-alpine
COPY docker_mdns_relay.py /app/docker_mdns_relay.py
COPY docker-mdns-relay.conf /app/docker-mdns-relay.conf
ENTRYPOINT ["python3", "/app/docker_mdns_relay.py"]
CMD ["client", "--config", "/app/docker-mdns-relay.conf"]
