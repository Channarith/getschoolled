"use client";

import { useEffect, useState } from "react";

import { useT } from "./i18n";

// Public labels for the class experience. These stand in for
// "AI-instructed learning" so the product sounds like practice with a
// teacher. One phrase is chosen per browser session.

export const LEARNING_PHRASES: Record<string, readonly string[]> = {
  en: [
    "Guided practice",
    "Live lessons",
    "Coached learning",
    "Building intelligence with tech",
    "Video and audio assistive learning",
    "Teacher-led practice",
    "Understanding how you learn",
    "Your private 24/7 tutor",
    "Live lessons available — book your teacher",
    "Practicing through and through",
  ],
  es: [
    "Práctica guiada",
    "Clases en vivo",
    "Aprendizaje acompañado",
    "Construir inteligencia con tecnología",
    "Aprendizaje con apoyo de video y audio",
    "Práctica dirigida por un docente",
    "Entender cómo aprendes",
    "Tu tutor privado, 24/7",
    "Clases en vivo disponibles — reserva a tu docente",
    "Practicar de principio a fin",
  ],
  fr: [
    "Pratique guidée",
    "Cours en direct",
    "Apprentissage accompagné",
    "Développer l'intelligence avec la technologie",
    "Apprentissage assisté par la vidéo et l'audio",
    "Pratique menée par un enseignant",
    "Comprendre comment vous apprenez",
    "Votre tuteur privé, 24 h/24",
    "Cours en direct disponibles — réservez votre enseignant",
    "Pratiquer encore et encore",
  ],
  de: [
    "Geführtes Üben",
    "Live-Unterricht",
    "Begleitetes Lernen",
    "Intelligenz mit Technik aufbauen",
    "Lernen mit Video- und Audiohilfe",
    "Üben mit Lehrkraft",
    "Verstehen, wie du lernst",
    "Dein privater Tutor, rund um die Uhr",
    "Live-Unterricht verfügbar — buche deine Lehrkraft",
    "Üben, bis es sitzt",
  ],
  it: [
    "Pratica guidata",
    "Lezioni dal vivo",
    "Apprendimento accompagnato",
    "Costruire intelligenza con la tecnologia",
    "Apprendimento assistito da video e audio",
    "Pratica guidata dall'insegnante",
    "Capire come impari",
    "Il tuo tutor privato, 24 ore su 24",
    "Lezioni dal vivo disponibili — prenota il tuo insegnante",
    "Esercitarsi fino in fondo",
  ],
  pt: [
    "Prática guiada",
    "Aulas ao vivo",
    "Aprendizagem acompanhada",
    "Construir inteligência com tecnologia",
    "Aprendizagem assistida por vídeo e áudio",
    "Prática conduzida pelo professor",
    "Entender como você aprende",
    "Seu tutor particular, 24 horas",
    "Aulas ao vivo disponíveis — reserve seu professor",
    "Praticar de ponta a ponta",
  ],
  ru: [
    "Практика с наставником",
    "Живые уроки",
    "Обучение с сопровождением",
    "Развитие мышления с помощью технологий",
    "Обучение с видео и аудио",
    "Практика с учителем",
    "Понять, как вы учитесь",
    "Ваш личный репетитор, круглосуточно",
    "Живые уроки доступны — запишитесь к учителю",
    "Практика до уверенного результата",
  ],
  ar: [
    "تدريب موجّه",
    "دروس مباشرة",
    "تعلّم بمرافقة",
    "بناء الذكاء مع التقنية",
    "تعلّم بمساعدة الفيديو والصوت",
    "تدريب بقيادة المعلّم",
    "فهم طريقة تعلّمك",
    "معلّمك الخاص على مدار الساعة",
    "دروس مباشرة متاحة — احجز معلّمك",
    "التمرين حتى الإتقان",
  ],
  hi: [
    "निर्देशित अभ्यास",
    "लाइव पाठ",
    "साथ में सीखना",
    "तकनीक के साथ समझ बनाना",
    "वीडियो और ऑडियो की सहायता से सीखना",
    "शिक्षक के साथ अभ्यास",
    "समझना कि आप कैसे सीखते हैं",
    "आपका निजी शिक्षक, दिन-रात",
    "लाइव पाठ उपलब्ध हैं — अपने शिक्षक को बुक करें",
    "बार-बार अभ्यास",
  ],
  zh: [
    "引导练习",
    "直播课堂",
    "陪伴式学习",
    "用科技建立理解",
    "视频与音频辅助学习",
    "教师带领的练习",
    "了解你如何学习",
    "你的私人全天候导师",
    "直播课已开放 — 预约你的老师",
    "反复练到会",
  ],
  yue: [
    "引導練習",
    "直播課堂",
    "有人陪住學",
    "用科技建立理解",
    "影片同聲音輔助學習",
    "老師帶領嘅練習",
    "了解你點樣學",
    "你嘅私人全天候導師",
    "直播課已開放 — 預約你嘅老師",
    "練到識為止",
  ],
  ja: [
    "ガイド付き練習",
    "ライブ授業",
    "伴走する学び",
    "技術で理解を育てる",
    "映像と音声で支える学び",
    "先生と進める練習",
    "自分の学び方を知る",
    "いつでも頼れる個人チューター",
    "ライブ授業を予約できます",
    "くり返し練習する",
  ],
  ko: [
    "안내된 연습",
    "라이브 수업",
    "함께하는 학습",
    "기술로 이해를 키우기",
    "영상과 음성으로 돕는 학습",
    "선생님과 하는 연습",
    "내가 배우는 방식을 이해하기",
    "하루 종일 함께하는 개인 튜터",
    "라이브 수업 예약하기",
    "익숙해질 때까지 연습",
  ],
  vi: [
    "Luyện tập có hướng dẫn",
    "Buổi học trực tiếp",
    "Học cùng người đồng hành",
    "Xây dựng sự hiểu biết với công nghệ",
    "Học với hỗ trợ video và âm thanh",
    "Luyện tập cùng giáo viên",
    "Hiểu cách bạn học",
    "Gia sư riêng của bạn, mọi lúc",
    "Có buổi học trực tiếp — đặt giáo viên",
    "Luyện đi luyện lại cho chắc",
  ],
  km: [
    "ការអនុវត្តមានការណែនាំ",
    "មេរៀនផ្ទាល់",
    "ការរៀនមានគ្រូដើរជាមួយ",
    "បង្កើតការយល់ដឹងជាមួយបច្ចេកវិទ្យា",
    "ការរៀនដោយមានវីដេអូ និងសំឡេងជួយ",
    "ការអនុវត្តដឹកនាំដោយគ្រូ",
    "ស្វែងយល់ពីរបៀបដែលអ្នករៀន",
    "គ្រូឯកជនរបស់អ្នក គ្រប់ពេល",
    "មានមេរៀនផ្ទាល់ — កក់គ្រូរបស់អ្នក",
    "ហាត់ហើយហាត់ទៀត",
  ],
};

