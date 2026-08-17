"""Translate curated child lessons so the words match the spoken language.

Picking a language must change the TEXT, not just the voice. Sending English
words to a Spanish voice produces phonetic nonsense for a 4-year-old.

Three tiers, best first:
  1. curated — hand-authored per language, reviewed for young learners
  2. xai     — real Grok translation constrained to a tiny child vocabulary,
               cached on disk so later runs are instant and offline
  3. english — honest fallback; callers surface this so nobody assumes the
               child is hearing their own language

Phonics and sight-word lessons are language-specific by nature: "A is for
apple" cannot be translated literally, because apple is manzana in Spanish and
starts with M. Those lessons carry curated per-language variants that teach the
same skill with words that really start with the right sound, and they refuse
machine translation.
"""

from __future__ import annotations

import json
import os
import re
import threading
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .studio_languages import language_name, normalize_language
from .voice_agent import XAI_DEFAULT_MODEL


@dataclass(frozen=True)
class TranslatedBeat:
    title: str
    words: str
    say: str
    activity: str
    # Optional picture symbol override. Native-script reading lessons teach
    # different characters than the English original (人 vs "A 🍎"), so their
    # curated rows carry their own symbol; "" keeps the English lesson's symbol.
    symbol: str = ""


def _beat_from_row(row: tuple[str, ...]) -> TranslatedBeat:
    """Curated rows are (title, words, say, activity[, symbol])."""
    title, words, say, activity = row[0], row[1], row[2], row[3]
    symbol = row[4] if len(row) > 4 else ""
    return TranslatedBeat(title, words, say, activity, symbol)


@dataclass(frozen=True)
class TranslationResult:
    beats: tuple[TranslatedBeat, ...]
    source: str  # curated | xai | english
    note: str = ""


# Lessons whose skill depends on the sounds/spelling of one specific language.
SOUND_SPECIFIC_TOPICS = frozenset({"letter_sounds", "sight_words"})


