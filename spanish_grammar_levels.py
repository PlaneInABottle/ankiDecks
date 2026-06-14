import argparse
import csv
import io
from pathlib import Path


LEVELS = [
    {
        "id": "a0_survival",
        "name": "A0 - Survival",
        "goal": "Recognize Spanish sentence shape, gender, number, and the first core verbs.",
        "topics": [
            "pronunciation and accent marks",
            "noun gender",
            "plural nouns",
            "adjective agreement",
            "subject pronouns",
            "ser basics",
            "negation",
            "yes-no questions",
        ],
    },
    {
        "id": "a1_1_foundations",
        "name": "A1.1 - Foundations",
        "goal": "Build simple present-tense sentences about identity, location, and routine.",
        "topics": [
            "ser vs estar",
            "regular -ar present",
            "regular -er and -ir present",
            "articles",
            "hay",
            "question words",
        ],
    },
    {
        "id": "a1_2_core_sentences",
        "name": "A1.2 - Core Sentences",
        "goal": "Talk about needs, plans, likes, possession, and basic objects.",
        "topics": [
            "tener and tener que",
            "ir a infinitive",
            "possessive adjectives",
            "gustar basics",
            "reflexive verbs",
            "direct object pronouns",
        ],
    },
    {
        "id": "a2_1_daily_past",
        "name": "A2.1 - Daily Past & Comparison",
        "goal": "Talk about completed events, background situations, comparisons, and simple commands.",
        "topics": [
            "regular preterite",
            "irregular preterite",
            "imperfect basics",
            "preterite vs imperfect",
            "comparatives",
            "informal commands",
        ],
    },
    {
        "id": "a2_2_natural_spanish",
        "name": "A2.2 - More Natural Spanish",
        "goal": "Connect ideas and avoid English-shaped Spanish in common A2 structures.",
        "topics": [
            "por vs para",
            "indirect object pronouns",
            "double object pronouns",
            "present progressive",
            "present perfect",
            "relative clauses and connectors",
        ],
    },
]


