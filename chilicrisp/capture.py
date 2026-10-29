"""Bounded streaming capture; no unbounded communicate() buffers."""
import hashlib
import threading


def drain(stream, destination, limit, overflow, summary):
    digest = hashlib.sha256()
    count = 0
    try:
        with open(destination, "xb") as output:
            while True:
                chunk = stream.read(8192)
                if not chunk:
                    break
                remaining = max(0, limit - count)
                output.write(chunk[:remaining])
                digest.update(chunk[:remaining])
                count += len(chunk)
                if count > limit:
                    overflow.set()
                    break
        summary.update(bytes=count, sha256=digest.hexdigest(),
                       hash_scope="retained_prefix" if count > limit else "complete_stream",
                       truncated=count > limit)
    except Exception as error:
        summary["error"] = str(error)
        overflow.set()
    finally:
        stream.close()


def capture(process, directory, limit):
    overflow = threading.Event()
    summaries, threads = {}, []
    for name in ("stdout", "stderr"):
        summaries[name] = {}
        thread = threading.Thread(target=drain, args=(
            getattr(process, name), directory / name, limit, overflow, summaries[name]), daemon=True)
        thread.start()
        threads.append(thread)
    return overflow, summaries, threads
