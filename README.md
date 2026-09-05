# NVIDIA Supply Chain and Partnership Research Service

Offline, reproducible research API and CLI for **NVIDIA Corporation (NASDAQ: NVDA)**.

This is **not investment advice**. It is a structured evidence pack for the ARTi Supply Chain and Partnership Research Challenge. Facts, reasonable inferences, and unknowns are labeled on every row.

## 1. Research target

| Field | Value |
| --- | --- |
| Legal entity | NVIDIA Corporation |
| Ticker | NASDAQ: NVDA |
| CIK | 0001045810 |
| Cut-off date | **31 March 2024** |
| Snapshot file | `data/snapshot_nvda.json` (version 1.2.0) |
| Access window | Evidence `access_time` values are 28 March 2024, on or before the cut-off |

**Scope.** Listed companies connected to NVIDIA in five relation types: `supplier`, `customer`, `partner`, `investor_or_investee`, `peer`. The snapshot includes every listed foundry, memory vendor, and contract manufacturer **named** in the FY2024 Form 10-K Manufacturing paragraph, plus newsroom customers, a Lenovo partnership, 13F holdings, and named GPU/SoC peers. Each row has a stable `relation_id`, direction, fact/inference/unknown status, locator, confidence, and relevance.

**Boundaries.** Only legally accessible public documents. No robots.txt bypass, no login, no paywall, no CAPTCHA solving, no rate-limit evasion, no API keys, and no restricted raw dumps. Undisclosed Tier-2 suppliers are out of scope. Unitree is not the research target.

**Fact labels.**

- `Confirmed Fact`: the cited locator names the entity and the mapped relation.
- `Reasonable Inference`: the locator supports a nearby claim (example: CoWoS packaging inferred for TSMC) but does not name the vendor in that sentence.
- `Unknown`: the locator names the entity but the net commercial direction is unresolved (example: Tesla as in-house SoC designer versus possible customer).

## 2. Why NVIDIA, not Unitree

NVIDIA is a U.S. registrant with Form 10-K and Form 13F-HR on SEC EDGAR. Those filings name foundries, memory vendors, contract manufacturers, competitors, and equity holdings with locators a reviewer can open without credentials. Unitree is private and would force weaker news-only chains.

## 3. Data pipeline (reproducible without re-fetch)

Reviewers do **not** need live SEC or newsroom access to run the service. Runtime reads the committed snapshot only.

1. **Select sources** that are public: NVIDIA FY2024 Form 10-K (filed 21 February 2024), NVIDIA 13F-HR for 31 December 2023 (filed 14 February 2024, accession `0001045810-24-000021`), NVIDIA Newsroom, Lenovo StoryHub.
2. **Manual extraction** of entity names, tickers, relation type, and a paragraph-level locator. No HTML scraper is shipped.
3. **Cleaning** in `data/snapshot_nvda.json`: English locators, ISO dates, `investor_or_investee` (not `investee`), access times on or before cut-off.
4. **Scoring** with the frozen formula in `src/scoring.py`. Pydantic rejects a row if `confidence_score` is not the sum of `score_components`.
5. **Serve** the snapshot through FastAPI and the CLI.

To refresh after a new cut-off: edit the JSON, keep URLs public, set `cut_off_date` and `access_time`, recompute component scores, run `pytest`. Do not add keys or scraped paywall text.

Schema: `data/schema.json`.

## 4. Confidence scoring

```
confidence_score =
    source_authority (0-40)
  + independence_directness (0-25)
  + timeliness vs cut-off (0-20)
  + quantifiable_info (0-15)
```

| Component | What raises the score | What lowers the score |
| --- | --- | --- |
| Source authority | SEC Form 10-K / 13F | Single-company newsroom |
| Independence / directness | Filing names the counterparty in a statutory section | First-party PR; inferred vendor from an adjacent sentence |
| Timeliness | Published in FY2024 / Q4 2023 filings | 2023-03 news versus 2024-03 cut-off |
| Quantifiable info | 13F share count | Named role with no dollars or units |

