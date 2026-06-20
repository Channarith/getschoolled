"""Catalog-content localization for the audio courses + browse screens.

The mobile + web UI chrome is translated via apps/mobile/src/i18n. This
module covers the *catalog content itself*: the strings that come from
the curriculum service - category names, level labels, lesson types,
segment headings, and the templated narration fragments inside each
audio lesson. With this in place, switching the app's locale also
re-titles every course on Home and re-narrates the Introduction / Recap
segments in the player.

Scope:
  - 13 fully-translated locales (en + 12 hand-written): es, fr, de, it,
    pt, ru, ar, hi, zh, ja, ko, vi. Other supported platform languages
    fall back to English cleanly via :func:`localize`.
  - 15 categories.
  - 3 levels (beginner / intermediate / advanced).
  - 3 language-lesson types (phrases / conversation / travel).
  - 8 segment heading templates (Introduction, Recap, Key idea N, ...).
  - 6 narration-prefix templates ("Welcome to ...", "Now you try ...").
  - Per-phrase concept English keys (the phrasebook id list) -> their
    localized heading, falling back to the English label.

For the long-form knowledge bodies (e.g. the 3-bullet "key idea" facts
in :mod:`aoep_shared.audio_courses`), we don't attempt automatic
translation - those are original content and need human translators;
the endpoints expose ``body_locale`` so the client knows when the
narration is in the requested locale vs the original English.
"""

from __future__ import annotations

from typing import Dict, Optional


# Canonical locale list. Keep in sync with apps/mobile/src/i18n/languages.ts
# (the 13 "full" tier locales).
SUPPORTED_LOCALES: tuple[str, ...] = (
    "en", "es", "fr", "de", "it", "pt",
    "ru", "ar", "hi", "zh", "ja", "ko", "vi",
)

DEFAULT_LOCALE = "en"


def normalize_locale(locale: Optional[str]) -> str:
    """Coerce a user-supplied locale string (e.g. ``es-MX``) to a base
    code we recognise; fall back to English on anything unsupported."""
    if not locale:
        return DEFAULT_LOCALE
    base = locale.lower().split("-")[0].split("_")[0]
    return base if base in SUPPORTED_LOCALES else DEFAULT_LOCALE


# --------------------------------------------------------------------------- #
# Category names
# --------------------------------------------------------------------------- #
# Mapping: canonical English -> {locale: localized}. English entries are
# always present; missing entries fall back to English in :func:`localize`.

