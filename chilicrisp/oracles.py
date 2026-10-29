"""Owner-side output checks; no candidate-provided code is executed."""
import math
import re

NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
HEADER = re.compile(rf"grid=(\d+)x(\d+); seasonal solve=({NUMBER})s; energy\+transport=({NUMBER})ms/1800 world seconds; retained ocean field buffers=({NUMBER})MiB")
RESIDUALS = re.compile(rf"relative budget residuals: water=({NUMBER}), initial salt=({NUMBER}), committed heat=({NUMBER})")
SEASON = re.compile(rf"season (\d+): SolveReport \{{ iterations: (\d+), relative_residual: ({NUMBER}), converged: (true|false) \}}")


def check_ocean(text, policy):
    """Check declared output invariants, not independent physical accuracy."""
    lines = text.splitlines()
    if len(lines) != 2 + policy["seasons"]:
        raise ValueError("unexpected number of output records")
    header, residuals = HEADER.fullmatch(lines[0]), RESIDUALS.fullmatch(lines[1])
    if not header or not residuals:
        raise ValueError("malformed header or conservation record")
    if list(map(int, header.groups()[:2])) != policy["grid"]:
        raise ValueError("grid differs from frozen workload")
    diagnostic = list(map(float, header.groups()[2:]))
    conservation = list(map(float, residuals.groups()))
    if not all(math.isfinite(v) and v >= 0 for v in diagnostic + conservation):
        raise ValueError("non-finite or negative output value")
    if any(v > policy["conservation_abs_max"] for v in conservation):
        raise ValueError("conservation threshold exceeded")
    seasons = []
    for index, line in enumerate(lines[2:]):
        record = SEASON.fullmatch(line)
        if not record or int(record[1]) != index:
            raise ValueError("missing, duplicate, unordered, or malformed season")
        residual = float(record[3])
        if (record[4] != "true" or not math.isfinite(residual) or
                residual < 0 or residual > policy["solver_residual_max"]):
            raise ValueError("seasonal convergence requirement failed")
        seasons.append(dict(season=index, iterations=int(record[2]), residual=residual))
    return dict(pass_checks=True, grid=policy["grid"], conservation=conservation,
                seasons=seasons, diagnostic_only=dict(seasonal_seconds=diagnostic[0],
                transport_ms=diagnostic[1], selected_buffer_mib=diagnostic[2]),
                scope="reported-output invariants; not independent physics validation")
