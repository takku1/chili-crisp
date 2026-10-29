"""Deterministic, bounded policy. The controller, not the agent, owns precision."""
from dataclasses import dataclass
from math import isqrt


@dataclass(frozen=True)
class Policy:
    initial_budget: int
    minimum_budget: int = 6291456
    initial_reduction: float = .25
    maximum_reduction: float = .5
    tolerance: float = .05
    confirmation_trials: int = 10
    max_trials: int = 30
    page_size: int = 4096

    def __post_init__(self):
        if not (0 < self.initial_reduction <= self.maximum_reduction < 1):
            raise ValueError("invalid reductions")
        if not (0 < self.tolerance < 1 and self.initial_budget >= self.minimum_budget > 0):
            raise ValueError("invalid budget or tolerance")
        if min(self.confirmation_trials, self.max_trials, self.page_size) < 1:
            raise ValueError("invalid counts")
        if self.initial_budget % self.page_size or self.minimum_budget % self.page_size:
            raise ValueError("budgets must be page aligned")


class Frontier:
    def __init__(self, policy):
        self.p = policy
        self.observations = {}
        self.history = []
        self.passing = self.failing = None
        self.budget = policy.initial_budget
        self.reduction = policy.initial_reduction
        self.stable_passes = 0

    def record(self, outcome):
        if outcome not in {"pass", "oom", "timeout", "wrong_output"}:
            raise ValueError("infrastructure outcomes cannot refine frontier")
        self.observations.setdefault(self.budget, []).append(outcome)
        self.history.append((self.budget, outcome))

    def next(self):
        """Return (EXPLORE/INVENT/STOP, budget or None, reason)."""
        p = self.p
        values = self.observations.get(self.budget, [])
        if len(self.history) >= p.max_trials and len(values) < p.confirmation_trials:
            return "INVENT" if self.passing and self.failing else "STOP", None, "trial_cap"
        if not values:
            return "EXPLORE", self.budget, "screen"
        # A selected point is confirmed with N observations, including its screen.
        if len(values) < p.confirmation_trials:
            return "EXPLORE", self.budget, "confirm"
        if "timeout" in values:
            return "STOP", None, "latency_pressure_requires_diagnosis"
        if "pass" in values and any(v != "pass" for v in values):
            return "STOP", None, "noisy_point_inconclusive"
        if "wrong_output" in values:
            return "STOP", None, "correctness_failure_requires_diagnosis"
        if all(v == "pass" for v in values):
            self.passing = self.budget
            self.stable_passes += 1
        else:
            self.failing = self.budget
            if self.passing is None:
                return "STOP", None, "initial_budget_not_passing"
        if len(self.history) >= p.max_trials:
            return "INVENT" if self.passing and self.failing else "STOP", None, "trial_cap"
        if self.failing is not None:
            if (self.passing - self.failing) / self.passing <= p.tolerance:
                return "INVENT", None, "bracket_ready"
            candidate = isqrt(self.passing * self.failing)
        else:
            # Two confirmed passing points permit the declared maximum reduction.
            if self.stable_passes >= 2:
                self.reduction = p.maximum_reduction
            candidate = max(p.minimum_budget, int(self.budget * (1 - self.reduction)))
        candidate = ((candidate + p.page_size - 1) // p.page_size) * p.page_size
        if candidate == self.budget or candidate in self.observations:
            if self.failing is None:
                reason = ("minimum_budget_reached_without_failure" if self.budget == p.minimum_budget
                          else "resolution_reached_without_failure")
                return "STOP", None, reason
            return "INVENT", None, "resolution_or_floor"
        self.budget = candidate
        return "EXPLORE", candidate, "refine" if self.failing else "descend"
