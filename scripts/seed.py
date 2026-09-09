"""Populate the database with a small, reproducible set of observations so a
reviewer opening the demo UI immediately sees a populated memory state
instead of an empty one. Safe to re-run: it resets first.

Usage: python3 scripts/seed.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.memory import MemoryStore

SEED_OBSERVATIONS = [
    # A colleague's name the ASR keeps flattening to a common spelling.
    dict(heard_word="aditya", corrected_word="Aaditya", category="person_name"),
    dict(heard_word="aditya", corrected_word="Aaditya", category="person_name"),
    # The product name, homophone of the fruit -- context-scoped on purpose.
    dict(heard_word="kiwi", corrected_word="Kivi", context_before="sarvam", category="product_term"),
    dict(heard_word="kiwi", corrected_word="Kivi", context_before="sarvam", category="product_term"),
    dict(heard_word="kiwi", corrected_word="Kivi", context_before="sarvam", category="product_term"),
    # A teammate's name with a less common spelling.
    dict(heard_word="nehal", corrected_word="Nehal", category="person_name"),
    dict(heard_word="nehal", corrected_word="Nehal", category="person_name"),
    # A work tool name ASR renders as an ordinary word.
    dict(heard_word="figma", corrected_word="Figma", category="product_term"),
    dict(heard_word="figma", corrected_word="Figma", category="product_term"),
]


def main():
    store = MemoryStore()
    store.reset()
    for obs in SEED_OBSERVATIONS:
        store.add_observation(**obs)
    print(f"Seeded {len(SEED_OBSERVATIONS)} observations.")
    for e in store.memory_state():
        print(f"  {e['canonical_term']!r:15} key={e['phonetic_key']:6} "
              f"ctx={e['context_before']}  obs={e['observation_count']}  conf={e['confidence']:.2f}")


if __name__ == "__main__":
    main()