TOPICS = [
    {
        "level": "a0_survival",
        "topic": "pronunciation and accent marks",
        "formula": "á, é, í, ó, ú mark stressed vowels; ñ is a separate sound; h is silent.",
        "use": "Use accent marks and special letters as part of spelling, not decoration.",
        "examples": ["sí = yes", "si = if", "año = year", "hablo = I speak"],
        "trap": "ano without ñ is a different word. Keep ñ.",
        "choose": ("Choose the Spanish spelling for 'year':<br>A) ano<br>B) año", "B) año", "ñ changes the sound and the meaning."),
        "correction": ("Si, estudio espanol.", "Sí, estudio español.", "Accent marks matter: sí = yes; español has ñ."),
        "production": ("Write in Spanish: Yes, I speak Spanish.", "Sí, hablo español.", "This uses sí with an accent and español with ñ."),
        "pattern": ("sí/no answer", "Sí, + sentence. / No, + sentence.", ["Sí, estudio.", "No, trabajo.", "Sí, hablo español."]),
    },
    {
        "level": "a0_survival",
        "topic": "noun gender",
        "formula": "el + masculine noun; la + feminine noun",
        "use": "Every Spanish noun has grammatical gender. Learn the article with the noun.",
        "examples": ["el libro", "la casa", "el problema"],
        "trap": "Many -a words are feminine, but el problema is masculine.",
        "choose": ("Choose: ___ libro<br>A) el<br>B) la", "A) el libro", "libro is masculine."),
        "correction": ("la problema", "el problema", "problema ends in -a but is masculine."),
        "production": ("Write in Spanish: the house", "la casa", "casa is feminine."),
        "pattern": ("article + noun", "el/la + noun", ["el libro", "la mesa", "el mapa"]),
    },
    {
        "level": "a0_survival",
        "topic": "plural nouns",
        "formula": "vowel + s; consonant + es",
        "use": "Make nouns plural according to their ending.",
        "examples": ["libro -> libros", "casa -> casas", "ciudad -> ciudades"],
        "trap": "The article changes too: el libro -> los libros.",
        "choose": ("Choose: two cities = dos ___<br>A) ciudad<br>B) ciudades", "B) dos ciudades", "A consonant-ending noun often adds -es."),
        "correction": ("los ciudad", "las ciudades", "ciudad is feminine; plural is ciudades."),
        "production": ("Write in Spanish: the books", "los libros", "el becomes los and libro becomes libros."),
        "pattern": ("plural article + noun", "los/las + plural noun", ["los libros", "las casas", "las ciudades"]),
    },
    {
        "level": "a0_survival",
        "topic": "adjective agreement",
        "formula": "noun + adjective; adjective agrees in gender and number",
        "use": "Most descriptive adjectives come after the noun and match it.",
        "examples": ["el libro rojo", "la casa roja", "los libros rojos"],
        "trap": "Do not keep the masculine adjective for every noun.",
        "choose": ("Choose: la casa ___<br>A) rojo<br>B) roja", "B) la casa roja", "casa is feminine, so rojo becomes roja."),
        "correction": ("las casas rojo", "las casas rojas", "Feminine plural noun needs feminine plural adjective."),
        "production": ("Write in Spanish: the red books", "los libros rojos", "libros is masculine plural, so rojos."),
        "pattern": ("noun + color", "article + noun + color", ["el coche blanco", "la puerta blanca", "los coches blancos"]),
    },
    {
        "level": "a0_survival",
        "topic": "subject pronouns",
        "formula": "yo, tú, él/ella/usted, nosotros/nosotras, vosotros/vosotras, ellos/ellas/ustedes",
        "use": "Spanish verb endings often show the subject, so pronouns are often optional.",
        "examples": ["yo hablo", "tú estudias", "ella trabaja"],
        "trap": "usted means you formal but uses third-person verb forms.",
        "choose": ("Choose the informal 'you':<br>A) tú<br>B) usted", "A) tú", "tú is informal singular you."),
        "correction": ("usted hablas", "usted habla", "usted uses third-person singular verb forms."),
        "production": ("Write in Spanish: she", "ella", "ella is the subject pronoun for she."),
        "pattern": ("optional subject", "(yo) hablo; (tú) estudias", ["Yo hablo.", "Hablo.", "Ella trabaja."]),
    },
    {
        "level": "a0_survival",
        "topic": "ser basics",
        "formula": "yo soy; tú eres; él/ella/usted es",
        "use": "Use ser for identity, origin, profession, and basic description.",
        "examples": ["Soy estudiante.", "Eres amable.", "Ella es médica."],
        "trap": "Do not use es with yo.",
        "choose": ("Choose: I am a student.<br>A) Soy estudiante.<br>B) Es estudiante.", "A) Soy estudiante.", "yo uses soy."),
        "correction": ("Yo es profesor.", "Yo soy profesor.", "The yo form of ser is soy."),
        "production": ("Write in Spanish: I am Ana.", "Soy Ana.", "Subject pronoun yo can be omitted."),
        "pattern": ("ser + identity", "soy/eres/es + noun/adjective", ["Soy estudiante.", "Eres Carlos.", "Es importante."]),
    },
    {
        "level": "a0_survival",
        "topic": "negation",
        "formula": "no + verb",
        "use": "Put no before the conjugated verb to make a sentence negative.",
        "examples": ["No soy médico.", "No estudio hoy.", "Ella no trabaja."],
        "trap": "Do not put no after the verb as in English short answers.",
        "choose": ("Choose: I am not a teacher.<br>A) No soy profesor.<br>B) Soy no profesor.", "A) No soy profesor.", "Spanish negation goes before the verb."),
        "correction": ("Soy no estudiante.", "No soy estudiante.", "Put no before soy."),
        "production": ("Write in Spanish: I do not study.", "No estudio.", "Use no before the verb."),
        "pattern": ("negative sentence", "no + conjugated verb", ["No hablo.", "No estudio.", "No es caro."]),
    },
    {
        "level": "a0_survival",
        "topic": "yes-no questions",
        "formula": "¿ + statement order + ?",
        "use": "Spanish yes-no questions can keep statement word order; intonation and punctuation mark the question.",
        "examples": ["¿Eres estudiante?", "¿Hablas español?", "¿Es importante?"],
        "trap": "Use the opening question mark in formal writing.",
        "choose": ("Choose the question:<br>A) ¿Hablas español?<br>B) Hablas español.", "A) ¿Hablas español?", "Question marks signal a written question."),
        "correction": ("Hablas español?", "¿Hablas español?", "Spanish uses opening and closing question marks."),
        "production": ("Write in Spanish: Do you speak Spanish?", "¿Hablas español?", "Statement order can become a question with punctuation/intonation."),
        "pattern": ("question from statement", "¿statement?", ["¿Estudias?", "¿Trabajas?", "¿Eres Ana?"]),
    },
    {
        "level": "a1_1_foundations",
        "topic": "ser vs estar",
        "formula": "ser = identity/essential description; estar = location/state",
        "use": "Choose ser for what something is and estar for where/how it is.",
        "examples": ["Soy estudiante.", "Estoy en casa.", "La puerta está abierta."],
        "trap": "Temporary feelings usually use estar: estoy cansado.",
        "choose": ("Choose: I am tired.<br>A) Soy cansado.<br>B) Estoy cansado.", "B) Estoy cansado.", "Tired is a state, so use estar."),
        "correction": ("Madrid está la capital de España.", "Madrid es la capital de España.", "Identity/role uses ser."),
        "production": ("Write in Spanish: I am at home.", "Estoy en casa.", "Location uses estar."),
        "pattern": ("ser/estar contrast", "ser + identity; estar + place/state", ["Es médico.", "Está aquí.", "Estoy bien."]),
    },
    {
        "level": "a1_1_foundations",
        "topic": "regular -ar present",
        "formula": "hablar: hablo, hablas, habla, hablamos, hablan",
        "use": "Use regular -ar endings for present habits and current facts.",
        "examples": ["Hablo español.", "Ella trabaja hoy.", "Estudiamos por la noche."],
        "trap": "The yo form ends in -o, not -a.",
        "choose": ("Choose: I speak Spanish.<br>A) Hablo español.<br>B) Habla español.", "A) Hablo español.", "yo form of hablar is hablo."),
        "correction": ("Yo habla español.", "Yo hablo español.", "The yo ending is -o."),
        "production": ("Write in Spanish: We study at night.", "Estudiamos por la noche.", "The nosotros form of estudiar is estudiamos."),
        "pattern": ("-ar present", "stem + o/as/a/amos/an", ["hablo", "hablas", "hablamos"]),
    },
    {
        "level": "a1_1_foundations",
        "topic": "regular -er and -ir present",
        "formula": "comer: como, comes, come; vivir: vivo, vives, vive",
        "use": "Use -er and -ir present endings for regular present-tense verbs.",
        "examples": ["Como arroz.", "Vivo en Madrid.", "Ella escribe mucho."],
        "trap": "-er and -ir are mostly the same in present except nosotros/vosotros.",
        "choose": ("Choose: I live in Mexico.<br>A) Vivo en México.<br>B) Vive en México.", "A) Vivo en México.", "yo form of vivir is vivo."),
        "correction": ("Ella comes arroz.", "Ella come arroz.", "Third-person singular of comer is come."),
        "production": ("Write in Spanish: I eat bread.", "Como pan.", "The yo form of comer is como."),
        "pattern": ("-er/-ir present", "stem + o/es/e/emos-en or imos-en", ["como", "vivo", "escribimos"]),
    },
    {
        "level": "a1_1_foundations",
        "topic": "articles",
        "formula": "definite: el/la/los/las; indefinite: un/una/unos/unas",
        "use": "Use definite articles for specific nouns and indefinite articles for nonspecific nouns.",
        "examples": ["un libro", "el libro", "unas casas", "las casas"],
        "trap": "Article gender and number must match the noun.",
        "choose": ("Choose: a house<br>A) un casa<br>B) una casa", "B) una casa", "casa is feminine singular."),
        "correction": ("el casas", "las casas", "Plural feminine noun needs las."),
        "production": ("Write in Spanish: some books", "unos libros", "libros is masculine plural."),
        "pattern": ("article agreement", "article + noun", ["un coche", "una mesa", "los problemas"]),
    },
    {
        "level": "a1_1_foundations",
        "topic": "hay",
        "formula": "hay = there is / there are",
        "use": "Use hay to say that something exists or is present.",
        "examples": ["Hay un libro.", "Hay tres personas.", "No hay tiempo."],
        "trap": "hay does not change for singular/plural.",
        "choose": ("Choose: There are two books.<br>A) Hay dos libros.<br>B) Hay dos libro.", "A) Hay dos libros.", "The noun becomes plural; hay stays the same."),
        "correction": ("Hay una problemas.", "Hay unos problemas.", "problemas is masculine plural."),
        "production": ("Write in Spanish: There is no time.", "No hay tiempo.", "Use no hay for there is not/there are not."),
        "pattern": ("existence", "hay + noun", ["Hay agua.", "Hay una mesa.", "Hay muchos libros."]),
    },
    {
        "level": "a1_1_foundations",
        "topic": "question words",
        "formula": "qué, quién, dónde, cuándo, cómo, cuánto/cuánta",
        "use": "Use question words to ask for specific information.",
        "examples": ["¿Qué estudias?", "¿Dónde vives?", "¿Cómo estás?"],
        "trap": "Question words normally carry accent marks.",
        "choose": ("Choose: Where do you live?<br>A) ¿Dónde vives?<br>B) ¿Qué vives?", "A) ¿Dónde vives?", "dónde asks where."),
        "correction": ("Donde vives?", "¿Dónde vives?", "Use accent and Spanish question marks."),
        "production": ("Write in Spanish: What do you study?", "¿Qué estudias?", "qué asks what."),
        "pattern": ("question word + verb", "¿question word + conjugated verb?", ["¿Qué comes?", "¿Dónde trabajas?", "¿Cuándo estudias?"]),
    },
    {
        "level": "a1_2_core_sentences",
        "topic": "tener and tener que",
        "formula": "tener = to have; tener que + infinitive = have to",
        "use": "Use tener for possession/age and tener que for obligation.",
        "examples": ["Tengo un libro.", "Tengo veinte años.", "Tengo que estudiar."],
        "trap": "Age uses tener, not ser/estar.",
        "choose": ("Choose: I have to work.<br>A) Tengo que trabajar.<br>B) Tengo trabajar.", "A) Tengo que trabajar.", "Obligation needs tener que + infinitive."),
        "correction": ("Soy veinte años.", "Tengo veinte años.", "Spanish expresses age with tener."),
        "production": ("Write in Spanish: I have to study today.", "Tengo que estudiar hoy.", "Use tener que + infinitive."),
        "pattern": ("obligation", "tener que + infinitive", ["Tengo que salir.", "Tienes que leer.", "Tenemos que practicar."]),
    },
    {
        "level": "a1_2_core_sentences",
        "topic": "ir a infinitive",
        "formula": "ir a + infinitive",
        "use": "Use ir a + infinitive for near future plans.",
        "examples": ["Voy a estudiar.", "Vamos a comer.", "Ella va a viajar."],
        "trap": "Do not conjugate the second verb after a.",
        "choose": ("Choose: We are going to eat.<br>A) Vamos a comemos.<br>B) Vamos a comer.", "B) Vamos a comer.", "After a, keep the infinitive."),
        "correction": ("Voy a estudio.", "Voy a estudiar.", "Use infinitive after ir a."),
        "production": ("Write in Spanish: I am going to read.", "Voy a leer.", "voy a + infinitive."),
        "pattern": ("near future", "ir conjugated + a + infinitive", ["Voy a salir.", "Vas a estudiar.", "Van a trabajar."]),
    },
    {
        "level": "a1_2_core_sentences",
        "topic": "possessive adjectives",
        "formula": "mi/mis, tu/tus, su/sus, nuestro/nuestra/nuestros/nuestras",
        "use": "Possessive adjectives agree with the thing possessed.",
        "examples": ["mi libro", "mis libros", "nuestra casa"],
        "trap": "mi changes to mis for plural possessed nouns.",
        "choose": ("Choose: my books<br>A) mi libros<br>B) mis libros", "B) mis libros", "libros is plural, so use mis."),
        "correction": ("nuestra libros", "nuestros libros", "nuestro agrees with libros, masculine plural."),
        "production": ("Write in Spanish: your house", "tu casa", "tu is singular informal your."),
        "pattern": ("possessive + noun", "mi/tu/su + noun", ["mi casa", "tus amigos", "sus libros"]),
    },
    {
        "level": "a1_2_core_sentences",
        "topic": "gustar basics",
        "formula": "me/te/le gusta + singular or infinitive; me/te/le gustan + plural",
        "use": "gustar agrees with the thing liked, not the person who likes it.",
        "examples": ["Me gusta el café.", "Me gustan los libros.", "Nos gusta estudiar."],
        "trap": "Do not say yo gusto for I like something.",
        "choose": ("Choose: I like books.<br>A) Me gusta los libros.<br>B) Me gustan los libros.", "B) Me gustan los libros.", "The liked thing is plural: los libros."),
        "correction": ("Yo gusto café.", "Me gusta el café.", "Use me gusta for I like it."),
        "production": ("Write in Spanish: I like Spanish.", "Me gusta el español.", "The thing liked is singular."),
        "pattern": ("liking", "me gusta/gustan + thing", ["Me gusta leer.", "Te gusta el café.", "Le gustan las películas."]),
    },
    {
        "level": "a1_2_core_sentences",
        "topic": "reflexive verbs",
        "formula": "me/te/se/nos + reflexive verb",
        "use": "Use reflexive pronouns when the subject does the action to itself or for daily routines.",
        "examples": ["Me levanto temprano.", "Te llamas Ana.", "Se ducha por la mañana."],
        "trap": "The reflexive pronoun changes with the subject.",
        "choose": ("Choose: I get up early.<br>A) Me levanto temprano.<br>B) Se levanto temprano.", "A) Me levanto temprano.", "yo uses me."),
        "correction": ("Yo se llamo Luis.", "Yo me llamo Luis.", "The yo reflexive pronoun is me."),
        "production": ("Write in Spanish: I call myself Ana / My name is Ana.", "Me llamo Ana.", "llamarse is reflexive for names."),
        "pattern": ("daily routine", "reflexive pronoun + verb", ["Me despierto.", "Te levantas.", "Se lava."]),
    },
    {
        "level": "a1_2_core_sentences",
        "topic": "direct object pronouns",
        "formula": "lo/la/los/las replace direct objects",
        "use": "Use direct object pronouns to avoid repeating the object.",
        "examples": ["Veo el libro -> Lo veo.", "Compro la camisa -> La compro.", "Leo los mensajes -> Los leo."],
        "trap": "The pronoun agrees with the object, not the subject.",
        "choose": ("Choose: I see the house -> ___ veo.<br>A) Lo<br>B) La", "B) La veo.", "casa is feminine singular."),
        "correction": ("Veo la película. Lo veo.", "Veo la película. La veo.", "película is feminine singular, so la."),
        "production": ("Write in Spanish: I read it. (it = el libro)", "Lo leo.", "libro is masculine singular."),
        "pattern": ("object before verb", "lo/la/los/las + conjugated verb", ["Lo quiero.", "La veo.", "Los compro."]),
    },
    {
        "level": "a2_1_daily_past",
        "topic": "regular preterite",
        "formula": "-ar: é, aste, ó, amos, aron; -er/-ir: í, iste, ió, imos, ieron",
        "use": "Use preterite for completed past actions.",
        "examples": ["Hablé con Ana.", "Comí arroz.", "Vivimos en Lima dos años."],
        "trap": "Present yo hablo is not past; use hablé.",
        "choose": ("Choose: Yesterday I studied.<br>A) Ayer estudio.<br>B) Ayer estudié.", "B) Ayer estudié.", "Ayer signals a completed past action."),
        "correction": ("Ayer trabajo mucho.", "Ayer trabajé mucho.", "Use preterite for completed action yesterday."),
        "production": ("Write in Spanish: I ate bread yesterday.", "Ayer comí pan.", "comer in yo preterite is comí."),
        "pattern": ("completed past", "preterite verb + past time", ["Ayer hablé.", "Anoche comí.", "El lunes trabajé."]),
    },
    {
        "level": "a2_1_daily_past",
        "topic": "irregular preterite",
        "formula": "ir/ser: fui; tener: tuve; hacer: hice; decir: dije",
        "use": "Common high-frequency verbs have irregular preterite forms.",
        "examples": ["Fui al mercado.", "Tuve una reunión.", "Hice la tarea.", "Dije la verdad."],
        "trap": "fui can mean I went or I was; context decides.",
        "choose": ("Choose: I went to the store.<br>A) Fui a la tienda.<br>B) Iba a la tienda.", "A) Fui a la tienda.", "A completed trip uses preterite."),
        "correction": ("Yo tení una reunión.", "Yo tuve una reunión.", "tener has irregular preterite tuve."),
        "production": ("Write in Spanish: I did the work.", "Hice el trabajo.", "hacer in yo preterite is hice."),
        "pattern": ("common irregular past", "fui/tuve/hice/dije + object/place", ["Fui a casa.", "Tuve tiempo.", "Dije no."]),
    },
    {
        "level": "a2_1_daily_past",
        "topic": "imperfect basics",
        "formula": "-aba for -ar; -ía for -er/-ir; era/iba/veía are key irregulars",
        "use": "Use imperfect for background, habits, descriptions, age, and ongoing past states.",
        "examples": ["Cuando era niño, vivía en Madrid.", "Estudiaba cada noche.", "Tenía diez años."],
        "trap": "Age in the past often uses imperfect: tenía.",
        "choose": ("Choose: When I was a child...<br>A) Cuando fui niño...<br>B) Cuando era niño...", "B) Cuando era niño...", "Background identity/description in the past uses imperfect."),
        "correction": ("Cuando tuve diez años, vivía en Chile.", "Cuando tenía diez años, vivía en Chile.", "Age as background uses imperfect."),
        "production": ("Write in Spanish: I used to study every night.", "Estudiaba cada noche.", "Repeated past habit uses imperfect."),
        "pattern": ("past habit/background", "imperfect + repeated/background context", ["Vivía allí.", "Trabajaba mucho.", "Era difícil."]),
    },
    {
        "level": "a2_1_daily_past",
        "topic": "preterite vs imperfect",
        "formula": "preterite = completed event; imperfect = background/habit/ongoing state",
        "use": "Choose past tense based on how the speaker frames the action.",
        "examples": ["Estudiaba cuando llamaste.", "Ayer estudié dos horas.", "Era tarde cuando salimos."],
        "trap": "The same verb can use either tense with different meaning.",
        "choose": ("Choose: I was studying when you called.<br>A) Estudiaba cuando llamaste.<br>B) Estudié cuando llamabas.", "A) Estudiaba cuando llamaste.", "Ongoing background uses imperfect; interrupting event uses preterite."),
        "correction": ("Ayer estudiaba dos horas.", "Ayer estudié dos horas.", "A completed measured action uses preterite."),
        "production": ("Write in Spanish: It was raining when I arrived.", "Llovía cuando llegué.", "Background weather uses imperfect; arrival is preterite."),
        "pattern": ("background + event", "imperfect cuando preterite", ["Comía cuando llamaste.", "Dormía cuando llegué.", "Trabajaba cuando empezó."]),
    },
    {
        "level": "a2_1_daily_past",
        "topic": "comparatives",
        "formula": "más/menos + adjective + que; tan + adjective + como",
        "use": "Use comparatives to compare people, things, or situations.",
        "examples": ["Madrid es más grande que Toledo.", "Este libro es menos caro.", "Ana es tan alta como Luis."],
        "trap": "Do not use más mejor; mejor already means better.",
        "choose": ("Choose: better than<br>A) más mejor que<br>B) mejor que", "B) mejor que", "mejor is already comparative."),
        "correction": ("Este café es más bueno.", "Este café es mejor.", "Use mejor for better."),
        "production": ("Write in Spanish: This book is more expensive than that one.", "Este libro es más caro que ese.", "más + adjective + que."),
        "pattern": ("comparison", "más/menos/tan + adjective + que/como", ["más rápido que", "menos caro que", "tan fácil como"]),
    },
    {
        "level": "a2_1_daily_past",
        "topic": "informal commands",
        "formula": "tú affirmative often uses él/ella present form: habla, come, escribe",
        "use": "Use informal commands to tell one person to do something.",
        "examples": ["Habla despacio.", "Come algo.", "Escribe tu nombre."],
        "trap": "Common irregulars: ven, di, sal, haz, ten, ve, pon, sé.",
        "choose": ("Choose: Speak slowly.<br>A) Habla despacio.<br>B) Hablas despacio.", "A) Habla despacio.", "Affirmative tú command of hablar is habla."),
        "correction": ("Comes algo.", "Come algo.", "The command form is come, not comes."),
        "production": ("Write in Spanish: Write your name.", "Escribe tu nombre.", "Affirmative tú command of escribir is escribe."),
        "pattern": ("tú command", "verb command + object/adverb", ["Lee esto.", "Escucha.", "Mira aquí."]),
    },
    {
        "level": "a2_2_natural_spanish",
        "topic": "por vs para",
        "formula": "para = purpose/destination/deadline; por = cause/exchange/path/duration",
        "use": "Choose por or para by the relationship between ideas.",
        "examples": ["Trabajo para aprender.", "Gracias por tu ayuda.", "Salimos para Madrid.", "Caminé por el parque."],
        "trap": "English for maps to both por and para.",
        "choose": ("Choose: I study to learn.<br>A) Estudio por aprender.<br>B) Estudio para aprender.", "B) Estudio para aprender.", "Purpose/goal uses para."),
        "correction": ("Gracias para tu ayuda.", "Gracias por tu ayuda.", "Cause/reason for thanks uses por."),
        "production": ("Write in Spanish: This gift is for Ana.", "Este regalo es para Ana.", "Recipient/destination uses para."),
        "pattern": ("purpose/reason", "para + goal; por + reason", ["para estudiar", "por eso", "por la mañana"]),
    },
    {
        "level": "a2_2_natural_spanish",
        "topic": "indirect object pronouns",
        "formula": "me, te, le, nos, les + verb",
        "use": "Use indirect object pronouns for to/for whom something happens.",
        "examples": ["Le escribo a Ana.", "Me das el libro.", "Nos mandan un mensaje."],
        "trap": "le/les are often clarified with a + person.",
        "choose": ("Choose: I write to Ana.<br>A) Le escribo a Ana.<br>B) La escribo a Ana.", "A) Le escribo a Ana.", "Writing to someone uses an indirect object pronoun."),
        "correction": ("Lo doy el libro a Juan.", "Le doy el libro a Juan.", "Juan receives the book, so use le."),
        "production": ("Write in Spanish: She gives me the key.", "Ella me da la llave.", "me is the indirect object pronoun for to me."),
        "pattern": ("recipient", "indirect object pronoun + verb + thing", ["Te mando un mensaje.", "Le doy agua.", "Nos explica la regla."]),
    },
    {
        "level": "a2_2_natural_spanish",
        "topic": "double object pronouns",
        "formula": "indirect + direct object pronoun; le/les -> se before lo/la/los/las",
        "use": "Use double object pronouns to replace both recipient and thing.",
        "examples": ["Doy el libro a Ana -> Se lo doy.", "Mando la carta a Luis -> Se la mando.", "Te lo explico."],
        "trap": "Do not say le lo; change le to se.",
        "choose": ("Choose: I give it to her.<br>A) Le lo doy.<br>B) Se lo doy.", "B) Se lo doy.", "le becomes se before lo."),
        "correction": ("Le la mando.", "Se la mando.", "le/les change to se before la."),
        "production": ("Write in Spanish: I explain it to you.", "Te lo explico.", "Indirect pronoun comes before direct pronoun."),
        "pattern": ("two pronouns", "me/te/se/nos + lo/la/los/las + verb", ["Me lo das.", "Se la compro.", "Nos los envían."]),
    },
    {
        "level": "a2_2_natural_spanish",
        "topic": "present progressive",
        "formula": "estar + gerundio (-ando/-iendo)",
        "use": "Use present progressive for actions happening right now.",
        "examples": ["Estoy estudiando.", "Está comiendo.", "Estamos escribiendo."],
        "trap": "Spanish uses simple present more often than English for general/current plans.",
        "choose": ("Choose: I am studying right now.<br>A) Estoy estudiando ahora.<br>B) Soy estudiando ahora.", "A) Estoy estudiando ahora.", "Progressive uses estar, not ser."),
        "correction": ("Estoy estudio.", "Estoy estudiando.", "After estar, use the gerund."),
        "production": ("Write in Spanish: We are eating.", "Estamos comiendo.", "estar + -iendo."),
        "pattern": ("right now", "estar + -ando/-iendo", ["Estoy hablando.", "Está leyendo.", "Estamos trabajando."]),
    },
    {
        "level": "a2_2_natural_spanish",
        "topic": "present perfect",
        "formula": "haber + participle: he/has/ha/hemos/han + -ado/-ido",
        "use": "Use present perfect for recent or experience-related past with present relevance.",
        "examples": ["He visto la película.", "Hemos terminado.", "¿Has comido?"],
        "trap": "Do not insert words between haber and the participle in basic Spanish.",
        "choose": ("Choose: I have finished.<br>A) He terminado.<br>B) Soy terminado.", "A) He terminado.", "Present perfect uses haber."),
        "correction": ("He visto ayer la película.", "Vi la película ayer.", "Ayer is a finished-time expression; use preterite."),
        "production": ("Write in Spanish: Have you eaten?", "¿Has comido?", "has + participle."),
        "pattern": ("recent/experience past", "haber + participle", ["He llegado.", "Has leído.", "Hemos hablado."]),
    },
    {
        "level": "a2_2_natural_spanish",
        "topic": "relative clauses and connectors",
        "formula": "que/donde connect clauses; porque/pero/aunque connect ideas",
        "use": "Use connectors to make longer but still controlled Spanish sentences.",
        "examples": ["El libro que compré es bueno.", "La casa donde vivo es pequeña.", "Estudio porque quiero mejorar."],
        "trap": "que is often enough for who/that/which at this level.",
        "choose": ("Choose: the book that I bought<br>A) el libro que compré<br>B) el libro quien compré", "A) el libro que compré", "Use que for things."),
        "correction": ("La casa que vivo es pequeña.", "La casa donde vivo es pequeña.", "Use donde for where/in which."),
        "production": ("Write in Spanish: I study because I want to improve.", "Estudio porque quiero mejorar.", "porque gives the reason."),
        "pattern": ("connected sentence", "clause + connector + clause", ["Quiero salir, pero trabajo.", "Estudio porque quiero aprender.", "Es difícil aunque es útil."]),
    },
]


