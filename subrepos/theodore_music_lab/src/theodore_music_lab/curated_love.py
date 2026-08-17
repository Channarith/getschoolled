"""Curated es/fr/de/it/pt glosses for Love of Learning karaoke lines.

Keys are English glosses (``text_en``). Khmer display uses ``text_km`` on the
line itself; other languages go through this table, then the LLM/lexicon stack.
"""

from __future__ import annotations

from .curated_lines import CURATED_LANGUAGES, normalize

CURATED_LOVE: dict[str, dict[str, str]] = {
    "My life was not worth much.": {
        "es": "Mi vida no valía mucho.",
        "fr": "Ma vie ne valait pas grand-chose.",
        "de": "Mein Leben war nicht viel wert.",
        "it": "La mia vita non valeva molto.",
        "pt": "Minha vida não valia muito.",
    },
    "I was down — no lunch, no luck.": {
        "es": "Estaba hundido: sin almuerzo, sin suerte.",
        "fr": "J'étais à terre — pas de déjeuner, pas de chance.",
        "de": "Ich war am Boden — kein Mittagessen, kein Glück.",
        "it": "Ero a terra — niente pranzo, niente fortuna.",
        "pt": "Eu estava por baixo — sem almoço, sem sorte.",
    },
    "Growing up in a house of leftover rice": {
        "es": "Crecer en una casa de arroz sobrante",
        "fr": "Grandir dans une maison de riz restant",
        "de": "Aufwachsen in einem Haus mit übrigem Reis",
        "it": "Crescere in una casa di riso avanzato",
        "pt": "Crescer numa casa de arroz sobrado",
    },
    "Cracked walls, wind coming in through the holes": {
        "es": "Paredes agrietadas, el viento entra por los huecos",
        "fr": "Murs fissurés, le vent entre par les trous",
        "de": "Rissige Wände, Wind kommt durch die Löcher",
        "it": "Muri screpolati, il vento entra dai buchi",
        "pt": "Paredes rachadas, o vento entra pelos buracos",
    },
    "Mother sewed clothes under dim light": {
        "es": "Mamá cosía ropa bajo una luz tenue",
        "fr": "Maman cousait des vêtements sous une faible lumière",
        "de": "Mutter nähte Kleider bei schwachem Licht",
        "it": "Mamma cuciva vestiti sotto una luce fioca",
        "pt": "Mãe costurava roupas sob luz fraca",
    },
    "Father held my hand when illness put me on the bed": {
        "es": "Papá me tomó la mano cuando la enfermedad me puso en la cama",
        "fr": "Papa me tenait la main quand la maladie m'a mis au lit",
        "de": "Vater hielt meine Hand, als Krankheit mich ins Bett legte",
        "it": "Papà mi teneva la mano quando la malattia mi mise a letto",
        "pt": "Papai segurou minha mão quando a doença me pôs na cama",
    },
    "Khmer land has mud after the rain": {
        "es": "La tierra jemer tiene barro después de la lluvia",
        "fr": "La terre khmère a de la boue après la pluie",
        "de": "Khmer-Land hat Schlamm nach dem Regen",
        "it": "La terra khmer ha fango dopo la pioggia",
        "pt": "A terra khmer tem lama depois da chuva",
    },
    "A little rice in a bowl on a wooden table": {
        "es": "Un poco de arroz en un plato sobre una mesa de madera",
        "fr": "Un peu de riz dans un bol sur une table en bois",
        "de": "Etwas Reis in einer Schale auf einem Holztisch",
        "it": "Un po' di riso in una ciotola su un tavolo di legno",
        "pt": "Um pouco de arroz num prato sobre uma mesa de madeira",
    },
    "But I saw letters on the blackboard": {
        "es": "Pero vi letras en la pizarra",
        "fr": "Mais j'ai vu des lettres sur le tableau",
        "de": "Aber ich sah Buchstaben an der Tafel",
        "it": "Ma vidi lettere sulla lavagna",
        "pt": "Mas eu vi letras no quadro-negro",
    },
    "Like a small light in the middle of a dark day": {
        "es": "Como una pequeña luz en medio de un día oscuro",
        "fr": "Comme une petite lumière au milieu d'un jour sombre",
        "de": "Wie ein kleines Licht inmitten eines dunklen Tages",
        "it": "Come una piccola luce in mezzo a un giorno buio",
        "pt": "Como uma pequena luz no meio de um dia escuro",
    },
    "When the wind slammed the door": {
        "es": "Cuando el viento golpeó la puerta",
        "fr": "Quand le vent claqua la porte",
        "de": "Als der Wind die Tür zuschlug",
        "it": "Quando il vento sbatté la porta",
        "pt": "Quando o vento bateu a porta",
    },
    "I still opened the book": {
        "es": "Aun así abrí el libro",
        "fr": "J'ouvris quand même le livre",
        "de": "Ich öffnete trotzdem das Buch",
        "it": "Aprivo comunque il libro",
        "pt": "Ainda assim abri o livro",
    },
    "When tears flowed": {
        "es": "Cuando fluían las lágrimas",
        "fr": "Quand les larmes coulaient",
        "de": "Als Tränen flossen",
        "it": "Quando scorrevano le lacrime",
        "pt": "Quando as lágrimas corriam",
    },
    "I wrote my own name clearly": {
        "es": "Escribí mi propio nombre con claridad",
        "fr": "J'écrivis mon propre nom clairement",
        "de": "Ich schrieb meinen eigenen Namen klar",
        "it": "Scrissi il mio nome chiaramente",
        "pt": "Escrevi meu próprio nome com clareza",
    },
    "The love of learning": {
        "es": "El amor por aprender",
        "fr": "L'amour d'apprendre",
        "de": "Die Liebe zum Lernen",
        "it": "L'amore per l'apprendimento",
        "pt": "O amor de aprender",
    },
    "It is my soul (my soul)": {
        "es": "Es mi alma (mi alma)",
        "fr": "C'est mon âme (mon âme)",
        "de": "Es ist meine Seele (meine Seele)",
        "it": "È la mia anima (la mia anima)",
        "pt": "É a minha alma (a minha alma)",
    },
    "It is my power (my power)": {
        "es": "Es mi poder (mi poder)",
        "fr": "C'est ma force (ma force)",
        "de": "Es ist meine Kraft (meine Kraft)",
        "it": "È la mia forza (la mia forza)",
        "pt": "É o meu poder (o meu poder)",
    },
    "From poverty rising forward": {
        "es": "Desde la pobreza subiendo hacia adelante",
        "fr": "De la pauvreté s'élevant vers l'avant",
        "de": "Aus der Armut nach vorn steigend",
        "it": "Dalla povertà che sale avanti",
        "pt": "Da pobreza subindo para frente",
    },
    "I never stop dreaming": {
        "es": "Nunca dejo de soñar",
        "fr": "Je n'arrête jamais de rêver",
        "de": "Ich höre nie auf zu träumen",
        "it": "Non smetto mai di sognare",
        "pt": "Eu nunca paro de sonhar",
    },
    "I had a life not worth living.": {
        "es": "Tenía una vida que no valía la pena vivir.",
        "fr": "J'avais une vie qui ne valait pas d'être vécue.",
        "de": "Ich hatte ein Leben, das nicht lebenswert war.",
        "it": "Avevo una vita che non valeva la pena vivere.",
        "pt": "Eu tinha uma vida que não valia a pena viver.",
    },
    "I had a world — no beginning.": {
        "es": "Tenía un mundo — sin comienzo.",
        "fr": "J'avais un monde — sans début.",
        "de": "Ich hatte eine Welt — ohne Anfang.",
        "it": "Avevo un mondo — senza inizio.",
        "pt": "Eu tinha um mundo — sem começo.",
    },
    "I walked through primary school": {
        "es": "Caminé por la escuela primaria",
        "fr": "J'ai traversé l'école primaire",
        "de": "Ich ging durch die Grundschule",
        "it": "Camminai attraverso la scuola elementare",
        "pt": "Eu caminhei pela escola primária",
    },
    "Shoes soaking wet, head held higher": {
        "es": "Zapatos empapados, la cabeza más alta",
        "fr": "Chaussures trempées, la tête plus haute",
        "de": "Schuhe triefend nass, Kopf höher gehalten",
        "it": "Scarpe inzuppate, testa più alta",
        "pt": "Sapatos encharcados, cabeça mais erguida",
    },
    "When some friends laughed that I was slow": {
        "es": "Cuando algunos amigos se rieron de que yo era lento",
        "fr": "Quand certains amis riaient que j'étais lent",
        "de": "Als manche Freunde lachten, ich sei langsam",
        "it": "Quando alcuni amici ridevano che ero lento",
        "pt": "Quando alguns amigos riram que eu era lento",
    },
    "I answered with letters on paper": {
        "es": "Respondí con letras en el papel",
        "fr": "J'ai répondu avec des lettres sur le papier",
        "de": "Ich antwortete mit Buchstaben auf Papier",
        "it": "Risposi con lettere sulla carta",
        "pt": "Respondi com letras no papel",
    },
    "The library was my second home": {
        "es": "La biblioteca era mi segundo hogar",
        "fr": "La bibliothèque était ma deuxième maison",
        "de": "Die Bibliothek war mein zweites Zuhause",
        "it": "La biblioteca era la mia seconda casa",
        "pt": "A biblioteca era minha segunda casa",
    },
    "Smell of old paper mixed with a calm heart": {
        "es": "Olor a papel viejo mezclado con un corazón en calma",
        "fr": "Odeur de vieux papier mêlée à un cœur calme",
        "de": "Geruch von altem Papier gemischt mit einem ruhigen Herzen",
        "it": "Odore di carta vecchia mescolato a un cuore calmo",
        "pt": "Cheiro de papel velho misturado com um coração calmo",
    },
    "My subjects were like little bridges": {
        "es": "Mis materias eran como pequeños puentes",
        "fr": "Mes matières étaient comme de petits ponts",
        "de": "Meine Fächer waren wie kleine Brücken",
        "it": "Le mie materie erano come piccoli ponti",
        "pt": "Minhas matérias eram como pequenas pontes",
    },
    "Crossing from the past to tomorrow": {
        "es": "Cruzando del pasado al mañana",
        "fr": "Traversant du passé à demain",
        "de": "Vom Vergangenheit zu morgen überqueren",
        "it": "Attraversando dal passato a domani",
        "pt": "Cruzando do passado para amanhã",
    },
    "Even when my body hurt": {
        "es": "Aunque el cuerpo doliera",
        "fr": "Même quand mon corps faisait mal",
        "de": "Auch wenn mein Körper schmerzte",
        "it": "Anche quando il corpo doleva",
        "pt": "Mesmo quando o corpo doía",
    },
    "I still wanted to know": {
        "es": "Aun así quería saber",
        "fr": "Je voulais quand même savoir",
        "de": "Ich wollte trotzdem wissen",
        "it": "Volevo comunque sapere",
        "pt": "Ainda assim eu queria saber",
    },
    "Even when exhausted": {
        "es": "Aunque estuviera agotado",
        "fr": "Même épuisé",
        "de": "Auch wenn erschöpft",
        "it": "Anche se esausto",
        "pt": "Mesmo exausto",
    },
    "I still went to meet the light": {
        "es": "Aun así fui a encontrar la luz",
        "fr": "Je suis quand même allé rencontrer la lumière",
        "de": "Ich ging trotzdem dem Licht entgegen",
        "it": "Andai comunque incontro alla luce",
        "pt": "Ainda assim fui ao encontro da luz",
    },
    "I do not forget the red earth under my feet": {
        "es": "No olvido la tierra roja bajo mis pies",
        "fr": "Je n'oublie pas la terre rouge sous mes pieds",
        "de": "Ich vergesse die rote Erde unter meinen Füßen nicht",
        "it": "Non dimentico la terra rossa sotto i miei piedi",
        "pt": "Não esqueço a terra vermelha sob meus pés",
    },
    "Do not forget the river lost when rain fell": {
        "es": "No olvides el río perdido cuando cayó la lluvia",
        "fr": "N'oublie pas la rivière perdue quand la pluie tomba",
        "de": "Vergiss den Fluss nicht, der verloren ging, als Regen fiel",
        "it": "Non dimenticare il fiume perso quando cadde la pioggia",
        "pt": "Não esqueça o rio perdido quando a chuva caiu",
    },
    "But I take my name": {
        "es": "Pero tomo mi nombre",
        "fr": "Mais je prends mon nom",
        "de": "Aber ich nehme meinen Namen",
        "it": "Ma prendo il mio nome",
        "pt": "Mas eu levo meu nome",
    },
    "And place it on the next page": {
        "es": "Y lo pongo en la página siguiente",
        "fr": "Et je le place sur la page suivante",
        "de": "Und setze ihn auf die nächste Seite",
        "it": "E lo metto sulla pagina successiva",
        "pt": "E o coloco na página seguinte",
    },
    "So little children can see": {
        "es": "Para que los niños pequeños puedan ver",
        "fr": "Pour que les petits enfants puissent voir",
        "de": "Damit kleine Kinder sehen können",
        "it": "Perché i bambini piccoli possano vedere",
        "pt": "Para que as crianças pequenas possam ver",
    },
    "That a long road can still be reached": {
        "es": "Que un camino largo aún se puede alcanzar",
        "fr": "Qu'un long chemin peut encore être atteint",
        "de": "Dass ein langer Weg noch erreicht werden kann",
        "it": "Che una strada lunga si può ancora raggiungere",
        "pt": "Que um caminho longo ainda se pode alcançar",
    },
    "If the heart still loves": {
        "es": "Si el corazón aún ama",
        "fr": "Si le cœur aime encore",
        "de": "Wenn das Herz noch liebt",
        "it": "Se il cuore ama ancora",
        "pt": "Se o coração ainda ama",
    },
    "Research and learning": {
        "es": "La investigación y el aprendizaje",
        "fr": "La recherche et l'apprentissage",
        "de": "Forschung und Lernen",
        "it": "La ricerca e l'apprendimento",
        "pt": "A pesquisa e o aprendizado",
    },
    "From Khmer land to a new day": {
        "es": "De la tierra jemer a un día nuevo",
        "fr": "De la terre khmère à un jour nouveau",
        "de": "Vom Khmer-Land zu einem neuen Tag",
        "it": "Dalla terra khmer a un nuovo giorno",
        "pt": "Da terra khmer a um novo dia",
    },
    "I was born to learn": {
        "es": "Nací para aprender",
        "fr": "Je suis né pour apprendre",
        "de": "Ich wurde geboren, um zu lernen",
        "it": "Sono nato per imparare",
        "pt": "Eu nasci para aprender",
    },
    "What does this line mean?": {
        "es": "¿Qué significa esta línea?",
        "fr": "Que signifie cette ligne ?",
        "de": "Was bedeutet diese Zeile?",
        "it": "Cosa significa questa riga?",
        "pt": "O que significa esta linha?",
    },
}

_INDEX: dict[str, dict[str, str]] | None = None


def _index() -> dict[str, dict[str, str]]:
    global _INDEX
    if _INDEX is None:
        _INDEX = {normalize(key): value for key, value in CURATED_LOVE.items()}
    return _INDEX


def curated_love(text: str, language: str) -> str:
    if language not in CURATED_LANGUAGES:
        return ""
    return _index().get(normalize(text), {}).get(language, "")
