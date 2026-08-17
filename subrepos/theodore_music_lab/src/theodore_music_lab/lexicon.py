"""Core song vocabulary in 26 languages + English usage examples.

This is the offline floor of the translation stack: every lyric line can always
show real target-language words for its content words, even with no network and
no curated full-line translation. Entries are term-major (one row per English
term) so a new language is a single key per row.

Non-Latin scripts carry a parenthesised romanization to keep the lab usable for
learners who cannot yet read the script.
"""

from __future__ import annotations

import re

# Languages whose rows are authored from reference material but have not been
# through a native-speaker pass yet; surfaced in the UI as a review badge.
NEEDS_NATIVE_REVIEW: frozenset[str] = frozenset(
    {"ar", "bn", "fa", "he", "hi", "km", "sw", "th", "ur"}
)

LEXICON: dict[str, dict[str, str]] = {
    "hello": {"es": "hola", "fr": "bonjour", "de": "hallo", "it": "ciao", "pt": "olá", "nl": "hallo", "pl": "cześć", "ru": "привет (privet)", "uk": "привіт (pryvit)", "tr": "merhaba", "ar": "مرحبا (marhaban)", "he": "שלום (shalom)", "hi": "नमस्ते (namaste)", "bn": "নমস্কার (nomoskar)", "ur": "سلام (salaam)", "fa": "سلام (salâm)", "zh": "你好 (nǐ hǎo)", "ja": "こんにちは (konnichiwa)", "ko": "안녕하세요 (annyeonghaseyo)", "vi": "xin chào", "th": "สวัสดี (sawatdee)", "id": "halo", "sw": "jambo", "el": "γεια σου (yia sou)", "cs": "ahoj", "km": "សួស្តី (suostei)"},
    "friend": {"es": "amigo", "fr": "ami", "de": "Freund", "it": "amico", "pt": "amigo", "nl": "vriend", "pl": "przyjaciel", "ru": "друг (drug)", "uk": "друг (druh)", "tr": "arkadaş", "ar": "صديق (sadiq)", "he": "חבר (chaver)", "hi": "दोस्त (dost)", "bn": "বন্ধু (bondhu)", "ur": "دوست (dost)", "fa": "دوست (dust)", "zh": "朋友 (péngyou)", "ja": "友達 (tomodachi)", "ko": "친구 (chingu)", "vi": "bạn", "th": "เพื่อน (phuean)", "id": "teman", "sw": "rafiki", "el": "φίλος (filos)", "cs": "přítel", "km": "មិត្ត (mit)"},
    "work": {"es": "trabajo", "fr": "travail", "de": "Arbeit", "it": "lavoro", "pt": "trabalho", "nl": "werk", "pl": "praca", "ru": "работа (rabota)", "uk": "робота (robota)", "tr": "iş", "ar": "عمل (amal)", "he": "עבודה (avoda)", "hi": "काम (kaam)", "bn": "কাজ (kaj)", "ur": "کام (kaam)", "fa": "کار (kâr)", "zh": "工作 (gōngzuò)", "ja": "仕事 (shigoto)", "ko": "일 (il)", "vi": "công việc", "th": "งาน (ngan)", "id": "kerja", "sw": "kazi", "el": "δουλειά (doulia)", "cs": "práce", "km": "ការងារ (kangea)"},
    "school": {"es": "escuela", "fr": "école", "de": "Schule", "it": "scuola", "pt": "escola", "nl": "school", "pl": "szkoła", "ru": "школа (shkola)", "uk": "школа (shkola)", "tr": "okul", "ar": "مدرسة (madrasa)", "he": "בית ספר (beit sefer)", "hi": "स्कूल (skool)", "bn": "স্কুল (skul)", "ur": "اسکول (school)", "fa": "مدرسه (madrese)", "zh": "学校 (xuéxiào)", "ja": "学校 (gakkō)", "ko": "학교 (hakgyo)", "vi": "trường học", "th": "โรงเรียน (rongrian)", "id": "sekolah", "sw": "shule", "el": "σχολείο (scholio)", "cs": "škola", "km": "សាលា (sala)"},
    "bank": {"es": "banco", "fr": "banque", "de": "Bank", "it": "banca", "pt": "banco", "nl": "bank", "pl": "bank", "ru": "банк (bank)", "uk": "банк (bank)", "tr": "banka", "ar": "بنك (bank)", "he": "בנק (bank)", "hi": "बैंक (bank)", "bn": "ব্যাংক (bank)", "ur": "بینک (bank)", "fa": "بانک (bânk)", "zh": "银行 (yínháng)", "ja": "銀行 (ginkō)", "ko": "은행 (eunhaeng)", "vi": "ngân hàng", "th": "ธนาคาร (thanakhan)", "id": "bank", "sw": "benki", "el": "τράπεζα (trapeza)", "cs": "banka", "km": "ធនាគារ (thoneakia)"},
    "money": {"es": "dinero", "fr": "argent", "de": "Geld", "it": "soldi", "pt": "dinheiro", "nl": "geld", "pl": "pieniądze", "ru": "деньги (dengi)", "uk": "гроші (hroshi)", "tr": "para", "ar": "نقود (nuqud)", "he": "כסף (kesef)", "hi": "पैसा (paisa)", "bn": "টাকা (taka)", "ur": "پیسہ (paisa)", "fa": "پول (pul)", "zh": "钱 (qián)", "ja": "お金 (okane)", "ko": "돈 (don)", "vi": "tiền", "th": "เงิน (ngoen)", "id": "uang", "sw": "pesa", "el": "χρήματα (chrimata)", "cs": "peníze", "km": "លុយ (luy)"},
    "office": {"es": "oficina", "fr": "bureau", "de": "Büro", "it": "ufficio", "pt": "escritório", "nl": "kantoor", "pl": "biuro", "ru": "офис (ofis)", "uk": "офіс (ofis)", "tr": "ofis", "ar": "مكتب (maktab)", "he": "משרד (misrad)", "hi": "कार्यालय (karyalay)", "bn": "অফিস (ofis)", "ur": "دفتر (daftar)", "fa": "دفتر (daftar)", "zh": "办公室 (bàngōngshì)", "ja": "オフィス (ofisu)", "ko": "사무실 (samusil)", "vi": "văn phòng", "th": "สำนักงาน (samnakngan)", "id": "kantor", "sw": "ofisi", "el": "γραφείο (grafio)", "cs": "kancelář", "km": "ការិយាល័យ (kariyalay)"},
    "store": {"es": "tienda", "fr": "magasin", "de": "Geschäft", "it": "negozio", "pt": "loja", "nl": "winkel", "pl": "sklep", "ru": "магазин (magazin)", "uk": "магазин (mahazyn)", "tr": "dükkan", "ar": "دكان (dukkan)", "he": "חנות (chanut)", "hi": "दुकान (dukan)", "bn": "দোকান (dokan)", "ur": "دکان (dukan)", "fa": "مغازه (maghâze)", "zh": "商店 (shāngdiàn)", "ja": "店 (mise)", "ko": "가게 (gage)", "vi": "cửa hàng", "th": "ร้าน (ran)", "id": "toko", "sw": "duka", "el": "κατάστημα (katastima)", "cs": "obchod", "km": "ហាង (hang)"},
    "supermarket": {"es": "supermercado", "fr": "supermarché", "de": "Supermarkt", "it": "supermercato", "pt": "supermercado", "nl": "supermarkt", "pl": "supermarket", "ru": "супермаркет (supermarket)", "uk": "супермаркет (supermarket)", "tr": "süpermarket", "ar": "سوبر ماركت (subar market)", "he": "סופרמרקט (supermarket)", "hi": "सुपरमार्केट (supermarket)", "bn": "সুপারমার্কেট (supermarket)", "ur": "سپر مارکٹ (supermarket)", "fa": "سوپرمارکت (supermârket)", "zh": "超市 (chāoshì)", "ja": "スーパー (sūpā)", "ko": "슈퍼마켓 (syupeomaket)", "vi": "siêu thị", "th": "ซูเปอร์มาร์เก็ต (supermaket)", "id": "supermarket", "sw": "duka kubwa", "el": "σουπερμάρκετ (soupermarket)", "cs": "supermarket", "km": "ផ្សារទំនើប (phsar tumnoeup)"},
    "restaurant": {"es": "restaurante", "fr": "restaurant", "de": "Restaurant", "it": "ristorante", "pt": "restaurante", "nl": "restaurant", "pl": "restauracja", "ru": "ресторан (restoran)", "uk": "ресторан (restoran)", "tr": "restoran", "ar": "مطعم (mat'am)", "he": "מסעדה (mis'ada)", "hi": "रेस्तराँ (restora)", "bn": "রেস্টুরেন্ট (restaurant)", "ur": "ریستوران (restoran)", "fa": "رستوران (restorân)", "zh": "餐厅 (cāntīng)", "ja": "レストラン (resutoran)", "ko": "식당 (sikdang)", "vi": "nhà hàng", "th": "ร้านอาหาร (ran ahan)", "id": "restoran", "sw": "mkahawa", "el": "εστιατόριο (estiatorio)", "cs": "restaurace", "km": "ភោជនីយដ្ឋាន (phochonithan)"},
    "food": {"es": "comida", "fr": "nourriture", "de": "Essen", "it": "cibo", "pt": "comida", "nl": "eten", "pl": "jedzenie", "ru": "еда (yeda)", "uk": "їжа (yizha)", "tr": "yemek", "ar": "طعام (ta'am)", "he": "אוכל (ochel)", "hi": "खाना (khana)", "bn": "খাবার (khabar)", "ur": "کھانا (khana)", "fa": "غذا (ghazâ)", "zh": "食物 (shíwù)", "ja": "食べ物 (tabemono)", "ko": "음식 (eumsik)", "vi": "thức ăn", "th": "อาหาร (ahan)", "id": "makanan", "sw": "chakula", "el": "φαγητό (fagito)", "cs": "jídlo", "km": "អាហារ (ahar)"},
    "please": {"es": "por favor", "fr": "s'il vous plaît", "de": "bitte", "it": "per favore", "pt": "por favor", "nl": "alsjeblieft", "pl": "proszę", "ru": "пожалуйста (pozhaluysta)", "uk": "будь ласка (bud laska)", "tr": "lütfen", "ar": "من فضلك (min fadlik)", "he": "בבקשה (bevakasha)", "hi": "कृपया (kripya)", "bn": "অনুগ্রহ করে (onugroho kore)", "ur": "براہ کرم (barah karam)", "fa": "لطفا (lotfan)", "zh": "请 (qǐng)", "ja": "お願いします (onegai shimasu)", "ko": "주세요 (juseyo)", "vi": "xin vui lòng", "th": "กรุณา (karuna)", "id": "tolong", "sw": "tafadhali", "el": "παρακαλώ (parakalo)", "cs": "prosím", "km": "សូម (som)"},
    "thank you": {"es": "gracias", "fr": "merci", "de": "danke", "it": "grazie", "pt": "obrigado", "nl": "dank je", "pl": "dziękuję", "ru": "спасибо (spasibo)", "uk": "дякую (dyakuyu)", "tr": "teşekkürler", "ar": "شكرا (shukran)", "he": "תודה (toda)", "hi": "धन्यवाद (dhanyavaad)", "bn": "ধন্যবাদ (dhonnobad)", "ur": "شکریہ (shukriya)", "fa": "متشکرم (moteshakkeram)", "zh": "谢谢 (xièxie)", "ja": "ありがとう (arigatō)", "ko": "감사합니다 (gamsahamnida)", "vi": "cảm ơn", "th": "ขอบคุณ (khop khun)", "id": "terima kasih", "sw": "asante", "el": "ευχαριστώ (efcharisto)", "cs": "děkuji", "km": "អរគុណ (arkoun)"},
    "ticket": {"es": "billete", "fr": "billet", "de": "Fahrkarte", "it": "biglietto", "pt": "bilhete", "nl": "kaartje", "pl": "bilet", "ru": "билет (bilet)", "uk": "квиток (kvytok)", "tr": "bilet", "ar": "تذكرة (tadhkira)", "he": "כרטיס (kartis)", "hi": "टिकट (ticket)", "bn": "টিকিট (tikit)", "ur": "ٹکٹ (ticket)", "fa": "بلیت (belit)", "zh": "票 (piào)", "ja": "切符 (kippu)", "ko": "표 (pyo)", "vi": "vé", "th": "ตั๋ว (tua)", "id": "tiket", "sw": "tiketi", "el": "εισιτήριο (isitirio)", "cs": "jízdenka", "km": "សំបុត្រ (sombot)"},
    "map": {"es": "mapa", "fr": "carte", "de": "Karte", "it": "mappa", "pt": "mapa", "nl": "kaart", "pl": "mapa", "ru": "карта (karta)", "uk": "карта (karta)", "tr": "harita", "ar": "خريطة (kharita)", "he": "מפה (mapa)", "hi": "नक्शा (naksha)", "bn": "মানচিত্র (manchitro)", "ur": "نقشہ (naqsha)", "fa": "نقشه (naghshe)", "zh": "地图 (dìtú)", "ja": "地図 (chizu)", "ko": "지도 (jido)", "vi": "bản đồ", "th": "แผนที่ (phaenthi)", "id": "peta", "sw": "ramani", "el": "χάρτης (chartis)", "cs": "mapa", "km": "ផែនទី (phaenti)"},
    "airport": {"es": "aeropuerto", "fr": "aéroport", "de": "Flughafen", "it": "aeroporto", "pt": "aeroporto", "nl": "vliegveld", "pl": "lotnisko", "ru": "аэропорт (aeroport)", "uk": "аеропорт (aeroport)", "tr": "havalimanı", "ar": "مطار (matar)", "he": "שדה תעופה (sde te'ufa)", "hi": "हवाई अड्डा (hawai adda)", "bn": "বিমানবন্দর (bimanbondor)", "ur": "ہوائی اڈا (hawai adda)", "fa": "فرودگاه (forudgâh)", "zh": "机场 (jīchǎng)", "ja": "空港 (kūkō)", "ko": "공항 (gonghang)", "vi": "sân bay", "th": "สนามบิน (sanambin)", "id": "bandara", "sw": "uwanja wa ndege", "el": "αεροδρόμιο (aerodromio)", "cs": "letiště", "km": "អាកាសយានដ្ឋាន (akasyanthan)"},
    "hotel": {"es": "hotel", "fr": "hôtel", "de": "Hotel", "it": "albergo", "pt": "hotel", "nl": "hotel", "pl": "hotel", "ru": "отель (otel)", "uk": "готель (hotel)", "tr": "otel", "ar": "فندق (funduq)", "he": "מלון (malon)", "hi": "होटल (hotal)", "bn": "হোটেল (hotel)", "ur": "ہوٹل (hotel)", "fa": "هتل (hotel)", "zh": "酒店 (jiǔdiàn)", "ja": "ホテル (hoteru)", "ko": "호텔 (hotel)", "vi": "khách sạn", "th": "โรงแรม (rongraem)", "id": "hotel", "sw": "hoteli", "el": "ξενοδοχείο (xenodochio)", "cs": "hotel", "km": "សណ្ឋាគារ (santhakea)"},
    "sandwich": {"es": "sándwich", "fr": "sandwich", "de": "Sandwich", "it": "panino", "pt": "sanduíche", "nl": "boterham", "pl": "kanapka", "ru": "сэндвич (sendvich)", "uk": "сендвіч (sendvich)", "tr": "sandviç", "ar": "شطيرة (shatira)", "he": "כריך (karich)", "hi": "सैंडविच (sandwich)", "bn": "স্যান্ডউইচ (sandwich)", "ur": "سینڈوچ (sandwich)", "fa": "ساندویچ (sândvich)", "zh": "三明治 (sānmíngzhì)", "ja": "サンドイッチ (sandoitchi)", "ko": "샌드위치 (sandeuwichi)", "vi": "bánh mì kẹp", "th": "แซนด์วิช (sandwich)", "id": "roti lapis", "sw": "sandwichi", "el": "σάντουιτς (sandouits)", "cs": "sendvič", "km": "សាំងវិច (sangvich)"},
    "tea": {"es": "té", "fr": "thé", "de": "Tee", "it": "tè", "pt": "chá", "nl": "thee", "pl": "herbata", "ru": "чай (chay)", "uk": "чай (chai)", "tr": "çay", "ar": "شاي (shay)", "he": "תה (te)", "hi": "चाय (chai)", "bn": "চা (cha)", "ur": "چائے (chai)", "fa": "چای (châi)", "zh": "茶 (chá)", "ja": "お茶 (ocha)", "ko": "차 (cha)", "vi": "trà", "th": "ชา (cha)", "id": "teh", "sw": "chai", "el": "τσάι (tsai)", "cs": "čaj", "km": "តែ (tae)"},
    "bus": {"es": "autobús", "fr": "bus", "de": "Bus", "it": "autobus", "pt": "ônibus", "nl": "bus", "pl": "autobus", "ru": "автобус (avtobus)", "uk": "автобус (avtobus)", "tr": "otobüs", "ar": "أوتوبيس (utubis)", "he": "אוטובוס (otobus)", "hi": "बस (bas)", "bn": "বাস (bas)", "ur": "بس (bas)", "fa": "اتوبوس (otobus)", "zh": "公共汽车 (gōnggòng qìchē)", "ja": "バス (basu)", "ko": "버스 (beoseu)", "vi": "xe buýt", "th": "รถบัส (rot bat)", "id": "bus", "sw": "basi", "el": "λεωφορείο (leoforio)", "cs": "autobus", "km": "ឡានក្រុង (lan krong)"},
    "car": {"es": "coche", "fr": "voiture", "de": "Auto", "it": "auto", "pt": "carro", "nl": "auto", "pl": "samochód", "ru": "машина (mashina)", "uk": "машина (mashyna)", "tr": "araba", "ar": "سيارة (sayyara)", "he": "מכונית (mechonit)", "hi": "गाड़ी (gaadi)", "bn": "গাড়ি (gari)", "ur": "گاڑی (gaari)", "fa": "ماشین (mâshin)", "zh": "汽车 (qìchē)", "ja": "車 (kuruma)", "ko": "자동차 (jadongcha)", "vi": "xe hơi", "th": "รถยนต์ (rotyon)", "id": "mobil", "sw": "gari", "el": "αυτοκίνητο (aftokinito)", "cs": "auto", "km": "ឡាន (lan)"},
    "train": {"es": "tren", "fr": "train", "de": "Zug", "it": "treno", "pt": "trem", "nl": "trein", "pl": "pociąg", "ru": "поезд (poyezd)", "uk": "поїзд (poyizd)", "tr": "tren", "ar": "قطار (qitar)", "he": "רכבת (rakevet)", "hi": "रेलगाड़ी (relgaadi)", "bn": "ট্রেন (tren)", "ur": "ٹرین (train)", "fa": "قطار (ghatâr)", "zh": "火车 (huǒchē)", "ja": "電車 (densha)", "ko": "기차 (gicha)", "vi": "tàu hỏa", "th": "รถไฟ (rotfai)", "id": "kereta", "sw": "treni", "el": "τρένο (treno)", "cs": "vlak", "km": "រថភ្លើង (roth pleung)"},
    "wheels": {"es": "ruedas", "fr": "roues", "de": "Räder", "it": "ruote", "pt": "rodas", "nl": "wielen", "pl": "koła", "ru": "колёса (kolyosa)", "uk": "колеса (kolesa)", "tr": "tekerlekler", "ar": "عجلات (ajalat)", "he": "גלגלים (galgalim)", "hi": "पहिये (pahiye)", "bn": "চাকা (chaka)", "ur": "پہیے (pahiye)", "fa": "چرخ‌ها (charkhâ)", "zh": "车轮 (chēlún)", "ja": "車輪 (sharin)", "ko": "바퀴 (bakwi)", "vi": "bánh xe", "th": "ล้อ (lo)", "id": "roda", "sw": "magurudumu", "el": "ρόδες (rodes)", "cs": "kola", "km": "កង់ (kang)"},
    "door": {"es": "puerta", "fr": "porte", "de": "Tür", "it": "porta", "pt": "porta", "nl": "deur", "pl": "drzwi", "ru": "дверь (dver)", "uk": "двері (dveri)", "tr": "kapı", "ar": "باب (bab)", "he": "דלת (delet)", "hi": "दरवाज़ा (darwaza)", "bn": "দরজা (doroja)", "ur": "دروازہ (darwaza)", "fa": "در (dar)", "zh": "门 (mén)", "ja": "ドア (doa)", "ko": "문 (mun)", "vi": "cửa", "th": "ประตู (pratu)", "id": "pintu", "sw": "mlango", "el": "πόρτα (porta)", "cs": "dveře", "km": "ទ្វារ (tvear)"},
    "town": {"es": "pueblo", "fr": "ville", "de": "Stadt", "it": "città", "pt": "cidade", "nl": "stad", "pl": "miasto", "ru": "город (gorod)", "uk": "місто (misto)", "tr": "kasaba", "ar": "بلدة (balda)", "he": "עיר (ir)", "hi": "शहर (shahar)", "bn": "শহর (shohor)", "ur": "شہر (shehar)", "fa": "شهر (shahr)", "zh": "城镇 (chéngzhèn)", "ja": "町 (machi)", "ko": "마을 (ma-eul)", "vi": "thị trấn", "th": "เมือง (mueang)", "id": "kota", "sw": "mji", "el": "πόλη (poli)", "cs": "město", "km": "ទីក្រុង (ti krong)"},
    "park": {"es": "parque", "fr": "parc", "de": "Park", "it": "parco", "pt": "parque", "nl": "park", "pl": "park", "ru": "парк (park)", "uk": "парк (park)", "tr": "park", "ar": "حديقة (hadiqa)", "he": "פארק (park)", "hi": "पार्क (park)", "bn": "পার্ক (park)", "ur": "پارک (park)", "fa": "پارک (pârk)", "zh": "公园 (gōngyuán)", "ja": "公園 (kōen)", "ko": "공원 (gongwon)", "vi": "công viên", "th": "สวน (suan)", "id": "taman", "sw": "bustani", "el": "πάρκο (parko)", "cs": "park", "km": "សួន (suon)"},
    "sun": {"es": "sol", "fr": "soleil", "de": "Sonne", "it": "sole", "pt": "sol", "nl": "zon", "pl": "słońce", "ru": "солнце (solntse)", "uk": "сонце (sontse)", "tr": "güneş", "ar": "شمس (shams)", "he": "שמש (shemesh)", "hi": "सूरज (sooraj)", "bn": "সূর্য (surjo)", "ur": "سورج (sooraj)", "fa": "خورشید (khorshid)", "zh": "太阳 (tàiyáng)", "ja": "太陽 (taiyō)", "ko": "해 (hae)", "vi": "mặt trời", "th": "ดวงอาทิตย์ (duang athit)", "id": "matahari", "sw": "jua", "el": "ήλιος (ilios)", "cs": "slunce", "km": "ព្រះអាទិត្យ (preah atit)"},
    "rain": {"es": "lluvia", "fr": "pluie", "de": "Regen", "it": "pioggia", "pt": "chuva", "nl": "regen", "pl": "deszcz", "ru": "дождь (dozhd)", "uk": "дощ (doshch)", "tr": "yağmur", "ar": "مطر (matar)", "he": "גשם (geshem)", "hi": "बारिश (baarish)", "bn": "বৃষ্টি (bristi)", "ur": "بارش (baarish)", "fa": "باران (bârân)", "zh": "雨 (yǔ)", "ja": "雨 (ame)", "ko": "비 (bi)", "vi": "mưa", "th": "ฝน (fon)", "id": "hujan", "sw": "mvua", "el": "βροχή (vrochi)", "cs": "déšť", "km": "ភ្លៀង (phlieng)"},
    "hand": {"es": "mano", "fr": "main", "de": "Hand", "it": "mano", "pt": "mão", "nl": "hand", "pl": "ręka", "ru": "рука (ruka)", "uk": "рука (ruka)", "tr": "el", "ar": "يد (yad)", "he": "יד (yad)", "hi": "हाथ (haath)", "bn": "হাত (hat)", "ur": "ہاتھ (haath)", "fa": "دست (dast)", "zh": "手 (shǒu)", "ja": "手 (te)", "ko": "손 (son)", "vi": "tay", "th": "มือ (mue)", "id": "tangan", "sw": "mkono", "el": "χέρι (cheri)", "cs": "ruka", "km": "ដៃ (dai)"},
    "up": {"es": "arriba", "fr": "en haut", "de": "oben", "it": "su", "pt": "para cima", "nl": "omhoog", "pl": "w górę", "ru": "вверх (vverkh)", "uk": "вгору (vhoru)", "tr": "yukarı", "ar": "فوق (fawq)", "he": "למעלה (lema'la)", "hi": "ऊपर (oopar)", "bn": "উপরে (upore)", "ur": "اوپر (oopar)", "fa": "بالا (bâlâ)", "zh": "上 (shàng)", "ja": "上 (ue)", "ko": "위 (wi)", "vi": "lên", "th": "ขึ้น (khuen)", "id": "atas", "sw": "juu", "el": "πάνω (pano)", "cs": "nahoru", "km": "លើ (leu)"},
    "down": {"es": "abajo", "fr": "en bas", "de": "unten", "it": "giù", "pt": "para baixo", "nl": "omlaag", "pl": "w dół", "ru": "вниз (vniz)", "uk": "вниз (vnyz)", "tr": "aşağı", "ar": "تحت (taht)", "he": "למטה (lemata)", "hi": "नीचे (neeche)", "bn": "নিচে (niche)", "ur": "نیچے (neeche)", "fa": "پایین (pâyin)", "zh": "下 (xià)", "ja": "下 (shita)", "ko": "아래 (arae)", "vi": "xuống", "th": "ลง (long)", "id": "bawah", "sw": "chini", "el": "κάτω (kato)", "cs": "dolů", "km": "ក្រោម (kraom)"},
    "left": {"es": "izquierda", "fr": "gauche", "de": "links", "it": "sinistra", "pt": "esquerda", "nl": "links", "pl": "lewo", "ru": "налево (nalevo)", "uk": "ліворуч (livoruch)", "tr": "sol", "ar": "يسار (yasar)", "he": "שמאל (smol)", "hi": "बाएँ (baayen)", "bn": "বাম (bam)", "ur": "بائیں (baayen)", "fa": "چپ (chap)", "zh": "左 (zuǒ)", "ja": "左 (hidari)", "ko": "왼쪽 (wenjjok)", "vi": "bên trái", "th": "ซ้าย (sai)", "id": "kiri", "sw": "kushoto", "el": "αριστερά (aristera)", "cs": "vlevo", "km": "ឆ្វេង (chveng)"},
    "right": {"es": "derecha", "fr": "droite", "de": "rechts", "it": "destra", "pt": "direita", "nl": "rechts", "pl": "prawo", "ru": "направо (napravo)", "uk": "праворуч (pravoruch)", "tr": "sağ", "ar": "يمين (yamin)", "he": "ימין (yamin)", "hi": "दाएँ (daayen)", "bn": "ডান (dan)", "ur": "دائیں (daayen)", "fa": "راست (râst)", "zh": "右 (yòu)", "ja": "右 (migi)", "ko": "오른쪽 (oreunjjok)", "vi": "bên phải", "th": "ขวา (khwa)", "id": "kanan", "sw": "kulia", "el": "δεξιά (dexia)", "cs": "vpravo", "km": "ស្តាំ (sdam)"},
    "morning": {"es": "mañana", "fr": "matin", "de": "Morgen", "it": "mattina", "pt": "manhã", "nl": "ochtend", "pl": "rano", "ru": "утро (utro)", "uk": "ранок (ranok)", "tr": "sabah", "ar": "صباح (sabah)", "he": "בוקר (boker)", "hi": "सुबह (subah)", "bn": "সকাল (sokal)", "ur": "صبح (subah)", "fa": "صبح (sobh)", "zh": "早上 (zǎoshang)", "ja": "朝 (asa)", "ko": "아침 (achim)", "vi": "buổi sáng", "th": "เช้า (chao)", "id": "pagi", "sw": "asubuhi", "el": "πρωί (proi)", "cs": "ráno", "km": "ព្រឹក (pruk)"},
    "song": {"es": "canción", "fr": "chanson", "de": "Lied", "it": "canzone", "pt": "canção", "nl": "lied", "pl": "piosenka", "ru": "песня (pesnya)", "uk": "пісня (pisnya)", "tr": "şarkı", "ar": "أغنية (ughniya)", "he": "שיר (shir)", "hi": "गाना (gaana)", "bn": "গান (gan)", "ur": "گانا (gaana)", "fa": "آهنگ (âhang)", "zh": "歌 (gē)", "ja": "歌 (uta)", "ko": "노래 (norae)", "vi": "bài hát", "th": "เพลง (phleng)", "id": "lagu", "sw": "wimbo", "el": "τραγούδι (tragoudi)", "cs": "písnička", "km": "បទចម្រៀង (bot chamrieng)"},
    "word": {"es": "palabra", "fr": "mot", "de": "Wort", "it": "parola", "pt": "palavra", "nl": "woord", "pl": "słowo", "ru": "слово (slovo)", "uk": "слово (slovo)", "tr": "kelime", "ar": "كلمة (kalima)", "he": "מילה (mila)", "hi": "शब्द (shabd)", "bn": "শব্দ (shobdo)", "ur": "لفظ (lafz)", "fa": "کلمه (kalame)", "zh": "词 (cí)", "ja": "言葉 (kotoba)", "ko": "단어 (daneo)", "vi": "từ", "th": "คำ (kham)", "id": "kata", "sw": "neno", "el": "λέξη (lexi)", "cs": "slovo", "km": "ពាក្យ (peak)"},
    "near": {"es": "cerca", "fr": "près", "de": "nah", "it": "vicino", "pt": "perto", "nl": "dichtbij", "pl": "blisko", "ru": "близко (blizko)", "uk": "близько (blyzko)", "tr": "yakın", "ar": "قريب (qarib)", "he": "קרוב (karov)", "hi": "पास (paas)", "bn": "কাছে (kache)", "ur": "قریب (qareeb)", "fa": "نزدیک (nazdik)", "zh": "近 (jìn)", "ja": "近い (chikai)", "ko": "가까이 (gakkai)", "vi": "gần", "th": "ใกล้ (klai)", "id": "dekat", "sw": "karibu", "el": "κοντά (konta)", "cs": "blízko", "km": "ជិត (chit)"},
    "far": {"es": "lejos", "fr": "loin", "de": "weit", "it": "lontano", "pt": "longe", "nl": "ver", "pl": "daleko", "ru": "далеко (daleko)", "uk": "далеко (daleko)", "tr": "uzak", "ar": "بعيد (ba'id)", "he": "רחוק (rachok)", "hi": "दूर (door)", "bn": "দূরে (dure)", "ur": "دور (door)", "fa": "دور (dur)", "zh": "远 (yuǎn)", "ja": "遠い (tōi)", "ko": "멀리 (meolli)", "vi": "xa", "th": "ไกล (klai)", "id": "jauh", "sw": "mbali", "el": "μακριά (makria)", "cs": "daleko", "km": "ឆ្ងាយ (chngay)"},
    "fast": {"es": "rápido", "fr": "vite", "de": "schnell", "it": "veloce", "pt": "rápido", "nl": "snel", "pl": "szybko", "ru": "быстро (bystro)", "uk": "швидко (shvydko)", "tr": "hızlı", "ar": "سريع (sari')", "he": "מהר (maher)", "hi": "तेज़ (tez)", "bn": "দ্রুত (druto)", "ur": "تیز (tez)", "fa": "سریع (sari')", "zh": "快 (kuài)", "ja": "速い (hayai)", "ko": "빠르게 (ppareuge)", "vi": "nhanh", "th": "เร็ว (reo)", "id": "cepat", "sw": "haraka", "el": "γρήγορα (grigora)", "cs": "rychle", "km": "លឿន (leuon)"},
    "slow": {"es": "despacio", "fr": "lentement", "de": "langsam", "it": "lento", "pt": "devagar", "nl": "langzaam", "pl": "wolno", "ru": "медленно (medlenno)", "uk": "повільно (povilno)", "tr": "yavaş", "ar": "بطيء (bati')", "he": "לאט (le'at)", "hi": "धीरे (dheere)", "bn": "ধীরে (dhire)", "ur": "آہستہ (aahista)", "fa": "آهسته (âheste)", "zh": "慢 (màn)", "ja": "遅い (osoi)", "ko": "느리게 (neurige)", "vi": "chậm", "th": "ช้า (cha)", "id": "lambat", "sw": "polepole", "el": "αργά (arga)", "cs": "pomalu", "km": "យឺត (yeut)"},
    # Verbs and function words the featured lyrics lean on, so the lexicon tier
    # reaches every line rather than only the noun-heavy ones.
    "count": {"es": "contar", "fr": "compter", "de": "zählen", "it": "contare", "pt": "contar", "nl": "tellen", "pl": "liczyć", "ru": "считать (schitat)", "uk": "рахувати (rakhuvaty)", "tr": "saymak", "ar": "يعد (ya'idd)", "he": "לספור (lispor)", "hi": "गिनना (ginna)", "bn": "গণনা করা (gonona kora)", "ur": "گننا (ginna)", "fa": "شمردن (shomordan)", "zh": "数 (shǔ)", "ja": "数える (kazoeru)", "ko": "세다 (seda)", "vi": "đếm", "th": "นับ (nap)", "id": "menghitung", "sw": "kuhesabu", "el": "μετρώ (metro)", "cs": "počítat", "km": "រាប់ (rab)"},
    "plan": {"es": "plan", "fr": "plan", "de": "Plan", "it": "piano", "pt": "plano", "nl": "plan", "pl": "plan", "ru": "план (plan)", "uk": "план (plan)", "tr": "plan", "ar": "خطة (khitta)", "he": "תוכנית (tochnit)", "hi": "योजना (yojana)", "bn": "পরিকল্পনা (porikolpona)", "ur": "منصوبہ (mansooba)", "fa": "برنامه (barnâme)", "zh": "计划 (jìhuà)", "ja": "計画 (keikaku)", "ko": "계획 (gyehoek)", "vi": "kế hoạch", "th": "แผน (phaen)", "id": "rencana", "sw": "mpango", "el": "σχέδιο (schedio)", "cs": "plán", "km": "ផែនការ (phaenkar)"},
    "bag": {"es": "bolsa", "fr": "sac", "de": "Tasche", "it": "borsa", "pt": "bolsa", "nl": "tas", "pl": "torba", "ru": "сумка (sumka)", "uk": "сумка (sumka)", "tr": "çanta", "ar": "حقيبة (haqiba)", "he": "תיק (tik)", "hi": "बैग (bag)", "bn": "ব্যাগ (bag)", "ur": "تھیلا (thaila)", "fa": "کیف (kif)", "zh": "包 (bāo)", "ja": "かばん (kaban)", "ko": "가방 (gabang)", "vi": "túi", "th": "กระเป๋า (krapao)", "id": "tas", "sw": "mfuko", "el": "τσάντα (tsanta)", "cs": "taška", "km": "កាបូប (kabob)"},
    "come": {"es": "venir", "fr": "venir", "de": "kommen", "it": "venire", "pt": "vir", "nl": "komen", "pl": "przyjść", "ru": "приходить (prikhodit)", "uk": "приходити (prykhodyty)", "tr": "gelmek", "ar": "يأتي (ya'ti)", "he": "לבוא (lavo)", "hi": "आना (aana)", "bn": "আসা (asha)", "ur": "آنا (aana)", "fa": "آمدن (âmadan)", "zh": "来 (lái)", "ja": "来る (kuru)", "ko": "오다 (oda)", "vi": "đến", "th": "มา (ma)", "id": "datang", "sw": "kuja", "el": "έρχομαι (erchomai)", "cs": "přijít", "km": "មក (mok)"},
    "say": {"es": "decir", "fr": "dire", "de": "sagen", "it": "dire", "pt": "dizer", "nl": "zeggen", "pl": "mówić", "ru": "говорить (govorit)", "uk": "казати (kazaty)", "tr": "söylemek", "ar": "يقول (yaqul)", "he": "לומר (lomar)", "hi": "कहना (kehna)", "bn": "বলা (bola)", "ur": "کہنا (kehna)", "fa": "گفتن (goftan)", "zh": "说 (shuō)", "ja": "言う (iu)", "ko": "말하다 (malhada)", "vi": "nói", "th": "พูด (phut)", "id": "berkata", "sw": "kusema", "el": "λέω (leo)", "cs": "říkat", "km": "និយាយ (niyay)"},
    "know": {"es": "saber", "fr": "savoir", "de": "wissen", "it": "sapere", "pt": "saber", "nl": "weten", "pl": "wiedzieć", "ru": "знать (znat)", "uk": "знати (znaty)", "tr": "bilmek", "ar": "يعرف (ya'rif)", "he": "לדעת (lada'at)", "hi": "जानना (jaanna)", "bn": "জানা (jana)", "ur": "جاننا (jaanna)", "fa": "دانستن (dânestan)", "zh": "知道 (zhīdào)", "ja": "知る (shiru)", "ko": "알다 (alda)", "vi": "biết", "th": "รู้ (ru)", "id": "tahu", "sw": "kujua", "el": "ξέρω (xero)", "cs": "vědět", "km": "ដឹង (deung)"},
    "way": {"es": "camino", "fr": "chemin", "de": "Weg", "it": "strada", "pt": "caminho", "nl": "weg", "pl": "droga", "ru": "путь (put)", "uk": "шлях (shlyakh)", "tr": "yol", "ar": "طريق (tariq)", "he": "דרך (derech)", "hi": "रास्ता (raasta)", "bn": "পথ (poth)", "ur": "راستہ (raasta)", "fa": "راه (râh)", "zh": "路 (lù)", "ja": "道 (michi)", "ko": "길 (gil)", "vi": "đường", "th": "ทาง (thang)", "id": "jalan", "sw": "njia", "el": "δρόμος (dromos)", "cs": "cesta", "km": "ផ្លូវ (phlov)"},
    "wait": {"es": "esperar", "fr": "attendre", "de": "warten", "it": "aspettare", "pt": "esperar", "nl": "wachten", "pl": "czekać", "ru": "ждать (zhdat)", "uk": "чекати (chekaty)", "tr": "beklemek", "ar": "ينتظر (yantazir)", "he": "לחכות (lechakot)", "hi": "इंतज़ार करना (intezaar karna)", "bn": "অপেক্ষা করা (opekkha kora)", "ur": "انتظار کرنا (intezaar karna)", "fa": "منتظر ماندن (montazer mândan)", "zh": "等 (děng)", "ja": "待つ (matsu)", "ko": "기다리다 (gidarida)", "vi": "chờ", "th": "รอ (ro)", "id": "menunggu", "sw": "kusubiri", "el": "περιμένω (perimeno)", "cs": "čekat", "km": "រង់ចាំ (rongcham)"},
    "good": {"es": "bueno", "fr": "bien", "de": "gut", "it": "bene", "pt": "bom", "nl": "goed", "pl": "dobrze", "ru": "хорошо (khorosho)", "uk": "добре (dobre)", "tr": "iyi", "ar": "جيد (jayyid)", "he": "טוב (tov)", "hi": "अच्छा (achha)", "bn": "ভালো (bhalo)", "ur": "اچھا (achha)", "fa": "خوب (khub)", "zh": "好 (hǎo)", "ja": "いい (ii)", "ko": "좋다 (jota)", "vi": "tốt", "th": "ดี (di)", "id": "baik", "sw": "nzuri", "el": "καλά (kala)", "cs": "dobře", "km": "ល្អ (l'or)"},
    "yes": {"es": "sí", "fr": "oui", "de": "ja", "it": "sì", "pt": "sim", "nl": "ja", "pl": "tak", "ru": "да (da)", "uk": "так (tak)", "tr": "evet", "ar": "نعم (na'am)", "he": "כן (ken)", "hi": "हाँ (haan)", "bn": "হ্যাঁ (hyan)", "ur": "ہاں (haan)", "fa": "بله (bale)", "zh": "是 (shì)", "ja": "はい (hai)", "ko": "네 (ne)", "vi": "vâng", "th": "ใช่ (chai)", "id": "ya", "sw": "ndiyo", "el": "ναι (nai)", "cs": "ano", "km": "បាទ (bat)"},
    "help": {"es": "ayudar", "fr": "aider", "de": "helfen", "it": "aiutare", "pt": "ajudar", "nl": "helpen", "pl": "pomóc", "ru": "помочь (pomoch)", "uk": "допомогти (dopomohty)", "tr": "yardım etmek", "ar": "يساعد (yusa'id)", "he": "לעזור (la'azor)", "hi": "मदद करना (madad karna)", "bn": "সাহায্য করা (shahajjo kora)", "ur": "مدد کرنا (madad karna)", "fa": "کمک کردن (komak kardan)", "zh": "帮助 (bāngzhù)", "ja": "助ける (tasukeru)", "ko": "돕다 (dopda)", "vi": "giúp", "th": "ช่วย (chuai)", "id": "membantu", "sw": "kusaidia", "el": "βοηθώ (voitho)", "cs": "pomoci", "km": "ជួយ (chuoy)"},
    "how much": {"es": "cuánto", "fr": "combien", "de": "wie viel", "it": "quanto", "pt": "quanto", "nl": "hoeveel", "pl": "ile", "ru": "сколько (skolko)", "uk": "скільки (skilky)", "tr": "ne kadar", "ar": "كم (kam)", "he": "כמה (kama)", "hi": "कितना (kitna)", "bn": "কত (koto)", "ur": "کتنا (kitna)", "fa": "چقدر (cheghadr)", "zh": "多少 (duōshao)", "ja": "いくら (ikura)", "ko": "얼마 (eolma)", "vi": "bao nhiêu", "th": "เท่าไหร่ (thaorai)", "id": "berapa", "sw": "ngapi", "el": "πόσο (poso)", "cs": "kolik", "km": "ប៉ុន្មាន (ponman)"},
    "where": {"es": "dónde", "fr": "où", "de": "wo", "it": "dove", "pt": "onde", "nl": "waar", "pl": "gdzie", "ru": "где (gde)", "uk": "де (de)", "tr": "nerede", "ar": "أين (ayna)", "he": "איפה (eifo)", "hi": "कहाँ (kahan)", "bn": "কোথায় (kothay)", "ur": "کہاں (kahan)", "fa": "کجا (kojâ)", "zh": "哪里 (nǎlǐ)", "ja": "どこ (doko)", "ko": "어디 (eodi)", "vi": "ở đâu", "th": "ที่ไหน (thi nai)", "id": "di mana", "sw": "wapi", "el": "πού (pou)", "cs": "kde", "km": "ណា (na)"},
    "wave": {"es": "saludar con la mano", "fr": "faire signe de la main", "de": "winken", "it": "salutare con la mano", "pt": "acenar", "nl": "zwaaien", "pl": "machać", "ru": "махать (makhat)", "uk": "махати (makhaty)", "tr": "el sallamak", "ar": "يلوح (yulawwih)", "he": "לנפנף (lenafnef)", "hi": "हाथ हिलाना (haath hilana)", "bn": "হাত নাড়া (hat nara)", "ur": "ہاتھ ہلانا (haath hilana)", "fa": "دست تکان دادن (dast tekân dâdan)", "zh": "挥手 (huīshǒu)", "ja": "手を振る (te o furu)", "ko": "손을 흔들다 (soneul heundeulda)", "vi": "vẫy tay", "th": "โบกมือ (bok mue)", "id": "melambaikan tangan", "sw": "kupunga mkono", "el": "χαιρετώ (chaireto)", "cs": "mávat", "km": "គ្រវីដៃ (kroviy dai)"},
    "low": {"es": "bajo", "fr": "bas", "de": "niedrig", "it": "basso", "pt": "baixo", "nl": "laag", "pl": "nisko", "ru": "низко (nizko)", "uk": "низько (nyzko)", "tr": "alçak", "ar": "منخفض (munkhafid)", "he": "נמוך (namuch)", "hi": "नीचा (neecha)", "bn": "নিচু (nichu)", "ur": "نیچا (neecha)", "fa": "پایین (pâyin)", "zh": "低 (dī)", "ja": "低い (hikui)", "ko": "낮게 (natge)", "vi": "thấp", "th": "ต่ำ (tam)", "id": "rendah", "sw": "chini", "el": "χαμηλά (chamila)", "cs": "nízko", "km": "ទាប (teab)"},
    "horn": {"es": "bocina", "fr": "klaxon", "de": "Hupe", "it": "clacson", "pt": "buzina", "nl": "claxon", "pl": "klakson", "ru": "гудок (gudok)", "uk": "гудок (hudok)", "tr": "korna", "ar": "بوق (buq)", "he": "צופר (tzofar)", "hi": "हॉर्न (horn)", "bn": "হর্ন (horn)", "ur": "ہارن (horn)", "fa": "بوق (bugh)", "zh": "喇叭 (lǎba)", "ja": "クラクション (kurakushon)", "ko": "경적 (gyeongjeok)", "vi": "còi", "th": "แตร (trae)", "id": "klakson", "sw": "honi", "el": "κόρνα (korna)", "cs": "klakson", "km": "ស្នែង (snaeng)"},
    "early": {"es": "temprano", "fr": "tôt", "de": "früh", "it": "presto", "pt": "cedo", "nl": "vroeg", "pl": "wcześnie", "ru": "рано (rano)", "uk": "рано (rano)", "tr": "erken", "ar": "مبكر (mubakkir)", "he": "מוקדם (mukdam)", "hi": "जल्दी (jaldi)", "bn": "তাড়াতাড়ি (taratari)", "ur": "جلدی (jaldi)", "fa": "زود (zud)", "zh": "早 (zǎo)", "ja": "早い (hayai)", "ko": "일찍 (iljjik)", "vi": "sớm", "th": "แต่เช้า (tae chao)", "id": "awal", "sw": "mapema", "el": "νωρίς (noris)", "cs": "brzy", "km": "ព្រលឹម (pralum)"},
    "sing": {"es": "cantar", "fr": "chanter", "de": "singen", "it": "cantare", "pt": "cantar", "nl": "zingen", "pl": "śpiewać", "ru": "петь (pet)", "uk": "співати (spivaty)", "tr": "şarkı söylemek", "ar": "يغني (yughanni)", "he": "לשיר (lashir)", "hi": "गाना (gaana)", "bn": "গাওয়া (gaoa)", "ur": "گانا (gaana)", "fa": "آواز خواندن (âvâz khândan)", "zh": "唱 (chàng)", "ja": "歌う (utau)", "ko": "노래하다 (noraehada)", "vi": "hát", "th": "ร้องเพลง (rong phleng)", "id": "menyanyi", "sw": "kuimba", "el": "τραγουδώ (tragoudo)", "cs": "zpívat", "km": "ច្រៀង (chrieng)"},
    "soft": {"es": "suave", "fr": "doucement", "de": "leise", "it": "piano", "pt": "baixinho", "nl": "zacht", "pl": "cicho", "ru": "тихо (tikho)", "uk": "тихо (tykho)", "tr": "yumuşak", "ar": "بهدوء (bihudu')", "he": "בשקט (besheket)", "hi": "धीरे (dheere)", "bn": "আস্তে (aste)", "ur": "آہستہ (aahista)", "fa": "آرام (ârâm)", "zh": "轻 (qīng)", "ja": "静かに (shizuka ni)", "ko": "부드럽게 (budeureopge)", "vi": "nhẹ", "th": "เบา (bao)", "id": "lembut", "sw": "taratibu", "el": "απαλά (apala)", "cs": "tiše", "km": "ស្ងាត់ៗ (sngat sngat)"},
    "loud": {"es": "fuerte", "fr": "fort", "de": "laut", "it": "forte", "pt": "alto", "nl": "hard", "pl": "głośno", "ru": "громко (gromko)", "uk": "гучно (huchno)", "tr": "yüksek sesle", "ar": "بصوت عال (bisawt 'ali)", "he": "בקול רם (bekol ram)", "hi": "ज़ोर से (zor se)", "bn": "জোরে (jore)", "ur": "زور سے (zor se)", "fa": "بلند (boland)", "zh": "大声 (dàshēng)", "ja": "大きな声で (ōkina koe de)", "ko": "크게 (keuge)", "vi": "to", "th": "ดัง (dang)", "id": "keras", "sw": "kwa sauti", "el": "δυνατά (dynata)", "cs": "nahlas", "km": "ខ្លាំង (khlang)"},
    "learn": {"es": "aprender", "fr": "apprendre", "de": "lernen", "it": "imparare", "pt": "aprender", "nl": "leren", "pl": "uczyć się", "ru": "учить (uchit)", "uk": "вчити (vchyty)", "tr": "öğrenmek", "ar": "يتعلم (yata'allam)", "he": "ללמוד (lilmod)", "hi": "सीखना (seekhna)", "bn": "শেখা (shekha)", "ur": "سیکھنا (seekhna)", "fa": "یاد گرفتن (yâd gereftan)", "zh": "学习 (xuéxí)", "ja": "学ぶ (manabu)", "ko": "배우다 (baeuda)", "vi": "học", "th": "เรียน (rian)", "id": "belajar", "sw": "kujifunza", "el": "μαθαίνω (matheno)", "cs": "učit se", "km": "រៀន (rien)"},
    "round": {"es": "vuelta", "fr": "tour", "de": "rundherum", "it": "giro", "pt": "volta", "nl": "rond", "pl": "wokoło", "ru": "кругом (krugom)", "uk": "навколо (navkolo)", "tr": "etrafında", "ar": "حول (hawl)", "he": "סביב (saviv)", "hi": "चारों ओर (chaaron or)", "bn": "চারপাশে (charpashe)", "ur": "چاروں طرف (chaaron taraf)", "fa": "دور (dowr)", "zh": "转圈 (zhuànquān)", "ja": "ぐるぐる (guruguru)", "ko": "빙빙 (bingbing)", "vi": "vòng quanh", "th": "รอบ (rop)", "id": "berputar", "sw": "kuzunguka", "el": "γύρω (gyro)", "cs": "dokola", "km": "ជុំវិញ (chum vinh)"},
    "foot": {"es": "pie", "fr": "pied", "de": "Fuß", "it": "piede", "pt": "pé", "nl": "voet", "pl": "stopa", "ru": "нога (noga)", "uk": "нога (noha)", "tr": "ayak", "ar": "قدم (qadam)", "he": "רגל (regel)", "hi": "पैर (pair)", "bn": "পা (pa)", "ur": "پاؤں (paon)", "fa": "پا (pâ)", "zh": "脚 (jiǎo)", "ja": "足 (ashi)", "ko": "발 (bal)", "vi": "chân", "th": "เท้า (thao)", "id": "kaki", "sw": "mguu", "el": "πόδι (podi)", "cs": "noha", "km": "ជើង (cheung)"},
    "floor": {"es": "suelo", "fr": "sol", "de": "Boden", "it": "pavimento", "pt": "chão", "nl": "vloer", "pl": "podłoga", "ru": "пол (pol)", "uk": "підлога (pidloha)", "tr": "yer", "ar": "أرضية (ardiyya)", "he": "רצפה (ritzpa)", "hi": "फ़र्श (farsh)", "bn": "মেঝে (mejhe)", "ur": "فرش (farsh)", "fa": "زمین (zamin)", "zh": "地板 (dìbǎn)", "ja": "床 (yuka)", "ko": "바닥 (badak)", "vi": "sàn", "th": "พื้น (phuen)", "id": "lantai", "sw": "sakafu", "el": "πάτωμα (patoma)", "cs": "podlaha", "km": "កម្រាល (kamral)"},
    "turn": {"es": "girar", "fr": "tourner", "de": "drehen", "it": "girare", "pt": "virar", "nl": "draaien", "pl": "obrócić się", "ru": "повернуться (povernutsya)", "uk": "повернутися (povernutysya)", "tr": "dönmek", "ar": "يدور (yadur)", "he": "להסתובב (lehistovev)", "hi": "घूमना (ghoomna)", "bn": "ঘোরা (ghora)", "ur": "گھومنا (ghoomna)", "fa": "چرخیدن (charkhidan)", "zh": "转 (zhuǎn)", "ja": "回る (mawaru)", "ko": "돌다 (dolda)", "vi": "quay", "th": "หมุน (mun)", "id": "berbalik", "sw": "kuzunguka", "el": "γυρίζω (gyrizo)", "cs": "otočit se", "km": "បែរ (bae)"},
    "smile": {"es": "sonreír", "fr": "sourire", "de": "lächeln", "it": "sorridere", "pt": "sorrir", "nl": "lachen", "pl": "uśmiechać się", "ru": "улыбаться (ulybatsya)", "uk": "усміхатися (usmikhatysya)", "tr": "gülümsemek", "ar": "يبتسم (yabtasim)", "he": "לחייך (lechayech)", "hi": "मुस्कुराना (muskurana)", "bn": "হাসা (hasha)", "ur": "مسکرانا (muskurana)", "fa": "لبخند زدن (labkhand zadan)", "zh": "微笑 (wēixiào)", "ja": "笑う (warau)", "ko": "웃다 (utda)", "vi": "cười", "th": "ยิ้ม (yim)", "id": "tersenyum", "sw": "kutabasamu", "el": "χαμογελώ (chamogelo)", "cs": "usmívat se", "km": "ញញឹម (nhonhim)"},
    "more": {"es": "más", "fr": "plus", "de": "mehr", "it": "più", "pt": "mais", "nl": "meer", "pl": "więcej", "ru": "больше (bolshe)", "uk": "більше (bilshe)", "tr": "daha", "ar": "أكثر (akthar)", "he": "עוד (od)", "hi": "और (aur)", "bn": "আরো (aro)", "ur": "اور (aur)", "fa": "بیشتر (bishtar)", "zh": "更多 (gèng duō)", "ja": "もっと (motto)", "ko": "더 (deo)", "vi": "thêm", "th": "มากกว่า (mak kwa)", "id": "lagi", "sw": "zaidi", "el": "περισσότερο (perissotero)", "cs": "více", "km": "ថែម (thaem)"},
    "clap": {"es": "aplaudir", "fr": "applaudir", "de": "klatschen", "it": "applaudire", "pt": "aplaudir", "nl": "klappen", "pl": "klaskać", "ru": "хлопать (khlopat)", "uk": "хлопати (khlopaty)", "tr": "el çırpmak", "ar": "يصفق (yusaffiq)", "he": "למחוא כפיים (limcho kapayim)", "hi": "ताली बजाना (taali bajana)", "bn": "তালি দেওয়া (tali deoa)", "ur": "تالی بجانا (taali bajana)", "fa": "دست زدن (dast zadan)", "zh": "拍手 (pāishǒu)", "ja": "拍手する (hakushu suru)", "ko": "박수 치다 (baksu chida)", "vi": "vỗ tay", "th": "ตบมือ (top mue)", "id": "bertepuk tangan", "sw": "kupiga makofi", "el": "χειροκροτώ (cheirokroto)", "cs": "tleskat", "km": "ទះដៃ (teah dai)"},
    "everywhere": {"es": "en todas partes", "fr": "partout", "de": "überall", "it": "dappertutto", "pt": "em todo lugar", "nl": "overal", "pl": "wszędzie", "ru": "везде (vezde)", "uk": "всюди (vsyudy)", "tr": "her yerde", "ar": "في كل مكان (fi kull makan)", "he": "בכל מקום (bechol makom)", "hi": "हर जगह (har jagah)", "bn": "সব জায়গায় (shob jaygay)", "ur": "ہر جگہ (har jagah)", "fa": "همه جا (hame jâ)", "zh": "到处 (dàochù)", "ja": "どこでも (doko demo)", "ko": "어디든 (eodideun)", "vi": "khắp nơi", "th": "ทุกที่ (thuk thi)", "id": "di mana-mana", "sw": "kila mahali", "el": "παντού (pantou)", "cs": "všude", "km": "គ្រប់ទីកន្លែង (krup ti kanleng)"},
}