CATEGORY: Dict[str, Dict[str, str]] = {
    "Languages": {
        "en": "Languages", "es": "Idiomas", "fr": "Langues", "de": "Sprachen",
        "it": "Lingue", "pt": "Idiomas", "ru": "Языки", "ar": "اللغات",
        "hi": "भाषाएँ", "zh": "语言", "ja": "言語", "ko": "언어", "vi": "Ngôn ngữ",
    },
    "History": {
        "en": "History", "es": "Historia", "fr": "Histoire", "de": "Geschichte",
        "it": "Storia", "pt": "História", "ru": "История", "ar": "التاريخ",
        "hi": "इतिहास", "zh": "历史", "ja": "歴史", "ko": "역사", "vi": "Lịch sử",
    },
    "Science & Nature": {
        "en": "Science & Nature", "es": "Ciencia y Naturaleza",
        "fr": "Sciences et Nature", "de": "Wissenschaft & Natur",
        "it": "Scienza e Natura", "pt": "Ciência e Natureza",
        "ru": "Наука и природа", "ar": "العلوم والطبيعة",
        "hi": "विज्ञान और प्रकृति", "zh": "科学与自然", "ja": "科学と自然",
        "ko": "과학과 자연", "vi": "Khoa học & Thiên nhiên",
    },
    "Business & Career": {
        "en": "Business & Career", "es": "Negocios y Carrera",
        "fr": "Affaires et Carrière", "de": "Business & Karriere",
        "it": "Affari e Carriera", "pt": "Negócios e Carreira",
        "ru": "Бизнес и карьера", "ar": "الأعمال والمهنة",
        "hi": "व्यापार और करियर", "zh": "商业与职业", "ja": "ビジネスとキャリア",
        "ko": "비즈니스와 커리어", "vi": "Kinh doanh & Sự nghiệp",
    },
    "Personal Finance": {
        "en": "Personal Finance", "es": "Finanzas personales",
        "fr": "Finances personnelles", "de": "Persönliche Finanzen",
        "it": "Finanza personale", "pt": "Finanças pessoais",
        "ru": "Личные финансы", "ar": "التمويل الشخصي",
        "hi": "व्यक्तिगत वित्त", "zh": "个人理财", "ja": "個人ファイナンス",
        "ko": "개인 재정", "vi": "Tài chính cá nhân",
    },
    "Health & Wellness": {
        "en": "Health & Wellness", "es": "Salud y Bienestar",
        "fr": "Santé et Bien-être", "de": "Gesundheit & Wohlbefinden",
        "it": "Salute e Benessere", "pt": "Saúde e Bem-estar",
        "ru": "Здоровье и благополучие", "ar": "الصحة والعافية",
        "hi": "स्वास्थ्य और कल्याण", "zh": "健康与养生", "ja": "健康とウェルネス",
        "ko": "건강과 웰니스", "vi": "Sức khỏe & Thể chất",
    },
    "Technology": {
        "en": "Technology", "es": "Tecnología", "fr": "Technologie",
        "de": "Technologie", "it": "Tecnologia", "pt": "Tecnologia",
        "ru": "Технологии", "ar": "التكنولوجيا", "hi": "तकनीक",
        "zh": "科技", "ja": "テクノロジー", "ko": "기술", "vi": "Công nghệ",
    },
    "Mindfulness & Philosophy": {
        "en": "Mindfulness & Philosophy", "es": "Atención plena y Filosofía",
        "fr": "Pleine conscience et Philosophie",
        "de": "Achtsamkeit & Philosophie",
        "it": "Mindfulness e Filosofia", "pt": "Mindfulness e Filosofia",
        "ru": "Осознанность и философия", "ar": "اليقظة والفلسفة",
        "hi": "सजगता और दर्शन", "zh": "正念与哲学", "ja": "マインドフルネスと哲学",
        "ko": "마음챙김과 철학", "vi": "Chánh niệm & Triết học",
    },
    "Arts & Culture": {
        "en": "Arts & Culture", "es": "Arte y Cultura",
        "fr": "Arts et Culture", "de": "Kunst & Kultur",
        "it": "Arte e Cultura", "pt": "Arte e Cultura",
        "ru": "Искусство и культура", "ar": "الفنون والثقافة",
        "hi": "कला और संस्कृति", "zh": "艺术与文化", "ja": "芸術と文化",
        "ko": "예술과 문화", "vi": "Nghệ thuật & Văn hóa",
    },
    "Productivity & Study": {
        "en": "Productivity & Study", "es": "Productividad y Estudio",
        "fr": "Productivité et Études", "de": "Produktivität & Lernen",
        "it": "Produttività e Studio", "pt": "Produtividade e Estudo",
        "ru": "Продуктивность и учёба", "ar": "الإنتاجية والدراسة",
        "hi": "उत्पादकता और अध्ययन", "zh": "效率与学习",
        "ja": "生産性と学習", "ko": "생산성과 학습", "vi": "Năng suất & Học tập",
    },
    "True Stories & Biographies": {
        "en": "True Stories & Biographies", "es": "Historias reales y Biografías",
        "fr": "Histoires vraies et Biographies",
        "de": "Wahre Geschichten & Biografien",
        "it": "Storie vere e Biografie", "pt": "Histórias reais e Biografias",
        "ru": "Истории и биографии", "ar": "قصص حقيقية وسير ذاتية",
        "hi": "सच्ची कहानियाँ और जीवनी", "zh": "真实故事与传记",
        "ja": "実話と伝記", "ko": "실화와 전기", "vi": "Câu chuyện thật & Tiểu sử",
    },
    "Geography & World": {
        "en": "Geography & World", "es": "Geografía y Mundo",
        "fr": "Géographie et Monde", "de": "Geografie & Welt",
        "it": "Geografia e Mondo", "pt": "Geografia e Mundo",
        "ru": "География и мир", "ar": "الجغرافيا والعالم",
        "hi": "भूगोल और दुनिया", "zh": "地理与世界",
        "ja": "地理と世界", "ko": "지리와 세계", "vi": "Địa lý & Thế giới",
    },
    "World Cultures": {
        "en": "World Cultures", "es": "Culturas del mundo",
        "fr": "Cultures du monde", "de": "Weltkulturen",
        "it": "Culture del mondo", "pt": "Culturas do mundo",
        "ru": "Мировые культуры", "ar": "ثقافات العالم",
        "hi": "विश्व संस्कृतियाँ", "zh": "世界文化",
        "ja": "世界の文化", "ko": "세계 문화", "vi": "Văn hóa thế giới",
    },
    "Cooking & Food": {
        "en": "Cooking & Food", "es": "Cocina y Comida",
        "fr": "Cuisine et Gastronomie", "de": "Kochen & Essen",
        "it": "Cucina e Cibo", "pt": "Culinária e Comida",
        "ru": "Кулинария и еда", "ar": "الطبخ والطعام",
        "hi": "रसोई और भोजन", "zh": "烹饪与美食",
        "ja": "料理と食", "ko": "요리와 음식", "vi": "Nấu ăn & Ẩm thực",
    },
    "Civics & Law": {
        "en": "Civics & Law", "es": "Cívica y Derecho",
        "fr": "Civisme et Droit", "de": "Bürgerkunde & Recht",
        "it": "Educazione civica e Diritto", "pt": "Civismo e Direito",
        "ru": "Гражданство и право", "ar": "التربية المدنية والقانون",
        "hi": "नागरिक शास्त्र और कानून", "zh": "公民与法律",
        "ja": "公民と法", "ko": "시민과 법", "vi": "Công dân & Pháp luật",
    },
    "Sports & Games": {
        "en": "Sports & Games", "es": "Deportes y Juegos",
        "fr": "Sports et Jeux", "de": "Sport & Spiele",
        "it": "Sport e Giochi", "pt": "Esportes e Jogos",
        "ru": "Спорт и игры", "ar": "الرياضة والألعاب",
        "hi": "खेल और गेम्स", "zh": "运动与游戏",
        "ja": "スポーツとゲーム", "ko": "스포츠와 게임", "vi": "Thể thao & Trò chơi",
    },
}


