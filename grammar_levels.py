import argparse
import csv
import io
import re
from pathlib import Path


LEVELS = [
    {
        "id": "level_1",
        "name": "Level 1 - Foundation",
        "goal": "Build automatic control of basic sentence structure.",
        "topics": [
            "be verbs",
            "simple present",
            "simple past",
            "basic questions",
            "plurals",
            "basic articles",
            "basic prepositions",
            "pronouns",
        ],
    },
    {
        "id": "level_2",
        "name": "Level 2 - Core Grammar",
        "goal": "Handle common everyday grammar choices accurately.",
        "topics": [
            "present continuous",
            "present perfect",
            "future forms",
            "comparatives",
            "countable and uncountable nouns",
            "common modals",
            "common preposition patterns",
        ],
    },
    {
        "id": "level_3",
        "name": "Level 3 - Intermediate Patterns",
        "goal": "Use sentence patterns needed for longer speech and writing.",
        "topics": [
            "conditionals",
            "passive voice",
            "relative clauses",
            "gerund vs infinitive",
            "reported speech",
            "phrasal verb grammar",
        ],
    },
    {
        "id": "level_4",
        "name": "Level 4 - Advanced Grammar",
        "goal": "Understand and produce more compressed advanced structures.",
        "topics": [
            "mixed conditionals",
            "inversion",
            "advanced modals",
            "participle clauses",
            "noun clauses",
            "emphasis structures",
            "reduced relative clauses",
        ],
    },
    {
        "id": "level_5",
        "name": "Level 5 - Fluency & Style",
        "goal": "Make grammar choices sound natural, precise, and connected.",
        "topics": [
            "sentence connectors",
            "formal grammar",
            "hedging",
            "modal nuance",
            "common learner mistakes",
            "style and register",
        ],
    },
]


def _topic_key(topic):
    return re.sub(r"[^a-z0-9]+", "_", topic.lower()).strip("_")


def _add_rule(cards, level, topic, front, back):
    cards.append(
        {
            "level": level,
            "topic": topic,
            "card_type": "rule",
            "front": front,
            "back": back,
            "tags": ["english_grammar", level, _topic_key(topic), "rule"],
        }
    )


def _add_cloze(cards, level, topic, text, extra):
    if "{{c1::" not in text:
        text = re.sub(r"\{c1::([^}]*)\}", r"{{c1::\1}}", text)
    cards.append(
        {
            "level": level,
            "topic": topic,
            "card_type": "cloze",
            "text": text,
            "extra": extra,
            "tags": ["english_grammar", level, _topic_key(topic), "cloze"],
        }
    )


def _add_correction(cards, level, topic, front, back):
    cards.append(
        {
            "level": level,
            "topic": topic,
            "card_type": "correction",
            "front": front,
            "back": back,
            "tags": ["english_grammar", level, _topic_key(topic), "correction"],
        }
    )


def _add_formula_cards(level, cards):
    formula_cards = [
        (
            "simple present",
            "Formula: present simple (affirmative)",
            "subject + V1; he/she/it uses V-s",
        ),
        (
            "present continuous",
            "Formula: present continuous",
            "am / is / are + V-ing",
        ),
        (
            "simple past",
            "Formula: past simple + past continuous in questions/negatives",
            "affirmative: subject + V2; question/negative: Did + subject + V1",
        ),
        (
            "past continuous",
            "Formula: past continuous",
            "was / were + V-ing",
        ),
        (
            "present perfect",
            "Formula: present perfect",
            "subject + have/has + V3",
        ),
        (
            "past perfect",
            "Formula: past perfect",
            "subject + had + V3",
        ),
        (
            "future tense",
            "Formula: future simple",
            "subject + will + V1",
        ),
        (
            "future forms",
            "Formula: going to future",
            "am / is / are + going to + V1",
        ),
        (
            "future perfect",
            "Formula: future perfect",
            "subject + will have + V3",
        ),
        (
            "passive voice",
            "Formula: passive",
            "be + V3",
        ),
        (
            "common modals",
            "Formula: modal (base form)",
            "modal + V1",
        ),
        (
            "common modals",
            "Formula: modal perfect",
            "modal + have + V3",
        ),
        (
            "conditionals",
            "Formula: zero conditional",
            "if + present simple, present simple",
        ),
        (
            "conditionals",
            "Formula: first conditional",
            "if + present simple, will + V1",
        ),
        (
            "conditionals",
            "Formula: second conditional",
            "if + V2, would + V1",
        ),
        (
            "conditionals",
            "Formula: third conditional",
            "if + had + V3, would have + V3",
        ),
    ]
    for topic, front, back in formula_cards:
        _add_rule(cards, level, topic, front, back)


def _be_form(subject):
    if subject == "I":
        return "am"
    if subject in {"He", "She", "It"}:
        return "is"
    return "are"


def _third_person_or_base(subject, base, third):
    return third if subject in {"He", "She", "It"} else base


def _present_have(subject):
    return "have" if subject.lower() in {"i", "you", "we", "they"} else "has"


