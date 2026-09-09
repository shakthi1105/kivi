# Kivi Word Memory -- Evaluation Report

**14/14 checks passed.**

## Summary

| Metric | Value |
|---|---|
| total_checks | 14 |
| passed | 14 |
| failed | 0 |
| useful_interventions | 6 |
| correct_non_interventions | 8 |
| missed_interventions | 0 |
| incorrect_interventions | 0 |
| wrong_decision_reason | 0 |
| precision | 1.0 |
| recall | 1.0 |
| expected_positive_cases | 6 |
| expected_negative_cases | 8 |
| avg_latency_ms | 0.412 |
| max_latency_ms | 0.707 |
| model_usage | none -- deterministic phonetic matching, no LLM calls in the resolve path |
| estimated_cost_usd | 0.0 |
| final_observations_row_count | 0 |
| final_memory_entries_row_count | 0 |

Precision/recall are computed over the binary question *"should the system have intervened on this input?"* -- a true positive is a correct, useful rewrite; a false positive is an incorrect/unnecessary rewrite (the failure mode that erodes trust fastest); a false negative is a missed correction the system had evidence for.

## Per-case results

### [PASS] brief_example / brief_example_check
_Reproduces the exact example given in the assignment brief: a name and a context-scoped product term, both should be corrected._

- Notes: Directly from the brief. Two independent memory entries both fire in the same sentence.
- Formatted input: `Ask Aditya to review the Sarvam Kiwi service.`
- Expected output: `Ask Aaditya to review the Sarvam Kivi service.`
- Actual output: `Ask Aaditya to review the Sarvam Kivi service.`
- Outcome: **useful_intervention**
- Latency: 0.707 ms
- Token decisions:
  - `Aditya` -> **intervened** (replaced with learned form 'Aaditya' (confidence 1.00, 2 observations, context-free))
  - `Kiwi` -> **intervened** (replaced with learned form 'Kivi' (confidence 1.00, 2 observations, after 'sarvam'))

### [PASS] single_observation_is_not_enough / one_obs_no_intervention
_A single correction is weak evidence (could be a one-off typo or joke). The system must not act on it yet._

- Notes: Only 1 observation exists; MIN_OBSERVATIONS=2. Must leave text untouched, not guess.
- Formatted input: `Priyanka joined the call late.`
- Expected output: `Priyanka joined the call late.`
- Actual output: `Priyanka joined the call late.`
- Outcome: **correct_non_intervention**
- Latency: 0.296 ms

### [PASS] crosses_threshold_after_second_observation / before_second_obs
_The same correction, once reinforced by a second independent observation, should now be trusted and applied. Tests that learning is a threshold crossed by evidence, not a one-shot event._

- Notes: Still only 1 observation at this point.
- Formatted input: `Priyanka joined the call late.`
- Expected output: `Priyanka joined the call late.`
- Actual output: `Priyanka joined the call late.`
- Outcome: **correct_non_intervention**
- Latency: 0.327 ms

### [PASS] crosses_threshold_after_second_observation / after_second_obs
_The same correction, once reinforced by a second independent observation, should now be trusted and applied. Tests that learning is a threshold crossed by evidence, not a one-shot event._

- Notes: Second observation pushes observation_count to 2 and confidence to 1.0; now applied.
- Formatted input: `Priyanka joined the call late.`
- Expected output: `Priyangka joined the call late.`
- Actual output: `Priyangka joined the call late.`
- Outcome: **useful_intervention**
- Latency: 0.349 ms
- Token decisions:
  - `Priyanka` -> **intervened** (replaced with learned form 'Priyangka' (confidence 1.00, 2 observations, context-free))

### [PASS] context_scoping_protects_unrelated_sense / kiwi_with_context_fires
_The product term 'Kivi' was only ever taught in the context 'sarvam ___'. The same phonetic word appearing without that context (the fruit) must be left alone -- this is the central false-positive risk the brief's example hints at._

- Notes: Context word 'sarvam' immediately precedes 'kiwi' -> should correct to the product name.
- Formatted input: `I use the Sarvam Kiwi app daily.`
- Expected output: `I use the Sarvam Kivi app daily.`
- Actual output: `I use the Sarvam Kivi app daily.`
- Outcome: **useful_intervention**
- Latency: 0.453 ms
- Token decisions:
  - `Kiwi` -> **intervened** (replaced with learned form 'Kivi' (confidence 1.00, 2 observations, after 'sarvam'))

### [PASS] context_scoping_protects_unrelated_sense / kiwi_without_context_is_untouched
_The product term 'Kivi' was only ever taught in the context 'sarvam ___'. The same phonetic word appearing without that context (the fruit) must be left alone -- this is the central false-positive risk the brief's example hints at._

- Notes: No 'sarvam' before 'kiwi' -- must NOT rewrite the fruit into the product name. Deliberate no-op.
- Formatted input: `I had a kiwi for breakfast this morning.`
- Expected output: `I had a kiwi for breakfast this morning.`
- Actual output: `I had a kiwi for breakfast this morning.`
- Outcome: **correct_non_intervention**
- Latency: 0.34 ms

### [PASS] conflicting_corrections_are_ambiguous / ambiguous_no_intervention
_The user has, on different occasions, corrected the same phonetic word to two different canonical forms with equal support. The system should recognise it cannot tell them apart and do nothing rather than guess._

