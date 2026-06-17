# Ultimate Language Learning With Anki

This document records the working plan for building Spanish and English learning decks in this repo. The goal is not to create the biggest deck; it is to create a deck system that produces usable language ability with manageable review load.

## Research Basis

The deck strategy is based on these principles:

- Spaced retrieval is the core. Cards should make the learner recall or produce, not only recognize.
- Recognition is useful at the beginning, especially for A0/A1, but should shrink as the learner advances.
- Production and typed cloze cards are stronger for active language ability than multiple choice.
- Audio should be used for retrieval: listen, type, compare, then optionally repeat aloud.
- Dictation helps listening because it forces attention to sound, word boundaries, spelling, and grammar.
- Reading aloud / vocal production improves memory, but it should supplement retrieval rather than replace it.
- Input still matters. Anki preserves and activates knowledge, but listening and reading outside Anki are still required.

Important source ideas already checked:

- Kang, Gollan, and Pashler: retrieval practice beat imitation for L2 spoken vocabulary, including comprehension and production.
- Dictation study with elementary EFL learners: frequent dictation improved listening comprehension.
- Production effect research: vocal production/read-aloud improves L2 vocabulary retention.
- CEFR/vocabulary estimates: A2 often implies roughly 1,500-2,500 passive words, with high-frequency vocabulary as the foundation.
- Schmitt/Nation vocabulary work: the first 2,000-3,000 high-frequency word families are central for input comprehension.

## Deck Architecture

### Keep Passive Vocabulary Separate

Keep `Spanish 4000 Words` as the passive recognition deck.

Purpose:

- Build broad Spanish word recognition.
- Preserve the original 4000 English word ordering.
- Use image, Spanish word, pronunciation hint, English, Spanish meaning/example, and English mirror fields.

Do not convert all 4,000 words into production cards immediately. That would create too many difficult reviews for an A0 learner.

### Build Active Spanish Separately

Main active deck:

`Spanish Core Learning`

Subdecks:

- `Spanish Core Learning::A0 Survival`
- `Spanish Core Learning::A1.1 Foundations`
- `Spanish Core Learning::A1.2 Core Sentences`
- `Spanish Core Learning::A2.1 Daily Past`
- `Spanish Core Learning::A2.2 Natural Spanish`
- `Spanish Core Learning::B1 Bridge`
- Future: `Spanish Core Learning::Listening`

Current implementation:

- Replaces the old `Spanish Grammar` deck.
- Uses a custom note type: `Spanish Core Learning`.
- Uses stable `SourceID` values, so notes can be updated in place.
- Contains 1,063 notes/cards in Anki after cleanup.
- Live Anki subdeck counts:
  - A0 Survival: 124
  - A1.1 Foundations: 359
  - A1.2 Core Sentences: 192
  - A2.1 Daily Past: 180
  - A2.2 Natural Spanish: 158
  - B1 Bridge: 50
- Current card families:
  - rule: 89
  - typed contrast: 89
  - typed correction: 89
  - typed production: 89
  - mini pattern: 89
  - typed cloze from sourced sentences: 438
  - audio cloze from sourced sentences: 180
- No A/B multiple-choice recognition cards remain in this active core deck.

## Target Size

The current cleaned active deck is a strong A0-A2 starting path, but it is not the whole language-learning system. It should be paired with listening, reading, and speaking outside Anki.

Recommended targets:

- Passive vocabulary: 3,000-4,000 recognition cards, already covered by `Spanish 4000 Words`.
- Active A0-A2 core: about 1,000-1,500 cards.
- Initial listening deck: 150-250 cards.
- Later B1 bridge: expand only after A0-A2 reviews are stable.

Practical phase targets:

- Phase 1: 1,058 Spanish Core cards. Done.
- Phase 2: expand short dictation / listen-then-produce if reviews are stable.
- Phase 3: 1,200-1,500 total active cards after several weeks of review data.

## Card Mix By Level

### A0

Goal: learn sentence shape, articles, gender, basic verbs, and survival chunks.

Recommended mix:

- 30-40% typed contrast and typed correction
- 25-35% typed cloze
- 10-20% typed production
- 10-15% rule / mini pattern anchors

Avoid long sentence production at A0. Use passive recognition in `Spanish 4000 Words`, not in the active core deck.

### A1

Goal: build controlled present-tense output.

Recommended mix:

- 20-30% typed contrast and typed correction
- 35-45% typed cloze
- 15-25% typed production
- 10-15% rule / mini pattern anchors