CARD_TYPE_LABELS = {
    "rule": "Rule",
    "choose": "Choose",
    "correction": "Correction",
    "production": "Production",
    "pattern": "Mini pattern",
}


def _slug(text):
    return text.replace(" ", "_").replace("/", "_").replace("-", "_").lower()


def _tags(level, topic, card_type):
    return ["spanish_grammar", "grammar_maintenance", level, _slug(topic), card_type]


def _self_grade(card_type):
    if card_type == "rule":
        return "Good = remembered the formula and examples. Hard = remembered one part. Again = could not explain it."
    if card_type == "choose":
        return "Good = chose correctly and knew why. Hard = guessed correctly. Again = chose wrong."
    if card_type == "correction":
        return "Good = fixed it and named the rule. Hard = fixed it only. Again = missed the correction."
    if card_type == "production":
        return "Good = produced the target sentence. Hard = minor gender/accent/ending issue. Again = wrong pattern."
    if card_type == "pattern":
        return "Good = could reuse the pattern with a new word. Hard = recognized only. Again = did not remember it."
    return "Good = confident. Hard = partial. Again = missed it."


def _add(cards, level, topic, card_type, front, answer, explanation, examples=None, common_mistake=""):
    cards.append(
        {
            "source_id": f"{level}::{_slug(topic)}::{card_type}",
            "level": level,
            "topic": topic,
            "card_type": card_type,
            "front": front,
            "answer": answer,
            "explanation": explanation,
            "examples": "<br>".join(f"- {example}" for example in (examples or [])),
            "common_mistake": common_mistake,
            "self_grade": _self_grade(card_type),
            "tags": _tags(level, topic, card_type),
        }
    )


