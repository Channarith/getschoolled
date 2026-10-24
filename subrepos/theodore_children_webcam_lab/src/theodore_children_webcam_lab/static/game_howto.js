// How to play every Play Lab game, in English, Spanish and Khmer.
//
// Each game has a title and four short lines: what you see, what to do, how you score, one tip.
// The text follows the real game code (app.js prompts, game_engine.py rules); nothing here invents a
// mechanic. "@fun", "@audio", "@trace", "@mirror" and "@ninja" are the shared scoring lines below.
// Khmer text was written for this release and needs a native-speaker review before it is final.

export const HOWTO_LANGS = ["en", "es", "km"];
export const KHMER_NEEDS_REVIEW = true;

export const UI = {
  en: {letsPlay: "Let's play", skip: "Skip", help: "How to play", next: "Next ▶", prev: "◀", back: "Back", close: "Close"},
  es: {letsPlay: "¡A jugar!", skip: "Omitir", help: "Cómo se juega", next: "Siguiente ▶", prev: "◀", back: "Atrás", close: "Cerrar"},
  km: {letsPlay: "តោះលេង!", skip: "រំលង", help: "របៀបលេង", next: "បន្ទាប់ ▶", prev: "◀", back: "ត្រឡប់", close: "បិទ"},
};

export const LABELS = {
  en: ["What you see", "What to do", "How you score", "Tip"],
  es: ["Lo que ves", "Qué hacer", "Cómo se puntúa", "Consejo"],
  km: ["អ្វីដែលអ្នកឃើញ", "អ្វីដែលត្រូវធ្វើ", "របៀបបានពិន្ទុ", "ជំនួយ"],
};

const SCORE = {
  en: {
    fun: "Each win gives Fun points and up to 3 stars. Quick first-try wins score the most, and winning in a row builds a combo.",
    audio: "Say it right to pass: 2 stars for a pass and 3 for a near-perfect match. Almost? You get another try.",
    trace: "Finish the whole path to win. Fun points and stars follow, and quick tidy tracing scores more.",
    mirror: "Each pose you match lights up a beat. Matching 85% of the beats is 3 stars, and 60% is 2 stars.",
    ninja: "Each correct sign moves you along the technique. Finish the last sign to unleash the finisher.",
  },
  es: {
    fun: "Cada acierto da puntos de Diversión y hasta 3 estrellas. Ganar rápido y a la primera da más, y ganar seguido crea un combo.",
    audio: "Dilo bien para pasar: 2 estrellas por pasar y 3 si es casi perfecto. ¿Casi? Tienes otro intento.",
    trace: "Termina todo el camino para ganar. Recibes puntos de Diversión y estrellas, y trazar rápido y limpio da más.",
    mirror: "Cada pose que igualas enciende un tiempo. Igualar el 85% son 3 estrellas y el 60% son 2 estrellas.",
    ninja: "Cada señal correcta te lleva por la técnica. Termina la última señal para lanzar el golpe final.",
  },
  km: {
    fun: "រាល់ការឈ្នះបានពិន្ទុសប្បាយ និងផ្កាយរហូតដល់ ៣។ ឈ្នះលឿនក្នុងលើកដំបូងបានច្រើនជាងគេ ហើយឈ្នះជាប់ៗគ្នាបង្កើតបាន «ខប់បូ»។",
    audio: "និយាយឱ្យត្រូវដើម្បីជាប់៖ ២ផ្កាយបើជាប់ និង ៣ផ្កាយបើស្ទើរតែត្រូវទាំងស្រុង។ ស្ទើរតែត្រូវ? អ្នកបានសាកម្តងទៀត។",
    trace: "គូរតាមផ្លូវរហូតដល់ចប់ដើម្បីឈ្នះ។ អ្នកបានពិន្ទុសប្បាយ និងផ្កាយ ហើយគូរលឿននិងស្អាតបានច្រើនជាង។",
    mirror: "ឥរិយាបថនីមួយៗដែលត្រូវ នឹងបំភ្លឺចង្វាក់មួយ។ ត្រូវ ៨៥% បាន ៣ផ្កាយ ហើយ ៦០% បាន ២ផ្កាយ។",
    ninja: "សញ្ញាដែលត្រូវនីមួយៗនាំអ្នកទៅមុខតាមបច្ចេកទេស។ ធ្វើសញ្ញាចុងក្រោយឱ្យចប់ដើម្បីបញ្ចេញកម្លាំងបញ្ចប់។",
  },
};

