#!/usr/bin/env bash
# Host prerequisites only. No service ACL changes, distro replacement, or
# security-profile disabling. Native certification remains a separate gate.
set -euo pipefail
if [[ $(id -u) -ne 0 ]]; then
    echo 'Run prerequisite setup as root inside the selected Linux distro.' >&2
    exit 1
fi
if [[ $(stat -fc %T /sys/fs/cgroup) != cgroup2fs ]]; then
    echo 'A cgroup v2 Linux environment is required.' >&2
    exit 1
fi
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-venv python3-pip bubblewrap libseccomp2 libseccomp-dev \
    libcap-dev build-essential pkg-config meson ninja-build curl ca-certificates git unzip debootstrap
if ! id chili-runner >/dev/null 2>&1; then
    useradd --create-home --shell /bin/bash chili-runner
fi
install -d -m 0755 -o chili-runner -g chili-runner /home/chili-runner/chili-lab
echo 'Installed host:'
uname -a
cat /etc/os-release
python3 --version
bwrap --version
version=$(bwrap --version | awk '{print $NF}')
if ! dpkg --compare-versions "$version" ge 0.12.0; then
    echo "Installed bubblewrap $version is too old; building pinned upstream 0.12.0."
    expected_commit=2a76602a8c71f36c1527cf9fc3417d9149822e0c
    build_dir=$(mktemp -d /var/tmp/chili-bubblewrap.XXXXXXXX)
    chown chili-runner:chili-runner "$build_dir"
    # Build as the unprivileged account. Only binary installation needs root.
    runuser -u chili-runner -- git clone --depth 1 --branch v0.12.0 --single-branch \
        https://github.com/containers/bubblewrap.git "$build_dir/source"
    actual_commit=$(runuser -u chili-runner -- git -C "$build_dir/source" rev-parse HEAD)
    if [[ "$actual_commit" != "$expected_commit" ]]; then
        echo "Upstream commit mismatch: expected $expected_commit; got $actual_commit" >&2
        exit 1
    fi
    runuser -u chili-runner -- meson setup "$build_dir/build" "$build_dir/source" \
        --buildtype=release -Dman=disabled -Dbash_completion=disabled \
        -Dzsh_completion=disabled -Dtests=false
    runuser -u chili-runner -- ninja -C "$build_dir/build"
    "$build_dir/build/bwrap" --version
    install -D -m 0755 "$build_dir/build/bwrap" /usr/local/bin/bwrap
    install -d -m 0755 /opt/chili-crisp/bubblewrap-0.12.0
    printf '%s\n' "$expected_commit" > /opt/chili-crisp/bubblewrap-0.12.0/source-commit.txt
    sha256sum /usr/local/bin/bwrap > /opt/chili-crisp/bubblewrap-0.12.0/binary.sha256
    printf '%s\n' "$build_dir" > /opt/chili-crisp/bubblewrap-0.12.0/build-directory.txt
    export PATH="/usr/local/bin:$PATH"
    hash -r
    version=$(bwrap --version | awk '{print $NF}')
    if ! dpkg --compare-versions "$version" ge 0.12.0; then
        echo 'Patched bubblewrap did not become the selected executable.' >&2
        exit 1
    fi
fi
echo "Selected bubblewrap: $(command -v bwrap) ($version)"
runuser -u chili-runner -- env PATH="$PATH" bwrap --version
pid1=$(cat /proc/1/comm)
if [[ "$pid1" != systemd ]]; then
    echo "WSL is currently using '$pid1' as PID 1; enabling systemd for this distribution."
    apt-get install -y systemd systemd-sysv
    python3 - <<'CHILI_WSL_CONFIG_PY'
import os
from pathlib import Path
import re
import stat
import time


def enable_systemd(text):
    """Change only the boot systemd key, preserving unrelated settings."""
    lines = text.splitlines(keepends=True)
    header = re.compile(r"^\s*\[\s*([^]]+?)\s*\]\s*(?:[#;].*)?$")
    sections = [(i, match[1].lower()) for i, line in enumerate(lines)
                if (match := header.match(line.strip()))]
    boots = [i for i, name in sections if name == "boot"]
    if len(boots) > 1:
        raise ValueError("Duplicate [boot] sections in /etc/wsl.conf; resolve before retrying")
    if not boots:
        return text + ("\n" if text and not text.endswith("\n") else "") + "[boot]\nsystemd=true\n"
    start = boots[0]
    end = next((i for i, _ in sections if i > start), len(lines))
    keys = [i for i in range(start + 1, end) if re.match(r"^\s*systemd\s*=", lines[i], re.I)]
    if len(keys) > 1:
        raise ValueError("Duplicate systemd keys in /etc/wsl.conf; resolve before retrying")
    if keys:
        index = keys[0]
        comment = re.search(r"\s+[#;].*", lines[index].rstrip("\r\n"))
        lines[index] = "systemd=true" + (comment[0] if comment else "") + "\n"
    else:
        if end and not lines[end - 1].endswith("\n"):
            lines[end - 1] += "\n"
        lines.insert(end, "systemd=true\n")
    return "".join(lines)


if __name__ == "__main__":
    path = Path("/etc/wsl.conf")
    if path.is_symlink():
        raise RuntimeError("Refusing to replace symlink /etc/wsl.conf")
    original = path.read_bytes() if path.exists() else b""
    updated = enable_systemd(original.decode("utf-8")).encode("utf-8")
    if updated != original:
        if path.exists():
            backup = path.with_name("wsl.conf.chili-backup-" + str(time.time_ns()))
            backup.write_bytes(original)
            print("Preserved original configuration:", backup)
        mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
        temporary = path.with_name(".wsl.conf.chili-" + str(time.time_ns()))
        temporary.write_bytes(updated)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    print("Configured [boot] systemd=true; a distribution restart is required.")
CHILI_WSL_CONFIG_PY
    # Reserved status understood by setup-wsl.ps1. Never kill user workloads
    # or shut down Docker's separate WSL distribution automatically.
    exit 20
fi
ready=false
for attempt in {1..30}; do
    if timeout 2 systemctl show-environment >/dev/null 2>&1; then
        ready=true
        break
    fi
    sleep 1
done
if [[ "$ready" != true ]]; then
    echo 'PID 1 is systemd, but its manager did not become reachable.' >&2
    systemctl show-environment >&2 || true
    exit 1
fi
if ! grep -qw memory /sys/fs/cgroup/cgroup.controllers || ! grep -qw pids /sys/fs/cgroup/cgroup.controllers; then
    echo 'The memory and pids controllers must be available.' >&2
    exit 1
fi
echo 'Prerequisites are available. No rootfs, delegation, native fixture, or frontier is claimed by this setup step.'