# One natural English sentence per term, used by the "examples" panel and by the
# offline Ask-AI fallback so a learner always sees the word in context.
EXAMPLES: dict[str, str] = {
    "hello": "I say hello to my teacher every morning.",
    "friend": "My friend waits for me at the bus stop.",
    "work": "I go to work at eight o'clock.",
    "school": "The children walk to school together.",
    "bank": "I go to the bank to change money.",
    "money": "I keep my money in my bag.",
    "office": "She makes a plan at the office.",
    "store": "We walk to the store to buy bread.",
    "supermarket": "The supermarket is next to the train station.",
    "restaurant": "In the restaurant I ask for the menu, please.",
    "food": "The food at this restaurant is very good.",
    "please": "One ticket, please.",
    "thank you": "Thank you for your help.",
    "ticket": "I need a ticket to the airport.",
    "map": "Can you show me the way on the map?",
    "airport": "At the airport I wait in line.",
    "hotel": "At the hotel I ask for my key.",
    "sandwich": "One sandwich and one cup of tea, please.",
    "tea": "I drink tea in the morning.",
    "bus": "The bus goes all through the town.",
    "car": "Look, a car and a train!",
    "train": "The train is fast, the bus is slow.",
    "wheels": "The wheels on the bus go round and round.",
    "door": "The door opens and shuts.",
    "town": "We ride all through the town.",
    "park": "We go to the park to play.",
    "sun": "See the sun, see the rain.",
    "rain": "In the rain I take my umbrella.",
    "hand": "Hold my hand, do not let go.",
    "up": "Up is where I look.",
    "down": "Down is where I go.",
    "left": "Turn left at the bank.",
    "right": "The store is on the right.",
    "morning": "In the morning I sing my song.",
    "song": "We can all sing this song along.",
    "word": "Every word can take us somewhere new.",
    "near": "The park is near my school.",
    "far": "The airport is very far away.",
    "fast": "The train goes fast.",
    "slow": "Come and learn them slow.",
    "count": "At the bank I count my money.",
    "plan": "At the office I make a plan.",
    "bag": "I pack my bag before the trip.",
    "come": "Come with us to the park.",
    "say": "I can say it in two languages.",
    "know": "I know these words too.",
    "way": "I find the way with my map.",
    "wait": "At the airport I wait in line.",
    "good": "I am good, thank you.",
    "yes": "Yes, me too!",
    "help": "Can you help me, please?",
    "how much": "How much is this ticket?",
    "where": "Where are we going?",
    "wave": "We wave hello from the bus.",
    "low": "She waves high and low.",
    "horn": "Beep beep says the horn.",
    "early": "We leave early in the morning.",
    "sing": "We can all sing along.",
    "soft": "Say it soft, then say it loud.",
    "loud": "Say it loud so everyone hears.",
    "learn": "We can learn them now.",
    "round": "The wheels go round and round.",
    "foot": "Two feet walk the floor.",
    "floor": "My feet walk across the floor.",
    "turn": "Turn around and smile.",
    "smile": "Turn around and smile at your friend.",
    "more": "Then we ask for more.",
    "clap": "I find the way and then I clap.",
    "everywhere": "The bus goes everywhere in the town.",
}