Typed answers should be short and constrained.

### A2

Goal: choose between similar forms and produce common structures.

Recommended mix:

- 15-25% typed contrast and correction
- 40-50% typed cloze
- 20-30% typed production
- 5-10% rule / mini pattern anchors

Use more tense contrast, prepositions, pronouns, connectors, and short sentence transformations.

### B1 Bridge

Goal: preview common structures without overloading an A0 learner.

Recommended topics:

- basic subjunctive triggers
- si clauses
- conditional basics
- aunque contrast
- reported speech basics

Keep this small until A2 is solid.

## Audio Plan

Audio should be a separate learning layer, not just decoration.

Deck:

`Spanish Core Learning::Listening`

Card types:

### Audio Cloze

Front:

- Spanish audio
- Spanish sentence with one blank
- Optional English meaning

Task:

- Type the missing word or chunk.

Back:

- Full Spanish sentence
- English meaning
- Grammar note
- Audio source
- Optional instruction: play again and repeat aloud

Best for:

- verb forms
- articles
- prepositions
- connectors
- common chunks

### Short Dictation

Front:

- Spanish audio only
- Optional cue: "Type the full sentence."

Task:

- Type the full short Spanish sentence.

Back:

- Correct Spanish
- English meaning
- Notes on spelling, accents, and grammar

Best for:

- listening word boundaries
- spelling
- accents
- common sentence patterns

### Listen Then Produce

Front:

- English meaning
- Maybe Spanish audio after answer, not before

Task:

- Type Spanish.

Back:

- Spanish answer
- Audio
- Rule or pattern

Best for:

- active speaking/writing

### Shadowing Prompt

Do not make shadowing the only task.

Use it on the back:

- "Play the audio again and repeat aloud once."

This supports pronunciation and fluency, but retrieval remains the main learning event.

## Audio Sources

Use Tatoeba first.

Already verified:

- Spanish-English link export exists at `per_language/spa/spa-eng_links.tsv.bz2`.
- Spanish sentence export exists.
- English sentence export exists.
- Audio metadata export exists: `sentences_with_audio.tar.bz2`.
- Direct MP3 pattern works: `https://audio.tatoeba.org/sentences/spa/{sentence_id}.mp3`.

For personal offline use, licensing is not a blocker, but keep source metadata anyway:

- sentence id
- audio id
- contributor
- license
- source URL

Reason: attribution fields also help quality review, regeneration, and debugging.

Avoid relying only on generated TTS at first. Native/community recordings are better for listening. TTS can be a fallback for high-value sentences without audio.

## Image Plan

Images are useful, but only when they support the retrieval task.

Research basis:

- Dual coding theory: combining verbal and visual representations can strengthen memory.
- Picture-superiority effects can help concrete vocabulary.
- L2 vocabulary studies on pictures are mixed; pictures help most when they make meaning clearer, but they can also create overconfidence or let the learner answer without retrieving the word.
- Multimedia annotations are useful when they reduce ambiguity, not when they add decorative noise.

Use images for:

- concrete nouns
- visible actions
- visual adjectives
- recognition cards for early vocabulary
- production prompts where the image gives meaning but not the target word

Current decision:

- Keep images in `Spanish 4000 Words`, because that deck is broad concrete vocabulary recognition and images support meaning.
- Do not add images to `Spanish Core Learning` by default. The core deck trains grammar, sentence retrieval, listening, and typed production; images would often leak the answer or distract from the target pattern.

Avoid images for:

- abstract grammar rules
- function words such as `por`, `para`, `se`, `que`
- tense-choice cards
- audio dictation
- cards where the picture gives away the answer too easily

Current status:

- `Spanish 4000 Words` already preserves source images from the 4000 English deck.
- `Spanish Core Learning` does not yet add new images because most cards are grammar, sentence patterns, or listening retrieval.

Future implementation:

- Add an optional `Image` field to active production cards promoted from `Spanish 4000 Words`.
- For concrete vocabulary, use image-front / type-Spanish cards only after recognition is stable.
- Keep images on the back or small on the front depending on whether they help or leak the answer.

## APIs And Sources

### Good Sources

Tatoeba:

- Real sentence pairs.
- Some native/community audio.
- Good for cloze, dictation, and sentence mining.
- Needs filtering and review because corpus examples vary in quality.

Wiktionary / Wiktextract:

- Useful for Spanish part of speech, gender, plural forms, and verb metadata.
- Prefer structured dumps where possible.