def _pad_level_cards(level, cards, target=180):
    if len(cards) >= target:
        return

    level_info = next((entry for entry in LEVELS if entry["id"] == level), None)
    topics = level_info["topics"] if level_info else ["grammar"]
    subjects = ["I", "You", "He", "She", "We", "They"]
    actions = [
        ("prepare", "prepares", "prepared", "preparing", "the report"),
        ("review", "reviews", "reviewed", "reviewing", "the plan"),
        ("submit", "submits", "submitted", "submitting", "the form"),
        ("analyse", "analyses", "analysed", "analysing", "the data"),
        ("update", "updates", "updated", "updating", "the message"),
        ("build", "builds", "built", "building", "the prototype"),
        ("explain", "explains", "explained", "explaining", "the rule"),
        ("practice", "practices", "practised", "practising", "the skill"),
    ]

    while len(cards) < target:
        idx = len(cards)
        topic = topics[idx % len(topics)]
        subject = subjects[idx % len(subjects)]
        verb, verb_third, past, present_participle, obj = actions[idx % len(actions)]
        card_type = ["rule", "cloze", "correction"][idx % 3]

        if card_type == "rule":
            _add_rule(
                cards,
                level,
                topic,
                f"{subject} ____ {obj}.",
                _third_person_or_base(subject, verb, verb_third),
            )
        elif card_type == "cloze":
            be = _be_form(subject)
            _add_cloze(
                cards,
                level,
                topic,
                f"{subject} {be} {{c1::{present_participle}}} {obj} this quarter.",
                "Use a correct auxiliary/verb form in context.",
            )
        else:
            _add_correction(
                cards,
                level,
                topic,
                f"Correct: {subject} {verb} {obj} yesterday.",
                f"{subject} {past} {obj} yesterday.",
            )


def _build_level_1_cards():
    level = "level_1"
    cards = []
    subjects = ["I", "You", "He", "She", "It", "We", "They"]
    be_states = ["a student", "a teacher", "in the office", "ready", "on time", "at home", "very busy"]

    for subject in subjects:
        for state in be_states:
            _add_rule(cards, level, "be verbs", f"{subject} _____ {state}.", _be_form(subject))

    present_actions = [
        ("work", "works", "from home"),
        ("start", "starts", "at 9 AM"),
        ("watch", "watches", "documentaries"),
        ("need", "needs", "support"),
        ("visit", "visits", "the museum"),
        ("prepare", "prepares", "slides"),
        ("finish", "finishes", "on time"),
    ]
    for subject in subjects:
        for base, third, context in present_actions:
            _add_rule(
                cards,
                level,
                "simple present",
                f"{subject} _____ {context} every day.",
                _third_person_or_base(subject, base, third),
            )

    past_actions = [
        ("go", "went", "to school"),
        ("take", "took", "the train"),
        ("see", "saw", "the presentation"),
        ("eat", "ate", "breakfast"),
        ("buy", "bought", "a notebook"),
        ("write", "wrote", "a short note"),
        ("find", "found", "a simple solution"),
    ]
    for subject in subjects:
        for _, past, context in past_actions:
            _add_rule(cards, level, "simple past", f"{subject} _____ {context} yesterday.", past)

    question_pairs = [
        ("She likes coffee", "Does she like coffee?"),
        ("You speak clearly", "Do you speak clearly?"),
        ("He visits the office", "Does he visit the office?"),
        ("They are ready", "Are they ready?"),
        ("It works today", "Does it work today?"),
        ("We need time", "Do we need time?"),
        ("Your friends like music", "Do your friends like music?"),
        ("My brother plays guitar", "Does my brother play guitar?"),
    ]
    for statement, question in question_pairs:
        _add_rule(cards, level, "basic questions", f"Correct question order: {statement}", question)

    article_rows = [
        ("apple", "a"),
        ("umbrella", "an"),
        ("hour", "an"),
        ("idea", "an"),
        ("euro", "a"),
        ("honest person", "an"),
        ("university", "a"),
        ("orange", "an"),
        ("cat", "a"),
        ("e-mail", "an"),
        ("engineer", "an"),
        ("house", "a"),
        ("elephant", "an"),
        ("one-way", "a"),
        ("honour", "an"),
        ("university", "a"),
    ]
    for noun, article in article_rows:
        _add_rule(cards, level, "basic articles", f"Choose article: ___ {noun}", article)

    plural_rows = [
        ("The room contains", "cats"),
        ("In our archive,", "documents"),
        ("The dashboard shows", "errors"),
        ("On the shelves, the team logged", "tickets"),
        ("The warehouse now has", "samples"),
        ("Our clients reviewed", "proposals"),
        ("During the audit, we tracked", "responses"),
        ("Security analysts confirmed", "incidents"),
        ("The report listed", "recommendations"),
        ("Managers requested", "updates"),
        ("The committee received", "complaints"),
        ("Customers submitted", "reviews"),
    ]
    for stem, plural in plural_rows:
        _add_cloze(
            cards,
            level,
            "plurals",
            f"{stem} {{c1::{plural}}}.",
            "Use plural noun when more than one is present.",
        )

    prepositions = [
        ("on", "The book is ___ the table."),
        ("in", "The cat is ___ the box."),
        ("under", "The notebook is ___ the desk."),
        ("between", "The chair is ___ the sofa and the table."),
        ("with", "I walked ___ my friend."),
        ("at", "We met ___ noon."),
        ("on", "The meeting starts ___ Monday."),
        ("in", "She lives ___ London."),
        ("for", "This guide is for students."),
        ("to", "We go ___ the office at 8.")
    ]
    for prep, sentence in prepositions:
        _add_rule(cards, level, "basic prepositions", f"Choose preposition: {sentence}", prep)
    preposition_clozes = [
        "They arrived at the station and sat {{c1::on}} the bench.",
        "The keys were found {{c1::under}} the table.",
        "The bus stopped {{c1::between}} the buildings and moved on.",
        "The book is lying {{c1::with}} the documents.",
    ]
    for sentence in preposition_clozes:
        _add_cloze(
            cards,
            level,
            "basic prepositions",
            sentence,
            "Choose one preposition that makes this sentence correct.",
        )

    pronoun_rows = [
        ("I", "you", "my"),
        ("You", "I", "your"),
        ("He", "she", "his"),
        ("She", "we", "her"),
        ("We", "they", "our"),
        ("They", "he", "their"),
        ("It", "we", "its"),
    ]
    for subject, companion, possessive in pronoun_rows:
        _add_rule(
            cards,
            level,
            "pronouns",
            f"{subject} handed in ____ document.",
            possessive,
        )
        _add_cloze(
            cards,
            level,
            "pronouns",
            f"{{c1::{subject}}} and {companion} are in the meeting.",
            "Use personal pronouns in subject position.",
        )

    correction_rows = [
        ("She don't like tea.", "She doesn't like tea."),
        ("He don't live here.", "He doesn't live here."),
        ("They is going now.", "They are going now."),
        ("I doesn't have time.", "I don't have time."),
        ("She are my friend.", "She is my friend."),
        ("There is many dogs.", "There are many dogs."),
        ("An apple is red.", "An apple is red."),
        ("He don't know.", "He doesn't know."),
        ("She is very usefuls.", "She is very useful."),
        ("They has finished.", "They have finished."),
        ("I am happy because she are here.", "I am happy because she is here."),
        ("There are too much water.", "There is too much water."),
        ("He need to wait.", "He needs to wait."),
        ("She can to drive now.", "She can drive now."),
        ("You was late.", "You were late."),
        ("It rains yesterday.", "It rained yesterday."),
        ("He don't likes games.", "He doesn't like games."),
        ("They was coming.", "They were coming."),
    ]
    for wrong, right in correction_rows:
        _add_correction(cards, level, "basic forms", f"Correct the sentence: {wrong}", right)

    return cards


