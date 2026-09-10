# LabelLens Strategy Memo

- Before the recommendation, here is what external verification changed (everything else below
- comes from your document): • Your strongest rival is confirmed real and current. The unnamed Python SIH26034 repo on GitHub's consumer-protection topic was updated Sep 3, 2026 and already ships multilingual OCR (English/Hindi/Gujarati), placement and numeral-height checks, clause-cited reports, PDF/DOCX export, and an enforcement dashboard. This means your "clause-cited explainable report + trilingual OCR" is parity, not differentiation. devdrishti-compliance-scanner
- (Kunal-Ch21) is also confirmed live. • LabelBlind FoLSol is further ahead than your doc suggests. It already validates labels against 70+ FSSAI and Metrology parameters — explicitly including font-height validation, clause-level regulatory references, and audit trails — and claims 92% accuracy. This kills both "font-height checking" and "cryptographic evidence trail" as claimed novelties in the commercial space
- (though not among SIH teams). • The real gap is enforcement, and the government itself confirms it. eMaap centralizes licensing, verification, and registration — but as of the Dec 2024 PIB release, "enforcement activities and compounding of offences are not online." eMaap is a business-facing compliance
- portal; nobody owns the enforcement-side evidence and case workflow. • PARAKH (Nik-404, HuggingFace) could not be verified in public search. Treat it as unconfirmed and do not reference it in your pitch. • PS26034 is already a forming field — 11+ ideas submitted as of Sept 9, 2026, ranking 12th of 185 active statements. Expect most submissions to be "OCR + rule check + dashboard"

clones. Given all this, brutally: the scan-and-check pipeline is a commodity. The product must be the

enforcement case-file, not the scanner.

## 1. FINAL IDEA

Build LabelLens as an evidence-grade field-inspection and enforcement-intelligence system for Legal Metrology officials — not a label scanner. Every team (including your direct public rival) is building the same thing: photo → OCR → rule check → clause-cited report. That gets you to par. The ministry's actual unsolved problem — confirmed by their own eMaap statements — is that enforcement and prosecution are offline, manual, and inconsistent, and your own research identifies the precise pains: no rule version control, no evidence provenance, no risk prioritization, and 3.5 lakh verifications a year that no officer can triage equally. So the product has three layers, in priority order: Prosecution-ready evidence pipeline. Every scan is captured with GPS/EXIF, hashed (SHA-256), appended to an immutable, hash-chained audit log, and automatically compiled into a Section 65B Indian Evidence Act certificate + evidence docket PDF (original photo, extracted declarations, rule version applied, bounding-box evidence of where each declaration was found or missing). The output of LabelLens is not a "report" — it is a case file that can survive a compounding hearing or court challenge. Brand-side tools (LabelBlind, Artwork Flow,

ManageArtworks) exist to help companies avoid violations; eMaap exists to license businesses;

nobody builds the state's side of the courtroom. Versioned, explainable rule engine. LMPC Rules 2011 encoded clause-by-clause as structured, versioned data — every verdict stores which rule version was applied at inspection time, so a case filed today can be re-examined against the rules as they stood on that date. This directly answers the "no version control / training lag / inconsistent application" pain in your research, which no competitor or public PS26034 repo addresses. Risk-ranked enforcement worklist. Scans aggregate into seller/manufacturer-level pattern intelligence: repeat offenders surface first, violations are severity-weighted, and an officer gets a prioritized queue instead of a flat list. One scan is a data point; the same importer violating Rule 7 across 40 SKUs is a case. The scanning/OCR/report layer still gets built — it is the entry point and the demo — but it is deliberately treated as infrastructure, not as the product. One coherent product: scan →

prove → prioritize.

## 2. FEATURES TO IMPLEMENT

### Core (table stakes — required for parity, not USPs)

- Label capture with perspective correction & quality gating — guided capture that rejects blurry/glared frames before analysis. Why: OCR failure is the #1 credibility killer in demos; a "retake this photo" gate makes your accuracy numbers honest.
- Layout-aware multilingual OCR + declaration extraction — extract MRP, net quantity, date, manufacturer/importer details, consumer care, country of origin, in English + at least Hindi. Why: the public rival already has trilingual OCR; you cannot compete without it.
- Clause-level placement & numeral-height rule engine — checks presence and placement/format/font-size against Rule 7-style mandates, with bounding-box evidence of where each item was found. Why: this is the standard architecture (Krishinetra) and your rival already does numeral-height — you must match it, but it earns zero differentiation points.
- Explainable GO / FIX / REVIEW verdict with clause citations — every violation shows the exact rule text and the evidence crop. Why: required for officer trust; already exists in the rival repo, so it is parity.
- Evidence-backed PDF report + product repository — searchable inspection history, photos attached, PDF/editable export, role-based access, dashboard. Why: explicitly required by the SIH problem statement and by every competing solution.

