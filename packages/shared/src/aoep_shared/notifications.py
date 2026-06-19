"""Notification feed generator for the mobile/web inbox.

The mobile app's Notifications screen (and web parity, later) calls
``GET /notifications/feed`` on the curriculum service. The endpoint returns a
chronological list of personalized notification items - new audio classes,
"continue listening" reminders, recommendations, daily streak nudges, etc.

Notifications are deterministic given the inputs (audio catalog, optional
student state) so server-side rendering and client-side caching match. Local
push notifications (delivered by the OS via expo-notifications on the device)
are scheduled by the client from these items - no remote push server is
required for the demo.

Pure/offline + stdlib + pydantic.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from .audio_courses import build_catalog


# UI strings for each notification kind, by locale. English is the source of
# truth; missing keys fall back to English.
_I18N: Dict[str, Dict[str, str]] = {
    "en": {
        "new_class.title": "New audio class: {title}",
        "new_class.body": "{min} min · {category} · {level}. Tap to start in Drive Mode.",
        "continue.title": "Continue: {title}",
        "continue.body": "Pick up where you left off — your spot is saved.",
        "recommended.title": "Picked for you: {title}",
        "recommended.body": "Matches your interest in {interests}.",
        "streak.title": "{days}-day streak! 🔥",
        "streak.body": "Keep the momentum — one short class today extends your streak.",
        "reminder.title": "Your daily class is ready",
        "reminder.body": "A 5-minute audio class is waiting in Drive Mode.",
    },
    "es": {
        "new_class.title": "Nueva clase de audio: {title}",
        "new_class.body": "{min} min · {category} · {level}. Toca para empezar en modo Conducir.",
        "continue.title": "Continúa: {title}",
        "continue.body": "Sigue donde lo dejaste — tu lugar está guardado.",
        "recommended.title": "Para ti: {title}",
        "recommended.body": "Coincide con tu interés en {interests}.",
        "streak.title": "¡Racha de {days} días! 🔥",
        "streak.body": "Mantén el ritmo — una clase corta extiende tu racha.",
        "reminder.title": "Tu clase diaria está lista",
        "reminder.body": "Una clase de audio de 5 minutos te espera en modo Conducir.",
    },
    "fr": {
        "new_class.title": "Nouveau cours audio : {title}",
        "new_class.body": "{min} min · {category} · {level}. Touchez pour démarrer en mode Conduite.",
        "continue.title": "Reprendre : {title}",
        "continue.body": "Reprenez là où vous vous êtes arrêté — votre place est gardée.",
        "recommended.title": "Pour vous : {title}",
        "recommended.body": "Correspond à votre intérêt pour {interests}.",
        "streak.title": "Série de {days} jours ! 🔥",
        "streak.body": "Maintenez le rythme — un cours court suffit pour prolonger la série.",
        "reminder.title": "Votre cours quotidien est prêt",
        "reminder.body": "Un cours audio de 5 minutes vous attend en mode Conduite.",
    },
    "de": {
        "new_class.title": "Neuer Audio-Kurs: {title}",
        "new_class.body": "{min} Min · {category} · {level}. Tippe, um im Fahr-Modus zu starten.",
        "continue.title": "Weiter: {title}",
        "continue.body": "Mach dort weiter, wo du aufgehört hast — dein Platz ist gespeichert.",
        "recommended.title": "Für dich: {title}",
        "recommended.body": "Passt zu deinem Interesse an {interests}.",
        "streak.title": "{days}-Tage-Serie! 🔥",
        "streak.body": "Behalte den Schwung — ein kurzer Kurs verlängert die Serie.",
        "reminder.title": "Dein täglicher Kurs ist bereit",
        "reminder.body": "Ein 5-Minuten-Audio-Kurs wartet im Fahr-Modus.",
    },
    "it": {
        "new_class.title": "Nuovo corso audio: {title}",
        "new_class.body": "{min} min · {category} · {level}. Tocca per iniziare in modalità Guida.",
        "continue.title": "Continua: {title}",
        "continue.body": "Riprendi da dove avevi lasciato.",
        "recommended.title": "Per te: {title}",
        "recommended.body": "Corrisponde al tuo interesse in {interests}.",
        "streak.title": "Serie di {days} giorni! 🔥",
        "streak.body": "Mantieni il ritmo — un corso breve estende la serie.",
        "reminder.title": "Il tuo corso giornaliero è pronto",
        "reminder.body": "Un corso audio di 5 minuti ti aspetta in modalità Guida.",
    },
    "pt": {
        "new_class.title": "Nova aula de áudio: {title}",
        "new_class.body": "{min} min · {category} · {level}. Toca para começar no modo Estrada.",
        "continue.title": "Continua: {title}",
        "continue.body": "Continua de onde paraste.",
        "recommended.title": "Para ti: {title}",
        "recommended.body": "Corresponde ao teu interesse em {interests}.",
        "streak.title": "Sequência de {days} dias! 🔥",
        "streak.body": "Mantém o ritmo — uma aula curta hoje prolonga a sequência.",
        "reminder.title": "A tua aula diária está pronta",
        "reminder.body": "Uma aula de áudio de 5 minutos espera-te no modo Estrada.",
    },
    "ru": {
        "new_class.title": "Новое аудиозанятие: {title}",
        "new_class.body": "{min} мин · {category} · {level}. Нажмите, чтобы запустить «За рулём».",
        "continue.title": "Продолжить: {title}",
        "continue.body": "С того места, где вы остановились.",
        "recommended.title": "Для вас: {title}",
        "recommended.body": "Подходит вашим интересам: {interests}.",
        "streak.title": "Серия {days} дней! 🔥",
        "streak.body": "Не сбивайте темп — короткое занятие сегодня продолжит серию.",
        "reminder.title": "Ваше ежедневное занятие готово",
        "reminder.body": "Пятиминутное аудиозанятие ждёт в режиме «За рулём».",
    },
    "ar": {
        "new_class.title": "درس صوتي جديد: {title}",
        "new_class.body": "{min} دقيقة · {category} · {level}. اضغط للبدء في وضع القيادة.",
        "continue.title": "متابعة: {title}",
        "continue.body": "تابع من حيث توقفت — موضعك محفوظ.",
        "recommended.title": "مختار لك: {title}",
        "recommended.body": "يتطابق مع اهتمامك بـ {interests}.",
        "streak.title": "سلسلة {days} يومًا! 🔥",
        "streak.body": "حافظ على الزخم — درس قصير اليوم يمدّ سلسلتك.",
        "reminder.title": "درسك اليومي جاهز",
        "reminder.body": "درس صوتي مدته 5 دقائق ينتظرك في وضع القيادة.",
    },
    "hi": {
        "new_class.title": "नई ऑडियो क्लास: {title}",
        "new_class.body": "{min} मिनट · {category} · {level}. ड्राइव मोड में शुरू करने के लिए टैप करें।",
        "continue.title": "जारी रखें: {title}",
        "continue.body": "जहाँ छोड़ा था वहीं से शुरू करें — आपका स्थान सहेज लिया गया है।",
        "recommended.title": "आपके लिए: {title}",
        "recommended.body": "{interests} में आपकी रुचि से मेल खाता है।",
        "streak.title": "{days} दिन की स्ट्रिक! 🔥",
        "streak.body": "गति बनाए रखें — एक छोटी सी क्लास आपकी स्ट्रिक बढ़ाएगी।",
        "reminder.title": "आपकी रोज़ की क्लास तैयार है",
        "reminder.body": "ड्राइव मोड में 5 मिनट की ऑडियो क्लास इंतज़ार कर रही है।",
    },
    "zh": {
        "new_class.title": "新音频课程：{title}",
        "new_class.body": "{min} 分钟 · {category} · {level}。点按以在驾驶模式中开始。",
        "continue.title": "继续：{title}",
        "continue.body": "从上次停下的地方继续 —— 进度已保存。",
        "recommended.title": "为你推荐：{title}",
        "recommended.body": "与你对 {interests} 的兴趣相符。",
        "streak.title": "已连续 {days} 天！🔥",
        "streak.body": "保持势头 —— 一节短课就能延续你的连续记录。",
        "reminder.title": "你的每日课程已就绪",
        "reminder.body": "一节 5 分钟的音频课程正在驾驶模式中等你。",
    },
    "ja": {
        "new_class.title": "新しい音声クラス：{title}",
        "new_class.body": "{min} 分 · {category} · {level}。タップでドライブモード開始。",
        "continue.title": "つづき：{title}",
        "continue.body": "前回の続きから — 位置は保存されています。",
        "recommended.title": "おすすめ：{title}",
        "recommended.body": "あなたの関心「{interests}」に合っています。",
        "streak.title": "{days}日連続！🔥",
        "streak.body": "勢いを維持 — 短いクラスで連続が伸ばせます。",
        "reminder.title": "今日のクラスができました",
        "reminder.body": "5分の音声クラスがドライブモードで待っています。",
    },
    "ko": {
        "new_class.title": "새 오디오 수업: {title}",
        "new_class.body": "{min}분 · {category} · {level}. 드라이브 모드에서 시작하려면 누르세요.",
        "continue.title": "이어서: {title}",
        "continue.body": "멈춘 지점부터 이어서 — 위치가 저장되어 있어요.",
        "recommended.title": "맞춤 추천: {title}",
        "recommended.body": "{interests}에 대한 관심과 일치합니다.",
        "streak.title": "{days}일 연속! 🔥",
        "streak.body": "흐름 유지 — 짧은 수업 하나면 연속을 이어갈 수 있어요.",
        "reminder.title": "오늘의 수업이 준비됐어요",
        "reminder.body": "5분짜리 오디오 수업이 드라이브 모드에서 기다리고 있어요.",
    },
    "vi": {
        "new_class.title": "Lớp âm thanh mới: {title}",
        "new_class.body": "{min} phút · {category} · {level}. Chạm để bắt đầu ở chế độ Lái xe.",
        "continue.title": "Tiếp tục: {title}",
        "continue.body": "Tiếp tục từ chỗ dừng — vị trí đã được lưu.",
        "recommended.title": "Dành cho bạn: {title}",
        "recommended.body": "Phù hợp với sở thích của bạn về {interests}.",
        "streak.title": "Chuỗi {days} ngày! 🔥",
        "streak.body": "Duy trì đà — một lớp ngắn hôm nay sẽ kéo dài chuỗi.",
        "reminder.title": "Lớp học hôm nay đã sẵn sàng",
        "reminder.body": "Lớp âm thanh 5 phút đang chờ trong chế độ Lái xe.",
    },
}


SUPPORTED_NOTIFICATION_LOCALES: tuple[str, ...] = tuple(_I18N.keys())


def _tr(locale: str, key: str, **fmt) -> str:
    table = _I18N.get(locale) or _I18N["en"]
    tpl = table.get(key) or _I18N["en"].get(key) or key
    try:
        return tpl.format(**fmt)
    except (KeyError, IndexError):
        return tpl


class NotificationItem(BaseModel):
    id: str
    kind: str  # new_class | continue | recommended | reminder | streak | system
    title: str
    body: str
    course_id: Optional[str] = None
    deep_link: Optional[str] = None
    created_at: str  # ISO-8601 UTC timestamp
    icon: str = "bell"  # bell | sparkle | flame | play | trophy | gift


class NotificationFeed(BaseModel):
    student_id: str = "guest"
    generated_at: str
    unread: int = 0
    items: List[NotificationItem] = Field(default_factory=list)


def _stable_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


def _iso(ts: _dt.datetime) -> str:
    return ts.replace(microsecond=0, tzinfo=_dt.timezone.utc).isoformat()


def build_feed(
    *,
    student_id: str = "guest",
    completed_course_ids: Optional[List[str]] = None,
    in_progress_course_ids: Optional[List[str]] = None,
    interests: Optional[List[str]] = None,
    streak_days: int = 0,
    now: Optional[_dt.datetime] = None,
    limit: int = 30,
    locale: str = "en",
) -> NotificationFeed:
    """Render a personalized notification feed.

    The feed mixes:
      * "new class" entries from the latest audio catalog (top of list);
      * "continue listening" reminders for any course the student has paused;
      * "recommended for you" suggestions matching the student's interests;
      * a "daily reminder" entry (Drive Mode greeting);
      * a "streak" entry when the student has an active streak.
    """
    completed = set(completed_course_ids or [])
    in_progress = list(in_progress_course_ids or [])
    interests_l = [i.lower() for i in (interests or [])]
    base = (now or _dt.datetime.now(_dt.timezone.utc)).replace(microsecond=0)

    items: List[NotificationItem] = []
    catalog = build_catalog()
    fresh = [c for c in catalog if c.id not in completed][:120]

    matched = []
    if interests_l:
        for c in fresh:
            blob = " ".join([c.category.lower(), c.subject.lower(),
                             c.title.lower(), *(t.lower() for t in c.tags)])
            if any(i in blob for i in interests_l):
                matched.append(c)
    pool = (matched or fresh)[:6]
    for offset, c in enumerate(pool[:3]):
        ts = base - _dt.timedelta(minutes=15 * (offset + 1))
        items.append(NotificationItem(
            id=_stable_id("new", student_id, c.id),
            kind="new_class",
            title=_tr(locale, "new_class.title", title=c.title),
            body=_tr(locale, "new_class.body",
                     min=c.duration_min, category=c.category, level=c.level),
            course_id=c.id,
            deep_link=f"aiclassroom://drive/{c.id}",
            created_at=_iso(ts),
            icon="sparkle",
        ))

    by_id = {c.id: c for c in catalog}
    for offset, cid in enumerate(in_progress[:3]):
        c = by_id.get(cid)
        if c is None:
            continue
        ts = base - _dt.timedelta(hours=offset + 1)
        items.append(NotificationItem(
            id=_stable_id("continue", student_id, c.id),
            kind="continue",
            title=_tr(locale, "continue.title", title=c.title),
            body=_tr(locale, "continue.body"),
            course_id=c.id,
            deep_link=f"aiclassroom://drive/{c.id}",
            created_at=_iso(ts),
            icon="play",
        ))

    if matched:
        rec = matched[3:6]
        for offset, c in enumerate(rec):
            ts = base - _dt.timedelta(hours=2 + offset)
            items.append(NotificationItem(
                id=_stable_id("rec", student_id, c.id),
                kind="recommended",
                title=_tr(locale, "recommended.title", title=c.title),
                body=_tr(locale, "recommended.body",
                         interests=", ".join(interests_l[:2])),
                course_id=c.id,
                deep_link=f"aiclassroom://drive/{c.id}",
                created_at=_iso(ts),
                icon="gift",
            ))

    if streak_days > 0:
        items.append(NotificationItem(
            id=_stable_id("streak", student_id, str(streak_days), base.date().isoformat()),
            kind="streak",
            title=_tr(locale, "streak.title", days=streak_days),
            body=_tr(locale, "streak.body"),
            deep_link="aiclassroom://drive",
            created_at=_iso(base - _dt.timedelta(hours=8)),
            icon="flame",
        ))

    items.append(NotificationItem(
        id=_stable_id("daily", student_id, base.date().isoformat()),
        kind="reminder",
        title=_tr(locale, "reminder.title"),
        body=_tr(locale, "reminder.body"),
        deep_link="aiclassroom://drive",
        created_at=_iso(base - _dt.timedelta(hours=10)),
        icon="bell",
    ))

    items.sort(key=lambda i: i.created_at, reverse=True)
    items = items[: max(1, limit)]
    return NotificationFeed(
        student_id=student_id,
        generated_at=_iso(base),
        unread=sum(1 for i in items if i.kind in {"new_class", "continue", "recommended"}),
        items=items,
    )
