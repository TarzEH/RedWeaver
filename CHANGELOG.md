# Changelog

All notable changes to RedWeaver are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet.

## [0.10.1] — 2026-07-26

### Security

- **XSS in `MarkdownRenderer`.** `escapeHtml` did not escape `"` or `'`, and link
  targets were interpolated into a quoted `href` before `dangerouslySetInnerHTML`,
  so `[x](" onmouseover="alert(1))` broke out of the attribute. The scheme check
  was a deny-list, which `java\tscript:`, `&#106;avascript:` and a double-encoded
  colon all walked past. Quotes are now escaped, schemes are allow-listed
  (http/https/mailto for links, http/https for images), and URLs are normalized
  before the scheme test.
- **Cross-tenant IDOR in `POST /api/chat`.** The session lookup was an unscoped
  `Session.objects.filter(id=...)`, so any authenticated user could plant a run
  inside another tenant's session and inherit its workspace. It now goes through
  `scoped_get_or_404` — the same rule `HuntCreateSerializer` already applied —
  with a UUID coercion so garbage returns 400 instead of 500.
- **Unscrubbed exception text in the HTML report export.** A provider 401 embeds a
  partial API key in its message, which `build_report` returned verbatim in the
  500 body. Now passed through `scrub_secrets`.

### Fixed

- **Asset severity histogram.** The endpoint returned only `max_severity` and a
  count, so the frontend "recovered" the split by assuming one finding at the peak
  and every other one at low. A session that was 12 critical / 18 high / 15 medium
  / 2 low rendered as "Critical 5, Low 42" — contradicting the severity chart
  directly beneath it. The aggregation now emits the full histogram.
- **Technology extraction matched negative findings**, so "No open ports detected
  on shop.example" became a technology named "on shop.example". It now requires
  the labelled form.

### Changed

- Asset aggregation moved into `apps/hunts/assets.py` as a pure function so it can
  be tested at all (the suite has no `pytest-django`). 21 tests cover the
  histogram, max-severity, grouping, ordering, port and technology extraction,
  exploitability and host resolution.
- README screenshots retaken across ten screens against seeded demo data on the
  reserved `.example` domain (RFC 2606).
- `apps/hunts/assets.py` added to CI's lint scope; `.playwright-mcp/` ignored.

## [0.10.0] — 2026-07-26

### Added

- **Hunt evaluation** (`redweaver_engine/evaluation/scoring.py`, `eval_hunt`) —
  score a completed run's findings against a golden answer key: recall, precision,
  F1, noise. Pure replay off the database, so no LLM calls. `--compare` diffs a run
  against a saved baseline and names regressions.
- **Per-agent model routing** (`redweaver_engine/model_routing.py`) — tiers
  (fast/standard/deep) let recon and crawler run on a cheap model while
  `exploit_analyst` and `report_writer` keep the frontier one. Ships inactive:
  every tier resolves empty, so all 11 agents use the globally selected model.
  Kill switch: `MODEL_ROUTING_ENABLED=false`.
- **Adversarial verification** (`redweaver_engine/crews/verify.py`) — a separate
  agent tries to refute each finding, seeing only evidence-bearing fields. Human
  triage always wins; uncertain verdicts change nothing.
- **Spend ceiling.** `Run.budget_usd` stops a hunt at a cost limit (cancelled,
  findings kept) and keeps `cost_usd` live at every task boundary instead of
  writing it once at the end.
- **Confidence calibration** (`apps/observability/calibration.py`) —
  `calibrate_confidence` fits `derive_confidence`'s weights against human-triaged
  findings by Brier score. Refuses to run below 15 labels per class.
- **Cost, end to end.** Four columns on `RunSummarySerializer` (cost, tokens,
  budget, `completed_at`) unlock spend per hunt, per target, over time and per
  finding with no new endpoint. The dashboard reports p50 and p95, never a mean —
  run cost is long-tailed.
- Route announcer and focus-on-heading for screen readers, scroll restoration
  keyed by pathname, and a run sub-nav reaching the asset-inventory and
  findings-triage screens (which previously had zero links anywhere).