# Curated translations: (title, words, say, activity) in lesson beat order.
_CURATED: dict[tuple[str, str], tuple[tuple[str, str, str, str], ...]] = {
    ("colors", "es"): (
        ("¡Hola, colores!", "Vamos a buscar cuatro colores.", "¡Hola, pequeño! Hoy vamos a buscar cuatro colores brillantes.", "Saluda a los colores."),
        ("Rojo", "El rojo es brillante.", "Esto es rojo. El rojo puede ser como una manzana.", "Busca algo rojo."),
        ("Azul", "El azul es fresco.", "Esto es azul. El azul puede ser como el cielo.", "Señala el cielo azul."),
        ("Amarillo", "El amarillo brilla.", "Esto es amarillo. El amarillo puede ser como el sol.", "Haz un sol grande con los brazos."),
        ("Verde", "El verde crece.", "Esto es verde. El verde puede ser como una hoja.", "Crece como una planta."),
        ("Busca colores", "¿Puedes ver un color?", "Mira a tu alrededor. Busca algo rojo, azul, amarillo o verde.", "Di el color que encontraste."),
        ("¡Muy bien!", "Rojo. Azul. Amarillo. Verde.", "¡Aprendiste cuatro colores! Dilos conmigo: rojo, azul, amarillo, verde.", "Date un aplauso."),
    ),
    ("shapes", "es"): (
        ("¡Hola, figuras!", "Las figuras están en todos lados.", "Hoy conocemos un círculo, un cuadrado y un triángulo.", "Dibuja una figura en el aire."),
        ("Círculo", "El círculo es redondo.", "Un círculo es redondo. No tiene esquinas.", "Haz un círculo con los brazos."),
        ("Cuadrado", "El cuadrado tiene cuatro lados.", "Un cuadrado tiene cuatro lados iguales y cuatro esquinas.", "Cuenta cuatro lados con el dedo."),
        ("Triángulo", "El triángulo tiene tres lados.", "Un triángulo tiene tres lados y tres esquinas.", "Levanta tres dedos."),
        ("Busca figuras", "¿Qué figura ves?", "Busca algo redondo, algo cuadrado o algo con forma de triángulo.", "Señala una figura."),
        ("¡Muy bien!", "Círculo. Cuadrado. Triángulo.", "Aprendiste tres figuras. ¡Círculo, cuadrado, triángulo!", "Aplaude tres veces."),
    ),
    ("counting_1_10", "es"): (
        ("¡A contar!", "Los números dicen cuántos hay.", "Hoy vamos a contar del uno al diez.", "Toca tus rodillas y prepárate."),
        ("Uno y dos", "Un sol. Dos zapatos.", "Uno es una cosa. Dos son dos cosas.", "Muestra un dedo y luego dos."),
        ("Tres y cuatro", "Tres estrellas. Cuatro bloques.", "Cuenta despacio: uno, dos, tres. Ahora cuenta cuatro bloques.", "Muestra tres dedos y luego cuatro."),
        ("Cinco y seis", "Cinco dedos. Seis puntos.", "Una mano tiene cinco dedos. Agrega uno más para hacer seis.", "Mueve los cinco dedos."),
        ("Siete y ocho", "Siete días. Ocho patas.", "La semana tiene siete días. La araña tiene ocho patas.", "Da siete aplausos."),
        ("Nueve y diez", "Nueve estrellas. Diez dedos.", "El nueve va antes del diez. Tienes diez dedos en los pies.", "Cuenta hasta diez con Theodore."),
        ("Tu turno", "¿Cuántos puntos hay?", "Cuenta cada punto una vez. Di el último número.", "Cuenta los cinco puntos."),
        ("¡Contamos!", "1 2 3 4 5 6 7 8 9 10", "¡Muy bien! Contaste hasta diez.", "Haz una reverencia."),
    ),
    ("addition_to_10", "es"): (
        ("Sumar es juntar", "Sumar junta los grupos.", "Cuando sumamos, juntamos grupos para saber cuántos hay en total.", "Junta tus manos."),
        ("Uno más uno", "1 + 1 = 2", "Una manzana más una manzana son dos manzanas.", "Muestra un dedo en cada mano."),
        ("Dos más uno", "2 + 1 = 3", "Dos puntos más un punto son tres puntos.", "Cuenta los tres puntos."),
        ("Dos más dos", "2 + 2 = 4", "Dos bloques más dos bloques son cuatro bloques.", "Cuenta: uno, dos, tres, cuatro."),
        ("Tres más dos", "3 + 2 = 5", "Empieza con tres. Agrega dos más. Ahora hay cinco.", "Sigue contando: cuatro, cinco."),
        ("Tu turno", "4 + 1 = ?", "Cuatro estrellas más una estrella. ¿Cuántas estrellas hay en total?", "Di la respuesta: cinco."),
        ("¡Campeón!", "Juntar. Contar. Total.", "Ya sabes sumar: junta los grupos, cuenta todo y di el total.", "Haz un signo de más con los brazos."),
    ),
    ("story_sequence", "es"): (
        ("Los cuentos tienen orden", "Las cosas pasan en orden.", "Un cuento tiene sucesos en orden. Decimos primero, después y al final.", "Levanta uno, dos y tres dedos."),
        ("Primero", "Primero, Mía sembró una semilla.", "Primero dice qué pasó al comienzo. Mía sembró una semilla.", "Di: primero la sembró."),
        ("Después", "Después, Mía la regó.", "Después dice qué pasó luego. Mía le dio agua a la semilla.", "Finge que riegas una semilla."),
        ("Al final", "Al final, creció una flor.", "Al final dice cómo terminó el cuento. Creció una flor bonita.", "Abre las manos como una flor."),
        ("Cuéntalo en orden", "Sembrar. Regar. Florecer.", "Cuenta el cuento: primero sembrar, después regar, al final florecer.", "Señala de izquierda a derecha."),
        ("El orden importa", "El orden ayuda a entender.", "Si mezclamos los sucesos, el cuento confunde. El orden lo hace claro.", "Di cuál fue el primer suceso."),
        ("¡Muy bien!", "Primero. Después. Al final.", "Ya puedes poner un cuento en orden y contarlo.", "Cuenta otra vez el cuento de la semilla."),
    ),
    ("animal_habitats", "es"): (
        ("El hábitat es un hogar", "Los animales necesitan comida, agua y refugio.", "Un hábitat es el hogar de un ser vivo. Le da lo que necesita.", "Di: hábitat quiere decir hogar."),
        ("Bosque", "El bosque tiene muchos árboles.", "El venado y el búho viven en el bosque. Los árboles dan comida y refugio.", "Ponte alto como un árbol."),
        ("Océano", "El océano es agua salada.", "Los peces y las ballenas viven en el océano. Su cuerpo les ayuda a nadar.", "Mueve las manos como aletas."),
        ("Desierto", "El desierto es muy seco.", "El camello vive en el desierto seco. Aguanta mucho tiempo sin agua.", "Camina sobre arena caliente."),
        ("Zona polar", "Las zonas polares son frías.", "El oso polar tiene pelo grueso y grasa para no tener frío.", "Abrázate para calentarte."),
        ("Busca el hogar", "¿Dónde vive un pez?", "Piensa qué necesita un pez. Vive en el agua, así que su hogar es el océano.", "Di: el pez vive en el océano."),
        ("¡Científico!", "Bosque. Océano. Desierto. Polar.", "Uniste animales con cuatro hábitats. Cada hábitat cubre necesidades especiales.", "Nombra un animal y su hábitat."),
    ),
    # Sound-specific. NOT translations: Spanish words chosen so each letter and
    # sight word actually teaches the intended sound in Spanish.
    ("letter_sounds", "es"): (
        ("Las letras suenan", "Vamos a oír A, B y C.", "Las letras tienen nombre y sonido. Hoy conocemos A, B y C.", "Canta A, B, C."),
        ("A suena /a/", "A de avión.", "La A suena /a/, como en avión. A, avión.", "Di avión despacio."),
        ("B suena /b/", "B de bota.", "La B suena /b/, como en bota. B, bota.", "Da un paso con tus botas."),
        ("C suena /k/", "C de casa.", "La C puede sonar /k/, como en casa. C, casa.", "Dibuja una casa en el aire."),
        ("Busca el sonido", "¿Qué letra empieza bota?", "Escucha: bota. Bota empieza con el sonido /b/. ¿Qué letra es?", "Señala la B."),
        ("Lee conmigo", "A avión. B bota. C casa.", "Lee conmigo: A avión. B bota. C casa.", "Di cada par en voz alta."),
        ("¡Estrella!", "Ya conoces A, B y C.", "¡Escuchaste muy bien! Conociste tres letras y sus sonidos.", "Dibuja tu letra favorita."),
    ),
    ("sight_words", "es"): (
        ("Palabras que leemos rápido", "Son palabras que recordamos.", "Estas palabras ayudan a leer con fluidez. Aprenderemos cinco.", "Señala tus ojos."),
        ("Yo", "Yo habla de mí.", "La palabra yo habla de mí. Lee: Yo puedo saltar.", "Di: Yo puedo saltar."),
        ("Veo", "Veo quiere decir mirar.", "La palabra veo quiere decir mirar. Lee: Yo veo un gato.", "Señala y di: yo veo."),
        ("El", "El señala una cosa.", "Lee esta palabra: el. Lee: El sol calienta.", "Busca la palabra el."),
        ("Un", "Un quiere decir uno.", "La palabra un quiere decir uno. Lee: Un perro corre.", "Di: un perro."),
        ("Es", "Es habla de ahora.", "Lee esta palabra: es. Lee: El gato es suave.", "Di: es suave."),
        ("Lee una oración", "Yo veo un gato.", "Ahora lee la oración conmigo: Yo veo un gato.", "Léela dos veces."),
        ("¡Estrella!", "Yo. Veo. El. Un. Es.", "Leíste cinco palabras. Practícalas otra vez mañana.", "Chócala contigo mismo."),
    ),
    # ------------------------------------------------------------------ Khmer
    ("colors", "km"): (
        ("សួស្តី ពណ៌!", "យើងនឹងរកពណ៌បួន។", "សួស្តីក្មេងតូច! ថ្ងៃនេះយើងនឹងរកពណ៌ភ្លឺៗបួន។", "ស្វាគមន៍ពណ៌ទាំងអស់។"),
        ("ក្រហម", "ក្រហម ភ្លឺ។", "នេះជាពណ៌ក្រហម។ ក្រហមដូចផ្លែប៉ោម។", "រកអ្វីៗពណ៌ក្រហម។"),
        ("ខៀវ", "ខៀវ ត្រជាក់។", "នេះជាពណ៌ខៀវ។ ខៀវដូចមេឃ។", "ចង្អុលទៅមេឃខៀវ។"),
        ("លឿង", "លឿង ចាំង។", "នេះជាពណ៌លឿង។ លឿងដូចព្រះអាទិត្យ។", "ធ្វើព្រះអាទិត្យធំៗ។"),
        ("បៃតង", "បៃតង ដុះ។", "នេះជាពណ៌បៃតង។ បៃតងដូចស្លឹកឈើ។", "ធ្វើដូចរុក្ខជាតិដុះ។"),
        ("រកពណ៌", "តើអ្នកឃើញពណ៌ទេ?", "មើលជុំវិញ។ រកអ្វីៗពណ៌ក្រហម ខៀវ លឿង ឬបៃតង។", "និយាយពណ៌ដែលអ្នករកឃើញ។"),
        ("ល្អណាស់!", "ក្រហម។ ខៀវ។ លឿង។ បៃតង។", "អ្នករៀនពណ៌បួនហើយ! និយាយជាមួយខ្ញុំ៖ ក្រហម ខៀវ លឿង បៃតង។", "ទះដៃឲ្យខ្លួនឯង។"),
    ),
    ("shapes", "km"): (
        ("សួស្តី រូបរាង!", "រូបរាងនៅជុំវិញយើង។", "ថ្ងៃនេះយើងស្គាល់រង្វង់ ការេ និងត្រីកោណ។", "គូររូបរាងក្នុងខ្យល់។"),
        ("រង្វង់", "រង្វង់ មូល។", "រង្វង់មូល។ វាគ្មានជ្រុង។", "ធ្វើរង្វង់ដោយដៃ។"),
        ("ការេ", "ការេមានបួនជ្រុង។", "ការេមានជ្រុងស្មើគ្នាបួន និងជ្រុងបួន។", "រាប់ជ្រុងបួនដោយម្រាមដៃ។"),
        ("ត្រីកោណ", "ត្រីកោណមានបីជ្រុង។", "ត្រីកោណមានបីជ្រុង និងបីជ្រុងកាច់។", "លើកម្រាមដៃបី។"),
        ("រករូបរាង", "តើអ្នកឃើញរូបរាងអ្វី?", "រកអ្វីៗមូល ការេ ឬត្រីកោណ។", "ចង្អុលរូបរាងមួយ។"),
        ("ល្អណាស់!", "រង្វង់។ ការេ។ ត្រីកោណ។", "អ្នករៀនរូបរាងបីហើយ! រង្វង់ ការេ ត្រីកោណ។", "ទះដៃបីដង។"),
    ),
    ("counting_1_10", "km"): (
        ("តោះរាប់!", "លេខប្រាប់ចំនួន។", "ថ្ងៃនេះយើងរាប់ពីមួយដល់ដប់។", "ទះលើភ្លៅ ត្រៀមខ្លួន។"),
        ("មួយ និងពីរ", "ព្រះអាទិត្យមួយ។ ស្បែកជើងពីរ។", "មួយ គឺរបស់មួយ។ ពីរ គឺរបស់ពីរ។", "បង្ហាញម្រាមមួយ រួចពីរ។"),
        ("បី និងបួន", "ផ្កាយបី។ ប្លុកបួន។", "រាប់យឺតៗ៖ មួយ ពីរ បី។ រាប់ប្លុកបួន។", "បង្ហាញម្រាមបី រួចបួន។"),
        ("ប្រាំ និងប្រាំមួយ", "ម្រាមប្រាំ។ ចំណុចប្រាំមួយ។", "ដៃមួយមានម្រាមប្រាំ។ បន្ថែមមួយទៀតបានប្រាំមួយ។", "កម្រើកម្រាមប្រាំ។"),
        ("ប្រាំពីរ និងប្រាំបី", "ថ្ងៃប្រាំពីរ។ ជើងប្រាំបី។", "សប្តាហ៍មានប្រាំពីរថ្ងៃ។ ពីងពាងមានជើងប្រាំបី។", "ទះដៃប្រាំពីរ។"),
        ("ប្រាំបួន និងដប់", "ផ្កាយប្រាំបួន។ ម្រាមជើងដប់។", "ប្រាំបួននៅមុនដប់។ អ្នកមានម្រាមជើងដប់។", "រាប់ដល់ដប់ជាមួយ Theodore។"),
        ("វេនអ្នក", "តើមានចំណុចប៉ុន្មាន?", "រាប់ចំណុចម្តងមួយ។ និយាយលេខចុងក្រោយ។", "រាប់ចំណុចប្រាំ។"),
        ("យើងរាប់បាន!", "1 2 3 4 5 6 7 8 9 10", "ពូកែណាស់! អ្នករាប់ដល់ដប់។", "ឱនក្បាលមួយ។"),
    ),
    ("addition_to_10", "km"): (
        ("បូក គឺបញ្ចូលគ្នា", "បូក បញ្ចូលក្រុមចូលគ្នា។", "ពេលបូក យើងបញ្ចូលក្រុមដើម្បីដឹងចំនួនសរុប។", "យកដៃមកជិតគ្នា។"),
        ("មួយបូកមួយ", "1 + 1 = 2", "ផ្លែប៉ោមមួយបូកផ្លែប៉ោមមួយ បានពីរ។", "បង្ហាញម្រាមមួយក្នុងដៃនីមួយៗ។"),
        ("ពីរបូកមួយ", "2 + 1 = 3", "ចំណុចពីរបូកមួយទៀត បានបី។", "រាប់ចំណុចទាំងបី។"),
        ("ពីរបូកពីរ", "2 + 2 = 4", "ប្លុកពីរបូកប្លុកពីរ បានបួន។", "រាប់៖ មួយ ពីរ បី បួន។"),
        ("បីបូកពីរ", "3 + 2 = 5", "ចាប់ផ្តើមពីបី។ បន្ថែមពីរ។ ឥឡូវមានប្រាំ។", "រាប់បន្ត៖ បួន ប្រាំ។"),
        ("វេនអ្នក", "4 + 1 = ?", "ផ្កាយបួនបូកផ្កាយមួយ។ សរុបប៉ុន្មានផ្កាយ?", "និយាយចម្លើយ៖ ប្រាំ។"),
        ("តារាបូក!", "បញ្ចូល។ រាប់។ សរុប។", "អ្នកចេះបូក៖ បញ្ចូលក្រុម រាប់ទាំងអស់ និយាយចំនួនសរុប។", "ធ្វើសញ្ញាបូកដោយដៃ។"),
    ),
    ("story_sequence", "km"): (
        ("រឿងមានលំដាប់", "ព្រឹត្តិការណ៍កើតឡើងតាមលំដាប់។", "រឿងមានព្រឹត្តិការណ៍តាមលំដាប់។ យើងនិយាយ ដំបូង បន្ទាប់ ចុងក្រោយ។", "លើកម្រាមមួយ ពីរ បី។"),
        ("ដំបូង", "ដំបូង មីយ៉ាដាំគ្រាប់ពូជ។", "ដំបូង ប្រាប់អំពីការចាប់ផ្តើម។ មីយ៉ាដាំគ្រាប់ពូជ។", "និយាយ៖ ដំបូងគាត់ដាំ។"),
        ("បន្ទាប់", "បន្ទាប់ មីយ៉ាស្រោចទឹក។", "បន្ទាប់ ប្រាប់អ្វីកើតក្រោយ។ មីយ៉ាស្រោចទឹកឲ្យគ្រាប់។", "ធ្វើដូចស្រោចទឹក។"),
        ("ចុងក្រោយ", "ចុងក្រោយ ផ្កាបានរីក។", "ចុងក្រោយ ប្រាប់ពីទីបញ្ចប់។ ផ្កាស្អាតបានរីក។", "បើកដៃដូចផ្កា។"),
        ("និយាយតាមលំដាប់", "ដាំ។ ស្រោច។ រីក។", "និយាយឡើងវិញ៖ ដំបូងដាំ បន្ទាប់ស្រោច ចុងក្រោយរីក។", "ចង្អុលពីឆ្វេងទៅស្តាំ។"),
        ("ហេតុអ្វីលំដាប់សំខាន់", "លំដាប់ជួយឲ្យរឿងច្បាស់។", "បើយើងលាយព្រឹត្តិការណ៍ រឿងច្របូកច្របល់។ លំដាប់ធ្វើឲ្យច្បាស់។", "ប្រាប់ព្រឹត្តិការណ៍ដំបូង។"),
        ("តារារឿង!", "ដំបូង។ បន្ទាប់។ ចុងក្រោយ។", "អ្នកចេះរៀបរឿងតាមលំដាប់ និងនិទានវា។", "និទានរឿងគ្រាប់ពូជម្តងទៀត។"),
    ),
    ("animal_habitats", "km"): (
        ("ជម្រក គឺផ្ទះ", "សត្វត្រូវការអាហារ ទឹក និងទីជម្រក។", "ជម្រកគឺផ្ទះរបស់សត្វ។ វាផ្តល់នូវអ្វីដែលសត្វត្រូវការ។", "និយាយ៖ ជម្រកមានន័យថាផ្ទះ។"),
        ("ព្រៃ", "ព្រៃមានដើមឈើច្រើន។", "ក្តាន់ និងសត្វមៀមរស់នៅក្នុងព្រៃ។ ដើមឈើផ្តល់អាហារ និងទីជម្រក។", "ធ្វើដូចដើមឈើខ្ពស់។"),
        ("មហាសមុទ្រ", "មហាសមុទ្រ ជាទឹកប្រៃ។", "ត្រី និងផ្សោតរស់នៅក្នុងមហាសមុទ្រ។ រាងកាយជួយឲ្យវាហែល។", "កម្រើកដៃដូចព្រុយត្រី។"),
        ("វាលខ្សាច់", "វាលខ្សាច់ ស្ងួតខ្លាំង។", "អូដ្ឋរស់នៅវាលខ្សាច់ស្ងួត។ វាអាចនៅបានយូរដោយគ្មានទឹក។", "ដើរលើខ្សាច់ក្តៅ។"),
        ("តំបន់ប៉ូល", "តំបន់ប៉ូល ត្រជាក់។", "ខ្លាឃ្មុំប៉ូលមានរោមក្រាស់ និងខ្លាញ់ជួយឲ្យកក់ក្តៅ។", "ឱបខ្លួនឯងឲ្យកក់ក្តៅ។"),
        ("រកផ្ទះ", "តើត្រីរស់នៅឯណា?", "គិតអំពីអ្វីដែលត្រីត្រូវការ។ ត្រីរស់នៅក្នុងទឹក ដូច្នេះជម្រករបស់វាគឺមហាសមុទ្រ។", "និយាយ៖ ត្រីរស់នៅមហាសមុទ្រ។"),
        ("អ្នកវិទ្យាសាស្ត្រ!", "ព្រៃ។ មហាសមុទ្រ។ វាលខ្សាច់។ ប៉ូល។", "អ្នកផ្គូផ្គងសត្វទៅជម្រកបួន។ ជម្រកនីមួយៗបំពេញតម្រូវការពិសេស។", "ប្រាប់សត្វមួយ និងជម្រករបស់វា។"),
    ),
    # Khmer reading = Khmer script (ក ខ គ), not English letters. Symbol override.
    ("letter_sounds", "km"): (
        ("អក្សរខ្មែរ", "យើងនឹងស្គាល់អក្សរបី។", "អក្សរខ្មែរមានសំឡេង។ ថ្ងៃនេះយើងស្គាល់ ក ខ គ។", "អានតាមខ្ញុំ៖ ក ខ គ។", "ក ខ គ"),
        ("ក", "ក ដូចជា កូន។", "នេះជាអក្សរ ក។ ក ដូចជាពាក្យ កូន។", "និយាយ កូន យឺតៗ។", "ក"),
        ("ខ", "ខ ដូចជា ខ្លា។", "នេះជាអក្សរ ខ។ ខ ដូចជាពាក្យ ខ្លា។", "ធ្វើសំឡេងខ្លា។", "ខ"),
        ("គ", "គ ដូចជា គោ។", "នេះជាអក្សរ គ។ គ ដូចជាពាក្យ គោ។", "ធ្វើដូចគោ។", "គ"),
        ("រកសំឡេង", "តើអក្សរណាចាប់ផ្តើម ខ្លា?", "ស្តាប់៖ ខ្លា។ ខ្លា ចាប់ផ្តើមដោយ ខ។ តើអក្សរណា?", "ចង្អុល ខ។", "ក ខ គ"),
        ("អានជាមួយខ្ញុំ", "ក កូន។ ខ ខ្លា។ គ គោ។", "អានជាមួយខ្ញុំ៖ ក កូន។ ខ ខ្លា។ គ គោ។", "អានឮៗម្តងមួយ។", "ក ខ គ"),
        ("តារាអក្សរ!", "អ្នកស្គាល់ ក ខ គ។", "ពូកែណាស់! អ្នកស្គាល់អក្សរបីហើយ។", "គូរអក្សរដែលអ្នកចូលចិត្ត។", "★"),
    ),
    ("sight_words", "km"): (
        ("ពាក្យដែលយើងចាំ", "ពាក្យទាំងនេះយើងចាំបានលឿន។", "ពាក្យទាំងនេះជួយឲ្យយើងអានលឿន។ យើងរៀនប្រាំ។", "ចង្អុលភ្នែករបស់អ្នក។", "ពាក្យ"),
        ("ខ្ញុំ", "ខ្ញុំ គឺជាខ្លួនខ្ញុំ។", "ពាក្យ ខ្ញុំ មានន័យថាខ្លួនខ្ញុំ។ អាន៖ ខ្ញុំអាចលោត។", "និយាយ៖ ខ្ញុំអាចលោត។", "ខ្ញុំ"),
        ("ឃើញ", "ឃើញ គឺមើល។", "ពាក្យ ឃើញ មានន័យថាមើល។ អាន៖ ខ្ញុំឃើញឆ្មា។", "ចង្អុលហើយនិយាយ៖ ខ្ញុំឃើញ។", "ឃើញ"),
        ("នេះ", "នេះ ចង្អុលរបស់មួយ។", "អានពាក្យនេះ៖ នេះ។ អាន៖ នេះជាថ្ងៃ។", "រកពាក្យ នេះ។", "នេះ"),
        ("មួយ", "មួយ គឺលេខមួយ។", "ពាក្យ មួយ មានន័យថាមួយ។ អាន៖ ឆ្កែមួយ។", "និយាយ៖ ឆ្កែមួយ។", "មួយ"),
        ("ជា", "ជា ប្រាប់អំពីឥឡូវ។", "អានពាក្យនេះ៖ ជា។ អាន៖ ឆ្មាជាសត្វទន់។", "និយាយ៖ ជាទន់។", "ជា"),
        ("អានប្រយោគ", "ខ្ញុំឃើញឆ្មាមួយ។", "ឥឡូវអានប្រយោគជាមួយខ្ញុំ៖ ខ្ញុំឃើញឆ្មាមួយ។", "អានពីរដង។", "ប្រយោគ"),
        ("តារាពាក្យ!", "ខ្ញុំ។ ឃើញ។ នេះ។ មួយ។ ជា។", "អ្នកអានពាក្យប្រាំ។ ថ្ងៃស្អែកហាត់ម្តងទៀត។", "ទះដៃជាមួយខ្លួនឯង។", "★"),
    ),
    # ----------------------------------------------------------- Mandarin (zh)
    ("colors", "zh"): (
        ("你好，颜色！", "我们要找四种颜色。", "小朋友你好！今天我们要找四种明亮的颜色。", "跟颜色打招呼。"),
        ("红色", "红色很鲜艳。", "这是红色。红色像苹果。", "找一样红色的东西。"),
        ("蓝色", "蓝色很清凉。", "这是蓝色。蓝色像天空。", "指向蓝色的天空。"),
        ("黄色", "黄色会发光。", "这是黄色。黄色像太阳。", "用手臂做个大太阳。"),
        ("绿色", "绿色会生长。", "这是绿色。绿色像树叶。", "像植物一样长大。"),
        ("找颜色", "你能看到颜色吗？", "看看四周。找红色、蓝色、黄色或绿色的东西。", "说出你找到的颜色。"),
        ("真棒！", "红。蓝。黄。绿。", "你学会了四种颜色！跟我说：红、蓝、黄、绿。", "给自己鼓鼓掌。"),
    ),
    ("shapes", "zh"): (
        ("你好，形状！", "形状到处都有。", "今天我们认识圆形、正方形和三角形。", "在空中画个形状。"),
        ("圆形", "圆形是圆的。", "圆形是圆的，没有角。", "用手臂做个圆。"),
        ("正方形", "正方形有四条边。", "正方形有四条一样长的边和四个角。", "用手指数四条边。"),
        ("三角形", "三角形有三条边。", "三角形有三条边和三个角。", "举起三根手指。"),
        ("找形状", "你看到什么形状？", "找圆的、正方的，或三角形的东西。", "指出一个形状。"),
        ("真棒！", "圆形。正方形。三角形。", "你学会了三个形状。圆形、正方形、三角形！", "拍手三下。"),
    ),
    ("counting_1_10", "zh"): (
        ("我们来数数！", "数字告诉我们有多少。", "今天我们从一数到十。", "拍拍膝盖，准备好。"),
        ("一和二", "一个太阳。两只鞋。", "一是一样东西。二是两样东西。", "先伸一根手指，再伸两根。"),
        ("三和四", "三颗星。四个方块。", "慢慢数：一、二、三。再数四个方块。", "先伸三根手指，再伸四根。"),
        ("五和六", "五根手指。六个点。", "一只手有五根手指。再加一个就是六。", "动动五根手指。"),
        ("七和八", "七天。八条腿。", "一个星期有七天。蜘蛛有八条腿。", "拍七下手。"),
        ("九和十", "九颗星。十个脚趾。", "九在十前面。你有十个脚趾。", "和 Theodore 一起数到十。"),
        ("该你了", "有几个点？", "每个点数一次。说出最后一个数。", "数五个点。"),
        ("我们数完了！", "1 2 3 4 5 6 7 8 9 10", "太棒了！你数到了十。", "鞠个躬。"),
    ),
    ("addition_to_10", "zh"): (
        ("加法是合起来", "加法把两组合起来。", "加的时候，我们把两组合起来，看一共有多少。", "把两只手合起来。"),
        ("一加一", "1 + 1 = 2", "一个苹果加一个苹果，是两个苹果。", "每只手伸一根手指。"),
        ("二加一", "2 + 1 = 3", "两个点加一个点，是三个点。", "数出三个点。"),
        ("二加二", "2 + 2 = 4", "两个方块加两个方块，是四个方块。", "数：一、二、三、四。"),
        ("三加二", "3 + 2 = 5", "先有三个。再加两个。现在有五个。", "接着数：四、五。"),
        ("该你了", "4 + 1 = ?", "四颗星加一颗星。一共几颗星？", "说出答案：五。"),
        ("加法小明星！", "合起来。数一数。总数。", "你会加法了：合起来、数一数、说出总数。", "用手臂做个加号。"),
    ),
    ("story_sequence", "zh"): (
        ("故事有顺序", "事情按顺序发生。", "故事里的事情有顺序。我们说首先、然后、最后。", "举起一、二、三根手指。"),
        ("首先", "首先，小美种下种子。", "首先讲开头发生了什么。小美种下一颗种子。", "说：首先她种下。"),
        ("然后", "然后，小美浇水。", "然后讲接下来发生了什么。小美给种子浇水。", "假装给种子浇水。"),
        ("最后", "最后，开出一朵花。", "最后讲故事怎么结束。开出一朵漂亮的花。", "张开手像一朵花。"),
        ("按顺序说", "种。浇。开花。", "再讲一遍：首先种，然后浇水，最后开花。", "从左到右指着说。"),
        ("顺序很重要", "顺序帮我们看懂故事。", "如果顺序乱了，故事就会让人糊涂。顺序让它清楚。", "说出第一件事。"),
        ("故事小明星！", "首先。然后。最后。", "你会把故事按顺序讲出来了。", "再讲一遍种子的故事。"),
    ),
    ("animal_habitats", "zh"): (
        ("栖息地是家", "动物需要食物、水和住所。", "栖息地是动物的家。它给动物需要的东西。", "说：栖息地就是家。"),
        ("森林", "森林里有很多树。", "鹿和猫头鹰住在森林里。树给它们食物和住所。", "像大树一样站高。"),
        ("海洋", "海洋是咸水。", "鱼和鲸鱼住在海洋里。它们的身体帮它们游泳。", "像鱼鳍一样动动手。"),
        ("沙漠", "沙漠很干。", "骆驼住在干旱的沙漠。它很久不喝水也可以。", "假装走在热沙上。"),
        ("极地", "极地很冷。", "北极熊有厚厚的毛和脂肪，帮它保暖。", "抱住自己取暖。"),
        ("找找家", "鱼住在哪里？", "想想鱼需要什么。鱼住在水里，所以它的家是海洋。", "说：鱼住在海洋。"),
        ("小科学家！", "森林。海洋。沙漠。极地。", "你把动物配到了四个栖息地。每个栖息地满足特别的需要。", "说一个动物和它的栖息地。"),
    ),
    # Mandarin reading = Chinese characters, not English letters. Symbol override.
    ("letter_sounds", "zh"): (
        ("认识汉字", "我们来认识三个字。", "汉字很有意思。今天我们认识三个字：人、山、水。", "跟我读：人、山、水。", "字"),
        ("人", "人就是人。", "这个字是“人”，读 rén。像一个人在走路。", "站起来像个人。", "人"),
        ("山", "山很高。", "这个字是“山”，读 shān。像三座山峰。", "用手做出山的样子。", "山"),
        ("水", "水会流动。", "这个字是“水”，读 shuǐ。像流动的水。", "用手比出水流。", "水"),
        ("找一找", "哪个字是“山”？", "听：shān。哪个字是“山”呢？", "指出“山”。", "人山水"),
        ("跟我读", "人。山。水。", "跟我一起读：人、山、水。", "大声读出每个字。", "人山水"),
        ("识字小明星！", "你认识人、山、水。", "太棒了！你认识了三个汉字。", "写出你最喜欢的字。", "★"),
    ),
    ("sight_words", "zh"): (
        ("我们记得的字", "这些字我们记得很快。", "这些常用字帮我们读得快。我们学五个。", "指指你的眼睛。", "常用字"),
        ("我", "“我”是我自己。", "这个字是“我”，读 wǒ。读：我会跳。", "说：我会跳。", "我"),
        ("你", "“你”是别人。", "这个字是“你”，读 nǐ。读：你好。", "跟朋友说：你好。", "你"),
        ("好", "“好”很棒。", "这个字是“好”，读 hǎo。读：你好。", "竖起大拇指说好。", "好"),
        ("是", "“是”表示现在。", "这个字是“是”，读 shì。读：我是小朋友。", "说：我是……", "是"),
        ("大", "“大”就是大。", "这个字是“大”，读 dà。读：大太阳。", "张开手臂做“大”。", "大"),
        ("读一句", "你好，我很好。", "跟我读整句：你好，我很好。", "读两遍。", "句"),
        ("识字小明星！", "我。你。好。是。大。", "你读了五个常用字。明天再练习。", "跟自己击掌。", "★"),
    ),
}


