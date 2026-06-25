# Refactor: CrewAI → LangChain deepagents (+ Ragas evaluation)

Status: **PLAN** · Branch: `refactor/deepagents-ragas` · Owner: Ori

This document is the plan of record for migrating RedWeaver's multi-agent engine
from **CrewAI** to **LangChain `deepagents`** (on a LangGraph DAG), and for adding
a **Ragas**-based RAG evaluation harness. It is written to be executed in phases
behind a feature flag, with CrewAI kept working until parity is proven.

---

## 1. Goals & non-goals

**Goals**
- Replace CrewAI orchestration with `deepagents` sub-agents wired into an explicit
  **LangGraph StateGraph**, preserving the deterministic hunt pipeline
  (recon → {fuzzer ∥ vuln-scan ∥ crawler} → web-search → exploit → [SSH chain] →
  report) and its parallel batching.
- Preserve **end-to-end observability**: every tool execution (with raw
  stdout/stderr), agent step/transition, finding, and event still persisted to
  Postgres and streamed to the "behind the scenes" UI.
- Add a **Ragas** evaluation harness for the pgvector RAG, reusing the existing
  multi-provider LLM + embeddings (including offline HF/Ollama).
- Keep multi-provider LLM support and the UI-first key/model selection intact.

**Non-goals (this branch)**
- No change to the knowledge-base content, chunking, or embedding storage.
- No removal of the legacy Chroma `knowledge-service` (already fallback-only).
- Final deletion of CrewAI deps is a *follow-up* once deepagents is the proven
  default (see Phase 6).

---

## 2. Decisions (agreed)

1. **Control flow:** explicit **LangGraph DAG** with each agent as a `deepagents`
   sub-agent node. Not a pure LLM-driven orchestrator — RedWeaver needs
   guaranteed ordering, the parallel fuzz/scan batch, and a deterministic
   observability timeline.
2. **Migration mode:** **incremental, feature-flagged.** Pin a `deepagents`
   version; keep CrewAI behind `HUNT_ENGINE=crewai` (default) while building
   `HUNT_ENGINE=deepagents`. Migrate **offsec first** (single agent), then
   **bug_hunt**. Flip the default only after parity.
3. **Sequencing:** **deepagents first, then Ragas.**

---

## 3. Why this is non-trivial (research summary)

- `deepagents` (v0.6.x, **pre-1.0, weekly API churn** — `instructions`→
  `system_prompt`, sub-agent key drift, streaming v3) is an opinionated harness
  over LangGraph. Its native orchestration is **emergent/LLM-driven** and
  **sub-agent delegation is synchronous/blocking by default** — which is exactly
  what RedWeaver must *not* rely on. → We use its sub-agent + tooling primitives
  but drive control flow with our own LangGraph DAG.
- What's **orchestrator-agnostic and survives**: YAML agent/task configs, Pydantic
  schemas (`crews/bug_hunt/schemas.py`), `ToolRegistry`/`BugHuntTool` protocol,
  the **instrumentation seam** (`tools/instrumentation.py` pluggable sinks),
  `LLMFactory` (provider/key resolution), Celery dispatch, Django persistence.
- What's **CrewAI-coupled and gets rewritten**: `crews/bug_hunt/builder.py`
  (`Agent/Task/Crew/Process`), `tools/crewai_adapter.py` (`crewai.tools.BaseTool`),
  `crews/bug_hunt/callbacks.py` (step/task callbacks → CrewAIEventBridge),
  `crews/offsec.py`, and `apps/hunts/crew_factory.py::_build_crewai_llm`.

---

## 4. Target architecture

### 4.1 Engine abstraction (the feature-flag seam)
Introduce a thin engine interface that `apps/hunts/tasks.py` and
`apps/hunts/offsec_tasks.py` call instead of CrewAI directly:

```
HuntEngine (protocol)
  run_hunt(run, target, scope, objective, ssh_config, attack_techniques, bridge) -> HuntResult
  run_offsec(run, target, findings, research_context, bridge) -> str  # markdown

CrewAIEngine(HuntEngine)      # wraps the existing CrewFactory + crew.kickoff()
DeepAgentsEngine(HuntEngine)  # new: LangGraph DAG of deepagents sub-agents
```

`HuntResult` normalizes `{ findings, report_markdown, prompt_tokens,
completion_tokens, raw_outputs }` so the Celery task body is engine-agnostic.
Selection: `settings.HUNT_ENGINE` (env `HUNT_ENGINE`, default `crewai`).

