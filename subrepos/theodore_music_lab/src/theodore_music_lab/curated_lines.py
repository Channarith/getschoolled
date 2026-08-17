"""Hand-authored full-line translations for the featured MP3 songs.

Tier 1 of the translation stack: every unique lyric line of the three featured
songs, translated line-for-line so a learner reads a real sentence rather than a
word list. Keys are the normalized English line (see ``normalize``).

All platform meaning languages (26 non-English) are curated for the featured
pack. Romance lines live inline; the remaining languages load from
``data/curated_lines_extra.json`` so the Python module stays readable.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .catalog import MEANING_LANGUAGES

# Every non-English platform language is curated for featured-song lines.
CURATED_LANGUAGES: tuple[str, ...] = tuple(code for code in MEANING_LANGUAGES if code != "en")


def normalize(text: str) -> str:
    """Lookup key for a lyric line: lowercase, punctuation-free, single-spaced."""
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", text.lower()).split())


# Romance baseline (kept in-repo for easy review). Extra languages merge from JSON.
CURATED_LINES: dict[str, dict[str, str]] = {
    "i go to work": {"es": "Voy al trabajo", "fr": "Je vais au travail", "de": "Ich gehe zur Arbeit", "it": "Vado al lavoro", "pt": "Eu vou para o trabalho"},
    "i go to school": {"es": "Voy a la escuela", "fr": "Je vais à l'école", "de": "Ich gehe zur Schule", "it": "Vado a scuola", "pt": "Eu vou para a escola"},
    "i say hello": {"es": "Digo hola", "fr": "Je dis bonjour", "de": "Ich sage hallo", "it": "Dico ciao", "pt": "Eu digo olá"},
    "i learn new rules": {"es": "Aprendo reglas nuevas", "fr": "J'apprends de nouvelles règles", "de": "Ich lerne neue Regeln", "it": "Imparo nuove regole", "pt": "Eu aprendo regras novas"},
    "at the bank": {"es": "En el banco", "fr": "À la banque", "de": "In der Bank", "it": "In banca", "pt": "No banco"},
    "i count my cash": {"es": "Cuento mi dinero", "fr": "Je compte mon argent", "de": "Ich zähle mein Geld", "it": "Conto i miei soldi", "pt": "Eu conto meu dinheiro"},
    "at the office": {"es": "En la oficina", "fr": "Au bureau", "de": "Im Büro", "it": "In ufficio", "pt": "No escritório"},
    "i make a plan": {"es": "Hago un plan", "fr": "Je fais un plan", "de": "Ich mache einen Plan", "it": "Faccio un piano", "pt": "Eu faço um plano"},
    "walk to the store": {"es": "Camino a la tienda", "fr": "Je marche jusqu'au magasin", "de": "Ich gehe zum Geschäft", "it": "Cammino fino al negozio", "pt": "Eu caminho até a loja"},
    "walk to the bus": {"es": "Camino al autobús", "fr": "Je marche jusqu'au bus", "de": "Ich gehe zum Bus", "it": "Cammino fino all'autobus", "pt": "Eu caminho até o ônibus"},
    "pack my bag": {"es": "Preparo mi bolsa", "fr": "Je prépare mon sac", "de": "Ich packe meine Tasche", "it": "Preparo la mia borsa", "pt": "Eu arrumo minha bolsa"},
    "come with us": {"es": "Ven con nosotros", "fr": "Viens avec nous", "de": "Komm mit uns", "it": "Vieni con noi", "pt": "Venha com a gente"},
    "bank bank bank": {"es": "Banco, banco, banco", "fr": "Banque, banque, banque", "de": "Bank, Bank, Bank", "it": "Banca, banca, banca", "pt": "Banco, banco, banco"},
    "supermarket": {"es": "Supermercado", "fr": "Supermarché", "de": "Supermarkt", "it": "Supermercato", "pt": "Supermercado"},
    "restaurant restaurant": {"es": "Restaurante, restaurante", "fr": "Restaurant, restaurant", "de": "Restaurant, Restaurant", "it": "Ristorante, ristorante", "pt": "Restaurante, restaurante"},
    "i can say it": {"es": "Puedo decirlo", "fr": "Je peux le dire", "de": "Ich kann es sagen", "it": "Posso dirlo", "pt": "Eu consigo dizer"},
    "food food food": {"es": "Comida, comida, comida", "fr": "Nourriture, nourriture, nourriture", "de": "Essen, Essen, Essen", "it": "Cibo, cibo, cibo", "pt": "Comida, comida, comida"},
    "please and thank you": {"es": "Por favor y gracias", "fr": "S'il vous plaît et merci", "de": "Bitte und danke", "it": "Per favore e grazie", "pt": "Por favor e obrigado"},
    "travel words": {"es": "Palabras de viaje", "fr": "Mots de voyage", "de": "Reisewörter", "it": "Parole di viaggio", "pt": "Palavras de viagem"},
    "i know them too": {"es": "Yo también las sé", "fr": "Je les connais aussi", "de": "Ich kenne sie auch", "it": "Le conosco anch'io", "pt": "Eu também as sei"},
    "i need a ticket": {"es": "Necesito un billete", "fr": "J'ai besoin d'un billet", "de": "Ich brauche eine Fahrkarte", "it": "Ho bisogno di un biglietto", "pt": "Eu preciso de um bilhete"},
    "i need a map": {"es": "Necesito un mapa", "fr": "J'ai besoin d'une carte", "de": "Ich brauche eine Karte", "it": "Ho bisogno di una mappa", "pt": "Eu preciso de um mapa"},
    "i find the way": {"es": "Encuentro el camino", "fr": "Je trouve le chemin", "de": "Ich finde den Weg", "it": "Trovo la strada", "pt": "Eu encontro o caminho"},
    "and then i clap": {"es": "Y luego aplaudo", "fr": "Et puis j'applaudis", "de": "Und dann klatsche ich", "it": "E poi applaudo", "pt": "E então eu aplaudo"},
    "at the airport": {"es": "En el aeropuerto", "fr": "À l'aéroport", "de": "Am Flughafen", "it": "All'aeroporto", "pt": "No aeroporto"},
    "i wait in line": {"es": "Espero en la fila", "fr": "J'attends dans la file", "de": "Ich warte in der Schlange", "it": "Aspetto in fila", "pt": "Eu espero na fila"},
    "at the hotel": {"es": "En el hotel", "fr": "À l'hôtel", "de": "Im Hotel", "it": "In albergo", "pt": "No hotel"},
    "i feel just fine": {"es": "Me siento muy bien", "fr": "Je me sens très bien", "de": "Mir geht es gut", "it": "Mi sento benissimo", "pt": "Eu me sinto muito bem"},
    "one sandwich please": {"es": "Un sándwich, por favor", "fr": "Un sandwich, s'il vous plaît", "de": "Ein Sandwich, bitte", "it": "Un panino, per favore", "pt": "Um sanduíche, por favor"},
    "one cup of tea": {"es": "Una taza de té", "fr": "Une tasse de thé", "de": "Eine Tasse Tee", "it": "Una tazza di tè", "pt": "Uma xícara de chá"},
    "how much is this": {"es": "¿Cuánto cuesta esto?", "fr": "Combien ça coûte ?", "de": "Wie viel kostet das?", "it": "Quanto costa questo?", "pt": "Quanto custa isto?"},
    "can you help me": {"es": "¿Puede ayudarme?", "fr": "Pouvez-vous m'aider ?", "de": "Können Sie mir helfen?", "it": "Può aiutarmi?", "pt": "Você pode me ajudar?"},
    "hello friend how are you": {"es": "Hola amigo, ¿cómo estás?", "fr": "Bonjour ami, comment vas-tu ?", "de": "Hallo Freund, wie geht es dir?", "it": "Ciao amico, come stai?", "pt": "Olá amigo, como vai você?"},
    "i am good yes me too": {"es": "Estoy bien, sí, yo también", "fr": "Je vais bien, oui, moi aussi", "de": "Mir geht es gut, ja, mir auch", "it": "Sto bene, sì, anch'io", "pt": "Estou bem, sim, eu também"},
    "look a bus a car a train": {"es": "Mira, un autobús, un coche, un tren", "fr": "Regarde, un bus, une voiture, un train", "de": "Schau, ein Bus, ein Auto, ein Zug", "it": "Guarda, un autobus, un'auto, un treno", "pt": "Olha, um ônibus, um carro, um trem"},
    "see the sun see the rain": {"es": "Mira el sol, mira la lluvia", "fr": "Regarde le soleil, regarde la pluie", "de": "Sieh die Sonne, sieh den Regen", "it": "Guarda il sole, guarda la pioggia", "pt": "Veja o sol, veja a chuva"},
    "wheels on the bus go round and round": {"es": "Las ruedas del autobús giran y giran", "fr": "Les roues du bus tournent et tournent", "de": "Die Räder vom Bus drehen sich rundherum", "it": "Le ruote dell'autobus girano e girano", "pt": "As rodas do ônibus giram e giram"},
    "all through the town": {"es": "Por toda la ciudad", "fr": "À travers toute la ville", "de": "Durch die ganze Stadt", "it": "Per tutta la città", "pt": "Por toda a cidade"},
    "open shut the door goes": {"es": "Se abre y se cierra la puerta", "fr": "La porte s'ouvre et se ferme", "de": "Die Tür geht auf und zu", "it": "La porta si apre e si chiude", "pt": "A porta abre e fecha"},
    "everywhere it goes": {"es": "A todas partes va", "fr": "Partout où il va", "de": "Überall wohin es fährt", "it": "Dappertutto dove va", "pt": "Por todo lugar que vai"},
    "where we going far away": {"es": "¿A dónde vamos? Muy lejos", "fr": "Où allons-nous ? Très loin", "de": "Wohin fahren wir? Weit weg", "it": "Dove andiamo? Molto lontano", "pt": "Para onde vamos? Bem longe"},
    "to the park to play": {"es": "Al parque a jugar", "fr": "Au parc pour jouer", "de": "Zum Park zum Spielen", "it": "Al parco per giocare", "pt": "Ao parque para brincar"},
    "hold my hand dont let go": {"es": "Toma mi mano, no la sueltes", "fr": "Tiens ma main, ne lâche pas", "de": "Halt meine Hand, lass nicht los", "it": "Tieni la mia mano, non lasciarla", "pt": "Segure minha mão, não solte"},
    "fast and fast and slow": {"es": "Rápido y rápido y despacio", "fr": "Vite et vite et lentement", "de": "Schnell und schnell und langsam", "it": "Veloce e veloce e lento", "pt": "Rápido e rápido e devagar"},
    "up and down the people go": {"es": "Arriba y abajo van las personas", "fr": "Les gens montent et descendent", "de": "Auf und ab gehen die Leute", "it": "Su e giù vanno le persone", "pt": "Para cima e para baixo vão as pessoas"},
    "waving hi waving low": {"es": "Saludando arriba, saludando abajo", "fr": "Ils saluent en haut, ils saluent en bas", "de": "Winken hoch, winken tief", "it": "Salutano in alto, salutano in basso", "pt": "Acenando alto, acenando baixo"},
    "beep beep says the horn": {"es": "Pi pi dice la bocina", "fr": "Bip bip dit le klaxon", "de": "Tut tut sagt die Hupe", "it": "Bip bip dice il clacson", "pt": "Bip bip diz a buzina"},
    "since the early morn": {"es": "Desde temprano en la mañana", "fr": "Depuis le petit matin", "de": "Seit dem frühen Morgen", "it": "Fin dal primo mattino", "pt": "Desde cedo pela manhã"},
    "hello am i wrong": {"es": "Hola, ¿me equivoco?", "fr": "Bonjour, est-ce que je me trompe ?", "de": "Hallo, liege ich falsch?", "it": "Ciao, mi sbaglio?", "pt": "Olá, estou errado?"},
    "morning singing my song": {"es": "Por la mañana canto mi canción", "fr": "Le matin je chante ma chanson", "de": "Am Morgen singe ich mein Lied", "it": "Di mattina canto la mia canzone", "pt": "De manhã canto minha canção"},
    "the sun is shining": {"es": "El sol está brillando", "fr": "Le soleil brille", "de": "Die Sonne scheint", "it": "Il sole sta brillando", "pt": "O sol está brilhando"},
    "we can all sing along": {"es": "Todos podemos cantar juntos", "fr": "Nous pouvons tous chanter ensemble", "de": "Wir können alle mitsingen", "it": "Possiamo cantare tutti insieme", "pt": "Todos nós podemos cantar juntos"},
    "up is where i look": {"es": "Arriba es donde miro", "fr": "En haut, c'est là que je regarde", "de": "Nach oben schaue ich", "it": "In alto è dove guardo", "pt": "Para cima é onde eu olho"},
    "down is where i go": {"es": "Abajo es donde voy", "fr": "En bas, c'est là que je vais", "de": "Nach unten gehe ich", "it": "In basso è dove vado", "pt": "Para baixo é onde eu vou"},
    "left and right are friends": {"es": "Izquierda y derecha son amigas", "fr": "Gauche et droite sont amies", "de": "Links und rechts sind Freunde", "it": "Sinistra e destra sono amiche", "pt": "Esquerda e direita são amigas"},
    "come and learn them slow": {"es": "Ven y apréndelas despacio", "fr": "Viens les apprendre lentement", "de": "Komm und lerne sie langsam", "it": "Vieni e imparale lentamente", "pt": "Venha e aprenda-as devagar"},
    "words this way words this way": {"es": "Palabras por aquí, palabras por aquí", "fr": "Les mots par ici, les mots par ici", "de": "Wörter hier entlang, Wörter hier entlang", "it": "Parole da questa parte, parole da questa parte", "pt": "Palavras por aqui, palavras por aqui"},
    "say it soft say it loud": {"es": "Dilo suave, dilo fuerte", "fr": "Dis-le doucement, dis-le fort", "de": "Sag es leise, sag es laut", "it": "Dillo piano, dillo forte", "pt": "Diga baixinho, diga alto"},
    "we can learn them now": {"es": "Podemos aprenderlas ahora", "fr": "Nous pouvons les apprendre maintenant", "de": "Wir können sie jetzt lernen", "it": "Possiamo impararle adesso", "pt": "Podemos aprendê-las agora"},
    "left and right up and down": {"es": "Izquierda y derecha, arriba y abajo", "fr": "Gauche et droite, en haut et en bas", "de": "Links und rechts, oben und unten", "it": "Sinistra e destra, su e giù", "pt": "Esquerda e direita, para cima e para baixo"},
    "round and round we go": {"es": "Damos vueltas y vueltas", "fr": "On tourne et on tourne", "de": "Wir drehen uns rundherum", "it": "Giriamo e giriamo", "pt": "Giramos e giramos"},
    "one hand points to you": {"es": "Una mano te señala", "fr": "Une main te montre", "de": "Eine Hand zeigt auf dich", "it": "Una mano ti indica", "pt": "Uma mão aponta para você"},
    "two feet walk the floor": {"es": "Dos pies caminan por el suelo", "fr": "Deux pieds marchent sur le sol", "de": "Zwei Füße gehen über den Boden", "it": "Due piedi camminano sul pavimento", "pt": "Dois pés caminham pelo chão"},
    "turn around and smile": {"es": "Da la vuelta y sonríe", "fr": "Tourne-toi et souris", "de": "Dreh dich um und lächle", "it": "Girati e sorridi", "pt": "Vire-se e sorria"},
    "then we ask for more": {"es": "Luego pedimos más", "fr": "Puis nous en demandons plus", "de": "Dann bitten wir um mehr", "it": "Poi chiediamo ancora", "pt": "Então pedimos mais"},
    "this way that way": {"es": "Por aquí, por allá", "fr": "Par ici, par là", "de": "Hier entlang, dort entlang", "it": "Da questa parte, da quella parte", "pt": "Por aqui, por ali"},
    "near and far": {"es": "Cerca y lejos", "fr": "Près et loin", "de": "Nah und fern", "it": "Vicino e lontano", "pt": "Perto e longe"},
    "every word can take us": {"es": "Cada palabra puede llevarnos", "fr": "Chaque mot peut nous emmener", "de": "Jedes Wort kann uns bringen", "it": "Ogni parola può portarci", "pt": "Cada palavra pode nos levar"},
    "where we are": {"es": "A donde estamos", "fr": "Là où nous sommes", "de": "Wohin wir gehören", "it": "Dove siamo", "pt": "Onde estamos"},
}


def _merge_extra_pack() -> None:
    """Fold the 26-language featured pack into CURATED_LINES (idempotent)."""
    pack = (
        Path(__file__).resolve().parent.parent.parent / "data" / "curated_lines_extra.json"
    )
    if not pack.is_file():
        return
    try:
        payload = json.loads(pack.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    lines = payload.get("lines")
    if not isinstance(lines, dict):
        return
    for key, row in lines.items():
        if not isinstance(row, dict):
            continue
        bucket = CURATED_LINES.setdefault(str(key), {})
        for lang, text in row.items():
            if lang in CURATED_LANGUAGES and isinstance(text, str) and text.strip():
                bucket[lang] = text.strip()


_merge_extra_pack()


def curated(text: str, language: str) -> str:
    """Reviewed full-line translation, or '' when this line/language is uncurated."""
    return CURATED_LINES.get(normalize(text), {}).get(language, "")


def curated_coverage(language: str) -> float:
    """Share of curated lines available for a language (0.0–1.0)."""
    if language == "en":
        return 1.0
    if not CURATED_LINES:
        return 0.0
    have = sum(1 for row in CURATED_LINES.values() if row.get(language))
    return round(have / len(CURATED_LINES), 3)