# --------------------------------------------------------------------------- #
# Levels
# --------------------------------------------------------------------------- #
LEVEL: Dict[str, Dict[str, str]] = {
    "beginner": {
        "en": "beginner", "es": "principiante", "fr": "débutant",
        "de": "Anfänger", "it": "principiante", "pt": "iniciante",
        "ru": "начальный", "ar": "مبتدئ", "hi": "शुरुआती",
        "zh": "入门", "ja": "初級", "ko": "초급", "vi": "Cơ bản",
    },
    "intermediate": {
        "en": "intermediate", "es": "intermedio", "fr": "intermédiaire",
        "de": "Mittelstufe", "it": "intermedio", "pt": "intermediário",
        "ru": "средний", "ar": "متوسط", "hi": "मध्यम",
        "zh": "中级", "ja": "中級", "ko": "중급", "vi": "Trung cấp",
    },
    "advanced": {
        "en": "advanced", "es": "avanzado", "fr": "avancé",
        "de": "Fortgeschritten", "it": "avanzato", "pt": "avançado",
        "ru": "продвинутый", "ar": "متقدم", "hi": "उन्नत",
        "zh": "高级", "ja": "上級", "ko": "고급", "vi": "Nâng cao",
    },
}


# --------------------------------------------------------------------------- #
# Language-lesson types (used in titles like
# "{language}: {lesson_type} (audio)")
# --------------------------------------------------------------------------- #
LESSON_TYPE: Dict[str, Dict[str, str]] = {
    "Essential phrases": {
        "en": "Essential phrases", "es": "Frases esenciales",
        "fr": "Phrases essentielles", "de": "Wichtige Sätze",
        "it": "Frasi essenziali", "pt": "Frases essenciais",
        "ru": "Основные фразы", "ar": "عبارات أساسية",
        "hi": "ज़रूरी वाक्यांश", "zh": "必备短语",
        "ja": "必須フレーズ", "ko": "필수 문장", "vi": "Cụm từ thiết yếu",
    },
    "Everyday conversation": {
        "en": "Everyday conversation", "es": "Conversación cotidiana",
        "fr": "Conversation quotidienne", "de": "Alltagsgespräche",
        "it": "Conversazione quotidiana", "pt": "Conversação do dia a dia",
        "ru": "Повседневная речь", "ar": "محادثة يومية",
        "hi": "रोज़मर्रा की बातचीत", "zh": "日常对话",
        "ja": "日常会話", "ko": "일상 대화", "vi": "Hội thoại hàng ngày",
    },
    "Travel survival": {
        "en": "Travel survival", "es": "Supervivencia de viaje",
        "fr": "Survie en voyage", "de": "Reise-Überleben",
        "it": "Sopravvivenza in viaggio", "pt": "Sobrevivência em viagem",
        "ru": "Выживание в путешествии", "ar": "البقاء في السفر",
        "hi": "यात्रा में काम के वाक्य", "zh": "旅行求生",
        "ja": "旅のサバイバル", "ko": "여행 생존", "vi": "Sống sót khi đi du lịch",
    },
}