### 4.2 bug_hunt as a LangGraph StateGraph
- **State** (`DeepAgentState` subclass): `messages`, per-agent structured outputs,
  accumulated `findings`, `report_markdown`, `target/scope/attack_focus`.
- **Nodes**: one per selected agent. Each node builds a `deepagents` sub-agent via
  `create_deep_agent(model=<langchain chat model>, tools=<registry tools for agent>,
  system_prompt=<from agents.yaml>, response_format=<agent schema>)` and invokes it
  on the node's slice of state.
- **Edges (the DAG)** — built dynamically from `select_agent_names(...)`:
  - `START → recon`
  - `recon → {fuzzer, vuln_scanner, crawler}` (fan-out, run concurrently)
  - `{fuzzer, vuln_scanner, crawler, web_search} → exploit_analyst` (fan-in/join)
  - `exploit_analyst → [privesc → tunnel_pivot → post_exploit]?` (SSH tier)
  - `… → report_writer → END`
  - ATT&CK plan / objective narrows which nodes exist (reuse `attack_planning.py`,
    `selection.py` unchanged — they output an agent-name list).
- **Parallelism**: LangGraph runs independent branches concurrently → preserves the
  fuzzer ∥ vuln-scan batch deterministically (no reliance on an LLM to parallelize).
- **Structured output**: `response_format=<PydanticSchema>` per sub-agent; reuse
  `schemas.py` as-is.

### 4.3 Tooling
- New `tools/langchain_adapter.py`: wrap each `BugHuntTool` as a LangChain tool
  (`StructuredTool`), porting the existing `_run` body from `crewai_adapter.py`
  **verbatim** — SSRF `check_target`, instrumentation (`publish_event` tool_call/
  tool_result, `record_tool_execution` with raw CLI capture), 12k truncation. This
  is the single chokepoint; reusing it keeps observability identical.
- `knowledge_search` tool ported the same way (dual pgvector→HTTP fallback intact).

### 4.4 LLM factory
- Add `LLMFactory.build_langchain_llm(model_override=None) -> BaseChatModel` using
  `langchain.chat_models.init_chat_model` over the already-present provider packages
  (`langchain-openai/-anthropic/-google-genai/-ollama`). Reuse provider/key
  resolution. `deepagents` accepts a `BaseChatModel` instance directly.

### 4.5 Observability bridge
- Replace `CrewAIEventBridge` with `LangGraphEventBridge` that consumes
  `graph.astream_events(..., version="v3")` / `stream_mode=["updates","messages"]`
  and emits the **same** events to the existing sinks:
  - tool_call/tool_result + raw execution → already emitted by the tool adapter
    (unchanged path).
  - agent enter/exit → AgentStep + AgentTransition.
  - per-node structured output → finding extraction (port `task_callback` logic).
  - `stream.subagents` gives per-sub-agent streams for nested visibility.
- Token/cost: sum `usage_metadata` from streamed AI messages → `prompt_tokens`/
  `completion_tokens`; keep `estimate_cost_usd`.

---

## 5. Phased execution plan

> Each phase is independently mergeable to the branch and leaves `main` behavior
> unchanged until Phase 4 flips the default.

### Phase 0 — Scaffolding & flag (no behavior change)
- Pin deps: `deepagents==<pinned>`, `langgraph` (pin transitive), keep
  `langchain-*` providers. Add `HUNT_ENGINE` setting (default `crewai`).
- Add `HuntEngine` protocol + `HuntResult`; wrap current path as `CrewAIEngine`.
- Refactor `tasks.py`/`offsec_tasks.py` to call the engine interface (CrewAI still
  runs). **Accept:** existing hunts pass unchanged; `HUNT_ENGINE=crewai` is default.

### Phase 1 — LangChain tool adapter + LLM builder + event bridge
- `tools/langchain_adapter.py` (port `_run`), `knowledge_search` LC tool.
- `LLMFactory.build_langchain_llm`.
- `LangGraphEventBridge` skeleton mapping stream events → sinks.
- **Accept:** unit tests: a wrapped tool records a `ToolExecution` with raw output
  identical to the CrewAI path; LLM builder returns a working chat model per provider.

### Phase 2 — Migrate **offsec** to deepagents (behind flag)
- `crews/offsec_da.py`: single `create_deep_agent` with knowledge/web/cve tools,
  markdown output. Engine routes offsec to it when `HUNT_ENGINE=deepagents`.