const HINTS: Record<string, string> = {
  en: "See how learning works on the Transparency page.",
  es: "Mira cómo funciona el aprendizaje en la página de Transparencia.",
  fr: "Voyez comment l'apprentissage fonctionne sur la page Transparence.",
  de: "Auf der Seite Transparenz steht, wie das Lernen funktioniert.",
  it: "Scopri come funziona l'apprendimento nella pagina Trasparenza.",
  pt: "Veja como a aprendizagem funciona na página de Transparência.",
  ru: "Как устроено обучение — на странице «Прозрачность».",
  ar: "اطّلع على طريقة التعلّم في صفحة الشفافية.",
  hi: "सीखना कैसे काम करता है, यह पारदर्शिता पेज पर देखें।",
  zh: "学习方式说明在透明度页面。",
  yue: "學習方式喺透明度頁面。",
  ja: "学び方の説明は透明性のページにあります。",
  ko: "학습이 어떻게 이루어지는지는 투명성 페이지에서 볼 수 있습니다.",
  vi: "Xem cách học hoạt động ở trang Minh bạch.",
  km: "មើលរបៀបរៀននៅទំព័រតម្លាភាព។",
};

const SESSION_KEY = "salareen.learnPhrase.v1";
let memoryIndex: number | null = null;

export function phrasesFor(locale: string): readonly string[] {
  return LEARNING_PHRASES[locale] ?? LEARNING_PHRASES.en;
}

export function learningHint(locale: string): string {
  return HINTS[locale] ?? HINTS.en;
}

export function readSessionPhraseIndex(count: number): number {
  if (typeof window === "undefined" || count <= 0) return 0;
  if (memoryIndex != null && memoryIndex >= 0 && memoryIndex < count) return memoryIndex;
  try {
    const raw = window.sessionStorage.getItem(SESSION_KEY);
    const stored = raw == null ? Number.NaN : Number(raw);
    if (Number.isInteger(stored) && stored >= 0 && stored < count) {
      memoryIndex = stored;
      return stored;
    }
    const next = Math.floor(Math.random() * count);
    memoryIndex = next;
    window.sessionStorage.setItem(SESSION_KEY, String(next));
    return next;
  } catch {
    const next = Math.floor(Math.random() * count);
    memoryIndex = next;
    return next;
  }
}

export function useLearningPhrase(): string {
  const { locale } = useT();
  const phrases = phrasesFor(locale);
  const [index, setIndex] = useState(0);
  useEffect(() => {
    setIndex(readSessionPhraseIndex(phrases.length));
  }, [locale, phrases.length]);
  return phrases[index] ?? phrases[0];
}
