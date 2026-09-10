# Vision model selection

Run on 2026-09-10 against the Nebius Token Factory catalogue available to this account
(23 models). Of the 22 non-embedding models, **7 accept image input**; the other 15 reject
it with `400 This model does not support image input`.

Each vision-capable model was given the same label-reading prompt LabelLens uses in
production, on two seeded labels with known ground truth: one Devanagari (8 declarations)
and one English (7 declarations).

- **fields** — declarations the deterministic extraction layer recovered from the model's
  output, which is what actually decides a verdict
- **text sim** — character similarity of the full read against ground truth
- **boxes** — how many lines came back with usable coordinates

## Devanagari label

| model | fields | text sim | lines | boxes | secs |
| --- | --- | --- | --- | --- | --- |
| **MiniMaxAI/MiniMax-M3** | **8/8** | **1.000** | 8/8 | 8 | **4.9** |
| moonshotai/Kimi-K2.6 | 8/8 | 1.000 | 8/8 | 8 | 15.8 |
| moonshotai/Kimi-K2.7-Code | 8/8 | 1.000 | 8/8 | 8 | 10.2 |
| moonshotai/Kimi-K3 | 8/8 | 1.000 | 8/8 | 8 | 26.7 |
| google/gemma-3-27b-it | 8/8 | 0.995 | 8/8 | 8 | 12.8 |
| zai-org/GLM-5.3-Flash | 8/8 | 0.971 | 8/8 | 8 | 16.7 |
| openbmb/MiniCPM-V-4_5 | 7/8 | 0.943 | 8/8 | 0 | 6.7 |

## English label

| model | fields | text sim | lines | boxes | secs |
| --- | --- | --- | --- | --- | --- |
| **MiniMaxAI/MiniMax-M3** | **7/7** | **1.000** | 7/7 | 7 | **3.8** |
| google/gemma-3-27b-it | 7/7 | 1.000 | 7/7 | 7 | 13.6 |
| moonshotai/Kimi-K2.7-Code | 7/7 | 1.000 | 7/7 | 7 | 4.0 |
| openbmb/MiniCPM-V-4_5 | 7/7 | 1.000 | 7/7 | 0 | 5.7 |
| zai-org/GLM-5.3-Flash | 7/7 | 1.000 | 7/7 | 7 | 10.1 |
| moonshotai/Kimi-K3 | 7/7 | 0.998 | 7/7 | 7 | 14.6 |
| moonshotai/Kimi-K2.6 | — | — | — | — | returned a null line |

## Decision

`MiniMaxAI/MiniMax-M3` is the default: exact on both scripts, roughly three times faster
than the next-best Devanagari reader, and it reads the two terms that defeated the previous
default (`उपभोक्ता सेवा`, `शुद्ध देसी घी`) correctly. `moonshotai/Kimi-K2.7-Code` and
`google/gemma-3-27b-it` are the fallbacks.

## Why the models' bounding boxes are discarded

Every model except MiniCPM-V returned coordinates for every line, which looks like
grounding. Compared against geometry measured from the same pixels, MiniMax-M3's boxes
give every line an identical height (0.040) at a perfectly uniform 0.07 spacing, and drift
progressively down the label:

| line | model y | measured y | error |
| --- | --- | --- | --- |
| 1 | 0.05 | 0.09 | 0.037 |
| 4 | 0.26 | 0.31 | 0.054 |
| 8 | 0.54 | 0.62 | 0.082 |

An error of 0.082 on a 640px image is ~52px — more than a full line height, so a crop
taken at those coordinates would show the wrong declaration. Uniform heights and even
spacing are the signature of an estimated layout, not a measured one.

The models are therefore used for text only. Position comes from
`app/services/layout.py`, which measures it by ink projection and is matched to the
recognised lines by reading order — and records nothing at all when the two disagree.
This matters because those coordinates are what the evidence docket crops and what the
type-size check measures: a plausible-looking guess is worse than an admitted gap.

## Reproducing

The benchmark probes the live catalogue, so re-run it when the model list changes:

```bash
cd backend && source .venv/bin/activate
python ../docs/bench_vision.py
```
