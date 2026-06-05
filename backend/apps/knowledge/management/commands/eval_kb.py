"""Retrieval evaluation harness for the pgvector KB.

Runs a small labeled set of (query -> expected file substring) cases through
kb_search and reports hit@k and MRR, so changes to the embedding model,
chunking, threshold, or hybrid re-ranking can be measured instead of guessed.

    python manage.py eval_kb [--k 5]
"""
from django.core.management.base import BaseCommand

# query -> substring expected in the top result's file path
EVAL_SET = [
    ("linux privilege escalation SUID binary", "privilege-escalation"),
    ("sql injection sqlmap payload", "sql-injection"),
    ("cross site scripting XSS payload", "cross-site-scripting"),
    ("nmap port scanning service enumeration", "reconnaissance"),
    ("hydra brute force ssh password", "password-attacks"),
    ("nuclei vulnerability scanning templates", "vulnerability-scanning"),
    ("active directory kerberoasting", "active-directory"),
    ("metasploit exploit module", "exploitation"),
    ("ssh tunneling port forwarding pivot", "tunneling"),
    ("aws cloud s3 bucket enumeration", "cloud-security"),
    ("credential harvesting post exploitation", "post-exploitation"),
    ("pentest report executive summary", "reporting"),
]


class Command(BaseCommand):
    help = "Evaluate KB retrieval quality (hit@k, MRR) over a labeled query set."

    def add_arguments(self, parser):
        parser.add_argument("--k", type=int, default=5)

    def handle(self, *args, **opts):
        from apps.knowledge.search import kb_search

        k = opts["k"]
        hits, rr_sum = 0, 0.0
        for query, expect in EVAL_SET:
            results = kb_search(query, top_k=k)
            rank = next(
                (i + 1 for i, r in enumerate(results) if expect in (r.get("file") or "")),
                None,
            )
            ok = rank is not None
            hits += 1 if ok else 0
            rr_sum += (1.0 / rank) if rank else 0.0
            top = results[0]["file"] if results else "—"
            mark = "✓" if ok else "✗"
            self.stdout.write(f"  {mark} hit@{k}={'Y' if ok else 'N'} rank={rank or '-'}  "
                              f"{query[:42]:42}  top={top}")
        n = len(EVAL_SET)
        self.stdout.write(self.style.SUCCESS(
            f"\nhit@{k} = {hits}/{n} ({hits / n:.0%})   MRR = {rr_sum / n:.3f}"
        ))