def _build_cards():
    cards = []
    for item in TOPICS:
        level = item["level"]
        topic = item["topic"]
        _add(
            cards,
            level,
            topic,
            "rule",
            f"Rule: {topic}",
            f"<b>Formula</b><br>{item['formula']}<br><br><b>Use</b><br>{item['use']}",
            "Memorize the pattern first; the other cards in this topic make you use it.",
            item["examples"],
            item["trap"],
        )
        choose_front, choose_answer, choose_reason = item["choose"]
        _add(cards, level, topic, "choose", choose_front, choose_answer, choose_reason, item["examples"], item["trap"])
        wrong, right, correction_reason = item["correction"]
        _add(cards, level, topic, "correction", f"Correct this Spanish: {wrong}", right, correction_reason, item["examples"], item["trap"])
        prompt, answer, note = item["production"]
        _add(cards, level, topic, "production", prompt, answer, note, item["examples"], item["trap"])
        pattern_name, pattern_formula, pattern_examples = item["pattern"]
        _add(
            cards,
            level,
            topic,
            "pattern",
            f"Mini pattern: {pattern_name}",
            pattern_formula,
            "This is a reusable sentence chunk. Practice swapping one word at a time.",
            pattern_examples,
            item["trap"],
        )
    return cards


SPANISH_GRAMMAR_CARDS = _build_cards()


