"""Shared deck IO helpers (stdlib only).

Kapsam bilerek dar tutuldu:
- Klasör oluşturma + UTF-8 yazma + TSV metin üretimi + yeni kod için slug.
- Mevcut generator'lardaki `_slug` / `_tags` / `render_tsv` fonksiyonlarına
  DOKUNULMUYOR. Sebep: bu fonksiyonların çıktısı Tags/SourceID üretir ve
  Anki'deki `SyncFingerprint` + `locked` mekanizmasına bağlıdır
  (bkz. anki_protect.py). Slug birleştimek tüm notları "değişti" gösterir,
  gereksiz mass-update / lock fırtınasına yol açar. Yeni generator'lar
  buradaki `slug_ascii` kullanmalı; eskiler stabil kalmalı.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path


def ensure_dir(path: str | Path) -> Path:
    output = Path(path)
    output.mkdir(parents=True, exist_ok=True)
    return output


def write_utf8(path: str | Path, text: str) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return str(target)


def tsv_text(header: list[str], rows: list[list[str]]) -> str:
    """Render Anki import TSV text with the standard html preamble."""
    with io.StringIO() as output:
        output.write("#separator:tab\n#html:true\n")
        writer = csv.writer(output, delimiter="\t", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
        return output.getvalue()


def slug_ascii(text: str) -> str:
    """New-code slug: lowercase ascii, non-alnum -> underscore."""
    return re.sub(r"[^a-z0-9]+", "_", (text or "").strip().lower()).strip("_")


def tag_string(tags) -> str:
    if isinstance(tags, str):
        return tags
    return " ".join(tags)


def print_level_summary(items, total: int) -> None:
    for item in items:
        print(f"{item['id']}: {item['card_count']} cards")
    print(f"total: {total} cards")