- Notes: 'Nehal' (2 obs, 0.50 confidence) and 'Nihal' (2 obs, 0.50 confidence) are tied. Below the ambiguity margin -- must not pick one arbitrarily. Note the input already reads 'Nehal' so the visible text happens not to change, but the trace must show decision=ambiguous, not already_correct -- a tie isn't confirmation.
- Formatted input: `Nehal sent the report yesterday.`
- Expected output: `Nehal sent the report yesterday.`
- Actual output: `Nehal sent the report yesterday.`
- Outcome: **correct_non_intervention**
- Latency: 0.43 ms
- Token decisions:
  - `Nehal` -> **ambiguous** (top candidates 'Nehal' (0.50) and 'Nihal' (0.50) are too close to call)

### [PASS] weak_majority_is_not_confident_enough / weak_majority_no_intervention
_A correction can have more observations than its alternative without clearing the confidence bar. This tests that the system requires a clear majority, not just a plurality._

- Notes: 'Zara' has 3/5=0.60 confidence, above 'Sarah' at 2/5=0.40, but below CONFIDENCE_THRESHOLD=0.66. System withholds rather than acting on a weak signal.
- Formatted input: `Sara will lead the workshop.`
- Expected output: `Sara will lead the workshop.`
- Actual output: `Sara will lead the workshop.`
- Outcome: **correct_non_intervention**
- Latency: 0.572 ms
- Token decisions:
  - `Sara` -> **low_confidence** (best candidate 'Zara' confidence 0.60 below threshold 0.66)

### [PASS] already_correct_text_is_a_no_op / already_correct_check
_If the formatted transcript already contains the learned canonical form, the system should recognise this as already satisfied, not attempt a (no-op) replacement._

- Notes: Distinguishes 'nothing to do because already right' from 'nothing to do because unsure' -- both are non-interventions but for different reasons, and the trace should say so.
- Formatted input: `Aaditya reviewed the pull request.`
- Expected output: `Aaditya reviewed the pull request.`
- Actual output: `Aaditya reviewed the pull request.`
- Outcome: **correct_non_intervention**
- Latency: 0.332 ms
- Token decisions:
  - `Aaditya` -> **already_correct** (already matches learned form 'Aaditya')

### [PASS] unrelated_text_passes_through / unrelated_text_check
_Baseline: text containing no words the system has any memory of must be returned byte-for-byte identical._

- Notes: No overlap with memory at all.
- Formatted input: `The weather in Chennai is warm today.`
- Expected output: `The weather in Chennai is warm today.`
- Actual output: `The weather in Chennai is warm today.`
- Outcome: **correct_non_intervention**
- Latency: 0.359 ms

### [PASS] casing_is_preserved_reasonably / all_caps_check
_A learned word appearing in ALL CAPS (e.g. shouted/emphasised speech) should be corrected while preserving the all-caps rendering._

- Notes: Casing convention (all-caps) of the original token is preserved on the corrected form.
- Formatted input: `ADITYA IS OUT TODAY.`
- Expected output: `AADITYA IS OUT TODAY.`
- Actual output: `AADITYA IS OUT TODAY.`
- Outcome: **useful_intervention**
- Latency: 0.39 ms
- Token decisions:
  - `ADITYA` -> **intervened** (replaced with learned form 'Aaditya' (confidence 1.00, 2 observations, context-free))

### [PASS] multiple_entries_in_one_sentence / multi_entry_check
_A richer sentence exercising several unrelated memory entries together, to check they don't interfere with each other._

- Notes: 'Nehal' is already correctly cased so it's a no-op; 'figma' and 'aditya' both need correcting; unrelated words pass through.
- Formatted input: `Nehal will share the figma file with aditya before lunch.`
- Expected output: `Nehal will share the Figma file with Aaditya before lunch.`
- Actual output: `Nehal will share the Figma file with Aaditya before lunch.`
- Outcome: **useful_intervention**
- Latency: 0.532 ms
- Token decisions:
  - `Nehal` -> **already_correct** (already matches learned form 'Nehal')
  - `figma` -> **intervened** (replaced with learned form 'Figma' (confidence 1.00, 2 observations, context-free))
  - `aditya` -> **intervened** (replaced with learned form 'Aaditya' (confidence 1.00, 2 observations, context-free))

### [PASS] reset_wipes_learned_state / before_reset_intervenes
_After a reset, all previously learned corrections must stop applying -- memory state and observation log are both empty._

- Notes: Confirms the entry is live before we reset.
- Formatted input: `Aditya is presenting today.`
- Expected output: `Aaditya is presenting today.`
- Actual output: `Aaditya is presenting today.`
- Outcome: **useful_intervention**
- Latency: 0.356 ms
- Token decisions:
  - `Aditya` -> **intervened** (replaced with learned form 'Aaditya' (confidence 1.00, 2 observations, context-free))

### [PASS] reset_wipes_learned_state / after_reset_no_longer_intervenes
_After a reset, all previously learned corrections must stop applying -- memory state and observation log are both empty._

- Notes: Reset must clear all memory_entries and observations; the same sentence is now untouched.
- Formatted input: `Aditya is presenting today.`
- Expected output: `Aditya is presenting today.`
- Actual output: `Aditya is presenting today.`
- Outcome: **correct_non_intervention**
- Latency: 0.332 ms