- `docs/TUNING.md`, `backend/evals/golden/README.md`.

### Changed

- **The chat is gone; the hunt flow is three states** — a new-hunt form (target,
  objective, scope, spend limit, SSH, ATT&CK focus), a running view with live
  spend and a Stop button, and the report. The old endpoint contained no LLM call
  at all: a regex pulled a URL out of the text and the "assistant reply" was an
  f-string, and the parser could *reject* valid input. `ChatPanel` (438 lines),
  `ScanIntentParser` and two chat-only utils deleted.
- Dashboard KPI rows adopt `StatGrid` (container queries) instead of sizing off
  the viewport, which gets the wrong answer inside a narrow panel at a wide
  viewport.
- Four implementations of the severity chip collapsed to one reading the shared
  palette; a shared `Table` primitive; empty and loading states throughout.
- `MitreHeatmap` became two ranked tables — the API exposes only a 1-D
  technique→count map, so a matrix would have under-reported silently.
- Knowledge panes become drawers instead of vanishing below ~1100px.
- Entrance animation removed from page containers (it replayed on every route
  change); kept on modals and toasts.

### Security

- **Cross-tenant IDOR (P0).** `HuntCreateSerializer.create` resolved
  caller-supplied `session_id`/`target_ids` with no scoping, so any authenticated
  user could create a run inside another tenant's workspace, read that tenant's
  private target address out of the 201 response, and start a real scan against
  their infrastructure. `SessionViewSet.link_target` reparented any `Target` by id.
  `graph_topology` leaked target type and whether SSH credentials were configured.
  All now resolve through `scoped_get_or_404`.
- **Sandbox escape to RCE (P0).** `file_io` `ALLOWED_ROOTS` included `/app` — the
  code root — `.py` was not blocked, and `validate()` whitelisted the CWD. The
  `file_writer` tool is attached to `report_writer` and `post_exploit`, whose
  context contains text scraped from the target under assessment. A prompt injected
  into a scanned page could rewrite `apps/hunts/tasks.py` and execute as the Celery
  worker. Roots are now the artifacts dir plus `/tmp/redweaver`, the CWD fallback
  is gone, and containment is checked on the realpath at a path-component boundary.
- **Unguarded file reads.** `FileReaderTool` did a bare `Path(...).read_text()` with
  no validation, so the same injected prompt could read `/proc/self/environ` or
  `settings/base.py` and echo the secrets into the report. Now validated through
  the same allow-list.
- **SSRF** — the Ollama settings endpoints took `?url=` straight into `httpx`, an
  oracle for internal hosts. Caller-supplied URLs now go through `check_target`
  with an http/https allow-list and `follow_redirects=False`.
- **Secret leakage** — raw provider exceptions were returned to the browser from
  three endpoints and published into `EventLog`, broadcast to every WebSocket
  subscriber of the run. All now pass through `scrub_secrets`.
- KB embedding config and reindex (global singleton state) were writable by any
  authenticated user, including viewers.

### Fixed

- **Live cost never worked.** `BudgetGuard` read `crew.usage_metrics`;
  `crewai.Crew` has no such attribute — it has `calculate_usage_metrics()`, which
  only then caches onto `usage_metrics`. The guard returned early on every call,
  so both the live cost readout and the budget ceiling were dead code. The first
  test passed because its fake crew exposed the attribute, validating the
  assumption instead of the contract.
- **Findings were displayed 5×.** The engine stamped each published finding event
  with its own uuid and the recorder minted a different one, so the two id spaces
  never collided; the UI now merges on `dedup_key`, so a finding appears once no
  matter how many agents mentioned it — and a refuted one can no longer return
  through a stream twin carrying no status.
- **Reloading a finished run wiped the reasoning timeline** — the backend sends
  `{action, result, ISO timestamp}` and the hydration read `{type, content,
  epoch}`. Typed as `Record<string, unknown>`, so nothing caught it. Now mapped
  through an exhaustive record with a real `AgentStep` type.