def _build_level_2_cards():
    level = "level_2"
    cards = []
    subjects = ["I", "You", "He", "She", "We", "They", "It"]

    _add_formula_cards(level, cards)

    continuous_examples = [
        ("I", "am", "reading", "a book", "right now."),
        ("You", "are", "waiting", "for confirmation", "right now."),
        ("She", "is", "working", "on the project", "right now."),
        ("He", "is", "studying", "for the interview", "at the moment."),
        ("We", "are", "preparing", "the release notes", "currently."),
        ("They", "are", "using", "the new tool", "now."),
    ]
    for subject, aux, verb, obj, time_expr in continuous_examples:
        _add_rule(
            cards,
            level,
            "present continuous",
            f"{subject} _____ {verb} {obj} {time_expr}",
            f"{aux} {verb} {obj} {time_expr}",
        )
        _add_cloze(
            cards,
            level,
            "present continuous",
            f"{subject} {aux} {{c1::{verb}}} {obj} {time_expr}",
            "Use be + verb+ing for present continuous.",
        )

    perfect_examples = [
        ("I", "have", "already", "finished", "the proposal."),
        ("She", "has", "recently", "reviewed", "the pull request."),
        ("We", "have", "just", "started", "the deployment."),
        ("They", "have", "never", "missed", "a weekly status update."),
        ("He", "has", "so far", "completed", "all pre-release checks."),
        ("I", "have", "", "visited", "a production outage review before."),
    ]
    for subject, aux, adverb, verb, obj in perfect_examples:
        auxiliary = aux
        _add_rule(
            cards,
            level,
            "present perfect",
            f"{subject} _____ {adverb + ' ' if adverb else ''}{verb} {obj}",
            f"{auxiliary} {adverb + ' ' if adverb else ''}{verb} {obj}",
        )
        _add_cloze(
            cards,
            level,
            "present perfect",
            f"{subject} {auxiliary} {adverb + ' ' if adverb else ''}{{c1::{verb}}} {obj}".replace("  ", " "),
            "Use have/has + past participle.",
        )

    _add_rule(
        cards,
        level,
        "present perfect",
        "Has _____ ever reported a critical issue?",
        "has ever reported",
    )
    _add_cloze(
        cards,
        level,
        "present perfect",
        "Has the lead engineer ever {{c1::reported}} a critical issue?",
        "Use present perfect in questions.",
    )

    _add_cloze(
        cards,
        level,
        "present perfect",
        "The release candidate {{c1::has passed}} QA already.",
        "Use have/has + V3 in present perfect with recent events.",
    )
    _add_correction(
        cards,
        level,
        "present perfect",
        "Correct: The team has ate the final tests.",
        "The team has eaten the final tests.",
    )
    _add_cloze(
        cards,
        level,
        "past perfect",
        "Before the server migration, the database {{c1::had been backed}} up.",
        "Use had + V3 for action before another past action.",
    )
    _add_correction(
        cards,
        level,
        "past perfect",
        "Correct: By the time the report arrived, we had review it.",
        "By the time the report arrived, we had reviewed it.",
    )
    _add_cloze(
        cards,
        level,
        "passive voice",
        "The incident report {{c1::was validated}} by the platform team.",
        "Passive: be + V3, not active subject-verb order.",
    )
    _add_correction(
        cards,
        level,
        "passive voice",
        "Correct: The proposal was approved by the board.",
        "The proposal was approved by the board.",
    )
    _add_cloze(
        cards,
        level,
        "common modals",
        "The architect {{c1::should have checked}} the risk register.",
        "Use modal perfect: modal + have + V3.",
    )
    _add_correction(
        cards,
        level,
        "common modals",
        "Correct: She should called the supplier immediately.",
        "She should have called the supplier immediately.",
    )

    future_data = [
        ("will start", "the session"),
        ("will finish", "the draft"),
        ("will arrive", "at 9 PM"),
        ("will join", "the project"),
        ("will review", "your notes"),
        ("will travel", "to the office"),
    ]
    for subject in subjects:
        for verb, obj in future_data:
            _add_rule(cards, level, "future forms", f"{subject} {verb} {obj} tomorrow.", f"{subject} {verb} {obj} tomorrow.")
            _add_cloze(cards, level, "future forms", f"{subject} {{c1::will}} {verb.split()[1] if verb.startswith('will') else verb} {obj} tomorrow.", "Future with will.")

    comparatives = [
        ("easy", "easier", "easiest"),
        ("hard", "harder", "hardest"),
        ("useful", "more useful", "most useful"),
        ("careful", "more careful", "most careful"),
        ("tall", "taller", "tallest"),
        ("good", "better", "best"),
        ("bad", "worse", "worst"),
        ("clear", "clearer", "clearest"),
    ]
    for base, comp, superl in comparatives:
        _add_rule(cards, level, "comparatives", f"This book is ___ than that one.", comp)
        _add_cloze(cards, level, "comparatives", f"This plan is {{c1::{comp}}} than the previous one.", f"Use comparative form of {base}.")
        _add_correction(
            cards,
            level,
            "comparatives",
            f"Correct: This route is more easiest than that one.",
            f"This route is {comp} than that one, close to the {superl} option.",
        )

    countable = [
        ("There is ___ useful information in the report.", "much"),
        ("The dashboard listed ___ issues from last week.", "many"),
        ("Can you share ___ practical advice with the analyst?", "some"),
        ("She added ___ examples to the minutes.", "a few"),
        ("We have ___ time left before the close.", "a little"),
        ("The release has ___ errors than the beta version.", "fewer"),
        ("The model used ___ power than the baseline.", "less"),
    ]
    for sentence, quantity in countable:
        _add_rule(
            cards,
            level,
            "countable and uncountable nouns",
            sentence,
            quantity,
        )
        _add_cloze(
            cards,
            level,
            "countable and uncountable nouns",
            sentence.replace("___", f"{{c1::{quantity}}}"),
            "Use quantity carefully with noun type.",
        )

    modal_examples = [
        ("must", "complete the form today"),
        ("can", "access the archived files"),
        ("should", "review the test results"),
        ("might", "need an additional patch"),
        ("need to", "ask security for approval"),
    ]
    for modal, rest in modal_examples:
        _add_rule(cards, level, "common modals", f"You _____ {rest}.", modal)
        _add_cloze(
            cards,
            level,
            "common modals",
            f"You {{c1::{modal}}} {rest}.",
            "Modal choice in context.",
        )
    for wrong, right in [
        ("She can to drive now.", "She can drive now."),
        ("You should to call her.", "You should call her."),
        ("He must to finish it.", "He must finish it."),
        ("They can goes now.", "They can go now."),
        ("She might of told me.", "She might have told me."),
    ]:
        _add_correction(cards, level, "common modals", f"Correct the sentence: {wrong}", right)

    preposition_patterns = [
        ("at", "The train arrives ___ the station."),
        ("on", "The team arrives ___ time for meetings."),
        ("in", "She is interested ___ robotics."),
        ("on", "The result depends ___ the data quality."),
        ("for", "He is responsible ___ the final release."),
        ("at", "He is good ___ coding."),
        ("of", "They are afraid ___ public speaking."),
        ("to", "This design is similar ___ the prototype."),
    ]
    for prep, frame in preposition_patterns:
        _add_rule(cards, level, "common preposition patterns", f"Complete: {frame}", prep)
        _add_cloze(
            cards,
            level,
            "common preposition patterns",
            frame.replace("___", f"{{c1::{prep}}}"),
            "Common preposition choice.",
        )

    _pad_level_cards(level, cards, target=200)
    return cards