# --------------------------------------------------------------------------- #
# Segment headings (those that appear inside the player UI)
# --------------------------------------------------------------------------- #
HEADING: Dict[str, Dict[str, str]] = {
    "Introduction": {
        "en": "Introduction", "es": "Introducción", "fr": "Introduction",
        "de": "Einführung", "it": "Introduzione", "pt": "Introdução",
        "ru": "Введение", "ar": "مقدمة", "hi": "परिचय",
        "zh": "引言", "ja": "はじめに", "ko": "소개", "vi": "Giới thiệu",
    },
    "Recap": {
        "en": "Recap", "es": "Resumen", "fr": "Récapitulatif",
        "de": "Zusammenfassung", "it": "Riepilogo", "pt": "Resumo",
        "ru": "Итог", "ar": "ملخص", "hi": "सारांश",
        "zh": "回顾", "ja": "まとめ", "ko": "정리", "vi": "Tóm tắt",
    },
    "Key idea": {
        "en": "Key idea", "es": "Idea clave", "fr": "Idée clé",
        "de": "Kernidee", "it": "Idea chiave", "pt": "Ideia-chave",
        "ru": "Главная мысль", "ar": "فكرة أساسية", "hi": "मुख्य विचार",
        "zh": "要点", "ja": "重要ポイント", "ko": "핵심 아이디어", "vi": "Ý chính",
    },
    "Why it matters": {
        "en": "Why it matters", "es": "Por qué importa",
        "fr": "Pourquoi c'est important", "de": "Warum es zählt",
        "it": "Perché conta", "pt": "Por que importa",
        "ru": "Почему это важно", "ar": "لماذا هذا مهم",
        "hi": "यह क्यों मायने रखता है", "zh": "为什么重要",
        "ja": "なぜ大切か", "ko": "왜 중요한가", "vi": "Vì sao quan trọng",
    },
    "Core ideas": {
        "en": "Core ideas", "es": "Ideas centrales",
        "fr": "Idées principales", "de": "Kernkonzepte",
        "it": "Idee centrali", "pt": "Ideias centrais",
        "ru": "Основные идеи", "ar": "الأفكار الأساسية",
        "hi": "मुख्य विचार", "zh": "核心思想",
        "ja": "中心となる考え", "ko": "핵심 개념", "vi": "Ý tưởng cốt lõi",
    },
    "Going deeper": {
        "en": "Going deeper", "es": "Profundizando",
        "fr": "Pour aller plus loin", "de": "Tiefer eintauchen",
        "it": "Approfondiamo", "pt": "Aprofundando",
        "ru": "Глубже", "ar": "نتعمق أكثر",
        "hi": "और गहराई में", "zh": "进一步深入",
        "ja": "もっと深く", "ko": "한 걸음 더", "vi": "Đi sâu hơn",
    },
}


