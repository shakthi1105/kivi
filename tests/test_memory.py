import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from app.memory import MemoryStore


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(db_path=str(tmp_path / "test.db"))
    s.reset()
    return s


def test_single_observation_does_not_intervene(store):
    store.add_observation("priyanka", "Priyangka")
    r = store.resolve("Priyanka joined the call.")
    assert r["memory_aware_text"] == "Priyanka joined the call."


def test_two_observations_intervene(store):
    store.add_observation("priyanka", "Priyangka")
    store.add_observation("priyanka", "Priyangka")
    r = store.resolve("Priyanka joined the call.")
    assert r["memory_aware_text"] == "Priyangka joined the call."


def test_context_scoping(store):
    store.add_observation("kiwi", "Kivi", context_before="sarvam")
    store.add_observation("kiwi", "Kivi", context_before="sarvam")
    with_ctx = store.resolve("The Sarvam Kiwi app is great.")
    without_ctx = store.resolve("I ate a kiwi.")
    assert "Kivi" in with_ctx["memory_aware_text"]
    assert without_ctx["memory_aware_text"] == "I ate a kiwi."


def test_ambiguous_correction_does_nothing(store):
    store.add_observation("nehal", "Nehal")
    store.add_observation("nehal", "Nehal")
    store.add_observation("nehal", "Nihal")
    store.add_observation("nehal", "Nihal")
    r = store.resolve("Nehal sent the file.")
    assert r["memory_aware_text"] == "Nehal sent the file."
    trace = [t for t in r["trace"] if t["token"] == "Nehal"][0]
    assert trace["decision"] == "ambiguous"


def test_already_correct_word_recognised_as_such(store):
    store.add_observation("aditya", "Aaditya")
    store.add_observation("aditya", "Aaditya")
    r = store.resolve("Aaditya reviewed it.")
    trace = [t for t in r["trace"] if t["token"] == "Aaditya"][0]
    assert trace["decision"] == "already_correct"


def test_reset_clears_everything(store):
    store.add_observation("aditya", "Aaditya")
    store.add_observation("aditya", "Aaditya")
    assert store.memory_state()
    store.reset()
    assert store.memory_state() == []
    assert store.observations() == []
    r = store.resolve("Aditya is here.")
    assert r["memory_aware_text"] == "Aditya is here."


def test_casing_preserved_for_all_caps(store):
    store.add_observation("aditya", "Aaditya")
    store.add_observation("aditya", "Aaditya")
    r = store.resolve("ADITYA IS HERE.")
    assert r["memory_aware_text"] == "AADITYA IS HERE."
