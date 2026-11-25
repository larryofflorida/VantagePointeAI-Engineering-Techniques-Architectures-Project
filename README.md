# VantagePoint HR Assistant — RAG corpus and prototype

A small, self-contained retrieval-augmented HR assistant built on a **synthetic** company, VantagePoint Technologies Inc.

It has three parts:

1. **A document pipeline** that converts ten policy PDFs into clean markdown and splits them into 73 section-level chunks with metadata.
2. **A mock HRIS dataset** (13 employees, PTO balances, benefits elections, offices, support tickets) used to personalize answers.
3. **A single-file web assistant** that retrieves relevant policy passages, adds the signed-in employee's record, and generates a cited answer.

> All people, numbers and policies are fictional. The dataset is meant for policy Q&A and RAG testing, not for real HR decisions.

---

## How it works

```
source_pdfs/*.pdf ──► scripts/convert.py ──► markdown/*.md ──► scripts/chunk.py ──► chunks.json(l)
                                                                                         │
hris_data/*_bundle.json ─────────────────────────────────────────────────────────────────┤
assistant/template.html ───────────────► scripts/build_assistant.py ◄────────────────────┘
                                                      │
                                                      ▼
                                  assistant/vantagepoint_hr_assistant.html  (single file)

In the browser:  question ─► BM25 search over chunks ─► top 6 passages
                                   + selected employee's HRIS record
                                   ─► Vantage (answer with [POL-XXX §n] citations)
                                   └► fallback: show the best passages 
```

Design points:

- **Why the converter is custom.** The PDFs' text layers run past the right page edge, so ordinary extraction (`pdftotext`, `pdfplumber.extract_text()`) clips table cells, for example "…\$1,000 W". `convert.py` reads characters directly, rebuilds table cells from the table geometry, and recovers the full text. Two cells where adjacent columns ran together are fixed by hand (see `FIXUPS` in `scripts/convert.py`).
- **Chunking.** One chunk per `##`/`###` section, split further on paragraph boundaries above about 1,400 characters. Each chunk carries `policy_id`, `version`, `effective`, `section`, `heading` and a `breadcrumb` such as `POL-HR-002 … > 2. Vacation & Personal PTO Accrual Tiers > 2.1 …`. Tables stay with their section.
- **Retrieval.** BM25 with light stemming, a small synonym map (for example `vacation→pto`, `wfh→remote`) and a double weight on the heading path. It runs entirely in the browser, with no server or vector database.
- **Personalization.** The model sees only the signed-in employee's record: employment details, manager, office, PTO and leave balances, benefits elections and their own tickets.
- **Citations.** The model is told to cite as `[POL-HR-002 §2.1]`. The UI turns those into clickable chips that open the source passage.
- **Conflict awareness.** The prompt lists known contradictions in the policy set (see below), so the assistant should surface them instead of picking a side silently.

---

## Repository layout

```
.
├── README.md
├── requirements.txt              # pdfplumber
├── source_pdfs/                  # the 10 policy PDFs (input)
├── scripts/
│   ├── convert.py                # PDF → markdown (rebuilds clipped tables)
│   ├── chunk.py                  # markdown → chunks.json / chunks.jsonl
│   └── build_assistant.py        # inline data into the HTML template
├── markdown/                     # generated: one .md per policy
├── chunks.json  chunks.jsonl     # generated: 73 chunks + metadata
├── hris_data/                    # synthetic HRIS (CSV + JSON + master bundle)
└── assistant/
    ├── template.html             # UI + retrieval + prompt (edit this)
    └── vantagepoint_hr_assistant.html   # generated single-file app
```

---

## Setup

Requirements: **Python 3.9+**. Nothing else is needed to *run* the assistant, since it is a static HTML file. The `pdfplumber` dependency is only needed to re-run the PDF conversion.

