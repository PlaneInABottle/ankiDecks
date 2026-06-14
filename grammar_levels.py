import argparse
import csv
import io
from pathlib import Path


LEVELS = [
    {
        "id": "b2_tense_system",
        "name": "B2 - Tense System",
        "goal": "Choose tense/aspect by meaning, not by isolated keywords.",
        "topics": [
            "present perfect vs past simple",
            "present perfect continuous",
            "past perfect",
            "future forms",
            "narrative tenses",
        ],
    },
    {
        "id": "b2_sentence_control",
        "name": "B2 - Sentence Control",
        "goal": "Control clauses, conditionals, passive voice, and reported speech.",
        "topics": [
            "conditionals",
            "mixed conditionals",
            "passive voice",
            "relative clauses",
            "reported speech",
            "noun clauses",
        ],
    },
    {
        "id": "b2_verb_patterns",
        "name": "B2 - Verb Patterns",
        "goal": "Remember high-friction verb grammar while speaking and writing.",
        "topics": [
            "gerund vs infinitive",
            "used to patterns",
            "modal verbs",
            "modal perfect",
            "causatives",
        ],
    },
    {
        "id": "c1_precision",
        "name": "C1 - Precision",
        "goal": "Make precise choices with articles, prepositions, quantifiers, and emphasis.",
        "topics": [
            "articles",
            "prepositions",
            "countable and uncountable nouns",
            "comparatives",
            "emphasis and inversion",
        ],
    },
    {
        "id": "c1_style",
        "name": "C1 - Style & Fluency",
        "goal": "Use advanced structures for natural, connected, professional English.",
        "topics": [
            "sentence connectors",
            "participle clauses",
            "reduced relative clauses",
            "hedging",
            "formal register",
        ],
    },
    {
        "id": "c2_mastery",
        "name": "C2 - Mastery",
        "goal": "Maintain high-level grammar for nuance, compression, stance, and complex writing.",
        "topics": [
            "advanced inversion",
            "subjunctive and mandative structures",
            "clefting and fronting",
            "ellipsis and substitution",
            "advanced concession",
            "nominalisation",
            "parallelism",
        ],
    },
]


def _tags(level, topic, card_type):
    return [
        "english_grammar",
        "grammar_maintenance",
        level,
        topic.replace(" ", "_").replace("/", "_"),
        card_type,
    ]


def _add(cards, level, topic, card_type, front, back):
    reason = ""
    examples = ""
    if "<b>Reason</b><br>" in back:
        reason = back.split("<b>Reason</b><br>", 1)[1]
    if "<b>Examples</b><br>" in back:
        examples = back.split("<b>Examples</b><br>", 1)[1].split("<b>Watch out</b>", 1)[0]
    cards.append(
        {
            "level": level,
            "topic": topic,
            "card_type": card_type,
            "front": front,
            "back": back,
            "reason": reason,
            "examples": examples,
            "self_grade": _self_grade(card_type),
            "tags": _tags(level, topic, card_type),
        }
    )


def _self_grade(card_type):
    if card_type == "rule":
        return "Good = remembered formula and use case. Hard = remembered one but not both. Again = could not explain the pattern."
    if card_type == "contrast":
        return "Good = chose the right option and explained why. Hard = chose right but explanation was weak. Again = chose wrong."
    if card_type == "correction":
        return "Good = fixed the sentence and named the rule. Hard = fixed it but could not explain. Again = missed the correction."
    if card_type == "production":
        return "Good = produced a natural sentence with the target pattern. Hard = understandable but awkward. Again = wrong pattern."
    if card_type == "choose":
        return "Good = chose correctly and explained why. Hard = chose correctly but weak explanation. Again = chose wrong."
    if card_type == "pattern":
        return "Good = could reuse the pattern in a new sentence. Hard = recognized it only. Again = did not remember it."
    return "Good = confident recall. Hard = partial recall. Again = missed it."


def _rule_back(formula, use, examples, traps=None):
    parts = [f"<b>Formula</b><br>{formula}", f"<b>Use</b><br>{use}", "<b>Examples</b>"]
    parts.extend(f"- {example}" for example in examples)
    if traps:
        parts.append("<b>Watch out</b>")
        parts.extend(f"- {trap}" for trap in traps)
    return "<br>".join(parts)


def _add_rule_set(cards, level, topic, formula, use, examples, traps=None):
    _add(cards, level, topic, "rule", f"Rule: {topic}", _rule_back(formula, use, examples, traps))


def _add_contrast(cards, level, topic, front, answer, reason):
    _add(cards, level, topic, "contrast", front, f"<b>Answer</b><br>{answer}<br><br><b>Reason</b><br>{reason}")


def _add_correction(cards, level, topic, wrong, right, reason):
    _add(cards, level, topic, "correction", f"Correct: {wrong}", f"{right}<br><br><b>Reason</b><br>{reason}")


def _add_production(cards, level, topic, prompt, answer, note):
    _add(cards, level, topic, "production", f"Say naturally: {prompt}", f"{answer}<br><br><b>Why</b><br>{note}")


def _add_practice(cards, level, topic, card_type, front, answer, reason):
    _add(cards, level, topic, card_type, front, f"<b>Answer</b><br>{answer}<br><br><b>Reason</b><br>{reason}")