def _build_level_3_cards():
    level = "level_3"
    cards = []
    subjects = ["I", "you", "he", "she", "we", "they", "it"]
    if_subjects = ["she", "he", "they", "we", "I", "you"]

    first_conditionals = [
        ("If you study", "we", "pass the exam"),
        ("If it rains", "the event", "be postponed"),
        ("If she arrives", "she", "join the meeting"),
        ("If we start", "we", "receive support"),
        ("If he calls", "he", "be credited"),
        ("If they continue", "they", "improve"),
    ]
    for prefix, result_subject, result_phrase in first_conditionals:
        _add_rule(
            cards,
            level,
            "conditionals",
            f"{prefix}, {result_subject} will {result_phrase}.",
            "Present condition + future result",
        )
        _add_cloze(
            cards,
            level,
            "conditionals",
            f"{prefix}, {result_subject} {{c1::will}} {result_phrase}.",
            "Use first conditional with present + will.",
        )

    second_conditionals = [
        ("If I were in charge", "I", "take ownership"),
        ("If she spoke clearly", "we", "trust her answer"),
        ("If they trained", "they", "solve it"),
        ("If we had more time", "we", "finish the draft"),
    ]
    for prefix, result_subject, result_phrase in second_conditionals:
        _add_rule(
            cards,
            level,
            "conditionals",
            f"{prefix}, {result_subject} would {result_phrase}.",
            "Second conditional pattern",
        )
        _add_cloze(
            cards,
            level,
            "conditionals",
            f"{prefix}, {result_subject} {{c1::would}} {result_phrase}.",
            "Use if + past simple, would + base.",
        )

    third_conditionals = [
        ("If you had studied", "we", "passed"),
        ("If they had checked", "the team", "fixed the issue"),
        ("If she had started", "she", "been ready"),
    ]
    for prefix, result_subject, result_phrase in third_conditionals:
        _add_rule(
            cards,
            level,
            "conditionals",
            f"{prefix}, {result_subject} would have {result_phrase}.",
            "Third conditional pattern",
        )
        _add_cloze(
            cards,
            level,
            "conditionals",
            f"{prefix}, {result_subject} {{c1::would have}} {result_phrase}.",
            "Use if + past perfect, would have + past participle.",
        )

    passive_subject_verbs = [
        ("The report", "was approved"),
        ("The files", "were approved"),
        ("The team", "was prepared"),
        ("The project", "was launched"),
        ("The letters", "were sent"),
        ("The door", "was closed"),
        ("The meetings", "were postponed"),
    ]
    objects = ["on Monday", "yesterday", "in this room", "by the manager", "before noon", "with care"]
    for subj, verb in passive_subject_verbs:
        for verb in [verb]:
            for obj in objects[:2]:
                _add_rule(cards, level, "passive voice", f"{subj} _____ {obj}.", verb)
                _add_cloze(cards, level, "passive voice", f"{subj} {{c1::{verb}}} {obj}.", "Use passive construction.")

    relative_examples = [
        ("The engineer _____ fixed the bug explained the cause.", "who"),
        ("The file _____ you sent yesterday is corrupted.", "that"),
        ("The office _____ we met is closed today.", "where"),
        ("Monday was the day _____ the audit started.", "when"),
        ("That is the reason _____ the server failed.", "why"),
        ("The tool _____ we use for testing is reliable.", "which"),
        ("The candidate _____ resume impressed us accepted the offer.", "whose"),
        ("The client _____ I called this morning answered quickly.", "whom"),
    ]
    for sentence, answer in relative_examples:
        _add_rule(cards, level, "relative clauses", sentence, answer)
        _add_cloze(
            cards,
            level,
            "relative clauses",
            sentence.replace("_____", f"{{c1::{answer}}}"),
            "Choose the relative word that fits the noun and context.",
        )

    gi_examples = [
        ("I enjoy _____ quiet work in the morning.", "doing"),
        ("She avoids _____ late at night.", "eating"),
        ("They decided _____ the meeting early.", "to leave"),
        ("He managed _____ the report before noon.", "to finish"),
        ("We promised _____ the client tomorrow.", "to call"),
        ("She refused _____ the document without review.", "to sign"),
        ("He stopped _____ sugar in his coffee.", "using"),
        ("I remember _____ that email yesterday.", "sending"),
        ("They suggested _____ the plan again.", "reviewing"),
        ("We hope _____ the issue today.", "to solve"),
        ("She offered _____ with the migration.", "to help"),
        ("He admitted _____ the mistake.", "making"),
    ]
    for sentence, answer in gi_examples:
        _add_rule(cards, level, "gerund vs infinitive", sentence, answer)
        _add_cloze(
            cards,
            level,
            "gerund vs infinitive",
            sentence.replace("_____", f"{{c1::{answer}}}"),
            "Some verbs take a gerund and others take an infinitive.",
        )

    report_verbs = [
        ("I said", "I was"),
        ("She said", "she was"),
        ("They said", "they were"),
        ("He said", "he was"),
        ("The manager said", "the manager said"),
    ]
    for intro, verb in report_verbs:
        _add_rule(cards, level, "reported speech", f"{intro} that he would arrive late.", f"{verb} would arrive late.")
        _add_cloze(cards, level, "reported speech", f"{intro} that she {{c1::was}} already there.", "Backshift in reported speech.")
        _add_correction(
            cards,
            level,
            "reported speech",
            f"Correct: She said that she is coming tomorrow.",
            "She said that she was coming the next day.",
        )

    phrasal_examples = [
        ("Please carry _____ with the work.", "on"),
        ("She turned _____ the offer politely.", "down"),
        ("We are looking _____ the missing file.", "for"),
        ("They set _____ the new account yesterday.", "up"),
        ("I ran _____ an old colleague downtown.", "into"),
        ("He gave _____ smoking last year.", "up"),
        ("The policy brought _____ several changes.", "about"),
        ("We worked _____ the problem together.", "through"),
        ("Can you fill _____ this form?", "out"),
        ("The meeting was called _____ because of snow.", "off"),
    ]
    for sentence, answer in phrasal_examples:
        _add_rule(cards, level, "phrasal verb grammar", sentence, answer)
        _add_cloze(
            cards,
            level,
            "phrasal verb grammar",
            sentence.replace("_____", f"{{c1::{answer}}}"),
            "Choose the particle that completes the phrasal verb.",
        )

    _pad_level_cards(level, cards, target=200)
    return cards


