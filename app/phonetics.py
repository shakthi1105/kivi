"""Phonetic and tokenization helpers.

We use the classic Metaphone algorithm (via `jellyfish`) as the phonetic key.
It's deterministic, fast (microseconds), requires no model calls, and is good
enough at collapsing "the ways this word tends to get misheard" into a single
bucket -- which is exactly the property we need: ASR errors are phonetic
confusions, not typos, so a phonetic key generalizes much better than string
edit-distance alone.

Nothing here is Kivi-specific; it would work the same for any language model
whose failure mode is "heard something that sounds like X".
"""
import re
import jellyfish

_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?|[^A-Za-z\s]+|\s+")


def phonetic_key(word: str) -> str:
    """Return a phonetic bucket key for a word. Empty/non-alpha -> ''."""
    cleaned = re.sub(r"[^A-Za-z]", "", word)
    if not cleaned:
        return ""
    return jellyfish.metaphone(cleaned)


def tokenize(text: str):
    """Split text into a list of tokens (words, punctuation, whitespace),
    such that ''.join(tokens) == text. Word tokens are alphabetic (with
    optional internal apostrophe); everything else (punctuation, whitespace,
    digits) is passed through untouched.
    """
    return _WORD_RE.findall(text)


def is_word(token: str) -> bool:
    return bool(re.match(r"^[A-Za-z]+(?:'[A-Za-z]+)?$", token))


def clean_lower(word: str) -> str:
    return re.sub(r"[^A-Za-z']", "", word).lower()


def apply_casing(original_token: str, canonical_term: str) -> str:
    """Render canonical_term in a casing consistent with how the original
    (wrong) token appeared, while otherwise trusting the stored casing of
    the canonical term (names/brands usually have one correct casing).
    """
    if original_token.isupper() and len(original_token) > 1:
        return canonical_term.upper()
    if original_token[:1].islower():
        # keep canonical's own internal casing, but don't force uppercase
        # if the canonical term is a common-cased word the user stored lowercase
        return canonical_term
    return canonical_term