def _add_expansion_cards(cards):
    entries = [
        ("b2_tense_system", "present perfect vs past simple", "choose", "Choose: I _____ three reports this week.<br>A) wrote<br>B) have written", "B) I have written three reports this week.", "this week is unfinished, so present perfect is natural."),
        ("b2_tense_system", "present perfect vs past simple", "pattern", "Mini pattern: unfinished time result", "I have + V3 + this week / today / recently.", "Use this when the time window connects to now."),
        ("b2_tense_system", "present perfect continuous", "choose", "Choose: You look tired. What _____?<br>A) have you done<br>B) have you been doing", "B) What have you been doing?", "The visible present result points to recent ongoing activity."),
        ("b2_tense_system", "present perfect continuous", "correction", "Correct: I have been knowing her for years.", "I have known her for years.", "Stative verbs like know usually use present perfect simple."),
        ("b2_tense_system", "past perfect", "correction", "Correct: By the time I arrived, they already left.", "By the time I arrived, they had already left.", "Use past perfect for the earlier past event."),
        ("b2_tense_system", "future forms", "choose", "Choose: Look at those clouds. It _____.<br>A) will rain<br>B) is going to rain", "B) It is going to rain.", "going to fits prediction based on present evidence."),
        ("b2_tense_system", "future forms", "production", "Express completion before a deadline: finish the draft / by Monday.", "I will have finished the draft by Monday.", "Future perfect marks completion before a future point."),
        ("b2_tense_system", "narrative tenses", "correction", "Correct: I walked home when I was seeing the accident.", "I was walking home when I saw the accident.", "Background action uses past continuous; interrupting event uses past simple."),
        ("b2_tense_system", "narrative tenses", "pattern", "Mini pattern: background + interruption", "I was V-ing when + past simple.", "Use this to tell a clear past sequence."),
        ("b2_sentence_control", "conditionals", "choose", "Choose: If I _____ more time, I would take the course.<br>A) have<br>B) had", "B) If I had more time, I would take the course.", "Second conditional uses past form for unreal present/future."),
        ("b2_sentence_control", "conditionals", "production", "Make third conditional: she did not check the file; she missed the error.", "If she had checked the file, she would have noticed the error.", "Third conditional imagines a different past."),
        ("b2_sentence_control", "mixed conditionals", "production", "Past mistake, present result: I did not sleep; I am tired now.", "If I had slept, I would not be tired now.", "Past condition plus present result."),
        ("b2_sentence_control", "passive voice", "choose", "Choose: The new policy _____ next month.<br>A) will introduce<br>B) will be introduced", "B) The new policy will be introduced next month.", "The policy receives the action, so passive is needed."),
        ("b2_sentence_control", "passive voice", "correction", "Correct: The decision made yesterday.", "The decision was made yesterday.", "Passive voice needs be + V3."),
        ("b2_sentence_control", "relative clauses", "choose", "Choose: The company _____ I work for is expanding.<br>A) where<br>B) that", "B) The company that I work for is expanding.", "that refers to the company as object of the relative clause."),
        ("b2_sentence_control", "relative clauses", "pattern", "Mini pattern: reduced relative", "The people invited to the meeting... / The team working on the issue...", "Use V3 for passive meaning and V-ing for active meaning."),
        ("b2_sentence_control", "reported speech", "choose", "Choose: She said she _____ busy the next day.<br>A) is<br>B) was", "B) She said she was busy the next day.", "Past reporting usually triggers backshift."),
        ("b2_sentence_control", "noun clauses", "choose", "Choose: I wonder _____.<br>A) where is he<br>B) where he is", "B) I wonder where he is.", "Embedded questions use statement word order."),
        ("b2_verb_patterns", "gerund vs infinitive", "choose", "Choose: I remember _____ him at the conference.<br>A) meeting<br>B) to meet", "A) I remember meeting him at the conference.", "remember + -ing refers to a past memory."),
        ("b2_verb_patterns", "gerund vs infinitive", "correction", "Correct: She avoided to answer the question.", "She avoided answering the question.", "avoid is followed by -ing."),
        ("b2_verb_patterns", "used to patterns", "choose", "Choose: I _____ waking up early now.<br>A) used to<br>B) am used to", "B) I am used to waking up early now.", "be used to means be familiar with and takes -ing/noun."),
        ("b2_verb_patterns", "modal verbs", "choose", "Choose: You _____ submit the form today; it is optional.<br>A) don't have to<br>B) mustn't", "A) You don't have to submit the form today.", "don't have to means not necessary; mustn't means prohibited."),
        ("b2_verb_patterns", "modal perfect", "correction", "Correct: You should told me earlier.", "You should have told me earlier.", "Past criticism uses should have + V3."),
        ("b2_verb_patterns", "causatives", "choose", "Choose: I _____ my passport renewed last week.<br>A) renewed<br>B) had", "B) I had my passport renewed last week.", "Causative have shows someone else did the service."),
        ("c1_precision", "articles", "choose", "Choose: _____ rich should pay more tax.<br>A) Rich<br>B) The rich", "B) The rich should pay more tax.", "the + adjective can refer to a group of people."),
        ("c1_precision", "articles", "correction", "Correct: The life is unpredictable.", "Life is unpredictable.", "Use zero article for general abstract nouns."),
        ("c1_precision", "articles", "pattern", "Mini pattern: abstract general vs specific", "Life is hard. / The life he described was hard.", "Zero article for general meaning; the for specified meaning."),
        ("c1_precision", "prepositions", "choose", "Choose: Her decision had an impact _____ the whole team.<br>A) on<br>B) to", "A) an impact on the whole team.", "impact on is the usual noun-preposition pattern."),
        ("c1_precision", "prepositions", "correction", "Correct: This is consistent to our policy.", "This is consistent with our policy.", "consistent with is the standard adjective-preposition pattern."),
        ("c1_precision", "countable and uncountable nouns", "choose", "Choose: We need _____.<br>A) more evidence<br>B) more evidences", "A) more evidence.", "evidence is usually uncountable."),
        ("c1_precision", "countable and uncountable nouns", "correction", "Correct: There were less complaints this month.", "There were fewer complaints this month.", "Use fewer with countable plural nouns."),
        ("c1_precision", "comparatives", "choose", "Choose: The more carefully we test, _____.<br>A) the fewer errors we miss<br>B) fewer errors we miss", "A) the fewer errors we miss.", "Correlative comparative uses the + comparative, the + comparative."),
        ("c1_precision", "comparatives", "pattern", "Mini pattern: proportional comparison", "The more + clause, the more/less + clause.", "Use this for linked increases/decreases."),
        ("c1_precision", "emphasis and inversion", "choose", "Choose: Only after the audit _____ the issue.<br>A) we understood<br>B) did we understand", "B) Only after the audit did we understand the issue.", "Fronted only after triggers inversion."),
        ("c1_precision", "emphasis and inversion", "production", "Emphasize that stable input was the thing needed.", "What we needed was stable input.", "What-cleft focuses the important information after was."),
        ("c1_style", "sentence connectors", "choose", "Choose: The design is simple; _____, it scales well.<br>A) moreover<br>B) however", "A) moreover", "Moreover adds supporting information; however contrasts."),
        ("c1_style", "sentence connectors", "correction", "Correct: The data was incomplete, therefore we delayed the launch.", "The data was incomplete; therefore, we delayed the launch.", "therefore connects independent clauses and needs strong punctuation."),
        ("c1_style", "participle clauses", "choose", "Choose: _____ the risks, we postponed the release.<br>A) Knowing<br>B) Known", "A) Knowing the risks, we postponed the release.", "The subject we actively knew the risks."),
        ("c1_style", "participle clauses", "production", "Compress: Because they had finished the analysis, they published the report.", "Having finished the analysis, they published the report.", "having + V3 shows earlier completed action."),
        ("c1_style", "reduced relative clauses", "choose", "Choose: The documents _____ yesterday are missing.<br>A) sending<br>B) sent", "B) The documents sent yesterday are missing.", "sent has passive meaning: documents were sent."),
        ("c1_style", "reduced relative clauses", "correction", "Correct: The people invited the meeting arrived early.", "The people invited to the meeting arrived early.", "invited to the meeting is a reduced passive relative phrase."),
        ("c1_style", "hedging", "choose", "Choose the more cautious claim:<br>A) This proves the method works.<br>B) This suggests the method may work.", "B) This suggests the method may work.", "C1 writing often needs careful strength of claim."),
        ("c1_style", "hedging", "correction", "Correct: The results definitely show that the policy caused the change.", "The results suggest that the policy may have contributed to the change.", "Use hedging when evidence is not conclusive."),
        ("c1_style", "formal register", "choose", "Choose the more formal version:<br>A) We looked into the issue.<br>B) We investigated the issue.", "B) We investigated the issue.", "Single precise verbs often sound more formal than phrasal verbs."),
        ("c1_style", "formal register", "production", "Make formal: Please check that all documents are current.", "Please ensure that all documents are up to date.", "ensure that is a formal/professional pattern."),
        ("c2_mastery", "advanced inversion", "choose", "Choose: Rarely _____ such a clear result.<br>A) we see<br>B) do we see", "B) Rarely do we see such a clear result.", "Fronted negative/restrictive adverbials trigger inversion."),
        ("c2_mastery", "advanced inversion", "correction", "Correct: Not only the proposal failed, but it damaged trust.", "Not only did the proposal fail, but it also damaged trust.", "Not only at the front requires auxiliary inversion."),
        ("c2_mastery", "subjunctive and mandative structures", "choose", "Choose: The policy requires that every file ____ encrypted.<br>A) is<br>B) be", "B) be", "Mandative structures use the base verb in formal English."),
        ("c2_mastery", "subjunctive and mandative structures", "production", "Make formal: They said he should receive compensation.", "They recommended that he receive compensation.", "recommend that + subject + base verb."),
        ("c2_mastery", "clefting and fronting", "choose", "Choose the cleft:<br>A) The delay worried me most.<br>B) What worried me most was the delay.", "B) What worried me most was the delay.", "A what-cleft controls focus and rhythm."),
        ("c2_mastery", "clefting and fronting", "correction", "Correct: What I need are a clear answer.", "What I need is a clear answer.", "The complement a clear answer is singular."),
        ("c2_mastery", "ellipsis and substitution", "choose", "Choose: If the legal team approves the plan, we should ____ too.<br>A) do so<br>B) do it so", "A) do so", "do so substitutes for the repeated action."),
        ("c2_mastery", "ellipsis and substitution", "production", "Avoid repetition: She accepted the first proposal but rejected the second proposal.", "She accepted the first proposal but rejected the second one.", "one replaces a repeated singular countable noun."),
        ("c2_mastery", "advanced concession", "choose", "Choose the more formal concession:<br>A) Although it was costly, it worked.<br>B) Costly though it was, it worked.", "B) Costly though it was, it worked.", "Adjective + though + clause is compact and formal."),
        ("c2_mastery", "advanced concession", "correction", "Correct: No matter carefully we tested it, one bug remained.", "No matter how carefully we tested it, one bug remained.", "no matter needs a wh-word such as how."),
        ("c2_mastery", "nominalisation", "choose", "Choose the more formal version:<br>A) because the supplier failed to comply<br>B) due to the supplier's failure to comply", "B) due to the supplier's failure to comply", "Nominalisation creates denser formal style."),
        ("c2_mastery", "nominalisation", "correction", "Correct: The investigate of the incident took weeks.", "The investigation of the incident took weeks.", "Use the correct noun form investigation."),
        ("c2_mastery", "parallelism", "choose", "Choose the parallel version:<br>A) efficient, scalable, and it is secure<br>B) efficient, scalable, and secure", "B) efficient, scalable, and secure", "Parallel items should share the same grammatical shape."),
        ("c2_mastery", "parallelism", "production", "Make parallel: The tool helps teams plan, testing, and to deploy.", "The tool helps teams plan, test, and deploy.", "Coordinated verbs should share the same form."),
        ("c1_precision", "articles", "production", "Use articles naturally: general education vs specific program.", "Education is expensive, but the education she received was excellent.", "Zero article for general abstract noun; the for a specified instance."),
        ("c1_style", "formal register", "correction", "Correct: We need to find out why the system broke.", "We need to determine why the system failed.", "determine/failed is more formal and precise than find out/broke."),
        ("c2_mastery", "ellipsis and substitution", "correction", "Correct: I hope so that they approve it.", "I hope that they approve it. / I hope so.", "so substitutes for a whole clause; do not combine hope so that."),
        ("b2_sentence_control", "reported speech", "pattern", "Mini pattern: reporting changes", "said (that) + subject + backshifted verb + adjusted time word.", "Use this for reported speech in a past reporting frame."),
        ("b2_verb_patterns", "modal perfect", "production", "Speculate about a missed email in the past.", "She might have missed the email.", "might have + V3 expresses past possibility."),
    ]
    for entry in entries:
        _add_practice(cards, *entry)


