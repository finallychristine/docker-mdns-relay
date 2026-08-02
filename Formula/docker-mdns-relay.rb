class DockerMdnsRelay < Formula
  desc "Bridge mDNS traffic between macOS and Docker Desktop networks"
  homepage "https://github.com/christine/docker-mdns-relay"
  url "https://github.com/christine/docker-mdns-relay.git",
      tag:      "v0.0.1",
      revision: "0a94751be750e99ef55244a6883b809c4e135134"
  version "0.0.1"

  depends_on "python@3.13"

  def install
    bin.install "docker_mdns_relay.py" => "docker-mdns-relay"
    rewrite_shebang detected_python_shebang, bin/"docker-mdns-relay"
  end

  service do
    run [opt_bin/"docker-mdns-relay", "host", "--interface", "en0"]
    keep_alive true
    log_path var/"log/docker-mdns-relay.log"
    error_log_path var/"log/docker-mdns-relay.log"
  end

  test do
    assert_match "usage:", shell_output("#{bin}/docker-mdns-relay --help")
  end
end
