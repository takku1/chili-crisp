"""Sum each sensor's readings. Loads every row before aggregating."""
N = 600_000


def readings():
    for i in range(N):
        yield f"{i % 997},{i * 7919 % 100003},sensor-{i % 13}\n"


rows = [line.strip().split(",") for line in readings()]
totals = {}
for _, value, sensor in rows:
    totals[sensor] = totals.get(sensor, 0) + int(value)
print(sorted(totals.items()))
