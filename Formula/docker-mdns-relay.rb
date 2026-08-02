class DockerMdnsRelay < Formula
  desc "Bridge mDNS traffic between macOS and Docker Desktop networks"
  homepage "https://github.com/finallychristine/docker-mdns-relay"
  url "https://github.com/finallychristine/docker-mdns-relay.git",
      tag:      "v0.0.3",
      revision: "c5cd91d013713151a43d0b9bd3012cf68a839bcd"
  version "0.0.3"

  depends_on "python@3.13"

  def install
    bin.install "docker_mdns_relay.py" => "docker-mdns-relay"
    rewrite_shebang detected_python_shebang, bin/"docker-mdns-relay"
    etc.install "docker-mdns-relay.conf"
  end

  service do
    run [opt_bin/"docker-mdns-relay", "host", "--config", etc/"docker-mdns-relay.conf"]
    keep_alive true
    log_path var/"log/docker-mdns-relay.log"
    error_log_path var/"log/docker-mdns-relay.log"
  end

  test do
    assert_match "usage:", shell_output("#{bin}/docker-mdns-relay --help")
  end
end