- **Cost accuracy.** `costs.py` matched substrings in dict order, so a model could
  be priced as a cheaper prefix, and had no `gpt-5` entries at all — every run on a
  newer model under-reported at `gpt-4o-mini` rates. Matching is now
  longest-key-first, unpriced models are surfaced by `is_priced()`, and the table
  is extendable via `REDWEAVER_MODEL_PRICES`.
- **SSRF-blocked tool calls were recorded as `status="success"`** because
  "blocked" was unmapped and the default was success, destroying the only durable
  evidence that the guard fired. `ToolStatus.BLOCKED` added; the fallback is now
  error, never success.
- Attack-chain linking matched on unbounded substrings, so a step of "ssh"
  attached every finding mentioning it.
- The report endpoint loaded every `ToolExecution` row twice — tens of MB of raw
  nmap/nuclei stdout into the web worker on a read path the UI hits on mount — to
  read two columns. Now one `.only()` query, reused.
- The workspace brand colour was the single unescaped interpolation in the HTML
  export's `<style>` block.
- Stopped and budget-halted runs rendered as grey "Idle" because `theme.ts` kept a
  duplicate `RunStatus` union.
- The dashboard headlined refuted findings as CRITICAL while triage showed the
  same finding struck through; severity facets read "Critical (0)" on a run where
  the verifier had refuted all four, so a working verifier looked like a broken
  scan. They now read "Critical (0) +2" with the hidden count, and a banner states
  how many were ruled out.
- The Debug page silently showed the first 50 rows of everything; it now requests
  the server max, reports the true count, and pages.
- Horizontal overflow: the hunts table pushed the document 328px past the viewport
  at 375px, and `PageHeader`'s action row clipped "New Hunt" off the right edge.
- CI installed only `pytest` and `ruff`, so `tests/test_verification.py` — which
  imports a module declaring its structured-output schema with pydantic at module
  scope — errored at collection and the whole suite never ran. `pydantic` added.
- `vite.config.js` and `tsconfig.node.tsbuildinfo` are `tsc -b` output, not source.
  The `.js` one is the dangerous one: Vite resolves it before `vite.config.ts`, so
  a stale committed copy silently shadows the real config. Both now ignored.

### Testing

Suite grew 25 → 276 tests across this release.

## [0.9.0-beta] — 2026-07-17

First public pre-release.

### Added

- **Multi-agent bug-hunting engine** on CrewAI — recon, crawler, vuln scanner,
  fuzzer, web search, exploit analyst, report writer and SSH agents.
- **Django (DRF + Channels) backend** with PostgreSQL as the single system of
  record: every run, finding, agent transition, tool execution (including raw tool
  output), reasoning step and screenshot is persisted and replayable.
- **Real-time streaming** to the browser over WebSocket, with a "behind the
  scenes" debug view and Django Admin.
- **MITRE ATT&CK scoping** — pick techniques in a built-in picker or paste an
  ATT&CK Navigator layer; the crew is scoped to the agents behind those tactics
  and a focus directive is injected into every task. Any run's coverage exports
  back to a one-click Navigator layer.
- **pgvector knowledge base** — 75 practitioner files across 14 domains (recon →
  web → AD → cloud → C2), each with detection and mitigation, consulted by the
  agents via RAG.
- **Real security tools in Docker**, no host installation: nmap, subfinder, httpx,
  nuclei, nikto, ffuf, gobuster, katana, whatweb, theHarvester.
- **Multi-provider LLM support** — OpenAI, Anthropic, Google, Ollama.
- **HTML report export** with CVSS, EPSS, KEV and SSVC badges, compliance and
  MITRE coverage, and per-run cost.
- Automated GitHub Releases on version-tag push.

[Unreleased]: https://github.com/TarzEH/RedWeaver/compare/v0.10.1...HEAD
[0.10.1]: https://github.com/TarzEH/RedWeaver/compare/v0.10.0...v0.10.1
[0.10.0]: https://github.com/TarzEH/RedWeaver/compare/v0.9.0-beta...v0.10.0
[0.9.0-beta]: https://github.com/TarzEH/RedWeaver/releases/tag/v0.9.0-beta
