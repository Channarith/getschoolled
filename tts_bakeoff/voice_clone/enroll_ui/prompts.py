"""Scripts the person reads aloud. English is the primary set (about 60 s); the others are drafts for a native-speaker check.

These are deliberately not the bake-off test sentences, so a reference recording never contains the text we later score.
"""
from __future__ import annotations

LANG_NAMES = {"en": "English", "es": "Español", "zh": "中文", "yue": "廣東話", "vi": "Tiếng Việt", "th": "ไทย", "km": "ខ្មែរ"}
DRAFT_LANGS = ("es", "zh", "yue", "vi", "th", "km")

_TEXT = {
    "en": [
        "Good morning, and welcome to today's lesson. We will start with something simple, then build up one step at a time.",
        "A quick brown fox jumps over the lazy dog, and five wizards quietly box a dozen jars of warm honey.",
        "Have you ever wondered why the sky is blue at noon, but turns orange and red when the sun goes down?",
        "Please open your notebook to page forty-seven, and write down three examples of fractions, such as one half, two thirds, and five eighths.",
        "Don't worry if it feels hard at first. Every great scientist, musician, and builder began exactly where you are today.",
        "Zebras, giraffes, and elephants wander across the wide African plains, searching for fresh water before the dry season.",
        "Now take a deep breath, read the question again slowly, and tell me what you think the answer might be.",
        "Wow, that is exactly right! Great job. You should be very proud of yourself.",
    ],
    "es": [
        "Buenos días, y bienvenidos a la lección de hoy. Empezaremos con algo sencillo y avanzaremos paso a paso.",
        "El veloz murciélago hindú comía feliz cardillo y kiwi, mientras la cigüeña tocaba el saxofón detrás del palenque.",
        "¿Alguna vez te has preguntado por qué el cielo es azul al mediodía y se vuelve rojo al atardecer?",
        "Abre tu cuaderno en la página cuarenta y siete y escribe tres ejemplos de fracciones, como un medio, dos tercios y cinco octavos.",
        "No te preocupes si al principio parece difícil. Todos los grandes científicos empezaron exactamente donde tú estás hoy.",
        "¡Qué bien! Esa es la respuesta correcta. Has trabajado muy duro y debes sentirte orgulloso.",
    ],
    "zh": [
        "大家早上好，欢迎来到今天的课程。我们先从简单的内容开始，一步一步往下学。",
        "你有没有想过，为什么中午的天空是蓝色的，而太阳下山的时候却变成了橙色和红色？",
        "请打开你的笔记本，翻到第四十七页，写下三个分数的例子，比如二分之一、三分之二和八分之五。",
        "如果一开始觉得很难，也不用担心。每一位伟大的科学家，都是从你现在的位置出发的。",
        "斑马、长颈鹿和大象在广阔的草原上游荡，在旱季到来之前寻找新鲜的水源。",
        "太棒了，这个答案完全正确！你学得非常认真，应该为自己感到骄傲。",
    ],
    "yue": [  # colloquial written Cantonese (Hong Kong usage), spoken register; line 5 is the six-tone drill (si1 si2 si3 si4 si5 si6)
        "大家早晨，歡迎嚟到今日嘅課堂。我哋先由簡單啲嘅開始，一步一步咁學啦。",
        "你有冇諗過，點解中午嘅天空係藍色，到日落嗰陣又會變成橙色同紅色呢？",
        "請打開你本簿，揭去第四十七頁，寫低三個分數嘅例子，例如二分之一、三分之二，同八分之五。",
        "如果一開始覺得好難，都唔使擔心㗎。每一位偉大嘅科學家，都係由你而家呢個位置開始嘅。",
        "請跟我讀：詩、史、試、時、市、事。呢六個字嘅聲調唔同，意思都唔同噃。",
        "斑馬、長頸鹿同大象喺廣闊嘅草原上面行嚟行去，喺乾季未到之前，搵啲乾淨嘅水飲。",
        "而家深呼吸一下，慢慢再睇多一次條問題，然後話俾我聽，你覺得答案係咩呀？",
        "嘩，答啱喇！好叻呀！你學得好用心，真係應該為自己感到驕傲㗎。",
    ],
    "vi": [
        "Chào buổi sáng, chào mừng các bạn đến với bài học hôm nay. Chúng ta sẽ bắt đầu từ những điều đơn giản, rồi tiến dần từng bước một.",
        "Bạn đã bao giờ tự hỏi tại sao bầu trời có màu xanh vào buổi trưa, nhưng lại chuyển sang màu cam và đỏ khi mặt trời lặn chưa?",
        "Hãy mở vở ra trang bốn mươi bảy và viết ba ví dụ về phân số, chẳng hạn như một phần hai, hai phần ba và năm phần tám.",
        "Đừng lo nếu lúc đầu thấy khó. Mọi nhà khoa học vĩ đại đều từng bắt đầu từ chính nơi bạn đang đứng hôm nay.",
        "Ngựa vằn, hươu cao cổ và voi lang thang trên những đồng cỏ rộng lớn để tìm nước ngọt trước mùa khô.",
        "Tuyệt vời! Đó chính xác là câu trả lời đúng. Bạn đã học rất chăm chỉ và nên tự hào về bản thân.",
    ],
    "th": [
        "สวัสดีตอนเช้า และยินดีต้อนรับสู่บทเรียนวันนี้ เราจะเริ่มจากเรื่องง่าย ๆ แล้วค่อย ๆ ต่อยอดทีละขั้น",
        "คุณเคยสงสัยไหมว่าทำไมท้องฟ้าจึงเป็นสีฟ้าตอนเที่ยง แต่กลับเปลี่ยนเป็นสีส้มและสีแดงตอนพระอาทิตย์ตก",
        "ลองเปิดสมุดไปที่หน้าสี่สิบเจ็ด แล้วเขียนตัวอย่างเศษส่วนสามตัวอย่าง เช่น หนึ่งส่วนสอง สองส่วนสาม และห้าส่วนแปด",
        "ไม่ต้องกังวลถ้าตอนแรกรู้สึกยาก นักวิทยาศาสตร์ผู้ยิ่งใหญ่ทุกคนก็เริ่มต้นจากจุดเดียวกับที่คุณอยู่ในวันนี้",
        "ม้าลาย ยีราฟ และช้างเดินเตร็ดเตร่ไปทั่วทุ่งหญ้ากว้าง เพื่อหาน้ำสะอาดก่อนที่ฤดูแล้งจะมาถึง",
        "เยี่ยมมาก! นั่นคือคำตอบที่ถูกต้องเลย คุณตั้งใจเรียนมาก และควรภูมิใจในตัวเอง",
    ],
    "km": [
        "អរុណសួស្តី ហើយសូមស្វាគមន៍មកកាន់មេរៀនថ្ងៃនេះ។ យើងនឹងចាប់ផ្តើមពីរឿងងាយៗ រួចបន្តម្តងមួយជំហានៗ។",
        "តើអ្នកធ្លាប់ឆ្ងល់ទេថា ហេតុអ្វីបានជាមេឃមានពណ៌ខៀវនៅពេលថ្ងៃត្រង់ ប៉ុន្តែប្តូរទៅជាពណ៌ទឹកក្រូច និងក្រហមនៅពេលថ្ងៃលិច?",
        "សូមបើកសៀវភៅរបស់អ្នកទៅទំព័រសែសិបប្រាំពីរ ហើយសរសេរឧទាហរណ៍ប្រភាគបីឧទាហរណ៍ ដូចជាមួយភាគពីរ ពីរភាគបី និងប្រាំភាគប្រាំបី។",
        "កុំបារម្ភ បើដំបូងមើលទៅពិបាក។ អ្នកវិទ្យាសាស្ត្រដ៏អស្ចារ្យគ្រប់រូប សុទ្ធតែចាប់ផ្តើមពីកន្លែងដែលអ្នកនៅថ្ងៃនេះ។",
        "សេះបង្កង់ ទន្សោងកវែង និងដំរី ដើរចុះឡើងលើវាលស្មៅធំទូលាយ ដើម្បីស្វែងរកទឹកស្អាតមុនរដូវប្រាំង។",
        "អស្ចារ្យណាស់! នោះជាចម្លើយត្រឹមត្រូវ។ អ្នករៀនយ៉ាងខ្នះខ្នែង ហើយគួរមានមោទនភាពចំពោះខ្លួនឯង។",
    ],
}

PROMPT_SETS = {lang: [{"id": f"{lang}-{i + 1}", "text": t} for i, t in enumerate(texts)] for lang, texts in _TEXT.items()}

CONSENT_STATEMENTS = {
    "en": "My name is {name}. I agree that my company may record my voice, make synthetic voice models from it, and use "
          "them commercially, for training, and for narrating courses. I understand that I can withdraw my consent at any time.",
    "yue": "我叫{name}。我同意我嘅公司可以錄低我把聲，用佢製作合成聲音模型，並且用於商業用途、模型訓練同埋課程旁白。"
           "我明白我可以隨時撤回我嘅同意。",
}
CONSENT_STATEMENT = CONSENT_STATEMENTS["en"]


def statement_for(name: str, lang: str = "en") -> str:
    return CONSENT_STATEMENTS[lang].format(name=" ".join(name.split()))