def _build_grammar_cards():
    cards = []

    _add_rule_set(
        cards,
        "b2_tense_system",
        "present perfect vs past simple",
        "present perfect: have/has + V3<br>past simple: V2",
        "Use present perfect for life experience, unfinished time, or present result. Use past simple for finished time.",
        [
            "I have visited Spain. = life experience",
            "I visited Spain last year. = finished time",
            "She has finished the report. = result now",
        ],
        ["Do not use present perfect with a finished time expression like yesterday/last year."],
    )
    _add_contrast(
        cards,
        "b2_tense_system",
        "present perfect vs past simple",
        "Choose: I _____ this company since 2021.<br>A) worked for<br>B) have worked for",
        "B) I have worked for this company since 2021.",
        "since + starting point + still true now -> present perfect.",
    )
    _add_correction(
        cards,
        "b2_tense_system",
        "present perfect vs past simple",
        "I know her since five years.",
        "I have known her for five years.",
        "Use present perfect with for + duration when the situation continues now.",
    )
    _add_production(
        cards,
        "b2_tense_system",
        "present perfect continuous",
        "I started learning Spanish two years ago and I still learn it.",
        "I have been learning Spanish for two years.",
        "Present perfect continuous emphasizes an activity continuing until now.",
    )
    _add_rule_set(
        cards,
        "b2_tense_system",
        "present perfect continuous",
        "have/has been + V-ing",
        "Use for continuing activities, repeated recent actions, or visible present results.",
        [
            "I have been working all morning.",
            "She has been studying Spanish for two years.",
            "It has been raining, so the ground is wet.",
        ],
        ["Stative verbs often prefer present perfect simple: I have known her, not I have been knowing her."],
    )
    _add_rule_set(
        cards,
        "b2_tense_system",
        "past perfect",
        "had + V3",
        "Use for an action before another past action.",
        [
            "When I arrived, they had already left.",
            "By the time we noticed the bug, users had reported it.",
        ],
    )
    _add_contrast(
        cards,
        "b2_tense_system",
        "past perfect",
        "Choose the better sequence:<br>A) When I arrived, they left.<br>B) When I arrived, they had left.",
        "B) When I arrived, they had left.",
        "had left makes it clear that their leaving happened before your arrival.",
    )
    _add_rule_set(
        cards,
        "b2_tense_system",
        "future forms",
        "will + V1; be going to + V1; present continuous; will have + V3",
        "Choose future form by meaning: prediction/decision, plan, arrangement, or completion before a future point.",
        [
            "I will call you later. = decision/promise",
            "We are going to redesign the page. = plan",
            "I am meeting her tomorrow. = arrangement",
            "By Friday, we will have finished. = completed before Friday",
        ],
    )
    _add_contrast(
        cards,
        "b2_tense_system",
        "future forms",
        "Choose: By the time you arrive, I _____ the slides.<br>A) will finish<br>B) will have finished",
        "B) By the time you arrive, I will have finished the slides.",
        "will have + V3 marks completion before a future reference point.",
    )
    _add_rule_set(
        cards,
        "b2_tense_system",
        "narrative tenses",
        "past simple + past continuous + past perfect",
        "Use narrative tenses to order background, events, and earlier events.",
        [
            "I was walking home when I saw the accident.",
            "She had left before I arrived.",
            "The team was testing the app when the server crashed.",
        ],
    )
    _add_production(
        cards,
        "b2_tense_system",
        "narrative tenses",
        "One action was in progress; another interrupted it: test the app / server crash.",
        "The team was testing the app when the server crashed.",
        "Past continuous gives the background activity; past simple gives the interrupting event.",
    )

    _add_rule_set(
        cards,
        "b2_sentence_control",
        "conditionals",
        "zero: if + present, present<br>first: if + present, will + V1<br>second: if + V2, would + V1<br>third: if + had + V3, would have + V3",
        "Use conditionals for facts, likely results, unreal present/future, and unreal past.",
        [
            "If water boils, it turns to steam.",
            "If it rains, we will postpone.",
            "If I were free, I would join.",
            "If she had studied, she would have passed.",
        ],
    )
    _add_rule_set(
        cards,
        "b2_sentence_control",
        "mixed conditionals",
        "past condition -> present result: if + had + V3, would + V1<br>present condition -> past result: if + V2, would have + V3",
        "Use when the condition and result belong to different times.",
        [
            "If I had slept earlier, I would feel better now.",
            "If I were more careful, I would not have made that mistake.",
        ],
    )
    _add_contrast(
        cards,
        "b2_sentence_control",
        "mixed conditionals",
        "Choose the meaning: If I had saved the file, I would not be rewriting it now.<br>A) past cause, present result<br>B) present cause, past result",
        "A) past cause, present result.",
        "had saved is an unreal past condition; would not be rewriting it now is the present result.",
    )
    _add_correction(
        cards,
        "b2_sentence_control",
        "conditionals",
        "If I would have known, I would tell you.",
        "If I had known, I would have told you.",
        "Do not use would in the if-clause of a third conditional.",
    )
    _add_rule_set(
        cards,
        "b2_sentence_control",
        "passive voice",
        "be + V3",
        "Use passive when the action/result matters more than the actor.",
        [
            "The report was approved.",
            "The files were sent.",
            "The issue has been fixed.",
        ],
    )
    _add_production(
        cards,
        "b2_sentence_control",
        "passive voice",
        "Make the result the focus: Someone rejected the proposal twice.",
        "The proposal was rejected twice.",
        "Passive voice keeps attention on the affected thing, not the actor.",
    )
    _add_rule_set(
        cards,
        "b2_sentence_control",
        "relative clauses",
        "who/which/that/where/when/whose + clause",
        "Use relative clauses to identify or add information about a noun.",
        [
            "The engineer who fixed it explained the cause.",
            "The tool which we use is reliable.",
            "The office where we met is closed.",
            "The candidate whose resume impressed us accepted the offer.",
        ],
    )
    _add_correction(
        cards,
        "b2_sentence_control",
        "relative clauses",
        "The candidate which resume impressed us accepted the offer.",
        "The candidate whose resume impressed us accepted the offer.",
        "Use whose for possession in relative clauses, including people and organizations.",
    )
    _add_rule_set(
        cards,
        "b2_sentence_control",
        "reported speech",
        "reporting verb + backshifted clause when reporting past speech",
        "Use reported speech to retell what someone said.",
        [
            "She said she was tired.",
            "He told me he had finished.",
            "They said they would arrive late.",
        ],
        ["Backshift depends on context; if the statement is still generally true, backshift may be optional."],
    )
    _add_correction(
        cards,
        "b2_sentence_control",
        "reported speech",
        "She said that she is coming tomorrow.",
        "She said that she was coming the next day.",
        "Past reporting context usually triggers backshift and time-word adjustment.",
    )
    _add_rule_set(
        cards,
        "b2_sentence_control",
        "noun clauses",
        "what/whether/why/how/where + subject + verb",
        "Use noun clauses as subject, object, or complement.",
        [
            "I know what she said.",
            "We discussed whether they agreed.",
            "The report explains why the system failed.",
        ],
    )
    _add_correction(
        cards,
        "b2_sentence_control",
        "noun clauses",
        "I do not know why did the system fail.",
        "I do not know why the system failed.",
        "A noun clause uses statement word order, not question inversion.",
    )

    _add_rule_set(
        cards,
        "b2_verb_patterns",
        "gerund vs infinitive",
        "verb + -ing or verb + to + V1",
        "Memorize verb patterns because meaning often depends on the first verb.",
        [
            "I enjoy working here.",
            "They decided to leave early.",
            "He admitted making the mistake.",
            "She offered to help.",
        ],
    )
    _add_contrast(
        cards,
        "b2_verb_patterns",
        "gerund vs infinitive",
        "Explain the difference:<br>A) I stopped to call her.<br>B) I stopped calling her.",
        "A = I paused another activity in order to call her.<br>B = I no longer called her.",
        "Some verbs change meaning depending on whether they take to + V1 or -ing.",
    )
    _add_rule_set(
        cards,
        "b2_verb_patterns",
        "used to patterns",
        "used to + V1; be used to + noun/-ing; get used to + noun/-ing",
        "Use these to separate past habits from familiarity/adaptation.",
        [
            "I used to work late. = past habit",
            "I am used to working late. = familiar with it",
            "I am getting used to the new schedule. = adapting now",
        ],
    )
    _add_correction(
        cards,
        "b2_verb_patterns",
        "used to patterns",
        "I am used to wake up early.",
        "I am used to waking up early.",
        "be used to is followed by a noun or -ing form.",
    )
    _add_rule_set(
        cards,
        "b2_verb_patterns",
        "modal verbs",
        "modal + V1",
        "Use modals for ability, permission, obligation, advice, certainty, and possibility.",
        [
            "She can drive.",
            "You should review it.",
            "They might be late.",
            "You must submit the form.",
        ],
    )
    _add_rule_set(
        cards,
        "b2_verb_patterns",
        "modal perfect",
        "modal + have + V3",
        "Use for past possibility, deduction, regret, criticism, or missed opportunity.",
        [
            "You should have told me.",
            "She might have missed the email.",
            "He must have forgotten.",
            "We could have avoided this.",
        ],
    )
    _add_contrast(
        cards,
        "b2_verb_patterns",
        "modal perfect",
        "What is the difference?<br>A) He must be tired.<br>B) He must have been tired.",
        "A = deduction about now.<br>B = deduction about the past.",
        "The perfect form moves the modal meaning into the past.",
    )
    _add_rule_set(
        cards,
        "b2_verb_patterns",
        "causatives",
        "have/get + object + V3",
        "Use causatives when someone arranges for another person to do something.",
        [
            "I had my car repaired.",
            "She got her hair cut.",
            "We had the report translated.",
        ],
    )
    _add_production(
        cards,
        "b2_verb_patterns",
        "causatives",
        "Say that a professional repaired your laptop; you did not repair it yourself.",
        "I had my laptop repaired.",
        "have/get + object + V3 shows that you arranged the service.",
    )

    _add_rule_set(
        cards,
        "c1_precision",
        "articles",
        "a/an/the/zero article",
        "Use articles to mark specificity, countability, shared knowledge, and generalization.",
        [
            "I need a laptop. = any laptop",
            "The laptop on the desk is mine. = specific",
            "Technology changes quickly. = general uncountable/abstract",
            "The technology we use is outdated. = specific technology",
        ],
    )
    _add_contrast(
        cards,
        "c1_precision",
        "articles",
        "Choose and explain:<br>A) I went to hospital.<br>B) I went to the hospital.",
        "B is standard American English for visiting/going to a specific hospital; British English often uses 'to hospital' for being admitted as a patient.",
        "Articles are partly variety-sensitive, so the card tests meaning and register, not a single universal phrase.",
    )
    _add_correction(
        cards,
        "c1_precision",
        "articles",
        "She gave me an useful advice.",
        "She gave me useful advice.",
        "advice is uncountable, and useful begins with a consonant sound, but no article is needed here.",
    )
    _add_rule_set(
        cards,
        "c1_precision",
        "prepositions",
        "fixed verb/adjective/noun + preposition patterns",
        "Many prepositions are pattern-based and must be learned as chunks.",
        [
            "depend on the data",
            "responsible for the release",
            "interested in robotics",
            "similar to the prototype",
        ],
    )
    _add_production(
        cards,
        "c1_precision",
        "prepositions",
        "Use the right fixed preposition: This decision depends ___ the data.",
        "This decision depends on the data.",
        "depend on is a fixed verb-preposition pattern.",
    )
    _add_rule_set(
        cards,
        "c1_precision",
        "countable and uncountable nouns",
        "many/few + countable; much/little + uncountable; fewer vs less",
        "Choose quantifiers based on noun type.",
        [
            "many issues / fewer issues",
            "much information / less information",
            "a piece of advice, not an advice",
        ],
    )
    _add_rule_set(
        cards,
        "c1_precision",
        "comparatives",
        "comparative + than; much/far/slightly + comparative; the + superlative",
        "Use modifiers to make comparisons precise.",
        [
            "This version is slightly faster.",
            "The new workflow is far more reliable.",
            "This is the most useful option.",
        ],
    )
    _add_correction(
        cards,
        "c1_precision",
        "comparatives",
        "This approach is more clearer than the old one.",
        "This approach is clearer than the old one.",
        "Do not double-mark comparatives: use clearer or more clear, not more clearer.",
    )
    _add_rule_set(
        cards,
        "c1_precision",
        "emphasis and inversion",
        "It was...that/who; what...was; negative/fronted phrase + auxiliary + subject",
        "Use emphasis and inversion to shift focus or sound more formal.",
        [
            "It was the analyst who found the bug.",
            "What we needed was stable input.",
            "Never have I seen this before.",
            "Only after testing did we deploy.",
        ],
    )

    _add_rule_set(
        cards,
        "c1_style",
        "sentence connectors",
        "connector + clause/punctuation pattern",
        "Use connectors to show contrast, addition, reason, result, concession, or sequence.",
        [
            "The report was complete; however, two risks remained.",
            "Because the data was inconsistent, we delayed the release.",
            "The scan passed; therefore, we approved deployment.",
            "Although the budget was reduced, the team delivered.",
        ],
    )
    _add_contrast(
        cards,
        "c1_style",
        "sentence connectors",
        "Choose the punctuation pattern:<br>A) The scan passed, however, two risks remained.<br>B) The scan passed; however, two risks remained.",
        "B) The scan passed; however, two risks remained.",
        "however connects independent clauses and usually needs stronger punctuation than a comma alone.",
    )
    _add_production(
        cards,
        "c1_style",
        "sentence connectors",
        "Join naturally with contrast: The model is accurate. It is too slow for production.",
        "The model is accurate; however, it is too slow for production.",
        "A semicolon + connector cleanly links two independent clauses.",
    )
    _add_rule_set(
        cards,
        "c1_style",
        "participle clauses",
        "V-ing / V3 / having + V3 clause",
        "Use participle clauses to compress related information.",
        [
            "Having prepared the draft, they submitted it.",
            "Knowing the risk, we delayed the release.",
            "Approved by the board, the plan moved forward.",
        ],
    )
    _add_correction(
        cards,
        "c1_style",
        "participle clauses",
        "Walking into the meeting, the agenda was already on the screen.",
        "Walking into the meeting, I saw that the agenda was already on the screen.",
        "The implied subject of a participle clause must match the subject of the main clause.",
    )
    _add_rule_set(
        cards,
        "c1_style",
        "reduced relative clauses",
        "noun + V-ing/V3 phrase",
        "Use reduced relatives to make noun descriptions shorter.",
        [
            "The person responsible for QA joined.",
            "The files sent yesterday arrived.",
            "The team working on the fix met today.",
        ],
    )
    _add_rule_set(
        cards,
        "c1_style",
        "hedging",
        "may/might/seems/appears/likely/could",
        "Use hedging to soften claims and avoid overstatement.",
        [
            "The result seems clear.",
            "The timeline may shift.",
            "This could be the best option.",
            "It appears that the model overfit the data.",
        ],
    )
    _add_production(
        cards,
        "c1_style",
        "hedging",
        "Make this less absolute: The new process is the cause of the delay.",
        "The new process appears to be one cause of the delay.",
        "Hedging protects accuracy when evidence is incomplete.",
    )
    _add_rule_set(
        cards,
        "c1_style",
        "formal register",
        "polite modal/passive/nominal structures",
        "Use formal grammar for professional or academic tone.",
        [
            "Could you please share the figures?",
            "The proposal was approved by the committee.",
            "Please ensure that all citations are up to date.",
        ],
    )

    _add_rule_set(
        cards,
        "c2_mastery",
        "advanced inversion",
        "fronted negative/restrictive phrase + auxiliary + subject + verb",
        "Use for emphatic or literary/formal ordering.",
        [
            "Under no circumstances should the data be shared.",
            "Not only did the proposal fail, but it also damaged trust.",
            "Had I known earlier, I would have intervened.",
        ],
        ["This is powerful but marked; avoid overusing it in casual speech."],
    )
    _add_production(
        cards,
        "c2_mastery",
        "advanced inversion",
        "Make more formal/emphatic: We should not share the data under any circumstances.",
        "Under no circumstances should we share the data.",
        "A fronted negative/restrictive phrase triggers auxiliary-subject inversion.",
    )
    _add_rule_set(
        cards,
        "c2_mastery",
        "subjunctive and mandative structures",
        "demand/recommend/insist + that + subject + base verb",
        "Use mandative subjunctive in formal recommendations, requirements, and demands.",
        [
            "They recommended that he be removed from the project.",
            "The policy requires that each file be encrypted.",
            "I insist that she receive a formal apology.",
        ],
    )
    _add_rule_set(
        cards,
        "c2_mastery",
        "clefting and fronting",
        "What/All/The thing + clause + be...; fronted object/adverbial",
        "Use to control information focus and rhythm.",
        [
            "What surprised me was how quickly they adapted.",
            "All I need is a clear answer.",
            "This problem, we cannot ignore.",
        ],
    )
    _add_production(
        cards,
        "c2_mastery",
        "clefting and fronting",
        "Emphasize the surprising part: Their speed surprised me.",
        "What surprised me was their speed.",
        "A what-cleft puts the focus after was.",
    )
    _add_rule_set(
        cards,
        "c2_mastery",
        "ellipsis and substitution",
        "omit repeated words; use do so/one/ones/so/neither/nor",
        "Use to avoid repetition while keeping meaning clear.",
        [
            "I expected the system to fail, and it did.",
            "She approved the first draft but rejected the second one.",
            "If the client objects, we should do so too.",
        ],
    )
    _add_correction(
        cards,
        "c2_mastery",
        "ellipsis and substitution",
        "She approved the first version but rejected the second version one.",
        "She approved the first version but rejected the second one.",
        "one substitutes for a repeated singular countable noun; do not keep both the noun and substitute.",
    )
    _add_rule_set(
        cards,
        "c2_mastery",
        "advanced concession",
        "adjective/adverb/noun + though/as + subject + verb; no matter + wh-word",
        "Use for compact concession in formal or literary style.",
        [
            "Difficult though it was, the migration succeeded.",
            "Try as he might, he could not reproduce the bug.",
            "No matter how carefully we tested it, one issue remained.",
        ],
    )
    _add_contrast(
        cards,
        "c2_mastery",
        "advanced concession",
        "Which is more compressed/formal?<br>A) Although it was difficult, the migration succeeded.<br>B) Difficult though it was, the migration succeeded.",
        "B) Difficult though it was, the migration succeeded.",
        "Adjective + though/as + clause is a compact concession pattern.",
    )
    _add_rule_set(
        cards,
        "c2_mastery",
        "nominalisation",
        "turn clauses/verbs into noun phrases",
        "Use nominalisation for dense formal writing, but avoid making prose heavy.",
        [
            "They failed to comply -> their failure to comply",
            "We investigated the incident -> our investigation of the incident",
            "The model improved -> the model's improvement",
        ],
    )
    _add_rule_set(
        cards,
        "c2_mastery",
        "parallelism",
        "match grammatical forms in coordinated structures",
        "Use parallel structure for clarity, rhythm, and formal polish.",
        [
            "The plan is efficient, scalable, and secure.",
            "She likes analysing data, writing reports, and presenting findings.",
            "The goal is not to blame but to understand.",
        ],
    )
    _add_correction(
        cards,
        "c2_mastery",
        "parallelism",
        "The plan is efficient, scales well, and security-focused.",
        "The plan is efficient, scalable, and secure.",
        "Parallel coordinated items should use the same grammatical shape.",
    )
    _add_contrast(
        cards,
        "c2_mastery",
        "advanced inversion",
        "Which is more formal/emphatic?<br>A) I had never seen such a result.<br>B) Never had I seen such a result.",
        "B) Never had I seen such a result.",
        "Fronted negative adverbials trigger inversion and create emphasis.",
    )
    _add_correction(
        cards,
        "c2_mastery",
        "subjunctive and mandative structures",
        "The committee recommended that he is removed.",
        "The committee recommended that he be removed.",
        "After recommend/insist/require in formal English, use base verb in a that-clause.",
    )
    _add_production(
        cards,
        "c2_mastery",
        "nominalisation",
        "Make this more formal: The supplier did not comply, so the launch was delayed.",
        "The supplier's failure to comply delayed the launch.",
        "Nominalisation compresses a clause into a noun phrase for formal style.",
    )
    _add_expansion_cards(cards)
    return cards


