"""Page language for the enrollment wizard. To add a language: a UI dict below, a CONSENT_FORM.<code>.txt, a spoken
consent statement in prompts.CONSENT_STATEMENTS, a recording script in prompts._TEXT, and an entry in UI_LANGS.

Only English is a reviewed text. Every other consent text is a DRAFT until a native speaker and counsel have signed it off;
the draft status is shown on the page and stored in the consent manifest.
"""
from __future__ import annotations

from pathlib import Path

FORM_DIR = Path(__file__).resolve().parents[1]
UI_LANGS = {"en": "English", "yue": "廣東話"}
CONSENT_FILES = {"en": "CONSENT_FORM.txt", "yue": "CONSENT_FORM.yue.txt"}
CONSENT_STATUS = {
    "en": "template: counsel review required",
    "yue": "draft translation: needs native speaker + counsel review",
}
DRAFT_CONSENT_LANGS = ("yue",)

UI = {
    "en": {
        "page_title": "Voice enrollment", "tab_wizard": "Enroll a voice", "tab_list": "Enrolled voices", "tab_say": "Say anything",
        "step1": "1 Who", "step2": "2 Consent", "step3": "3 Record", "step4": "4 Done",
        "who_h": "Who is this?", "full_name": "Full name", "name_ph": "e.g. Alice Tran", "role": "Role",
        "role_employee": "Employee", "role_owner": "Owner", "interface_language": "Page language",
        "who_hint": "Only the name is stored, nothing else. Recordings stay on this machine.", "continue": "Continue",
        "consent_h": "Consent", "consent_hint": "Read the whole text. It scrolls.",
        "draft_banner": "Draft translation: needs native speaker + counsel review. Read it fully before agreeing.",
        "agree_commercial_use": "My voice may be used commercially, in any language.",
        "agree_model_training": "My recordings may be used to train and improve voice models.",
        "agree_course_narration": "My voice model may narrate courses and lessons.",
        "agree_may_withdraw": "I understand I can withdraw my consent at any time.",
        "typed_label": "Type your full name as your signature", "mode_voice": "Say it aloud (recorded)", "mode_form": "I already signed a form",
        "read_aloud": "Read this out loud, in your own voice:", "record": "Record", "stop": "Stop", "record_again": "Record again",
        "form_path_label": "Path of the signed form on this machine (pdf, png, jpg, heic, txt)",
        "form_hint": "The file is copied into the voice folder and its hash recorded. The boxes and typed name above are still required.",
        "back": "Back", "submit_consent": "I agree and consent",
        "record_h": "Record your voice", "language": "Language", "draft_note": "These scripts are drafts: a native speaker should check them.",
        "record_tips": "Quiet room, microphone about a hand's width away, natural speed, as if teaching a child. About one minute in total. Use the same device for every line.",
        "enable_mic": "Enable microphone", "mic_on": "microphone is on: speak and watch the bar", "check_voice": "Check my voice",
        "line_n": "Line {i} of {n}", "re_record": "Re-record", "recording": "recording...", "saved": "saved", "saved_s": "{s} s saved",
        "uploading": "{s} s, uploading...", "n_recorded": "{n} of {total} lines recorded",
        "done_h": "Done", "another": "Enroll another person", "see_list": "Enrolled voices",
        "done_msg": "{name} is enrolled: {seconds} s of speech, {snr} dB signal-to-noise. You can now test the voice under Enrolled voices.",
        "err_name": "Enter the person's full name.", "err_statement": "Record the spoken statement first.",
        "err_form": "Enter the path of the signed form.", "not_accepted": "Not accepted: {error} Re-record the lines that had warnings.",
        "check_h": "Pronunciation check", "check_running": "Checking pronunciation...", "check_unavailable": "No speech recognizer is installed on this machine, so the pronunciation check was skipped. Enrollment is not affected.",
        "check_warn": "{n} line(s) may not match the script. This is a warning only: re-record them if they were misread.",
        "check_ok": "All lines match the script.", "line_pass": "match", "line_warn": "check",
    },
    "yue": {
        "page_title": "聲音登記", "tab_wizard": "登記聲音", "tab_list": "已登記嘅聲音", "tab_say": "講任何嘢",
        "step1": "1 邊位", "step2": "2 同意", "step3": "3 錄音", "step4": "4 完成",
        "who_h": "邊位呀？", "full_name": "全名", "name_ph": "例如：陳大文", "role": "身份",
        "role_employee": "僱員", "role_owner": "擁有人", "interface_language": "頁面語言",
        "who_hint": "只會儲存姓名，冇其他資料。錄音只會留喺呢部電腦。", "continue": "繼續",
        "consent_h": "同意", "consent_hint": "請睇晒成份文字，可以向下捲動。",
        "draft_banner": "草稿譯本，須由母語人士同律師覆核。同意之前請睇清楚。",
        "agree_commercial_use": "我把聲可以用於商業用途，可以講任何語言。",
        "agree_model_training": "我嘅錄音可以用嚟訓練同改進聲音模型。",
        "agree_course_narration": "我嘅聲音模型可以為課程同課堂旁白。",
        "agree_may_withdraw": "我明白我可以隨時撤回我嘅同意。",
        "typed_label": "請輸入你嘅全名作為簽名", "mode_voice": "讀出嚟（會錄低）", "mode_form": "我已經簽咗同意書",
        "read_aloud": "請用你自己把聲讀出下面呢段說話：", "record": "錄音", "stop": "停止", "record_again": "重新錄音",
        "form_path_label": "已簽同意書喺呢部電腦嘅路徑（pdf、png、jpg、heic、txt）",
        "form_hint": "檔案會複製到聲音資料夾，並且記低佢嘅雜湊值。上面嘅剔選格同簽名仍然要填。",
        "back": "返回", "submit_consent": "我同意",
        "record_h": "錄低你把聲", "language": "語言", "draft_note": "呢啲稿係草稿，請母語人士睇一睇。",
        "record_tips": "喺安靜嘅房間，咪高風離口大約一個手掌，用自然嘅速度，好似教細路咁讀。一共大約一分鐘。每一句都用同一部機。",
        "enable_mic": "開啟咪高風", "mic_on": "咪高風已開啟：講嘢啦，睇住條格", "check_voice": "檢查我把聲",
        "line_n": "第 {i} 句，共 {n} 句", "re_record": "重新錄", "recording": "錄緊音...", "saved": "已儲存", "saved_s": "已儲存 {s} 秒",
        "uploading": "{s} 秒，上載緊...", "n_recorded": "已錄 {n} / {total} 句",
        "done_h": "完成", "another": "登記另一位", "see_list": "已登記嘅聲音",
        "done_msg": "{name} 已登記：{seconds} 秒語音，信噪比 {snr} dB。你而家可以喺「已登記嘅聲音」試用呢把聲。",
        "err_name": "請輸入全名。", "err_statement": "請先錄低讀出嚟嘅同意聲明。",
        "err_form": "請輸入已簽同意書嘅路徑。", "not_accepted": "未接受：{error} 請重新錄有警告嘅句子。",
        "check_h": "發音檢查", "check_running": "檢查緊發音...", "check_unavailable": "呢部電腦冇安裝語音識別，所以跳過咗發音檢查，唔影響登記。",
        "check_warn": "有 {n} 句可能同稿唔夾。呢個只係提示：如果讀錯咗，請重新錄。",
        "check_ok": "所有句子都同稿夾。", "line_pass": "夾", "line_warn": "請檢查",
    },
}


def consent_path(lang: str) -> Path:
    return FORM_DIR / CONSENT_FILES[lang]
