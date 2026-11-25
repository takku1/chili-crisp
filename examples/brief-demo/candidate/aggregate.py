"""Sum each sensor's readings. Streams: one row in memory at a time."""
N = 600_000


def readings():
    for i in range(N):
        yield f"{i % 997},{i * 7919 % 100003},sensor-{i % 13}\n"


totals = {}
for line in readings():
    _, value, sensor = line.rstrip("\n").split(",")
    totals[sensor] = totals.get(sensor, 0) + int(value)
print(sorted(totals.items()))
