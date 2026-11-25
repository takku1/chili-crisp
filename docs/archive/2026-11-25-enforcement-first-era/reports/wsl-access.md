# WSL access diagnosis

Read-only checks show WSL 2.7.14.0 and kernel 6.18.33.2-2 installed, `WslService` running automatically, and two registered distributions: `Ubuntu-26.04` (WSL 2) and `docker-desktop`. The Ubuntu distribution currently defaults to root, so the runner will require a separate unprivileged Linux account.

From the managed agent execution session, both enumeration and an explicitly selected `Ubuntu-26.04` launch fail with `E_ACCESSDENIED` at the WSL service boundary. Even `/bin/true` cannot start. This indicates an access boundary before Linux execution; it does not justify reinstalling or unregistering a distribution. Whether the same command succeeds in a normal user terminal has not been observed here.

`tools/setup-wsl.ps1` first verifies an explicit distro launch, then invokes the reviewable `tools/setup-linux.sh` for host packages and an unprivileged runner account. It stops without setup if launch access is denied. The Linux script checks cgroup v2, available controllers, systemd, and the minimum bubblewrap version. It does not change Windows security settings, switch Codex permissions, delete distributions, or claim native certification.

The PowerShell entry point was syntax-checked locally. The Linux setup cannot be executed or validated by this session while WSL service access is denied. Run it from an authorized session:

```powershell
& 'Z:\chilicrisp\tools\setup-wsl.ps1'
```

Rootfs preparation, cgroup delegation, kernel fixture evidence and Worldgame pressure trials remain subsequent steps. A working Linux command from another terminal does not itself grant the current agent session WSL access.

The user subsequently confirmed that the script starts Ubuntu successfully from a normal terminal, but the distribution's bubblewrap package is below the required version. Setup now builds upstream 0.12.0 as the unprivileged runner when necessary, checks release commit `2a76602a8c71f36c1527cf9fc3417d9149822e0c`, and installs a non-setuid binary at `/usr/local/bin/bwrap`. The distribution package remains at `/usr/bin/bwrap`. Source identity, binary hash, and build-directory location are saved under `/opt/chili-crisp/bubblewrap-0.12.0`. The upstream source build is not yet executed by the managed Windows agent session.

A subsequent user run reached the systemd-manager gate. Setup now inspects PID 1: when systemd is not the init process, it installs `systemd`/`systemd-sysv`, preserves unrelated `/etc/wsl.conf` settings, backs up an existing changed file, and sets `[boot] systemd=true`. It returns reserved status 20 so PowerShell displays restart/resume instructions instead of a generic setup failure. Restarting the selected distribution is left to the user after saving active work. When systemd is already PID 1, setup waits briefly for the manager and displays its actual error if unreachable. Five portable configuration-edit tests pass, as does PowerShell parsing; actual Linux startup remains untested by this agent session. This follows [Microsoft's WSL systemd setup](https://learn.microsoft.com/en-us/windows/wsl/systemd).
