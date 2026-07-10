"""Classify a spoken transcript into an intent (pure; no ROS imports).

Two commands are handled directly here rather than through the LLM, because they
act on the robot's *current* pose, not a destination:

  - "save this location as the office"  -> {"kind": "save", "name": "the office"}
  - "where am i" / "what room is this"  -> {"kind": "whereami"}

Everything else is {"kind": "navigate"} and is handed to the LLM as before.
Intercepting here keeps these two off the LLM's goal schema, where they don't
belong, and makes them deterministic (no model round-trip to mis-transcribe).
"""
import re

# "save ... as/called/named <name>" — the name runs to the end of the phrase.
_SAVE_AS_RE = re.compile(
    r"\bsave\b.+?\b(?:as|called|named)\b\s+(?P<name>.+)$", re.IGNORECASE)
# "save this location/spot/..." with no name given — we know the intent but must
# ask for a name.
_SAVE_BARE_RE = re.compile(
    r"\bsave\b.+\b(?:location|spot|place|position|point|here)\b", re.IGNORECASE)
_WHERE_RE = re.compile(
    r"\b(?:where\s+am\s+i|where\s+are\s+we|what\s+room|which\s+room|"
    r"what(?:'s| is)\s+my\s+location)\b", re.IGNORECASE)


def parse_intent(transcript):
    """Return {"kind": "save"|"whereami"|"navigate", ...}. Never raises."""
    text = (transcript or "").strip()
    if not text:
        return {"kind": "navigate"}
    if _WHERE_RE.search(text):
        return {"kind": "whereami"}
    m = _SAVE_AS_RE.search(text)
    if m:
        return {"kind": "save", "name": clean_name(m.group("name"))}
    if _SAVE_BARE_RE.search(text):
        return {"kind": "save", "name": ""}
    return {"kind": "navigate"}


def clean_name(raw):
    """Tidy a spoken location name: drop trailing punctuation, a trailing
    'please', and surrounding whitespace; lowercase and collapse spaces."""
    if not raw:
        return ""
    name = raw.strip().strip(".!?,")
    name = re.sub(r"\s+please$", "", name, flags=re.IGNORECASE)
    return " ".join(name.lower().split())