# --------------------------------------------------------------------------- #
# Narration template fragments (templated parts of the body text).
# Format strings use named placeholders so translations can reorder them
# naturally per language (e.g. SOV vs SVO word order).
# --------------------------------------------------------------------------- #
NARRATION: Dict[str, Dict[str, str]] = {
    # Language-lesson intro: language + lesson type
    "lang_intro": {
        "en": ("Welcome to {language} - {lesson}. This is a hands-free audio "
               "lesson, so keep your eyes on the road. Just listen, then "
               "repeat each phrase out loud."),
        "es": ("Bienvenido a {language} - {lesson}. Esta es una lección "
               "de audio manos libres, así que mantén los ojos en la "
               "carretera. Solo escucha y repite cada frase en voz alta."),
        "fr": ("Bienvenue à {language} - {lesson}. C'est une leçon audio "
               "mains libres, alors gardez les yeux sur la route. Écoutez, "
               "puis répétez chaque phrase à voix haute."),
        "de": ("Willkommen bei {language} - {lesson}. Das ist eine "
               "freihändige Audio-Lektion - behalte die Straße im Blick. "
               "Hör einfach zu und sprich dann jeden Satz laut nach."),
        "it": ("Benvenuto a {language} - {lesson}. Questa è una lezione "
               "audio a mani libere, tieni gli occhi sulla strada. Ascolta "
               "e poi ripeti ad alta voce ogni frase."),
        "pt": ("Bem-vindo a {language} - {lesson}. Esta é uma aula de "
               "áudio mãos-livres - mantém os olhos na estrada. Ouve e "
               "depois repete cada frase em voz alta."),
        "ru": ("Добро пожаловать в {language} - {lesson}. Это аудио-урок "
               "со свободными руками, не отводите взгляд от дороги. "
               "Слушайте и повторяйте каждую фразу вслух."),
        "ar": ("مرحبًا بك في {language} - {lesson}. هذا درس صوتي بدون "
               "استخدام اليدين، فابقَ ناظرًا إلى الطريق. استمع ثم كرّر كل "
               "عبارة بصوت عالٍ."),
        "hi": ("{language} में आपका स्वागत है - {lesson}. यह एक "
               "हैंड्स-फ़्री ऑडियो पाठ है, तो सड़क पर ध्यान रखें। बस "
               "सुनें और हर वाक्य ज़ोर से दोहराएँ।"),
        "zh": ("欢迎来到{language} - {lesson}。这是一节免提音频课程，请专心看路。"
               "只需聆听，然后大声跟读每一个短语。"),
        "ja": ("{language}の{lesson}へようこそ。ハンズフリーの音声レッスン"
               "ですから、目は道に向けたままで。聞いて、それぞれのフレーズを"
               "声に出して繰り返してください。"),
        "ko": ("{language} - {lesson}에 오신 것을 환영합니다. 핸즈프리 "
               "오디오 수업이니 시선은 도로에 두세요. 듣고 각 문장을 "
               "소리 내어 따라 하세요."),
        "vi": ("Chào mừng đến với {language} - {lesson}. Đây là bài học "
               "âm thanh rảnh tay, hãy giữ mắt trên đường. Cứ nghe rồi "
               "lặp lại to từng câu."),
    },
    # Per-phrase line: "In {language}, '{en}' is {target}."
    "lang_phrase_say": {
        "en": "In {language}, '{en}' is: {target}.",
        "es": "En {language}, '{en}' se dice: {target}.",
        "fr": "En {language}, '{en}' se dit : {target}.",
        "de": "Auf {language} heißt '{en}': {target}.",
        "it": "In {language}, '{en}' si dice: {target}.",
        "pt": "Em {language}, '{en}' diz-se: {target}.",
        "ru": "На {language} «{en}» — это: {target}.",
        "ar": "بـ {language}، '{en}' تُقال: {target}.",
        "hi": "{language} में '{en}' को कहते हैं: {target}.",
        "zh": "在{language}中，「{en}」是：{target}。",
        "ja": "{language}で「{en}」は：{target}。",
        "ko": "{language}에서 '{en}'은(는): {target}.",
        "vi": "Trong {language}, '{en}' là: {target}.",
    },
    # Per-phrase romanization line
    "lang_phrase_roman": {
        "en": " You can say it as: {roman}.",
        "es": " Puedes pronunciarlo como: {roman}.",
        "fr": " Vous pouvez le prononcer : {roman}.",
        "de": " Du kannst es so aussprechen: {roman}.",
        "it": " Puoi pronunciarlo come: {roman}.",
        "pt": " Podes pronunciá-lo: {roman}.",
        "ru": " Произнесите так: {roman}.",
        "ar": " يمكنك نطقها هكذا: {roman}.",
        "hi": " आप इसे ऐसे बोल सकते हैं: {roman}.",
        "zh": " 你可以读作：{roman}。",
        "ja": " このように発音できます：{roman}。",
        "ko": " 이렇게 발음할 수 있어요: {roman}.",
        "vi": " Bạn có thể đọc là: {roman}.",
    },
    # "Now you try - repeat: {target}. ... {target}."
    "lang_phrase_repeat": {
        "en": " Now you try - repeat after me: {target}. ... {target}.",
        "es": " Ahora prueba tú - repite conmigo: {target}. ... {target}.",
        "fr": " À votre tour - répétez après moi : {target}. ... {target}.",
        "de": " Jetzt du - sprich nach: {target}. ... {target}.",
        "it": " Adesso tu - ripeti dopo di me: {target}. ... {target}.",
        "pt": " Agora tu - repete depois de mim: {target}. ... {target}.",
        "ru": " Теперь вы — повторите за мной: {target}. ... {target}.",
        "ar": " الآن دورك — كرّر معي: {target}. ... {target}.",
        "hi": " अब आपकी बारी — मेरे साथ दोहराइए: {target}. ... {target}.",
        "zh": " 现在你试试，跟我读：{target}。……{target}。",
        "ja": " では、あなたの番です — 続けて言ってみて：{target}。……{target}。",
        "ko": " 이제 따라 해보세요 — 저를 따라: {target}. ... {target}.",
        "vi": " Bây giờ tới lượt bạn — lặp lại theo tôi: {target}. ... {target}.",
    },
    # "Great work! Let's review what you learned in {language}: {recap}."
    "lang_recap": {
        "en": ("Great work! Let's review what you learned in {language}: "
               "{recap}. Practice these on your next drive and they'll stick."),
        "es": ("¡Buen trabajo! Repasemos lo que aprendiste en {language}: "
               "{recap}. Practícalas en tu próximo viaje y se te quedarán."),
        "fr": ("Bravo ! Revoyons ce que vous avez appris en {language} : "
               "{recap}. Entraînez-vous lors du prochain trajet et "
               "vous les retiendrez."),
        "de": ("Super gemacht! Wiederholen wir, was du auf {language} "
               "gelernt hast: {recap}. Übe sie auf der nächsten Fahrt - "
               "dann sitzen sie."),
        "it": ("Ottimo lavoro! Ripassiamo cosa hai imparato in {language}: "
               "{recap}. Esercitati al prossimo viaggio e ti resteranno "
               "in mente."),
        "pt": ("Bom trabalho! Vamos rever o que aprendeste em {language}: "
               "{recap}. Pratica na próxima viagem e vão ficar."),
        "ru": ("Отличная работа! Повторим, что вы выучили на {language}: "
               "{recap}. Практикуйте их в следующей поездке — и они "
               "запомнятся."),
        "ar": ("عمل رائع! لنراجع ما تعلمته بـ {language}: {recap}. "
               "تدرّب عليها في رحلتك القادمة وستثبت في ذهنك."),
        "hi": ("बहुत बढ़िया! आइए दोहराते हैं कि आपने {language} में क्या "
               "सीखा: {recap}. अगली ड्राइव में इन्हें दोहराइए, ये ज़रूर "
               "याद रहेंगे।"),
        "zh": ("做得好！我们来回顾你在{language}中学到的内容：{recap}。"
               "下次开车时再练习，就能牢牢记住。"),
        "ja": ("お疲れさまでした！{language}で学んだことを振り返りましょう："
               "{recap}。次のドライブで練習すれば、しっかり身につきます。"),
        "ko": ("잘 하셨어요! {language}에서 배운 내용을 정리해 볼게요: "
               "{recap}. 다음 운전 때 연습하면 확실히 익숙해질 거예요."),
        "vi": ("Tuyệt vời! Cùng ôn lại những gì bạn đã học bằng {language}: "
               "{recap}. Luyện tập trong chuyến đi sau và bạn sẽ nhớ chúng."),
    },
    # Knowledge lesson intro: "Welcome to this audio lesson on {title}..."
    "know_intro": {
        "en": ("Welcome to this audio lesson on {title}. Keep your eyes on "
               "the road - there's nothing to look at. In a few minutes "
               "you'll understand the key ideas, just by listening."),
        "es": ("Bienvenido a esta lección de audio sobre {title}. Mantén "
               "los ojos en la carretera - no hay nada que mirar. En unos "
               "minutos entenderás las ideas clave solo con escuchar."),
        "fr": ("Bienvenue dans cette leçon audio sur {title}. Gardez les "
               "yeux sur la route - rien à regarder. En quelques minutes, "
               "vous comprendrez l'essentiel, simplement en écoutant."),
        "de": ("Willkommen zu dieser Audio-Lektion über {title}. Behalte "
               "die Straße im Blick - hier gibt's nichts zu sehen. In "
               "wenigen Minuten verstehst du die Kerngedanken nur durch "
               "Zuhören."),
        "it": ("Benvenuto a questa lezione audio su {title}. Tieni gli "
               "occhi sulla strada - non c'è nulla da guardare. In pochi "
               "minuti capirai le idee principali, solo ascoltando."),
        "pt": ("Bem-vindo a esta aula de áudio sobre {title}. Mantém os "
               "olhos na estrada - não há nada para ver. Em poucos minutos "
               "entendes as ideias principais só ouvindo."),
        "ru": ("Добро пожаловать на аудио-урок «{title}». Не отводите "
               "взгляд от дороги — смотреть не на что. За несколько "
               "минут вы усвоите ключевые идеи только на слух."),
        "ar": ("مرحبًا بك في درس صوتي عن {title}. ابقَ ناظرًا إلى الطريق "
               "— لا شيء لتنظر إليه. في دقائق ستفهم الأفكار الأساسية "
               "بالاستماع فقط."),
        "hi": ("{title} पर इस ऑडियो पाठ में आपका स्वागत है। सड़क पर ध्यान "
               "रखें — देखने को कुछ नहीं है। कुछ मिनटों में आप मुख्य "
               "विचार सिर्फ़ सुनकर समझ जाएँगे।"),
        "zh": ("欢迎收听关于{title}的音频课。请专心看路 —— 屏幕上没有要看的内容。"
               "几分钟之内，只靠听就能理解核心要点。"),
        "ja": ("{title}についての音声レッスンへようこそ。画面を見る必要は"
               "ありません — 道を見ていてください。数分間、聞くだけで主要な"
               "アイデアが理解できます。"),
        "ko": ("{title}에 대한 오디오 수업에 오신 것을 환영합니다. "
               "도로에 시선을 두세요 — 볼 게 없어요. 몇 분만 들으면 "
               "핵심을 이해할 수 있습니다."),
        "vi": ("Chào mừng đến với bài học âm thanh về {title}. Hãy giữ "
               "mắt trên đường - không có gì để nhìn. Trong vài phút, chỉ "
               "cần nghe là bạn sẽ nắm được những ý chính."),
    },
    # Knowledge lesson recap
    "know_recap": {
        "en": ("Quick recap of {title}: {recap} Nicely done - learning on "
               "the move."),
        "es": ("Resumen rápido de {title}: {recap} Bien hecho - aprendiendo "
               "en movimiento."),
        "fr": ("Bref récapitulatif sur {title} : {recap} Bravo, vous "
               "apprenez en route."),
        "de": ("Kurze Zusammenfassung zu {title}: {recap} Gut gemacht - "
               "Lernen unterwegs."),
        "it": ("Breve riepilogo di {title}: {recap} Ottimo lavoro - imparare "
               "in movimento."),
        "pt": ("Resumo rápido de {title}: {recap} Bom trabalho - aprender "
               "em movimento."),
        "ru": ("Краткий итог по «{title}»: {recap} Отлично — учёба в "
               "движении."),
        "ar": ("ملخص سريع لـ {title}: {recap} أحسنت — التعلم وأنت في الطريق."),
        "hi": ("{title} का त्वरित सारांश: {recap} बढ़िया — चलते-फिरते सीखना।"),
        "zh": ("{title}的快速回顾：{recap} 做得好 —— 在路上也能学习。"),
        "ja": ("{title}の簡単なまとめ：{recap} お見事 — 移動中の学び。"),
        "ko": ("{title}의 빠른 정리: {recap} 잘하셨어요 — 이동 중 학습."),
        "vi": ("Ôn nhanh về {title}: {recap} Tốt lắm — học ngay khi đang "
               "di chuyển."),
    },
}


# --------------------------------------------------------------------------- #
# Generic localize() helper used by audio_courses.py.
# --------------------------------------------------------------------------- #
def localize(table: Dict[str, Dict[str, str]], key: str, locale: str) -> str:
    """Look up ``key`` in ``table`` for the given ``locale``; fall back to
    the ``en`` entry, then to ``key`` itself."""
    row = table.get(key)
    if not row:
        return key
    return row.get(locale) or row.get(DEFAULT_LOCALE) or key


def localize_category(category: str, locale: str) -> str:
    return localize(CATEGORY, category, locale)


def localize_level(level: str, locale: str) -> str:
    return localize(LEVEL, level, locale)


def localize_lesson_type(lesson_type: str, locale: str) -> str:
    return localize(LESSON_TYPE, lesson_type, locale)


def localize_heading(heading: str, locale: str) -> str:
    return localize(HEADING, heading, locale)


def narration(key: str, locale: str, **fmt) -> str:
    tpl = localize(NARRATION, key, locale)
    try:
        return tpl.format(**fmt)
    except (KeyError, IndexError):
        return tpl