GRAMMAR_CARDS = _build_grammar_cards()


def get_cards(level=None, card_type=None):
    wanted_types = None
    if card_type is not None:
        ct = card_type.strip().lower()
        if ct == "basic":
            wanted_types = {"rule", "contrast", "correction", "production", "choose", "pattern"}
        else:
            wanted_types = {ct}

    result = []
    for card in GRAMMAR_CARDS:
        if level is not None and card["level"] != level:
            continue
        if wanted_types is not None and card["card_type"] not in wanted_types:
            continue
        result.append({**card, "tags": list(card["tags"])})
    return result


def get_level_summary():
    return [
        {
            "id": level["id"],
            "name": level["name"],
            "goal": level["goal"],
            "topics": list(level["topics"]),
            "card_count": len([card for card in GRAMMAR_CARDS if card["level"] == level["id"]]),
        }
        for level in LEVELS
    ]


def _tag_string(tags):
    return " ".join(tags)


def render_basic_tsv(cards):
    header = ["#separator:tab", "#html:true"]
    rows = [
        [
            card["topic"],
            card["level"],
            card["card_type"],
            card["front"],
            card["back"],
            card.get("reason", ""),
            card.get("examples", ""),
            card.get("self_grade", ""),
            _tag_string(card["tags"]),
        ]
        for card in cards
    ]
    with io.StringIO() as output:
        writer = csv.writer(output, delimiter="\t", lineterminator="\n")
        for line in header:
            output.write(f"{line}\n")
        writer.writerow(["Topic", "Level", "CardType", "Front", "Answer", "Reason", "Examples", "SelfGrade", "Tags"])
        writer.writerows(rows)
        return output.getvalue()


def render_cloze_tsv(cards):
    header = ["#separator:tab", "#html:true"]
    with io.StringIO() as output:
        writer = csv.writer(output, delimiter="\t", lineterminator="\n")
        for line in header:
            output.write(f"{line}\n")
        writer.writerow(["Text", "Extra", "Tags"])
        return output.getvalue()


def write_import_files(output_dir="generated"):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    basic_path = output_path / "english_grammar_basic.tsv"
    cloze_path = output_path / "english_grammar_cloze.tsv"
    basic_path.write_text(render_basic_tsv(get_cards()), encoding="utf-8")
    cloze_path.write_text(render_cloze_tsv([]), encoding="utf-8")
    return str(basic_path), str(cloze_path)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Generate B2/C1/C2 English grammar maintenance deck TSV files.")
    parser.add_argument("--output-dir", default="generated/grammar", help="Output directory")
    parser.add_argument("--summary", action="store_true", help="Print level/card summary")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.summary:
        for item in get_level_summary():
            print(f"{item['id']}: {item['card_count']} cards")
        print(f"total: {len(get_cards())} cards")
        return 0
    paths = write_import_files(args.output_dir)
    print(f"Wrote basic import file: {paths[0]}")
    print(f"Wrote cloze import file: {paths[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