// [icon, en[title, see, do, score, tip], es[...], km[...]]
export const HOWTO = {
  "trace-letter": ["✏️",
    ["Trace a letter", "A big glowing letter shows a path from start to finish.", "Point one finger up and follow the path, or drag on the screen.", "@trace", "Go slowly. Close is good enough, and Undo lets you redo a stroke."],
    ["Traza una letra", "Una letra grande y brillante muestra un camino de principio a fin.", "Levanta un dedo y sigue el camino, o arrastra sobre la pantalla.", "@trace", "Ve despacio. Cerca es suficiente, y Deshacer te deja repetir un trazo."],
    ["គូរតាមអក្សរ", "អក្សរធំភ្លឺបង្ហាញផ្លូវពីចំណុចចាប់ផ្តើមដល់ចំណុចបញ្ចប់។", "លើកម្រាមដៃមួយឡើង ហើយគូរតាមផ្លូវ ឬអូសលើអេក្រង់។", "@trace", "គូរយឺតៗ។ ជិតត្រូវក៏បានដែរ ហើយ «មិនធ្វើវិញ» ជួយឱ្យអ្នកគូរសាជាថ្មី។"]],
  "trace-picture": ["🖍️",
    ["Trace a picture", "A picture appears with an outline around it.", "Use one finger to draw all the way around the picture.", "@trace", "Stay near the line, but it does not need to be perfect."],
    ["Traza un dibujo", "Aparece un dibujo con su contorno.", "Usa un dedo para dibujar todo el contorno del dibujo.", "@trace", "Quédate cerca de la línea, pero no tiene que ser perfecto."],
    ["គូរតាមរូប", "រូបមួយបង្ហាញឡើងជាមួយគ្រោងរបស់វា។", "ប្រើម្រាមដៃមួយគូររង្វិលជុំវិញរូបទាំងមូល។", "@trace", "នៅជិតបន្ទាត់ តែមិនចាំបាច់ឥតខ្ចោះទេ។"]],
  "color-picture": ["🎨",
    ["Color the picture", "A picture with empty shapes and a row of crayons.", "Pick a color first, then scratch inside a shape like a marker. Lift your finger to stop.", "Fill every shape to finish. Fun points and stars follow.", "Stay inside the shape. Undo takes a stroke back."],
    ["Colorea el dibujo", "Un dibujo con formas vacías y una fila de crayones.", "Primero elige un color y luego rayas dentro de una forma como con un marcador. Levanta el dedo para parar.", "Rellena todas las formas para terminar. Recibes puntos de Diversión y estrellas.", "Quédate dentro de la forma. Deshacer quita un trazo."],
    ["ដាក់ពណ៌លើរូប", "រូបមួយមានរូបរាងទទេ និងដុំជាបន្ទាត់ពណ៌ជាច្រើន។", "ជ្រើសពណ៌មុន រួចគូសក្នុងរូបរាងដូចប្រើប៊ិច។ លើកម្រាមដៃដើម្បីឈប់។", "ដាក់ពណ៌គ្រប់រូបរាងដើម្បីបញ្ចប់។ អ្នកបានពិន្ទុសប្បាយ និងផ្កាយ។", "នៅក្នុងរូបរាង។ «មិនធ្វើវិញ» ដកបន្ទាត់មួយចេញ។"]],
  "connect-dots": ["🔵",
    ["Connect the dots", "Numbered dots are hiding a picture.", "Touch the numbers in order, starting at 1.", "Reach the last dot to reveal the picture and win.", "Draw from one dot to the next. Do not skip a number."],
    ["Une los puntos", "Unos puntos numerados esconden un dibujo.", "Toca los números en orden, empezando por el 1.", "Llega al último punto para ver el dibujo y ganar.", "Dibuja de un punto al siguiente. No te saltes ningún número."],
    ["តភ្ជាប់ចំណុច", "ចំណុចមានលេខលាក់រូបមួយ។", "ប៉ះលេខតាមលំដាប់ ចាប់ផ្តើមពីលេខ ១។", "ទៅដល់ចំណុចចុងក្រោយដើម្បីបង្ហាញរូប និងឈ្នះ។", "គូរពីចំណុចមួយទៅចំណុចបន្ទាប់។ កុំរំលងលេខ។"]],
  "trace-outline": ["🧩",
    ["Trace the outline", "A picture outline to follow.", "Follow the outline with one finger. It does not need to be perfect.", "@trace", "Stay close to the line; Undo fixes a slip."],
    ["Traza el contorno", "El contorno de un dibujo para seguir.", "Sigue el contorno con un dedo. No tiene que ser perfecto.", "@trace", "Quédate cerca de la línea; Deshacer arregla un resbalón."],
    ["គូរតាមគ្រោង", "គ្រោងរូបមួយសម្រាប់គូរតាម។", "គូរតាមគ្រោងដោយប្រើម្រាមដៃមួយ។ មិនចាំបាច់ឥតខ្ចោះទេ។", "@trace", "នៅជិតបន្ទាត់។ «មិនធ្វើវិញ» ជួយកែកំហុស។"]],
  "say-letter": ["🔤",
    ["Say the letter", "A big letter appears and Theodore says it.", "Tap the microphone and say its name, or type it and tap Check.", "@audio", "Not sure? Tap Hear it to listen first."],
    ["Di la letra", "Aparece una letra grande y Theodore la dice.", "Toca el micrófono y di su nombre, o escríbela y toca Comprobar.", "@audio", "¿No estás seguro? Toca Escuchar para oírla primero."],
    ["និយាយអក្សរ", "អក្សរធំបង្ហាញឡើង ហើយ Theodore និយាយវា។", "ប៉ះមីក្រូហ្វូន ហើយនិយាយឈ្មោះអក្សរ ឬវាយវាចូល រួចប៉ះ «ពិនិត្យ»។", "@audio", "មិនប្រាកដ? ប៉ះ «ស្តាប់» ដើម្បីស្តាប់សិន។"]],
  "repeat-after-me": ["🔁",
    ["Repeat after me", "You hear a short sentence.", "Say the sentence back, or type it and tap Check.", "@audio", "Speak clearly. Tap Hear it to listen again."],
    ["Repite después de mí", "Escuchas una frase corta.", "Repite la frase, o escríbela y toca Comprobar.", "@audio", "Habla claro. Toca Escuchar para oírla otra vez."],
    ["និយាយតាមខ្ញុំ", "អ្នកឮប្រយោគខ្លីមួយ។", "និយាយប្រយោគនោះវិញ ឬវាយចូល រួចប៉ះ «ពិនិត្យ»។", "@audio", "និយាយឱ្យច្បាស់។ ប៉ះ «ស្តាប់» ដើម្បីស្តាប់ម្តងទៀត។"]],
  "pronounce-word": ["🗣️",
    ["Pronounce the word", "A word appears and is read aloud.", "Say the word clearly into the microphone.", "@audio", "Say it slowly, sound by sound."],
    ["Pronuncia la palabra", "Aparece una palabra y se lee en voz alta.", "Di la palabra con claridad al micrófono.", "@audio", "Dila despacio, sonido por sonido."],
    ["បញ្ចេញសំឡេងពាក្យ", "ពាក្យមួយបង្ហាញឡើង ហើយត្រូវបានអានឱ្យឮ។", "និយាយពាក្យនោះឱ្យច្បាស់ទៅក្នុងមីក្រូហ្វូន។", "@audio", "និយាយយឺតៗ ម្តងមួយសំឡេង។"]],
  "rhyme-time": ["🎶",
    ["Say a rhyme", "You hear a word, like cat.", "Say any word that rhymes with it, like hat.", "@audio", "Any real rhyming word counts."],
    ["Di una rima", "Escuchas una palabra, como gato.", "Di cualquier palabra que rime con ella, como pato.", "@audio", "Vale cualquier palabra real que rime."],
    ["និយាយពាក្យចុងស្រដៀងគ្នា", "អ្នកឮពាក្យមួយ ដូចជា «cat»។", "និយាយពាក្យណាមួយដែលចុងស្រដៀងគ្នា ដូចជា «hat»។", "@audio", "ពាក្យពិតណាមួយដែលចុងស្រដៀងគ្នា ក៏បានដែរ។"]],
  "listen-answer": ["👂",
    ["Answer what you hear", "You hear a short question.", "Answer it out loud, or type your answer and tap Check.", "@audio", "Tap Hear it to listen again before you answer."],
    ["Responde lo que oyes", "Escuchas una pregunta corta.", "Respóndela en voz alta, o escribe tu respuesta y toca Comprobar.", "@audio", "Toca Escuchar para oírla otra vez antes de responder."],
    ["ឆ្លើយតាមអ្វីដែលឮ", "អ្នកឮសំណួរខ្លីមួយ។", "ឆ្លើយឱ្យឮ ឬវាយចម្លើយ រួចប៉ះ «ពិនិត្យ»។", "@audio", "ប៉ះ «ស្តាប់» ដើម្បីស្តាប់ម្តងទៀតមុនឆ្លើយ។"]],
  "missing-word": ["❓",
    ["Say the missing word", "You hear a sentence with a word left out.", "Say the word that was left out.", "@audio", "Think about which word makes the sentence make sense."],
    ["Di la palabra que falta", "Escuchas una frase con una palabra omitida.", "Di la palabra que falta.", "@audio", "Piensa qué palabra le da sentido a la frase."],
    ["និយាយពាក្យដែលបាត់", "អ្នកឮប្រយោគមួយដែលខ្វះពាក្យមួយ។", "និយាយពាក្យដែលត្រូវបានលុបចេញ។", "@audio", "គិតថាពាក្យអ្វីធ្វើឱ្យប្រយោគមានន័យ។"]],
  "opposites": ["↔️",
    ["Say the opposite", "You hear a word, like hot.", "Say its opposite, like cold.", "@audio", "Tap Check if you typed your answer."],
    ["Di lo contrario", "Escuchas una palabra, como caliente.", "Di su contrario, como frío.", "@audio", "Toca Comprobar si escribiste tu respuesta."],
    ["និយាយពាក្យផ្ទុយ", "អ្នកឮពាក្យមួយ ដូចជា «ក្តៅ»។", "និយាយពាក្យផ្ទុយរបស់វា ដូចជា «ត្រជាក់»។", "@audio", "ប៉ះ «ពិនិត្យ» បើអ្នកវាយចម្លើយ។"]],
  "explain-it": ["💬",
    ["Explain it", "You hear a short idea.", "Explain why, using what you heard.", "@audio", "A short answer with one reason is enough."],
    ["Explícalo", "Escuchas una idea corta.", "Explica por qué, usando lo que oíste.", "@audio", "Una respuesta corta con una razón es suficiente."],
    ["ពន្យល់វា", "អ្នកឮគំនិតខ្លីមួយ។", "ពន្យល់ពីមូលហេតុ ដោយប្រើអ្វីដែលអ្នកបានឮ។", "@audio", "ចម្លើយខ្លីមួយដែលមានមូលហេតុមួយ គឺគ្រប់គ្រាន់ហើយ។"]],
  "sum-it-up": ["📝",
    ["Sum it up", "You hear a short story.", "Say the short idea, not every detail.", "@audio", "One short sentence is best."],
    ["Resúmelo", "Escuchas una historia corta.", "Di la idea corta, no cada detalle.", "@audio", "Una frase corta es lo mejor."],
    ["សង្ខេបវា", "អ្នកឮរឿងខ្លីមួយ។", "និយាយគំនិតខ្លី មិនមែនគ្រប់ព័ត៌មានលម្អិតទេ។", "@audio", "ប្រយោគខ្លីមួយគឺល្អបំផុត។"]],
  "prove-it": ["✅",
    ["Prove you understand", "You hear a short explanation.", "Say the reason you heard.", "@audio", "Use a word from what you heard."],
    ["Demuestra que entiendes", "Escuchas una explicación corta.", "Di la razón que escuchaste.", "@audio", "Usa una palabra de lo que oíste."],
    ["បង្ហាញថាអ្នកយល់", "អ្នកឮការពន្យល់ខ្លីមួយ។", "និយាយមូលហេតុដែលអ្នកបានឮ។", "@audio", "ប្រើពាក្យមួយពីអ្វីដែលអ្នកបានឮ។"]],
  "story-order": ["📖",
    ["What happened first", "You hear a short story.", "Say what happened first (some rounds ask what happened last).", "@audio", "Tap Hear it to listen again."],
    ["Qué pasó primero", "Escuchas una historia corta.", "Di qué pasó primero (algunas rondas preguntan qué pasó al final).", "@audio", "Toca Escuchar para oírla otra vez."],
    ["អ្វីបានកើតឡើងមុនគេ", "អ្នកឮរឿងខ្លីមួយ។", "និយាយអ្វីដែលកើតឡើងមុនគេ (ជុំខ្លះសួរអ្វីដែលកើតឡើងក្រោយគេ)។", "@audio", "ប៉ះ «ស្តាប់» ដើម្បីស្តាប់ម្តងទៀត។"]],
  "how-many": ["🔢",
    ["How many did you hear", "You hear a few sounds or items.", "Say or type the number.", "@audio", "Listen once, count, then answer."],
    ["¿Cuántos oíste?", "Escuchas unos cuantos sonidos o cosas.", "Di o escribe el número.", "@audio", "Escucha una vez, cuenta y luego responde."],
    ["ឮប៉ុន្មាន", "អ្នកឮសំឡេង ឬវត្ថុមួយចំនួន។", "និយាយ ឬវាយចំនួន។", "@audio", "ស្តាប់មួយដង រាប់ រួចឆ្លើយ។"]],
  "same-or-different": ["👯",
    ["Same or different", "You hear two words or sounds.", "Say same or different.", "@audio", "Replay with Hear it if you are not sure."],
    ["Igual o diferente", "Escuchas dos palabras o sonidos.", "Di igual o diferente.", "@audio", "Vuelve a oírlo con Escuchar si no estás seguro."],
    ["ដូចគ្នា ឬខុសគ្នា", "អ្នកឮពាក្យ ឬសំឡេងពីរ។", "និយាយថា «ដូចគ្នា» ឬ «ខុសគ្នា»។", "@audio", "ស្តាប់ម្តងទៀតដោយប៉ះ «ស្តាប់» បើមិនប្រាកដ។"]],
  "finish-the-line": ["⏭️",
    ["Finish the line", "You hear the start of a sentence.", "Say the words that finish it.", "@audio", "Tap Hear it to listen again."],
    ["Termina la frase", "Escuchas el comienzo de una frase.", "Di las palabras que la terminan.", "@audio", "Toca Escuchar para oírla otra vez."],
    ["បញ្ចប់ប្រយោគ", "អ្នកឮដើមប្រយោគមួយ។", "និយាយពាក្យដែលបញ្ចប់វា។", "@audio", "ប៉ះ «ស្តាប់» ដើម្បីស្តាប់ម្តងទៀត។"]],
  "spell-aloud": ["🅰️",
    ["Spell what you hear", "You hear a word.", "Say each letter out loud, one at a time, or type it and tap Check.", "@audio", "Take your time between letters."],
    ["Deletrea lo que oyes", "Escuchas una palabra.", "Di cada letra en voz alta, una por una, o escríbela y toca Comprobar.", "@audio", "Tómate tu tiempo entre letras."],
    ["ប្រកបពាក្យដែលអ្នកឮ", "អ្នកឮពាក្យមួយ។", "និយាយអក្សរនីមួយៗឱ្យឮ ម្តងមួយ ឬវាយវា រួចប៉ះ «ពិនិត្យ»។", "@audio", "កុំប្រញាប់រវាងអក្សរនីមួយៗ។"]],
  "karaoke": ["🎤",
    ["Karaoke sing-along", "Pick a song. The words stay large and light up as the song plays.", "Sing along with the highlighted words.", "This one is just for fun: sing as loud as you like!", "Tap Play to start the song over."],
    ["Karaoke para cantar", "Elige una canción. Las palabras se ven grandes y se iluminan mientras suena.", "Canta con las palabras resaltadas.", "Este es solo por diversión: ¡canta tan fuerte como quieras!", "Toca Jugar para empezar la canción otra vez."],
    ["ច្រៀងខារ៉ាអូខេ", "ជ្រើសបទចម្រៀង។ ពាក្យនៅធំ ហើយភ្លឺនៅពេលបទចាក់។", "ច្រៀងតាមពាក្យដែលភ្លឺ។", "ល្បែងនេះសម្រាប់តែសប្បាយ៖ ច្រៀងឱ្យខ្លាំងតាមចិត្ត!", "ប៉ះ «លេង» ដើម្បីចាប់ផ្តើមបទម្តងទៀត។"]],
  "oh-behave": ["😮",
    ["Oh behave", "A glowing circle and a face to copy.", "Make the face it asks for, inside the glowing circle.", "@fun", "Hold the face for a moment before the timer ends."],
    ["Pórtate bien", "Un círculo brillante y una cara para copiar.", "Haz la cara que pide, dentro del círculo brillante.", "@fun", "Mantén la cara un momento antes de que acabe el tiempo."],
    ["ធ្វើមុខតាម", "រង្វង់ភ្លឺមួយ និងមុខមួយសម្រាប់ធ្វើតាម។", "ធ្វើមុខដែលវាសុំ នៅក្នុងរង្វង់ភ្លឺ។", "@fun", "កាន់មុខនោះមួយភ្លែតមុនពេលវេលាអស់។"]],
  "heart": ["💖",
    ["Make hearts", "A glowing heart target.", "Use both hands: fingertips together at the top and thumbs meeting at the bottom.", "@fun", "A plain circle does not count; make a real heart shape."],
    ["Haz corazones", "Un objetivo de corazón brillante.", "Usa las dos manos: las puntas de los dedos juntas arriba y los pulgares juntos abajo.", "@fun", "Un círculo simple no cuenta; haz una forma de corazón de verdad."],
    ["ធ្វើបេះដូង", "គោលដៅបេះដូងភ្លឺមួយ។", "ប្រើដៃទាំងពីរ៖ ចុងម្រាមដៃជាប់គ្នានៅខាងលើ ហើយមេដៃជួបគ្នានៅខាងក្រោម។", "@fun", "រង្វង់ធម្មតាមិនរាប់ទេ ត្រូវធ្វើរាងបេះដូងពិត។"]],
  "idea": ["💡",
    ["I have an idea", "A glowing circle near the top.", "Hold one index finger up in the air.", "@fun", "Keep your hand in the picture and hold still."],
    ["Tengo una idea", "Un círculo brillante cerca de la parte de arriba.", "Levanta un dedo índice en el aire.", "@fun", "Mantén la mano en la imagen y quédate quieto."],
    ["ខ្ញុំមានគំនិត", "រង្វង់ភ្លឺមួយនៅជិតខាងលើ។", "លើកម្រាមដៃចង្អុលមួយឡើងលើអាកាស។", "@fun", "ដាក់ដៃនៅក្នុងរូប ហើយកាន់ឱ្យនឹង។"]],
  "fist-bump": ["👊",
    ["Fist bump", "A fist target in the middle of the screen.", "Make a fist and bump Theodore.", "@fun", "Keep your hand in the picture."],
    ["Choca el puño", "Un objetivo de puño en el centro de la pantalla.", "Cierra el puño y chócalo con Theodore.", "@fun", "Mantén la mano en la imagen."],
    ["ទះកណ្តាប់ដៃ", "គោលដៅកណ្តាប់ដៃនៅកណ្តាលអេក្រង់។", "ធ្វើកណ្តាប់ដៃ ហើយទះជាមួយ Theodore។", "@fun", "ដាក់ដៃនៅក្នុងរូប។"]],
  "wow": ["🤩",
    ["Wow face", "A glowing circle with a surprised face.", "Open your mouth and raise your eyebrows like a surprise.", "@fun", "Look at the camera and hold it."],
    ["Cara de asombro", "Un círculo brillante con una cara sorprendida.", "Abre la boca y levanta las cejas como una sorpresa.", "@fun", "Mira a la cámara y mantenla."],
    ["មុខភ្ញាក់ផ្អើល", "រង្វង់ភ្លឺមួយដែលមានមុខភ្ញាក់ផ្អើល។", "ហាមាត់ ហើយលើកចិញ្ចើមដូចភ្ញាក់ផ្អើល។", "@fun", "មើលកាមេរ៉ា ហើយកាន់វា។"]],
  "blow-kiss": ["😘",
    ["Blow a kiss", "A kiss target in the middle.", "Make a little O, bring a hand near your mouth, then send it away.", "@fun", "Look at the camera first."],
    ["Lanza un beso", "Un objetivo de beso en el centro.", "Haz una pequeña O, acerca una mano a la boca y luego envíalo lejos.", "@fun", "Mira primero a la cámara."],
    ["ផ្លុំថ្វាយ", "គោលដៅថ្វាយបងមួយនៅកណ្តាល។", "ធ្វើមាត់តូចៗរាង O នាំដៃមកជិតមាត់ រួចបញ្ជូនវាចេញទៅ។", "@fun", "មើលកាមេរ៉ាសិន។"]],
  "wink": ["😉",
    ["Wink challenge", "A winking face in a glowing circle.", "Wink one eye at Theodore.", "@fun", "Keep the other eye open and hold the wink."],
    ["Reto del guiño", "Una cara que guiña en un círculo brillante.", "Guiña un ojo a Theodore.", "@fun", "Mantén el otro ojo abierto y sostén el guiño."],
    ["ប្រកួតព្រិចភ្នែក", "មុខព្រិចភ្នែកនៅក្នុងរង្វង់ភ្លឺ។", "ព្រិចភ្នែកម្ខាងទៅ Theodore។", "@fun", "បើកភ្នែកម្ខាងទៀតឱ្យនៅបើក ហើយកាន់ការព្រិចនោះ។"]],
  "make-pose": ["🦸",
    ["Make a hero pose", "A hero star target.", "Raise both hands and hold your biggest hero pose.", "@fun", "Step back so your hands show."],
    ["Haz una pose de héroe", "Un objetivo de estrella de héroe.", "Levanta las dos manos y mantén tu pose de héroe más grande.", "@fun", "Da un paso atrás para que se vean tus manos."],
    ["ធ្វើឥរិយាបថវីរបុរស", "គោលដៅផ្កាយវីរបុរសមួយ។", "លើកដៃទាំងពីរ ហើយកាន់ឥរិយាបថវីរបុរសធំបំផុតរបស់អ្នក។", "@fun", "ថយក្រោយបន្តិចដើម្បីឱ្យឃើញដៃរបស់អ្នក។"]],
  "balloon": ["🎈",
    ["Pop balloons", "A balloon floats on the screen.", "Touch it with one finger before time runs out.", "@fun", "Keep your hand in the picture, or just tap the balloon."],
    ["Revienta globos", "Un globo flota en la pantalla.", "Tócalo con un dedo antes de que se acabe el tiempo.", "@fun", "Mantén la mano en la imagen, o simplemente toca el globo."],
    ["ផ្ទុះបាឡុង", "បាឡុងមួយអណ្តែតលើអេក្រង់។", "ប៉ះវាដោយម្រាមដៃមួយមុនពេលវេលាអស់។", "@fun", "ដាក់ដៃនៅក្នុងរូប ឬគ្រាន់តែប៉ះបាឡុង។"]],
  "fish": ["🐟",
    ["Catch flying fish", "A fish flies across the screen.", "Touch it with one finger before it gets away.", "@fun", "Keep your hand in the picture, or just tap the fish."],
    ["Atrapa peces voladores", "Un pez vuela por la pantalla.", "Tócalo con un dedo antes de que escape.", "@fun", "Mantén la mano en la imagen, o simplemente toca el pez."],
    ["ចាប់ត្រីហោះ", "ត្រីមួយហោះកាត់អេក្រង់។", "ប៉ះវាដោយម្រាមដៃមួយមុនវារត់បាត់។", "@fun", "ដាក់ដៃនៅក្នុងរូប ឬគ្រាន់តែប៉ះត្រី។"]],
  "popcorn": ["🍿",
    ["Catch popcorn", "A popcorn kernel pops up.", "Make a big O with your mouth to catch it, or tap it on the screen.", "@fun", "Keep your face in the picture."],
    ["Atrapa palomitas", "Salta una palomita.", "Haz una O grande con la boca para atraparla, o tócala en la pantalla.", "@fun", "Mantén la cara en la imagen."],
    ["ចាប់ពោតលីង", "គ្រាប់ពោតលីងមួយលោតឡើង។", "ធ្វើមាត់រាង O ធំដើម្បីចាប់វា ឬប៉ះវាលើអេក្រង់។", "@fun", "ដាក់មុខនៅក្នុងរូប។"]],
  "fruit-cut": ["🍉",
    ["Fruit cut", "A piece of fruit flies by.", "Slice through it with a quick finger sweep in the air, or tap it on the screen.", "@fun", "Move your finger quickly through the fruit."],
    ["Corta la fruta", "Una fruta pasa volando.", "Córtala con un movimiento rápido del dedo en el aire, o tócala en la pantalla.", "@fun", "Mueve el dedo rápido a través de la fruta."],
    ["កាត់ផ្លែឈើ", "ផ្លែឈើមួយហោះកាត់។", "កាត់វាដោយអូសម្រាមដៃលឿនៗលើអាកាស ឬប៉ះវាលើអេក្រង់។", "@fun", "អូសម្រាមដៃឱ្យលឿនកាត់ផ្លែឈើ។"]],
  "mirror-hall": ["🪞",
    ["Mirror Hall", "A mirror with glowing spots for your head and hands.", "Step back so your upper body shows, then match each pose on the beat.", "@mirror", "Pick a slower pace if the beats come too fast."],
    ["Sala de espejos", "Un espejo con puntos brillantes para tu cabeza y tus manos.", "Da un paso atrás para que se vea la parte de arriba de tu cuerpo e iguala cada pose al ritmo.", "@mirror", "Elige un ritmo más lento si los tiempos van muy rápido."],
    ["សាលកញ្ចក់", "កញ្ចក់មួយមានចំណុចភ្លឺសម្រាប់ក្បាល និងដៃរបស់អ្នក។", "ថយក្រោយឱ្យឃើញខ្លួនខាងលើ រួចធ្វើឥរិយាបថនីមួយៗឱ្យត្រូវតាមចង្វាក់។", "@mirror", "ជ្រើសល្បឿនយឺតជាង បើចង្វាក់លឿនពេក។"]],
  "ninja-weave": ["🥷",
    ["Ninja Weave", "Hand signs to make, one after another.", "Show both hands and make each sign shown, in order.", "@ninja", "Take your time on the first sign; pick an easier pace if you need to."],
    ["Tejido ninja", "Señales de mano para hacer, una tras otra.", "Muestra las dos manos y haz cada señal que aparece, en orden.", "@ninja", "Tómate tu tiempo con la primera señal; elige un ritmo más fácil si lo necesitas."],
    ["ត្បាញនីនចា", "សញ្ញាដៃដែលត្រូវធ្វើ ម្តងមួយបន្តបន្ទាប់។", "បង្ហាញដៃទាំងពីរ ហើយធ្វើសញ្ញានីមួយៗដែលបង្ហាញ តាមលំដាប់។", "@ninja", "កុំប្រញាប់សញ្ញាដំបូង។ ជ្រើសល្បឿនងាយជាង បើត្រូវការ។"]],
  "air-drums": ["🥁",
    ["Air drums", "Drum pads on the screen.", "Hit the pads with your hands on the beat.", "@fun", "Keep both hands in the picture."],
    ["Batería en el aire", "Pads de batería en la pantalla.", "Golpea los pads con las manos al ritmo.", "@fun", "Mantén las dos manos en la imagen."],
    ["វាយស្គរលើអាកាស", "ក្តារស្គរនៅលើអេក្រង់។", "វាយក្តារស្គរដោយដៃរបស់អ្នកតាមចង្វាក់។", "@fun", "ដាក់ដៃទាំងពីរនៅក្នុងរូប។"]],
  "bird-flap": ["🐦",
    ["Flap like a bird", "A bird on the screen.", "Lift both hands up and down. Fly!", "@fun", "Big, smooth flaps work best."],
    ["Aletea como un pájaro", "Un pájaro en la pantalla.", "Sube y baja las dos manos. ¡Vuela!", "@fun", "Los aleteos grandes y suaves funcionan mejor."],
    ["ហើរដូចបក្សី", "បក្សីមួយនៅលើអេក្រង់។", "លើក និងបន្ទាបដៃទាំងពីរ។ ហើរ!", "@fun", "ការហើរធំៗ និងរលូន ដំណើរការល្អបំផុត។"]],
  "head-bop": ["🎧",
    ["Head bop", "Music with a steady beat.", "Move your head gently up and down to the beat.", "@fun", "Keep your face in the picture. Gentle nods are fine."],
    ["Mueve la cabeza", "Música con un ritmo constante.", "Mueve la cabeza suavemente arriba y abajo al ritmo.", "@fun", "Mantén la cara en la imagen. Los movimientos suaves valen."],
    ["គ្រវីក្បាលតាមចង្វាក់", "តន្ត្រីមានចង្វាក់ថេរ។", "ធ្វើក្បាលឡើងចុះថ្នមៗតាមចង្វាក់។", "@fun", "ដាក់មុខនៅក្នុងរូប។ ក្បាលឡើងចុះថ្នមៗ ក៏បាន។"]],
  "face-chase": ["🙂",
    ["Face chase", "A glowing circle that moves around.", "Move your face into the glowing circle.", "@fun", "Keep your face in the picture."],
    ["Persigue con la cara", "Un círculo brillante que se mueve.", "Mueve tu cara hasta el círculo brillante.", "@fun", "Mantén la cara en la imagen."],
    ["ដេញតាមមុខ", "រង្វង់ភ្លឺមួយដែលផ្លាស់ទីជុំវិញ។", "ផ្លាស់ទីមុខរបស់អ្នកចូលទៅក្នុងរង្វង់ភ្លឺ។", "@fun", "ដាក់មុខនៅក្នុងរូប។"]],
  "stand-sit": ["🪑",
    ["Stand up, sit down", "Theodore asks you to stand.", "Step back so Theodore sees you, then stand up gently and sit back down.", "@fun", "Seated-only mode turns this into a seated reach."],
    ["Levántate y siéntate", "Theodore te pide que te levantes.", "Da un paso atrás para que Theodore te vea, luego levántate despacio y vuelve a sentarte.", "@fun", "El modo solo sentado lo convierte en un estiramiento sentado."],
    ["ក្រោកឈរ អង្គុយចុះ", "Theodore សុំឱ្យអ្នកក្រោកឈរ។", "ថយក្រោយឱ្យ Theodore ឃើញអ្នក រួចក្រោកឈរថ្នមៗ ហើយអង្គុយចុះវិញ។", "@fun", "ជម្រើស «អង្គុយប៉ុណ្ណោះ» ប្តូរវាទៅជាការលូកដៃពេលអង្គុយ។"]],
  "dance-freeze": ["💃",
    ["Dance freeze", "Music plays.", "Move any way you like, and freeze when Theodore says freeze.", "@fun", "Step back so your whole body shows."],
    ["Baila y congela", "Suena música.", "Muévete como quieras y quédate quieto cuando Theodore diga ¡congela!", "@fun", "Da un paso atrás para que se vea todo tu cuerpo."],
    ["រាំ ហើយឈប់", "តន្ត្រីចាក់។", "ធ្វើចលនាតាមចិត្ត ហើយឈប់ឱ្យនឹងពេល Theodore និយាយថា «ឈប់»។", "@fun", "ថយក្រោយឱ្យឃើញរាងកាយទាំងមូល។"]],
  "rainbow-reach": ["🌈",
    ["Rainbow reach", "A rainbow across the top.", "Stretch both hands toward opposite top corners.", "@fun", "Reach up and across."],
    ["Alcanza el arcoíris", "Un arcoíris en la parte de arriba.", "Estira las dos manos hacia esquinas opuestas de arriba.", "@fun", "Estírate hacia arriba y hacia los lados."],
    ["លូកដល់ឥន្ទធនូ", "ឥន្ទធនូមួយនៅខាងលើ។", "លូកដៃទាំងពីរទៅជ្រុងខាងលើទល់មុខគ្នា។", "@fun", "លូកឡើងលើ និងទៅចំហៀង។"]],
};