Existing `Spanish 4000 Words` data:

- Useful controlled vocabulary base.
- Good for passive recognition and selecting active production targets.

### Use Carefully

LibreTranslate:

- Possible fallback translation.
- Do not treat as source of truth.

Free Dictionary API / Wordnik / WordsAPI:

- More useful for English than Spanish.
- Can help English decks, not primary Spanish grammar source.

Speech-to-text / pronunciation APIs:

- Useful later for pronunciation scoring.
- Not needed for first Anki listening implementation.

### AnkiWeb Shared Decks

Useful for comparison, not blind import.

Potentially useful references:

- 9000 Spanish sentences with native audio
- Spanish Tatoeba Sentences with Audio
- Spanish Top 5000 Vocabulary

Do not import huge decks directly into the main study flow. They can overwhelm scheduling and mix unknown quality into progress. Mine ideas or compare formats instead.

## Quality Rules

Every generated card should satisfy:

- Stable `SourceID`.
- Clear level.
- Clear card type.
- One main retrieval task.
- Answer is not ambiguous if type-checked.
- Full sentence production should use compare/self-grade if multiple answers are valid.
- Spanish sentence and English mirror must correspond.
- No random corpus sentence just because it matches a word.
- No duplicate sentence text for the same target.
- No malformed blanks, for example blanking `es` inside `Eso`.
- For audio cards, the played sentence must match the typed target exactly.

## Review Load

Do not add thousands of active cards at once.

Recommended new-card pace:

- Spanish 4000 Words: 10-20/day recognition.
- Spanish Core Learning: 5-15/day active cards.
- Listening: 3-8/day once added.

If reviews become heavy, reduce new cards before deleting content.

## Implementation Roadmap

### Current Spanish Core Coverage

`Spanish Core Learning` now contains 1,058 active cards:

- 433 typed sentence cloze cards from sourced Tatoeba Spanish-English sentence pairs.
- 180 Spanish audio cloze cards with verified Tatoeba audio.
- 89 rule anchors.
- 89 typed contrast cards.
- 89 typed correction cards.
- 89 typed production cards.
- 89 mini-pattern cards.

English meaning cues were removed from fronts. Cards should rely on Spanish context, audio, and typed retrieval.

### Next Step 1: Expand Spanish Core Beyond A2

Use Tatoeba `spa-eng_links.tsv.bz2`, not the huge global links file.

Add more typed cloze cards for:

- articles: el/la/los/las/un/una
- ser/estar/tener/ir/querer/poder
- present tense forms
- gustar chunks
- pronouns
- prepositions
- time expressions
- past tense anchors
- connectors
- por/para
- present perfect

Use structural filtering plus review, not a broad word blacklist.

### Next Step 2: Expand Listening

Target 150-250 cards.

Use only sentences with verified audio metadata.

Start with:

- 100-150 audio cloze cards
- 40-70 short dictation cards
- 20-30 listen-then-produce cards

### Next Step 3: Sync To Anki Safely

Use `sync_spanish_core_to_anki.py`.

Rules:

- Update existing notes by `SourceID`.
- Prune stale notes only when replacing generated content intentionally.
- Do not delete `Spanish 4000 Words`.
- Keep `Spanish Grammar` deleted/replaced by `Spanish Core Learning`.

## Current English Mastery Coverage

`English Mastery` replaces the old separate `English Grammar Maintenance` and `English Natural Phrases` decks.

It contains 972 active cards:

- 360 natural phrase cloze cards.
- 300 natural phrase production cards.
- 33 rule anchors.
- 99 typed grammar contrast cards.
- 120 English audio cloze cards.
- 60 English dictation cards.

The deck is intended for B2-C2 maintenance and advancement, not beginner English. It should train phrase retrieval, grammar contrast, listening accuracy, and more natural production while the original `4000 Essential English Words` deck remains unchanged.

### Next Step 4: Review

Run:

```bash
python3 test_scripts.py
python3 spanish_core_learning.py --summary
```

Then manually sample:

- 30 grammar cards
- 50 sourced cloze cards
- all audio card types before full sync

## What Not To Do

- Do not make all cards multiple choice.
- Do not make every 4000 vocabulary word a production card immediately.
- Do not import huge AnkiWeb decks directly into the active study queue.
- Do not use AI-generated translations without source/mirror review.
- Do not use audio as passive decoration only.
- Do not optimize for card count over review quality.
