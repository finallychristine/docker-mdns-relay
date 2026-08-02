class DockerMdnsRelay < Formula
  desc "Bridge mDNS traffic between macOS and Docker Desktop networks"
  homepage "https://github.com/finallychristine/docker-mdns-relay"
  url "ssh://git@github.com/finallychristine/docker-mdns-relay.git",
      using:    :git,
      tag:      "v0.0.4",
      revision: "fe3a4a6d7716d4cf2f16726212dd89fe3e3b6eb6"
  version "0.0.4"

  depends_on "python@3.13"

  def install
    libexec.install "docker_mdns_relay.py" => "docker-mdns-relay"
    bin.write_env_script libexec/"docker-mdns-relay",
      PATH: formula_opt_bin("python@3.13")
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
