"""Kivi's word-level (phonetic) memory system.

Product decisions encoded here (see README for the full rationale):

1. What counts as "learning": an explicit observation that the user
   corrected a word Kivi produced -- (heard_word -> corrected_word), with an
   optional preceding word for context. This is the highest-signal event
   available: the user directly told us what they wanted. We deliberately do
   NOT try to infer corrections implicitly from ambient text, because that
   invites false positives we can't explain later.

2. Evidence has to accumulate before it changes behaviour. A single
   observation could be a one-off typo, a joke, or noise. MIN_OBSERVATIONS
   gates that.

3. Confidence is relative, not absolute. For a given (phonetic bucket,
   context) we track every distinct correction the user has ever asked for
   and their relative share. If "adithya" has been requested twice and
   "aaditya" once for the same phonetic bucket, confidence is split -- the
   system won't confidently pick either.

4. Context can scope a correction. "kiwi" -> "Kivi" only after "sarvam"
   should not rewrite the fruit. A context-free entry (no preceding word
   requirement) is only created when the user says so; by default corrections
   are context-free ONLY if explicitly registered without a context word.
   Product terms/brand collisions should usually be registered *with*
   context by the caller.

5. The system prefers doing nothing. Below-threshold confidence, below
   MIN_OBSERVATIONS, or ambiguous top candidates all resolve to "no change",
   and the reason is recorded, not silently dropped.
"""
import datetime
from dataclasses import dataclass, field
from typing import Optional

from app import db
from app.phonetics import phonetic_key, tokenize, is_word, clean_lower, apply_casing

MIN_OBSERVATIONS = 2          # don't act on a single correction
CONFIDENCE_THRESHOLD = 0.66   # need a clear majority within the candidate group
AMBIGUITY_MARGIN = 0.15       # top two candidates must differ by at least this much


def _now() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()


@dataclass
class TokenDecision:
    token: str
    decision: str                     # intervened | already_correct | no_memory |
                                       # below_min_observations | low_confidence | ambiguous | not_a_word
    output: str
    reason: str
    candidates: list = field(default_factory=list)