# Newly authored languages awaiting a native-speaker review pass. Their lessons
# are used, but the UI flags them so a teacher can double-check the wording.
NEEDS_NATIVE_REVIEW = frozenset({"km", "zh"})


_lock = threading.RLock()


def curated_languages(topic_id: str) -> list[str]:
    return sorted(lang for (topic, lang) in _CURATED if topic == topic_id)


def _cache_path(data_dir: Path, topic_id: str, language: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", f"{topic_id}__{language}")
    return data_dir / "i18n" / f"{safe}.json"


def _load_cache(path: Path) -> tuple[TranslatedBeat, ...] | None:
    if not path.is_file():
        return None
    try:
        rows = json.loads(path.read_text(encoding="utf-8")).get("beats", [])
        return tuple(
            TranslatedBeat(r["title"], r["words"], r["say"], r["activity"]) for r in rows
        )
    except Exception:  # noqa: BLE001 — a broken cache must never block a lesson
        return None


def _save_cache(path: Path, beats: tuple[TranslatedBeat, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "beats": [
            {"title": b.title, "words": b.words, "say": b.say, "activity": b.activity}
            for b in beats
        ]
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _xai_translate(
    beats: tuple[tuple[str, str, str, str], ...],
    language: str,
    *,
    timeout_s: float = 40.0,
) -> tuple[TranslatedBeat, ...] | None:
    """Real Grok call constrained to tiny child vocabulary. None on any failure."""
    api_key = os.environ.get("XAI_API_KEY", "").strip()
    if not api_key:
        return None
    base = os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1").rstrip("/")
    model = os.environ.get("XAI_MODEL", "").strip() or XAI_DEFAULT_MODEL
    target = language_name(language)
    payload_in = [
        {"i": i, "title": t, "words": w, "say": s, "activity": a}
        for i, (t, w, s, a) in enumerate(beats)
    ]
    system = (
        f"You translate lessons for children aged 4 to 8 into {target}. "
        "Use the simplest everyday words a young child knows. Keep each field as "
        "short as the English. Keep numbers and math symbols unchanged. Do not add "
        "commentary. Return ONLY a JSON array of the same length with the keys "
        "i, title, words, say, activity."
    )
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload_in, ensure_ascii=False)},
        ],
        "temperature": 0.2,
        "max_tokens": 2000,
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        text = raw["choices"][0]["message"]["content"].strip()
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
        rows = json.loads(text)
        if not isinstance(rows, list) or len(rows) != len(beats):
            return None
        rows = sorted(rows, key=lambda r: int(r.get("i", 0)))
        out: list[TranslatedBeat] = []
        for row, fallback in zip(rows, beats):
            out.append(
                TranslatedBeat(
                    str(row.get("title") or fallback[0]).strip(),
                    str(row.get("words") or fallback[1]).strip(),
                    str(row.get("say") or fallback[2]).strip(),
                    str(row.get("activity") or fallback[3]).strip(),
                )
            )
        return tuple(out)
    except Exception:  # noqa: BLE001 — never fail a lesson because of the network
        return None


