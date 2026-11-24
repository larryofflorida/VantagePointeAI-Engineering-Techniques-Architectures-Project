# Deployment, environment variables and cold-start behavior

*Last verified locally; numbers from `python scripts/measure_cold_start.py` (results in `evaluation/cold_start_results.json`).*

## 1. Is deployment fully functional? No.

| Piece | Status | What is verified | What is not |
|---|---|---|---|
| **Static assistant page → GitHub Pages** | Workflow written (`.github/workflows/ci.yml`, `deploy` job) | Every step before deployment was executed locally in a clean git repo (build, stale-file check, import check, MCP smoke test, 51 tests); `make site` produces the bundle; YAML parses | The `deploy` job has **never run on GitHub**: Pages enablement, permissions and the post-deploy URL check are untested |
| **MCP server (stdio)** | Works locally | Starts, answers `initialize`, `tools/list`, `tools/call`; refuses to start without a valid identity; runs from any working directory; runs with **no Node.js** installed | No container image, process supervisor, health endpoint or HTTP transport; **no hosted deployment exists** |
| **Orchestrator, LLM calls, gateway/SSO, HRIS read API** | Designed only (`design-and-evaluation.md` §6, §8) | – | Not built. The prototype page gets answers through the host's `sample` capability, which exists only where the page is run inside Claude |
| **Web page on GitHub Pages** | Retrieval-only | Page serves, script parses, retrieval runs in Node | No generated answers there (no model behind it); the synthetic HRIS data is visible in the page source |

So the repository can be built, tested and run locally, and the static page is ready to publish, but there is no production deployment of the backend.

## 2. Environment variables

The project reads **one** runtime environment variable.

| Variable | Used by | Required | Default | Description |
|---|---|---|---|---|
| `HR_EMPLOYEE_ID` | `evaluation/mcp_server.py` | **Yes** | none | Employee the server session acts as (e.g. `EMP-1011`). Every `get_my_*`, calculator and ticket tool is bound to it. The server **exits with code 2** if it is missing or not an ID in the HRIS data. A stand-in for the SSO subject a gateway would inject in production. |
| `PY` | `Makefile` | No | `python` | Python executable used by `make` targets (e.g. `make PY=python3 test`). Build-time only. |

Not environment variables, but things a deployment needs:

| Item | Detail |
|---|---|
| Python | Server needs Python 3 and the **standard library only** (no third-party runtime packages). Verified on 3.12; other versions not tested. |
| Node.js | **Build time only** (`make build` extracts retrieval parameters; tests run the page's JS). The server no longer needs it; this was a hidden dependency that I found and removed while preparing this document (see §4). |
| `pdfplumber` | Needed only for PDF → markdown (`make convert`), not at runtime. |
| Files read at startup | `chunks.json`, `hris_data/vantagepoint_hris_master_bundle.json`, `evaluation/retrieval_params.json`. Paths are resolved from the code's location, not the working directory (verified by running from `/`). Deploy the repository layout intact. |
| GitHub Pages (CI) | Repository setting **Settings → Pages → Source: GitHub Actions**; the workflow requests `pages: write` and `id-token: write` for the deploy job only. No secrets are used. |

**Proposed, not implemented** (a production design would need these; none exist in the code): an LLM API key held server-side, an HRIS read-API URL and credentials, an OIDC issuer/audience for the gateway, and log/trace settings. Do not assume they are read anywhere today.

### Run the MCP server

```bash
HR_EMPLOYEE_ID=EMP-1011 python evaluation/mcp_server.py     # newline-delimited JSON-RPC on stdin/stdout
python scripts/mcp_smoke.py                                  # discover tools and call two of them
```

## 3. Cold-start behavior

Measured in the build sandbox: Python 3.12.3, 15 runs each, OS file cache warm, no container image pull. Treat as relative magnitudes; a serverless or container platform will add its own start-up time, which I did not measure.

| What | Median | p95 | Notes |
|---|---|---|---|
| MCP server: process spawn → `initialize` response | **20.2 ms** | 31.7 ms | Python start, load `chunks.json` and HRIS data, build the in-memory BM25 index. Before removing the Node dependency: 49.4 ms median, 65.1 ms p95 |
| MCP server: first `tools/call` after initialize | 0.2 ms | 0.4 ms | `search_policy` |
| MCP server: later `tools/call` | 0.1 ms | 0.2 ms | Everything is in memory; no further warm-up |
| MCP server: peak memory | 12.4 MB | – | Largest child process measured |
| Static page: retrieval index build (Node) | 12.1 ms | – | Happens once on page load; a browser's timing was not measured |
| Static page: first / second search | 0.27 / 0.04 ms | – | |
| Static page: size | 116.2 KB | – | 33.6 KB gzip-compressed (computed, not observed from a live host) |

**What this means for each deployment mode**

* **stdio MCP server (today).** Every new session is a new process, so every session pays the ~20.2 ms start once and nothing afterwards. There is no network, database or model call on the start-up path, so there is no external dependency that can slow a cold start.
* **Static page on GitHub Pages.** No server cold start at all; the cost is the one-time download and in-browser index build. Not yet observed on a real Pages URL.
* **Inside Claude (`sample` capability).** The first use shows a consent prompt; model latency is outside this project's control and was **not measured**.
* **Future HTTP service (not built).** Load chunks, HRIS access and the index at process start (they take tens of milliseconds here), expose a readiness check that returns only after load, and keep at least one instance warm if the platform scales to zero. Re-measure on the target platform before promising latency; the numbers above exclude container pull, runtime init and network.

## 4. Fix made while writing this document

`evaluation/hr_tools.py` used to shell out to Node.js **at import time** to read the stop-words and synonyms from the page template. The server therefore crashed with `FileNotFoundError: node` on any machine without Node, and start-up carried a Node process launch (about 49.4 ms). The parameters are now exported at build time to `evaluation/retrieval_params.json` (`scripts/export_retrieval_params.py`, run by `make build`), checked into git, verified by CI against the page template (`check-generated` and a test), and a test now starts the server with no Node on `PATH`.

## 5. What would make deployment "fully functional"

1. Run the CI workflow on GitHub and confirm the Pages deploy and post-deploy check (needs the Pages setting above).
2. Add an HTTP (Streamable HTTP) transport, a container image, health/readiness endpoints, and a documented set of production environment variables.
3. Build the orchestrator and gateway with SSO, and move HRIS data behind a read API (the page currently embeds all synthetic employees).
4. Re-measure cold start on the chosen platform and set an explicit latency budget.
