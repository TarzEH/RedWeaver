"""Token usage must be summed per LLM *object*, not per agent.

crewai's `Crew.calculate_usage_metrics()` walks `self.agents` and adds every
agent's `agent.llm.get_token_usage_summary()`. RedWeaver hands the *same*
`crewai.LLM` instance to every agent unless model routing overrides it (see
`AgentLLMResolver.for_agent`), and token counters accumulate on that one shared
object. So a 7-agent crew reported the same totals seven times.

Measured live: 2,283,995 tokens after a single completed task, against a
3,703,308-token total for a whole previous 7-task run. The end-of-run figure
looked fine only because it comes from `result.token_usage` — a different
mechanism — so cost ballooned mid-run and snapped back at the end. The part
that actually hurts: the budget ceiling trips ~7x early, killing a $1.50 hunt
at roughly $0.20 of real spend.

The fix sums once per distinct LLM instance, by identity. These tests pin both
halves of that: shared objects collapse, genuinely different ones do not.
"""
from apps.hunts.budget import usage_from_crew


class Summary:
    """Shaped like crewai's UsageMetrics."""

    def __init__(self, prompt, completion):
        self.prompt_tokens = prompt
        self.completion_tokens = completion
        self.total_tokens = (prompt or 0) + (completion or 0)


class FakeLLM:
    """Shaped like crewai.LLM: cumulative counters, read via a summary method."""

    def __init__(self, prompt, completion, model="gpt-4o-mini", temperature=0.1):
        self.prompt_tokens = prompt
        self.completion_tokens = completion
        self.model = model
        self.temperature = temperature
        self.summary_calls = 0

    def get_token_usage_summary(self):
        self.summary_calls += 1
        return Summary(self.prompt_tokens, self.completion_tokens)

    def __eq__(self, other):
        # Deliberate: pydantic models compare by field value. If the dedup used
        # equality instead of identity, two distinct LLMs configured the same
        # way would collapse into one and real spend would be under-counted.
        return (
            isinstance(other, FakeLLM)
            and (self.model, self.temperature) == (other.model, other.temperature)
        )

    __hash__ = None  # like a mutable pydantic model: unhashable


class FakeAgent:
    def __init__(self, llm):
        self.llm = llm


class FakeCrew:
    """Mirrors crewai.Crew closely enough for the accounting question.

    `calculate_usage_metrics()` reproduces crewai's own per-*agent* summation —
    the buggy source — so any implementation that leans on it for a crew with a
    shared LLM will over-count and fail these tests.
    """

    def __init__(self, agents, manager_agent=None):
        self.agents = agents
        if manager_agent is not None:
            self.manager_agent = manager_agent

    def calculate_usage_metrics(self):
        prompt = completion = 0
        holders = list(self.agents)
        manager = getattr(self, "manager_agent", None)
        if manager is not None:
            holders.append(manager)
        for agent in holders:
            summary = agent.llm.get_token_usage_summary()
            prompt += summary.prompt_tokens
            completion += summary.completion_tokens
        self.usage_metrics = Summary(prompt, completion)
        return self.usage_metrics


# --- the regression -------------------------------------------------------

def test_one_shared_llm_across_seven_agents_is_counted_once():
    """The live bug: an unrouted RedWeaver crew shares a single LLM object."""
    shared = FakeLLM(300_000, 26_285)
    crew = FakeCrew([FakeAgent(shared) for _ in range(7)])

    assert usage_from_crew(crew) == (300_000, 26_285)


def test_shared_llm_does_not_scale_with_crew_size():
    """Same LLM state, different agent counts -> identical reported usage."""
    def usage_for(n_agents):
        shared = FakeLLM(1_000, 250)
        return usage_from_crew(FakeCrew([FakeAgent(shared) for _ in range(n_agents)]))

    assert usage_for(1) == usage_for(3) == usage_for(7) == (1_000, 250)


def test_a_shared_llm_is_summarised_only_once():
    """Not just arithmetic: the shared object is visited a single time."""
    shared = FakeLLM(10, 5)
    usage_from_crew(FakeCrew([FakeAgent(shared) for _ in range(5)]))

    assert shared.summary_calls == 1


# --- routing active: distinct objects must all count ----------------------

def test_agents_with_genuinely_different_llms_are_all_counted():
    """With model routing on, each routed agent holds its own LLM."""
    crew = FakeCrew([
        FakeAgent(FakeLLM(100, 10, model="gpt-4o-mini")),
        FakeAgent(FakeLLM(200, 20, model="claude-haiku")),
        FakeAgent(FakeLLM(400, 40, model="gpt-4o")),
    ])

    assert usage_from_crew(crew) == (700, 70)


def test_routing_mix_shared_default_plus_one_override():
    """Realistic routing: most agents on the default, one on its own model."""
    default = FakeLLM(1_000, 100, model="gpt-4o-mini")
    routed = FakeLLM(50, 5, model="gpt-4o")
    crew = FakeCrew([
        FakeAgent(default), FakeAgent(default), FakeAgent(default),
        FakeAgent(routed),
        FakeAgent(default),
    ])

    assert usage_from_crew(crew) == (1_050, 105)