def _build_level_4_cards():
    level = "level_4"
    cards = []
    subjects = ["I", "you", "he", "she", "we", "they", "it"]

    mixed = [
        ("If she had studied", "she would now be accepted"),
        ("If he had worked", "he would have arrived"),
        ("If we had left", "we would be ahead"),
        ("If I had known", "I would have told you"),
        ("If they had practiced", "they would be confident"),
    ]
    for clause, result in mixed:
        _add_rule(cards, level, "mixed conditionals", f"{clause}, {result}.", "mixed conditional")
        _add_cloze(
            cards,
            level,
            "mixed conditionals",
            f"{clause}, {{c1::{result}}}.",
            "Use had + past participle with could/would have.",
        )

    inversion_starts = [
        ("Never", "have", "I", "seen"),
        ("Rarely", "do", "they", "understand"),
        ("Not until", "did", "we", "finish"),
        ("Only after", "had", "she", "realized"),
        ("Never", "have", "we", "forgotten"),
        ("Seldom", "did", "I", "misjudge"),
    ]
    for adv, aux, subject, verb in inversion_starts:
        _add_rule(cards, level, "inversion", f"{adv} {aux} {subject} {verb} this report before.", "Use inversion with negative adjunct")
        _add_cloze(cards, level, "inversion", f"{adv} {{c1::{aux}}} {subject} {verb} this report before.", "Inversion form.")
        _add_correction(cards, level, "inversion", f"Correct: {adv} {subject} {verb} this report.", f"{adv} {aux} {subject} {verb} this report before.")

    advanced_modals = [
        ("She", "might have", "missed"),
        ("They", "could have", "finished"),
        ("He", "should have", "called"),
        ("We", "must have", "forgotten"),
        ("You", "may have", "received"),
        ("It", "might have", "changed"),
    ]
    for subject, modal, verb in advanced_modals:
        _add_rule(cards, level, "advanced modals", f"{subject} {modal} {verb} the deadline.", f"{modal} {verb} the deadline")
        _add_cloze(cards, level, "advanced modals", f"{subject} {{c1::{modal.split()[0]}}} have {verb} the deadline.", "Modal + perfect form.")
        _add_correction(cards, level, "advanced modals", f"Correct: {subject} {modal} of finished it.", f"{subject} {modal} have finished it.")

    participles = [
        ("Having prepared", "the draft"),
        ("Knowing", "the procedure"),
        ("Being", "prepared"),
        ("Having discussed", "the issue"),
        ("Working", "with precision"),
    ]
    tails = ["they submitted the report.", "we moved to the next task.", "she avoided mistakes.", "the team approved it.", "the manager spoke clearly."]
    for clause, noun in participles:
        for tail in tails:
            _add_rule(cards, level, "participle clauses", f"{clause} {noun}, {tail}", "participle")
            _add_cloze(cards, level, "participle clauses", f"{clause} {{c1::{noun}}}, {tail}", "Use reduced participle clause.")

    noun_clause_examples = [
        ("I know what she said.", "what she said"),
        ("We discussed whether they agreed.", "whether they agreed"),
        ("The report shows why the system failed.", "why the system failed"),
        ("I wonder if the team understands.", "if the team understands"),
        ("She explained how the script worked.", "how the script worked"),
        ("We asked where the test data came from.", "where the test data came from"),
        ("They confirmed what the team needed.", "what the team needed"),
    ]
    for sentence, clause in noun_clause_examples:
        _add_rule(
            cards,
            level,
            "noun clauses",
            f"Complete the sentence: {sentence}",
            "noun clause",
        )
        _add_cloze(
            cards,
            level,
            "noun clauses",
            sentence.replace(clause, f"{{c1::{clause}}}"),
            "Use a complete noun-clause expression.",
        )

    emphasis_examples = [
        ("It was the analyst who found the bug first.", "the analyst"),
        ("What the team needed most was stable input.", "stable input"),
        ("It was during the planning meeting that we set the deadline.", "during the planning meeting"),
        ("What they wanted most was a clear timeline.", "a clear timeline"),
        ("It was your report that convinced the committee.", "your report"),
        ("What the client asked for was a quick fix.", "a quick fix"),
    ]
    for sentence, focused in emphasis_examples:
        _add_rule(cards, level, "emphasis structures", sentence, "emphasis structure")
        _add_cloze(
            cards,
            level,
            "emphasis structures",
            sentence.replace(focused, f"{{c1::{focused}}}"),
            "Use emphasis for focus and contrast.",
        )

    reduced_relative_examples = [
        ("Having completed the security review", "the team signed off on production access."),
        ("Having fixed the regression bug", "the release passed smoke testing."),
        ("Having secured stakeholder approval", "the team started the rollout."),
        ("Having reviewed the client notes", "we revised the final draft."),
        ("Having collected user feedback", "the roadmap changed immediately."),
        ("Having updated the schedule", "the launch date shifted by one week."),
        ("Having closed the budget gap", "the vendor accepted the contract."),
        ("Having validated the migration", "we moved traffic to the new cluster."),
    ]
    for prefix, tail in reduced_relative_examples:
        sentence = f"{prefix}, {tail}"
        _add_rule(cards, level, "reduced relative clauses", sentence, "reduced clause")
        _add_correction(cards, level, "reduced relative clauses", f"Correct: {sentence}", sentence)
        _add_cloze(
            cards,
            level,
            "reduced relative clauses",
            f"{{c1::{prefix}}}, {tail}",
            "Use a reduced relative/adverbial clause.",
        )

    return cards