### Differentiating (the reason to pick LabelLens)

- Hash-chained evidence ledger + Section 65B docket generation (strongest USP) — each scan gets SHA-256 fingerprint + GPS/EXIF + timestamp, appended to an append-only hash-chained log; one click generates a prosecution docket: original image, hash proof, extraction results, applied rule version, and a draft 65B certificate. Why: converts the tool from "advisory scanner" into "case-file generator." Feasible with standard crypto/PDF tooling; commercially unoccupied on the enforcement side. Honest caveat: the system drafts the 65B certificate — actual admissibility still depends on the officer's certification process. Do not claim "auto-generated court notices."
- Rule-version pinning ("inspection-time rules") — rules stored as versioned structured data; every verdict records the version applied; re-running an old scan against today's rules shows a diff ("Rule 7 amended 2025 — verdict may change"). Why: solves a documented, real problem (no version control, inconsistent application across inspectors) that is provably absent from all known competitors.
- Seller/manufacturer risk graph + prioritized worklist — entity resolution across scans (same manufacturer/importer/address/GST patterns), repeat-offender scoring, severity-weighted queue for officers. Why: your research explicitly notes officers can't review thousands of flags equally; a flat violation list is what everyone else ships. This is cheap to build (database + scoring) and very convincing in a demo.
- Offline-first field mode with Hindi UI — full scan→verdict→docket workflow works without connectivity; syncs later. Why: inspections happen in markets, mandis, and small-town shops with poor connectivity; the jury-facing guidance for this PS explicitly values "works offline, in the local language." Cheap to build (PWA/service worker), high narrative value.

### Supporting (credibility and completeness)

- Cross-source seller verification (lightweight) — flag mismatches between what's printed on the pack (license no., FSSAI no., address) and what the scan extracted, marking fields as "verified on label" vs "illegible." Why: addresses your "cross-source verification" idea but keeps it label-internal — no brittle scraping dependency.
- Manual review / override workflow with full audit trail — officer corrections are logged with reason; model accuracy feedback loop. Why: honest about OCR limits (cite the packaging-OCR benchmark from your research), and the audit trail reinforces the evidence story.
- Monthly automated compliance report generation — you already have this; keep it, it is cheap and ministry-shaped.

### Deliberately NOT built (from your idea list)

- Live e-commerce price cross-check (Amazon/Blinkit scraping) — see Section 5.
- AR/LiDAR millimeter font-height engine — see Section 5.
- Multi-layer sticker tamper detection — CV-unreliable in a demo, easily attacked by judges with one curved glossy pack; cut.
- Automated unit-sale-price math verifier — fold in only as one rule-engine check (MRP ÷ net qty sanity check) if time permits; not a headline.
- Contrast/color-blind readability auditor — fold into the placement rule engine as a low-priority flag; not a standalone feature.

## 3. TECH STACK

Practical, student-feasible, demo-able:

| Layer | Technology | Purpose |
| --- | --- | --- |
| Mobile/PWA front end | React + Vite PWA (or Flutter if your team prefers) | Guided capture, offline queue, Hindi UI, field officer UX |
| OCR/Vision | PaddleOCR (strong Indic-script support) + OpenCV | Multilingual text extraction, perspective correction, bounding boxes |
| Extraction/verification | FastAPI + Python; regex/NER layer first, LLM (Gemini/GPT-class API) as fallback explainer only | Deterministic declaration extraction with an LLM for messy fields — keeps you honest about "regulation-mapped logic isn't prompt-dependent" |
| Rule engine | YAML/JSON-encoded versioned rule packs + Python evaluator | Clause-by-clause LMPC rules, version pinning, placement/font-size checks |
| Evidence layer | SHA-256 hashing, hash-chained SQLite/Postgres append-only table, PyFPDF/ReportLab | Tamper-evident audit log + 65B docket PDF |
| Backend/DB | FastAPI + PostgreSQL + Redis | Scans, entities, risk scoring, worklist |
| Dashboard | React + a charting lib (Recharts) | Enforcement dashboard, risk-ranked queue |
| Infra | Docker + free-tier cloud deploy (Render/Railway) + GitHub Actions | One-command demo deployment |

Total: a 4–6 person team can credibly build this; the riskiest piece (OCR accuracy) is mitigated by the capture-quality gate rather than by exotic models.

## 4. USPs

### Against existing Indian products (LabelBlind FoLSol, Artwork Flow, ManageArtworks, Complinity, eMaap)