`relevance_score` is separate: SoundHound can be 99 confidence (the holding exists) and 35 relevance (not core GPU supply).

## 5. Environment

Copy `.env.example` if you need an override. **Do not put credentials in the environment.** This project has none.

| Variable | Required | Purpose |
| --- | --- | --- |
| `DATA_SNAPSHOT_PATH` | No | Alternate snapshot path. Default: `data/snapshot_nvda.json` |
| `UVICORN_HOST` / `UVICORN_PORT` | No | Documented only if you bind uvicorn yourself |

Python 3.10+.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On macOS/Linux use `source .venv/bin/activate`.

## 6. Start, query, test

API:

```bash
python -m uvicorn src.app:app --host 127.0.0.1 --port 8000
```

- `GET /health` and `GET /` (service index)
- `GET /v1/metadata`
- `GET /v1/companies/{symbol}/relations?rel_type=&fact_status=&min_score=&min_relevance=&published_on_or_after=&published_on_or_before=&page=&limit=`
- `GET /v1/companies/{symbol}/graph` (same filters except pagination)
- `GET /v1/companies/{symbol}/evidence?target_ticker=`

`symbol` must be `NVDA` (or `NASDAQ: NVDA`). Other issuers return `404` with `error_code=ENTITY_NOT_SUPPORTED`. Invalid enums return `422` with `error_code=VALIDATION_ERROR`. Inverted date bounds return `400` with `error_code=DATE_RANGE_INVALID`. Relations are sorted by relevance, then confidence, then `relation_id`.

CLI:

```bash
python -m src --symbol NVDA --type supplier --min-score 90
python -m src --symbol NVDA --fact-status Unknown
python -m src --symbol NVDA --mode graph
python -m src --symbol NVDA --mode evidence --target-ticker "NYSE: TSM"
python -m src --symbol NVDA --type investee
python -m src.validate
```

`investee` is accepted as an alias of `investor_or_investee`.

Tests (happy path, pagination, time/relevance filters, 404, 422, CLI, snapshot invariants):

```bash
python -m pytest -q
```

Key path: `GET /v1/companies/NVDA/relations?page=1&limit=2`.  
Failure path: `GET /v1/companies/TSLA/relations` (Tesla is a *related* peer in the snapshot, not a supported research target).

## 7. Known blind spots and later data quality

- The Manufacturing paragraph is now fully mapped for listed names (TSMC, Samsung, Micron, SK hynix, Hon Hai, Wistron, Fabrinet). Unnamed sub-tier vendors remain out of scope.
- Newsroom customer rows are first-party; independence is capped on purpose.
- Microsoft (March 2023) is older than Amazon (November 2023); continuation through the cut-off is not re-attested by a 2024 filing in this snapshot.
- Dual roles (Microsoft/Amazon as GPU customers *and* internal-chip peers) are noted in `source_conflict_notes` rather than duplicated as two high-confidence types without evidence.
- Korean listings use KRX tickers; ADR tickers are noted in disambiguation where relevant.
- Future improvement: add a second independent source per newsroom row (customer 10-K / 8-K) and a filing-derived customer-concentration table if NVIDIA ever names buyers.

## 8. AI declaration

Cursor Grok 4.6 (Cursor AI coding agent) was used to scaffold FastAPI/CLI/tests, to compare the tree against the ARTi checklist, and to open public SEC/newsroom pages for locator checks.

**Manual verification I accept:** FY2024 10-K Manufacturing and Competition wording; 13F-HR accession `0001045810-24-000021` SoundHound share count `1730883`; newsroom dates for Microsoft (21 March 2023) and AWS (28 November 2023); Lenovo StoryHub (24 October 2023). No API keys, personal data, or client secrets were given to the agent.

I take personal responsibility for the research judgments (relation type, fact vs inference vs unknown, scores) and for the engineering behavior of this repository.