def _build_level_5_cards():
    level = "level_5"
    cards = []

    connectors = [
        ("however", "contrast"),
        ("moreover", "addition"),
        ("nevertheless", "concession"),
        ("therefore", "result"),
        ("although", "contrast"),
        ("because", "reason"),
        ("furthermore", "addition"),
    ]
    connector_statements = {
        "however": [
            ("The prototype looked stable, {{c1::however}}, the deployment still crashed under peak load."),
            ("The report was complete, {{c1::however}}, two risks remained unresolved."),
        ],
        "moreover": [
            ("The API is now faster, {{c1::moreover}}, error responses are clearer."),
            ("The app supports two languages, {{c1::moreover}}, accessibility updates were added."),
        ],
        "nevertheless": [
            ("The schedule was tight, {{c1::nevertheless}}, the quality bar did not drop."),
            ("The sprint started late, {{c1::nevertheless}}, we met every milestone."),
        ],
        "therefore": [
            ("The security scan found no issues, {{c1::therefore}}, we approved the release."),
            ("The team repeated the regression tests, {{c1::therefore}}, the defect rate improved."),
        ],
        "although": [
            ("{{c1::Although}} the budget was reduced, the team delivered all milestones."),
            ("{{c1::Although}} the feature was delayed, the quality improved."),
        ],
        "because": [
            ("{{c1::Because}} the data was inconsistent, the model stayed in training mode."),
            ("{{c1::Because}} the team had a new lead, the project accelerated."),
        ],
        "furthermore": [
            ("The monitoring logs are clearer, {{c1::furthermore}}, rollback is now faster."),
            ("The app is faster, {{c1::furthermore}}, support response times are lower."),
        ],
    }
    for connector, role in connectors:
        _add_rule(
            cards,
            level,
            "sentence connectors",
            f"Use '{connector}' for {role}.",
            connector,
        )
        for sentence in connector_statements[connector]:
            _add_cloze(cards, level, "sentence connectors", sentence, f"Use {connector} as a logical connector.")

    formal_pairs = [
        "Could you please share the figures?",
        "It appears that the report is ready.",
        "Please ensure the file is complete.",
        "The committee approved the proposal.",
        "The meeting was rescheduled due to travel delays.",
        "Please verify that all citations are up to date.",
        "The board will review the final proposal tomorrow.",
        "Kindly submit your final comments by close of business.",
        "The committee formally confirmed the revised milestones.",
    ]
    for sentence in formal_pairs:
        _add_rule(cards, level, "formal grammar", f"Rewrite formally: {sentence}", sentence)
        _add_cloze(cards, level, "formal grammar", f"{{c1::{sentence}}}", "Maintain formal style and precision.")

    hedges = [
        ("The timeline may shift unexpectedly.", "may"),
        ("The results might improve next quarter.", "might"),
        ("We may not be fully staffed this week.", "may"),
        ("Perhaps we should review this again.", "Perhaps"),
        ("This seems potentially useful.", "seems"),
        ("This is likely to be delayed.", "likely"),
        ("This may not be feasible without extra testing.", "may"),
        ("This strategy could be the best option.", "could"),
        ("The requirements may change during implementation.", "may"),
        ("The change might not be permanent.", "might"),
    ]
    for sentence, hedge in hedges:
        _add_rule(cards, level, "hedging", f"Add hedging language: {sentence}", hedge)
        _add_cloze(cards, level, "hedging", sentence.replace(hedge, f"{{c1::{hedge}}}"), "Use hedging to soften claims.")

    modal_nuances = [
        ("She seems to need more data.", "seems"),
        ("It appears to need follow-up.", "appears"),
        ("The draft may be revised in phase two.", "may"),
        ("We could use additional QA.", "could"),
        ("The team might need further validation.", "might"),
        ("This plan should be reviewed for scope.", "should"),
        ("The timeline should stay stable.", "should"),
        ("The dataset might need another split.", "might"),
        ("The client could approve this next month.", "could"),
        ("The interface seems to need simplification.", "seems"),
        ("The estimate may be adjusted soon.", "may"),
    ]
    for subject, token in modal_nuances:
        _add_rule(cards, level, "modal nuance", f"{subject}", token)
        _add_cloze(cards, level, "modal nuance", subject.replace(token, f"{{c1::{token}}}"), "Choose subtle modal.")
        _add_correction(cards, level, "modal nuance", f"Correct: {subject}", f"{subject}")

    mistakes = [
        ("I am used to used to go.", "I am used to going."),
        ("Between you and I, this was hard.", "Between you and me, this was hard."),
        ("She explained me the details.", "She explained the details to me."),
        ("He suggested me to stay.", "He suggested that I stay."),
        ("The data is reliable", "The data are reliable"),
        ("He gave me advise.", "He gave me advice."),
        ("She said me to leave.", "She told me to leave."),
        ("The less I see it, the less I likes it.", "The less I see it, the less I like it."),
        ("I explained him the decision.", "I explained the decision to him."),
        ("Between Bob and I, we discussed the plan.", "Between Bob and me, we discussed the plan."),
        ("She suggested me the report.", "She suggested the report to me."),
    ]
    for wrong, right in mistakes:
        _add_correction(cards, level, "common learner mistakes", f"Correct this: {wrong}", right)

    style_rows = [
        ("The policy is likely to be revised.", "formal", "Therefore, we postponed publication."),
        ("The result seems clear.", "academic", "However, further validation is still required."),
        ("He might not be fully certain.", "cautious", "Therefore, we should avoid a definitive claim."),
        ("The method was considered robust.", "technical", "Moreover, it performed well under load."),
        ("The team had substantial concerns.", "formal", "Therefore, the release was delayed."),
        ("The model performed below expectations.", "academic", "Consequently, we revised the training data."),
        ("The report contained incomplete metadata.", "technical", "Therefore, we delayed publication."),
        ("The schedule was adjusted again.", "formal", "As a result, the client was notified."),
        ("The dashboard showed stable error rates.", "technical", "Nevertheless, we continued monitoring."),
        ("The release was delayed by one week.", "formal", "Consequently, the announcement was updated."),
    ]
    for sentence, tone, followup in style_rows:
        _add_rule(cards, level, "style and register", f"Rewrite for a {tone} register: {sentence}", sentence)
        _add_cloze(
            cards,
            level,
            "style and register",
            f"{sentence} {{c1::{followup}}}",
            "Choose a register-aware follow-up sentence.",
        )
    return cards