// Pop Quiz Toss: five short steps with pictures (art names are in static/art/).
export const POP_QUIZ_STEPS = {
  en: [
    ["Stand back so both hands show", ["Step back about two big steps so your shoulders and both hands are in the picture.", "Face a light. On a phone or without a camera, press and drag on the ball instead."]],
    ["Your hand picks the answer", ["LEFT hand = the LEFT answer. RIGHT hand = the RIGHT answer.", "Pick a hand, throw at your answer, and Sala helps your ball find it."]],
    ["Grab, pull, throw", ["✊ Close your fist to grab the ball.", "↩️ Pull back like a slingshot.", "🖐️ Open your hand to throw it at your answer."]],
    ["Say it too for a bonus", ["Say the answer out loud and throw at it: 5 points. Just one of the two: 2 points.", "You get at least 10 seconds for every question. Take your time!"]],
    ["First to 100 wins", ["Keep a streak going for fireballs, rainbows and comets.", "Never throw a real object. This is a pretend ball!"]],
  ],
  es: [
    ["Aléjate para que se vean las dos manos", ["Da unos dos pasos grandes hacia atrás para que se vean tus hombros y las dos manos.", "Ponte frente a una luz. En un teléfono o sin cámara, presiona y arrastra la pelota."]],
    ["Tu mano elige la respuesta", ["Mano IZQUIERDA = respuesta de la IZQUIERDA. Mano DERECHA = respuesta de la DERECHA.", "Elige una mano, lanza hacia tu respuesta y Sala ayuda a que tu pelota la encuentre."]],
    ["Agarra, tira y lanza", ["✊ Cierra el puño para agarrar la pelota.", "↩️ Tira hacia atrás como una honda.", "🖐️ Abre la mano para lanzarla a tu respuesta."]],
    ["Dilo también para un bonus", ["Di la respuesta en voz alta y lánzala: 5 puntos. Solo una de las dos: 2 puntos.", "Tienes al menos 10 segundos por pregunta. ¡Tómate tu tiempo!"]],
    ["El primero en llegar a 100 gana", ["Mantén una racha para conseguir bolas de fuego, arcoíris y cometas.", "Nunca lances un objeto de verdad. ¡Esta es una pelota de mentira!"]],
  ],
  km: [
    ["ថយក្រោយឱ្យឃើញដៃទាំងពីរ", ["ថយក្រោយប្រហែលពីរជំហានធំ ដើម្បីឱ្យឃើញស្មា និងដៃទាំងពីរក្នុងរូប។", "ឈរទល់នឹងពន្លឺ។ លើទូរស័ព្ទ ឬគ្មានកាមេរ៉ា សូមចុច ហើយអូសបាល់ជំនួសវិញ។"]],
    ["ដៃរបស់អ្នកជ្រើសចម្លើយ", ["ដៃឆ្វេង = ចម្លើយខាងឆ្វេង។ ដៃស្តាំ = ចម្លើយខាងស្តាំ។", "ជ្រើសដៃមួយ គប់ទៅចម្លើយរបស់អ្នក ហើយ Sala ជួយឱ្យបាល់ទៅដល់។"]],
    ["ចាប់ ទាញ គប់", ["✊ ក្តាប់ដៃដើម្បីចាប់បាល់។", "↩️ ទាញថយក្រោយដូចអំបោះគប់ថ្ម។", "🖐️ ហាដៃដើម្បីគប់ទៅចម្លើយរបស់អ្នក។"]],
    ["និយាយផង បានពិន្ទុបន្ថែម", ["និយាយចម្លើយឱ្យឮ ហើយគប់ទៅវា៖ ៥ពិន្ទុ។ ត្រូវតែមួយក្នុងពីរ៖ ២ពិន្ទុ។", "អ្នកមានយ៉ាងហោចណាស់ ១០វិនាទីក្នុងសំណួរនីមួយៗ។ កុំប្រញាប់!"]],
    ["អ្នកដល់ ១០០ មុនគេឈ្នះ", ["រក្សាការឈ្នះជាប់ៗគ្នាដើម្បីបានបាល់ភ្លើង ឥន្ទធនូ និងផ្កាយដុះកន្ទុយ។", "កុំគប់វត្ថុពិត។ នេះគ្រាន់តែជាបាល់លេងសើច!"]],
  ],
};

