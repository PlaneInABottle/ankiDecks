# Anti-Memorization Brainstorm: Solving Surface Memorization in Anki Flashcards

## The Problem

Flashcard learners often memorize the *card surface* (specific sentence, layout, visual cues) rather than the *target knowledge* (grammar pattern, word meaning). The card feels easy because the learner recognizes the surface, not because they've genuinely retrieved the knowledge. This is the single biggest weakness in SRS-based language learning.

## Research Basis

### Encoding Specificity (Tulving & Thomson, 1973)

Memory binds the target word to the specific sentence it appears in. "Hay" gets bound to "¡Ah, allí ___ una mariposa!" — so the learner can retrieve it *in that sentence* but maybe not in "Hay demasiadas cosas que hacer" or in real conversation.

- **Source**: Tulving, E., & Thomson, D. M. (1973). Encoding specificity and retrieval processes in episodic memory. *Psychological Review*, 80(5), 352–373.
- **Wikipedia**: https://en.wikipedia.org/wiki/Encoding_specificity_principle

### New Theory of Disuse (Bjork & Bjork, 1992)

Memory has two strengths:
- **Storage strength (SS)**: how well-learned something is
- **Retrieval strength (RS)**: how accessible it is right now

When RS is high (card feels easy), restudy gives almost zero SS boost. The learner is practicing *recognition*, not *retrieval*. The card feels "learned" but the knowledge isn't deepening.

- **Source**: Bjork, R. A., & Bjork, E. L. (1992). A new theory of disuse and an old theory of stimulus fluctuation.
- **Lab**: https://bjorklab.psych.ucla.edu/research/

### Transfer-Appropriate Processing (Morris et al., 1977)

Memory is best when retrieval conditions match encoding conditions. If you only practice "see sentence → fill blank", you train one retrieval route. Real conversation requires a different route: "concept → produce word". If the routes don't overlap, the training doesn't transfer.

- **Source**: Morris, C. D., Bransford, J. D., & Franks, J. J. (1977). Levels of processing versus transfer appropriate processing. *Journal of Verbal Learning and Verbal Behavior*, 16(5), 519–533.
- **Wikipedia**: https://en.wikipedia.org/wiki/Transfer-appropriate_processing

### Generation Effect (Slamecka & Graf, 1978)

Generating produces better retention than recognizing. But once you've memorized the sentence, cloze stops being generation and becomes recognition — you're just matching the surface to a stored memory.

### Desirable Difficulty (Bjork, 1994)

Some difficulty improves retention. The color/font add-on creates a *perceptual* desirable difficulty, which helps a little. But the *structural* surface — same sentence, same blank position, same cue type — is unchanged. The brain still recognizes "oh, this is the butterfly sentence, the answer is hay" regardless of font color.

- **Source**: Bjork, R. A. (1994). Memory and metamemory considerations in the training of human beings.
- **Wikipedia**: https://en.wikipedia.org/wiki/Desirable_difficulty

### Why the Color/Font Add-on Only Partially Helps

It changes the *perceptual* surface (what Bjork calls a "perceptual desirable difficulty"), which helps a little. But the *structural* surface — the same sentence, same blank position, same cue type — is unchanged. Your brain still recognizes the card regardless of font color.

---

## Five Approaches (Ranked by Impact)

### 1. Sentence Rotator (Highest Impact)

**Concept**: One card per target, but the displayed sentence changes every review. The learner can never memorize a sentence because they see a different one each time.

**Example**:
- Review 1: `¡Ah, allí _____ una mariposa!` → type `hay`
- Review 2 (same card, days later): `_____ demasiadas cosas que hacer` → type `hay`
- Review 3: `A esta hora _____ un tráfico increíble` → type `hay`

**Research basis**: Encoding specificity — by rotating sentences, the target word is bound to *all* contexts, not just one. This forces genuine retrieval of the word, not recognition of the sentence.

**Implementation options**:

#### Option A: JavaScript in card template (no add-on needed)

- Store all 6 sentences in one field, pipe-separated: `¡Ah, allí hay una mariposa! | Hay demasiadas cosas que hacer | A esta hora hay un tráfico increíble`
- Front template JavaScript picks a random sentence, blanks the target, displays it
- Each review shows a different sentence — surface memorization becomes impossible
- **Pros**: Immediately buildable, zero add-on, works on all platforms (desktop, mobile, web)
- **Cons**: Doesn't track which sentences have been shown, so distribution is random; can't ensure even rotation; can't log which sentences are hardest
- **Effort**: ~2 hours

#### Option B: Python Anki add-on

