"""Simplified Chinese and Khmer translations for the YouTube lesson verses.

Kept apart from ``curated_embeds.py`` so the Unicode packs stay readable, then
merged into the same tier-1 lookup. Every verse line plus every teaching prompt
and prepared answer of the three pause-and-ask lessons is here, so a learner who
picks Khmer or Chinese reads (and hears) the video in that language offline —
without an LLM key.

Quoted English inside a prompt stays English on purpose: the learner is being
asked about that exact English phrase.

Khmer is machine-authored and pending native review (same bar as
``curated_zh_km.py``); Chinese is Simplified.
"""

from __future__ import annotations

CURATED_EMBEDS_ZH_KM: dict[str, dict[str, str]] = {
    # ---- Legend of Cambodia: Neang Neak ----------------------------------
    "Long ago a foreign prince sailed across the sea to a new land.": {
        "zh": "很久以前，一位外国王子乘船横渡大海，来到一片新的土地。",
        "km": "យូរណាស់មកហើយ ព្រះអង្គម្ចាស់បរទេសមួយអង្គបានធ្វើដំណើរតាមនាវាឆ្លងសមុទ្រ មកដល់ទឹកដីថ្មីមួយ។",
    },
    "What does 'sailed across the sea' mean?": {
        "zh": "'sailed across the sea' 是什么意思？",
        "km": "'sailed across the sea' មានន័យដូចម្តេច?",
    },
    "'Sailed across the sea' means he travelled by boat over the ocean to get somewhere.": {
        "zh": "'Sailed across the sea' 意思是他乘船横渡海洋，去到某个地方。",
        "km": "'Sailed across the sea' មានន័យថា គាត់បានធ្វើដំណើរតាមទូកឆ្លងមហាសមុទ្រ ដើម្បីទៅដល់កន្លែងណាមួយ។",
    },
    "Why is 'Long ago' at the start of the sentence?": {
        "zh": "为什么 'Long ago' 放在句子开头？",
        "km": "ហេតុអ្វី 'Long ago' ស្ថិតនៅដើមប្រយោគ?",
    },
    "'Long ago' is a time phrase that sets a fairy-tale past. English often puts time first: Long ago + subject + verb.": {
        "zh": "'Long ago' 是时间短语，为故事设定久远的过去。英语常把时间放在最前面：Long ago + 主语 + 动词。",
        "km": "'Long ago' គឺជាឃ្លាពេលវេលា ដែលកំណត់អតីតកាលបែបរឿងនិទាន។ ភាសាអង់គ្លេសច្រើនដាក់ពេលវេលានៅដំបូង៖ Long ago + ប្រធាន + កិរិយាសព្ទ។",
    },
    "He met a dragon princess who lived in the kingdom by the water.": {
        "zh": "他遇见了一位住在水边王国里的龙公主。",
        "km": "គាត់បានជួបព្រះនាងនាគ ដែលរស់នៅក្នុងអាណាចក្រនៅមាត់ទឹក។",
    },
    "What is a 'dragon princess'?": {
        "zh": "'dragon princess' 是什么？",
        "km": "'dragon princess' គឺជាអ្វី?",
    },
    "A princess who is also a dragon (or from a dragon family) — a magical royal woman in the legend.": {
        "zh": "一位同时是龙（或出自龙族）的公主——传说中拥有魔力的王室女子。",
        "km": "ព្រះនាងដែលជានាគផង (ឬមកពីត្រកូលនាគ) — ស្ត្រីរាជវង្សដែលមានវេទមន្តក្នុងរឿងព្រេង។",
    },
    "What does the relative clause 'who lived in the kingdom by the water' do?": {
        "zh": "关系从句 'who lived in the kingdom by the water' 起什么作用？",
        "km": "ឃ្លាសម្ព័ន្ធ 'who lived in the kingdom by the water' មានតួនាទីអ្វី?",
    },
    "It describes the princess. 'Who' refers to her; the clause tells us where she lived.": {
        "zh": "它修饰这位公主。'Who' 指的是她；这个从句告诉我们她住在哪里。",
        "km": "វាពណ៌នាអំពីព្រះនាង។ 'Who' សំដៅលើនាង ហើយឃ្លានេះប្រាប់យើងថានាងរស់នៅទីណា។",
    },
    "They married, and the princess cut off her dragon tail to walk on land.": {
        "zh": "他们结婚了，公主割去自己的龙尾，好在陆地上行走。",
        "km": "ពួកគេបានរៀបការ ហើយព្រះនាងបានកាត់កន្ទុយនាគរបស់នាងចេញ ដើម្បីដើរលើដីគោក។",
    },
    "What does the past tense pair 'married' and 'cut off' show?": {
        "zh": "过去时的一对动词 'married' 和 'cut off' 表示什么？",
        "km": "គូកិរិយាសព្ទអតីតកាល 'married' និង 'cut off' បង្ហាញអ្វី?",
    },
    "Both verbs are simple past: completed actions in the story. English myths usually stay in the past throughout.": {
        "zh": "两个动词都是一般过去时：故事中已完成的动作。英语神话通常全篇都用过去时。",
        "km": "កិរិយាសព្ទទាំងពីរជាអតីតកាលសាមញ្ញ៖ អំពើដែលបានបញ្ចប់ក្នុងរឿង។ រឿងព្រេងអង់គ្លេសច្រើនរក្សាអតីតកាលពេញមួយរឿង។",
    },
    "What does 'cut off' mean here?": {
        "zh": "这里的 'cut off' 是什么意思？",
        "km": "'cut off' នៅទីនេះមានន័យដូចម្តេច?",
    },
    "'Cut off' means she removed her tail — a dramatic change so she could live like a human on land.": {
        "zh": "'Cut off' 意思是她去掉了自己的尾巴——一个重大的改变，让她能像人一样在陆地上生活。",
        "km": "'Cut off' មានន័យថានាងបានយកកន្ទុយចេញ — ការផ្លាស់ប្តូរធំមួយ ដើម្បីឱ្យនាងអាចរស់នៅដូចមនុស្សលើដីគោក។",
    },
    "Their children became the first people of Cambodia.": {
        "zh": "他们的孩子成为柬埔寨最早的人民。",
        "km": "កូនរបស់ពួកគេបានក្លាយជាប្រជាជនដំបូងបង្អស់នៃប្រទេសកម្ពុជា។",
    },
    "According to the legend, where do Cambodian people come from?": {
        "zh": "根据传说，柬埔寨人来自何处？",
        "km": "តាមរឿងព្រេង ប្រជាជនកម្ពុជាមកពីណា?",
    },
    "From the children of the foreign prince and the dragon princess — that is the founding story of the land.": {
        "zh": "来自那位外国王子与龙公主的孩子——这就是这片土地的立国传说。",
        "km": "មកពីកូនរបស់ព្រះអង្គម្ចាស់បរទេស និងព្រះនាងនាគ — នោះជារឿងកកើតនៃទឹកដីនេះ។",
    },
    "Why use 'became' instead of 'become'?": {
        "zh": "为什么用 'became' 而不用 'become'？",
        "km": "ហេតុអ្វីប្រើ 'became' ជំនួស 'become'?",
    },
    "'Became' is the past of 'become'. The legend is finished history, so English uses the past form.": {
        "zh": "'Became' 是 'become' 的过去式。传说属于已完成的历史，所以英语用过去式。",
        "km": "'Became' គឺជាទម្រង់អតីតកាលនៃ 'become'។ រឿងព្រេងជាប្រវត្តិដែលបានបញ្ចប់ ដូច្នេះភាសាអង់គ្លេសប្រើទម្រង់អតីតកាល។",
    },
    "Even today, Khmer wedding customs remember the dragon princess.": {
        "zh": "直到今天，高棉的婚礼习俗仍然纪念这位龙公主。",
        "km": "ទោះបីសព្វថ្ងៃនេះ ទំនៀមទម្លាប់មង្គលការខ្មែរនៅចងចាំព្រះនាងនាគ។",
    },
    "What are 'wedding customs'?": {
        "zh": "'wedding customs' 是什么？",
        "km": "'wedding customs' គឺជាអ្វី?",
    },
    "The traditional things people do at a wedding — clothes, music, steps and symbols that families keep.": {
        "zh": "人们在婚礼上遵循的传统——衣着、音乐、仪式步骤和家族保留的象征。",
        "km": "អ្វីៗបែបប្រពៃណីដែលមនុស្សធ្វើនៅពិធីមង្គលការ — សម្លៀកបំពាក់ ភ្លេង ជំហានពិធី និងនិមិត្តរូបដែលក្រុមគ្រួសាររក្សាទុក។",
    },
    "What does 'Even today' contrast with?": {
        "zh": "'Even today' 与什么形成对比？",
        "km": "'Even today' ផ្ទុយនឹងអ្វី?",
    },
    "It contrasts the ancient legend with the present: the story still shapes modern weddings.": {
        "zh": "它把古老的传说与现在作对比：这个故事仍然影响着今天的婚礼。",
        "km": "វាប្រៀបធៀបរឿងព្រេងបុរាណនឹងបច្ចុប្បន្ន៖ រឿងនេះនៅតែមានឥទ្ធិពលលើមង្គលការសព្វថ្ងៃ។",
    },
    # ---- Legend of Laos: Sang Sinxay --------------------------------------
    "Sang Sinxay was born with special powers and a brave heart.": {
        "zh": "桑辛赛生来就拥有特殊的力量和勇敢的心。",
        "km": "សាងសិនស័យបានកើតមកជាមួយអំណាចពិសេស និងដួងចិត្តដ៏អង់អាច។",
    },
    "What does 'a brave heart' mean?": {
        "zh": "'a brave heart' 是什么意思？",
        "km": "'a brave heart' មានន័យដូចម្តេច?",
    },
    "It means he is courageous — not afraid to help others even when it is hard.": {
        "zh": "意思是他很勇敢——即使困难，也不怕去帮助别人。",
        "km": "មានន័យថាគាត់មានភាពក្លាហាន — មិនខ្លាចជួយអ្នកដទៃ ទោះបីជាពិបាកក៏ដោយ។",
    },
    "Why is 'was born' passive?": {
        "zh": "为什么 'was born' 是被动语态？",
        "km": "ហេតុអ្វី 'was born' ជាទម្រង់អកម្ម?",
    },
    "'Was born' is a fixed past-passive for birth. We say someone was born, not 'borned'.": {
        "zh": "'Was born' 是表示出生的固定过去被动形式。我们说 someone was born，而不是 'borned'。",
        "km": "'Was born' ជាទម្រង់អកម្មអតីតកាលថេរសម្រាប់ការកើត។ យើងនិយាយថា someone was born មិនមែន 'borned' ទេ។",
    },
    "An ogre stole his aunt, so Sinxay set out on a long journey.": {
        "zh": "一个食人魔抢走了他的姑姑，于是辛赛踏上了漫长的旅程。",
        "km": "យក្សមួយបានលួចយកមីងរបស់គាត់ ដូច្នេះសិនស័យបានចេញដំណើរដ៏វែងឆ្ងាយ។",
    },
    "What does 'set out on a journey' mean?": {
        "zh": "'set out on a journey' 是什么意思？",
        "km": "'set out on a journey' មានន័យដូចម្តេច?",
    },
    "It means he started travelling with a clear purpose — here, to find his aunt.": {
        "zh": "意思是他带着明确的目的开始旅行——这里是为了找到他的姑姑。",
        "km": "មានន័យថាគាត់បានចាប់ផ្តើមធ្វើដំណើរដោយមានគោលបំណងច្បាស់លាស់ — នៅទីនេះ គឺដើម្បីរកមីងរបស់គាត់។",
    },
    "What does 'so' connect in this sentence?": {
        "zh": "在这个句子里 'so' 连接什么？",
        "km": "នៅក្នុងប្រយោគនេះ 'so' ភ្ជាប់អ្វី?",
    },
    "'So' shows result: the theft caused the journey. Cause first, result after 'so'.": {
        "zh": "'So' 表示结果：抢走姑姑导致了这段旅程。原因在前，结果在 'so' 之后。",
        "km": "'So' បង្ហាញលទ្ធផល៖ ការលួចបានធ្វើឱ្យមានដំណើរនេះ។ មូលហេតុនៅមុន លទ្ធផលនៅក្រោយ 'so'។",
    },
    "He fought many dangers and never gave up on his family.": {
        "zh": "他与许多危险搏斗，从未放弃自己的家人。",
        "km": "គាត់បានប្រយុទ្ធនឹងគ្រោះថ្នាក់ជាច្រើន ហើយមិនដែលបោះបង់ក្រុមគ្រួសាររបស់គាត់ឡើយ។",
    },
    "What does 'never gave up' mean?": {
        "zh": "'never gave up' 是什么意思？",
        "km": "'never gave up' មានន័យដូចម្តេច?",
    },
    "He kept trying. 'Give up' means stop trying; 'never gave up' means he continued.": {
        "zh": "他一直努力。'Give up' 意思是停止努力；'never gave up' 意思是他继续下去。",
        "km": "គាត់បានព្យាយាមជាបន្ត។ 'Give up' មានន័យថាឈប់ព្យាយាម ខណៈ 'never gave up' មានន័យថាគាត់បន្តទៅមុខ។",
    },
    "Are 'fought' and 'gave' regular past verbs?": {
        "zh": "'fought' 和 'gave' 是规则过去式动词吗？",
        "km": "តើ 'fought' និង 'gave' ជាកិរិយាសព្ទអតីតកាលទៀងទាត់ឬទេ?",
    },
    "No — they are irregular. Fight → fought, give → gave. Learners must memorise them.": {
        "zh": "不是——它们是不规则动词。Fight → fought，give → gave。学习者必须记住它们。",
        "km": "មិនទេ — ពួកវាមិនទៀងទាត់។ Fight → fought, give → gave។ អ្នកសិក្សាត្រូវចងចាំពួកវា។",
    },
    "At last he rescued his aunt and returned home as a hero.": {
        "zh": "最后他救出了姑姑，作为英雄回到家乡。",
        "km": "ចុងក្រោយគាត់បានសង្គ្រោះមីងរបស់គាត់ ហើយត្រឡប់មកផ្ទះវិញជាវីរបុរស។",
    },
    "How does the epic end for Sinxay?": {
        "zh": "这部史诗中辛赛的结局如何？",
        "km": "រឿងវីរភាពនេះបញ្ចប់យ៉ាងណាសម្រាប់សិនស័យ?",
    },
    "He saves his aunt and goes home celebrated as a hero — the classic rescue ending.": {
        "zh": "他救出姑姑，回到家中被当作英雄庆祝——经典的营救式结局。",
        "km": "គាត់សង្គ្រោះមីងរបស់គាត់ ហើយត្រឡប់ទៅផ្ទះដោយត្រូវគេសាទរជាវីរបុរស — ការបញ្ចប់បែបសង្គ្រោះបុរាណ។",
    },
    "What does 'at last' signal?": {
        "zh": "'at last' 表示什么？",
        "km": "'at last' បង្ហាញអ្វី?",
    },
    "It signals the long wait is over: after many struggles, the success finally arrives.": {
        "zh": "它表示漫长的等待结束了：经历许多挣扎之后，成功终于到来。",
        "km": "វាបង្ហាញថាការរង់ចាំយូរបានបញ្ចប់៖ បន្ទាប់ពីការតស៊ូជាច្រើន ជោគជ័យមកដល់ជាទីបំផុត។",
    },
    "Lao people still tell this epic to teach courage and loyalty.": {
        "zh": "老挝人至今仍讲述这部史诗，用来教导勇气与忠诚。",
        "km": "ប្រជាជនលាវនៅតែនិទានរឿងវីរភាពនេះ ដើម្បីបង្រៀនភាពក្លាហាន និងភាពស្មោះត្រង់។",
    },
    "What is an 'epic'?": {
        "zh": "'epic' 是什么？",
        "km": "'epic' គឺជាអ្វី?",
    },
    "A long heroic story about a nation's legendary hero — bigger than a short fairy tale.": {
        "zh": "一个关于民族传奇英雄的长篇英雄故事——比短篇童话更宏大。",
        "km": "រឿងវីរភាពវែងអំពីវីរបុរសព្រេងនិទានរបស់ជាតិមួយ — ធំជាងរឿងនិទានខ្លី។",
    },
    "Why use the infinitive 'to teach'?": {
        "zh": "为什么使用不定式 'to teach'？",
        "km": "ហេតុអ្វីប្រើទម្រង់ 'to teach'?",
    },
    "'To teach' shows purpose: they tell the story in order to teach courage and loyalty.": {
        "zh": "'To teach' 表示目的：他们讲这个故事是为了教导勇气与忠诚。",
        "km": "'To teach' បង្ហាញគោលបំណង៖ ពួកគេនិទានរឿងនេះដើម្បីបង្រៀនភាពក្លាហាន និងភាពស្មោះត្រង់។",
    },
    # ---- Movie lesson: The Incredibles -----------------------------------
    "Watch the movie clip carefully — listen for how people really speak.": {
        "zh": "仔细观看这段电影片段——注意听人们真实的说话方式。",
        "km": "មើលវីដេអូខ្លីនេះដោយយកចិត្តទុកដាក់ — ស្តាប់របៀបដែលមនុស្សនិយាយពិតៗ។",
    },
    "What does 'listen for' mean?": {
        "zh": "'listen for' 是什么意思？",
        "km": "'listen for' មានន័យដូចម្តេច?",
    },
    "'Listen for' means pay attention until you hear a specific word or sound, not just hear generally.": {
        "zh": "'Listen for' 意思是专注地听，直到听见某个特定的词或声音，而不是随便听一听。",
        "km": "'Listen for' មានន័យថាផ្តោតអារម្មណ៍ស្តាប់ រហូតដល់អ្នកឮពាក្យ ឬសំឡេងជាក់លាក់ មិនមែនគ្រាន់តែឮធម្មតាទេ។",
    },
    "Why is 'how people really speak' useful for learners?": {
        "zh": "为什么 'how people really speak' 对学习者有用？",
        "km": "ហេតុអ្វី 'how people really speak' មានប្រយោជន៍ដល់អ្នកសិក្សា?",
    },
    "Movie English is natural speech: reduced sounds, stress and everyday grammar you need beyond textbooks.": {
        "zh": "电影里的英语是自然口语：弱读、重音，以及课本之外你需要的日常语法。",
        "km": "ភាសាអង់គ្លេសក្នុងភាពយន្តជាការនិយាយធម្មជាតិ៖ សំឡេងកាត់ខ្លី សំឡេងសង្កត់ និងវេយ្យាករណ៍ប្រចាំថ្ងៃដែលអ្នកត្រូវការលើសពីសៀវភៅ។",
    },
    "Heroes hide their powers and try to live a normal family life.": {
        "zh": "英雄们隐藏自己的超能力，努力过普通的家庭生活。",
        "km": "វីរបុរសបិទបាំងអំណាចរបស់ពួកគេ ហើយព្យាយាមរស់នៅជីវិតគ្រួសារធម្មតា។",
    },
    "What does 'live a normal family life' mean?": {
        "zh": "'live a normal family life' 是什么意思？",
        "km": "'live a normal family life' មានន័យដូចម្តេច?",
    },
    "It means everyday home routines — school, work, dinner — without superhero drama.": {
        "zh": "意思是每天的家庭日常——上学、上班、吃晚饭——没有超级英雄的戏剧场面。",
        "km": "មានន័យថាទម្លាប់ប្រចាំថ្ងៃក្នុងផ្ទះ — សាលា ការងារ អាហារពេលល្ងាច — ដោយគ្មានរឿងរ៉ាវវីរបុរសអស្ចារ្យ។",
    },
    "Why are both verbs after 'and' in the present?": {
        "zh": "为什么 'and' 后面的两个动词都用现在时？",
        "km": "ហេតុអ្វីកិរិយាសព្ទទាំងពីរនៅក្រោយ 'and' ជាបច្ចុប្បន្នកាល?",
    },
    "'Hide' and 'try' are present simple for habits and ongoing situations in the story setup.": {
        "zh": "'Hide' 和 'try' 是一般现在时，用于故事设定中的习惯和持续状态。",
        "km": "'Hide' និង 'try' ជាបច្ចុប្បន្នកាលសាមញ្ញ សម្រាប់ទម្លាប់ និងស្ថានភាពដែលកំពុងបន្តក្នុងការកំណត់រឿង។",
    },
    "Notice short spoken phrases like 'Come on!' and 'We've got to go.'": {
        "zh": "注意像 'Come on!' 和 'We've got to go.' 这样的简短口语短语。",
        "km": "សូមកត់សម្គាល់ឃ្លានិយាយខ្លីៗ ដូចជា 'Come on!' និង 'We've got to go.'។",
    },
    "When do people say 'Come on!'?": {
        "zh": "人们什么时候说 'Come on!'？",
        "km": "ពេលណាមនុស្សនិយាយថា 'Come on!'?",
    },
    "To urge someone to hurry, try harder, or follow — a friendly push, not a full sentence.": {
        "zh": "用来催促别人快点、再努力或跟上——是一种友好的推动，而不是完整的句子。",
        "km": "ដើម្បីជំរុញអ្នកណាម្នាក់ឱ្យប្រញាប់ ព្យាយាមបន្ថែម ឬតាមមក — ជាការជំរុញដោយមិត្តភាព មិនមែនប្រយោគពេញលេញទេ។",
    },
    'What does "We\'ve got to go" mean in formal English?': {
        "zh": "在正式英语里，\"We've got to go\" 是什么意思？",
        "km": "\"We've got to go\" មានន័យដូចម្តេចនៅក្នុងភាសាអង់គ្លេសផ្លូវការ?",
    },
    "It means 'We have to go' / 'We must leave.' Spoken English prefers 'have got to' for urgency.": {
        "zh": "意思是 'We have to go' / 'We must leave.' 口语英语更爱用 'have got to' 来表达紧迫。",
        "km": "មានន័យថា 'We have to go' / 'We must leave.'។ ភាសាអង់គ្លេសនិយាយចូលចិត្តប្រើ 'have got to' សម្រាប់ការបន្ទាន់។",
    },
    "Stress falls on the important words: GO, HELP, NOW — little words stay soft.": {
        "zh": "重音落在重要的词上：GO、HELP、NOW——小词读得轻。",
        "km": "សំឡេងសង្កត់ធ្លាក់លើពាក្យសំខាន់៖ GO, HELP, NOW — ពាក្យតូចៗនិយាយស្រាល។",
    },
    "What is word stress?": {
        "zh": "什么是词重音？",
        "km": "សំឡេងសង្កត់ពាក្យគឺជាអ្វី?",
    },
    "The beat you say louder and longer. Content words (go, help, now) carry stress; a/the/to stay soft.": {
        "zh": "你说得更响、更长的那一拍。实义词（go、help、now）承担重音；a/the/to 读得轻。",
        "km": "ចង្វាក់ដែលអ្នកនិយាយឱ្យខ្លាំង និងវែងជាង។ ពាក្យមានអត្ថន័យ (go, help, now) ទទួលសំឡេងសង្កត់ ចំណែក a/the/to និយាយស្រាល។",
    },
    "Why does English skip stress on 'little words'?": {
        "zh": "为什么英语不在 'little words' 上加重音？",
        "km": "ហេតុអ្វីភាសាអង់គ្លេសមិនសង្កត់លើ 'little words'?",
    },
    "Articles and prepositions are grammar glue. Stressing content words helps listeners catch the message fast.": {
        "zh": "冠词和介词是语法的黏合剂。重读实义词能帮听者更快抓住信息。",
        "km": "ពាក្យកំណត់នាម (a/the) និងបុព្វបទ ជាកាវវេយ្យាករណ៍។ ការសង្កត់លើពាក្យមានអត្ថន័យជួយអ្នកស្តាប់ចាប់សារបានលឿន។",
    },
    "Replay the clip and shadow the lines out loud to make the phrases yours.": {
        "zh": "重播片段，跟着台词大声影子跟读，让这些短语成为你自己的。",
        "km": "ចាក់វីដេអូឡើងវិញ ហើយនិយាយតាមឃ្លាឱ្យឮៗ ដើម្បីធ្វើឱ្យឃ្លាទាំងនោះក្លាយជារបស់អ្នក។",
    },
    "What does 'shadow' mean in language learning?": {
        "zh": "在语言学习里 'shadow' 是什么意思？",
        "km": "នៅក្នុងការសិក្សាភាសា 'shadow' មានន័យដូចម្តេច?",
    },
    "Speak along with the audio a split-second behind it — copy rhythm, stress and emotion.": {
        "zh": "比音频慢半秒跟着说出来——模仿节奏、重音和情绪。",
        "km": "និយាយតាមសំឡេងដោយយឺតជាងវាមួយប៉ព្រិចភ្នែក — ចម្លងចង្វាក់ សំឡេងសង្កត់ និងអារម្មណ៍។",
    },
    "Why replay after the explanations?": {
        "zh": "为什么讲解之后要重播？",
        "km": "ហេតុអ្វីត្រូវចាក់ឡើងវិញបន្ទាប់ពីការពន្យល់?",
    },
    "First watch for meaning, then study the language, then speak it. Repetition turns phrases into usable English.": {
        "zh": "先看懂意思，再学语言，然后说出来。重复能把短语变成可用的英语。",
        "km": "ដំបូងមើលដើម្បីយល់អត្ថន័យ បន្ទាប់មកសិក្សាភាសា ហើយបន្ទាប់មកនិយាយវា។ ការធ្វើម្តងហើយម្តងទៀតបម្លែងឃ្លាទៅជាភាសាអង់គ្លេសដែលប្រើបាន។",
    },
}
