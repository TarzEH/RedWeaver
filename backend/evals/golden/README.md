# Golden sets — answer keys for hunt evaluation

Each file here is the answer key for one **intentionally vulnerable** target: the
issues a good hunt should find (`expected`) and the claims that are known-bogus
on that target (`forbidden`). `manage.py eval_hunt` replays a completed run
against a key and reports recall, precision and noise.

Only ever point these at targets you own or that are published for testing.

## Format

```yaml
name: my-target            # defaults to the file name
target: http://host:port   # informational; used to auto-pick a run with --all
notes: free text

expected:                  # what a good hunt must find — drives RECALL
  - id: sqli-login         # stable id, shown in the report
    title_any: ["sql injection", "sqli"]   # any substring, matched on title+description
    url_any: ["/login"]                    # optional: substring of affected_url
    min_severity: high                     # optional: floor on reported severity
    note: why this matters

forbidden:                 # known-false claims for this target — drives PRECISION
  - id: wordpress-noise
    title_any: ["wordpress"]
    note: this target does not run WordPress
```

A rule matches a finding only when **every** constraint it declares holds. A rule
must declare `title_any` or `url_any` — a rule with neither would match
everything, and `eval_hunt` rejects the file rather than silently scoring wrong.

## The three outcomes

| Outcome | Meaning |
|---|---|
| true positive | matched an `expected` rule |
| false positive | matched a `forbidden` rule |
| unscored | the key says nothing about it |

Unscored findings are reported as `noise_ratio`, never folded into precision —
"the key doesn't mention it" is not the same as "it's wrong". As you tune a key,
move recurring unscored findings into `expected` or `forbidden` so more of each
run becomes scorable.

## Calibrating a new key

1. Run a hunt against the target and score it: `manage.py eval_hunt --run <id> --golden <file>`.
2. Read the unscored titles it prints, and sort them into `expected` / `forbidden`.
3. Save the result as a baseline: `--json baselines/<name>.json`.
4. After any prompt/model/tool change, re-score and compare: `--compare baselines/<name>.json`.

The shipped keys are **starting points, not ground truth** — they were written
against the public description of each target, not against a specific run. Tune
them against your own runs before trusting the absolute numbers; the deltas
between runs are meaningful much earlier than the absolute scores are.