- Tracks shown sentences per card, ensures even rotation
- Can integrate with FSRS to show harder sentences when retrieval strength is high (more desirable difficulty)
- Can log which sentences cause failures and weight them to appear more often
- **Pros**: Robust, trackable, integrates with scheduling
- **Cons**: Requires Anki add-on development, desktop-only logic (mobile would need AnkiWeb sync)
- **Effort**: ~1-2 days

**Verdict**: Option A is immediately buildable with zero add-on. Option B is the "proper" solution if A proves effective.

---

### 2. Cue Type Rotator (High Impact)

**Concept**: One card per target, but the *task type* changes every review. Sometimes text cloze, sometimes audio, sometimes L1→L2, sometimes dictation.

**Example** (same card, different reviews):
- Review 1 (text cloze): `_____ muchas palabras` → type `hay`
- Review 2 (audio cloze): 🔊 `_____ muchas palabras` → type `hay`
- Review 3 (L1→L2): `Type the Spanish for: There are many words` → type `hay`
- Review 4 (dictation): 🔊 `Type the full sentence` → type `Hay muchas palabras que no entiendo`

**Research basis**: Transfer-appropriate processing — training multiple retrieval routes means the knowledge transfers to real conversation (which requires all of these routes simultaneously).

**Implementation**: Would need a Python Anki add-on that swaps the template + fields displayed on each review. More complex than sentence rotation because it changes the entire card structure, not just one field.

**Pros**: Trains transfer to real conversation; directly addresses the "I can do flashcards but can't speak" problem
**Cons**: Complex add-on; changes card structure dynamically; mobile compatibility uncertain
**Effort**: ~3-5 days

---

### 3. Context Fader (Medium Impact)

**Concept**: Gradually remove context as the card matures, forcing deeper retrieval.

**Example** (same card, maturing over weeks):
- Reviews 1-5: `¡Ah, allí _____ una mariposa!` (full sentence context)
- Reviews 6-10: `_____ una mariposa` (reduced context)
- Reviews 11-15: `Type: "there is"` (no context, pure production)

**Research basis**: Bjork's desirable difficulty — as retrieval strength grows, make the task harder to keep boosting storage strength instead of just reinforcing recognition.

**Implementation**: Would need an add-on that reads the card's review count / interval and modifies the displayed content based on maturity. AnkiConnect can query intervals, so this is buildable.

**Pros**: Creates a difficulty gradient; adapts to learner's growing ability
**Cons**: Hard to calibrate the thresholds; might frustrate learners; requires careful field design
**Effort**: ~2-3 days

---

### 4. Fresh Sentence Injector (Medium Impact)

**Concept**: Periodically retire old sentence cards and inject new sentences for the same target.

**Example**: After 30 days of reviewing 6 "hay" sentences, suspend those 6 cards and create 6 new "hay" sentences from Tatoeba. The learner faces fresh surfaces but the same target.

**Implementation**: Python pipeline script (like the ones already in this repo). Query AnkiConnect for cards with >20 reviews, mine new Tatoeba sentences, create new cards, suspend old ones.

**Pros**: No add-on needed; uses existing pipeline architecture; keeps deck fresh
**Cons**: Creates new cards (inflates review count); requires periodic manual runs; doesn't solve the problem within a single card
**Effort**: ~1 day

---

### 5. Multi-Blank Cloze (Low Impact)

**Concept**: Use Anki's native `{{c1::word1}}` `{{c2::word2}}` cloze system to create multiple cloze cards from the same sentence, each blanking a different word.

**Implementation**: Native Anki feature, no add-on needed.

**Pros**: Easy; native; tests different targets from one sentence
**Cons**: Tests *different targets* from the same sentence, not the *same target* in different sentences. Useful but doesn't directly solve surface memorization.
**Effort**: ~1 hour

---

## Recommended Build Order

1. **Sentence Rotator (Option A: JS template)** — prototype immediately, zero add-on, directly solves the core problem
2. **Sentence Rotator (Option B: Python add-on)** — upgrade if A proves effective
3. **Cue Type Rotator (add-on)** — the deeper fix that trains transfer to real conversation
4. **Fresh Sentence Injector (pipeline)** — keep deck fresh over months
5. **Context Fader / Multi-Blank** — nice-to-have enhancements

---

## Key Insight

The color/font add-on addresses *perceptual* surface memorization. The Sentence Rotator addresses *structural* surface memorization — which is the harder and more important problem. Both together would create a system where the learner cannot memorize the card surface and must genuinely retrieve the target knowledge every time.

---

## Status

This is a brainstorm document. No implementation has been done yet. The user will review and decide which approach(es) to build.