# Longest-first so multi-word entries win over their parts ("thank you").
_TERMS_BY_LENGTH: tuple[str, ...] = tuple(
    sorted(LEXICON, key=lambda t: (-len(t.split()), -len(t)))
)

# Inflected or colloquial surface forms mapped to their lexicon entry, so a
# lyric like "Waving hi waving low" still resolves to real vocabulary.
_ALIASES = {
    "words": "word",
    "friends": "friend",
    "hands": "hand",
    "cars": "car",
    "trains": "train",
    "doors": "door",
    "songs": "song",
    "rules": "word",
    "feet": "foot",
    "cash": "money",
    "fine": "good",
    "hi": "hello",
    "hey": "hello",
    "thanks": "thank you",
    "says": "say",
    "said": "say",
    "saying": "say",
    "waving": "wave",
    "waves": "wave",
    "morn": "morning",
    "singing": "sing",
    "learning": "learn",
    "counting": "count",
    "waiting": "wait",
    "turning": "turn",
    "smiling": "smile",
    "clapping": "clap",
    "helping": "help",
    "coming": "come",
    "knows": "know",
    "shops": "store",
    "shop": "store",
}


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z' ]+", " ", text.lower()).strip()


def terms_in_line(text: str) -> list[str]:
    """Lexicon terms present in a lyric line, in reading order, deduplicated."""
    tokens = [_ALIASES.get(tok, tok) for tok in _normalize(text).split()]
    plain = f" {' '.join(tokens)} "
    found: list[tuple[int, str]] = []
    for term in _TERMS_BY_LENGTH:
        idx = plain.find(f" {term} ")
        if idx >= 0:
            found.append((idx, term))
    found.sort()
    seen: set[str] = set()
    ordered: list[str] = []
    for _, term in found:
        if term not in seen:
            seen.add(term)
            ordered.append(term)
    return ordered


def gloss(term: str, language: str) -> str:
    """Target-language word for a lexicon term ('' when not covered)."""
    row = LEXICON.get(term)
    if not row:
        return ""
    if language == "en":
        return term
    return row.get(language, "")


def vocabulary_for_line(text: str, language: str) -> list[dict[str, str]]:
    """Per-line key vocabulary with target word + English example sentence."""
    rows: list[dict[str, str]] = []
    for term in terms_in_line(text):
        rows.append(
            {
                "en": term,
                "target": gloss(term, language),
                "example_en": EXAMPLES.get(term, ""),
            }
        )
    return rows


def coverage(language: str) -> float:
    """Share of lexicon terms translated for a language (0.0–1.0)."""
    if language == "en":
        return 1.0
    if not LEXICON:
        return 0.0
    have = sum(1 for row in LEXICON.values() if row.get(language))
    return round(have / len(LEXICON), 3)
