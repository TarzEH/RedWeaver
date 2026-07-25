"""Where the budget guard reads token usage from.

This exists because the original implementation read `crew.usage_metrics` and
nothing else. CrewAI's `Crew` has **no such attribute** until
`calculate_usage_metrics()` has run — it is that method which aggregates each
agent's token process and *then* caches the result onto `usage_metrics`. So the
guard silently saw (0, 0) on every call: live cost never updated during a run,
and the budget ceiling could never trip.

The bug survived its first test because that test's fake crew exposed
`usage_metrics` — it validated the assumption instead of the contract. These
tests pin the real shape: the method is the source of truth.
"""
import pytest

from apps.hunts.budget import usage_from_crew


class Metrics:
    def __init__(self, prompt, completion):
        self.prompt_tokens = prompt
        self.completion_tokens = completion


class RealShapeCrew:
    """Mirrors crewai.Crew: a method that computes, then caches the attribute."""

    def __init__(self, prompt, completion):
        self._metrics = Metrics(prompt, completion)
        self.calls = 0

    def calculate_usage_metrics(self):
        self.calls += 1
        self.usage_metrics = self._metrics  # exactly what crewai does
        return self._metrics


def test_reads_usage_through_the_method_not_a_bare_attribute():
    """The regression: a crew exposing only the method must yield real numbers."""
    crew = RealShapeCrew(1200, 340)
    assert usage_from_crew(crew) == (1200, 340)
    assert crew.calls == 1, "the method must actually be called"


def test_method_is_preferred_over_a_stale_cached_attribute():
    """`usage_metrics` is a cache of the last call — the live method wins."""
    crew = RealShapeCrew(500, 100)
    crew.usage_metrics = Metrics(1, 1)  # stale value from an earlier task
    assert usage_from_crew(crew) == (500, 100)


def test_attribute_only_object_still_works():
    class AttrOnly:
        usage_metrics = Metrics(70, 30)

    assert usage_from_crew(AttrOnly()) == (70, 30)


def test_a_crew_with_neither_yields_zero_rather_than_raising():
    class Bare:
        pass

    assert usage_from_crew(Bare()) == (0, 0)


def test_a_raising_method_degrades_to_zero_not_a_crash():
    """Usage accounting must never take down a hunt."""
    class Exploding:
        def calculate_usage_metrics(self):
            raise RuntimeError("provider blew up")

    assert usage_from_crew(Exploding()) == (0, 0)


def test_a_raising_method_falls_back_to_the_cached_attribute():
    class ExplodingButCached:
        usage_metrics = Metrics(9, 4)

        def calculate_usage_metrics(self):
            raise RuntimeError("transient")

    assert usage_from_crew(ExplodingButCached()) == (9, 4)


@pytest.mark.parametrize("prompt,completion", [(None, None), (0, 0), ("", "")])
def test_missing_or_empty_counters_read_as_zero(prompt, completion):
    class Crew:
        usage_metrics = Metrics(prompt, completion)

    assert usage_from_crew(Crew()) == (0, 0)
