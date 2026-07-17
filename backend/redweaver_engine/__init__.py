"""redweaver_engine — framework-agnostic CrewAI bug-hunting engine.

Moved verbatim from the legacy FastAPI ``app`` package so it can be imported
by the Django apps (and by tests) with zero Django dependencies. Contains the
CrewAI crew/agents, the security-tool registry + adapters, report generation,
external API clients, the LLM factory, and the huntflow tree types.
"""