def _build_grammar_cards():
    cards = []
    cards.extend(_build_level_1_cards())
    cards.extend(_build_level_2_cards())
    cards.extend(_build_level_3_cards())
    cards.extend(_build_level_4_cards())
    cards.extend(_build_level_5_cards())
    return cards


GRAMMAR_CARDS = _build_grammar_cards()


def get_cards(level=None, card_type=None):
    """Return cards filtered by optional level id and/or card type."""
    wanted_types = None
    if card_type is not None:
        ct = card_type.strip().lower()
        if ct == "basic":
            wanted_types = {"rule", "correction"}
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
    """Return one summary row per level with card count."""
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
    """Render Rule/Correction cards (basic note type) as Anki import TSV."""
    header = ["#separator:tab", "#html:true"]
    basic_rows = [
        [card["front"], card["back"], _tag_string(card["tags"])]
        for card in cards
        if card["card_type"] in {"rule", "correction"}
    ]
    with io.StringIO() as output:
        writer = csv.writer(output, delimiter="\t", lineterminator="\n")
        for line in header:
            output.write(f"{line}\n")
        writer.writerow(["Front", "Back", "Tags"])
        writer.writerows(basic_rows)
        return output.getvalue()


def render_cloze_tsv(cards):
    """Render Cloze cards as Anki import TSV."""
    header = ["#separator:tab", "#html:true"]
    cloze_rows = [
        [card["text"], card.get("extra", ""), _tag_string(card["tags"])]
        for card in cards
        if card["card_type"] == "cloze"
    ]
    with io.StringIO() as output:
        writer = csv.writer(output, delimiter="\t", lineterminator="\n")
        for line in header:
            output.write(f"{line}\n")
        writer.writerow(["Text", "Extra", "Tags"])
        writer.writerows(cloze_rows)
        return output.getvalue()


