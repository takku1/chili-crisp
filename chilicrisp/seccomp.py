"""Compile a default-deny BPF program using the host's libseccomp."""
import ctypes
import ctypes.util
import errno
import tempfile

# Single-process runtime pilot. Threads/process creation, networking, mount,
# ptrace, bpf, perf, shared-memory APIs, and io_uring intentionally absent.
SYSCALLS = """read write readv writev close close_range fstat newfstatat stat lstat
statx lseek pread64 pwrite64 openat open access faccessat faccessat2 readlink
readlinkat getdents64 mmap mprotect munmap mremap madvise brk arch_prctl
set_tid_address set_robust_list rseq futex futex_waitv rt_sigaction rt_sigprocmask
rt_sigreturn sigaltstack clock_gettime clock_nanosleep nanosleep gettimeofday
getrandom getpid getppid gettid getuid geteuid getgid getegid uname sysinfo
getcwd chdir fchdir fcntl ioctl dup dup2 dup3 pipe pipe2 poll ppoll select pselect6
prlimit64 getrlimit getrusage times sched_getaffinity sched_yield wait4 waitid exit exit_group
execve execveat restart_syscall mkdir mkdirat unlink unlinkat rename renameat
renameat2 ftruncate fsync fdatasync umask chmod fchmod fchmodat utimensat
statfs fstatfs""".split()


class ArgumentComparison(ctypes.Structure):
    _fields_ = [("arg", ctypes.c_uint), ("op", ctypes.c_int),
                ("datum_a", ctypes.c_uint64), ("datum_b", ctypes.c_uint64)]


def compile_filter(profile="pilot_allowlist_v1"):
    if profile not in {"pilot_allowlist_v1", "pilot_build_v1"}:
        raise ValueError("Unsupported seccomp profile")
    library = ctypes.util.find_library("seccomp")
    if not library:
        raise RuntimeError("libseccomp unavailable")
    lib = ctypes.CDLL(library)
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    lib.seccomp_rule_add_array.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int,
                                         ctypes.c_uint, ctypes.POINTER(ArgumentComparison)]
    lib.seccomp_export_bpf.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    context = lib.seccomp_init(0x00050000 | errno.EPERM)
    if not context:
        raise RuntimeError("seccomp_init failed")
    stream = tempfile.TemporaryFile()
    try:
        for name in SYSCALLS:
            number = lib.seccomp_syscall_resolve_name(name.encode())
            if number >= 0 and lib.seccomp_rule_add(context, 0x7fff0000, number, 0):
                raise RuntimeError(f"seccomp rule failed: {name}")
        if profile == "pilot_build_v1":
            # x86_64 compiler worker only. No namespace bits are permitted in clone.
            import platform
            if platform.machine() != "x86_64":
                raise RuntimeError("Build seccomp profile currently requires x86_64")
            for name in ("fork", "vfork", "kill", "tgkill"):
                number = lib.seccomp_syscall_resolve_name(name.encode())
                if number >= 0 and lib.seccomp_rule_add(context, 0x7fff0000, number, 0):
                    raise RuntimeError("Build seccomp rule failed: " + name)
            mask = ArgumentComparison(0, 7, 0x7e020080, 0)  # SCMP_CMP_MASKED_EQ
            number = lib.seccomp_syscall_resolve_name(b"clone")
            if number < 0 or lib.seccomp_rule_add_array(context, 0x7fff0000, number, 1, ctypes.byref(mask)):
                raise RuntimeError("Build clone filter failed")
            # clone3 embeds flags behind a pointer. Deny it; ENOSYS permits libc's
            # normal fallback to the argument-filtered clone/vfork paths.
            number = lib.seccomp_syscall_resolve_name(b"clone3")
            if number >= 0 and lib.seccomp_rule_add(context, 0x00050000 | errno.ENOSYS, number, 0):
                raise RuntimeError("Build clone3 denial failed")
        if lib.seccomp_export_bpf(context, stream.fileno()):
            raise RuntimeError("seccomp export failed")
        stream.seek(0)
        return stream
    except Exception:
        stream.close()
        raise
    finally:
        lib.seccomp_release(context)
