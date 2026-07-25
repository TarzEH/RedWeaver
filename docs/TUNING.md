# Tuning a hunt: measure, route, verify, cap

Four features that turn "the scan felt better after I changed the prompt" into a
number. They compose into one loop:

```
measure a run   →   change one thing   →   measure again   →   keep or revert
 eval_hunt          routing / prompts        eval_hunt          --compare
```

Everything here is **off or inert by default** except the verification pass.
Nothing changes how your existing installs behave until you configure it.

| Feature | Default | Turn it on with |
|---|---|---|
| [Evaluation harness](#1-measure-what-a-hunt-actually-found) | n/a — a command you run | `manage.py eval_hunt` |
| [Per-agent model routing](#2-route-each-agent-to-the-right-model) | inactive (one model for all agents) | `MODEL_TIER_*` / `AGENT_MODEL_*` |
| [Verification pass](#3-verify-findings-with-an-independent-skeptic) | **on** | `VERIFY_FINDINGS=false` to disable |
| [Budget ceiling](#4-cap-what-a-run-can-spend) | no limit | `RUN_BUDGET_USD` or per-run `budget_usd` |
| [Confidence calibration](#5-calibrate-confidence-against-real-triage) | hand-tuned weights | `manage.py calibrate_confidence` |

---

## 1. Measure what a hunt actually found

`eval_kb` measures whether the knowledge base retrieves the right document.
Nothing measured whether the **hunt** found the right vulnerabilities — so every
prompt, model and tool change was a guess.

`eval_hunt` scores a completed run's findings against a hand-written answer key.
It is a **replay**: it reads the database, makes no LLM calls, costs nothing, and
runs in milliseconds, so it can go in CI.

```bash
python manage.py eval_hunt --run <run-id> --golden evals/golden/juice-shop.yaml
```

```
juice-shop  run=8f3a1c94  target=http://localhost:3000  [delivered (false positives excluded)]
  ✓ found   express-stack
  ✓ found   http-open
  ✓ found   security-headers
  ✗ MISSED  api-endpoints
  ✗ MISSED  exposed-metadata
  ! FP      Apache httpd 2.4.49 path traversal
  recall 60% (3/5)   precision 75%   F1 0.667   noise 41% (7/17)
  cost $0.0430   duration 384s
```

### The three outcomes

| Outcome | Meaning | Feeds |
|---|---|---|
| true positive | matched an `expected` rule | precision, recall |
| false positive | matched a `forbidden` rule (known-bogus for this target) | precision |
| unscored | the answer key is silent about it | `noise_ratio` only |

Unscored findings are **never** folded into precision. "The key doesn't mention
it" is not the same as "it's wrong", and quietly counting it either way would
make the metric a lie. When nothing is scorable, precision reports `n/a` rather
than a free 100%.

### Comparing runs

```bash
# after a change you like the look of
python manage.py eval_hunt --run <before-id> --golden <key> --json evals/baseline.json
python manage.py eval_hunt --run <after-id>  --golden <key> --compare evals/baseline.json
```

`--compare` prints per-metric deltas and, most usefully, `REGRESSION — no longer
found: sqli` when a change quietly cost you a detection.

### Measuring the verification pass

By default `eval_hunt` scores what the pipeline **delivers** (false positives
excluded). `--raw` scores the hunt's unfiltered output. The gap between the two
is exactly what verification is buying you:

```bash
python manage.py eval_hunt --run <id> --golden <key> --raw   # precision 61%
python manage.py eval_hunt --run <id> --golden <key>         # precision 88%
```

### Writing an answer key

See [`backend/evals/golden/README.md`](../backend/evals/golden/README.md). The
two shipped keys (`acuart-vulnweb`, `juice-shop`) are **starting points written
from each target's public description, not from a scored run** — tune them
against your own runs before treating the absolute numbers as fact. Deltas
between runs are trustworthy long before absolute scores are.

---

## 2. Route each agent to the right model

Every agent used to share one LLM. But `recon`, `crawler` and `fuzzer` mostly
reformat huge tool dumps into JSON — cheap-model work — while `exploit_analyst`,
`report_writer` and the attack playbook do the actual reasoning. Splitting them
typically cuts run cost by more than half at equal quality.

**Routing ships inactive.** Every tier in
[`backend/redweaver_engine/config/model_routing.yaml`](../backend/redweaver_engine/config/model_routing.yaml)
has an empty `model`, so every agent uses the globally selected model exactly as
before. **No provider is ever inferred** — a local runtime like Ollama is used
only where you name it explicitly.

### Tiers

| Tier | Agents |
|---|---|
| `fast` | recon, crawler, fuzzer, web_search, verifier |
| `standard` | vuln_scanner, privesc, tunnel_pivot, post_exploit |
| `deep` | exploit_analyst, report_writer, attack |

```bash
# Cheap model for the bulk work, frontier model for the reasoning.
MODEL_TIER_FAST=gpt-4.1-nano
MODEL_TIER_DEEP=gpt-5

# Or one specific agent, overriding its tier.
AGENT_MODEL_REPORT_WRITER=claude-sonnet-4-6

# Or put one tier on a self-hosted model — opt-in, never a default.
MODEL_TIER_FAST_PROVIDER=ollama
MODEL_TIER_FAST=llama3.2

MODEL_ROUTING_ENABLED=false   # kill switch: ignore the config entirely
```

Resolution order, first non-empty wins:

1. `AGENT_MODEL_<AGENT>` / `AGENT_PROVIDER_<AGENT>`
2. vault keys `agent_model_<agent>` / `agent_provider_<agent>`
3. `MODEL_TIER_<TIER>` / `MODEL_TIER_<TIER>_PROVIDER`
4. vault keys `model_tier_<tier>` / `model_tier_<tier>_provider`
5. `model:` / `provider:` in `model_routing.yaml`
6. the globally selected model and provider

A tier that names only a provider uses that provider's default model. A broken
override never takes a hunt down — the agent falls back to the default LLM and
logs a warning.

**Then measure it.** Routing is exactly the kind of change that feels free and
might not be: score a run before and after with `eval_hunt --compare`.

---

## 3. Verify findings with an independent skeptic

The hunt's `exploit_analyst` reports its own `false_positives` list — the same
model grading its own homework. It reliably misses the failure mode that matters:
a confident, well-formatted finding the evidence does not support.

The verification pass is a separate agent, run after the hunt over the persisted
findings, prompted only to **refute**. It sees the evidence-bearing fields only
(`title`, `description`, `affected_url`, `evidence`, `tool_used`, CVE/CVSS) —
severity labels and remediation prose are withheld so it judges the evidence
rather than the confidence of the writing.

```bash
VERIFY_FINDINGS=true      # default
VERIFY_MAX_FINDINGS=25    # cap per run — verification costs one batched call
VERIFY_MIN_SEVERITY=low   # skip info-level noise; verifying "port 443 is open" proves nothing
```

Two rules it will not break:

- **Human triage always wins.** A finding someone has already moved off `new` is
  never touched, so hand-labelled findings stay usable as ground truth for
  calibration and `eval_hunt`.
- **Uncertainty changes nothing.** Only a verdict above threshold (0.65 to
  refute, 0.70 to confirm) moves status; anything weaker adjusts `confidence`
  at most.

Verdicts land on `Finding.status`, `Finding.confidence` and
`Finding.verified_by_agent`, and surface in three places:

- **Findings triage** — a refuted finding is struck through, desaturated and
  dashed, not just another coloured chip. "Hide ruled out" is on by default with
  the count always visible, and every facet count states which population it
  describes. Hover the badge to see which agent adjudicated it.
- **The report** — refuted findings no longer feed the severity counts, the risk
  rating or the remediation plan. They stay listed with their status, and
  `false_positive_count` / `false_positive_titles` say what was excluded.
- **`eval_hunt`** — the `--raw` vs default gap, which is the measurement.

`run.report_markdown` — the narrative the report_writer produced *during* the
hunt — is frozen before verification runs and does **not** reflect the verdicts.
The HTML/JSON report is generated on request from the database, so it does.

### What this looked like in practice

A hunt against a Cloudflare-fronted host reported five findings the evidence did
not support — a 2025 Cloudflare CVE at **critical**, and four 2009-era nginx CVEs
at high/medium — all matched against a banner with nothing tying those versions
to the host. The verifier refuted all five:

```
before   Overall Risk: Critical   1 critical · 1 high · 3 medium
after    Overall Risk: Low        0 critical · 0 high · 0 medium
```

---

## 4. Cap what a run can spend

A hunt is a long agentic loop; a target that keeps producing tool output can
quietly burn far more than intended.

```bash
RUN_BUDGET_USD=2.00       # installation-wide default; 0 (the default) = no limit
```

```jsonc
POST /api/hunts/   { "target_ids": [...], "budget_usd": "0.50" }   // per run
```

When the ceiling is crossed the run stops, keeps every finding gathered so far,
still runs verification, and is marked **cancelled** — not completed, because it
never had the coverage a completed run claims.

Enforcement is at **task** granularity, not per token: a single task can
overshoot before the next check. Treat it as a circuit breaker, not a hard cap.

A side benefit: `Run.cost_usd` is now refreshed at every task boundary instead of
only being written once at the end, so the UI shows spend as it accrues.

### Cost accuracy

`costs.py` matches model ids by substring, **longest key first** — so
`gpt-4o-mini` can no longer be priced as `gpt-4o`. Models with no price entry are
reported by `is_priced()` and logged, instead of being silently billed at
gpt-4o-mini rates. Correct or extend the table without a code change:

```bash
REDWEAVER_MODEL_PRICES='{"gpt-5.3": [1.25, 10.0], "my-local-model": [0, 0]}'
```

---

## 5. Calibrate confidence against real triage

`Finding.confidence` is a clamped linear sum of corroborating signals (KEV, EPSS,
CVSS, CVE refs, exploitability, evidence). Those weights were picked by hand.
Once analysts have triaged findings, that intuition can be replaced with a
measurement:

```bash
python manage.py calibrate_confidence
```

It fits the weights on the **same** clamped linear model that ships in
production, minimising Brier score (mean squared error against the 0/1 label),
using plain coordinate descent — no numpy, no new dependency. It prints the
before/after Brier score, the fitted weights, and how many labelled findings
exercised each one:

```
  feature          weight   (was)   support
  cisa_kev          0.310   0.250      41
  epss_high         0.150   0.100       6  ⚠ low support
```

It **never applies the weights itself** — it prints a `CONFIDENCE_WEIGHTS` value
you set deliberately:

```bash
CONFIDENCE_WEIGHTS='{"bias": 0.35, "cisa_kev": 0.31, ...}'   # partial overrides merge
```

Guardrails, because a fit on a handful of labels is worse than not fitting at
all: it refuses to run below 15 labelled findings per class, bounds every weight
to `[-0.5, 0.6]` so one over-represented signal cannot dominate, and flags any
weight fitted on fewer than 10 samples as untrustworthy.

---

## Running the checks

```bash
cd backend && python -m pytest tests/ -q
```

The scoring, routing, cost, verification and calibration logic is all pure — no
Django, no database, no network — so the suite runs in well under a second.
