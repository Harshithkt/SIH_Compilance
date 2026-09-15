# LabelLens

**The enforcement case-file for Legal Metrology.** It doesn't just find a missing MRP — it
produces a record that survives a challenge.

An officer photographs a packaged commodity. LabelLens gates the frame for quality, reads the
label in English or Hindi, checks every mandatory declaration against a **version-locked,
clause-by-clause encoding of the Legal Metrology (Packaged Commodities) Rules, 2011**, and
issues an explainable **GO / FIX / REVIEW** verdict. Every inspection is fingerprinted
(SHA-256), geotagged and committed to an **append-only hash-chained ledger**, and can be
exported as a **prosecution evidence docket** with a draft certificate under s.63(4) of the
Bharatiya Sakshya Adhiniyam, 2023 (formerly s.65B, Indian Evidence Act). Across inspections it
builds a **seller-level risk graph** so officers work the worst offenders first.

Existing tools help brands avoid violations, and government portals license businesses.
LabelLens is built for the officer who has to prove one.

---

## Quick start

Two terminals. Backend first.

```bash
# 1. Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env         # add your NEBIUS_API_KEY
python -m app.seed           # generates demo inspections (also resets the database)
uvicorn app.main:app --reload --port 8000
```

```bash
# 2. Frontend
cd frontend
npm install
npm run dev                  # http://localhost:5173 (proxies /api to :8000)
```

API docs: <http://localhost:8000/docs>

### With Docker

```bash
echo "NEBIUS_API_KEY=your-key" > .env
docker compose up --build          # app on http://localhost:8080
docker compose exec backend python -m app.seed
```

Evidence images, dockets and the ledger live in named volumes, so case files survive a
container rebuild. *(The compose setup has not yet been run end to end — no Docker daemon
was available on the machine it was written on.)*

### Configuration

All settings live in `backend/.env` (see `.env.example`). Only the API key is required.

| Variable | Default | Purpose |
| --- | --- | --- |
| `NEBIUS_API_KEY` | — | Nebius Token Factory key. Required for vision reading. |
| `LABELLENS_NEBIUS_BASE_URL` | `https://api.tokenfactory.nebius.com/v1` | OpenAI-compatible endpoint |
| `LABELLENS_NEBIUS_VISION_MODEL` | `openbmb/MiniCPM-V-4_5` | Label text recognition |
| `LABELLENS_NEBIUS_TEXT_MODEL` | `meta-llama/Llama-3.3-70B-Instruct` | Plain-language explanations |
| `LABELLENS_OCR_PROVIDER` | `auto` | `auto` \| `nebius` \| `tesseract` \| `manual` |
| `LABELLENS_ACTIVE_RULE_VERSION` | `2022-v2` | Rule pack applied to new inspections |

`GET /api/v1/system/models` lists the model IDs actually available on your account — use it
before pinning a different model, since the catalogue changes.

---

## The three layers

The scan pipeline is infrastructure. The product is what sits on top of it.

### 1. Prosecution-ready evidence

Every inspection is committed as one entry in an append-only ledger. Each entry's hash covers
the scan record **and** the hash of the entry before it, so altering any earlier record — or
the photograph it points at — breaks every hash after it.

```
entry #1  prev=0000…0000  ──►  entry #2  prev=<hash #1>  ──►  entry #3  prev=<hash #2>
```

`GET /api/v1/ledger/verify` recomputes the whole chain, including the on-disk SHA-256 of every
evidence image, and names the exact entry at which a record diverges.

`GET /api/v1/scans/{id}/docket` produces the case file: inspection particulars, the
photograph with its fingerprint, extracted declarations, the rule version applied, findings
with clause citations, **crops cut from the original photograph** at the recorded coordinates,
the integrity proof, and a draft s.63(4) BSA certificate.

The system *drafts* that certificate. Admissibility still depends on the officer signing it,
and the docket says so on its face. LabelLens does not issue legal process.

### 2. Versioned rules

Rules are YAML packs in `backend/app/rules/`, each with a version, an effective date and a
SHA-256. Every verdict records the version applied at inspection time, so a case filed today
can be re-examined against the rules as they stood on that date.

Two packs ship: `2011-v1` and `2022-v2` (amended Second Schedule type sizes, a new best-before
requirement for pre-packaged food, unit-sale-price elevated from advisory to a declaration
requirement). Open a pre-amendment inspection and compare versions to see the answer to the
question that actually arises in contested cases: *would today's rules give a different
verdict?*

### 3. Risk-ranked worklist

One scan is a data point; the same importer breaching the same clause across forty SKUs is a
case. Scans resolve to manufacturer/packer/importer entities and are scored by
severity weight × repeat contraventions × recency, so the queue is ordered by risk rather
than recency. Each entity has its own page showing every inspection against it and the
clauses it breaches most often, and `GET /api/v1/reports/monthly` rolls a period up into
the figures a controller's office is asked for — carrying the ledger's integrity status,
because a compliance number is only worth as much as the records behind it still verifying.