```bash
git clone <your-repo-url> vantagepoint-hr-assistant   # or unzip the archive
cd vantagepoint-hr-assistant

python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Rebuild everything from the PDFs

```bash
python scripts/convert.py            # source_pdfs/ → markdown/
python scripts/chunk.py              # markdown/ → chunks.json, chunks.jsonl
python scripts/build_assistant.py    # → assistant/vantagepoint_hr_assistant.html
```

Expected output: `73 chunks written`, then a ~116 KB HTML file. Run these again whenever you change a PDF, the HRIS data, or `assistant/template.html`.

To use a different policy set, drop your PDFs into `source_pdfs/` and rerun. Heading detection expects a title at about 20 pt, section headings at about 14 pt and subsections at about 11.5 pt bold, and a `Document ID: … | Version: … | Effective Date: …` line, as in the provided PDFs. `convert.py` will need adjusting for other layouts.

---

## Run locally

### Option 1: open the file

Double-click `assistant/vantagepoint_hr_assistant.html`, or:

```bash
open assistant/vantagepoint_hr_assistant.html        # macOS
xdg-open assistant/vantagepoint_hr_assistant.html    # Linux
```

### Option 2: tiny static server

```bash
cd assistant
python -m http.server 8000
# visit http://localhost:8000/vantagepoint_hr_assistant.html
```

### What works locally

Outside Vantage, the page runs in **retrieval-only mode**. Pick an employee, ask a question, and you get the top-matching policy passages. The Policy library tab also works fully. The footer line on the Assistant tab shows which mode is active.

Generated, cited answers need an LLM behind the page. See Deployment below. For quick local retrieval checks, the passages and the "Retrieved passages" list under each answer show whether the right sections are being found.

---

## Deployment

#

1. Build the file (`python scripts/build_assistant.py`).
2. Publish `assistant/vantagepoint_hr_assistant.html` as an artifact, declaring the `sample` capability (`capabilities: {"sample": {}}`). The page calls `vantage.use("sample")` .
3. The artifact is private to you until you share it.

Limits: answers depend on the viewer's access and, and the HRIS snapshot ships inside the page, so only share the artifact with people who may see that data. That is fine for synthetic data and not for real data.

### B. Any static host (retrieval-only)

Upload `assistant/vantagepoint_hr_assistant.html` to GitHub Pages, S3 + CloudFront, Netlify, Cloudflare Pages or an internal web server. It works as a policy search tool with an employee-context card.
### C. Production: your own backend and LLM

Do not ship real HRIS data to the browser, and do not call a model from client code with a secret key. For real use, move retrieval and prompting behind an API:

```
Browser  ──POST /api/ask {question, history}──►  Your API
                                                  1. authenticate (SSO) → employee_id from the session, never from the request
                                                  2. fetch ONLY that employee's record from your HRIS
                                                  3. retrieve passages (same chunks; BM25 or embeddings)
                                                  4. call the Anthropic API with the prompt from assistant/template.html
                                                  5. return {answer, citations}
```

Changes to make in `assistant/template.html`:

- Delete the embedded `HRIS` data and the employee picker (identity comes from your auth layer).
- Replace the `sample(...)` call in `ask()` with a `fetch('/api/ask', …)` that returns the answer text, and keep `renderAnswer()` for the citation chips.
- Move the `RULES` prompt and the retrieval code (`search`, `ctx`) server-side. `chunks.jsonl` is the corpus to load there.
- If you add embeddings (recommended once the corpus grows), embed `chunks.jsonl` records with `breadcrumb + text` and keep the BM25 score as a hybrid signal.

Operational checklist: store the API key in a secrets manager; log questions and cited sections for audit; set per-user rate limits; keep the corpus versioned (each chunk has `version` and `effective`); and add a "contact People Operations" path for questions the assistant cannot answer.

---

## Customizing

| To change… | Edit |
|---|---|
| Chunk size or splitting | `MAXLEN` in `scripts/chunk.py` |
| Synonyms / stop words / BM25 weights | `SYN`, `STOP`, and `search()` in `assistant/template.html` |
| Assistant rules, tone, known-conflict list | `RULES` in `assistant/template.html` |
| Number of passages sent to the model | `search(…, 6)` in `ask()` |
| Example questions | `profile()` in `assistant/template.html` |
| Employee data | files in `hris_data/` (rebuild with `build_assistant.py`; use the master bundle) |

---

## Known inconsistencies in the source policies

These are preserved as written, since the assistant is meant to cope with them:

- **Payroll cutoff:** POL-HR-001 §3 gives cutoffs on the 10th and 25th (semi-monthly); POL-COMP-001 §1 describes biweekly Friday pay.
- **New York hub:** POL-HR-001 lists New York as a hub; POL-HR-003 and the relocation and transit benefits do not.
- **Lost devices:** POL-IT-001 §3 allows 2 hours to report; POL-SEC-001 §5.3 requires 30 minutes.
- **Holiday count:** POL-HR-002 describes both "13 paid holidays" and "16 paid days" including the winter shutdown.
- **Gifts of exactly \$100:** POL-ETH-001 §3.2 accepts gifts "under \$100" and declines those "exceeding \$100".
- **TSA PreCheck:** POL-FIN-001 says a wellness perk covers it, but POL-BEN-001 does not list it.
- **IRS figures:** the \$0.70 mileage rate and \$325 commuter limit are labeled 2026 but match the 2025 figures; verify if real-world accuracy matters.

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Footer says "retrieval only" |  see Deployment A or C for generated answers |
| Answer cites the wrong section | Check the "Retrieved passages" list; add a synonym or raise the passage count |
| Table cells look clipped after conversion | The source PDF clips them; `convert.py` recovers them. If you add new PDFs, check tables in `markdown/` and add a `FIXUPS` entry if columns merged |
| `ModuleNotFoundError: pdfplumber` | Activate the venv and run `pip install -r requirements.txt` |
| `assert … in s` error from `convert.py` | A `FIXUPS` string no longer matches the PDF; update or remove that entry |
| Page is blank | Rebuild with `python scripts/build_assistant.py`; make sure you open the generated file, not `template.html` |

---

## Notes and limitations

- Retrieval is keyword-based. Questions phrased with unusual vocabulary may miss the right passage until you add synonyms or embeddings.
- The model's answers are only as good as the policy text; where the policies conflict, the assistant is instructed to say so rather than choose.
- The assistant gives policy information, not legal or HR determinations. Anything consequential should go to People Operations.
- The HRIS snapshot is dated **2026-11-18** and is static.

## License and data

All content is synthetic, created for testing. Replace it with your own policies and data before any real use, and apply your organization's privacy and security review to the production architecture above.
