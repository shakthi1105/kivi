# The Words Kivi Keeps — Word-Level Phonetic Memory

> **At a glance:** A deterministic, user-correction-driven phonetic memory system for speech-to-text outputs. Built with **Python, FastAPI, SQLite and Metaphone**, with explicit confidence thresholds, context-aware corrections, and per-token decision traces.
>
> **Evaluation-first:** Includes **11 evaluation scenarios / 14 checks** and **7 core pytest unit tests plus evaluation-fixture contract checks**, covering ambiguity, false interventions, insufficient evidence, and regressions. See [evaluation details](#4-evaluation) and [reproduction steps](RUN.md).

[![Tests and evaluation](https://github.com/shakthi1105/kivi/actions/workflows/ci.yml/badge.svg)](https://github.com/shakthi1105/kivi/actions/workflows/ci.yml)

**Quick links:** [How to run](RUN.md) · [Evaluation methodology](eval/README.md) · [Evaluation cases](eval/cases.json) · [Tests](tests/) · [Evaluation report (previous run)](eval/report.md) · [CI runs](https://github.com/shakthi1105/kivi/actions/workflows/ci.yml)

---

A minimal, end-to-end implementation of Kivi's "phonetic memory": the system
that lets Kivi move a transcript from **ASR output** and **formatted output**
to a **memory-aware output** that reflects the specific names, brands, and
terms that belong to one person.

See `RUN.md` for exact commands. This document explains what was built and why.

---

## 1. Product decisions

**What it means for Kivi to "remember a word."** A memory entry is a claim of
the shape: *"when this phonetic pattern shows up (optionally, only right
after this other word), the user actually means this specific spelling."*
It is not a general dictionary of correct English — it only exists to correct
the small, personal vocabulary that generic ASR/LM training could never have
seen: names, brands, internal tools, nicknames.

**What counts as evidence.** The system only learns from *explicit
corrections* — the user editing a word Kivi produced. This is the strongest
possible signal (the user directly said "this is wrong, this is what I
meant") and it's the only one we use. We deliberately did **not** build
implicit learning (e.g. inferring a correction from context or repetition in
unedited text), because an implicit signal is much weaker and any mistake
there is unexplainable to the user later — "why did Kivi start calling my
friend by the wrong name?" needs a real answer.

**Evidence has to accumulate before it changes behaviour.**
A single correction could be a typo, a joke, a one-off. `MIN_OBSERVATIONS = 2`
means nothing is applied off one data point.

**Confidence is a competition between candidates, not an absolute score.**
For a given phonetic pattern (and context, if any), the system tracks *every*
distinct correction the user has ever asked for and the share of
observations each one has. If a phonetic bucket has 3 observations for one
spelling and 2 for another, that's a 60/40 split — not a confident answer.
`CONFIDENCE_THRESHOLD = 0.66` requires a clear majority, not just a plurality.

**Context can scope a correction.** The brief's own example
(`kiwi → Kivi`) is a homophone collision with an ordinary English word — the
fruit. Correcting every occurrence of "kiwi" anywhere would break unrelated
sentences. So an observation can optionally carry the word that preceded it
("sarvam ___"), and that correction only fires when the same word precedes
it again. Corrections registered without context are context-free (e.g. a
person's name — there's no ambient sense of "Aditya" the system should be
protecting).

**The system prefers doing nothing, and says why.** Every token gets a
labelled decision, not just "changed" or "unchanged":

| Decision | Meaning |
|---|---|
| `intervened` | Applied a learned correction |
| `already_correct` | Text already matches the learned form |
| `ambiguous` | Two+ candidates are too close to call — a coin flip, so it isn't made |
| `low_confidence` | Best candidate exists but hasn't earned a clear majority |
| `no_memory` | No entry exists (or none clears the observation minimum) |

This distinction matters in practice: "Kivi didn't fix this word" has
completely different causes and completely different fixes (wait for more
data vs. genuinely can't tell vs. never seen it), and a product/support team
debugging a complaint needs to know which one happened.

---

## 2. Architecture

```
observation (heard_word, corrected_word, context?)
        │
        ▼
  observations table   (append-only log — the ground truth of what happened)
        │  triggers a recompute of confidence for
        │  every entry sharing (phonetic_key, context)
        ▼
  memory_entries table (derived belief state: canonical_term, confidence,
                         observation_count — always a function of the log,
                         never hand-edited)
        │
        ▼
resolve(formatted_text) -- tokenizes, and for each word:
    1. looks up candidates by phonetic key of the token AND by exact
       canonical-term match (see "cases discovered" below for why both)
    2. splits candidates into context-matched vs. context-free
    3. checks ambiguity → already-correct → confidence threshold → apply
        │
        ▼
memory_aware_text + a full per-token reasoning trace
```

- **Storage:** SQLite (embedded, zero setup, easy to inspect with any SQLite
  browser, trivial to reset).
- **Phonetic key:** classic Metaphone (`jellyfish` library). ASR errors are
  phonetic confusions, not typos, so a phonetic bucket generalizes far better
  than string edit-distance for this specific failure mode.
- **No LLM in the resolve path.** The matching/decision logic is entirely
  deterministic. This was a deliberate choice: it makes the system's
  behaviour fully explainable (the trace *is* the reasoning, not a
  post-hoc explanation of an opaque call), it's free and sub-millisecond, and
  it needs no API key to run. The trade-off is discussed under Limitations.
- **API:** FastAPI, five endpoints (`POST /api/observations`,
  `GET /api/memory`, `GET /api/observations`, `POST /api/resolve`,
  `POST /api/reset`).
- **Demo UI:** one static HTML/JS page (`static/`) that exercises the full
  loop: teach → inspect memory → feed a transcript → see the result and the
  reasoning → reset.

---

## 3. Cases discovered beyond the brief's example

The brief gives exactly one example. Building and testing the system
surfaced several more, all covered in `eval/cases.json`:

1. **Single observation ≠ learning.** One correction must not change output
   (`single_observation_is_not_enough`).
2. **Crossing the threshold.** The *same* correction, reinforced by a second
   observation, starts applying (`crosses_threshold_after_second_observation`)
   — evidence accumulating in real time, not a static dictionary.
3. **Context protects the unrelated sense.** `kiwi → Kivi` (learned only
   after "sarvam") must not touch "I had a kiwi for breakfast"
   (`context_scoping_protects_unrelated_sense`) — this is the sharpest edge
   in the brief's own example, made explicit and tested.
4. **Conflicting corrections are ambiguous, not resolved by luck.** If a user
   has corrected the same phonetic word to two different spellings equally
   often, the system must not silently prefer one
   (`conflicting_corrections_are_ambiguous`).
5. **A majority isn't automatically a confident majority.** 60% support for
   one candidate over another is a real majority but below our 66%
   threshold, and is correctly withheld
   (`weak_majority_is_not_confident_enough`).
6. **"Already correct" is a distinct state from "no memory."** If the text
   already contains the learned form, that's a confirmed no-op, not an
   unknown word (`already_correct_text_is_a_no_op`).
7. **Casing conventions are respected**, e.g. an ALL-CAPS occurrence of a
   corrected word stays ALL-CAPS (`casing_is_preserved_reasonably`).
8. **Reset really resets** — both tables are cleared and previously-applied
   corrections stop applying immediately (`reset_wipes_learned_state`).
9. **A subtle bug found by testing, not anticipated up front:** an
   already-corrected word can have a *different* phonetic key from the error
   spelling that taught the system about it — `metaphone("aditya") = "ATTY"`
   but `metaphone("aaditya") = "TTY"`. Looking candidates up by phonetic key
   alone made an already-fixed sentence look like Kivi had "no memory" of the
   word at all, which is wrong — it should recognise the word as already
   correct. The fix (see `app/memory.py`, `_candidates_for`) also looks up
   candidates by exact canonical-term match, and this is unit-tested
   (`tests/test_memory.py::test_already_correct_word_recognised_as_such`).
10. **A second ordering bug, also found by testing:** when two corrections
    are genuinely tied (case 4), and the input text happens to already read
    like one of the tied options, an earlier version of the code reported
    `already_correct` instead of `ambiguous` — treating a coincidence as
    confirmation. The fix checks ambiguity *before* checking "already
    correct." This is exactly the kind of failure a curated set of
    after-the-fact examples would never catch, which is why both the eval
    suite and a separate pytest suite assert on the specific decision label,
    not just the output text.

---

## 4. Evaluation

Two independent layers:

- **`eval/cases.json` + `eval/run_eval.py`** — the primary evaluation the
  brief asks for. 11 scenarios / 14 checks, each preserving: inputs, expected
  result, actual result, the relevant memory state, and the reasoning trace.
  Outcomes are classified into `useful_intervention`,
  `correct_non_intervention`, `missed_intervention` (false negative),
  `incorrect_intervention` (false positive), and `wrong_decision_reason`
  (right output, wrong reasoning) — so useful and incorrect/unnecessary
  interventions are reported *separately*, as required, not blended into one
  pass rate. Precision/recall are computed over "should this input have
  triggered an intervention?". Latency, model usage, cost, and final
  row-counts (db growth) are included in the summary. Run it and it writes
  `eval/results.json` (full detail) and `eval/report.md` (human-readable) —
  see `RUN.md`.
- **`tests/test_memory.py`** — 7 pytest unit tests on the core logic in
  isolation. This is what actually caught bug #10 above during development;
  it's included so a reviewer has a second, faster way to probe the logic
  directly rather than only through end-to-end scenarios.

Both suites are deterministic and reproducible: no network calls, no LLM,
same output every run.

---

## 5. Limitations / explicitly out of scope

- **Single-token entities only.** Multi-word names/phrases ("Sarvam Kivi
  Labs" as one unit) aren't modelled; each word is corrected independently.
- **No decay or forgetting.** A learned correction persists forever until a
  full reset. A real product would likely want confidence to decay if a term
  goes unused for a long time, or an explicit "forget this" action.
- **Metaphone is a generic English-oriented algorithm.** It won't perfectly
  capture the actual confusion patterns of any specific ASR model, and will
  handle multilingual or code-switched names poorly. A production version
  should probably learn its own confusion patterns from the ASR's real error
  distribution rather than using a fixed general-purpose algorithm.
- **Context is exactly one preceding word.** Sentence-initial occurrences,
  or terms that need two words of context, aren't handled.
- **No semantic disambiguation.** Two genuinely unrelated words that happen
  to share a metaphone code (a phonetic bucket collision) would be treated
  as candidates for the same slot; nothing here understands meaning, only
  sound.
- **No LLM-based fallback for genuinely ambiguous cases.** The system's
  answer to ambiguity is "do nothing," which is safe but not maximally
  helpful — a richer version could surface an ambiguous case to the user for
  a one-tap disambiguation instead of just staying silent.
- This deliberately covers only the "smallest useful edge" the brief
  describes — phonetic memory — not the larger episodic/semantic/factual
  memory vision Kivi is aiming for.

---

## 6. AI use

This system — the product decisions, the code, the tests, the evaluation
suite, and this README — was built in collaboration with Claude (Anthropic),
working inside a coding-agent session with a real sandbox: every module was
actually run, not just written. The core logic was exercised manually first,
then against the pytest suite and the eval suite, and two real bugs (items 9
and 10 above) were found and fixed that way during development, not
discovered later during review. The final `eval/results.json` and
`eval/report.md` in this repository are the actual output of the last run of
`eval/run_eval.py` against the committed code, not hand-written or edited.