### Correcting a misread

Text recognition is not perfect, particularly on Devanagari. An officer can correct any
declaration from the inspection page; the correction requires a reason, is logged with the
officer's name, re-runs the rule engine against the *pinned* rule version, and is appended
to the ledger as a further entry. The original commit stays in the chain and remains
verifiable — history is added to, never rewritten.

---

## Honest boundaries

These are deliberate, and they are what keeps the claims defensible:

- **The verdict is never model-generated.** The vision model reads text; a deterministic
  regex/keyword layer maps it onto regulated declarations; the rule engine decides. The LLM is
  used only for optional plain-language explanations, which are labelled as advisory.
- **Unmeasurable is not the same as non-compliant.** When a declaration's position on the
  label cannot be established, the type-size check cannot run, and it is reported as *not
  assessable* — never as a contravention. A false accusation in an evidence docket is worse
  than a gap. Equally, coordinates are measured from the photograph, never invented: if the
  measured line count does not match the recognised line count, no box is recorded.
- **Type size is scale-invariant.** The check compares a declaration's measured line height
  as a fraction of the label, not in absolute pixels, so the verdict does not depend on how
  close the officer stood. It approximates the Second Schedule mandate; it is not a
  measurement in millimetres, and the docket says so.
- **Bad frames are rejected, not guessed at.** The capture gate checks resolution, focus,
  glare and contrast, and tells the officer what to fix.
- **Devanagari in PDFs.** ReportLab does not run OpenType shaping, so Hindi values can be
  mis-positioned in the docket text. This is why declarations also appear as image crops from
  the original photograph — the evidentially stronger form regardless.

### 4. Field Physical Verification (Rule 22 MPE) & Enforcement Signals

- **Physical Verification (Rule 22 / First Schedule)**: Field weight/volume measurements recorded by officers are evaluated directly against Legal Metrology (Packaged Commodities) Rules, Rule 22 Maximum Permissible Error (MPE) tables (mass and volume bands up to 50g: 9%, 50–100g: 4.5g, etc.). Results (`PASS`, `FAIL`, `REVIEW`, `NOT_ASSESSABLE`) are committed into the tamper-evident evidence chain.
- **E-Commerce Screenshot Uploads**: Supports `ECOMMERCE_LISTING` image source alongside `PHYSICAL_LABEL`, preserving source context and rendering visible non-legal inspection disclaimers.
- **Internal Price-Anomaly & History Signals**: Generates non-legal internal enforcement intelligence signals based on historical unit price distributions and prior entity adverse cases (`NO_SIGNAL`, `LOW_SIGNAL`, `REVIEW`, `INSUFFICIENT_HISTORY`). All signals are explicitly marked as informational and do not replace deterministic legal findings.
- **Anonymized Public Transparency Dashboard**: Exposes an unauthenticated public route (`/public-dashboard`) for aggregate compliance rates and district/category breakdowns with zero PII exposure.

### Roadmap vs. Current Scope

- **Implemented**: Deterministic rule engine, Nebius VLM + PaddleOCR + Tesseract pipeline, SHA-256 evidence chain, BSA s.63(4) dockets, Rule 22 MPE physical verification, internal price/contact/history signals, anonymized public dashboard.
- **Roadmap / Future Work**: Fully on-device native OCR (WebAssembly/TFLite edge execution), configurable per-field confidence thresholds for automated auto-approvals.

## Testing

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/ -q
```

The suite covers the extraction segmentation rules, the rule engine (including the
not-assessable path), and the tamper-evidence guarantees the docket depends on — editing a
committed record, and editing a stored evidence photograph.

### Demonstrating tamper-evidence

```bash
curl -s localhost:8000/api/v1/ledger/verify        # intact

python3 -c "
from PIL import Image
img = Image.open('backend/storage/images/seed_03.jpg')
img.paste((247,245,238), (40, 200, 600, 250))      # erase the MRP line
img.save('backend/storage/images/seed_03.jpg', quality=95)"

curl -s localhost:8000/api/v1/ledger/verify        # names the exact broken entry
cd backend && python -m app.seed                   # restore
```

## Layout

```
backend/
  app/
    rules/            versioned LMPC rule packs (YAML)
    services/
      quality.py      capture-quality gate
      ocr.py          Nebius vision / Tesseract / manual providers
      extraction.py   deterministic declaration extraction
      rule_engine.py  clause evaluation, verdicts, version diffing
      evidence_chain.py  hash-chained ledger + verification
      docket_pdf.py   evidence docket & draft certificate
      layout.py       text-line geometry measured from the photograph
      risk_scoring.py entity risk scoring
      compliance_report.py  periodic report for the controller's office
      pipeline.py     capture → gate → read → extract → evaluate → commit
    routers/          FastAPI endpoints
frontend/
  src/
    pages/            Inspect, Worklist, Entity, Inspections, Ledger, Report, Rule packs
    offlineQueue.ts   IndexedDB queue for inspections captured without signal
    i18n.tsx          English / Hindi UI
```
