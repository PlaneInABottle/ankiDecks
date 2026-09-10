"""Generate Turkish cue data for English 4000 production cards."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List

import spanish_deck


OUTPUT_PATH = Path("generated/english_4000/english_turkish_production.tsv")
REVIEWED_ENGLISH_PATH = Path("generated/spanish_full/english_spanish_review.tsv")
CACHE_PATH = Path("generated/english_4000/mymemory_cache.json")
GOOGLE_CACHE_PATH = Path("generated/english_4000/google_translate_cache.json")
MYMEMORY_URL = "https://api.mymemory.translated.net/get"
GOOGLE_TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
GOOGLE_BATCH_SIZE = 80

SOURCE_SPECIFIC_TURKISH_OVERRIDES = {
    ("4000 Essential English Words::1.Book", "", "agree"): "katılmak / aynı fikirde olmak",
    ("4000 Essential English Words::1.Book", "", "boat"): "tekne",
    ("4000 Essential English Words::1.Book", "", "capital"): "başkent",
    ("4000 Essential English Words::1.Book", "", "evil"): "kötü / zalim",
    ("4000 Essential English Words::1.Book", "", "bad"): "kötü / fena",
    ("4000 Essential English Words::1.Book", "", "laugh"): "gülüş",
    ("4000 Essential English Words::1.Book", "", "view"): "bakmak",
    ("4000 Essential English Words::1.Book", "", "avoid"): "kaçınmak",
    ("4000 Essential English Words::1.Book", "", "content"): "memnun / hâlinden hoşnut",
    ("4000 Essential English Words::1.Book", "", "glad"): "memnun / sevinçli",
    ("4000 Essential English Words::1.Book", "", "expect"): "beklemek",
    ("4000 Essential English Words::1.Book", "", "grade"): "not",
    ("4000 Essential English Words::1.Book", "", "secret"): "sır",
    ("4000 Essential English Words::1.Book", "", "ever"): "herhangi bir zaman",
    ("4000 Essential English Words::1.Book", "", "instead"): "yerine",
    ("4000 Essential English Words::1.Book", "", "football"): "amerikan futbolu",
    ("4000 Essential English Words::1.Book", "", "sense"): "sezmek",
    ("4000 Essential English Words::1.Book", "", "appeal"): "çekici gelmek",
    ("4000 Essential English Words::1.Book", "", "found"): "kurmak",
    ("4000 Essential English Words::1.Book", "", "direct"): "doğrudan",
    ("4000 Essential English Words::1.Book", "", "sheet"): "sayfa",
    ("4000 Essential English Words::1.Book", "", "across"): "karşıya geçmek",
    ("4000 Essential English Words::1.Book", "", "happen"): "tesadüfen / denk gelmek",
    ("4000 Essential English Words::1.Book", "", "bother"): "zahmet etmek",
    ("4000 Essential English Words::1.Book", "", "fashionable"): "modaya uygun",
    ("4000 Essential English Words::1.Book", "", "frequently"): "sık sık / sıklıkla",
    ("4000 Essential English Words::1.Book", "", "shake"): "el sıkışmak / tokalaşmak",
    ("4000 Essential English Words::1.Book", "", "divide"): "bölmek / paylaştırmak",
    ("4000 Essential English Words::1.Book", "", "profit"): "kâr / kazanç",
    ("4000 Essential English Words::1.Book", "", "dull"): "sıkıcı / heyecansız",
    ("4000 Essential English Words::1.Book", "", "former"): "önceki / artık olmayan",
    ("4000 Essential English Words::1.Book", "", "loan"): "borç / kredi",
    ("4000 Essential English Words::1.Book", "", "practical"): "kullanışlı / yararlı / pratik",
    ("4000 Essential English Words::1.Book", "", "urge"): "ısrar etmek / teşvik etmek",
    ("4000 Essential English Words::1.Book", "", "limit"): "sınır / limit",
    ("4000 Essential English Words::1.Book", "", "fortunate"): "şanslı / talihli",
    ("4000 Essential English Words::1.Book", "", "available"): "mevcut / müsait / kullanılabilir",
    ("4000 Essential English Words::1.Book", "", "whether"): "olup olmadığı / -ip -mediği",
    ("4000 Essential English Words::Extra", "2_6", "boxers"): "boxer külot",
    ("4000 Essential English Words::Extra", "2_7", "cap"): "şapka",
    ("4000 Essential English Words::Extra", "2_40", "suit"): "takım elbise",
    ("4000 Essential English Words::Extra", "2_45", "tie"): "kravat",
    ("4000 Essential English Words::Extra", "3_52", "cricket"): "cırcır böceği",
    ("4000 Essential English Words::Extra", "3_75", "peanut"): "yer fıstığı",
    ("4000 Essential English Words::Extra", "3_77", "pistachio"): "antep fıstığı",
    ("4000 Essential English Words::Extra", "3_80", "beef"): "sığır eti",
    ("4000 Essential English Words::Extra", "3_116", "football"): "amerikan futbolu",
    ("4000 Essential English Words::Extra", "3_30", "seal"): "fok",
    ("4000 Essential English Words::Extra", "3_42", "mole"): "köstebek",
    ("4000 Essential English Words::Extra", "1_1_2", "temple"): "şakak",
    ("4000 Essential English Words::Extra", "1_1_17", "head"): "kafa",
    ("4000 Essential English Words::Extra", "1_1_22", "stomach"): "mide",
    ("4000 Essential English Words::Extra", "1_1_34", "palm"): "avuç içi",
    ("4000 Essential English Words::Extra", "1_1_40", "back"): "sırt",
    ("4000 Essential English Words::Extra", "1_1_41", "hip"): "kalça",
    ("4000 Essential English Words::Extra", "1_1_42", "bottom"): "kalça",
    ("4000 Essential English Words::Extra", "1_1_75", "navy"): "lacivert",
    ("4000 Essential English Words::3.Book", "", "found"): "kurmak",
    ("4000 Essential English Words::4.Book", "", "tie"): "bağlamak",
    ("4000 Essential English Words::4.Book", "", "found"): "dayandırmak",
    ("4000 Essential English Words::1.Book", "", "specific"): "spesifik / belirli",
    ("4000 Essential English Words::4.Book", "", "precise"): "kesin / net",
    ("4000 Essential English Words::4.Book", "", "explicit"): "açık / net",
    ("4000 Essential English Words::4.Book", "", "enroll"): "kaydolmak",
    ("4000 Essential English Words::1.Book", "", "clerk"): "mağaza görevlisi / satış görevlisi",
    ("4000 Essential English Words::1.Book", "", "locate"): "yerini bulmak / konumunu tespit etmek",
    ("4000 Essential English Words::1.Book", "", "earn"): "para kazanmak",
    ("4000 Essential English Words::1.Book", "", "safety"): "güvenlik / sağlamlık",
    ("4000 Essential English Words::1.Book", "", "perform"): "sahnelemek / icra etmek",
    ("4000 Essential English Words::1.Book", "", "strike"): "saldırmak / vurmak",
    ("4000 Essential English Words::1.Book", "", "term"): "terim / sözcük",
    ("4000 Essential English Words::1.Book", "", "recognize"): "tanımak / hatırlamak",
    ("4000 Essential English Words::1.Book", "", "along"): "birlikte / yanında",
    ("4000 Essential English Words::1.Book", "", "attract"): "cezbetmek / ilgisini çekmek",
    ("4000 Essential English Words::1.Book", "", "maintain"): "sürdürmek / düzenli bakmak",
    ("4000 Essential English Words::1.Book", "", "neither"): "hiçbiri / ne o ne bu",
    ("4000 Essential English Words::1.Book", "", "situated"): "yer almak / bulunmak",
    ("4000 Essential English Words::1.Book", "", "false"): "yanlış / sahte",
    ("4000 Essential English Words::1.Book", "", "figure out"): "çözmek / anlamak",
    ("4000 Essential English Words::1.Book", "", "rather"): "daha doğrusu / tercihen",
    ("4000 Essential English Words::1.Book", "", "band"): "müzik grubu / bant",
    ("4000 Essential English Words::1.Book", "", "barely"): "zar zor / anca",
    ("4000 Essential English Words::1.Book", "", "schedule"): "program / takvim",
    ("4000 Essential English Words::1.Book", "", "burden"): "yük / sorumluluk",
    ("4000 Essential English Words::1.Book", "", "compromise"): "ödün vermek / uzlaşmak",
    ("4000 Essential English Words::1.Book", "", "meeting"): "toplantı / buluşma",
    ("4000 Essential English Words::1.Book", "", "moderate"): "ılımlı / ne az ne fazla",
    ("4000 Essential English Words::1.Book", "", "settle"): "uzlaşmak / sonuca erdirmek",
    ("4000 Essential English Words::1.Book", "", "demonstrate"): "göstermek / sunmak",
    ("4000 Essential English Words::1.Book", "", "december"): "Aralık ayı",
    ("4000 Essential English Words::1.Book", "", "actual"): "gerçek / asıl / gerçeğe dayalı",
    ("4000 Essential English Words::2.Book", "", "factual"): "olgusal / gerçeklere dayalı",
    ("4000 Essential English Words::1.Book", "", "basic"): "temel / basit",
    ("4000 Essential English Words::2.Book", "", "basis"): "temel / dayanak",
    ("4000 Essential English Words::2.Book", "", "elementary"): "temel / basit düzey",
    ("4000 Essential English Words::1.Book", "", "plate"): "tabak",
    ("4000 Essential English Words::1.Book", "", "pole"): "direk / sırık",
    ("4000 Essential English Words::1.Book", "", "pressure"): "baskı / basınç",
    ("4000 Essential English Words::1.Book", "", "tip"): "uç",
    ("4000 Essential English Words::1.Book", "", "lack"): "eksiklik / yetersizlik",
    ("4000 Essential English Words::1.Book", "", "medicine"): "ilaç",
    ("4000 Essential English Words::1.Book", "", "mix"): "karışım",
    ("4000 Essential English Words::1.Book", "", "populate"): "yaşamak / yerleşmek",
    ("4000 Essential English Words::1.Book", "", "dive"): "dalmak",
    ("4000 Essential English Words::1.Book", "", "craft"): "ustalıkla yapmak / imal etmek",
    ("4000 Essential English Words::1.Book", "", "own"): "sahip olmak",
    ("4000 Essential English Words::2.Book", "", "possess"): "elinde bulundurmak / sahip olmak",
    ("4000 Essential English Words::1.Book", "", "thin"): "zayıf / ince",
    ("4000 Essential English Words::2.Book", "", "line"): "sıra / çizgi",
    ("4000 Essential English Words::2.Book", "", "log"): "kütük",
    ("4000 Essential English Words::2.Book", "", "destination"): "varış noktası / hedef",
    ("4000 Essential English Words::1.Book", "", "customer"): "mağaza müşterisi",
    ("4000 Essential English Words::1.Book", "", "client"): "müşteri / danışan",
    ("4000 Essential English Words::1.Book", "", "social"): "toplumsal / sosyal",
    ("4000 Essential English Words::1.Book", "", "sociable"): "girişken / sosyal",
    ("4000 Essential English Words::2.Book", "", "violent"): "şiddet kullanan / vahşi",
    ("4000 Essential English Words::2.Book", "", "severe"): "ciddi / ağır / şiddetli",
    ("4000 Essential English Words::1.Book", "", "consume"): "tüketmek / yiyip içmek",
    ("4000 Essential English Words::2.Book", "", "exhaust"): "yormak / bitkin düşürmek",
    ("4000 Essential English Words::2.Book", "", "study"): "ders çalışmak / incelemek",
    ("4000 Essential English Words::2.Book", "", "work"): "çalışmak / iş yapmak",
    ("4000 Essential English Words::2.Book", "", "household"): "hane / ev halkı",
    ("4000 Essential English Words::1.Book", "", "speed"): "hız yapmak / hız",
    ("4000 Essential English Words::1.Book", "", "range"): "aralık / yelpaze",
    ("4000 Essential English Words::1.Book", "", "scene"): "sahne / bölüm",
    ("4000 Essential English Words::1.Book", "", "stage"): "sahne / platform",
    # High-confidence sense corrections from the source definitions/examples.
    ("4000 Essential English Words::1.Book", "", "season"): "mevsim",
    ("4000 Essential English Words::1.Book", "", "worth"): "değerinde olmak",
    ("4000 Essential English Words::1.Book", "", "lead"): "yol göstermek / önden götürmek",
    ("4000 Essential English Words::2.Book", "", "firm"): "sert / sıkı",
    ("4000 Essential English Words::3.Book", "", "shortly"): "birazdan / yakında",
    ("4000 Essential English Words::3.Book", "", "volume"): "miktar / yoğunluk",
    ("4000 Essential English Words::4.Book", "", "tool"): "araç",
    ("4000 Essential English Words::4.Book", "", "case"): "durum / örnek",
    ("4000 Essential English Words::4.Book", "", "quote"): "alıntı / fiyat teklifi",
    ("4000 Essential English Words::4.Book", "", "inhale"): "içine çekmek / solumak",
    ("4000 Essential English Words::5.Book", "", "compliance"): "kurallara uyma / itaat",
    ("4000 Essential English Words::5.Book", "", "sentence"): "ceza / hüküm",
    ("4000 Essential English Words::5.Book", "", "linger"): "uzun süre kalmak / sürmek",
    ("4000 Essential English Words::6.Book", "", "faculty"): "yeti / yetenek",
    ("4000 Essential English Words::6.Book", "", "soundly"): "kesin biçimde / açık farkla",
    ("4000 Essential English Words::6.Book", "", "humor"): "ruh hâli",
    # Reviewed Turkish cues aligned to the exact source sense.
    ("4000 Essential English Words::1.Book", "", "stroll"): "ağır ağır yürümek / dolaşmak",
    ("4000 Essential English Words::1.Book", "", "depend"): "dayanmak / ihtiyaç duymak",
    ("4000 Essential English Words::1.Book", "", "base"): "taban / alt kısım",
    ("4000 Essential English Words::1.Book", "", "organize"): "düzenlemek / organize etmek",
    ("4000 Essential English Words::1.Book", "", "cost"): "mal olmak / tutmak",
    ("4000 Essential English Words::2.Book", "", "consequence"): "sonuç",
    ("4000 Essential English Words::2.Book", "", "incredible"): "inanılmaz / olağanüstü",
    ("4000 Essential English Words::2.Book", "", "can"): "-ebilmek / yapabilmek",
    ("4000 Essential English Words::2.Book", "", "clear"): "boşaltmak / temizlemek",
    ("4000 Essential English Words::2.Book", "", "depart"): "ayrılmak / yola çıkmak",
    ("4000 Essential English Words::2.Book", "", "nevertheless"): "yine de / buna rağmen",
    ("4000 Essential English Words::2.Book", "", "ruins"): "harabeler / kalıntılar",
    ("4000 Essential English Words::2.Book", "", "significant"): "önemli / kayda değer",
    ("4000 Essential English Words::2.Book", "", "capable"): "yetenekli / yapabilecek durumda",
    ("4000 Essential English Words::2.Book", "", "convey"): "iletmek / aktarmak",
    ("4000 Essential English Words::2.Book", "", "delight"): "sevinç / mutluluk",
    ("4000 Essential English Words::2.Book", "", "against"): "-e karşı / -e yaslanmış",
    ("4000 Essential English Words::2.Book", "", "prevent"): "önlemek",
    ("4000 Essential English Words::2.Book", "", "enormous"): "devasa / çok büyük",
    ("4000 Essential English Words::2.Book", "", "extraordinary"): "olağanüstü / sıra dışı",
    ("4000 Essential English Words::2.Book", "", "mad"): "öfkeli / kızgın",
    ("4000 Essential English Words::2.Book", "", "trap"): "tuzağa düşürmek / yakalamak",
    ("4000 Essential English Words::2.Book", "", "trial"): "yargılama / dava",
    ("4000 Essential English Words::2.Book", "", "admission"): "giriş izni / kabul",
    ("4000 Essential English Words::2.Book", "", "forecast"): "hava tahmini",
    ("4000 Essential English Words::2.Book", "", "afford"): "parası yetmek / karşılayabilmek",
    ("4000 Essential English Words::2.Book", "", "mess"): "dağınıklık",
    ("4000 Essential English Words::2.Book", "", "fortune"): "talih",
    ("4000 Essential English Words::3.Book", "", "engineer"): "tasarlamak / ustaca planlamak",
    ("4000 Essential English Words::3.Book", "", "kid"): "şaka yapmak",
    ("4000 Essential English Words::3.Book", "", "disguise"): "kılık / kılık değiştirme",
    ("4000 Essential English Words::3.Book", "", "puff"): "bir tutam / duman bulutu",
    ("4000 Essential English Words::3.Book", "", "stem"): "gövde / sap",
    ("4000 Essential English Words::3.Book", "", "howl"): "ulumak",
    ("4000 Essential English Words::3.Book", "", "peer"): "dikkatle bakmak",
    ("4000 Essential English Words::3.Book", "", "consequent"): "sonuç olarak ortaya çıkan",
    ("4000 Essential English Words::3.Book", "", "curve"): "kavis çizmek / eğrilmek",
    ("4000 Essential English Words::4.Book", "", "practice"): "alışkanlık / uygulama",
    ("4000 Essential English Words::4.Book", "", "verify"): "doğrulamak / teyit etmek",
    ("4000 Essential English Words::4.Book", "", "render"): "hâle getirmek",
    ("4000 Essential English Words::4.Book", "", "upgrade"): "geliştirmek / yükseltmek",
    ("4000 Essential English Words::4.Book", "", "utensil"): "mutfak gereci / araç",
    ("4000 Essential English Words::4.Book", "", "crisp"): "çıtır / gevrek",
    ("4000 Essential English Words::5.Book", "", "review"): "inceleme / değerlendirme",
    ("4000 Essential English Words::6.Book", "", "nick"): "hafifçe kesmek / çizmek",
    ("4000 Essential English Words::6.Book", "", "orbit"): "yörüngede dönmek",
    ("4000 Essential English Words::6.Book", "", "tract"): "geniş arazi / bölge",
    ("4000 Essential English Words::6.Book", "", "amend"): "düzeltmek / iyileştirmek",
    # Manual sense fixes (2026-09-10 audit): bare-word Google output had picked
    # the wrong sense or wrong part-of-speech form for these definitions.
    ("4000 Essential English Words::4.Book", "", "coin"): "türetmek / yeni sözcük üretmek",
    ("4000 Essential English Words::2.Book", "", "branch"): "dal",
    ("4000 Essential English Words::5.Book", "", "pity"): "acıma",
    ("4000 Essential English Words::4.Book", "", "straightforward"): "anlaşılır / kolay anlaşılır",
    ("4000 Essential English Words::4.Book", "", "vocal"): "fikrini açıkça dile getiren",
    ("4000 Essential English Words::4.Book", "", "leading"): "öncü / lider",
    ("4000 Essential English Words::Extra", "3_79", "bacon"): "domuz pastırması",
    ("4000 Essential English Words::6.Book", "", "imperial"): "imparatorlukla ilgili",
    ("4000 Essential English Words::6.Book", "", "upcoming"): "yaklaşan",
    ("4000 Essential English Words::4.Book", "", "bankrupt"): "iflas etmiş / müflis",
    ("4000 Essential English Words::3.Book", "", "bench"): "bank",
    # Full-deck audit 2026-09-10 (part 2): every card read against its book
    # definition. Bare-word machine output had the wrong sense or form.
    # 1.Book
    ("4000 Essential English Words::1.Book", "", "bury"): "gömmek",
    ("4000 Essential English Words::1.Book", "", "gulf"): "görüş ayrılığı",
    ("4000 Essential English Words::1.Book", "", "space"): "boş alan",
    ("4000 Essential English Words::1.Book", "", "downtown"): "şehir merkezi",
    ("4000 Essential English Words::1.Book", "", "sheet"): "kağıt",
    ("4000 Essential English Words::1.Book", "", "instrument"): "alet / araç",
    ("4000 Essential English Words::1.Book", "", "lay"): "koymak",
    ("4000 Essential English Words::1.Book", "", "set"): "koymak",
    ("4000 Essential English Words::1.Book", "", "cheer"): "tezahürat yapmak",
    ("4000 Essential English Words::1.Book", "", "silly"): "saçma",
    ("4000 Essential English Words::1.Book", "", "from"): "-den / -dan",
    ("4000 Essential English Words::1.Book", "", "though"): "olsa da",
    ("4000 Essential English Words::1.Book", "", "bite"): "ısırma",
    ("4000 Essential English Words::1.Book", "", "january"): "Ocak",
    # 2.Book
    ("4000 Essential English Words::2.Book", "", "ought"): "-meli / -malı",
    ("4000 Essential English Words::2.Book", "", "grand"): "görkemli / büyük",
    ("4000 Essential English Words::2.Book", "", "save"): "kurtarmak",
    ("4000 Essential English Words::2.Book", "", "rid"): "kurtarmak",
    ("4000 Essential English Words::2.Book", "", "dine"): "akşam yemeği yemek",
    ("4000 Essential English Words::2.Book", "", "compose"): "oluşturmak",
    ("4000 Essential English Words::2.Book", "", "cast"): "fırlatmak",
    ("4000 Essential English Words::2.Book", "", "bend"): "bükmek",
    ("4000 Essential English Words::2.Book", "", "swing"): "sallamak",
    ("4000 Essential English Words::2.Book", "", "engage"): "uğraşmak / girişmek",
    ("4000 Essential English Words::2.Book", "", "officer"): "subay",
    ("4000 Essential English Words::2.Book", "", "carriage"): "fayton",
    ("4000 Essential English Words::2.Book", "", "junior"): "küçük / ast",
    ("4000 Essential English Words::2.Book", "", "element"): "unsur",
    ("4000 Essential English Words::2.Book", "", "mineral"): "mineral",
    ("4000 Essential English Words::2.Book", "", "tissue"): "kağıt mendil",
    ("4000 Essential English Words::2.Book", "", "yard"): "bahçe",
    ("4000 Essential English Words::2.Book", "", "dish"): "yemek çeşidi",
    ("4000 Essential English Words::2.Book", "", "fantastic"): "harika",
    ("4000 Essential English Words::2.Book", "", "pot"): "tencere",
    ("4000 Essential English Words::2.Book", "", "sort"): "çeşit / tür",
    ("4000 Essential English Words::2.Book", "", "basin"): "leğen",
    ("4000 Essential English Words::2.Book", "", "terror"): "dehşet",
    ("4000 Essential English Words::2.Book", "", "still"): "hâlâ",
    ("4000 Essential English Words::2.Book", "", "metal"): "metal",
    ("4000 Essential English Words::2.Book", "", "initial"): "ilk",
    ("4000 Essential English Words::2.Book", "", "vision"): "görme",
    ("4000 Essential English Words::2.Book", "", "sleeve"): "kol",
    ("4000 Essential English Words::2.Book", "", "intelligence"): "zeka",
    ("4000 Essential English Words::2.Book", "", "stable"): "sabit / sağlam",
    ("4000 Essential English Words::2.Book", "", "disabled"): "engelli",
    # 3.Book
    ("4000 Essential English Words::3.Book", "", "ashamed"): "utanmış",
    ("4000 Essential English Words::3.Book", "", "aboard"): "gemide / uçakta",
    ("4000 Essential English Words::3.Book", "", "might"): "güç",
    ("4000 Essential English Words::3.Book", "", "royal"): "kraliyete ait",
    ("4000 Essential English Words::3.Book", "", "entire"): "bütün",
    ("4000 Essential English Words::3.Book", "", "execute"): "idam etmek",
    ("4000 Essential English Words::3.Book", "", "occupy"): "oturmak",
    ("4000 Essential English Words::3.Book", "", "tease"): "alay etmek / takılmak",
    ("4000 Essential English Words::3.Book", "", "abandon"): "terk etmek",
    ("4000 Essential English Words::3.Book", "", "restore"): "eski haline getirmek",
    ("4000 Essential English Words::3.Book", "", "dissolve"): "çözmek",
    ("4000 Essential English Words::3.Book", "", "assure"): "güvence vermek",
    ("4000 Essential English Words::3.Book", "", "dismiss"): "önemsememek / geçiştirmek",
    ("4000 Essential English Words::3.Book", "", "navigate"): "yön bulmak",
    ("4000 Essential English Words::3.Book", "", "yield"): "teslim olmak / bırakmak",
    ("4000 Essential English Words::3.Book", "", "sneak"): "gizlice sokulmak",
    ("4000 Essential English Words::3.Book", "", "spare"): "ihtiyaç fazlasını vermek",
    ("4000 Essential English Words::3.Book", "", "accommodate"): "yer sağlamak / barındırmak",
    ("4000 Essential English Words::3.Book", "", "commission"): "görevlendirmek",
    ("4000 Essential English Words::3.Book", "", "gaze"): "dik dik bakmak",
    ("4000 Essential English Words::3.Book", "", "glance"): "göz atmak",
    ("4000 Essential English Words::3.Book", "", "sole"): "tek",
    ("4000 Essential English Words::3.Book", "", "caretaker"): "bakıcı",
    ("4000 Essential English Words::3.Book", "", "inferior"): "kalitesiz",
    ("4000 Essential English Words::3.Book", "", "decent"): "makul / yeterli",
    ("4000 Essential English Words::3.Book", "", "valentine"): "sevgili",
    ("4000 Essential English Words::3.Book", "", "inhabitant"): "sakin",
    ("4000 Essential English Words::3.Book", "", "shed"): "baraka",
    ("4000 Essential English Words::3.Book", "", "wagon"): "yük arabası",
    ("4000 Essential English Words::3.Book", "", "kit"): "takım / set",
    ("4000 Essential English Words::3.Book", "", "vessel"): "gemi",
    ("4000 Essential English Words::3.Book", "", "chef"): "aşçı",
    ("4000 Essential English Words::3.Book", "", "massive"): "devasa",
    ("4000 Essential English Words::3.Book", "", "affair"): "olay / mesele",
    ("4000 Essential English Words::3.Book", "", "assembly"): "toplantı / kurul",
    ("4000 Essential English Words::3.Book", "", "nut"): "kuruyemiş",
    ("4000 Essential English Words::3.Book", "", "scheme"): "plan / tertip",
    ("4000 Essential English Words::3.Book", "", "straw"): "pipet",
    ("4000 Essential English Words::3.Book", "", "cliff"): "yar",
    ("4000 Essential English Words::3.Book", "", "tender"): "yumuşak",
    ("4000 Essential English Words::3.Book", "", "cottage"): "kır evi",
    ("4000 Essential English Words::3.Book", "", "prospect"): "beklenti / olasılık",
    ("4000 Essential English Words::3.Book", "", "bargain"): "kelepir",
    ("4000 Essential English Words::3.Book", "", "volume"): "miktar / hacim",
    ("4000 Essential English Words::3.Book", "", "drain"): "gider",
    ("4000 Essential English Words::3.Book", "", "fuse"): "fitil",
    ("4000 Essential English Words::3.Book", "", "paste"): "macun",
    ("4000 Essential English Words::3.Book", "", "chill"): "ürperti",
    ("4000 Essential English Words::3.Book", "", "limb"): "kalın dal",
    ("4000 Essential English Words::3.Book", "", "overnight"): "bir gecede",
    ("4000 Essential English Words::3.Book", "", "absence"): "yokluk",
    ("4000 Essential English Words::3.Book", "", "relief"): "rahatlama",
    ("4000 Essential English Words::3.Book", "", "bitter"): "kırgın",
    ("4000 Essential English Words::3.Book", "", "domestic"): "iç / yerli",
    ("4000 Essential English Words::3.Book", "", "mercy"): "merhamet",
    ("4000 Essential English Words::3.Book", "", "sympathy"): "şefkat",
    # 4.Book
    ("4000 Essential English Words::4.Book", "", "corrupt"): "yolsuz",
    ("4000 Essential English Words::4.Book", "", "inhibit"): "engellemek",
    ("4000 Essential English Words::4.Book", "", "ongoing"): "devam eden",
    ("4000 Essential English Words::4.Book", "", "forthcoming"): "gelmekte olan",
    ("4000 Essential English Words::4.Book", "", "whereby"): "vasıtasıyla",
    ("4000 Essential English Words::4.Book", "", "ashore"): "karaya",
    ("4000 Essential English Words::4.Book", "", "stranded"): "mahsur kalmış",
    ("4000 Essential English Words::4.Book", "", "interpret"): "yorumlamak",
    ("4000 Essential English Words::4.Book", "", "albeit"): "-e rağmen",
    ("4000 Essential English Words::4.Book", "", "select"): "seçmek",
    ("4000 Essential English Words::4.Book", "", "assign"): "atamak",
    ("4000 Essential English Words::4.Book", "", "misguided"): "yanlış yönlendirilmiş",
    ("4000 Essential English Words::4.Book", "", "urban"): "kentsel",
    ("4000 Essential English Words::4.Book", "", "known"): "bilinen",
    ("4000 Essential English Words::4.Book", "", "key"): "kilit / çok önemli",
    ("4000 Essential English Words::4.Book", "", "lunar"): "aya ait",
    ("4000 Essential English Words::4.Book", "", "viable"): "uygulanabilir",
    ("4000 Essential English Words::4.Book", "", "frantic"): "paniklemiş",
    ("4000 Essential English Words::4.Book", "", "respective"): "her birine ait",
    ("4000 Essential English Words::4.Book", "", "metropolitan"): "büyükşehre ait",
    ("4000 Essential English Words::4.Book", "", "refine"): "iyileştirmek",
    ("4000 Essential English Words::4.Book", "", "expel"): "kovmak / çıkarmak",
    ("4000 Essential English Words::4.Book", "", "signify"): "simgelemek",
    ("4000 Essential English Words::4.Book", "", "theorize"): "kuram geliştirmek",
    ("4000 Essential English Words::4.Book", "", "prevail"): "kabul görmek / yaygın olmak",
    ("4000 Essential English Words::4.Book", "", "marshal"): "toplayıp düzene sokmak",
    ("4000 Essential English Words::4.Book", "", "pledge"): "söz vermek",
    ("4000 Essential English Words::4.Book", "", "invoke"): "ileri sürmek / dayanak göstermek",
    ("4000 Essential English Words::4.Book", "", "cram"): "tıkıştırmak",
    ("4000 Essential English Words::4.Book", "", "subscribe"): "benimsemek / katılmak",
    ("4000 Essential English Words::4.Book", "", "keep"): "sürdürmek",
    ("4000 Essential English Words::4.Book", "", "enable"): "olanak sağlamak",
    ("4000 Essential English Words::4.Book", "", "prompt"): "sevk etmek",
    ("4000 Essential English Words::4.Book", "", "align"): "yanında yer almak / desteklemek",
    ("4000 Essential English Words::4.Book", "", "foster"): "geliştirmek / desteklemek",
    ("4000 Essential English Words::4.Book", "", "soar"): "hızla yükselmek",
    ("4000 Essential English Words::4.Book", "", "mark"): "anmak / kutlamak",
    ("4000 Essential English Words::4.Book", "", "hold"): "sahip olmak",
    ("4000 Essential English Words::4.Book", "", "keen"): "zeki",
    ("4000 Essential English Words::4.Book", "", "psychic"): "medyum",
    ("4000 Essential English Words::4.Book", "", "stroke"): "fırça darbesi",
    ("4000 Essential English Words::4.Book", "", "tribute"): "hürmet / saygı",
    ("4000 Essential English Words::4.Book", "", "creation"): "eser",
    ("4000 Essential English Words::4.Book", "", "aspect"): "yön",
    ("4000 Essential English Words::4.Book", "", "asset"): "değer",
    ("4000 Essential English Words::4.Book", "", "outlook"): "bakış açısı",
    ("4000 Essential English Words::4.Book", "", "extension"): "ek / uzantı",
    ("4000 Essential English Words::4.Book", "", "utility"): "kamu hizmeti",
    ("4000 Essential English Words::4.Book", "", "pioneer"): "çığır açan",
    ("4000 Essential English Words::4.Book", "", "transplant"): "nakil",
    ("4000 Essential English Words::4.Book", "", "counterpart"): "muadil",
    ("4000 Essential English Words::4.Book", "", "individual"): "birey",
    ("4000 Essential English Words::4.Book", "", "major"): "büyük / önemli",
    ("4000 Essential English Words::4.Book", "", "practitioner"): "hekim",
    ("4000 Essential English Words::4.Book", "", "provision"): "sağlama / tedarik",
    ("4000 Essential English Words::4.Book", "", "interchange"): "fikir alışverişi",
    ("4000 Essential English Words::4.Book", "", "scrap"): "kağıt parçası",
    ("4000 Essential English Words::4.Book", "", "wild"): "yabani",
    ("4000 Essential English Words::4.Book", "", "fat"): "yağ",
    ("4000 Essential English Words::4.Book", "", "integrity"): "dürüstlük",
    ("4000 Essential English Words::4.Book", "", "mandarin"): "mandarin çincesi",
    ("4000 Essential English Words::4.Book", "", "veteran"): "deneyimli",
    ("4000 Essential English Words::4.Book", "", "artery"): "atardamar",
    # 5.Book
    ("4000 Essential English Words::5.Book", "", "condensed"): "yoğunlaştırılmış",
    ("4000 Essential English Words::5.Book", "", "escape"): "kaçmak",
    ("4000 Essential English Words::5.Book", "", "horrified"): "dehşete düşmüş",
    ("4000 Essential English Words::5.Book", "", "typewritten"): "daktiloyla yazılmış",
    ("4000 Essential English Words::5.Book", "", "impending"): "olmak üzere olan",
    ("4000 Essential English Words::5.Book", "", "stricken"): "yakalanmış / tutulmuş",
    ("4000 Essential English Words::5.Book", "", "extinct"): "nesli tükenmiş",
    ("4000 Essential English Words::5.Book", "", "omit"): "dışarıda bırakmak",
    ("4000 Essential English Words::5.Book", "", "skill"): "beceri",
    ("4000 Essential English Words::5.Book", "", "doomed"): "mahvolmaya mahkum",
    ("4000 Essential English Words::5.Book", "", "sheer"): "tam / mutlak",
    ("4000 Essential English Words::5.Book", "", "martial"): "savaşla ilgili",
    ("4000 Essential English Words::5.Book", "", "solar"): "güneşle ilgili",
    ("4000 Essential English Words::5.Book", "", "animate"): "canlı",
    ("4000 Essential English Words::5.Book", "", "vain"): "kibirli",
    ("4000 Essential English Words::5.Book", "", "armed"): "silahlı",
    ("4000 Essential English Words::5.Book", "", "outraged"): "çok öfkeli",
    ("4000 Essential English Words::5.Book", "", "beloved"): "çok sevilen",
    ("4000 Essential English Words::5.Book", "", "complain"): "şikayet etmek",
    ("4000 Essential English Words::5.Book", "", "due"): "vadesi gelmiş",
    ("4000 Essential English Words::5.Book", "", "prior"): "önceki",
    ("4000 Essential English Words::5.Book", "", "idle"): "aylak / boş",
    ("4000 Essential English Words::5.Book", "", "grim"): "kasvetli",
    ("4000 Essential English Words::5.Book", "", "overhead"): "tepede",
    ("4000 Essential English Words::5.Book", "", "earthen"): "topraktan",
    ("4000 Essential English Words::5.Book", "", "hostile"): "düşmanca",
    ("4000 Essential English Words::5.Book", "", "connect"): "bağlamak",
    ("4000 Essential English Words::5.Book", "", "promote"): "terfi ettirmek",
    ("4000 Essential English Words::5.Book", "", "scramble"): "didinmek",
    ("4000 Essential English Words::5.Book", "", "buzz"): "heyecan yaratmak",
    ("4000 Essential English Words::5.Book", "", "operate"): "çalışmak / işlemek",
    ("4000 Essential English Words::5.Book", "", "display"): "sergilemek",
    ("4000 Essential English Words::5.Book", "", "zoom"): "hızla hareket etmek",
    ("4000 Essential English Words::5.Book", "", "flush"): "kızarmak",
    ("4000 Essential English Words::5.Book", "", "glimpse"): "gözüne ilişmek",
    ("4000 Essential English Words::5.Book", "", "oppress"): "zulmetmek / baskı yapmak",
    ("4000 Essential English Words::5.Book", "", "nurture"): "besleyip büyütmek",
    ("4000 Essential English Words::5.Book", "", "moral"): "ahlak dersi",
    ("4000 Essential English Words::5.Book", "", "resolution"): "karar",
    ("4000 Essential English Words::5.Book", "", "landmark"): "nirengi noktası",
    ("4000 Essential English Words::5.Book", "", "law"): "kanun / yasa",
    ("4000 Essential English Words::5.Book", "", "plea"): "yalvarış",
    ("4000 Essential English Words::5.Book", "", "meantime"): "aradaki süre",
    ("4000 Essential English Words::5.Book", "", "succession"): "ardıllık",
    ("4000 Essential English Words::5.Book", "", "bead"): "damla",
    ("4000 Essential English Words::5.Book", "", "horn"): "korna",
    ("4000 Essential English Words::5.Book", "", "midst"): "orta",
    ("4000 Essential English Words::5.Book", "", "sake"): "hatır",
    ("4000 Essential English Words::5.Book", "", "dip"): "düşüş",
    ("4000 Essential English Words::5.Book", "", "cabin"): "kütük ev",
    ("4000 Essential English Words::5.Book", "", "contingent"): "heyet / birlik",
    ("4000 Essential English Words::5.Book", "", "temper"): "mizaç / huy",
    ("4000 Essential English Words::5.Book", "", "celebrity"): "ünlü kişi",
    ("4000 Essential English Words::5.Book", "", "species"): "tür",
    ("4000 Essential English Words::5.Book", "", "tornado"): "hortum",
    ("4000 Essential English Words::5.Book", "", "string"): "ip",
    ("4000 Essential English Words::5.Book", "", "shutter"): "panjur",
    ("4000 Essential English Words::5.Book", "", "scribe"): "katip",
    ("4000 Essential English Words::5.Book", "", "intake"): "alım",
    ("4000 Essential English Words::5.Book", "", "avail"): "yarar / fayda",
    # 6.Book
    ("4000 Essential English Words::6.Book", "", "choke"): "boğazına kaçmak",
    ("4000 Essential English Words::6.Book", "", "stuffed"): "doldurulmuş",
    ("4000 Essential English Words::6.Book", "", "recycle"): "geri dönüştürmek",
    ("4000 Essential English Words::6.Book", "", "ample"): "bol / yeterli",
    ("4000 Essential English Words::6.Book", "", "inland"): "iç kesim",
    ("4000 Essential English Words::6.Book", "", "municipal"): "belediyeye ait",
    ("4000 Essential English Words::6.Book", "", "aquatic"): "suda yaşayan",
    ("4000 Essential English Words::6.Book", "", "prominent"): "önemli / tanınmış",
    ("4000 Essential English Words::6.Book", "", "repetitive"): "tekrarlı",
    ("4000 Essential English Words::6.Book", "", "reproductive"): "üremeye ait",
    ("4000 Essential English Words::6.Book", "", "medieval"): "ortaçağa ait",
    ("4000 Essential English Words::6.Book", "", "oriented"): "yönelmiş",
    ("4000 Essential English Words::6.Book", "", "dumb"): "dilsiz",
    ("4000 Essential English Words::6.Book", "", "outright"): "düpedüz / açık",
    ("4000 Essential English Words::6.Book", "", "skeletal"): "iskelete ait",
    ("4000 Essential English Words::6.Book", "", "civic"): "yurttaşlıkla ilgili",
    ("4000 Essential English Words::6.Book", "", "liable"): "olası / muhtemel",
    ("4000 Essential English Words::6.Book", "", "overboard"): "denize düşmüş",
    ("4000 Essential English Words::6.Book", "", "aerial"): "havadan",
    ("4000 Essential English Words::6.Book", "", "sideways"): "yanlamasına",
    ("4000 Essential English Words::6.Book", "", "decorate"): "süslemek / dekore etmek",
    ("4000 Essential English Words::6.Book", "", "hesitant"): "tereddütlü",
    ("4000 Essential English Words::6.Book", "", "overjoyed"): "çok sevinmiş",
    ("4000 Essential English Words::6.Book", "", "foul"): "pis / iğrenç",
    ("4000 Essential English Words::6.Book", "", "winding"): "kıvrımlı",
    ("4000 Essential English Words::6.Book", "", "outstretched"): "uzatılmış",
    ("4000 Essential English Words::6.Book", "", "ingenious"): "dahiyane",
    ("4000 Essential English Words::6.Book", "", "infamous"): "kötü şöhretli",
    ("4000 Essential English Words::6.Book", "", "naval"): "donanmayla ilgili",
    ("4000 Essential English Words::6.Book", "", "conceive"): "tasavvur etmek",
    ("4000 Essential English Words::6.Book", "", "dissatisfy"): "memnun edememek",
    ("4000 Essential English Words::6.Book", "", "overwork"): "fazla çalıştırmak",
    ("4000 Essential English Words::6.Book", "", "discharge"): "taburcu etmek",
    ("4000 Essential English Words::6.Book", "", "seclude"): "tecrit etmek",
    ("4000 Essential English Words::6.Book", "", "sob"): "hıçkırarak ağlamak",
    ("4000 Essential English Words::6.Book", "", "stray"): "yolunu şaşırmak",
    ("4000 Essential English Words::6.Book", "", "resent"): "gücenmek / içerlemek",
    ("4000 Essential English Words::6.Book", "", "deduct"): "kesmek / çıkarmak",
    ("4000 Essential English Words::6.Book", "", "speculate"): "tahminde bulunmak / varsaymak",
    ("4000 Essential English Words::6.Book", "", "saturate"): "tamamen ıslatmak",
    ("4000 Essential English Words::6.Book", "", "hack"): "parçalayarak doğramak",
    ("4000 Essential English Words::6.Book", "", "stall"): "ertelemek / durdurmak",
    ("4000 Essential English Words::6.Book", "", "consolidate"): "birleştirip sağlamlaştırmak",
    ("4000 Essential English Words::6.Book", "", "entitle"): "hak vermek",
    ("4000 Essential English Words::6.Book", "", "cater"): "ihtiyaçları karşılamak",
    ("4000 Essential English Words::6.Book", "", "escort"): "eşlik etmek / refakat etmek",
    ("4000 Essential English Words::6.Book", "", "sow"): "tohum ekmek",
    ("4000 Essential English Words::6.Book", "", "zip"): "fermuar çekmek",
    ("4000 Essential English Words::6.Book", "", "sober"): "ciddi / ağırbaşlı",
    ("4000 Essential English Words::6.Book", "", "oracle"): "kâhin",
    ("4000 Essential English Words::6.Book", "", "convention"): "gelenek / görenek",
    ("4000 Essential English Words::6.Book", "", "epic"): "destan",
    ("4000 Essential English Words::6.Book", "", "register"): "kayıt / sicil",
    ("4000 Essential English Words::6.Book", "", "locale"): "mekan",
    ("4000 Essential English Words::6.Book", "", "stool"): "tabure",
    ("4000 Essential English Words::6.Book", "", "testament"): "kanıt",
    ("4000 Essential English Words::6.Book", "", "cot"): "portatif yatak",
    ("4000 Essential English Words::6.Book", "", "brute"): "kaba saba kimse",
    ("4000 Essential English Words::6.Book", "", "mob"): "güruh",
    ("4000 Essential English Words::6.Book", "", "charter"): "berat / tüzük",
    ("4000 Essential English Words::6.Book", "", "bulk"): "büyük bölüm / hacim",
    ("4000 Essential English Words::6.Book", "", "whereabouts"): "bulunduğu yer",
    ("4000 Essential English Words::6.Book", "", "feat"): "büyük başarı",
    ("4000 Essential English Words::6.Book", "", "undergraduate"): "lisans öğrencisi",
    ("4000 Essential English Words::6.Book", "", "shaft"): "uzun sap",
    ("4000 Essential English Words::6.Book", "", "compound"): "kapalı yerleşke",
    ("4000 Essential English Words::6.Book", "", "twig"): "ince dal",
    ("4000 Essential English Words::6.Book", "", "preliminary"): "ön",
    ("4000 Essential English Words::6.Book", "", "majesty"): "ululuk",
    ("4000 Essential English Words::6.Book", "", "bliss"): "saadet",
    ("4000 Essential English Words::6.Book", "", "persistent"): "azimli / ısrarcı",
    ("4000 Essential English Words::6.Book", "", "guts"): "iç organlar",
    ("4000 Essential English Words::6.Book", "", "humor"): "mizah / ruh hali",
    # Extra (no book definition; fixed against the picture vocabulary sense)
    ("4000 Essential English Words::Extra", "2_7", "cap"): "kep",
    ("4000 Essential English Words::Extra", "2_9", "coat"): "palto",
    ("4000 Essential English Words::Extra", "2_19", "mittens"): "tek parmaklı eldiven",
    ("4000 Essential English Words::Extra", "2_28", "ring"): "yüzük",
    ("4000 Essential English Words::Extra", "2_43", "sweatshirt"): "sweatshirt",
    ("4000 Essential English Words::Extra", "3_10", "skiing"): "kayak",
    ("4000 Essential English Words::Extra", "3_11", "snowboarding"): "snowboard",
    ("4000 Essential English Words::Extra", "3_45", "robin"): "kızılgerdan",
    ("4000 Essential English Words::Extra", "3_118", "alligator, crocodile"): "aligatör / timsah",
    ("4000 Essential English Words::Extra", "1_1_10", "jaw"): "çene kemiği",
    ("4000 Essential English Words::Extra", "1_1_45", "calf"): "baldır",
    ("4000 Essential English Words::Extra", "1_1_55", "father, dad"): "baba",
    ("4000 Essential English Words::Extra", "1_1_56", "mother, mom"): "anne",
    ("4000 Essential English Words::Extra", "1_1_60", "grandfather, grandpa"): "büyükbaba",
    ("4000 Essential English Words::Extra", "1_1_61", "grandmother, grandma"): "büyükanne",
    ("4000 Essential English Words::Extra", "1_1_63", "uncle"): "amca / dayı",
    ("4000 Essential English Words::Extra", "1_1_64", "aunt"): "teyze / hala",
    ("4000 Essential English Words::Extra", "1_1_66", "my parents' niece"): "anne babamın kız yeğeni",
    ("4000 Essential English Words::Extra", "1_1_68", "my parents' nephew"): "anne babamın erkek yeğeni",
    # Full-deck audit 2026-09-10 (part 3): verification round. Cambridge-checked
    # where senses compete (e.g. keen is both eager and sharp-minded), and every
    # new cue re-checked for collisions with other cards' cues, since production
    # cards cue in Turkish and identical cues are ambiguous. Later entries win.
    ("4000 Essential English Words::4.Book", "", "keen"): "hevesli / zeki",
    ("4000 Essential English Words::4.Book", "", "aspect"): "boyut",
    ("4000 Essential English Words::3.Book", "", "might"): "kudret",
    ("4000 Essential English Words::3.Book", "", "sole"): "yegane",
    ("4000 Essential English Words::5.Book", "", "midst"): "tam ortası",
    ("4000 Essential English Words::3.Book", "", "domestic"): "ülke içi",
    ("4000 Essential English Words::4.Book", "", "asset"): "katma değer",
    ("4000 Essential English Words::2.Book", "", "sleeve"): "yen",
    ("4000 Essential English Words::2.Book", "", "rid"): "arındırmak",
    ("4000 Essential English Words::6.Book", "", "testament"): "gösterge",
    ("4000 Essential English Words::6.Book", "", "convention"): "görenek",
    ("4000 Essential English Words::3.Book", "", "volume"): "toplam hacim",
    ("4000 Essential English Words::3.Book", "", "assembly"): "meclis",
    ("4000 Essential English Words::3.Book", "", "affair"): "hâdise",
    ("4000 Essential English Words::3.Book", "", "massive"): "iri / kocaman",
    ("4000 Essential English Words::3.Book", "", "kit"): "set",
    ("4000 Essential English Words::3.Book", "", "inhabitant"): "mukim",
    ("4000 Essential English Words::3.Book", "", "decent"): "makul",
    ("4000 Essential English Words::6.Book", "", "sober"): "ağırbaşlı",
    ("4000 Essential English Words::2.Book", "", "stable"): "sabit",
    ("4000 Essential English Words::1.Book", "", "silly"): "ciddiyetsiz",
    ("4000 Essential English Words::6.Book", "", "humor"): "mizah",
    ("4000 Essential English Words::4.Book", "", "key"): "kilit",
    ("4000 Essential English Words::4.Book", "", "inhibit"): "ket vurmak",
    ("4000 Essential English Words::6.Book", "", "prominent"): "tanınmış",
    ("4000 Essential English Words::6.Book", "", "outright"): "düpedüz",
    ("4000 Essential English Words::6.Book", "", "foul"): "pis",
    ("4000 Essential English Words::6.Book", "", "infamous"): "kötü nam salmış",
    ("4000 Essential English Words::6.Book", "", "deduct"): "kesinti yapmak",
    ("4000 Essential English Words::6.Book", "", "speculate"): "tahmin yürütmek",
    ("4000 Essential English Words::6.Book", "", "stall"): "oyalamak",
    ("4000 Essential English Words::6.Book", "", "escort"): "refakat etmek",
    ("4000 Essential English Words::1.Book", "", "sheet"): "tabaka",
    ("4000 Essential English Words::1.Book", "", "instrument"): "alet",
    ("4000 Essential English Words::2.Book", "", "junior"): "kıdemsiz",
    ("4000 Essential English Words::2.Book", "", "yard"): "ev bahçesi",
    ("4000 Essential English Words::6.Book", "", "artifact"): "tarihi eser",
    ("4000 Essential English Words::5.Book", "", "deposit"): "para yatırmak",
    ("4000 Essential English Words::2.Book", "", "fantastic"): "fevkalade",
    ("4000 Essential English Words::5.Book", "", "species"): "canlı türü",
    ("4000 Essential English Words::5.Book", "", "vain"): "kendini beğenmiş",
    ("4000 Essential English Words::4.Book", "", "viable"): "gerçekleşebilir",
    ("4000 Essential English Words::5.Book", "", "prior"): "evvelki",
    ("4000 Essential English Words::4.Book", "", "assign"): "görev dağıtmak",
    ("4000 Essential English Words::4.Book", "", "fat"): "katı yağ",
    ("4000 Essential English Words::4.Book", "", "integrity"): "doğruluk",
    ("4000 Essential English Words::6.Book", "", "garment"): "giyecek",
    ("4000 Essential English Words::5.Book", "", "grim"): "ürkütücü",
    ("4000 Essential English Words::5.Book", "", "escape"): "kaçıp kurtulmak",
    ("4000 Essential English Words::5.Book", "", "horrified"): "şoke olmuş",
    ("4000 Essential English Words::4.Book", "", "hold"): "haiz olmak",
    ("4000 Essential English Words::5.Book", "", "display"): "teşhir etmek",
    ("4000 Essential English Words::2.Book", "", "compose"): "parçalardan birleştirmek",
    ("4000 Essential English Words::3.Book", "", "drain"): "gider borusu",
    ("4000 Essential English Words::4.Book", "", "keep"): "devam ettirmek",
    ("4000 Essential English Words::5.Book", "", "animate"): "yaşayan",
    ("4000 Essential English Words::1.Book", "", "lay"): "yatırmak",
    ("4000 Essential English Words::5.Book", "", "bind"): "kenetlemek",
    ("4000 Essential English Words::5.Book", "", "connect"): "bağlantı kurmak",
    ("4000 Essential English Words::3.Book", "", "dissolve"): "eritmek",
    ("4000 Essential English Words::4.Book", "", "select"): "özenle seçmek",
    ("4000 Essential English Words::3.Book", "", "yield"): "devretmek",
    ("4000 Essential English Words::3.Book", "", "tease"): "dalga geçmek",
    ("4000 Essential English Words::6.Book", "", "ample"): "kâfi",
    # 2026-09-10: user-authorized corrections of live-Anki-reviewed cues where
    # the book sense clearly differs (review no longer blocks improvement).
    ("4000 Essential English Words::1.Book", "", "essential"): "önemli / temel",
    ("4000 Essential English Words::1.Book", "", "along"): "boyunca",
    ("4000 Essential English Words::2.Book", "", "supplement"): "takviye etmek / gıda takviyesi",
    # 2026-09-10 (part 4): keen-type verification. Cambridge-checked where
    # senses compete: several cues covered only the book's narrow sense while
    # missing the word's dominant everyday sense (keen = eager first,
    # straightforward = honest as well as simple). Both senses are now cued.
    ("4000 Essential English Words::4.Book", "", "straightforward"): "açık sözlü / anlaşılır",
    ("4000 Essential English Words::4.Book", "", "hold"): "tutmak / haiz olmak",
    ("4000 Essential English Words::4.Book", "", "keep"): "saklamak / devam ettirmek",
    ("4000 Essential English Words::4.Book", "", "mark"): "işaretlemek / kutlamak",
    ("4000 Essential English Words::1.Book", "", "cheer"): "tezahürat yapmak / neşelendirmek",
    ("4000 Essential English Words::3.Book", "", "occupy"): "oturmak / işgal etmek",
    ("4000 Essential English Words::6.Book", "", "charter"): "kiralamak / berat",
    ("4000 Essential English Words::6.Book", "", "compound"): "bileşik / kapalı yerleşke",
    ("4000 Essential English Words::6.Book", "", "faculty"): "fakülte / yeti",
    ("4000 Essential English Words::3.Book", "", "peer"): "akran / dikkatle bakmak",
    ("4000 Essential English Words::3.Book", "", "kid"): "çocuk / şaka yapmak",
    ("4000 Essential English Words::5.Book", "", "concrete"): "beton / somut",
    ("4000 Essential English Words::5.Book", "", "bill"): "fatura / banknot",
    ("4000 Essential English Words::4.Book", "", "subject"): "konu / maruz bırakmak",
    ("4000 Essential English Words::6.Book", "", "subject"): "konu / maruz bırakmak",
    ("4000 Essential English Words::4.Book", "", "object"): "nesne / itiraz etmek",
    ("4000 Essential English Words::2.Book", "", "pound"): "dövmek / sterlin",
    ("4000 Essential English Words::2.Book", "", "prime"): "en önemli / başlıca",
    ("4000 Essential English Words::5.Book", "", "promote"): "terfi ettirmek / tanıtmak",
    ("4000 Essential English Words::2.Book", "", "grave"): "mezar / vahim",
    ("4000 Essential English Words::2.Book", "", "glory"): "şan / görkem",
}


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value or "")
    return html.unescape(" ".join(text.split()))


def strip_html_preserve_lines(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value or "")
    return html.unescape(text)


def normalize_turkish_cue(value: str) -> str:
    cue = strip_html(value)
    cue = re.sub(r"\s*\([^)]*\)\s*$", "", cue).strip()
    cue = cue.lower().replace("i̇", "i")
    return cue


def source_id(row: Dict[str, str]) -> str:
    return "::".join(
        [
            row.get("deck", ""),
            row.get("card_number", ""),
            strip_html(row.get("english_word", "")).lower(),
        ]
    )


def source_sort_rank(deck: str) -> int:
    for index in range(1, 7):
        if deck.endswith(f"::{index}.Book"):
            return index
    if deck.endswith("::Extra"):
        return 7
    return 99


def source_card_number(value: str) -> tuple[int, ...]:
    numbers = [int(part) for part in re.findall(r"\d+", value or "")]
    return tuple(numbers or [999999])


def difficulty_order(source_rows: List[Dict[str, str]]) -> Dict[str, int]:
    source_file_indexes = {id(row): index for index, row in enumerate(source_rows, start=1)}
    sorted_rows = sorted(
        source_rows,
        key=lambda row: (
            source_sort_rank(row.get("deck", "")),
            source_file_indexes.get(id(row), 999999),
            source_card_number(row.get("card_number", "")),
            strip_html(row.get("english_word", "")).lower(),
            strip_html(row.get("english_meaning", "")).lower(),
        ),
    )
    return {source_id(row): index for index, row in enumerate(sorted_rows, start=1)}


def infer_pos(row: Dict[str, str]) -> str:
    meaning = strip_html(row.get("english_meaning", "")).lower()
    if meaning.startswith("to "):
        return "verb"
    if meaning.startswith(("a ", "an ", "the ")) and " is " in meaning[:80]:
        return "noun"
    if meaning.startswith(("if ", "when ", "something ", "someone ")):
        return "adjective"
    if " means " in meaning[:80]:
        return "adverb"
    return ""


def cue_source(row: Dict[str, str]) -> str:
    word = strip_html(row.get("english_word", ""))
    if not word:
        return ""
    if infer_pos(row) == "verb" and not word.lower().startswith("to "):
        return f"to {word}"
    if infer_pos(row) == "adjective":
        return f"to be {word}"
    return word


def load_existing(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["SourceID"]: row for row in csv.DictReader(handle, delimiter="\t")}


def load_reviewed_english(path: Path) -> Dict[str, Dict[str, str]]:
    """Load the human-reviewed English definition/example for production clues."""
    if not path.exists():
        return {}
    reviewed = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            sid = "::".join(
                [
                    row.get("Source Deck", ""),
                    row.get("Source Card", ""),
                    strip_html(row.get("English", "")).lower(),
                ]
            )
            reviewed[sid] = {
                "EnglishMeaning": strip_html(row.get("English Meaning", "")),
                "EnglishExample": strip_html(row.get("English Example", "")),
            }
    return reviewed


def load_cache(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_cache(path: Path, cache: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def translate_mymemory(text: str, cache: Dict[str, str], delay: float = 0.05) -> str:
    text = strip_html(text)
    if not text:
        return ""
    if text in cache:
        return cache[text]
    params = urllib.parse.urlencode({"q": text, "langpair": "en|tr"})
    request = urllib.request.Request(
        f"{MYMEMORY_URL}?{params}",
        headers={"User-Agent": "anki-language-deck-builder/1.0"},
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))
    translated = normalize_turkish_cue(payload.get("responseData", {}).get("translatedText", ""))
    cache[text] = translated
    time.sleep(delay)
    return translated


def translate_google(text: str, cache: Dict[str, str], delay: float = 0.03) -> str:
    text = strip_html(text)
    if not text:
        return ""
    if text in cache:
        return cache[text]
    params = urllib.parse.urlencode(
        {
            "client": "gtx",
            "sl": "en",
            "tl": "tr",
            "dt": "t",
            "q": text,
        }
    )
    request = urllib.request.Request(
        f"{GOOGLE_TRANSLATE_URL}?{params}",
        headers={"User-Agent": "anki-language-deck-builder/1.0"},
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))
    translated = normalize_turkish_cue("".join(part[0] for part in payload[0] if part and part[0]))
    cache[text] = translated
    time.sleep(delay)
    return translated


def translate_google_batch(texts: List[str], cache: Dict[str, str], delay: float = 0.08) -> None:
    missing = []
    seen = set()
    for text in texts:
        text = strip_html(text)
        if not text or text in cache or text in seen:
            continue
        missing.append(text)
        seen.add(text)

    for offset in range(0, len(missing), GOOGLE_BATCH_SIZE):
        batch = missing[offset : offset + GOOGLE_BATCH_SIZE]
        params = urllib.parse.urlencode(
            {
                "client": "gtx",
                "sl": "en",
                "tl": "tr",
                "dt": "t",
                "q": "\n".join(batch),
            }
        )
        request = urllib.request.Request(
            f"{GOOGLE_TRANSLATE_URL}?{params}",
            headers={"User-Agent": "anki-language-deck-builder/1.0"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        translated = strip_html_preserve_lines("".join(part[0] for part in payload[0] if part and part[0]))
        lines = [normalize_turkish_cue(line) for line in translated.splitlines()]
        if len(lines) != len(batch):
            for text in batch:
                translate_google(text, cache, delay=0)
        else:
            for text, line in zip(batch, lines):
                cache[text] = line
        time.sleep(delay)


def translate_cue(text: str, provider: str, cache: Dict[str, str]) -> str:
    if provider == "google":
        return translate_google(text, cache)
    if provider == "mymemory":
        return translate_mymemory(text, cache)
    raise ValueError(f"Unsupported provider: {provider}")


def prefetch_translations(texts: List[str], provider: str, cache: Dict[str, str]) -> None:
    if provider == "google":
        translate_google_batch(texts, cache)


def source_specific_override(row: Dict[str, str]) -> str:
    key = (
        row.get("deck", ""),
        row.get("card_number", ""),
        strip_html(row.get("english_word", "")).lower(),
    )
    return SOURCE_SPECIFIC_TURKISH_OVERRIDES.get(key, "")


def polish_cue_for_row(row: Dict[str, str], cue: str) -> str:
    cue = normalize_turkish_cue(cue)
    if infer_pos(row) == "adjective":
        cue = re.sub(r"\s+olmak$", "", cue).strip()
    return cue


def build_rows(
    source_rows: List[Dict[str, str]],
    existing: Dict[str, Dict[str, str]],
    cache: Dict[str, str],
    limit: int | None,
    output_path: Path | None = None,
    cache_path: Path | None = None,
    provider: str = "google",
    refresh: bool = False,
    reviewed_english: Dict[str, Dict[str, str]] | None = None,
) -> List[Dict[str, str]]:
    reviewed_english = reviewed_english or {}
    rows: List[Dict[str, str]] = []
    order_map = difficulty_order(source_rows)
    texts_to_translate = []
    for index, row in enumerate(source_rows, start=1):
        sid = source_id(row)
        order = order_map.get(sid, index)
        previous = existing.get(sid, {})
        if not refresh and previous.get("TurkishCue", "").strip():
            continue
        if limit is None or order <= limit:
            texts_to_translate.append(cue_source(row))
    prefetch_translations(texts_to_translate, provider, cache)
    if cache_path is not None:
        save_cache(cache_path, cache)

    for index, row in enumerate(source_rows, start=1):
        sid = source_id(row)
        order = order_map.get(sid, index)
        previous = existing.get(sid, {})
        reviewed = reviewed_english.get(sid, {})
        source_text = cue_source(row)
        turkish_cue = "" if refresh else previous.get("TurkishCue", "").strip()
        status = "" if refresh else previous.get("Status", "").strip()
        if not turkish_cue:
            if limit is None or order <= limit:
                try:
                    turkish_cue = translate_cue(source_text, provider, cache)
                    status = f"draft_{provider}_word"
                except Exception as error:
                    turkish_cue = ""
                    status = f"error:{type(error).__name__}"
            else:
                status = "pending"
        rows.append(
            {
                "SourceID": sid,
                "Order": str(order),
                "SourceDeck": row.get("deck", ""),
                "SourceCard": row.get("card_number", ""),
                "English": strip_html(row.get("english_word", "")),
                "EnglishMeaning": reviewed.get("EnglishMeaning")
                or strip_html(row.get("english_meaning", "")),
                "EnglishExample": reviewed.get("EnglishExample")
                or strip_html(row.get("english_example", "")),
                "CueSource": source_text,
                "TurkishCue": source_specific_override(row) or polish_cue_for_row(row, turkish_cue),
                "Status": status,
            }
        )
        if index % 25 == 0:
            if cache_path is not None:
                save_cache(cache_path, cache)
            if output_path is not None:
                write_rows(output_path, rows)
    return rows


def write_rows(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "SourceID",
        "Order",
        "SourceDeck",
        "SourceCard",
        "English",
        "EnglishMeaning",
        "EnglishExample",
        "CueSource",
        "TurkishCue",
        "Status",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Turkish cue TSV for English 4000 production cards.")
    parser.add_argument("--source", default="4000 Essential English Words.txt")
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--reviewed-english", default=str(REVIEWED_ENGLISH_PATH))
    parser.add_argument("--cache", help="Translation cache path. Defaults to provider-specific cache.")
    parser.add_argument("--provider", choices=["google", "mymemory"], default="google")
    parser.add_argument("--refresh", action="store_true", help="Regenerate existing cues instead of preserving them.")
    parser.add_argument("--limit", type=int, help="Translate only the first N missing cues; keep later rows pending.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_rows = spanish_deck.parse_source_deck(args.source)
    output = Path(args.output)
    cache_path = Path(args.cache) if args.cache else (GOOGLE_CACHE_PATH if args.provider == "google" else CACHE_PATH)
    existing = load_existing(output)
    reviewed_english = load_reviewed_english(Path(args.reviewed_english))
    cache = load_cache(cache_path)
    rows = build_rows(
        source_rows,
        existing,
        cache,
        args.limit,
        output,
        cache_path,
        provider=args.provider,
        refresh=args.refresh,
        reviewed_english=reviewed_english,
    )
    write_rows(output, rows)
    save_cache(cache_path, cache)
    counts: Dict[str, int] = {}
    for row in rows:
        counts[row["Status"]] = counts.get(row["Status"], 0) + 1
    print(json.dumps({"rows": len(rows), "status": counts, "output": str(output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