- **Accept:** with the flag on, an offsec playbook generates with KB grounding and
  the same persisted events; markdown quality ≈ CrewAI version on a sample run.

### Phase 3 — Migrate **bug_hunt** to the LangGraph DAG (the big one)
- `crews/bug_hunt/graph_engine.py`: dynamic StateGraph builder from
  `select_agent_names`; nodes = deepagents sub-agents; edges = the DAG in §4.2;
  parallel fan-out/fan-in; structured outputs via `response_format`.
- Wire `LangGraphEventBridge` for full observability + finding extraction +
  token accounting.
- **Accept (parity):** on a fixed test target, deepagents engine produces
  findings, a structured report, a complete observability timeline (tool raw
  output, agent transitions, screenshots), and token/cost numbers comparable to
  CrewAI. Parallel batch visibly concurrent.

### Phase 4 — Parity validation & default flip
- Side-by-side runs (CrewAI vs deepagents) on web + host + SSH targets; compare
  findings count/severity, report sections, event completeness, latency, cost.
- Flip default `HUNT_ENGINE=deepagents`; keep CrewAI selectable for one release.
- **Accept:** no regression in finding quality guards or report rendering; UI
  debug surface fully populated.

### Phase 5 — Ragas evaluation harness
- Add `ragas` (pin `>=0.4,<0.5`) + `rapidfuzz` (non-LLM metrics).
- `apps/knowledge/eval/ragas_eval.py`: build `EvaluationDataset` from a golden
  set; wrap the active LLM (`LangchainLLMWrapper`) + embeddings
  (`LangchainEmbeddingsWrapper`, supports offline HF/Ollama).
- Metrics: `LLMContextPrecisionWithReference`, `LLMContextRecall`, `Faithfulness`,
  `ResponseRelevancy` (+ optional `FactualCorrectness`).
- Golden set: start by upgrading the 12 inline `eval_kb.py` queries into a
  JSON/YAML fixture with `reference`/`reference_contexts`; optionally seed more via
  `TestsetGenerator` over `knowledge-base/`.
- New mgmt command `eval_kb_ragas` (thresholds + `--json` artifact;
  `raise_exceptions=False`, tuned `RunConfig` timeouts for local models).
- Optional `KbEvalRun` model to persist scores over time.
- **Accept:** command runs against pgvector RAG with both OpenAI and a local model;
  emits per-metric aggregate scores and fails below thresholds (CI-ready). Use it
  to confirm Phase 3/4 didn't degrade RAG/answer quality.

### Phase 6 — Cleanup (follow-up, after stable default)
- Remove `crewai`, `crewai-tools`, `CrewAIEngine`, `crewai_adapter.py`,
  `CrewAIEventBridge`, `_build_crewai_llm`. Update README/ARCHITECTURE.

---

## 6. Risks & mitigations
| Risk | Mitigation |
|------|-----------|
| `deepagents` API churn (pre-1.0) | Pin exact version; isolate behind `DeepAgentsEngine`; verify `system_prompt` vs `instructions` and the `files`/state channel shape on the pinned version. |
| Losing deterministic order / parallel batch | Don't use the native orchestrator — drive with an explicit LangGraph DAG (§4.2). |
| Observability fidelity (raw tool output, timeline) | Reuse the single tool-adapter chokepoint verbatim; map node enter/exit + structured output to existing sinks. |
| Token/cost accounting differs | Sum `usage_metadata` from streamed AI messages; keep `estimate_cost_usd`. |
| Structured output flaky on local models | Keep schemas lenient; add retry/repair; allow degraded text fallback. |
| Ragas non-determinism / local-model flakiness | `temperature=0`, `RunConfig(timeout↑, max_retries↑)`, `raise_exceptions=False`, prefer reference-based + non-LLM metrics in CI. |

## 7. Dependencies
- **Add:** `deepagents==<pin>`, `langgraph` (pin), `ragas>=0.4,<0.5`, `rapidfuzz`.
- **Reuse:** `langchain-openai/-anthropic/-google-genai/-ollama`, `langchain-core`,
  `langchain-text-splitters`, `langchain-huggingface`, `pgvector`, `pydantic`.
- **Remove (Phase 6):** `crewai`, `crewai-tools`.

## 8. Rollback
Per-phase: `HUNT_ENGINE=crewai` restores CrewAI instantly (Phases 0–4). The branch
is not merged until Phase 4 parity holds; Ragas (Phase 5) is additive and isolated.
