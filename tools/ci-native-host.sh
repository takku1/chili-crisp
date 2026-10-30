#!/usr/bin/env bash
# Provision a disposable GitHub-hosted Ubuntu runner for the native fixtures.
# Never run this on a workstation: it relaxes the AppArmor user-namespace policy.
set -euo pipefail
sudo apt-get update -q
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q gcc libseccomp2 libcap-dev meson ninja-build pkg-config python3-venv
# The runner requires bubblewrap >= 0.12.0 (GHSA-pxhw-h44j-8pfx); Ubuntu 24.04 ships 0.9.
git clone --quiet --depth 1 --branch v0.12.0 https://github.com/containers/bubblewrap /tmp/bubblewrap
meson setup /tmp/bubblewrap/_build /tmp/bubblewrap -Dman=disabled -Dtests=false -Dselinux=disabled >/dev/null
ninja -C /tmp/bubblewrap/_build >/dev/null
sudo ninja -C /tmp/bubblewrap/_build install >/dev/null
# A source-built bwrap has no AppArmor userns profile.
sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0 || true
id chili-runner >/dev/null 2>&1 || sudo useradd --create-home --shell /bin/bash chili-runner
sudo -u chili-runner mkdir -p /home/chili-runner/chili-lab
bwrap --version
cat /sys/fs/cgroup/cgroup.controllers
