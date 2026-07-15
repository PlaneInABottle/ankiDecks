---
name: audit-language-decks
description: Audit and repair authored or generated language-learning decks, including TSV/CSV glossaries, grammar cards, sentence-mining corpora, cached selections, and Anki import files. Use when reviewing translation accuracy, naturalness, grammar classification, CEFR level, dialect consistency, duplicate or leaking clozes, metadata, provenance, generator root causes, regeneration safety, or protected Anki synchronization.
---

# Audit Language Decks

Treat deck content as executable data. Fix the durable source and the pipeline that accepted bad content before regenerating artifacts.

## Workflow

1. Read project instructions and canonical generation, test, and sync commands.
2. Classify each relevant file as one of:
   - durable authored source;
   - external corpus or immutable upstream data;
   - derived selection cache;
   - generated import artifact;
   - validation or synchronization code.
3. Record baseline row counts by level, card type, status, target, and provenance. Run existing tests before editing.
4. Review representative cards and every reported failure across these dimensions:
   - source meaning versus target headword, definition, example, and mirror;
   - grammatical function rather than token presence alone;
   - natural phrasing, agreement, tense, accents, and punctuation;
   - level suitability and sentence completeness;
   - configured regional dialect;
   - duplicates, answer leakage, ambiguous prompts, and unsafe metadata inference.
5. Trace each failure with `git blame`, `git log -S`, and generator flow. Identify why validation allowed it; do not stop at correcting the row.
6. Fix the smallest durable layer that owns the error:
   - correct authored source data directly;
   - add contextual validation for deterministic failures;
   - validate cached rows under current rules;
   - version derived caches when selection policy changes;
   - rank candidates by teaching quality and use level-specific quotas instead of filling weak global quotas;
   - use documented ID rejects or text corrections only for immutable external corpus rows.
7. Add regression tests for the corrected content and the root-cause invariant. Avoid context-free spellchecking rules that reject valid homographs.
8. Regenerate through canonical commands. Never hand-edit generated artifacts as the only fix.
9. Inspect generated output directly, including changed row counts, metadata, dialect leaks, rejected IDs, duplicate IDs, and cloze visibility.
10. Run the full repository test suite and `git diff --check`. Report any criterion that remains unverified.

## Review Principles

- Prefer fewer strong examples over quota-filling weak examples.
- Require a mined target to occur exactly once and in the intended grammatical role.
- Keep semantic corrections separate from source mirrors and provenance.
- Treat a `reviewed` label as a claim requiring validation, not proof of correctness.
- Preserve manual Anki edits through the repository's fingerprint or lock mechanism.
- Do not use force-overwrite or stale-note pruning without explicit sync authorization.

## This Repository

- Treat `generated/spanish_reviewed_glossary_full.tsv` as the durable Spanish 4,000-word glossary.
- Treat `generated/sources/tatoeba/selected_spa_eng_pairs.tsv` as a derived, policy-versioned cache.
- Generate the vocabulary deck with:

  `python3 spanish_deck.py --glossary generated/spanish_reviewed_glossary_full.tsv --output-dir generated/spanish_full`

- Generate Spanish Core with:

  `python3 spanish_core_learning.py`

- Verify with:

  `python3 test_scripts.py`

- When the user explicitly requests live Anki synchronization, first run `python3 protect_manual_edits.py --apply`. Then sync the changed deck through its documented script without `--force`. Use `--prune-stale` for Spanish Core only when removal of obsolete generated notes is part of the approved change.