def test_identical_config_but_distinct_objects_are_counted_twice():
    """Proves identity-based dedup, not equality-based.

    These two compare equal (as pydantic models with the same fields would),
    yet they are separate LLMs with separate counters. Both must count.
    """
    first = FakeLLM(500, 50, model="gpt-4o-mini", temperature=0.1)
    second = FakeLLM(500, 50, model="gpt-4o-mini", temperature=0.1)
    assert first == second, "the double must actually compare equal by value"
    assert first is not second

    assert usage_from_crew(FakeCrew([FakeAgent(first), FakeAgent(second)])) == (1_000, 100)


# --- manager agent --------------------------------------------------------

def test_manager_agent_llm_is_included():
    worker = FakeLLM(100, 10)
    manager = FakeLLM(700, 70)
    crew = FakeCrew([FakeAgent(worker), FakeAgent(worker)], manager_agent=FakeAgent(manager))

    assert usage_from_crew(crew) == (800, 80)


def test_manager_sharing_the_agents_llm_is_not_double_counted():
    shared = FakeLLM(100, 10)
    crew = FakeCrew([FakeAgent(shared), FakeAgent(shared)], manager_agent=FakeAgent(shared))

    assert usage_from_crew(crew) == (100, 10)


def test_a_none_manager_agent_is_ignored():
    shared = FakeLLM(100, 10)
    crew = FakeCrew([FakeAgent(shared)])
    crew.manager_agent = None

    assert usage_from_crew(crew) == (100, 10)


# --- degradation: accounting must never take down a hunt ------------------

def test_agents_without_an_llm_attribute_are_skipped():
    class LLMLess:
        pass

    good = FakeLLM(100, 10)
    assert usage_from_crew(FakeCrew([LLMLess(), FakeAgent(good)])) == (100, 10)


def test_agents_with_llm_none_are_skipped():
    good = FakeLLM(100, 10)
    assert usage_from_crew(FakeCrew([FakeAgent(None), FakeAgent(good)])) == (100, 10)


def test_an_llm_without_the_summary_method_is_skipped():
    class Opaque:
        pass

    good = FakeLLM(100, 10)
    assert usage_from_crew(FakeCrew([FakeAgent(Opaque()), FakeAgent(good)])) == (100, 10)


def test_one_exploding_llm_does_not_lose_the_others():
    class Exploding:
        def get_token_usage_summary(self):
            raise RuntimeError("provider blew up")

    good = FakeLLM(100, 10)
    assert usage_from_crew(FakeCrew([FakeAgent(Exploding()), FakeAgent(good)])) == (100, 10)


def test_a_summary_of_none_is_skipped():
    class NoSummary:
        def get_token_usage_summary(self):
            return None

    good = FakeLLM(100, 10)
    assert usage_from_crew(FakeCrew([FakeAgent(NoSummary()), FakeAgent(good)])) == (100, 10)


def test_missing_counters_on_a_summary_read_as_zero():
    class Blank:
        def get_token_usage_summary(self):
            return object()

    good = FakeLLM(100, 10)
    assert usage_from_crew(FakeCrew([FakeAgent(Blank()), FakeAgent(good)])) == (100, 10)


def test_empty_or_none_counters_do_not_raise():
    llm = FakeLLM(None, "")
    assert usage_from_crew(FakeCrew([FakeAgent(llm)])) == (0, 0)


# --- falling back rather than reporting a false zero ----------------------

def test_no_agents_attribute_falls_back_to_the_crew_aggregate():
    """A crew shaped unlike ours must keep the old behaviour, not report zero."""
    class Legacy:
        def calculate_usage_metrics(self):
            return Summary(1_200, 340)

    assert usage_from_crew(Legacy()) == (1_200, 340)


def test_agents_none_falls_back_to_the_crew_aggregate():
    class Odd:
        agents = None

        def calculate_usage_metrics(self):
            return Summary(11, 7)

    assert usage_from_crew(Odd()) == (11, 7)


def test_non_iterable_agents_falls_back_to_the_crew_aggregate():
    class Odd:
        agents = 7  # not a collection

        def calculate_usage_metrics(self):
            return Summary(11, 7)

    assert usage_from_crew(Odd()) == (11, 7)


def test_agents_with_no_usable_llm_at_all_falls_back_not_zero():
    """Unknown != zero: an empty crew must not silently mask real spend."""
    class Empty:
        agents = []

        def calculate_usage_metrics(self):
            return Summary(64, 32)

    assert usage_from_crew(Empty()) == (64, 32)


def test_agents_with_no_usable_llm_and_no_aggregate_yields_zero():
    class Nothing:
        agents = []

    assert usage_from_crew(Nothing()) == (0, 0)


def test_a_raising_agents_walk_falls_back_to_the_crew_aggregate():
    class Hostile:
        @property
        def agents(self):
            raise RuntimeError("attribute access blew up")

        def calculate_usage_metrics(self):
            return Summary(5, 3)

    assert usage_from_crew(Hostile()) == (5, 3)


def test_per_instance_sum_wins_over_the_crew_aggregate():
    """When both sources exist, the deduped one is authoritative."""
    shared = FakeLLM(1_000, 100)
    crew = FakeCrew([FakeAgent(shared) for _ in range(7)])
    crew.usage_metrics = Summary(7_000, 700)  # the inflated cached value

    assert usage_from_crew(crew) == (1_000, 100)
