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

import deck_io


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
    ("4000 Essential English Words::1.Book", "", "view"): "bakmak / incelemek",
    # 2026-09-16: elle doğrulanan ayırt edici ipuçları (kitap tanımına göre,
    # makine çevirisi değil). prize/award/reward üçü de "ödül" idi;
    # watch/monitor ikisi de "izlemek" idi ve üretim kartında çakışıyordu.
    # prize = kazananın aldığı şey; award = iyi işe törenle verilen;
    # reward = emek/iyi davranış karşılığı (mükâfat).
    ("4000 Essential English Words::1.Book", "", "prize"): "birincilik ödülü (kazanana verilen)",
    ("4000 Essential English Words::1.Book", "", "reward"): "karşılık ödülü (mükâfat)",
    ("4000 Essential English Words::2.Book", "", "award"): "başarı ödülü (törenle verilen)",
    # watch = bir süre bakmak (film gibi); monitor = yakından denetleyerek
    # izlemek (öğretmenin sınavda öğrencileri gözetlemesi gibi).
    ("4000 Essential English Words::2.Book", "", "watch"): "bir süre izlemek (film gibi)",
    ("4000 Essential English Words::2.Book", "", "monitor"): "yakından izleyip denetlemek",
    ("4000 Essential English Words::1.Book", "", "avoid"): "kaçınmak (uzak durmak)",
    ("4000 Essential English Words::1.Book", "", "content"): "memnun / hâlinden hoşnut",
    ("4000 Essential English Words::1.Book", "", "glad"): "memnun / sevinçli",
    ("4000 Essential English Words::1.Book", "", "expect"): "beklemek (olacağına inanmak)",
    ("4000 Essential English Words::1.Book", "", "grade"): "not",
    ("4000 Essential English Words::1.Book", "", "secret"): "sır",
    ("4000 Essential English Words::1.Book", "", "ever"): "herhangi bir zaman",
    ("4000 Essential English Words::1.Book", "", "instead"): "yerine",
    ("4000 Essential English Words::1.Book", "", "football"): "amerikan futbolu",
    ("4000 Essential English Words::1.Book", "", "sense"): "sezmek",
    ("4000 Essential English Words::1.Book", "", "appeal"): "çekici gelmek",
    ("4000 Essential English Words::1.Book", "", "found"): "kurmak",
    ("4000 Essential English Words::1.Book", "", "direct"): "doğrudan",
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
    ("4000 Essential English Words::4.Book", "", "tool"): "araç",
    ("4000 Essential English Words::4.Book", "", "case"): "durum / örnek",
    ("4000 Essential English Words::4.Book", "", "quote"): "alıntı / fiyat teklifi",
    ("4000 Essential English Words::4.Book", "", "inhale"): "içine çekmek / solumak",
    ("4000 Essential English Words::5.Book", "", "compliance"): "kurallara uyma / itaat",
    ("4000 Essential English Words::5.Book", "", "sentence"): "ceza / hüküm",
    ("4000 Essential English Words::5.Book", "", "linger"): "uzun süre kalmak / sürmek",
    ("4000 Essential English Words::6.Book", "", "soundly"): "kesin biçimde / açık farkla",
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
    ("4000 Essential English Words::3.Book", "", "disguise"): "kılık / kılık değiştirme",
    ("4000 Essential English Words::3.Book", "", "puff"): "bir tutam / duman bulutu",
    ("4000 Essential English Words::3.Book", "", "stem"): "gövde / sap",
    ("4000 Essential English Words::3.Book", "", "howl"): "ulumak",
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
    ("4000 Essential English Words::1.Book", "", "set"): "koymak",
    ("4000 Essential English Words::1.Book", "", "from"): "-den / -dan",
    ("4000 Essential English Words::1.Book", "", "though"): "olsa da",
    ("4000 Essential English Words::1.Book", "", "bite"): "ısırma",
    ("4000 Essential English Words::1.Book", "", "january"): "Ocak",
    # 2.Book
    ("4000 Essential English Words::2.Book", "", "ought"): "-meli / -malı",
    ("4000 Essential English Words::2.Book", "", "grand"): "görkemli / büyük",
    ("4000 Essential English Words::2.Book", "", "save"): "kurtarmak",
    ("4000 Essential English Words::2.Book", "", "dine"): "akşam yemeği yemek",
    ("4000 Essential English Words::2.Book", "", "cast"): "fırlatmak",
    ("4000 Essential English Words::2.Book", "", "bend"): "bükmek",
    ("4000 Essential English Words::2.Book", "", "swing"): "sallamak",
    ("4000 Essential English Words::2.Book", "", "engage"): "uğraşmak / girişmek",
    ("4000 Essential English Words::2.Book", "", "officer"): "subay",
    ("4000 Essential English Words::2.Book", "", "carriage"): "fayton",
    ("4000 Essential English Words::2.Book", "", "element"): "unsur",
    ("4000 Essential English Words::2.Book", "", "mineral"): "mineral",
    ("4000 Essential English Words::2.Book", "", "tissue"): "kağıt mendil",
    ("4000 Essential English Words::2.Book", "", "dish"): "yemek çeşidi",
    ("4000 Essential English Words::2.Book", "", "pot"): "tencere",
    ("4000 Essential English Words::2.Book", "", "sort"): "çeşit / tür",
    ("4000 Essential English Words::2.Book", "", "basin"): "leğen",
    ("4000 Essential English Words::2.Book", "", "terror"): "dehşet",
    ("4000 Essential English Words::2.Book", "", "still"): "hâlâ",
    ("4000 Essential English Words::2.Book", "", "metal"): "metal",
    ("4000 Essential English Words::2.Book", "", "initial"): "ilk",
    ("4000 Essential English Words::2.Book", "", "vision"): "görme",
    ("4000 Essential English Words::2.Book", "", "intelligence"): "zeka",
    ("4000 Essential English Words::2.Book", "", "disabled"): "engelli",
    # 3.Book
    ("4000 Essential English Words::3.Book", "", "ashamed"): "utanmış",
    ("4000 Essential English Words::3.Book", "", "aboard"): "gemide / uçakta",
    ("4000 Essential English Words::3.Book", "", "royal"): "kraliyete ait",
    ("4000 Essential English Words::3.Book", "", "entire"): "bütün",
    ("4000 Essential English Words::3.Book", "", "execute"): "idam etmek",
    ("4000 Essential English Words::3.Book", "", "abandon"): "terk etmek",
    ("4000 Essential English Words::3.Book", "", "restore"): "eski haline getirmek",
    ("4000 Essential English Words::3.Book", "", "assure"): "güvence vermek",
    ("4000 Essential English Words::3.Book", "", "dismiss"): "önemsememek / geçiştirmek",
    ("4000 Essential English Words::3.Book", "", "navigate"): "yön bulmak",
    ("4000 Essential English Words::3.Book", "", "sneak"): "gizlice sokulmak",
    ("4000 Essential English Words::3.Book", "", "spare"): "ihtiyaç fazlasını vermek",
    ("4000 Essential English Words::3.Book", "", "accommodate"): "yer sağlamak / barındırmak",
    ("4000 Essential English Words::3.Book", "", "commission"): "görevlendirmek",
    ("4000 Essential English Words::3.Book", "", "gaze"): "dik dik bakmak",
    ("4000 Essential English Words::3.Book", "", "glance"): "göz atmak",
    ("4000 Essential English Words::3.Book", "", "caretaker"): "bakıcı",
    ("4000 Essential English Words::3.Book", "", "inferior"): "kalitesiz",
    ("4000 Essential English Words::3.Book", "", "valentine"): "sevgili",
    ("4000 Essential English Words::3.Book", "", "shed"): "baraka",
    ("4000 Essential English Words::3.Book", "", "wagon"): "yük arabası",
    ("4000 Essential English Words::3.Book", "", "vessel"): "gemi",
    ("4000 Essential English Words::3.Book", "", "chef"): "aşçı",
    ("4000 Essential English Words::3.Book", "", "nut"): "kuruyemiş",
    ("4000 Essential English Words::3.Book", "", "scheme"): "plan / tertip",
    ("4000 Essential English Words::3.Book", "", "straw"): "pipet",
    ("4000 Essential English Words::3.Book", "", "cliff"): "yar",
    ("4000 Essential English Words::3.Book", "", "tender"): "yumuşak",
    ("4000 Essential English Words::3.Book", "", "cottage"): "kır evi",
    ("4000 Essential English Words::3.Book", "", "prospect"): "beklenti / olasılık",
    ("4000 Essential English Words::3.Book", "", "bargain"): "kelepir",
    ("4000 Essential English Words::3.Book", "", "fuse"): "fitil",
    ("4000 Essential English Words::3.Book", "", "paste"): "macun",
    ("4000 Essential English Words::3.Book", "", "chill"): "ürperti",
    ("4000 Essential English Words::3.Book", "", "limb"): "kalın dal",
    ("4000 Essential English Words::3.Book", "", "overnight"): "bir gecede",
    ("4000 Essential English Words::3.Book", "", "absence"): "yokluk",
    ("4000 Essential English Words::3.Book", "", "relief"): "rahatlama",
    ("4000 Essential English Words::3.Book", "", "bitter"): "kırgın",
    ("4000 Essential English Words::3.Book", "", "mercy"): "merhamet",
    ("4000 Essential English Words::3.Book", "", "sympathy"): "şefkat",
    # 4.Book
    ("4000 Essential English Words::4.Book", "", "corrupt"): "yolsuz",
    ("4000 Essential English Words::4.Book", "", "ongoing"): "devam eden",
    ("4000 Essential English Words::4.Book", "", "forthcoming"): "gelmekte olan",
    ("4000 Essential English Words::4.Book", "", "whereby"): "vasıtasıyla",
    ("4000 Essential English Words::4.Book", "", "ashore"): "karaya",
    ("4000 Essential English Words::4.Book", "", "stranded"): "mahsur kalmış",
    ("4000 Essential English Words::4.Book", "", "interpret"): "yorumlamak",
    ("4000 Essential English Words::4.Book", "", "albeit"): "-e rağmen",
    ("4000 Essential English Words::4.Book", "", "misguided"): "yanlış yönlendirilmiş",
    ("4000 Essential English Words::4.Book", "", "urban"): "kentsel",
    ("4000 Essential English Words::4.Book", "", "known"): "bilinen",
    ("4000 Essential English Words::4.Book", "", "lunar"): "aya ait",
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
    ("4000 Essential English Words::4.Book", "", "enable"): "olanak sağlamak",
    ("4000 Essential English Words::4.Book", "", "prompt"): "sevk etmek",
    ("4000 Essential English Words::4.Book", "", "align"): "yanında yer almak / desteklemek",
    ("4000 Essential English Words::4.Book", "", "foster"): "geliştirmek / desteklemek",
    ("4000 Essential English Words::4.Book", "", "soar"): "hızla yükselmek",
    ("4000 Essential English Words::4.Book", "", "psychic"): "medyum",
    ("4000 Essential English Words::4.Book", "", "stroke"): "fırça darbesi",
    ("4000 Essential English Words::4.Book", "", "tribute"): "hürmet / saygı",
    ("4000 Essential English Words::4.Book", "", "creation"): "eser",
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
    ("4000 Essential English Words::4.Book", "", "mandarin"): "mandarin çincesi",
    ("4000 Essential English Words::4.Book", "", "veteran"): "deneyimli",
    ("4000 Essential English Words::4.Book", "", "artery"): "atardamar",
    # 5.Book
    ("4000 Essential English Words::5.Book", "", "condensed"): "yoğunlaştırılmış",
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
    ("4000 Essential English Words::5.Book", "", "armed"): "silahlı",
    ("4000 Essential English Words::5.Book", "", "outraged"): "çok öfkeli",
    ("4000 Essential English Words::5.Book", "", "beloved"): "çok sevilen",
    ("4000 Essential English Words::5.Book", "", "complain"): "şikayet etmek",
    ("4000 Essential English Words::5.Book", "", "due"): "vadesi gelmiş",
    ("4000 Essential English Words::5.Book", "", "idle"): "aylak / boş",
    ("4000 Essential English Words::5.Book", "", "overhead"): "tepede",
    ("4000 Essential English Words::5.Book", "", "earthen"): "topraktan",
    ("4000 Essential English Words::5.Book", "", "hostile"): "düşmanca",
    ("4000 Essential English Words::5.Book", "", "scramble"): "didinmek",
    ("4000 Essential English Words::5.Book", "", "buzz"): "heyecan yaratmak",
    ("4000 Essential English Words::5.Book", "", "operate"): "çalışmak / işlemek",
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
    ("4000 Essential English Words::5.Book", "", "sake"): "hatır",
    ("4000 Essential English Words::5.Book", "", "dip"): "düşüş",
    ("4000 Essential English Words::5.Book", "", "cabin"): "kütük ev",
    ("4000 Essential English Words::5.Book", "", "contingent"): "heyet / birlik",
    ("4000 Essential English Words::5.Book", "", "temper"): "mizaç / huy",
    ("4000 Essential English Words::5.Book", "", "celebrity"): "ünlü kişi",
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
    ("4000 Essential English Words::6.Book", "", "inland"): "iç kesim",
    ("4000 Essential English Words::6.Book", "", "municipal"): "belediyeye ait",
    ("4000 Essential English Words::6.Book", "", "aquatic"): "suda yaşayan",
    ("4000 Essential English Words::6.Book", "", "repetitive"): "tekrarlı",
    ("4000 Essential English Words::6.Book", "", "reproductive"): "üremeye ait",
    ("4000 Essential English Words::6.Book", "", "medieval"): "ortaçağa ait",
    ("4000 Essential English Words::6.Book", "", "oriented"): "yönelmiş",
    ("4000 Essential English Words::6.Book", "", "dumb"): "dilsiz",
    ("4000 Essential English Words::6.Book", "", "skeletal"): "iskelete ait",
    ("4000 Essential English Words::6.Book", "", "civic"): "yurttaşlıkla ilgili",
    ("4000 Essential English Words::6.Book", "", "liable"): "olası / muhtemel",
    ("4000 Essential English Words::6.Book", "", "overboard"): "denize düşmüş",
    ("4000 Essential English Words::6.Book", "", "aerial"): "havadan",
    ("4000 Essential English Words::6.Book", "", "sideways"): "yanlamasına",
    ("4000 Essential English Words::6.Book", "", "decorate"): "süslemek / dekore etmek",
    ("4000 Essential English Words::6.Book", "", "hesitant"): "tereddütlü",
    ("4000 Essential English Words::6.Book", "", "overjoyed"): "çok sevinmiş",
    ("4000 Essential English Words::6.Book", "", "winding"): "kıvrımlı",
    ("4000 Essential English Words::6.Book", "", "outstretched"): "uzatılmış",
    ("4000 Essential English Words::6.Book", "", "ingenious"): "dahiyane",
    ("4000 Essential English Words::6.Book", "", "naval"): "donanmayla ilgili",
    ("4000 Essential English Words::6.Book", "", "conceive"): "tasavvur etmek",
    ("4000 Essential English Words::6.Book", "", "dissatisfy"): "memnun edememek",
    ("4000 Essential English Words::6.Book", "", "overwork"): "fazla çalıştırmak",
    ("4000 Essential English Words::6.Book", "", "discharge"): "taburcu etmek",
    ("4000 Essential English Words::6.Book", "", "seclude"): "tecrit etmek",
    ("4000 Essential English Words::6.Book", "", "sob"): "hıçkırarak ağlamak",
    ("4000 Essential English Words::6.Book", "", "stray"): "yolunu şaşırmak",
    ("4000 Essential English Words::6.Book", "", "resent"): "gücenmek / içerlemek",
    ("4000 Essential English Words::6.Book", "", "saturate"): "tamamen ıslatmak",
    ("4000 Essential English Words::6.Book", "", "hack"): "parçalayarak doğramak",
    ("4000 Essential English Words::6.Book", "", "consolidate"): "birleştirip sağlamlaştırmak",
    ("4000 Essential English Words::6.Book", "", "entitle"): "hak vermek",
    ("4000 Essential English Words::6.Book", "", "cater"): "ihtiyaçları karşılamak",
    ("4000 Essential English Words::6.Book", "", "sow"): "tohum ekmek",
    ("4000 Essential English Words::6.Book", "", "zip"): "fermuar çekmek",
    ("4000 Essential English Words::6.Book", "", "oracle"): "kâhin",
    ("4000 Essential English Words::6.Book", "", "epic"): "destan",
    ("4000 Essential English Words::6.Book", "", "register"): "kayıt / sicil",
    ("4000 Essential English Words::6.Book", "", "locale"): "mekan",
    ("4000 Essential English Words::6.Book", "", "stool"): "tabure",
    ("4000 Essential English Words::6.Book", "", "cot"): "portatif yatak",
    ("4000 Essential English Words::6.Book", "", "brute"): "kaba saba kimse",
    ("4000 Essential English Words::6.Book", "", "mob"): "güruh",
    ("4000 Essential English Words::6.Book", "", "bulk"): "büyük bölüm / hacim",
    ("4000 Essential English Words::6.Book", "", "whereabouts"): "bulunduğu yer",
    ("4000 Essential English Words::6.Book", "", "feat"): "büyük başarı",
    ("4000 Essential English Words::6.Book", "", "undergraduate"): "lisans öğrencisi",
    ("4000 Essential English Words::6.Book", "", "shaft"): "uzun sap",
    ("4000 Essential English Words::6.Book", "", "twig"): "ince dal",
    ("4000 Essential English Words::6.Book", "", "preliminary"): "ön",
    ("4000 Essential English Words::6.Book", "", "majesty"): "ululuk",
    ("4000 Essential English Words::6.Book", "", "bliss"): "saadet",
    ("4000 Essential English Words::6.Book", "", "persistent"): "azimli / ısrarcı",
    ("4000 Essential English Words::6.Book", "", "guts"): "iç organlar",
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
    ("4000 Essential English Words::5.Book", "", "display"): "teşhir etmek",
    ("4000 Essential English Words::2.Book", "", "compose"): "parçalardan birleştirmek",
    ("4000 Essential English Words::3.Book", "", "drain"): "gider borusu",
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

    # 2026-09-16: kontrollu cakisma giderme (379 grup, ~823 kart).
    # Her ipucu kitap tanimindaki ayirt edici ogeye gore elle hazirlandi,
    # makine cevirisi degil. Inceleme duzeltmeleri: almighty 4.Book'a
    # tasindi (kucuk harf), ensure tabani 'saglamak / garanti etmek' oldu.
    ("4000 Essential English Words::1.Book", "", "hurry"): "acele etmek (çabuk yapmak)",
    ("4000 Essential English Words::1.Book", "", "rush"): "acele etmek (koşarcasına gitmek)",
    ("4000 Essential English Words::6.Book", "", "dedicate"): "adamak (kendini vermek)",
    ("4000 Essential English Words::2.Book", "", "devote"): "adamak (zaman ayırmak)",
    ("4000 Essential English Words::1.Book", "", "fair"): "adil (makul ve haklı)",
    ("4000 Essential English Words::5.Book", "", "justly"): "adil (hakça yapılan)",
    ("4000 Essential English Words::5.Book", "", "forgive"): "affetmek (küs kalmamak)",
    ("4000 Essential English Words::3.Book", "", "pardon"): "affetmek (hatayı bağışlamak)",
    ("4000 Essential English Words::1.Book", "", "wood"): "ahşap (ağaç malzeme)",
    ("4000 Essential English Words::2.Book", "", "wooden"): "ahşap (ağaçtan yapılmış)",
    ("4000 Essential English Words::6.Book", "", "kin"): "akraba (aile ve hısım)",
    ("4000 Essential English Words::2.Book", "", "relative"): "akraba (aile üyesi)",
    ("4000 Essential English Words::6.Book", "", "fluent"): "akıcı (dili iyi konuşan)",
    ("4000 Essential English Words::4.Book", "", "fluid"): "akıcı (düzgün hareket eden)",
    ("4000 Essential English Words::5.Book", "", "intelligent"): "akıllı (çok zeki)",
    ("4000 Essential English Words::1.Book", "", "smart"): "akıllı (zeki)",
    ("4000 Essential English Words::1.Book", "", "dinner"): "akşam yemeği (günün ana öğünü)",
    ("4000 Essential English Words::3.Book", "", "supper"): "akşam yemeği (akşam öğünü)",
    ("4000 Essential English Words::4.Book", "", "area"): "alan (geniş bir yer)",
    ("4000 Essential English Words::4.Book", "", "field"): "alan (uzmanlık konusu)",
    ("4000 Essential English Words::5.Book", "", "mock"): "alay etmek (zalimce dalga geçmek)",
    ("4000 Essential English Words::5.Book", "", "ridicule"): "alay etmek (aşağılayarak gülmek)",
    ("4000 Essential English Words::6.Book", "", "applaud"): "alkışlamak (beğeni için)",
    ("4000 Essential English Words::4.Book", "", "clap"): "alkışlamak (dikkat çekmek için)",
    ("4000 Essential English Words::6.Book", "", "alternate"): "alternatif (başka bir seçenek)",
    ("4000 Essential English Words::5.Book", "", "alternative"): "alternatif (ilk seçenek yerine)",
    ("4000 Essential English Words::3.Book", "", "beneath"): "altında (daha aşağıda)",
    ("4000 Essential English Words::3.Book", "", "underneath"): "altında (tam alt tarafında)",
    ("4000 Essential English Words::2.Book", "", "aim"): "amaç (gerçekleştirilecek hedef)",
    ("4000 Essential English Words::5.Book", "", "objective"): "amaç (planın hedefi)",
    ("4000 Essential English Words::1.Book", "", "purpose"): "amaç (yapma sebebi)",
    ("4000 Essential English Words::5.Book", "", "abrupt"): "ani (beklenmedik)",
    ("4000 Essential English Words::1.Book", "", "sudden"): "ani (çabucak olan)",
    ("4000 Essential English Words::6.Book", "", "poll"): "anket (görüş sorma)",
    ("4000 Essential English Words::4.Book", "", "survey"): "anket (soru listesi)",
    ("4000 Essential English Words::5.Book", "", "comprehend"): "anlamak (tam kavramak)",
    ("4000 Essential English Words::1.Book", "", "understand"): "anlamak",
    ("4000 Essential English Words::3.Book", "", "agreement"): "anlaşma (resmî karar)",
    ("4000 Essential English Words::1.Book", "", "deal"): "anlaşma (iki taraf arası)",
    ("4000 Essential English Words::4.Book", "", "discord"): "anlaşmazlık (sürtüşme ve kavga)",
    ("4000 Essential English Words::3.Book", "", "dispute"): "anlaşmazlık (tartışma)",
    ("4000 Essential English Words::5.Book", "", "search"): "aramak (dikkatle etrafa bakarak)",
    ("4000 Essential English Words::2.Book", "", "seek"): "aramak (peşinden gitmek)",
    ("4000 Essential English Words::2.Book", "", "investigate"): "araştırmak (olayı incelemek)",
    ("4000 Essential English Words::6.Book", "", "probe"): "araştırmak (soruşturarak öğrenmek)",
    ("4000 Essential English Words::6.Book", "", "companion"): "arkadaş (birlikte vakit geçirilen)",
    ("4000 Essential English Words::6.Book", "", "fellow"): "arkadaş (aynı işi paylaşan)",
    ("4000 Essential English Words::1.Book", "", "friend"): "arkadaş (sevilen yakın tanıdık)",
    ("4000 Essential English Words::3.Book", "", "archaeology"): "arkeoloji (eski toplum kalıntıları)",
    ("4000 Essential English Words::4.Book", "", "archeology"): "arkeoloji (antik eserler)",
    ("4000 Essential English Words::4.Book", "", "boost"): "artırmak (iyileştirerek yükseltmek)",
    ("4000 Essential English Words::1.Book", "", "increase"): "artırmak (miktarını büyütmek)",
    ("4000 Essential English Words::6.Book", "", "aspire"): "arzulamak (hedefe ulaşmak istemek)",
    ("4000 Essential English Words::2.Book", "", "desire"): "arzulamak (bir şeyi istemek)",
    ("4000 Essential English Words::2.Book", "", "hop"): "atlamak (kısa mesafe)",
    ("4000 Essential English Words::2.Book", "", "skip"): "atlamak (yapmadan geçmek)",
    ("4000 Essential English Words::6.Book", "", "discard"): "atmak (elden çıkarmak)",
    ("4000 Essential English Words::2.Book", "", "throw"): "atmak (el ile havaya)",
    ("4000 Essential English Words::3.Book", "", "toss"): "atmak (yavaşça, hafifçe)",
    ("4000 Essential English Words::6.Book", "", "attorney"): "avukat (hukuki danışman)",
    ("4000 Essential English Words::1.Book", "", "lawyer"): "avukat (mahkemede savunan)",
    ("4000 Essential English Words::1.Book", "", "month"): "ay (yılın bölümü)",
    ("4000 Essential English Words::2.Book", "", "moon"): "ay (dünyanın uydusu)",
    ("4000 Essential English Words::6.Book", "", "enlighten"): "aydınlatmak (bilgi vererek)",
    ("4000 Essential English Words::5.Book", "", "illuminate"): "aydınlatmak (ışık tutmak)",
    ("4000 Essential English Words::2.Book", "", "also"): "ayrıca (bir de)",
    ("4000 Essential English Words::3.Book", "", "furthermore"): "ayrıca (üstelik)",
    ("4000 Essential English Words::4.Book", "", "diverge"): "ayrılmak (farklı yöne sapmak)",
    ("4000 Essential English Words::1.Book", "", "leave"): "ayrılmak (bir yerden gitmek)",
    ("4000 Essential English Words::2.Book", "", "decrease"): "azaltmak (öncekinden düşürmek)",
    ("4000 Essential English Words::6.Book", "", "diminish"): "azaltmak (giderek küçülmek)",
    ("4000 Essential English Words::5.Book", "", "reduce"): "azaltmak (boyutunu küçültmek)",
    ("4000 Essential English Words::5.Book", "", "articulate"): "açık sözlü (net anlatan)",
    ("4000 Essential English Words::6.Book", "", "outspoken"): "açık sözlü (çekinmeden söyleyen)",
    ("4000 Essential English Words::2.Book", "", "net"): "ağ (hayvan yakalama)",
    ("4000 Essential English Words::4.Book", "", "network"): "ağ (bağlı kişiler)",
    ("4000 Essential English Words::1.Book", "", "web"): "ağ (örümcek ağı)",
    ("4000 Essential English Words::3.Book", "", "dominant"): "baskın (daha güçlü)",
    ("4000 Essential English Words::4.Book", "", "predominant"): "baskın (en yaygın)",
    ("4000 Essential English Words::1.Book", "", "shout"): "bağırmak (yüksek sesle)",
    ("4000 Essential English Words::6.Book", "", "yell"): "bağırmak (birine seslenmek)",
    ("4000 Essential English Words::2.Book", "", "accomplish"): "başarmak (işi bitirmek)",
    ("4000 Essential English Words::1.Book", "", "achieve"): "başarmak (çabayla elde etmek)",
    ("4000 Essential English Words::4.Book", "", "commence"): "başlamak (resmî dille)",
    ("4000 Essential English Words::1.Book", "", "start"): "başlamak (işe koyulmak)",
    ("4000 Essential English Words::3.Book", "", "headline"): "başlık (gazete haberi)",
    ("4000 Essential English Words::3.Book", "", "hood"): "başlık (kabanın kısmı)",
    ("4000 Essential English Words::3.Book", "", "refer"): "başvurmak (değinmek)",
    ("4000 Essential English Words::2.Book", "", "resort"): "başvurmak (çare olarak)",
    ("4000 Essential English Words::4.Book", "", "resourceful"): "becerikli (elindekini kullanan)",
    ("4000 Essential English Words::5.Book", "", "skillful"): "becerikli (işini iyi yapan)",
    ("4000 Essential English Words::5.Book", "", "await"): "beklemek (resmî, nesne alan)",
    ("4000 Essential English Words::2.Book", "", "wait"): "beklemek (bir yerde durmak)",
    ("4000 Essential English Words::6.Book", "", "ambiguous"): "belirsiz (iki anlama gelen)",
    ("4000 Essential English Words::5.Book", "", "obscure"): "belirsiz (pek bilinmeyen)",
    ("4000 Essential English Words::1.Book", "", "vague"): "belirsiz (ayrıntı vermeyen)",
    ("4000 Essential English Words::2.Book", "", "maybe"): "belki (doğru olabilir)",
    ("4000 Essential English Words::2.Book", "", "perhaps"): "belki (gerçekleşebilir)",
    ("4000 Essential English Words::5.Book", "", "alike"): "benzer (karşılıklı olarak)",
    ("4000 Essential English Words::6.Book", "", "analogous"): "benzer (bazı yönlerden)",
    ("4000 Essential English Words::4.Book", "", "similar"): "benzer (neredeyse aynı)",
    ("4000 Essential English Words::6.Book", "", "component"): "bileşen (makinenin parçası)",
    ("4000 Essential English Words::2.Book", "", "ingredient"): "bileşen (yemek malzemesi)",
    ("4000 Essential English Words::1.Book", "", "bit"): "biraz (az miktarda)",
    ("4000 Essential English Words::2.Book", "", "somewhat"): "biraz (bir dereceye kadar)",
    ("4000 Essential English Words::5.Book", "", "combine"): "birleştirmek (tek şey yapmak)",
    ("4000 Essential English Words::1.Book", "", "merge"): "birleştirmek (tek bütün yapmak)",
    ("4000 Essential English Words::3.Book", "", "unify"): "birleştirmek (insanları kaynaştırmak)",
    ("4000 Essential English Words::6.Book", "", "bicycle"): "bisiklet (pedallı iki tekerlekli)",
    ("4000 Essential English Words::1.Book", "", "bike"): "bisiklet (insan gücüyle)",
    ("4000 Essential English Words::6.Book", "", "adjacent"): "bitişik (hemen yanında)",
    ("4000 Essential English Words::6.Book", "", "adjoining"): "bitişik (odayla birleşik)",
    ("4000 Essential English Words::6.Book", "", "abundant"): "bol (miktarca çok)",
    ("4000 Essential English Words::1.Book", "", "plenty"): "bol (yeterinden fazla)",
    ("4000 Essential English Words::4.Book", "", "disrupt"): "bozmak (işleyişini engellemek)",
    ("4000 Essential English Words::5.Book", "", "impair"): "bozmak (zayıflatıp kötüleştirmek)",
    ("4000 Essential English Words::3.Book", "", "spoil"): "bozmak (çürütmek)",
    ("4000 Essential English Words::5.Book", "", "blank"): "boş (üzeri yazısız)",
    ("4000 Essential English Words::3.Book", "", "empty"): "boş (içi dolu olmayan)",
    ("4000 Essential English Words::4.Book", "", "cavity"): "boşluk (madde içindeki oyuk)",
    ("4000 Essential English Words::3.Book", "", "gap"): "boşluk (iki şey arası)",
    ("4000 Essential English Words::5.Book", "", "although"): "buna rağmen (karşıtlık kurar)",
    ("4000 Essential English Words::4.Book", "", "notwithstanding"): "buna rağmen (her şeye karşın)",
    ("4000 Essential English Words::Extra", "3_124", "beetle"): "böcek (kınkanatlı)",
    ("4000 Essential English Words::2.Book", "", "bug"): "böcek (küçük haşere)",
    ("4000 Essential English Words::5.Book", "", "chapter"): "bölüm (kitabın kısmı)",
    ("4000 Essential English Words::6.Book", "", "episode"): "bölüm (dizinin kısmı)",
    ("4000 Essential English Words::5.Book", "", "charm"): "büyülemek (kişiliğiyle etkilemek)",
    ("4000 Essential English Words::5.Book", "", "enchant"): "büyülemek (hayran bırakmak)",
    ("4000 Essential English Words::2.Book", "", "fascinate"): "büyülemek (merakla bağlamak)",
    ("4000 Essential English Words::4.Book", "", "enlarge"): "büyütmek (boyutunu artırmak)",
    ("4000 Essential English Words::4.Book", "", "magnify"): "büyütmek (olduğundan büyük göstermek)",
    ("4000 Essential English Words::5.Book", "", "lively"): "canlı (enerjik ve hareketli)",
    ("4000 Essential English Words::5.Book", "", "vivid"): "canlı (parlak renkli)",
    ("4000 Essential English Words::2.Book", "", "heaven"): "cennet (ölümden sonra gidilen)",
    ("4000 Essential English Words::5.Book", "", "paradise"): "cennet (kusursuz mutluluk yeri)",
    ("4000 Essential English Words::5.Book", "", "bravery"): "cesaret (yiğitçe davranış)",
    ("4000 Essential English Words::2.Book", "", "courage"): "cesaret (korkusuzluk hissi)",
    ("4000 Essential English Words::2.Book", "", "bold"): "cesur (atılmaktan korkmayan)",
    ("4000 Essential English Words::2.Book", "", "brave"): "cesur (tehlikeye göğüs geren)",
    ("4000 Essential English Words::4.Book", "", "penalize"): "cezalandırmak (ceza kesmek)",
    ("4000 Essential English Words::1.Book", "", "punish"): "cezalandırmak (acı çektirmek)",
    ("4000 Essential English Words::6.Book", "", "earnest"): "ciddi (içten ve dürüst)",
    ("4000 Essential English Words::6.Book", "", "solemn"): "ciddi (ağırbaşlı)",
    ("4000 Essential English Words::2.Book", "", "appliance"): "cihaz (ev aleti)",
    ("4000 Essential English Words::5.Book", "", "device"): "cihaz (makine veya alet)",
    ("4000 Essential English Words::4.Book", "", "plunge"): "dalmak (hızla derine)",
    ("4000 Essential English Words::6.Book", "", "prosecute"): "dava açmak (suçlayarak)",
    ("4000 Essential English Words::2.Book", "", "sue"): "dava açmak (zarar için)",
    ("4000 Essential English Words::1.Book", "", "behavior"): "davranış (sergilenen hareketler)",
    ("4000 Essential English Words::5.Book", "", "conduct"): "davranış (tavır ve tutum)",
    ("4000 Essential English Words::5.Book", "", "disperse"): "dağıtmak (yayılıp gitmek)",
    ("4000 Essential English Words::5.Book", "", "distribute"): "dağıtmak (herkese pay vermek)",
    ("4000 Essential English Words::3.Book", "", "scatter"): "dağıtmak (etrafa saçmak)",
    ("4000 Essential English Words::4.Book", "", "audit"): "denetlemek (mali kayıtları)",
    ("4000 Essential English Words::4.Book", "", "oversee"): "denetlemek (ilerlemeyi gözetmek)",
    ("4000 Essential English Words::6.Book", "", "supervise"): "denetlemek (çalışanları gözetmek)",
    ("4000 Essential English Words::2.Book", "", "journal"): "dergi (akademik yayın)",
    ("4000 Essential English Words::1.Book", "", "magazine"): "dergi (haber ve yazı)",
    ("4000 Essential English Words::2.Book", "", "proceed"): "devam etmek (yola koyulmak)",
    ("4000 Essential English Words::2.Book", "", "resume"): "devam etmek (aradan sonra sürdürmek)",
    ("4000 Essential English Words::2.Book", "", "disadvantage"): "dezavantaj (işi zorlaştıran durum)",
    ("4000 Essential English Words::6.Book", "", "drawback"): "dezavantaj (olumsuz yan)",
    ("4000 Essential English Words::4.Book", "", "assess"): "değerlendirmek (niteliğini yargılamak)",
    ("4000 Essential English Words::5.Book", "", "evaluate"): "değerlendirmek (karar için incelemek)",
    ("4000 Essential English Words::3.Book", "", "precious"): "değerli (çok kıymetli)",
    ("4000 Essential English Words::5.Book", "", "worthwhile"): "değerli (zahmete değer)",
    ("4000 Essential English Words::3.Book", "", "steep"): "dik (eğimi sarp)",
    ("4000 Essential English Words::5.Book", "", "upright"): "dik (dimdik ayakta)",
    ("4000 Essential English Words::1.Book", "", "attention"): "dikkat (birinin ilgisi)",
    ("4000 Essential English Words::3.Book", "", "caution"): "dikkat (tehlikeden sakınma)",
    ("4000 Essential English Words::1.Book", "", "consider"): "dikkate almak (üzerinde düşünmek)",
    ("4000 Essential English Words::5.Book", "", "heed"): "dikkate almak (öğüde uymak)",
    ("4000 Essential English Words::6.Book", "", "erect"): "dikmek (inşa etmek)",
    ("4000 Essential English Words::3.Book", "", "sew"): "dikmek (iğne iplikle)",
    ("4000 Essential English Words::5.Book", "", "stitch"): "dikmek (kumaşları birleştirerek)",
    ("4000 Essential English Words::2.Book", "", "language"): "dil (iletişim sistemi)",
    ("4000 Essential English Words::Extra", "1_1_8", "tongue"): "dil (ağızdaki organ)",
    ("4000 Essential English Words::2.Book", "", "tongue"): "dil (ağızdaki organ)",
    ("4000 Essential English Words::4.Book", "", "curb"): "dizginlemek (artmasını önlemek)",
    ("4000 Essential English Words::6.Book", "", "restrain"): "dizginlemek (fiziksel güçle tutmak)",
    ("4000 Essential English Words::4.Book", "", "array"): "dizi (çok sayıda)",
    ("4000 Essential English Words::4.Book", "", "sequence"): "dizi (art arda gelen)",
    ("4000 Essential English Words::Extra", "1_1_9", "tooth"): "diş (ağız içindeki)",
    ("4000 Essential English Words::6.Book", "", "tusk"): "diş (filin uzun dişi)",
    ("4000 Essential English Words::1.Book", "", "doctor"): "doktor (hastalara bakan)",
    ("4000 Essential English Words::5.Book", "", "physician"): "doktor (tıp uzmanı)",
    ("4000 Essential English Words::3.Book", "", "closet"): "dolap (küçük depo odası)",
    ("4000 Essential English Words::2.Book", "", "cupboard"): "dolap (yiyecek/eşya saklanan)",
    ("4000 Essential English Words::2.Book", "", "confirm"): "doğrulamak / teyit etmek (doğruluğunu onaylamak)",
    ("4000 Essential English Words::6.Book", "", "inherent"): "doğuştan (ayrılmaz parçası)",
    ("4000 Essential English Words::6.Book", "", "innate"): "doğuştan (sonradan öğrenilmemiş)",
    ("4000 Essential English Words::4.Book", "", "cease"): "durdurmak (son vermek)",
    ("4000 Essential English Words::5.Book", "", "halt"): "durdurmak (hareketi kesmek)",
    ("4000 Essential English Words::3.Book", "", "circumstance"): "durum (koşullar)",
    ("4000 Essential English Words::1.Book", "", "condition"): "durum (içinde bulunulan hâl)",
    ("4000 Essential English Words::2.Book", "", "status"): "durum (toplumsal konum)",
    ("4000 Essential English Words::6.Book", "", "posture"): "duruş (vücudun pozisyonu)",
    ("4000 Essential English Words::5.Book", "", "stance"): "duruş (konudaki tutum)",
    ("4000 Essential English Words::1.Book", "", "announce"): "duyurmak (ilan etmek)",
    ("4000 Essential English Words::4.Book", "", "publicize"): "duyurmak (tanıtımını yapmak)",
    ("4000 Essential English Words::2.Book", "", "pour"): "dökmek (sıvıyı boşaltmak)",
    ("4000 Essential English Words::2.Book", "", "spill"): "dökmek (kazara devirmek)",
    ("4000 Essential English Words::3.Book", "", "rotate"): "döndürmek (ekseni çevresinde)",
    ("4000 Essential English Words::2.Book", "", "spin"): "döndürmek (hızla kendi çevresinde)",
    ("4000 Essential English Words::4.Book", "", "cycle"): "döngü (başa dönen olaylar)",
    ("4000 Essential English Words::5.Book", "", "loop"): "döngü (halka yapılmış ip)",
    ("4000 Essential English Words::2.Book", "", "convert"): "dönüştürmek (başka şeye çevirmek)",
    ("4000 Essential English Words::4.Book", "", "transform"): "dönüştürmek (kökten değiştirmek)",
    ("4000 Essential English Words::3.Book", "", "poke"): "dürtmek (parmakla hızlıca itmek)",
    ("4000 Essential English Words::6.Book", "", "prod"): "dürtmek (sivri uçla itmek)",
    ("4000 Essential English Words::1.Book", "", "arrange"): "düzenlemek (yerlerini ayarlamak)",
    ("4000 Essential English Words::5.Book", "", "edit"): "düzenlemek (yazıyı düzeltmek)",
    ("4000 Essential English Words::5.Book", "", "regulate"): "düzenlemek (kuralla denetlemek)",
    ("4000 Essential English Words::1.Book", "", "regular"): "düzenli (belirli aralıklarla)",
    ("4000 Essential English Words::3.Book", "", "tidy"): "düzenli (tertipli ve temiz)",
    ("4000 Essential English Words::2.Book", "", "enemy"): "düşman (savaşan ülke)",
    ("4000 Essential English Words::6.Book", "", "foe"): "düşman (hasım/rakip)",
    ("4000 Essential English Words::6.Book", "", "contemplate"): "düşünmek (kafa yormak)",
    ("4000 Essential English Words::5.Book", "", "ponder"): "düşünmek (uzun uzun tartmak)",
    ("4000 Essential English Words::1.Book", "", "think"): "düşünmek (görüş sahibi olmak)",
    ("4000 Essential English Words::1.Book", "", "drop"): "düşürmek (elinden kaçırmak)",
    ("4000 Essential English Words::1.Book", "", "lower"): "düşürmek (aşağı indirmek)",
    ("4000 Essential English Words::2.Book", "", "legend"): "efsane (geçmişten gelen hikâye)",
    ("4000 Essential English Words::5.Book", "", "myth"): "efsane (kültürü açıklayan öykü)",
    ("4000 Essential English Words::2.Book", "", "attach"): "eklemek (iki şeyi birleştirmek)",
    ("4000 Essential English Words::2.Book", "", "insert"): "eklemek (içine yerleştirmek)",
    ("4000 Essential English Words::Extra", "2_13", "dress"): "elbise (tek parça giysi)",
    ("4000 Essential English Words::3.Book", "", "robe"): "elbise (bol ve uzun giysi)",
    ("4000 Essential English Words::3.Book", "", "acquire"): "elde etmek (mülk edinmek)",
    ("4000 Essential English Words::2.Book", "", "obtain"): "elde etmek (istenen şeyi almak)",
    ("4000 Essential English Words::5.Book", "", "glove"): "eldiven (tek tanesi)",
    ("4000 Essential English Words::Extra", "2_15", "gloves"): "eldiven (bir çift)",
    ("4000 Essential English Words::2.Book", "", "criticize"): "eleştirmek (kötü yönlerini saymak)",
    ("4000 Essential English Words::5.Book", "", "critique"): "eleştirmek (iyi kötü yönlerini)",
    ("4000 Essential English Words::1.Book", "", "certain"): "emin (bilgisi kesin)",
    ("4000 Essential English Words::3.Book", "", "hinder"): "engellemek (yapmasını zorlaştırmak)",
    ("4000 Essential English Words::4.Book", "", "obstruct"): "engellemek (yolunu tıkamak)",
    ("4000 Essential English Words::4.Book", "", "defer"): "ertelemek (sonraya bırakmak)",
    ("4000 Essential English Words::3.Book", "", "postpone"): "ertelemek (planlanandan sonraya)",
    ("4000 Essential English Words::5.Book", "", "flesh"): "et (bedendeki kas/yağ)",
    ("4000 Essential English Words::1.Book", "", "meat"): "et (yemek olarak)",
    ("4000 Essential English Words::5.Book", "", "ethical"): "etik (doğru davranış)",
    ("4000 Essential English Words::4.Book", "", "ethics"): "etik (ahlak kuralları)",
    ("4000 Essential English Words::1.Book", "", "effect"): "etki (yapılan değişiklik)",
    ("4000 Essential English Words::5.Book", "", "impact"): "etki (büyük tesir)",
    ("4000 Essential English Words::3.Book", "", "host"): "ev sahibi (konuk ağırlayan)",
    ("4000 Essential English Words::4.Book", "", "landlord"): "ev sahibi (kira alan)",
    ("4000 Essential English Words::5.Book", "", "lean"): "eğilmek (bir yöne yaslanmak)",
    ("4000 Essential English Words::6.Book", "", "tilt"): "eğilmek (eğik konuma getirmek)",
    ("4000 Essential English Words::6.Book", "", "incline"): "eğim (dik yükseliş)",
    ("4000 Essential English Words::3.Book", "", "slope"): "eğim (meyilli zemin)",
    ("4000 Essential English Words::2.Book", "", "amuse"): "eğlendirmek (güldürüp hoş etmek)",
    ("4000 Essential English Words::1.Book", "", "entertain"): "eğlendirmek (keyifli vakit geçirtmek)",
    ("4000 Essential English Words::4.Book", "", "equal"): "eşit (aynı ölçüde)",
    ("4000 Essential English Words::6.Book", "", "evenly"): "eşit (dengeli dağıtılmış)",
    ("4000 Essential English Words::1.Book", "", "different"): "farklı (aynı olmayan)",
    ("4000 Essential English Words::3.Book", "", "distinct"): "farklı (göze çarpan)",
    ("4000 Essential English Words::4.Book", "", "excess"): "fazlalık (gereğinden çok)",
    ("4000 Essential English Words::4.Book", "", "surplus"): "fazlalık (artan miktar)",
    ("4000 Essential English Words::3.Book", "", "awkward"): "garip (utandırıcı ve rahatsız)",
    ("4000 Essential English Words::2.Book", "", "strange"): "garip (alışılmadık)",
    ("4000 Essential English Words::3.Book", "", "income"): "gelir (kişisel kazanç)",
    ("4000 Essential English Words::4.Book", "", "revenue"): "gelir (şirket kazancı)",
    ("4000 Essential English Words::5.Book", "", "evolve"): "gelişmek (zamanla değişmek)",
    ("4000 Essential English Words::6.Book", "", "flourish"): "gelişmek (serpilip büyümek)",
    ("4000 Essential English Words::3.Book", "", "prosper"): "gelişmek (zenginleşmek)",
    ("4000 Essential English Words::6.Book", "", "thrive"): "gelişmek (sağlıkla büyümek)",
    ("4000 Essential English Words::1.Book", "", "develop"): "geliştirmek (daha ileri götürmek)",
    ("4000 Essential English Words::5.Book", "", "enhance"): "geliştirmek (değerini artırmak)",
    ("4000 Essential English Words::6.Book", "", "improve"): "geliştirmek (durumu iyileştirmek)",
    ("4000 Essential English Words::2.Book", "", "broad"): "geniş (enli, dar değil)",
    ("4000 Essential English Words::5.Book", "", "vast"): "geniş (çok büyük)",
    ("4000 Essential English Words::1.Book", "", "wide"): "geniş (yanlara doğru)",
    ("4000 Essential English Words::2.Book", "", "breadth"): "genişlik (yüzeyin eni)",
    ("4000 Essential English Words::4.Book", "", "width"): "genişlik (ölçülen en)",
    ("4000 Essential English Words::3.Book", "", "retreat"): "geri çekilmek (yenilgiyle kaçmak)",
    ("4000 Essential English Words::3.Book", "", "withdraw"): "geri çekilmek (ülkesine dönmek)",
    ("4000 Essential English Words::5.Book", "", "genuine"): "gerçek (sahte olmayan)",
    ("4000 Essential English Words::1.Book", "", "real"): "gerçek (var olan)",
    ("4000 Essential English Words::2.Book", "", "entrance"): "giriş (binaya girilen yer)",
    ("4000 Essential English Words::4.Book", "", "input"): "giriş (bilgisayara verilen veri)",
    ("4000 Essential English Words::5.Book", "", "confidential"): "gizli (sır olarak saklanan)",
    ("4000 Essential English Words::2.Book", "", "hidden"): "gizli (fark edilmeyen)",
    ("4000 Essential English Words::3.Book", "", "privacy"): "gizlilik (yalnız kalma hâli)",
    ("4000 Essential English Words::6.Book", "", "secrecy"): "gizlilik (sır saklama)",
    ("4000 Essential English Words::2.Book", "", "shade"): "gölge (güneşten korunan yer)",
    ("4000 Essential English Words::2.Book", "", "shadow"): "gölge (cismin yansıması)",
    ("4000 Essential English Words::2.Book", "", "duty"): "görev (zorunlu sorumluluk)",
    ("4000 Essential English Words::2.Book", "", "task"): "görev (yapılacak zor iş)",
    ("4000 Essential English Words::3.Book", "", "spectacle"): "gösteri (hayranlık veren görüntü)",
    ("4000 Essential English Words::6.Book", "", "stunt"): "gösteri (dikkat çeken numara)",
    ("4000 Essential English Words::6.Book", "", "din"): "gürültü (uzun süren patırtı)",
    ("4000 Essential English Words::1.Book", "", "noise"): "gürültü (rahatsız eden ses)",
    ("4000 Essential English Words::4.Book", "", "power"): "güç (etkileme yetkisi)",
    ("4000 Essential English Words::2.Book", "", "strength"): "güç (fiziksel kuvvet)",
    ("4000 Essential English Words::2.Book", "", "motion"): "hareket (el kol işareti)",
    ("4000 Essential English Words::4.Book", "", "movement"): "hareket (toplumsal akım)",
    ("4000 Essential English Words::5.Book", "", "awesome"): "harika (heybetli ve etkileyici)",
    ("4000 Essential English Words::1.Book", "", "great"): "harika (çok iyi)",
    ("4000 Essential English Words::2.Book", "", "delicate"): "hassas (kolay kırılan)",
    ("4000 Essential English Words::2.Book", "", "sensitive"): "hassas (çabuk incinen)",
    ("4000 Essential English Words::2.Book", "", "fault"): "hata (kusurun sahibi)",
    ("4000 Essential English Words::1.Book", "", "mistake"): "hata (yanlış yapılan)",
    ("4000 Essential English Words::4.Book", "", "subsist"): "hayatta kalmak (geçimini sağlamak)",
    ("4000 Essential English Words::4.Book", "", "survive"): "hayatta kalmak (ölümden kurtulmak)",
    ("4000 Essential English Words::3.Book", "", "benefactor"): "hayırsever (para veren kişi)",
    ("4000 Essential English Words::2.Book", "", "charitable"): "hayırsever (yardım amaçlı kuruluş)",
    ("4000 Essential English Words::5.Book", "", "charity"): "hayırseverlik (ihtiyaç sahibine yardım)",
    ("4000 Essential English Words::6.Book", "", "philanthropy"): "hayırseverlik (karşılıksız yardım)",
    ("4000 Essential English Words::5.Book", "", "rapid"): "hızlı (çabuk değişen)",
    ("4000 Essential English Words::3.Book", "", "swift"): "hızlı (çevik ve atik)",
    ("4000 Essential English Words::4.Book", "", "administrative"): "idari (kurum yönetimiyle ilgili)",
    ("4000 Essential English Words::6.Book", "", "managerial"): "idari (yöneticilikle ilgili)",
    ("4000 Essential English Words::6.Book", "", "allege"): "iddia etmek (kanıtsız öne sürmek)",
    ("4000 Essential English Words::1.Book", "", "claim"): "iddia etmek (doğru olduğunu söylemek)",
    ("4000 Essential English Words::2.Book", "", "convince"): "ikna etmek (bir şeye inandırmak)",
    ("4000 Essential English Words::2.Book", "", "persuade"): "ikna etmek (yapmaya razı etmek)",
    ("4000 Essential English Words::5.Book", "", "medication"): "ilaç (doktorun verdiği)",
    ("4000 Essential English Words::4.Book", "", "communicate"): "iletişim kurmak (duyguları aktarmak)",
    ("4000 Essential English Words::1.Book", "", "contact"): "iletişim kurmak (bağlantıya geçmek)",
    ("4000 Essential English Words::1.Book", "", "associate"): "ilişkilendirmek (zihinde bağdaştırmak)",
    ("4000 Essential English Words::4.Book", "", "correlate"): "ilişkilendirmek (ölçümle bağlantılı olmak)",
    ("4000 Essential English Words::6.Book", "", "concession"): "imtiyaz (karşı tarafa bırakılan hak)",
    ("4000 Essential English Words::6.Book", "", "franchise"): "imtiyaz (marka satış hakkı)",
    ("4000 Essential English Words::5.Book", "", "autograph"): "imza (ünlünün el yazısı)",
    ("4000 Essential English Words::5.Book", "", "signature"): "imza (belgeye atılan ad)",
    ("4000 Essential English Words::1.Book", "", "belief"): "inanç (doğruluğuna inanmak)",
    ("4000 Essential English Words::2.Book", "", "faith"): "inanç (kanıtsız güven)",
    ("4000 Essential English Words::3.Book", "", "slim"): "ince (zayıf yapılı)",
    ("4000 Essential English Words::5.Book", "", "subtle"): "ince (fark edilmesi güç)",
    ("4000 Essential English Words::6.Book", "", "descent"): "iniş (aşağı doğru hareket)",
    ("4000 Essential English Words::4.Book", "", "landing"): "iniş (uçakla yere konma)",
    ("4000 Essential English Words::2.Book", "", "clue"): "ipucu (suçu çözen delil)",
    ("4000 Essential English Words::5.Book", "", "hint"): "ipucu (sezdiren küçük bilgi)",
    ("4000 Essential English Words::6.Book", "", "propel"): "itmek (ileri doğru sürüklemek)",
    ("4000 Essential English Words::3.Book", "", "shove"): "itmek (var gücüyle kaba)",
    ("4000 Essential English Words::3.Book", "", "thrust"): "itmek (hızla ve sertçe)",
    ("4000 Essential English Words::4.Book", "", "internal"): "içsel (bir şeyin içinde)",
    ("4000 Essential English Words::6.Book", "", "intrinsic"): "içsel (özünde bulunan)",
    ("4000 Essential English Words::3.Book", "", "disgusting"): "iğrenç (çok tiksindirici)",
    ("4000 Essential English Words::4.Book", "", "gross"): "iğrenç (mide bulandıran)",
    ("4000 Essential English Words::6.Book", "", "nasty"): "iğrenç (pis ve tatsız)",
    ("4000 Essential English Words::4.Book", "", "collaborate"): "işbirliği yapmak (birlikte üretmek)",
    ("4000 Essential English Words::4.Book", "", "cooperate"): "işbirliği yapmak (uyum gösterip yardım etmek)",
    ("4000 Essential English Words::2.Book", "", "hire"): "işe almak (ücretle çalıştırmak)",
    ("4000 Essential English Words::6.Book", "", "recruit"): "işe almak (örgüte üye seçmek)",
    ("4000 Essential English Words::6.Book", "", "crust"): "kabuk (ekmek dış yüzeyi)",
    ("4000 Essential English Words::2.Book", "", "shell"): "kabuk (midye gibi sert örtü)",
    ("4000 Essential English Words::1.Book", "", "accept"): "kabul etmek (sunulanı almak)",
    ("4000 Essential English Words::3.Book", "", "acknowledge"): "kabul etmek (doğruluğunu onaylamak)",
    ("4000 Essential English Words::5.Book", "", "concede"): "kabul etmek (istemeyerek itiraf etmek)",
    ("4000 Essential English Words::5.Book", "", "destiny"): "kader (kişinin yaşayacakları)",
    ("4000 Essential English Words::3.Book", "", "fate"): "kader (olayları belirleyen güç)",
    ("4000 Essential English Words::2.Book", "", "lift"): "kaldırmak (yukarı doğru)",
    ("4000 Essential English Words::1.Book", "", "remove"): "kaldırmak (yerinden alıp götürmek)",
    ("4000 Essential English Words::3.Book", "", "canal"): "kanal (su yolu)",
    ("4000 Essential English Words::3.Book", "", "channel"): "kanal (akarsuyun açtığı yatak)",
    ("4000 Essential English Words::1.Book", "", "evidence"): "kanıt (iddiayı destekleyen belge)",
    ("4000 Essential English Words::2.Book", "", "proof"): "kanıt (gerçekliği gösteren)",
    ("4000 Essential English Words::2.Book", "", "close"): "kapatmak (açıklığı örtmek)",
    ("4000 Essential English Words::2.Book", "", "shut"): "kapatmak (sımsıkı örtmek)",
    ("4000 Essential English Words::3.Book", "", "extent"): "kapsam (derece ve ciddiyet)",
    ("4000 Essential English Words::4.Book", "", "scope"): "kapsam (ilgili olduğu alan)",
    ("4000 Essential English Words::5.Book", "", "comprehensive"): "kapsamlı (her ayrıntıyı içeren)",
    ("4000 Essential English Words::3.Book", "", "extensive"): "kapsamlı (geniş alana yayılan)",
    ("4000 Essential English Words::1.Book", "", "door"): "kapı (bina girişi)",
    ("4000 Essential English Words::1.Book", "", "gate"): "kapı (bahçe parmaklığı)",
    ("4000 Essential English Words::6.Book", "", "tumult"): "kargaşa (kalabalığın uğultusu)",
    ("4000 Essential English Words::6.Book", "", "uproar"): "kargaşa (öfkeyle yükselen gürültü)",
    ("4000 Essential English Words::3.Book", "", "blend"): "karıştırmak (bütünleşene dek)",
    ("4000 Essential English Words::5.Book", "", "confuse"): "karıştırmak (kafasını bulandırmak)",
    ("4000 Essential English Words::3.Book", "", "stir"): "karıştırmak (kaşıkla hafifçe)",
    ("4000 Essential English Words::5.Book", "", "mixture"): "karışım (elde edilen bileşim)",
    ("4000 Essential English Words::5.Book", "", "cyclone"): "kasırga (dönen rüzgârlı fırtına)",
    ("4000 Essential English Words::2.Book", "", "hurricane"): "kasırga (okyanusta kopan fırtına)",
    ("4000 Essential English Words::3.Book", "", "endure"): "katlanmak (zorluğa dayanmak)",
    ("4000 Essential English Words::6.Book", "", "undergo"): "katlanmak (maruz kalıp geçirmek)",
    ("4000 Essential English Words::4.Book", "", "rigid"): "katı (değiştirilemeyen kural)",
    ("4000 Essential English Words::2.Book", "", "strict"): "katı (kurallara uyduran)",
    ("4000 Essential English Words::1.Book", "", "attend"): "katılmak (bir yere gitmek)",
    ("4000 Essential English Words::2.Book", "", "participate"): "katılmak (aktif görev almak)",
    ("4000 Essential English Words::3.Book", "", "grasp"): "kavramak (elle tutmak)",
    ("4000 Essential English Words::5.Book", "", "grip"): "kavramak (sımsıkı yapışmak)",
    ("4000 Essential English Words::6.Book", "", "glide"): "kaymak (havada süzülmek)",
    ("4000 Essential English Words::2.Book", "", "slip"): "kaymak (kayıp düşmek)",
    ("4000 Essential English Words::5.Book", "", "resource"): "kaynak (kullanılabilir para/malzeme)",
    ("4000 Essential English Words::5.Book", "", "source"): "kaynak (bir şeyin çıktığı yer)",
    ("4000 Essential English Words::2.Book", "", "dig"): "kazmak (çukur açmak)",
    ("4000 Essential English Words::6.Book", "", "excavate"): "kazmak (kalıntı aramak için)",
    ("4000 Essential English Words::6.Book", "", "engrave"): "kazımak (yüzeye yazı oymak)",
    ("4000 Essential English Words::5.Book", "", "scrape"): "kazımak (sertçe sürtüp soymak)",
    ("4000 Essential English Words::5.Book", "", "refrain"): "kaçınmak (yapmaktan geri durmak)",
    ("4000 Essential English Words::6.Book", "", "arch"): "kemer (köprünün eğrisi)",
    ("4000 Essential English Words::Extra", "2_3", "belt"): "kemer (bele takılan kayış)",
    ("4000 Essential English Words::2.Book", "", "definite"): "kesin (şüpheye yer bırakmayan)",
    ("4000 Essential English Words::4.Book", "", "definitive"): "kesin (en yetkin ve resmî)",
    ("4000 Essential English Words::6.Book", "", "exact"): "kesin (her ayrıntısı doğru)",
    ("4000 Essential English Words::2.Book", "", "sharp"): "keskin (kolayca kesen)",
    ("4000 Essential English Words::5.Book", "", "stark"): "keskin (çarpıcı ve belirgin)",
    ("4000 Essential English Words::2.Book", "", "discover"): "keşfetmek (ilk kez bulmak)",
    ("4000 Essential English Words::1.Book", "", "explore"): "keşfetmek (yeni yerler gezmek)",
    ("4000 Essential English Words::5.Book", "", "hermit"): "keşiş (yalnız yaşayan)",
    ("4000 Essential English Words::2.Book", "", "monk"): "keşiş (dindar, sade yaşayan)",
    ("4000 Essential English Words::4.Book", "", "contaminate"): "kirletmek (zehirli madde karıştırmak)",
    ("4000 Essential English Words::5.Book", "", "pollute"): "kirletmek (havayı/suyu pisletmek)",
    ("4000 Essential English Words::2.Book", "", "classic"): "klasik (geçmişten gelen tipik)",
    ("4000 Essential English Words::4.Book", "", "classical"): "klasik (ciddi sanat müziği)",
    ("4000 Essential English Words::5.Book", "", "odor"): "koku (belirgin ve keskin)",
    ("4000 Essential English Words::3.Book", "", "scent"): "koku (hoş çiçek kokusu)",
    ("4000 Essential English Words::4.Book", "", "check"): "kontrol etmek (doğru mu diye sormak)",
    ("4000 Essential English Words::1.Book", "", "control"): "kontrol etmek (yönlendirip yönetmek)",
    ("4000 Essential English Words::6.Book", "", "sever"): "koparmak (tamamen kesip ayırmak)",
    ("4000 Essential English Words::5.Book", "", "snap"): "koparmak (çat diye kırıvermek)",
    ("4000 Essential English Words::5.Book", "", "aisle"): "koridor (koltuk arası geçit)",
    ("4000 Essential English Words::3.Book", "", "corridor"): "koridor (odalara açılan geçit)",
    ("4000 Essential English Words::1.Book", "", "fear"): "korku (endişe duyma)",
    ("4000 Essential English Words::3.Book", "", "horror"): "korku (dehşete kapılma)",
    ("4000 Essential English Words::3.Book", "", "horrible"): "korkunç (iğrenç derecede kötü)",
    ("4000 Essential English Words::5.Book", "", "horrifying"): "korkunç (dehşete düşüren)",
    ("4000 Essential English Words::1.Book", "", "terrible"): "korkunç",
    ("4000 Essential English Words::6.Book", "", "intimidate"): "korkutmak (gözdağı vermek)",
    ("4000 Essential English Words::1.Book", "", "scare"): "korkutmak (ani ürkütmek)",
    ("4000 Essential English Words::5.Book", "", "conserve"): "korumak (tükenmemesi için)",
    ("4000 Essential English Words::2.Book", "", "preserve"): "korumak (zarar görmemesi için)",
    ("4000 Essential English Words::1.Book", "", "protect"): "korumak (incinmekten sakınmak)",
    ("4000 Essential English Words::5.Book", "", "retain"): "korumak (elinde tutmak)",
    ("4000 Essential English Words::3.Book", "", "jog"): "koşmak (yavaş tempoda)",
    ("4000 Essential English Words::6.Book", "", "sprint"): "koşmak (kısa mesafe hızlıca)",
    ("4000 Essential English Words::3.Book", "", "hut"): "kulübe (tek odalı, kerpiçten)",
    ("4000 Essential English Words::3.Book", "", "lodge"): "kulübe (dağdaki avcı evi)",
    ("4000 Essential English Words::2.Book", "", "cloth"): "kumaş (giysilik dokuma)",
    ("4000 Essential English Words::3.Book", "", "fabric"): "kumaş (mobilyaya da kullanılan)",
    ("4000 Essential English Words::5.Book", "", "establish"): "kurmak (oluşturup hayata geçirmek)",
    ("4000 Essential English Words::5.Book", "", "rescue"): "kurtarmak (tehlikeden çekip almak)",
    ("4000 Essential English Words::6.Book", "", "defect"): "kusur (eksik ya da bozuk parça)",
    ("4000 Essential English Words::6.Book", "", "flaw"): "kusur (işleyişi bozan hata)",
    ("4000 Essential English Words::6.Book", "", "deteriorate"): "kötüleşmek (giderek bozulmak)",
    ("4000 Essential English Words::5.Book", "", "worsen"): "kötüleşmek (birden ağırlaşmak)",
    ("4000 Essential English Words::6.Book", "", "globe"): "küre (dünya yuvarlağı)",
    ("4000 Essential English Words::Extra", "2_38", "sphere"): "küre (top gibi yuvarlak cisim)",
    ("4000 Essential English Words::2.Book", "", "sphere"): "küre (top gibi yuvarlak cisim)",
    ("4000 Essential English Words::5.Book", "", "paddle"): "kürek (kanoyu ilerleten)",
    ("4000 Essential English Words::6.Book", "", "shovel"): "kürek (uzun saplı, kar atan)",
    ("4000 Essential English Words::6.Book", "", "spade"): "kürek (bahçede toprak kazan)",
    ("4000 Essential English Words::4.Book", "", "scorn"): "küçümsemek (saygısızca davranmak)",
    ("4000 Essential English Words::6.Book", "", "underestimate"): "küçümsemek (olduğundan az sanmak)",
    ("4000 Essential English Words::3.Book", "", "brief"): "kısa (süresi az olan)",
    ("4000 Essential English Words::2.Book", "", "short"): "kısa (boyu az olan)",
    ("4000 Essential English Words::4.Book", "", "envious"): "kıskanç (başkasındakini isteyen)",
    ("4000 Essential English Words::3.Book", "", "jealous"): "kıskanç (kaybetmekten çekinen)",
    ("4000 Essential English Words::6.Book", "", "constrain"): "kısıtlamak (gelişmesini engellemek)",
    ("4000 Essential English Words::4.Book", "", "restrict"): "kısıtlamak (büyümesini sınırlamak)",
    ("4000 Essential English Words::3.Book", "", "famine"): "kıtlık (yiyecek bulunamaması)",
    ("4000 Essential English Words::5.Book", "", "shortage"): "kıtlık (yeterli miktar olmaması)",
    ("4000 Essential English Words::4.Book", "", "attire"): "kıyafet (özel gün giysisi)",
    ("4000 Essential English Words::6.Book", "", "outfit"): "kıyafet (bir arada giyilen takım)",
    ("4000 Essential English Words::3.Book", "", "harbor"): "liman (gemilerin sığındığı kıyı)",
    ("4000 Essential English Words::3.Book", "", "port"): "liman (yükleme boşaltma yeri)",
    ("4000 Essential English Words::3.Book", "", "devastate"): "mahvetmek (büyük yıkım bırakmak)",
    ("4000 Essential English Words::5.Book", "", "ruin"): "mahvetmek (bozup berbat etmek)",
    ("4000 Essential English Words::1.Book", "", "article"): "makale (gazetede çıkan yazı)",
    ("4000 Essential English Words::5.Book", "", "essay"): "makale (belli konuda yazı)",
    ("4000 Essential English Words::6.Book", "", "abbey"): "manastır (keşiş ve rahibe evi)",
    ("4000 Essential English Words::6.Book", "", "monastery"): "manastır (yalnız keşişlerin binası)",
    ("4000 Essential English Words::3.Book", "", "ladder"): "merdiven (taşınır, yaslanan)",
    ("4000 Essential English Words::1.Book", "", "stair"): "merdiven (tek basamak)",
    ("4000 Essential English Words::5.Book", "", "staircase"): "merdiven (basamak takımı)",
    ("4000 Essential English Words::2.Book", "", "occupation"): "meslek (geçim için yapılan iş)",
    ("4000 Essential English Words::2.Book", "", "profession"): "meslek (eğitim gerektiren uzmanlık)",
    ("4000 Essential English Words::3.Book", "", "germ"): "mikrop (hastalık yapan canlı)",
    ("4000 Essential English Words::4.Book", "", "microbe"): "mikrop (mikroskobik canlı)",
    ("4000 Essential English Words::1.Book", "", "amount"): "miktar (ne kadar olduğu)",
    ("4000 Essential English Words::2.Book", "", "quantity"): "miktar (belli ölçüde parça)",
    ("4000 Essential English Words::3.Book", "", "heritage"): "miras (toplumun dili ve dini)",
    ("4000 Essential English Words::4.Book", "", "legacy"): "miras (geçmişten kalan etki)",
    ("4000 Essential English Words::6.Book", "", "obsolete"): "modası geçmiş (daha iyisi çıkan)",
    ("4000 Essential English Words::4.Book", "", "outmoded"): "modası geçmiş (artık kullanılmayan)",
    ("4000 Essential English Words::5.Book", "", "immense"): "muazzam (boyutu çok büyük)",
    ("4000 Essential English Words::3.Book", "", "tremendous"): "muazzam (büyük ve harika)",
    ("4000 Essential English Words::4.Book", "", "fabulous"): "muhteşem (son derece iyi)",
    ("4000 Essential English Words::4.Book", "", "gorgeous"): "muhteşem (göz alıcı, çekici)",
    ("4000 Essential English Words::3.Book", "", "magnificent"): "muhteşem (görkemli ve büyük)",
    ("4000 Essential English Words::6.Book", "", "spectacular"): "muhteşem (etkileyici gösteri)",
    ("4000 Essential English Words::6.Book", "", "splendid"): "muhteşem (çok iyi, şahane)",
    ("4000 Essential English Words::2.Book", "", "interfere"): "müdahale etmek (sorun çıkarıp engellemek)",
    ("4000 Essential English Words::5.Book", "", "intervene"): "müdahale etmek (araya girip çözmek)",
    ("4000 Essential English Words::1.Book", "", "excellent"): "mükemmel (çok iyi, üstün)",
    ("4000 Essential English Words::5.Book", "", "perfect"): "mükemmel (hatasız, kusursuz)",
    ("4000 Essential English Words::3.Book", "", "humble"): "mütevazı (üstünlük taslamayan)",
    ("4000 Essential English Words::3.Book", "", "modest"): "mütevazı (kendini önemsemeyen)",
    ("4000 Essential English Words::5.Book", "", "humid"): "nemli (havada su buharı)",
    ("4000 Essential English Words::6.Book", "", "moist"): "nemli (hafifçe ıslak)",
    ("4000 Essential English Words::3.Book", "", "cheerful"): "neşeli (cana yakın, sevinçli)",
    ("4000 Essential English Words::3.Book", "", "merry"): "neşeli (şen, keyifli)",
    ("4000 Essential English Words::5.Book", "", "eventual"): "nihai (olayların sonunda gelen)",
    ("4000 Essential English Words::1.Book", "", "final"): "nihai (en son bölüm)",
    ("4000 Essential English Words::6.Book", "", "ultimate"): "nihai (varılacak son amaç)",
    ("4000 Essential English Words::2.Book", "", "intent"): "niyet (yapılacak işin planı)",
    ("4000 Essential English Words::2.Book", "", "intention"): "niyet (yapmayı düşündüğü şey)",
    ("4000 Essential English Words::4.Book", "", "seizure"): "nöbet (kasılmalı hastalık krizi)",
    ("4000 Essential English Words::6.Book", "", "vigil"): "nöbet (gece uyanık bekleme)",
    ("4000 Essential English Words::1.Book", "", "event"): "olay (önemli gelişme)",
    ("4000 Essential English Words::3.Book", "", "incident"): "olay (hoş olmayan vaka)",
    ("4000 Essential English Words::4.Book", "", "exceptional"): "olağanüstü (üstün, seçkin)",
    ("4000 Essential English Words::6.Book", "", "phenomenal"): "olağanüstü (inanılmaz büyük)",
    ("4000 Essential English Words::6.Book", "", "adverse"): "olumsuz (zararlı etki)",
    ("4000 Essential English Words::5.Book", "", "negative"): "olumsuz (üzücü, hoş olmayan)",
    ("4000 Essential English Words::4.Book", "", "mend"): "onarmak (yırtığı dikerek)",
    ("4000 Essential English Words::2.Book", "", "repair"): "onarmak (tamir edip düzelterek)",
    ("4000 Essential English Words::6.Book", "", "proportion"): "oran (parçanın bütüne payı)",
    ("4000 Essential English Words::5.Book", "", "rate"): "oran (gerçekleşme hızı)",
    ("4000 Essential English Words::4.Book", "", "ratio"): "oran (iki sayının karşılaştırması)",
    ("4000 Essential English Words::2.Book", "", "army"): "ordu (savaşan asker topluluğu)",
    ("4000 Essential English Words::2.Book", "", "military"): "ordu",
    ("4000 Essential English Words::5.Book", "", "mid"): "orta (sürecin ortasında)",
    ("4000 Essential English Words::5.Book", "", "middle"): "orta (tam merkezdeki yer)",
    ("4000 Essential English Words::6.Book", "", "abolish"): "ortadan kaldırmak (kanunu, sistemi)",
    ("4000 Essential English Words::4.Book", "", "eliminate"): "ortadan kaldırmak (istenmeyeni tümüyle)",
    ("4000 Essential English Words::4.Book", "", "joint"): "ortak (iki kişinin paylaştığı)",
    ("4000 Essential English Words::4.Book", "", "partner"): "ortak (birlikte çalışan kişi)",
    ("4000 Essential English Words::3.Book", "", "arise"): "ortaya çıkmak (sorun olarak belirmek)",
    ("4000 Essential English Words::2.Book", "", "emerge"): "ortaya çıkmak (içinden dışarı çıkmak)",
    ("4000 Essential English Words::1.Book", "", "bright"): "parlak (çok ışık veren)",
    ("4000 Essential English Words::3.Book", "", "brilliant"): "parlak (zeki, akıllı kişi)",
    ("4000 Essential English Words::6.Book", "", "gleam"): "parlamak (hafifçe pırıldamak)",
    ("4000 Essential English Words::2.Book", "", "shine"): "parlamak (güçlü ışık vermek)",
    ("4000 Essential English Words::5.Book", "", "shatter"): "parçalamak (minik parçalara)",
    ("4000 Essential English Words::5.Book", "", "smash"): "parçalamak (vurup kırıvererek)",
    ("4000 Essential English Words::3.Book", "", "boom"): "patlamak (gümbürdeyen ses çıkarmak)",
    ("4000 Essential English Words::3.Book", "", "burst"): "patlamak (yarılıp açılmak)",
    ("4000 Essential English Words::3.Book", "", "erupt"): "patlamak (yanardağın püskürmesi)",
    ("4000 Essential English Words::3.Book", "", "explode"): "patlamak (parçalara ayrılmak)",
    ("4000 Essential English Words::4.Book", "", "personnel"): "personel (işyeri çalışanları)",
    ("4000 Essential English Words::1.Book", "", "staff"): "personel (birlikte çalışan grup)",
    ("4000 Essential English Words::4.Book", "", "rack"): "raf (katlı eşya standı)",
    ("4000 Essential English Words::2.Book", "", "shelf"): "raf (duvardaki tahta)",
    ("4000 Essential English Words::4.Book", "", "comfortable"): "rahat (konforlu, huzurlu)",
    ("4000 Essential English Words::5.Book", "", "cozy"): "rahat (sıcak, keyifli)",
    ("4000 Essential English Words::3.Book", "", "opponent"): "rakip (maçtaki karşı taraf)",
    ("4000 Essential English Words::3.Book", "", "rival"): "rakip (aynı şeyi isteyen)",
    ("4000 Essential English Words::5.Book", "", "decline"): "reddetmek (daveti çevirmek)",
    ("4000 Essential English Words::1.Book", "", "refuse"): "reddetmek (hayır demek)",
    ("4000 Essential English Words::4.Book", "", "reject"): "reddetmek (kabul etmemek)",
    ("4000 Essential English Words::2.Book", "", "formal"): "resmi (ciddi, kurallı)",
    ("4000 Essential English Words::3.Book", "", "official"): "resmi (yetkili onaylı)",
    ("4000 Essential English Words::4.Book", "", "epidemic"): "salgın (hızla yayılan hastalık)",
    ("4000 Essential English Words::4.Book", "", "outbreak"): "salgın (ani başlayan hastalık)",
    ("4000 Essential English Words::4.Book", "", "intimate"): "samimi (çok yakın ilişki)",
    ("4000 Essential English Words::2.Book", "", "sincere"): "samimi (içten, dürüst)",
    ("4000 Essential English Words::6.Book", "", "celsius"): "santigrat (sıcaklık ölçeği)",
    ("4000 Essential English Words::6.Book", "", "centigrade"): "santigrat (Celsius ile aynı)",
    ("4000 Essential English Words::5.Book", "", "esteemed"): "saygın (çok saygı duyulan)",
    ("4000 Essential English Words::4.Book", "", "reputable"): "saygın (itibarı iyi olan)",
    ("4000 Essential English Words::6.Book", "", "intact"): "sağlam (hasarsız, eksiksiz)",
    ("4000 Essential English Words::6.Book", "", "rugged"): "sağlam (engebeli, sarp arazi)",
    ("4000 Essential English Words::5.Book", "", "cause"): "sebep (sonuca yol açan)",
    ("4000 Essential English Words::4.Book", "", "motive"): "sebep (kişiyi iten gerekçe)",
    ("4000 Essential English Words::4.Book", "", "reason"): "sebep (durumu açıklayan neden)",
    ("4000 Essential English Words::5.Book", "", "harsh"): "sert (acımasız koşullar)",
    ("4000 Essential English Words::5.Book", "", "stern"): "sert (ciddi, otoriter kişi)",
    ("4000 Essential English Words::2.Book", "", "tough"): "sert (zorlayıcı, çetin)",
    ("4000 Essential English Words::2.Book", "", "quiet"): "sessiz (az ses çıkaran)",
    ("4000 Essential English Words::2.Book", "", "silent"): "sessiz (hiç ses çıkarmayan)",
    ("4000 Essential English Words::5.Book", "", "fond"): "sevmek (düşkün olmak)",
    ("4000 Essential English Words::1.Book", "", "love"): "sevmek (çok sevip bağlanmak)",
    ("4000 Essential English Words::3.Book", "", "audience"): "seyirci (izleyen topluluk)",
    ("4000 Essential English Words::6.Book", "", "spectator"): "seyirci (maçı izleyen kişi)",
    ("4000 Essential English Words::6.Book", "", "delete"): "silmek (yazıyı kaldırmak)",
    ("4000 Essential English Words::3.Book", "", "wipe"): "silmek (bezle temizlemek)",
    ("4000 Essential English Words::2.Book", "", "fog"): "sis (yoğun, kalın örtü)",
    ("4000 Essential English Words::3.Book", "", "mist"): "sis (ince su damlacıkları)",
    ("4000 Essential English Words::3.Book", "", "alley"): "sokak (binalar arası dar)",
    ("4000 Essential English Words::1.Book", "", "street"): "sokak (şehirdeki cadde)",
    ("4000 Essential English Words::1.Book", "", "eventually"): "sonunda (eninde sonunda)",
    ("4000 Essential English Words::4.Book", "", "finally"): "sonunda (son adımda, nihayet)",
    ("4000 Essential English Words::1.Book", "", "conclusion"): "sonuç (final bölüm)",
    ("4000 Essential English Words::3.Book", "", "outcome"): "sonuç (olayın nihai çıktısı)",
    ("4000 Essential English Words::3.Book", "", "result"): "sonuç (bir şeyden doğan)",
    ("4000 Essential English Words::1.Book", "", "ask"): "sormak (cevap bekleyerek)",
    ("4000 Essential English Words::3.Book", "", "inquire"): "sormak (bilgi almak için)",
    ("4000 Essential English Words::4.Book", "", "accountable"): "sorumlu (hesap veren)",
    ("4000 Essential English Words::2.Book", "", "responsible"): "sorumlu (bir işi yöneten)",
    ("4000 Essential English Words::5.Book", "", "peel"): "soymak (meyve kabuğunu)",
    ("4000 Essential English Words::2.Book", "", "rob"): "soymak (zorla mal almak)",
    ("4000 Essential English Words::5.Book", "", "crime"): "suç (kanunla cezalandırılan)",
    ("4000 Essential English Words::3.Book", "", "offense"): "suç (kanunu çiğneyen davranış)",
    ("4000 Essential English Words::5.Book", "", "offense"): "suç (kanunu çiğneyen davranış)",
    ("4000 Essential English Words::2.Book", "", "accuse"): "suçlamak (yaptığını söylemek)",
    ("4000 Essential English Words::2.Book", "", "blame"): "suçlamak (sorumlusu saymak)",
    ("4000 Essential English Words::6.Book", "", "culprit"): "suçlu (işi yapan kişi)",
    ("4000 Essential English Words::2.Book", "", "guilty"): "suçlu (vicdanen rahatsız)",
    ("4000 Essential English Words::5.Book", "", "constant"): "sürekli (her zaman olan)",
    ("4000 Essential English Words::5.Book", "", "constantly"): "sürekli (durmadan yapan)",
    ("4000 Essential English Words::3.Book", "", "crawl"): "sürünmek (dizler üstünde)",
    ("4000 Essential English Words::3.Book", "", "creep"): "sürünmek (sessizce, yavaşça)",
    ("4000 Essential English Words::5.Book", "", "distress"): "sıkıntı (üzüntü, kaygı)",
    ("4000 Essential English Words::4.Book", "", "nuisance"): "sıkıntı (can sıkıcı kişi/şey)",
    ("4000 Essential English Words::1.Book", "", "trouble"): "sıkıntı (yaşanan problem)",
    ("4000 Essential English Words::2.Book", "", "border"): "sınır (bölgenin kenarı)",
    ("4000 Essential English Words::5.Book", "", "boundary"): "sınır (araziyi ayıran çizgi)",
    ("4000 Essential English Words::6.Book", "", "frontier"): "sınır (iki ülke arası)",
    ("4000 Essential English Words::6.Book", "", "commonplace"): "sıradan (her zamanki)",
    ("4000 Essential English Words::2.Book", "", "ordinary"): "sıradan (özel yanı olmayan)",
    ("4000 Essential English Words::3.Book", "", "ridge"): "sırt (dağdaki uzun çıkıntı)",
    ("4000 Essential English Words::3.Book", "", "bounce"): "sıçramak (yere çarpıp yükselmek)",
    ("4000 Essential English Words::3.Book", "", "leap"): "sıçramak (uzun mesafe atlamak)",
    ("4000 Essential English Words::3.Book", "", "splash"): "sıçramak (sıvıyı etrafa dağıtmak)",
    ("4000 Essential English Words::3.Book", "", "refuge"): "sığınak (güvenli yer)",
    ("4000 Essential English Words::6.Book", "", "sanctuary"): "sığınak (tehlikedekine korunak)",
    ("4000 Essential English Words::Extra", "3_59", "cereal"): "tahıl (kahvaltılık gevrek)",
    ("4000 Essential English Words::3.Book", "", "cereal"): "tahıl (kahvaltılık gevrek)",
    ("4000 Essential English Words::2.Book", "", "grain"): "tahıl (buğday, pirinç ürünü)",
    ("4000 Essential English Words::6.Book", "", "emulate"): "taklit etmek (örnek almak)",
    ("4000 Essential English Words::3.Book", "", "imitate"): "taklit etmek (aynı davranmak)",
    ("4000 Essential English Words::4.Book", "", "mimic"): "taklit etmek (sesini, hareketini)",
    ("4000 Essential English Words::5.Book", "", "altogether"): "tamamen (büsbütün)",
    ("4000 Essential English Words::1.Book", "", "completely"): "tamamen (her yönüyle)",
    ("4000 Essential English Words::5.Book", "", "define"): "tanımlamak (ne olduğunu açıklamak)",
    ("4000 Essential English Words::2.Book", "", "identify"): "tanımlamak (ne olduğunu saptamak)",
    ("4000 Essential English Words::2.Book", "", "debate"): "tartışmak (fikir savunmak)",
    ("4000 Essential English Words::2.Book", "", "discuss"): "tartışmak (biriyle konuşmak)",
    ("4000 Essential English Words::3.Book", "", "draft"): "taslak (yazının ilk hâli)",
    ("4000 Essential English Words::1.Book", "", "outline"): "taslak (yazının planı)",
    ("4000 Essential English Words::6.Book", "", "depict"): "tasvir etmek (resimle göstermek)",
    ("4000 Essential English Words::3.Book", "", "portray"): "tasvir etmek (anlatıp göstermek)",
    ("4000 Essential English Words::4.Book", "", "danger"): "tehlike (zarar görme olasılığı)",
    ("4000 Essential English Words::4.Book", "", "hazard"): "tehlike (sağlığa zararlı etken)",
    ("4000 Essential English Words::4.Book", "", "technical"): "teknik (ustalık gerektiren)",
    ("4000 Essential English Words::4.Book", "", "technique"): "teknik (iş yapma yolu)",
    ("4000 Essential English Words::5.Book", "", "perspire"): "terlemek (kibar söyleyiş)",
    ("4000 Essential English Words::3.Book", "", "sweat"): "terlemek (vücuttan su kaybı)",
    ("4000 Essential English Words::4.Book", "", "encouragement"): "teşvik (moral veren)",
    ("4000 Essential English Words::4.Book", "", "incentive"): "teşvik (isteklendiren ödül)",
    ("4000 Essential English Words::6.Book", "", "spur"): "teşvik etmek (harekete geçirmek)",
    ("4000 Essential English Words::6.Book", "", "stimulate"): "teşvik etmek (faaliyeti artırmak)",
    ("4000 Essential English Words::5.Book", "", "sum"): "toplam (parasal tutar)",
    ("4000 Essential English Words::2.Book", "", "total"): "toplam (hepsi sayılmış)",
    ("4000 Essential English Words::6.Book", "", "assemble"): "toplamak (bir araya gelmek)",
    ("4000 Essential English Words::3.Book", "", "gather"): "toplamak (grup oluşturmak)",
    ("4000 Essential English Words::4.Book", "", "dust"): "toz (toprak zerreleri)",
    ("4000 Essential English Words::4.Book", "", "powder"): "toz (öğütülmüş madde)",
    ("4000 Essential English Words::6.Book", "", "bizarre"): "tuhaf (akıl almaz)",
    ("4000 Essential English Words::2.Book", "", "odd"): "tuhaf (alışılmadık)",
    ("4000 Essential English Words::5.Book", "", "weird"): "tuhaf (ürkütücü derecede)",
    ("4000 Essential English Words::4.Book", "", "coherent"): "tutarlı (parçaları uyumlu)",
    ("4000 Essential English Words::5.Book", "", "consistent"): "tutarlı (davranışı hep aynı)",
    ("4000 Essential English Words::4.Book", "", "transport"): "ulaşım (taşıma sistemi)",
    ("4000 Essential English Words::5.Book", "", "transportation"): "ulaşım (taşıt araçları)",
    ("4000 Essential English Words::1.Book", "", "master"): "usta (işin ehli)",
    ("4000 Essential English Words::3.Book", "", "proficient"): "usta (becerikli)",
    ("4000 Essential English Words::5.Book", "", "arouse"): "uyandırmak (ilgi ve merak)",
    ("4000 Essential English Words::6.Book", "", "evoke"): "uyandırmak (anı ve duygu)",
    ("4000 Essential English Words::5.Book", "", "admonish"): "uyarmak (kınayarak)",
    ("4000 Essential English Words::3.Book", "", "alert"): "uyarmak (haber vererek)",
    ("4000 Essential English Words::5.Book", "", "warn"): "uyarmak (tehlikeye karşı)",
    ("4000 Essential English Words::1.Book", "", "appropriate"): "uygun (yerinde olan)",
    ("4000 Essential English Words::6.Book", "", "convenient"): "uygun (kolaylık sağlayan)",
    ("4000 Essential English Words::6.Book", "", "eligible"): "uygun (şartları tutan)",
    ("4000 Essential English Words::1.Book", "", "far"): "uzak (mesafe olarak)",
    ("4000 Essential English Words::3.Book", "", "remote"): "uzak (ıssız köşede)",
    ("4000 Essential English Words::5.Book", "", "aircraft"): "uçak (hava aracı)",
    ("4000 Essential English Words::3.Book", "", "plane"): "uçak (kanatlı, motorlu)",
    ("4000 Essential English Words::1.Book", "", "assume"): "varsaymak (kanıt olmadan)",
    ("4000 Essential English Words::3.Book", "", "presume"): "varsaymak (kesin bilmeden)",
    ("4000 Essential English Words::5.Book", "", "efficient"): "verimli (enerji israf etmeyen)",
    ("4000 Essential English Words::2.Book", "", "fertile"): "verimli (ürün veren toprak)",
    ("4000 Essential English Words::2.Book", "", "capture"): "yakalamak (ele geçirip tutmak)",
    ("4000 Essential English Words::1.Book", "", "catch"): "yakalamak (kapıp almak)",
    ("4000 Essential English Words::1.Book", "", "alone"): "yalnız (tek başına)",
    ("4000 Essential English Words::2.Book", "", "solitary"): "yalnız (tek olan)",
    ("4000 Essential English Words::4.Book", "", "loneliness"): "yalnızlık (üzüntü veren)",
    ("4000 Essential English Words::5.Book", "", "solitude"): "yalnızlık (tamamen tek başına)",
    ("4000 Essential English Words::5.Book", "", "alongside"): "yanında (yan yana)",
    ("4000 Essential English Words::1.Book", "", "beside"): "yanında (hemen bitişiğinde)",
    ("4000 Essential English Words::5.Book", "", "injure"): "yaralamak (bedene zarar)",
    ("4000 Essential English Words::4.Book", "", "wound"): "yaralamak (deriyi keserek)",
    ("4000 Essential English Words::5.Book", "", "assist"): "yardım etmek (destek olmak)",
    ("4000 Essential English Words::1.Book", "", "help"): "yardım etmek (kolaylaştırmak)",
    ("4000 Essential English Words::3.Book", "", "ban"): "yasaklamak (resmî olarak)",
    ("4000 Essential English Words::5.Book", "", "forbid"): "yasaklamak (emir vererek)",
    ("4000 Essential English Words::4.Book", "", "prohibit"): "yasaklamak (izin vermeyerek)",
    ("4000 Essential English Words::3.Book", "", "cub"): "yavru (vahşi hayvan)",
    ("4000 Essential English Words::5.Book", "", "offspring"): "yavru (kişinin çocukları)",
    ("4000 Essential English Words::2.Book", "", "pup"): "yavru (köpek yavrusu)",
    ("4000 Essential English Words::5.Book", "", "arc"): "yay (eğri biçim)",
    ("4000 Essential English Words::2.Book", "", "bow"): "yay (ok atan silah)",
    ("4000 Essential English Words::1.Book", "", "common"): "yaygın (sık görülen)",
    ("4000 Essential English Words::4.Book", "", "prevalent"): "yaygın (ülkeden ülkeye)",
    ("4000 Essential English Words::4.Book", "", "widespread"): "yaygın (dünyaya yayılmış)",
    ("4000 Essential English Words::6.Book", "", "disseminate"): "yaymak (bilgi ve haber)",
    ("4000 Essential English Words::4.Book", "", "emit"): "yaymak (gaz ve ısı)",
    ("4000 Essential English Words::2.Book", "", "radiate"): "yaymak (enerji ve ısı)",
    ("4000 Essential English Words::1.Book", "", "spread"): "yaymak (yüzeye sürmek)",
    ("4000 Essential English Words::3.Book", "", "broadcast"): "yayın (televizyon programı)",
    ("4000 Essential English Words::3.Book", "", "publication"): "yayın (basılı eser)",
    ("4000 Essential English Words::2.Book", "", "swear"): "yemin etmek (kutsal kitap üzerine)",
    ("4000 Essential English Words::4.Book", "", "vow"): "yemin etmek (törenle)",
    ("4000 Essential English Words::6.Book", "", "renovate"): "yenilemek (binayı onarmak)",
    ("4000 Essential English Words::4.Book", "", "replenish"): "yenilemek (eksikleri doldurmak)",
    ("4000 Essential English Words::6.Book", "", "innovation"): "yenilik (yeni buluş)",
    ("4000 Essential English Words::4.Book", "", "novelty"): "yenilik (alışılmadık şey)",
    ("4000 Essential English Words::1.Book", "", "beat"): "yenmek (yarışta geçmek)",
    ("4000 Essential English Words::3.Book", "", "defeat"): "yenmek (maçta alt etmek)",
    ("4000 Essential English Words::6.Book", "", "indigenous"): "yerli (o bölgede doğal)",
    ("4000 Essential English Words::4.Book", "", "native"): "yerli (doğduğu ülke)",
    ("4000 Essential English Words::2.Book", "", "ability"): "yetenek (yapabilme gücü)",
    ("4000 Essential English Words::3.Book", "", "aptitude"): "yetenek (doğal yatkınlık)",
    ("4000 Essential English Words::2.Book", "", "talent"): "yetenek (üstün beceri)",
    ("4000 Essential English Words::2.Book", "", "adequate"): "yeterli (ihtiyaca yeten)",
    ("4000 Essential English Words::2.Book", "", "sufficient"): "yeterli (miktar ve nitelik)",
    ("4000 Essential English Words::1.Book", "", "journey"): "yolculuk (uzun gezi)",
    ("4000 Essential English Words::3.Book", "", "voyage"): "yolculuk (gemi veya uçakla)",
    ("4000 Essential English Words::5.Book", "", "dense"): "yoğun (sık ve kalabalık)",
    ("4000 Essential English Words::2.Book", "", "intense"): "yoğun (çok güçlü)",
    ("4000 Essential English Words::4.Book", "", "administrator"): "yönetici (kurum müdürü)",
    ("4000 Essential English Words::6.Book", "", "executive"): "yönetici (zirvedeki müdür)",
    ("4000 Essential English Words::4.Book", "", "administration"): "yönetim (kurul ve ekip)",
    ("4000 Essential English Words::4.Book", "", "management"): "yönetim (idare süreci)",
    ("4000 Essential English Words::4.Book", "", "administer"): "yönetmek (organize etmek)",
    ("4000 Essential English Words::1.Book", "", "manage"): "yönetmek (başında olmak)",
    ("4000 Essential English Words::4.Book", "", "almighty"): "yüce (Tanrı adı)",
    ("4000 Essential English Words::3.Book", "", "supreme"): "yüce (en üstün)",
    ("4000 Essential English Words::3.Book", "", "march"): "yürümek (düzenli adımlarla)",
    ("4000 Essential English Words::2.Book", "", "walk"): "yürümek (koşmadan)",
    ("4000 Essential English Words::6.Book", "", "confront"): "yüzleşmek (yüz yüze gelip)",
    ("4000 Essential English Words::4.Book", "", "face"): "yüzleşmek (doğrudan)",
    ("4000 Essential English Words::2.Book", "", "float"): "yüzmek (batmadan su üstünde)",
    ("4000 Essential English Words::1.Book", "", "swim"): "yüzmek (suda ilerlemek)",
    ("4000 Essential English Words::5.Book", "", "rip"): "yırtmak (çekip ayırmak)",
    ("4000 Essential English Words::1.Book", "", "tear"): "yırtmak (parça koparmak)",
    ("4000 Essential English Words::6.Book", "", "chunk"): "yığın (iri parça)",
    ("4000 Essential English Words::6.Book", "", "heap"): "yığın (gelişigüzel küme)",
    ("4000 Essential English Words::3.Book", "", "pile"): "yığın (üst üste yığılmış)",
    ("4000 Essential English Words::3.Book", "", "stack"): "yığın (düzenli istif)",
    ("4000 Essential English Words::3.Book", "", "triumph"): "zafer (kazanma coşkusu)",
    ("4000 Essential English Words::4.Book", "", "victory"): "zafer (kazanılan mücadele)",
    ("4000 Essential English Words::2.Book", "", "damage"): "zarar vermek (kırarak)",
    ("4000 Essential English Words::1.Book", "", "harm"): "zarar vermek (canı yakan)",
    ("4000 Essential English Words::3.Book", "", "elegant"): "zarif (şık ve gösterişli)",
    ("4000 Essential English Words::6.Book", "", "gracious"): "zarif (kibar ve yardımsever)",
    ("4000 Essential English Words::5.Book", "", "feeble"): "zayıf (gücü yetmeyen)",
    ("4000 Essential English Words::4.Book", "", "weak"): "zayıf (hastalıktan güçsüz)",
    ("4000 Essential English Words::2.Book", "", "peak"): "zirve (dağın tepesi)",
    ("4000 Essential English Words::3.Book", "", "summit"): "zirve (en yüksek nokta)",
    ("4000 Essential English Words::4.Book", "", "compel"): "zorlamak (mecbur bırakmak)",
    ("4000 Essential English Words::3.Book", "", "strain"): "zorlamak (güç harcayarak)",
    ("4000 Essential English Words::4.Book", "", "imperative"): "zorunlu (çok gerekli)",
    ("4000 Essential English Words::4.Book", "", "mandatory"): "zorunlu (kanun gereği)",
    ("4000 Essential English Words::1.Book", "", "effort"): "çaba (emek harcama)",
    ("4000 Essential English Words::6.Book", "", "endeavor"): "çaba (yeni girişim)",
    ("4000 Essential English Words::3.Book", "", "diligent"): "çalışkan (özenli ve dikkatli)",
    ("4000 Essential English Words::4.Book", "", "industrious"): "çalışkan (durmadan çalışan)",
    ("4000 Essential English Words::5.Book", "", "distort"): "çarpıtmak (gerçeği saptırmak)",
    ("4000 Essential English Words::6.Book", "", "warp"): "çarpıtmak (ısıyla eğrilmek)",
    ("4000 Essential English Words::5.Book", "", "contemporary"): "çağdaş (günümüzle ilgili)",
    ("4000 Essential English Words::3.Book", "", "modern"): "çağdaş (yeni moda)",
    ("4000 Essential English Words::3.Book", "", "core"): "çekirdek (ana merkez)",
    ("4000 Essential English Words::6.Book", "", "nucleus"): "çekirdek (atomun merkezi)",
    ("4000 Essential English Words::2.Book", "", "frame"): "çerçeve (resim kenarlığı)",
    ("4000 Essential English Words::4.Book", "", "framework"): "çerçeve (kural ve fikirler)",
    ("4000 Essential English Words::1.Book", "", "environment"): "çevre (yaşanılan ortam)",
    ("4000 Essential English Words::6.Book", "", "periphery"): "çevre (kenar bölge)",
    ("4000 Essential English Words::5.Book", "", "enclose"): "çevrelemek (içine almak)",
    ("4000 Essential English Words::2.Book", "", "surround"): "çevrelemek (her yandan sarmak)",
    ("4000 Essential English Words::5.Book", "", "diverse"): "çeşitli (farklı türlerden)",
    ("4000 Essential English Words::1.Book", "", "various"): "çeşitli (birçok çeşitte)",
    ("4000 Essential English Words::4.Book", "", "diversity"): "çeşitlilik (farklılık zenginliği)",
    ("4000 Essential English Words::5.Book", "", "variety"): "çeşitlilik (birçok tür)",
    ("4000 Essential English Words::4.Book", "", "couple"): "çift (iki tane)",
    ("4000 Essential English Words::2.Book", "", "double"): "çift (iki kat fazla)",
    ("4000 Essential English Words::3.Book", "", "lawn"): "çim (bahçe çimeni)",
    ("4000 Essential English Words::6.Book", "", "turf"): "çim (toprağıyla birlikte)",
    ("4000 Essential English Words::1.Book", "", "garbage"): "çöp (bozuk yiyecek)",
    ("4000 Essential English Words::4.Book", "", "rubbish"): "çöp (süprüntü)",
    ("4000 Essential English Words::1.Book", "", "trash"): "çöp (değersiz şeyler)",
    ("4000 Essential English Words::5.Book", "", "resolve"): "çözmek (anlaşmazlığı gidermek)",
    ("4000 Essential English Words::1.Book", "", "solve"): "çözmek (cevabı bulmak)",
    ("4000 Essential English Words::4.Book", "", "disprove"): "çürütmek (yanlışlığını göstermek)",
    ("4000 Essential English Words::6.Book", "", "refute"): "çürütmek (aksini kanıtlamak)",
    ("4000 Essential English Words::4.Book", "", "extract"): "çıkarmak (çekip almak)",
    ("4000 Essential English Words::2.Book", "", "subtract"): "çıkarmak (matematikte eksiltmek)",
    ("4000 Essential English Words::4.Book", "", "importance"): "önem (değerli olma)",
    ("4000 Essential English Words::4.Book", "", "significance"): "önem (anlam taşıma)",
    ("4000 Essential English Words::6.Book", "", "bias"): "önyargı (bir yanı kayırma)",
    ("4000 Essential English Words::3.Book", "", "prejudice"): "önyargı (gruba karşı haksız)",
    ("4000 Essential English Words::1.Book", "", "example"): "örnek (tipik durum)",
    ("4000 Essential English Words::1.Book", "", "instance"): "örnek (tek bir olay)",
    ("4000 Essential English Words::3.Book", "", "boast"): "övünmek (kendini yücelterek)",
    ("4000 Essential English Words::5.Book", "", "brag"): "övünmek (başarısını anlatarak)",
    ("4000 Essential English Words::1.Book", "", "attribute"): "özellik (kişiye has nitelik)",
    ("4000 Essential English Words::1.Book", "", "feature"): "özellik (üründeki işlev)",
    ("4000 Essential English Words::3.Book", "", "trait"): "özellik (kişilik parçası)",
    ("4000 Essential English Words::2.Book", "", "overcome"): "üstesinden gelmek (sorunu çözerek)",
    ("4000 Essential English Words::6.Book", "", "tackle"): "üstesinden gelmek (kararlılıkla)",
    ("4000 Essential English Words::2.Book", "", "insist"): "ısrar etmek (söyleyip durmak)",
    ("4000 Essential English Words::3.Book", "", "persist"): "ısrar etmek (yılmadan sürdürmek)",
    ("4000 Essential English Words::1.Book", "", "amaze"): "şaşırtmak (hayrete düşürmek)",
    ("4000 Essential English Words::2.Book", "", "surprise"): "şaşırtmak (beklenmedik şeyle)",
    ("4000 Essential English Words::2.Book", "", "strip"): "şerit (uzun ve dar parça)",
    ("4000 Essential English Words::3.Book", "", "stripe"): "şerit (kalın çizgi)",
    ("4000 Essential English Words::3.Book", "", "fierce"): "şiddetli (vahşi ve öfkeli)",
    ("4000 Essential English Words::5.Book", "", "vehement"): "şiddetli (öfkeyle dolu)",
    ("4000 Essential English Words::2.Book", "", "fame"): "şöhret (halkça tanınma)",
    ("4000 Essential English Words::6.Book", "", "renown"): "şöhret (iyilikle anılma)",
    ("4000 Essential English Words::1.Book", "", "doubt"): "şüphe (emin olamama)",
    ("4000 Essential English Words::6.Book", "", "suspicion"): "şüphe (suç işlendiğine dair)",
    ("4000 Essential English Words::6.Book", "", "dubious"): "şüpheli (inandırıcı olmayan)",
    ("4000 Essential English Words::3.Book", "", "suspicious"): "şüpheli (kuşkuyla bakan)",
    ("4000 Essential English Words::4.Book", "", "ensure"): "sağlamak / garanti etmek",
    # 2026-09-16: grant = talebi onaylayarak verme (allow = bir seye izin verme).
    ("4000 Essential English Words::2.Book", "", "grant"): "vermek (talebi onaylayarak)",
    # recognition kitapta "ovgu/takdir alma" anlaminda; makine "tanima" yazmisti.
    ("4000 Essential English Words::2.Book", "", "recognition"): "takdir / övgü",
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
    deck_io.ensure_dir(path.parent)
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
    deck_io.ensure_dir(path.parent)
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