def write_import_files(output_dir="generated"):
    """Write both Basic and Cloze TSV files to the output directory."""
    cards = get_cards()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    basic_path = output_path / "english_grammar_basic.tsv"
    cloze_path = output_path / "english_grammar_cloze.tsv"

    basic_tsv = render_basic_tsv(cards)
    cloze_tsv = render_cloze_tsv(cards)

    basic_path.write_text(basic_tsv, encoding="utf-8")
    cloze_path.write_text(cloze_tsv, encoding="utf-8")
    return (str(basic_path), str(cloze_path))


def main():
    parser = argparse.ArgumentParser(description="Generate English Grammar starter TSV decks")
    parser.add_argument("--level", choices=[level["id"] for level in LEVELS], help="Generate cards for only this level")
    parser.add_argument("--summary", action="store_true", help="Print concise summary per level")
    parser.add_argument(
        "--output-dir",
        default="generated",
        help="Directory where TSV files are written (default: generated)",
    )

    args = parser.parse_args()

    if args.summary:
        for summary in get_level_summary():
            print(f"{summary['id']}: {summary['card_count']} cards")
        return

    filtered_cards = get_cards(level=args.level)
    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    basic_path = output_path / "english_grammar_basic.tsv"
    cloze_path = output_path / "english_grammar_cloze.tsv"

    basic_tsv = render_basic_tsv(filtered_cards)
    cloze_tsv = render_cloze_tsv(filtered_cards)
    basic_path.write_text(basic_tsv, encoding="utf-8")
    cloze_path.write_text(cloze_tsv, encoding="utf-8")
    return (str(basic_path), str(cloze_path))


if __name__ == "__main__":
    main()
