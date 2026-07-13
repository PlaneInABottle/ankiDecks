"""Shared helpers for protecting manually edited Anki notes from sync overwrites.

A note tagged with ``LOCKED_TAG`` is treated as hand-edited. Sync scripts skip
content-field updates for such notes so manual edits are preserved. The note is
still created if missing, and scheduling/deck operations still apply.

Run ``protect_manual_edits.py`` while Anki is open to automatically detect notes
whose content differs from the source TSV and tag them as locked.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from functools import lru_cache
from pathlib import Path

LOCKED_TAG = "locked"
FINGERPRINT_FIELD = "SyncFingerprint"
LEGACY_FINGERPRINT_PATH = (
    Path(__file__).resolve().parent / "generated" / "legacy_sync_fingerprints.json"
)

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
    FINGERPRINT_FIELD,
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


def content_fields(field_names) -> list:
    """Return authored fields from a model's complete field list."""
    return [name for name in field_names if name not in NON_CONTENT_FIELDS]


def content_fingerprint(fields: dict, field_names) -> str:
    """Return a stable fingerprint of exactly the fields a sync may replace."""
    values = [[name, raw_collapse(_field_text(fields.get(name)))] for name in field_names]
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def source_fields_with_fingerprint(
    source_fields: dict, field_names, fingerprint_field: str = FINGERPRINT_FIELD
) -> dict:
    """Copy source fields and record the content version written by the sync."""
    fields = dict(source_fields)
    fields[fingerprint_field] = content_fingerprint(fields, field_names)
    return fields


@lru_cache(maxsize=4)
def load_legacy_fingerprints(path: str = str(LEGACY_FINGERPRINT_PATH)) -> dict:
    """Load generated-version fingerprints used only for first-run migration.

    The manifest contains hashes, not card text.  A legacy note is eligible for
    normal in-place updating only when its live authored fields exactly match a
    known generated version.  Missing manifests fail closed.
    """
    manifest_path = Path(path)
    if not manifest_path.exists():
        return {}
    with manifest_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("version") != 1 or not isinstance(payload.get("namespaces"), dict):
        raise ValueError(f"Unsupported legacy fingerprint manifest: {manifest_path}")
    return payload["namespaces"]


def legacy_fingerprints(
    namespace: str,
    source_id: str,
    path: str = str(LEGACY_FINGERPRINT_PATH),
) -> tuple[str, ...]:
    """Return known previous generated fingerprints for one stable source ID."""
    value = load_legacy_fingerprints(path).get(namespace, {}).get(source_id, ())
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list):
        return tuple(item for item in value if isinstance(item, str) and item)
    return ()


def note_has_untracked_edits(
    live_fields: dict,
    source_fields: dict,
    field_names,
    fingerprint_field: str = FINGERPRINT_FIELD,
    legacy_fingerprints: tuple[str, ...] = (),
) -> bool:
    """Return whether updating a note would overwrite a user edit.

    Newer synced notes carry the fingerprint of the last content written by a
    script. If the live fields no longer match it, the user changed the note.
    Legacy notes have no stored fingerprint.  They may update when their live
    content equals either the current source or an explicitly supplied hash of
    a previous generated version.  Anything else is treated as a manual edit.
    """
    live_fingerprint = content_fingerprint(live_fields, field_names)
    stored_fingerprint = _field_text(live_fields.get(fingerprint_field))
    if stored_fingerprint:
        return live_fingerprint != stored_fingerprint
    known_generated = {
        content_fingerprint(source_fields, field_names),
        *(fingerprint for fingerprint in legacy_fingerprints if fingerprint),
    }
    return live_fingerprint not in known_generated


def _field_text(value) -> str:
    if isinstance(value, dict):
        return value.get("value", "")
    return value or ""
