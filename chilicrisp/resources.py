"""Resource vocabulary and capabilities of the current runner.

These are implementation declarations, not a successful host preflight.
"""

RESOURCES = {
    "memory": {"unit": "bytes", "enforcement": "cgroup memory.max", "search": True},
    "swap": {"unit": "bytes", "enforcement": "cgroup memory.swap.max=0", "search": False},
    "wall_time": {"unit": "seconds", "enforcement": "runner deadline", "search": False},
    "processes": {"unit": "tasks", "enforcement": "cgroup pids.max", "search": False},
    "file_descriptors": {"unit": "descriptors", "enforcement": "RLIMIT_NOFILE", "search": False},
    "scratch": {"unit": "bytes", "enforcement": "bounded tmpfs", "search": False},
    "output": {"unit": "bytes_per_stream", "enforcement": "bounded capture", "search": False},
    "network": {"unit": "access", "enforcement": "isolated namespace; denied syscalls", "search": False},
    "cpu_bandwidth": {"unit": "quota_usec/period_usec", "enforcement": "cgroup cpu.max",
                      "search": False, "grid_sweep": True},
    "cpu_time": {"unit": "seconds", "enforcement": None, "search": False},
    "storage": {"unit": "bytes", "enforcement": None, "search": False},
    "io_bandwidth": {"unit": "bytes_per_second", "enforcement": None, "search": False},
    "io_operations": {"unit": "operations_per_second", "enforcement": None, "search": False},
    "network_bandwidth": {"unit": "bytes_per_second", "enforcement": None, "search": False},
    "gpu_memory": {"unit": "bytes", "enforcement": None, "search": False},
    "energy": {"unit": "joules", "enforcement": None, "search": False},
}


def capabilities():
    return {"backend": "bubblewrap", "host_preflight": "not_run",
            "development_loop": {"backend": "trusted_local_measurement", "requires_vm": False,
                                 "agent_interface": "request/submit or external command",
                                 "acceptance": "experimental retention; no production promotion"},
            "resources": {name: dict(value) for name, value in RESOURCES.items()}}