- Enforcement-side vs. brand-side. Every funded/commercial Indian tool helps manufacturers make compliant labels; eMaap helps businesses get licensed. LabelLens is the only one built for the officer who must prove a violation. Strongly supported — the commercial tools' own positioning confirms this, and PIB confirms enforcement is not yet online. This is your single best USP.
- Evidence admissibility (65B docket + hash chain). Commercial tools keep audit trails for workflow management; none package output as legal evidence for prosecution. Potential differentiation — FoLSol does advertise audit trails, so you must frame yours as evidentiary, not operational.
- Rule-version pinning. Not offered anywhere we could verify, and it is a documented government pain. Strongly supported (by your research) — phrase as solving "which rules applied on the inspection date," a question that genuinely arises in contested cases.

### Against previous SIH teams (MetaMark, Krishinetra, NiyamDrishti, INSPECTO)

- Courtroom-grade output. MetaMark added hardware verification, Krishinetra added e-commerce scraping, NiyamDrishti added monitoring — all upstream of the actual bottleneck, which is converting a finding into a defensible case. Potential differentiation — based on public information available; you cannot prove a negative, so present it as "no publicly documented SIH solution addresses evidence admissibility or rule-version traceability."
- Novelty of focus, not of technology. You explicitly do not claim OCR, dashboards, or AI compliance checking as novel (correct — your rival repo already has them).

### Against likely PS26034 submissions

- The known public rival already covers trilingual OCR + numeral-height + clause-cited reports + dashboard. If you ship only that, you lose to parity at best. Your differentiation is layers 1 and 3 of the final idea: the evidence ledger and the risk-ranked worklist. Strongly supported by the verified repo description.
- Against "a weekend Roboflow rebuild" skepticism: the hash-chained evidence pipeline and versioned rule engine are not weekend features, and they directly answer the jury's two hardest questions — "who faces this problem?" (the inspecting officer, by name and workflow) and "why hasn't it been solved?" (enforcement is offline and evidence doesn't survive challenge).

### Dependency flags

- The 65B docket USP is dependent on successful implementation — a half-working "tamper-proof" claim will hurt you more than help; demo it live (show hash mismatch on edited photo) or don't claim it.
- The risk-worklist USP is strongly supported by your research but must be seeded with realistic demo data to look credible.

## 5. WHAT TO REMOVE

- Live e-commerce price-mismatch cross-checking (Amazon/Blinkit scraping). Three reasons: (a) it is the most crowded space — MetaMark (national winner), Krishinetra, and NiyamDrishti all built it; (b) it is brittle and ToS-risky, and judges know scrapers break mid-demo; (c) it drags you into competing on MetaMark's home turf, which your own benchmark analysis says to avoid. A static comparison against a photo of a listing (not live scraping) is an acceptable demo substitute if you insist on keeping a trace of this idea.
- AR/LiDAR millimeter font-height engine. Commercially already done (FoLSol advertises font-height validation against Legal Metrology rules), hardware-dependent (most judges' phones lack reliable depth sensing), and a failed live measurement will sink your credibility. Do numeral-height checks in relative pixels like your rival does — parity is enough here.
- Multi-layer sticker/tamper detector. Genuinely novel, but the CV is unreliable on curved, glossy, low-light retail packs — exactly the demo conditions — and "tamper probability score" invites unanswerable judge questions. Kill it; the tamper-evidence story is better told through your hash chain (evidence of the record, not of the sticker).
- Hardware-based physical verification. National winner's territory; your doc already says don't compete here.
- Contrast/color-blind readability auditor as a standalone feature. Interesting, cheap to compute (WCAG formula), but it answers a question the ministry isn't asking and smells like feature-stuffing. Fold it into the rule engine as one low-priority flag or drop entirely.
- "Auto-generated prosecution notice" framing. A student system cannot issue legal process; claiming it invites a fatal credibility question. Reframe as evidence docket + 65B certificate draft — same technical work, defensible claim.
- Speculating about SafeSecure / RULEBREAKERS. Your doc is right: no reliable public information exists. Never mention them.

## 6. FINAL POSITIONING

One-line pitch: LabelLens is the enforcement case-file for Legal Metrology — it doesn't just find missing MRPs, it proves them in a way that survives the courtroom.

Short project description: LabelLens is a mobile-first, offline-capable field-inspection system for Legal Metrology enforcement officials. An officer photographs a packaged commodity; LabelLens corrects and reads the label in English or Hindi, checks every mandatory declaration against a version-locked, clause-by-clause encoding of the Legal Metrology (Packaged Commodities) Rules, 2011 — with placement and font-size checks and bounding-box evidence — and issues an explainable GO / FIX / REVIEW verdict. Every scan is fingerprinted (SHA-256), geotagged, and written to an immutable audit log, producing a Section 65B-ready evidence docket in one click. Across scans, LabelLens builds a seller-level risk graph so inspectors raid repeat offenders first, and every verdict is permanently pinned to the rule version in force on the inspection date — so no case collapses because "the rules changed." Where existing tools help brands avoid violations and government portals license businesses, LabelLens is built for the officer who has to prove one.
