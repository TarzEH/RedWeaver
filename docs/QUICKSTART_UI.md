# Quickstart — run your first scan

A 5-minute walkthrough from a fresh checkout to reading a finished report. Assumes
Docker is installed and you have an LLM API key (OpenAI, Anthropic, or Google).

> New to the report screen? See **[Reading a report](READING_A_REPORT.md)**.
> Something not working? See **[Troubleshooting](TROUBLESHOOTING.md)**.

---

## 1. Bring the stack up

```bash
cp .env.example .env        # then open .env and add your LLM API key
docker compose up -d --build
```

This starts everything (no tools to install): `web` (Django API + WebSocket),
`worker` + `beat` (Celery), `postgres` (pgvector), `redis`, `knowledge` (RAG
service), and `frontend`.

Wait until `docker compose ps` shows `web`, `postgres`, `redis`, and `knowledge`
as **healthy**.

## 2. Log in

Open **http://localhost:5173**.

The default admin is seeded automatically on first boot:

| Email | Password |
|-------|----------|
| `admin@redweaver.local` | `admin` |

> These come from `DJANGO_SUPERUSER_*` in `docker-compose.yml` / `.env`. Change
> them for anything other than local use (see [SECURITY.md](../SECURITY.md)).

## 3. Add your LLM key in the UI (if you didn't via .env)

Go to **Settings** (gear icon) → paste your provider API key and pick a model.
Without a working key a run fails immediately with *"No LLM API key configured"*
or a provider `401`.

## 4. Start a hunt

1. Click **New Hunt** (top-right of the Dashboard).
2. Enter a target you are **authorized to test** — e.g. `https://scanme.nmap.org`
   or your own staging host. (RedWeaver blocks internal/metadata IPs by scope guard.)
3. *(Optional)* scope it with MITRE ATT&CK techniques to focus the agent crew.
4. Send. The agent stream starts live in the center panel.

## 5. Watch it work

- **Center** — the live agent chat/stream (recon → crawl → fuzz → scan → exploit → report).
- **Right panel** — two tabs: **Flow** (live agent graph) and **Findings** (top results as they land).
- The run also shows token usage and estimated cost as it progresses.

A typical run takes a few minutes and ends with an inline report block in the stream.

## 6. Read the results

Once the run is **completed**, you have:

| View | Route | What it's for |
|------|-------|---------------|
| **Report** | `/hunt/<runId>/report` | The polished, shareable assessment (charts, ATT&CK, OWASP, remediation, full write-up) |
| **Findings** | `/hunt/<runId>/findings` | Triage table — filter by severity, search, expand each finding |
| **Compare** | `/hunt/<runId>/compare` | Diff this run against a previous one (new/fixed findings) |
| **Behind the scenes** | `/debug/<runId>` | Raw tool output, agent steps, screenshots, event replay, Attack playbook |

Export from the report block: Markdown, HTML, JSON, CSV, **SARIF**, or PDF.

---

## What "good" looks like

- Findings should map to **real tool output** — open the *Behind the scenes* view
  to see the `nmap`/scanner result behind a finding.
- A bare open web port (80/443) is ranked **informational**, not Low — that's
  expected, not a vulnerability.
- Severity, CVSS, and CVE attribution should be sensible. If a finding looks
  hallucinated (e.g. a desktop-OS CVE on a static web page), treat it skeptically
  and check its evidence.