def get_cards(level=None, card_type=None):
    result = []
    for card in SPANISH_GRAMMAR_CARDS:
        if level is not None and card["level"] != level:
            continue
        if card_type is not None and card["card_type"] != card_type:
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
            "card_count": len([card for card in SPANISH_GRAMMAR_CARDS if card["level"] == level["id"]]),
        }
        for level in LEVELS
    ]


def render_tsv(cards):
    header = ["#separator:tab", "#html:true"]
    rows = [
        [
            card["source_id"],
            card["level"],
            card["topic"],
            card["card_type"],
            CARD_TYPE_LABELS[card["card_type"]],
            card["front"],
            card["answer"],
            card["explanation"],
            card["examples"],
            card["common_mistake"],
            card["self_grade"],
            " ".join(card["tags"]),
        ]
        for card in cards
    ]
    with io.StringIO() as output:
        writer = csv.writer(output, delimiter="\t", lineterminator="\n")
        for line in header:
            output.write(f"{line}\n")
        writer.writerow(
            [
                "SourceID",
                "Level",
                "Topic",
                "CardType",
                "CardTypeLabel",
                "Front",
                "Answer",
                "Explanation",
                "Examples",
                "CommonMistake",
                "SelfGrade",
                "Tags",
            ]
        )
        writer.writerows(rows)
        return output.getvalue()


def write_import_files(output_dir="generated/spanish_grammar"):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    path = output_path / "spanish_grammar_a0_a2.tsv"
    path.write_text(render_tsv(get_cards()), encoding="utf-8")
    return str(path)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Generate A0-A2 Spanish grammar Anki deck TSV.")
    parser.add_argument("--output-dir", default="generated/spanish_grammar", help="Output directory")
    parser.add_argument("--summary", action="store_true", help="Print level/card summary")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.summary:
        for item in get_level_summary():
            print(f"{item['id']}: {item['card_count']} cards")
        print(f"total: {len(get_cards())} cards")
        return 0
    path = write_import_files(args.output_dir)
    print(f"Wrote import file: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
