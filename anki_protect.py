"""Shared helpers for protecting manually edited Anki notes from sync overwrites.

A note tagged with ``LOCKED_TAG`` is treated as hand-edited. Sync scripts skip
content-field updates for such notes so manual edits are preserved. The note is
still created if missing, and scheduling/deck operations still apply.

Run ``protect_manual_edits.py`` while Anki is open to automatically detect notes
whose content differs from the source TSV and tag them as locked.
"""

from __future__ import annotations

import html
import re

LOCKED_TAG = "locked"

# Fields that are not "content" the user authors by hand. These are either
# identifiers, scheduling/deck metadata, or media handles rewritten by the sync
# itself, so differences there do not count as a manual content edit.
NON_CONTENT_FIELDS = {
    "SourceID",
    "DeckPath",
    "Tags",
    "Audio",
    "AudioURL",
    "AudioContributor",
    "AudioLicense",
    "AudioID",
}


def note_is_locked(tags) -> bool:
    return LOCKED_TAG in (tags or [])


def normalize(value: str) -> str:
    """Collapse whitespace and strip HTML for a forgiving content comparison."""
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", "", str(value))
    text = html.unescape(text)
    return " ".join(text.split())


def raw_collapse(value: str) -> str:
    """Collapse whitespace only, preserving HTML markup."""
    if not value:
        return ""
    return " ".join(str(value).split())


def content_changed(live: str, source: str) -> bool:
    """True when a field differs enough to be a manual edit.

    Both the raw (markup-preserving) and the text (markup-stripped) forms are
    compared so that formatting-only changes are also detected.
    """
    return normalize(live) != normalize(source) or raw_collapse(live) != raw_collapse(source)


def detect_content_edits(live_fields: dict, source_fields: dict, field_names) -> list:
    """Return the list of field names that were manually edited.

    ``live_fields`` / ``source_fields`` map field name -> {"value": ...} (Anki
    notesInfo shape) or field name -> string (TSV row shape).
    """
    edited = []
    for name in field_names:
        if name in NON_CONTENT_FIELDS:
            continue
        live = _field_text(live_fields.get(name))
        source = _field_text(source_fields.get(name))
        if content_changed(live, source):
            edited.append(name)
    return edited


def _field_text(value) -> str:
    if isinstance(value, dict):
        return value.get("value", "")
    return value or ""
