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
    return cards


GRAMMAR_CARDS = _build_grammar_cards()


def get_cards(level=None, card_type=None):
    wanted_types = None
    if card_type is not None:
        ct = card_type.strip().lower()
        if ct == "basic":
            wanted_types = {"rule", "contrast", "correction", "production"}
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
