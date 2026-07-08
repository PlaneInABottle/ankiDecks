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


def _choose_back(correct, grammar_name, formula, reason, examples):
    return (
        f"<b>Correct</b><br>{correct}<br><br>"
        f"<b>Grammar</b><br>{grammar_name}<br><br>"
        f"<b>Formula</b><br>{formula}<br><br>"
        f"<b>Reason</b><br>{reason}<br><br>"
        f"<b>Examples</b><br>- {examples[0]}<br>- {examples[1]}<br><br>"
        f"<b>Self-Grade</b><br>{_self_grade('choose')}"
    )


def _add_choose(cards, level, topic, front, correct, grammar_name, formula, reason, examples):
    _add(
        cards,
        level,
        topic,
        "choose",
        front,
        _choose_back(correct, grammar_name, formula, reason, examples),
    )


def _build_choose_only_grammar_cards():
    cards = []
    topic_map = {
        "b2_tense_system": {
            "present perfect vs past simple": [
                (
                    "Choose: I _____ in London since 2018.<br>A) lived<br>B) have lived",
                    "B) I have lived in London since 2018.",
                    "Present perfect vs past simple",
                    "have/has + V3 / V2",
                    "since + unfinished period stays open, so present perfect.",
                    [
                        "I have lived in London since 2018.",
                        "I lived in London for a year in 2018.",
                    ],
                ),
                (
                    "Choose: She _____ this position last year.<br>A) took<br>B) has taken",
                    "A) She took this position last year.",
                    "Present perfect vs past simple",
                    "V2 for finished, bounded time",
                    "last year closes the period, so past simple.",
                    [
                        "She took this position last year.",
                        "She has taken new responsibilities.",
                    ],
                ),
                (
                    "Choose: We _____ three versions already this week.<br>A) have reviewed<br>B) reviewed",
                    "A) We have reviewed three versions already this week.",
                    "Present perfect vs past simple",
                    "have/has + V3 with for/since",
                    "with this week as open window, present perfect is preferred.",
                    [
                        "We have reviewed three versions this week.",
                        "We reviewed three versions yesterday.",
                    ],
                ),
            ],
            "present perfect continuous": [
                (
                    "Choose: I _____ preparing for this meeting for two hours.<br>A) have been<br>B) was",
                    "A) I have been preparing for this meeting for two hours.",
                    "Present perfect continuous",
                    "have/has been + V-ing",
                    "This emphasizes ongoing preparation over time up to now.",
                    [
                        "I have been preparing all day.",
                        "She has been studying Spanish recently.",
                    ],
                ),
                (
                    "Choose: Why _____ so tired tonight?<br>Cue: look<br>A) have you been looking<br>B) are you looking",
                    "A) Why have you been looking so tired tonight?",
                    "Present perfect continuous",
                    "have/has been + V-ing",
                    "A visible present result follows from recent repeated activity.",
                    [
                        "Why have you been working so late?",
                        "They have been testing all night.",
                    ],
                ),
                (
                    "Choose: The team _____ the server for an hour, and users are still waiting.<br>Cue: check<br>A) has been checking<br>B) has checked",
                    "A) The team has been checking the server for an hour, and users are still waiting.",
                    "Present perfect continuous",
                    "have/has been + V-ing",
                    "With a singular team subject, use has been.",
                    [
                        "The team has been monitoring logs.",
                        "The app has been running slowly.",
                    ],
                ),
            ],
            "past perfect": [
                (
                    "Choose: By the time we arrived, they _____ already left.<br>A) had<br>B) have",
                    "A) By the time we arrived, they had already left.",
                    "Past perfect",
                    "had + V3",
                    "past perfect anchors an earlier past event.",
                    [
                        "By the time we arrived, they had already left.",
                        "She had finished before the meeting started.",
                    ],
                ),
                (
                    "Choose: The manager said the system _____ before sunrise.<br>A) had crashed<br>B) crashed",
                    "A) The manager said the system had crashed before sunrise.",
                    "Past perfect",
                    "had + V3",
                    "reported past often keeps sequencing clear with past perfect.",
                    [
                        "The server had crashed by 7:00.",
                        "He said the file had been sent.",
                    ],
                ),
                (
                    "Choose: When we got there, the engineer had already _____ the patch.<br>A) applied<br>B) applies",
                    "A) When we got there, the engineer had already applied the patch.",
                    "Past perfect",
                    "had + V3",
                    "Use past perfect when one event was earlier than another past event.",
                    [
                        "They had applied the patch before the audit started.",
                        "She had checked everything first.",
                    ],
                ),
            ],
            "future forms": [
                (
                    "Choose: The team _____ tomorrow's rollout tomorrow morning.<br>A) is starting<br>B) will start",
                    "B) The team will start tomorrow's rollout tomorrow morning.",
                    "Future forms",
                    "will + V1 / be going to + V1 / present continuous",
                    "Spontaneous decision or prediction uses will.",
                    [
                        "The team will review the changes tomorrow.",
                        "The team is starting tomorrow morning.",
                    ],
                ),
                (
                    "Choose: I _____ the final draft by Friday.<br>A) will finish<br>B) will have finished",
                    "B) I will have finished the final draft by Friday.",
                    "Future forms",
                    "will have + V3",
                    "Use future perfect for action completed before a future reference.",
                    [
                        "By Friday, we will have finished all reviews.",
                        "By Friday, the rollout will have started.",
                    ],
                ),
                (
                    "Choose: We _____ a design review at 14:00.<br>A) are having<br>B) have",
                    "A) We are having a design review at 14:00.",
                    "Future forms",
                    "present continuous (arrangement)",
                    "Planned arrangements are commonly in present continuous.",
                    [
                        "We are launching at 9 a.m.",
                        "I am meeting her tomorrow.",
                    ],
                ),
            ],
            "narrative tenses": [
                (
                    "Choose: I _____ the report when the lights failed.<br>A) was editing<br>B) edited",
                    "A) I was editing the report when the lights failed.",
                    "Narrative tenses",
                    "past continuous + past simple",
                    "Past continuous is background; past simple is interruption.",
                    [
                        "I was typing when the alarm sounded.",
                        "They were walking when it started.",
                    ],
                ),
                (
                    "Choose: She _____ the alarm before the door opened.<br>A) had noticed<br>B) noticed",
                    "B) She noticed the alarm before the door opened.",
                    "Narrative tenses",
                    "simple past sequencing",
                    "A single chronological chain can stay in simple past.",
                    [
                        "She noticed the alarm before the room emptied.",
                        "He arrived before the call ended.",
                    ],
                ),
                (
                    "Choose: They _____ all blockers before we started testing.<br>A) had cleared<br>B) cleared",
                    "A) They had cleared all blockers before we started testing.",
                    "Narrative tenses",
                    "past perfect",
                    "Past perfect marks earlier past action.",
                    [
                        "They had fixed issues before deployment.",
                        "We started testing afterward.",
                    ],
                ),
            ],
        },
        "b2_sentence_control": {
            "conditionals": [
                (
                    "Choose: If it _____ this weekend, we will cancel the trip.<br>A) rains<br>B) rained",
                    "A) If it rains this weekend, we will cancel the trip.",
                    "Conditionals",
                    "if + present, will + V1",
                    "Real future condition takes present tense in if-clause.",
                    [
                        "If it rains, we will stay in.",
                        "If traffic is bad, we will leave earlier.",
                    ],
                ),
                (
                    "Choose: If I _____ more time, I would improve the draft.<br>A) had<br>B) have",
                    "A) If I had more time, I would improve the draft.",
                    "Conditionals",
                    "if + V2, would + V1",
                    "Second conditional for unreal present.",
                    [
                        "If I had more data, I would be more precise.",
                        "If she had a better phone, she would call.",
                    ],
                ),
                (
                    "Choose: If they _____ on time, they would have finished earlier.<br>A) had started<br>B) started",
                    "A) If they had started on time, they would have finished earlier.",
                    "Conditionals",
                    "if + had + V3, would have + V3",
                    "Third conditional reports impossible past outcome.",
                    [
                        "If we had trained, we would have finished.",
                        "If you had checked, you would have fixed it.",
                    ],
                ),
            ],
            "mixed conditionals": [
                (
                    "Choose: If he had _____ to bed earlier, he would be relaxed now.<br>A) gone<br>B) go",
                    "A) If he had gone to bed earlier, he would be relaxed now.",
                    "Mixed conditionals",
                    "past condition + present result",
                    "A past condition can produce a present consequence.",
                    [
                        "If they had invested, the firm would be stronger now.",
                        "If she had exercised, she would feel better now.",
                    ],
                ),
                (
                    "Choose: If I _____ more disciplined, I would not have failed the audit.<br>Cue: be<br>A) were<br>B) had been",
                    "A) If I were more disciplined, I would not have failed the audit.",
                    "Mixed conditionals",
                    "present condition + past result",
                    "A present unreal state can be linked to an alternate past result.",
                    [
                        "If she were calmer, she might not have interrupted.",
                        "If he were clearer, he might have avoided confusion.",
                    ],
                ),
                (
                    "Choose: If she _____ a better process, we would have saved hours.<br>A) had used<br>B) uses",
                    "A) If she had used a better process, we would have saved hours.",
                    "Mixed conditionals",
                    "mixed structure",
                    "Past condition linked to hypothetical past result in speech.",
                    [
                        "If we had planned better, we would have avoided delays.",
                        "If he had stayed, we could have solved it faster.",
                    ],
                ),
            ],
            "passive voice": [
                (
                    "Choose: The report _____ by the editor yesterday.<br>A) reviewed<br>B) was reviewed",
                    "B) The report was reviewed by the editor yesterday.",
                    "Passive voice",
                    "be + V3",
                    "Focus on report and process rather than actor.",
                    [
                        "The memo was approved by the team.",
                        "The file was sent yesterday.",
                    ],
                ),
                (
                    "Choose: The new policy _____ next month.<br>A) will introduce<br>B) will be introduced",
                    "B) The new policy will be introduced next month.",
                    "Passive voice",
                    "be + V3",
                    "Modal passives keep subject as recipient of action.",
                    [
                        "The change will be introduced tomorrow.",
                        "The update will be rolled out next week.",
                    ],
                ),
                (
                    "Choose: The issue _____ before the fix was deployed.<br>Cue: close<br>A) had been closed<br>B) had closed",
                    "A) The issue had been closed before the fix was deployed.",
                    "Passive voice",
                    "had been + V3",
                    "Past perfect passive expresses earlier completed process.",
                    [
                        "The server had been restarted before deployment.",
                        "The room had been cleaned before inspection.",
                    ],
                ),
            ],
            "relative clauses": [
                (
                    "Choose: I met the engineer _____ designed the new API.<br>A) who<br>B) whose",
                    "A) I met the engineer who designed the new API.",
                    "Relative clauses",
                    "who/which/that/whose/where",
                    "Use the right relative pronoun for person/function.",
                    [
                        "I met the engineer who designed the API.",
                        "That is the file that explains the process.",
                    ],
                ),
                (
                    "Choose: The room _____ we met yesterday was small.<br>A) where<br>B) which",
                    "A) The room where we met yesterday was small.",
                    "Relative clauses",
                    "where/which relative adverb",
                    "which is often optional but where is cleaner for place.",
                    [
                        "The place where we met was small.",
                        "She works in the office where we discussed scope.",
                    ],
                ),
                (
                    "Choose: She thanked the colleague _____ draft was excellent.<br>A) whose<br>B) who",
                    "A) She thanked the colleague whose draft was excellent.",
                    "Relative clauses",
                    "whose for possession",
                    "whose introduces possession after a noun.",
                    [
                        "They hired the director whose team delivered.",
                        "I met a lawyer whose client succeeded.",
                    ],
                ),
            ],
            "reported speech": [
                (
                    "Choose: She said she _____ leaving on Friday.<br>A) is<br>B) was",
                    "B) She said she was leaving on Friday.",
                    "Reported speech",
                    "backshift after past reporting verbs",
                    "Past report often requires backshift in reported clause.",
                    [
                        "He said he was ready.",
                        "She said he was working late.",
                    ],
                ),
                (
                    "Choose: He told me that the issue _____ fixed.<br>A) had been<br>B) is",
                    "A) He told me that the issue had been fixed.",
                    "Reported speech",
                    "that-clause reporting",
                    "reported facts in the past often backshift to past perfect.",
                    [
                        "He told me that the patch had been deployed.",
                        "She said the team was waiting.",
                    ],
                ),
                (
                    "Choose: She asked whether the ticket _____ reviewed.<br>A) had been<br>B) was",
                    "A) She asked whether the ticket had been reviewed.",
                    "Reported speech",
                    "whether/if + backshift",
                    "Indirect questions follow normal clause word order with backshift.",
                    [
                        "She asked whether we had finished.",
                        "He wondered whether the data had changed.",
                    ],
                ),
            ],
            "noun clauses": [
                (
                    "Choose: I know why it is _____ that the meeting starts tomorrow.<br>A) important<br>B) importantly",
                    "B) I know why it is important that the meeting starts tomorrow.",
                    "Noun clauses",
                    "noun clauses as object/subject",
                    "Noun clauses can be formed with what/whether/how + word order.",
                    [
                        "I know why it is delayed.",
                        "She explained what she needed.",
                    ],
                ),
                (
                    "Choose: Tell me _____ the client approved the budget.<br>A) if<br>B) where",
                    "A) Tell me if the client approved the budget.",
                    "Noun clauses",
                    "indirect question in noun clause",
                    "use if for yes/no reported questions in a noun position.",
                    [
                        "Tell me if the build passed.",
                        "Ask whether we should continue.",
                    ],
                ),
                (
                    "Choose: I wonder _____ or not we should ship now.<br>A) whether<br>B) if what",
                    "A) I wonder whether or not we should ship now.",
                    "Noun clauses",
                    "whether/if as noun clause introducers",
                    "Use whether before or not in yes/no noun clauses.",
                    [
                        "I wonder whether we should continue.",
                        "I wonder if we should pause.",
                    ],
                ),
            ],
        },
        "b2_verb_patterns": {
            "gerund vs infinitive": [
                (
                    "Choose: I remember _____ her before the meeting.<br>A) to call<br>B) calling",
                    "B) I remember calling her before the meeting.",
                    "Gerund vs infinitive",
                    "verb + -ing / to + V1",
                    "remember + -ing often describes an actual past action.",
                    [
                        "I remember making this mistake.",
                        "I remember to submit the report.",
                    ],
                ),
                (
                    "Choose: They decided _____ another run.<br>Cue: do<br>A) to do<br>B) doing",
                    "A) They decided to do another run.",
                    "Gerund vs infinitive",
                    "decide + to + infinitive",
                    "decide is commonly followed by to + infinitive.",
                    [
                        "They decided to deploy.",
                        "She decided to leave early.",
                    ],
                ),
                (
                    "Choose: He enjoys _____ this task.<br>A) to repeat<br>B) repeating",
                    "B) He enjoys repeating this task.",
                    "Gerund vs infinitive",
                    "certain verbs need -ing",
                    "enjoy, avoid, admit commonly take gerund.",
                    [
                        "He enjoys working on this topic.",
                        "She enjoys solving puzzles.",
                    ],
                ),
            ],
            "used to patterns": [
                (
                    "Choose: I _____ take trains until 2020.<br>A) used to<br>B) am used to",
                    "A) I used to take trains until 2020.",
                    "Used to patterns",
                    "used to vs be used to + noun/gerund",
                    "used to = past habit.",
                    [
                        "I used to commute by train.",
                        "I am used to commuting by train now.",
                    ],
                ),
                (
                    "Choose: He is _____ late meetings now.<br>A) used to<br>B) used to being",
                    "A) He is used to late meetings now.",
                    "Used to patterns",
                    "be used to + noun/gerund",
                    "be used to is followed by noun or gerund.",
                    [
                        "I am used to this level of ambiguity.",
                        "She is used to working late.",
                    ],
                ),
                (
                    "Choose: They are _____ used to writing their own documentation.<br>A) getting<br>B) get",
                    "A) They are getting used to writing their own documentation.",
                    "Used to patterns",
                    "get used to + gerund",
                    "Use get used to for the process of becoming accustomed.",
                    [
                        "She is getting used to the new tool.",
                        "They are getting used to remote work.",
                    ],
                ),
            ],
            "modal verbs": [
                (
                    "Choose: You _____ call customer support on Sundays.<br>A) mustn't<br>B) must",
                    "A) You mustn't call customer support on Sundays.",
                    "Modal verbs",
                    "mustn't = prohibition",
                    "Use this modal for prohibition: the action is not allowed.",
                    [
                        "You must submit the form.",
                        "You mustn't exceed limits.",
                    ],
                ),
                (
                    "Choose: She _____ this error now.<br>A) can fix<br>B) could fix",
                    "A) She can fix this error now.",
                    "Modal verbs",
                    "can / could / may / should",
                    "Use can for present ability/permission in direct statements.",
                    [
                        "She can resolve it quickly.",
                        "He can start immediately.",
                    ],
                ),
                (
                    "Choose: We _____ call a specialist if needed.<br>A) may<br>B) might",
                    "A) We may call a specialist if needed.",
                    "Modal verbs",
                    "may for permission/possibility",
                    "may is used for polite possibility.",
                    [
                        "We may review that option.",
                        "She may be online now.",
                    ],
                ),
            ],
            "modal perfect": [
                (
                    "Choose: You _____ the database after the breach.<br>Cue: lock<br>A) should have locked<br>B) shouldn't have locked",
                    "A) You should have locked the database after the breach.",
                    "Modal perfect",
                    "modal + have + V3",
                    "Use should have + past participle to critique a missed action.",
                    [
                        "You should have updated the patch.",
                        "She should have verified the logs.",
                    ],
                ),
                (
                    "Choose: He _____ your email.<br>Cue: miss<br>A) might have missed<br>B) must have missed",
                    "A) He might have missed your email.",
                    "Modal perfect",
                    "modal + have + V3",
                    "Past possibility uses modal + have + V3.",
                    [
                        "She might have forgotten the meeting.",
                        "They might have seen it.",
                    ],
                ),
                (
                    "Choose: They _____ this downtime with one extra check.<br>Cue: avoid<br>A) could have avoided<br>B) should have avoided",
                    "A) They could have avoided this downtime with one extra check.",
                    "Modal perfect",
                    "could/might have + V3",
                    "Could have expresses unrealized past possibility.",
                    [
                        "We could have prevented this bug.",
                        "He could have improved clarity.",
                    ],
                ),
            ],
            "causatives": [
                (
                    "Choose: I _____ my car repaired last week.<br>A) had<br>B) have",
                    "A) I had my car repaired last week.",
                    "Causatives",
                    "have/get + object + past participle",
                    "Use causative with external agent for arranged service.",
                    [
                        "She had her passport renewed.",
                        "They had the room cleaned.",
                    ],
                ),
                (
                    "Choose: She _____ her team trained in this framework.<br>A) got<br>B) got to",
                    "A) She got her team trained in this framework.",
                    "Causatives",
                    "get + object + past participle",
                    "Use get + object + past participle as a causative pattern.",
                    [
                        "He got the server fixed.",
                        "They got the contract reviewed.",
                    ],
                ),
                (
                    "Choose: We got the document _____ by a translator.<br>A) translated<br>B) translating",
                    "B) We got the document translated by a translator.",
                    "Causatives",
                    "have/get + object + past participle",
                    "Both patterns are valid; choose the one matching naturalness.",
                    [
                        "I had the car cleaned.",
                        "We got the account restored.",
                    ],
                ),
            ],
        },
        "c1_precision": {
            "articles": [
                (
                    "Choose: The _____ should pay more tax.<br>A) rich<br>B) rich people",
                    "A) The rich should pay more tax.",
                    "Articles",
                    "a/an/the/zero",
                    "Use zero for generic category, the when specific group is context-defined.",
                    [
                        "Rich people are overrepresented here.",
                        "The rich in this region have many options.",
                    ],
                ),
                (
                    "Choose: Honesty is a key value in _____ profession.<br>A) a<br>B) this",
                    "A) Honesty is a key value in every profession.",
                    "Articles",
                    "zero article (general abstract)",
                    "General abstract nouns often take zero article.",
                    [
                        "Honesty is essential.",
                        "Life can be unpredictable.",
                    ],
                ),
                (
                    "Choose: She showed us _____ honest mistake.<br>A) a<br>B) an",
                    "A) She showed us an honest mistake.",
                    "Articles",
                    "a/an before noun sound",
                    "Use an before words starting with vowel sounds.",
                    [
                        "An honest mistake is still a mistake.",
                        "An hour of rest helps.",
                    ],
                ),
            ],
            "prepositions": [
                (
                    "Choose: The app depends _____ user behavior.<br>A) at<br>B) on",
                    "B) The app depends on user behavior.",
                    "Prepositions",
                    "fixed verbal collocations",
                    "depend is followed by on.",
                    [
                        "The model depends on the dataset.",
                        "This relies on good design.",
                    ],
                ),
                (
                    "Choose: She is responsible _____ quality control.<br>A) for<br>B) about",
                    "A) She is responsible for quality control.",
                    "Prepositions",
                    "adjective/noun + preposition fixed",
                    "responsible takes for.",
                    [
                        "He is responsible for outcomes.",
                        "We are responsible for quality.",
                    ],
                ),
                (
                    "Choose: The two systems are comparable _____ this prototype.<br>A) to<br>B) with",
                    "A) The two systems are comparable to this prototype.",
                    "Prepositions",
                    "comparable to",
                    "comparable usually takes to in standard formal register.",
                    [
                        "This version is comparable to the old one.",
                        "Their result is comparable to ours.",
                    ],
                ),
            ],
            "countable and uncountable nouns": [
                (
                    "Choose: She gave us useful _____.<br>A) advice<br>B) advices",
                    "A) She gave us useful advice.",
                    "Countable and uncountable nouns",
                    "uncountable nouns usually no plural",
                    "advice is uncountable.",
                    [
                        "Useful advice is rare.",
                        "There is advice available.",
                    ],
                ),
                (
                    "Choose: There were _____ complaints this month.<br>A) fewer<br>B) less",
                    "A) There were fewer complaints this month.",
                    "Countable and uncountable nouns",
                    "fewer for countables, less for uncountables",
                    "Complaints are countable here.",
                    [
                        "There were fewer issues this quarter.",
                        "There is less noise now.",
                    ],
                ),
                (
                    "Choose: We need much more _____ from vendors.<br>A) informations<br>B) information",
                    "B) We need much more information from vendors.",
                    "Countable and uncountable nouns",
                    "much/little with uncountables",
                    "information remains uncountable.",
                    [
                        "We need more information.",
                        "Much patience is required.",
                    ],
                ),
            ],
            "comparatives": [
                (
                    "Choose: This model is _____ expensive than that one.<br>A) more<br>B) most",
                    "A) This model is more expensive than that one.",
                    "Comparatives",
                    "comparative + than",
                    "Use comparative form with than for direct comparison.",
                    [
                        "This is more reliable than that.",
                        "This report is clearer than that one.",
                    ],
                ),
                (
                    "Choose: The more you read, _____ you write.<br>A) the better<br>B) better",
                    "A) The more you read, the better you write.",
                    "Comparatives",
                    "the + comparative / the + comparative",
                    "Correlative pattern for linked changes.",
                    [
                        "The more data, the better.",
                        "The less you wait, the faster it comes.",
                    ],
                ),
                (
                    "Choose: It is _____ complicated form of this construction.<br>A) the least<br>B) least",
                    "A) It is the least complicated form of this construction.",
                    "Comparatives",
                    "superlative with the",
                    "Use the with superlative forms.",
                    [
                        "This is the least risky option.",
                        "This is the most concise version.",
                    ],
                ),
            ],
            "emphasis and inversion": [
                (
                    "Choose: Only then _____ they fully understand the problem.<br>A) did<br>B) do",
                    "A) Only then did they fully understand the problem.",
                    "Emphasis and inversion",
                    "fronted adverbial + inversion",
                    "Fronted negatives/restrictives trigger inversion.",
                    [
                        "Only then did they respond.",
                        "Only after this did we decide.",
                    ],
                ),
                (
                    "Choose: Never _____ this complexity before.<br>A) I saw<br>B) did I see",
                    "B) Never have I seen this complexity before.",
                    "Emphasis and inversion",
                    "never / rarely + inversion",
                    "Negative fronting requires auxiliary inversion.",
                    [
                        "Never have we faced this delay.",
                        "Rarely do we meet such cases.",
                    ],
                ),
                (
                    "Choose: It was _____ they accepted the policy.<br>A) what<br>B) that",
                    "A) It was the fact that they accepted the policy.",
                    "Emphasis and inversion",
                    "clefting/what-focus",
                    "It-cleft allows emphasis on a clause.",
                    [
                        "It was the result that mattered.",
                        "It was a mistake to ignore.",
                    ],
                ),
            ],
        },
        "c1_style": {
            "sentence connectors": [
                (
                    "Choose: The model became stable; _____ we can expand usage.<br>A) therefore<br>B) however",
                    "A) The model became stable; therefore, we can expand usage.",
                    "Sentence connectors",
                    "connector expresses consequence/contrast",
                    "therefore links result.",
                    [
                        "The test passed; therefore, we deployed.",
                        "Data were inconsistent; however, we proceeded.",
                    ],
                ),
                (
                    "Choose: The design is clear; _____ the release was delayed by tests.<br>A) however<br>B) therefore",
                    "A) The design is clear; however, the release was delayed by tests.",
                    "Sentence connectors",
                    "however for contrast",
                    "Use a contrast connector between two independent clauses.",
                    [
                        "The plan is solid; however, timing is tight.",
                        "They wanted speed; however, accuracy suffered.",
                    ],
                ),
                (
                    "Choose: We delayed the launch _____ we found a security bug.<br>A) because<br>B) therefore",
                    "A) We delayed the launch because we found a security bug.",
                    "Sentence connectors",
                    "because/so for cause/effect",
                    "because introduces reason before result.",
                    [
                        "We delayed because of late data.",
                        "We fixed it because it was broken.",
                    ],
                ),
            ],
            "participle clauses": [
                (
                    "Choose: _____ the report, the team approved the plan.<br>A) Reading<br>B) Read",
                    "A) Reading the report, the team approved the plan.",
                    "Participle clauses",
                    "V-ing / V3 / having + V3",
                    "Participles compress subordinate information.",
                    [
                        "Reading the report, she approved the policy.",
                        "Having reviewed the file, he responded.",
                    ],
                ),
                (
                    "Choose: _____ the project quickly made deadlines manageable.<br>A) Completed<br>B) Completing",
                    "B) Completing the project quickly made deadlines manageable.",
                    "Participle clauses",
                    "reducing relative-like structures",
                    "Use active verbal clause for simultaneous concise action.",
                    [
                        "Completing the draft, they revised wording.",
                        "Completing quickly improves throughput.",
                    ],
                ),
                (
                    "Choose: Once the data _____ validated, the model moved to production.<br>A) was<br>B) is",
                    "A) Once the data was validated, the model moved to production.",
                    "Participle clauses",
                    "once + subordinate structure",
                    "Participle clause must be semantically clear.",
                    [
                        "Once validated, the data was released.",
                        "Once cleaned, the dataset was safe.",
                    ],
                ),
            ],
            "reduced relative clauses": [
                (
                    "Choose: The files _____ yesterday were approved.<br>A) submitted<br>B) submitting",
                    "A) The files submitted yesterday were approved.",
                    "Reduced relative clauses",
                    "noun + V3 phrase",
                    "Passive reduced clauses often use V3.",
                    [
                        "The reports submitted today are under review.",
                        "The issue fixed yesterday still persists.",
                    ],
                ),
                (
                    "Choose: The manager _____ for years now led the review.<br>A) working<br>B) who has worked",
                    "A) The manager working for years now led the review.",
                    "Reduced relative clauses",
                    "active reduced relative",
                    "V-ing compresses relative clauses about the noun.",
                    [
                        "The person running the project explained it.",
                        "The team working on this issue reported.",
                    ],
                ),
                (
                    "Choose: The candidate _____ this change was promoted.<br>A) who proposed<br>B) proposing",
                    "A) The candidate who proposed this change was promoted.",
                    "Reduced relative clauses",
                    "full relative can be safer",
                    "Some reduced forms are awkward; choose full relative for clarity.",
                    [
                        "The person who proposed the change was promoted.",
                        "The engineer who designed it explained.",
                    ],
                ),
            ],
            "hedging": [
                (
                    "Choose: The results _____ indicate a moderate improvement.<br>A) seem<br>B) prove",
                    "A) The results seem to indicate a moderate improvement.",
                    "Hedging",
                    "may/seem/suggest",
                    "hedging softens assertiveness in academic/professional writing.",
                    [
                        "The data seem to support the claim.",
                        "It appears to be true.",
                    ],
                ),
                (
                    "Choose: This could _____ be an isolated incident.<br>A) possibly<br>B) possible",
                    "A) This could possibly be an isolated incident.",
                    "Hedging",
                    "could/may for cautious interpretation",
                    "Adverbs can hedge modality.",
                    [
                        "This may possibly be a false alarm.",
                        "It seems possibly valid.",
                    ],
                ),
                (
                    "Choose: The new protocol is _____ effective, pending broader testing.<br>A) possibly<br>B) definitive",
                    "A) The new protocol is possibly effective, pending broader testing.",
                    "Hedging",
                    "adverbs and qualifiers",
                    "Hedging keeps claims proportionate to evidence.",
                    [
                        "This may be effective.",
                        "This possibly helps under load.",
                    ],
                ),
            ],
            "formal register": [
                (
                    "Choose: They _____ out an internal review after the outage.<br>A) carried<br>B) carry",
                    "A) They carried out an internal review after the outage.",
                    "Formal register",
                    "formal lexical choices",
                    "carry out, conduct are formal alternatives to phrasal alternatives.",
                    [
                        "They conducted a review.",
                        "The committee carried out assessments.",
                    ],
                ),
                (
                    "Choose: Should the audit fail, we _____ a mitigation path immediately.<br>A) implement<br>B) carry",
                    "B) Should the audit fail, we should implement a mitigation path immediately.",
                    "Formal register",
                    "inverted modal conditionals",
                    "Formal writing can use should + inversion.",
                    [
                        "Should the system fail, notify support.",
                        "Should concerns arise, escalate immediately.",
                    ],
                ),
                (
                    "Choose: Please _____ that the revised timeline is sent by tomorrow.<br>A) assure<br>B) ensure",
                    "B) Please ensure that the revised timeline is sent by tomorrow.",
                    "Formal register",
                    "ensure that + clause",
                    "ensure that is common in formal request register.",
                    [
                        "Please ensure that the file is complete.",
                        "Please provide all details.",
                    ],
                ),
            ],
        },
        "c2_mastery": {
            "advanced inversion": [
                (
                    "Choose: Rarely _____ such clarity in one report.<br>A) we see<br>B) do we see",
                    "B) Rarely do we see such clarity in one report.",
                    "Advanced inversion",
                    "negative adverbials + inversion",
                    "Rarely at sentence start triggers inversion.",
                    [
                        "Rarely have we seen this quality.",
                        "Seldom do teams document this clearly.",
                    ],
                ),
                (
                    "Choose: Not only _____ the team approve the report, but the launch also improved speed.<br>A) did<br>B) do",
                    "B) Not only did the team approve the report, but the launch also improved speed.",
                    "Advanced inversion",
                    "not only ... not a clause",
                    "not only + fronting triggers inversion in the first clause.",
                    [
                        "Not only did they complete it, but they improved it.",
                        "Not only did he mention it; he solved it.",
                    ],
                ),
                (
                    "Choose: Under no circumstances _____ credentials publicly.<br>A) should we share<br>B) we should share",
                    "A) Under no circumstances should we share credentials publicly.",
                    "Advanced inversion",
                    "fronted negative phrase + inversion",
                    "fronted negative phrase with no/rarely/seldom drives inversion.",
                    [
                        "Under no circumstances should this be disclosed.",
                        "Under no circumstances did he share the file.",
                    ],
                ),
            ],
            "subjunctive and mandative structures": [
                (
                    "Choose: The manager required that every analyst _____ this plan.<br>A) check<br>B) checks",
                    "A) The manager required that every analyst check this plan.",
                    "Subjunctive and mandative structures",
                    "recommend/require + that + bare verb",
                    "Mandative style uses the bare infinitive.",
                    [
                        "The policy requires every team comply.",
                        "The board required that results be verified.",
                    ],
                ),
                (
                    "Choose: The committee suggested that the team _____ the data before approval.<br>A) should review<br>B) review",
                    "B) The committee suggested that the team review the data before approval.",
                    "Subjunctive and mandative structures",
                    "suggest/insist/demand + subjunctive-like",
                    "Modal + to is often avoided after recommend/insist in formal form.",
                    [
                        "The committee suggested that changes happen now.",
                        "They insisted that the policy be updated.",
                    ],
                ),
                (
                    "Choose: It is essential that all members _____ informed.<br>A) are<br>B) be",
                    "B) It is essential that all members be informed.",
                    "Subjunctive and mandative structures",
                    "it is essential that + be",
                    "Fixed evaluative construction uses base verb.",
                    [
                        "It is essential that errors be avoided.",
                        "It is vital that reports be accurate.",
                    ],
                ),
            ],
            "clefting and fronting": [
                (
                    "Choose: _____ delayed the rollout was the data inconsistency.<br>A) What<br>B) Which",
                    "A) What delayed the rollout was the data inconsistency.",
                    "Clefting and fronting",
                    "what-cleft emphasizes information",
                    "What-cleft helps highlight important component.",
                    [
                        "What mattered was reliability.",
                        "What worked was the revised wording.",
                    ],
                ),
                (
                    "Choose: It was _____ that changed quality most.<br>A) the process was simple<br>B) the process",
                    "B) It was the process that changed quality most.",
                    "Clefting and fronting",
                    "it-cleft with that-clause",
                    "it + be + focused element + that-clause.",
                    [
                        "It was the team that solved it.",
                        "It was the timeline that failed us.",
                    ],
                ),
                (
                    "Choose: The fact _____ the script had changed was the source of this risk.<br>A) that<br>B) which",
                    "A) The fact that the script had changed was the source of this risk.",
                    "Clefting and fronting",
                    "fronted noun phrase for emphasis",
                    "Use that-clause with it-cleft-like focus for precision.",
                    [
                        "The fact that the script changed was critical.",
                        "What mattered was timing.",
                    ],
                ),
            ],
            "ellipsis and substitution": [
                (
                    "Choose: She said it was urgent, and we should _____ too.<br>A) do so<br>B) do this",
                    "A) She said it was urgent, and we should do so too.",
                    "Ellipsis and substitution",
                    "do so replacing verb phrase",
                    "do so substitutes for a full repeated clause.",
                    [
                        "The team agreed and so did we.",
                        "He promised to call, and I did so.",
                    ],
                ),
                (
                    "Choose: I bought two cables; this cable is blue and that _____ is red.<br>A) one<br>B) ones",
                    "A) I bought two cables; this cable is blue and that one is red.",
                    "Ellipsis and substitution",
                    "one/ones for noun substitution",
                    "Use one for a repeated singular noun.",
                    [
                        "This one is faster.",
                        "Give me the one with more storage.",
                    ],
                ),
                (
                    "Choose: We reviewed the test, and she _____ too.<br>A) did<br>B) did so",
                    "B) We reviewed the test, and she did so too.",
                    "Ellipsis and substitution",
                    "did so / did for repetition",
                    "did so replaces repeated action cleanly.",
                    [
                        "He said yes, and I did so.",
                        "They completed the task and did so.",
                    ],
                ),
            ],
            "advanced concession": [
                (
                    "Choose: _____ the evidence was limited, we still moved forward.<br>A) Despite<br>B) Although",
                    "B) Although the evidence was limited, we still moved forward.",
                    "Advanced concession",
                    "although + clause",
                    "Although introduces counterpoint while maintaining main assertion.",
                    [
                        "Although the time was short, we finished.",
                        "Although there were risks, we proceeded.",
                    ],
                ),
                (
                    "Choose: Difficult _____ it was, she remained calm.<br>A) though<br>B) in spite",
                    "A) Difficult though it was, she remained calm.",
                    "Advanced concession",
                    "though-adjective inversion",
                    "though + adjective clause compresses meaning.",
                    [
                        "Unexpected though it was, the issue appeared.",
                        "Hard though it was, he stayed.",
                    ],
                ),
                (
                    "Choose: No matter _____ they tried, the result stayed the same.<br>A) how hard<br>B) where",
                    "A) No matter how hard they tried, the result stayed the same.",
                    "Advanced concession",
                    "no matter + wh-word",
                    "No matter links non-finite extent with concessive meaning.",
                    [
                        "No matter how late, we arrived.",
                        "No matter what he says, we continue.",
                    ],
                ),
            ],
            "nominalisation": [
                (
                    "Choose: The committee's _____ to proceed was unanimous.<br>A) recommendation<br>B) recommend",
                    "A) The committee's recommendation to proceed was unanimous.",
                    "Nominalisation",
                    "verb -> noun conversion",
                    "Nominalised forms compress clause meaning.",
                    [
                        "His recommendation changed the schedule.",
                        "Their refusal delayed the launch.",
                    ],
                ),
                (
                    "Choose: The _____ to complete testing caused delays.<br>A) failure of the team failed<br>B) failure",
                    "B) The failure to complete testing caused delays.",
                    "Nominalisation",
                    "to-infinitive noun phrase",
                    "to-clause as noun phrase can create formal compression.",
                    [
                        "The attempt to improve worked.",
                        "The refusal to comply caused concern.",
                    ],
                ),
                (
                    "Choose: Due _____ training, rollout was slower.<br>A) to the lack of<br>B) to lack",
                    "A) Due to the lack of training, rollout was slower.",
                    "Nominalisation",
                    "nominalised cause expressions",
                    "use nominal phrase for formal causal structure.",
                    [
                        "Due to the lack of context, confusion grew.",
                        "Due to time, rollout was delayed.",
                    ],
                ),
            ],
            "parallelism": [
                (
                    "Choose: The tool is fast, safe, and _____.<br>A) reliable<br>B) reliably",
                    "A) The tool is fast, safe, and reliable.",
                    "Parallelism",
                    "match item form in list",
                    "All items in coordination should match grammatical form.",
                    [
                        "The system is robust, clear, and reliable.",
                        "The plan was fast, cheap, and stable.",
                    ],
                ),
                (
                    "Choose: Our goal is to measure, improve, and _____ quality.<br>A) maintain<br>B) maintaining",
                    "A) Our goal is to measure, improve, and maintain quality.",
                    "Parallelism",
                    'verb form matching in "to + list"',
                    "Use matching base forms after to where possible.",
                    [
                        "The team aims to plan, build, and test.",
                        "Our goal is to reduce, prevent, and eliminate risk.",
                    ],
                ),
                (
                    "Choose: It is not about speed, _____ about reliability.<br>A) only, not<br>B) only but",
                    "A) It is not about speed, only about reliability.",
                    "Parallelism",
                    "balanced phrase structure",
                    "Balance coordinated noun phrases for clarity.",
                    [
                        "This is about function, not aesthetics.",
                        "We care about security, not shortcuts.",
                    ],
                ),
            ],
        },
    }
    for level, entries in topic_map.items():
        for topic, cards_for_topic in entries.items():
            for front, correct, grammar_name, formula, reason, examples in cards_for_topic:
                _add_choose(cards, level, topic, front, correct, grammar_name, formula, reason, examples)

    return cards


GRAMMAR_CARDS = _build_choose_only_grammar_cards()


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