export const POP_QUIZ_UI = {
  en: {label: "How to play Pop Quiz Toss"},
  es: {label: "Cómo se juega Pop Quiz Toss"},
  km: {label: "របៀបលេង Pop Quiz Toss"},
};

/** en, es or km from ?lang= or the page language; anything else is English. */
export function howtoLang(search = globalThis.location?.search || "", htmlLang = globalThis.document?.documentElement?.lang || "") {
  let raw = "";
  try {
    raw = (new URLSearchParams(search).get("lang") || "").trim().toLowerCase().replace(/_/g, "-");
  } catch (_) {
    raw = "";
  }
  const code = (raw || String(htmlLang || "").toLowerCase()).split("-")[0];
  return HOWTO_LANGS.includes(code) ? code : "en";
}

function resolve(line, lang) {
  return line.startsWith("@") ? (SCORE[lang]?.[line.slice(1)] || SCORE.en[line.slice(1)]) : line;
}

/** {icon, title, lines:[see, do, score, tip], labels} for a game in a language (English if missing). */
export function howtoFor(gameId, lang = "en") {
  const row = HOWTO[gameId];
  if (!row) return null;
  const code = HOWTO_LANGS.includes(lang) ? lang : "en";
  const index = 1 + HOWTO_LANGS.indexOf(code);
  const text = row[index] || row[1];
  const [title, ...lines] = text;
  return {icon: row[0], title, lines: lines.map((line) => resolve(line, code)), labels: LABELS[code] || LABELS.en};
}

export function popQuizSteps(lang = "en") {
  const code = HOWTO_LANGS.includes(lang) ? lang : "en";
  return (POP_QUIZ_STEPS[code] || POP_QUIZ_STEPS.en).map(([title, lines]) => ({title, lines}));
}