class MemoryStore:
    def __init__(self, db_path: str = None):
        self.db_path = db_path
        db.init_db(db_path)

    def _conn(self):
        return db.get_connection(self.db_path)

    # ---------------------------------------------------------------- learn

    def add_observation(self, heard_word: str, corrected_word: str,
                         context_before: Optional[str] = None,
                         category: Optional[str] = None,
                         source: str = "user_edit") -> dict:
        """Record one correction event and update the derived memory entry."""
        heard_word = heard_word.strip()
        corrected_word = corrected_word.strip()
        ctx = context_before.strip().lower() if context_before else None
        key = phonetic_key(heard_word)
        if not key:
            raise ValueError(f"'{heard_word}' has no phonetic content to learn from")

        conn = self._conn()
        now = _now()
        conn.execute(
            "INSERT INTO observations (heard_word, corrected_word, context_before, "
            "category, source, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (heard_word, corrected_word, ctx, category, source, now),
        )

        # Upsert the specific (key, context, canonical_term) memory row
        row = conn.execute(
            "SELECT id, observation_count FROM memory_entries "
            "WHERE phonetic_key=? AND context_before IS ? AND canonical_term=?",
            (key, ctx, corrected_word),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE memory_entries SET observation_count = observation_count + 1, "
                "last_seen=? WHERE id=?",
                (now, row["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO memory_entries (phonetic_key, context_before, canonical_term, "
                "category, observation_count, confidence, last_seen, created_at) "
                "VALUES (?, ?, ?, ?, 1, 0, ?, ?)",
                (key, ctx, corrected_word, category, now, now),
            )

        # Recompute confidence for every entry sharing this (key, context) bucket
        siblings = conn.execute(
            "SELECT id, observation_count FROM memory_entries "
            "WHERE phonetic_key=? AND context_before IS ?",
            (key, ctx),
        ).fetchall()
        total = sum(s["observation_count"] for s in siblings)
        for s in siblings:
            conf = s["observation_count"] / total if total else 0
            conn.execute("UPDATE memory_entries SET confidence=? WHERE id=?", (conf, s["id"]))

        conn.commit()
        conn.close()
        return {"phonetic_key": key, "context_before": ctx, "canonical_term": corrected_word}

    # ------------------------------------------------------------- inspect

    def memory_state(self) -> list:
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM memory_entries ORDER BY phonetic_key, context_before, confidence DESC"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def observations(self) -> list:
        conn = self._conn()
        rows = conn.execute("SELECT * FROM observations ORDER BY id").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def reset(self) -> None:
        db.reset_db(self.db_path)

    # ------------------------------------------------------------- resolve

    def _candidates_for(self, conn, key: str, clean_token: str, context_word: Optional[str]):
        """Candidate memory entries for a token. We look up two ways and take
        the union:
          (a) by phonetic key of the token as it appears in the text -- the
              normal path, for tokens that still show the ASR-error spelling;
          (b) by exact (case-insensitive) canonical_term match -- because once
              a word IS already corrected in the text, its own phonetic key
              can differ from metaphone(heard_word) (e.g. metaphone("aditya")
              != metaphone("aaditya")), which would otherwise make an
              already-fixed word look like it has "no memory" at all.
        Path (b) is what lets the system correctly recognise "already right"
        rather than "unknown", and is a case we found by testing, not one
        given in the brief.
        """
        by_key = conn.execute(
            "SELECT * FROM memory_entries WHERE phonetic_key=? AND observation_count >= ?",
            (key, MIN_OBSERVATIONS),
        ).fetchall()
        by_canonical = conn.execute(
            "SELECT * FROM memory_entries WHERE LOWER(canonical_term)=? AND observation_count >= ?",
            (clean_token, MIN_OBSERVATIONS),
        ).fetchall()
        seen_ids = set()
        rows = []
        for r in list(by_key) + list(by_canonical):
            rd = dict(r)
            if rd["id"] not in seen_ids:
                seen_ids.add(rd["id"])
                rows.append(rd)
        rows.sort(key=lambda r: r["confidence"], reverse=True)
        context_matches = [r for r in rows if r["context_before"] == context_word]
        global_matches = [r for r in rows if r["context_before"] is None]
        return context_matches, global_matches

    def resolve(self, formatted_text: str, asr_text: str = None) -> dict:
        """Given Kivi's already-formatted transcript, apply memory to produce
        the memory-aware transcript. asr_text is accepted for symmetry with
        the product's three-stage pipeline and is included in the trace for
        inspectability, but resolution itself operates on formatted_text
        (memory should refine formatting, not redo ASR cleanup).
        """
        tokens = tokenize(formatted_text)
        conn = self._conn()

        decisions: list[TokenDecision] = []
        prev_word_clean = None  # lowercased previous *word* token (context)

        for tok in tokens:
            if not is_word(tok):
                decisions.append(TokenDecision(tok, "not_a_word", tok, "punctuation/whitespace"))
                continue

            clean = clean_lower(tok)
            key = phonetic_key(clean)
            context_matches, global_matches = self._candidates_for(conn, key, clean, prev_word_clean)
            pool = context_matches if context_matches else global_matches

            if not pool:
                decisions.append(TokenDecision(tok, "no_memory", tok,
                                                "no memory entry meets the observation minimum for this word"))
                prev_word_clean = clean
                continue

            top = pool[0]

            # Ambiguity is checked BEFORE "already correct": if two candidates
            # are tied, the fact that the text happens to already spell one of
            # them is not confirmation -- it's still a coin flip which one the
            # user meant, so we must not quietly treat it as settled.
            if len(pool) > 1 and (top["confidence"] - pool[1]["confidence"]) < AMBIGUITY_MARGIN:
                decisions.append(TokenDecision(
                    tok, "ambiguous", tok,
                    f"top candidates '{top['canonical_term']}' ({top['confidence']:.2f}) and "
                    f"'{pool[1]['canonical_term']}' ({pool[1]['confidence']:.2f}) are too close to call",
                    candidates=pool))
                prev_word_clean = clean
                continue

            top_rendered = apply_casing(tok, top["canonical_term"])
            if top_rendered == tok:
                decisions.append(TokenDecision(tok, "already_correct", tok,
                                                f"already matches learned form '{top['canonical_term']}'",
                                                candidates=pool))
                prev_word_clean = clean
                continue

            if top["confidence"] < CONFIDENCE_THRESHOLD:
                decisions.append(TokenDecision(
                    tok, "low_confidence", tok,
                    f"best candidate '{top['canonical_term']}' confidence {top['confidence']:.2f} "
                    f"below threshold {CONFIDENCE_THRESHOLD}",
                    candidates=pool))
                prev_word_clean = clean
                continue

            replacement = apply_casing(tok, top["canonical_term"])
            ctx_note = f"after '{prev_word_clean}'" if top["context_before"] else "context-free"
            decisions.append(TokenDecision(
                tok, "intervened", replacement,
                f"replaced with learned form '{top['canonical_term']}' "
                f"(confidence {top['confidence']:.2f}, {top['observation_count']} observations, {ctx_note})",
                candidates=pool))
            prev_word_clean = clean_lower(replacement)

        conn.close()

        memory_aware_text = "".join(d.output for d in decisions)
        return {
            "asr_text": asr_text,
            "formatted_text": formatted_text,
            "memory_aware_text": memory_aware_text,
            "trace": [
                {
                    "token": d.token,
                    "decision": d.decision,
                    "output": d.output,
                    "reason": d.reason,
                    "candidates": [
                        {"canonical_term": c["canonical_term"], "confidence": round(c["confidence"], 3),
                         "observation_count": c["observation_count"],
                         "context_before": c["context_before"]}
                        for c in d.candidates
                    ],
                }
                for d in decisions if d.decision != "not_a_word"
            ],
        }