def translate_beats(
    *,
    topic_id: str,
    language: str,
    beats: tuple[tuple[str, str, str, str], ...],
    data_dir: Path | None = None,
    allow_xai: bool = True,
) -> TranslationResult:
    """Return child-safe text in ``language`` plus where that text came from."""
    lang = normalize_language(language)
    english = tuple(TranslatedBeat(*b) for b in beats)
    if lang == "en":
        return TranslationResult(english, "curated")

    curated = _CURATED.get((topic_id, lang))
    if curated is not None:
        note = ""
        if lang in NEEDS_NATIVE_REVIEW:
            note = (
                f"Hand-authored {language_name(lang)}; pending native-speaker review."
            )
        return TranslationResult(
            tuple(_beat_from_row(row) for row in curated), "curated", note=note
        )

    if topic_id in SOUND_SPECIFIC_TOPICS:
        available = ", ".join(curated_languages(topic_id)) or "en"
        return TranslationResult(
            english,
            "english",
            note=(
                "This lesson teaches English letter sounds, so it is not machine "
                f"translated. Reviewed versions exist for: {available}."
            ),
        )

    if data_dir is not None:
        cached = _load_cache(_cache_path(data_dir, topic_id, lang))
        if cached is not None and len(cached) == len(beats):
            return TranslationResult(cached, "xai", note="cached Grok translation")

    if allow_xai:
        with _lock:
            translated = _xai_translate(beats, lang)
        if translated is not None:
            if data_dir is not None:
                _save_cache(_cache_path(data_dir, topic_id, lang), translated)
            return TranslationResult(
                translated,
                "xai",
                note="machine translated by Grok; review before classroom use",
            )

    return TranslationResult(
        english,
        "english",
        note=(
            f"No reviewed {language_name(lang)} text yet and Grok translation is "
            "unavailable, so the words stay English. Set XAI_API_KEY to translate."
        ),
    )
