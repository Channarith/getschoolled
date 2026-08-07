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


@dataclass(frozen=True)
class TranslatedBeat:
    title: str
    words: str
    say: str
    activity: str


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
}


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
    model = os.environ.get("XAI_MODEL", "grok-2-1212")
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
        return TranslationResult(
            tuple(TranslatedBeat(*row) for row in curated), "curated"
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
