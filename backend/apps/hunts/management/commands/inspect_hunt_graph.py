"""Inspect the deepagents/LangGraph hunt DAG for a target — no LLM calls.

Prints the selected agents and the directed edges the engine would build, so the
deterministic pipeline wiring can be validated cheaply (Phase 4 parity tooling).

    python manage.py inspect_hunt_graph --target https://example.com
    python manage.py inspect_hunt_graph --target 10.0.0.5 --ssh
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Print the deepagents hunt DAG (nodes + edges) for a target — no LLM."

    def add_arguments(self, parser):
        parser.add_argument("--target", required=True)
        parser.add_argument("--objective", default="comprehensive")
        parser.add_argument("--ssh", action="store_true", help="include an SSH target")
        parser.add_argument("--techniques", default="", help="comma-separated ATT&CK technique IDs")

    def handle(self, *args, **opts):
        from redweaver_engine.crews.bug_hunt.graph_engine import (
            AGENT_SCHEMAS,
            SSH_AGENTS,
            END_SENTINEL,
            START_SENTINEL,
            plan_dag,
        )
        from redweaver_engine.crews.bug_hunt.selection import select_agent_names

        ssh_config = {"host": "10.0.0.5", "username": "root"} if opts["ssh"] else None
        techniques = [t.strip() for t in opts["techniques"].split(",") if t.strip()] or None

        ttype, selected = select_agent_names(
            opts["target"], opts["objective"], ssh_config, attack_techniques=techniques
        )
        present = [a for a in selected if a in AGENT_SCHEMAS]
        if ssh_config:
            present += [a for a in SSH_AGENTS if a not in present]

        self.stdout.write(f"target type : {ttype}")
        self.stdout.write(f"agents ({len(present)}): {', '.join(present)}")
        self.stdout.write("edges:")
        for a, b in plan_dag(present):
            a = "START" if a == START_SENTINEL else a
            b = "END" if b == END_SENTINEL else b
            self.stdout.write(f"  {a} -> {b}")
