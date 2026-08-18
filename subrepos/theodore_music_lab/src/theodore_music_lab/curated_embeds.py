"""Hand-authored translations for YouTube embed verses and question prompts.

Same curated languages as lyric lines: es/fr/de/it/pt here, plus the Simplified
Chinese and Khmer pack in ``curated_embeds_zh_km.py``. Lookup is by the English
source text after ``normalize``, so verse and question strings share one
dictionary.
"""

from __future__ import annotations

from .curated_embeds_zh_km import CURATED_EMBEDS_ZH_KM
from .curated_lines import CURATED_LANGUAGES, normalize

CURATED_EMBEDS: dict[str, dict[str, str]] = {
    "Long ago a foreign prince sailed across the sea to a new land.": {
        "es": "Hace mucho tiempo un príncipe extranjero navegó a través del mar hacia una nueva tierra.",
        "fr": "Il y a longtemps, un prince étranger traversa la mer jusqu'à une nouvelle terre.",
        "de": "Vor langer Zeit segelte ein fremder Prinz über das Meer zu einem neuen Land.",
        "it": "Molto tempo fa un principe straniero navigò attraverso il mare verso una nuova terra.",
        "pt": "Há muito tempo um príncipe estrangeiro navegou pelo mar até uma nova terra.",
    },
    "What does 'sailed across the sea' mean?": {
        "es": "¿Qué significa 'sailed across the sea'?",
        "fr": "Que signifie 'sailed across the sea' ?",
        "de": "Was bedeutet 'sailed across the sea'?",
        "it": "Cosa significa 'sailed across the sea'?",
        "pt": "O que significa 'sailed across the sea'?",
    },
    "'Sailed across the sea' means he travelled by boat over the ocean to get somewhere.": {
        "es": "'Sailed across the sea' significa que viajó en barco por el océano para llegar a algún lugar.",
        "fr": "'Sailed across the sea' signifie qu'il a voyagé en bateau sur l'océan pour atteindre un endroit.",
        "de": "'Sailed across the sea' bedeutet, dass er mit dem Boot über den Ozean reiste, um irgendwohin zu kommen.",
        "it": "'Sailed across the sea' significa che viaggiò in barca sull'oceano per arrivare da qualche parte.",
        "pt": "'Sailed across the sea' significa que ele viajou de barco pelo oceano para chegar a algum lugar.",
    },
    "Why is 'Long ago' at the start of the sentence?": {
        "es": "¿Por qué 'Long ago' está al inicio de la oración?",
        "fr": "Pourquoi 'Long ago' est-il au début de la phrase ?",
        "de": "Warum steht 'Long ago' am Satzanfang?",
        "it": "Perché 'Long ago' è all'inizio della frase?",
        "pt": "Por que 'Long ago' está no início da frase?",
    },
    "'Long ago' is a time phrase that sets a fairy-tale past. English often puts time first: Long ago + subject + verb.": {
        "es": "'Long ago' es una frase de tiempo que sitúa un pasado de cuento. El inglés a menudo pone el tiempo primero: Long ago + sujeto + verbo.",
        "fr": "'Long ago' est une expression de temps qui pose un passé de conte. L'anglais place souvent le temps en premier : Long ago + sujet + verbe.",
        "de": "'Long ago' ist eine Zeitangabe, die eine Märchenvergangenheit setzt. Englisch stellt die Zeit oft nach vorn: Long ago + Subjekt + Verb.",
        "it": "'Long ago' è una frase temporale che ambienta un passato da fiaba. L'inglese spesso mette il tempo prima: Long ago + soggetto + verbo.",
        "pt": "'Long ago' é uma expressão de tempo que situa um passado de conto. O inglês muitas vezes coloca o tempo primeiro: Long ago + sujeito + verbo.",
    },
    "He met a dragon princess who lived in the kingdom by the water.": {
        "es": "Conoció a una princesa dragón que vivía en el reino junto al agua.",
        "fr": "Il rencontra une princesse dragon qui vivait dans le royaume près de l'eau.",
        "de": "Er traf eine Drachenprinzessin, die im Königreich am Wasser lebte.",
        "it": "Incontrò una principessa drago che viveva nel regno vicino all'acqua.",
        "pt": "Ele conheceu uma princesa dragão que vivia no reino à beira da água.",
    },
    "What is a 'dragon princess'?": {
        "es": "¿Qué es una 'dragon princess'?",
        "fr": "Qu'est-ce qu'une 'dragon princess' ?",
        "de": "Was ist eine 'dragon princess'?",
        "it": "Cos'è una 'dragon princess'?",
        "pt": "O que é uma 'dragon princess'?",
    },
    "A princess who is also a dragon (or from a dragon family) — a magical royal woman in the legend.": {
        "es": "Una princesa que también es un dragón (o de una familia de dragones): una mujer real mágica en la leyenda.",
        "fr": "Une princesse qui est aussi un dragon (ou d'une famille de dragons) — une femme royale magique dans la légende.",
        "de": "Eine Prinzessin, die auch ein Drache ist (oder aus einer Drachenfamilie) — eine magische königliche Frau in der Legende.",
        "it": "Una principessa che è anche un drago (o di una famiglia di draghi) — una donna reale magica nella leggenda.",
        "pt": "Uma princesa que também é um dragão (ou de uma família de dragões) — uma mulher real mágica na lenda.",
    },
    "What does the relative clause 'who lived in the kingdom by the water' do?": {
        "es": "¿Qué hace la cláusula relativa 'who lived in the kingdom by the water'?",
        "fr": "Que fait la relative 'who lived in the kingdom by the water' ?",
        "de": "Was leistet der Relativsatz 'who lived in the kingdom by the water'?",
        "it": "Cosa fa la relativa 'who lived in the kingdom by the water'?",
        "pt": "O que faz a oração relativa 'who lived in the kingdom by the water'?",
    },
    "It describes the princess. 'Who' refers to her; the clause tells us where she lived.": {
        "es": "Describe a la princesa. 'Who' se refiere a ella; la cláusula dice dónde vivía.",
        "fr": "Elle décrit la princesse. 'Who' la désigne ; la proposition dit où elle vivait.",
        "de": "Er beschreibt die Prinzessin. 'Who' bezieht sich auf sie; der Satz sagt, wo sie lebte.",
        "it": "Descrive la principessa. 'Who' si riferisce a lei; la proposizione dice dove viveva.",
        "pt": "Descreve a princesa. 'Who' refere-se a ela; a oração diz onde ela vivia.",
    },
    "They married, and the princess cut off her dragon tail to walk on land.": {
        "es": "Se casaron, y la princesa se cortó la cola de dragón para caminar en tierra.",
        "fr": "Ils se marièrent, et la princesse se coupa la queue de dragon pour marcher sur la terre.",
        "de": "Sie heirateten, und die Prinzessin schnitt ihren Drachenschwanz ab, um auf dem Land zu gehen.",
        "it": "Si sposarono, e la principessa si tagliò la coda di drago per camminare sulla terra.",
        "pt": "Eles se casaram, e a princesa cortou a cauda de dragão para caminhar em terra.",
    },
    "What does the past tense pair 'married' and 'cut off' show?": {
        "es": "¿Qué muestra el par en pasado 'married' y 'cut off'?",
        "fr": "Que montre la paire au passé 'married' et 'cut off' ?",
        "de": "Was zeigt das Vergangenheits-Paar 'married' und 'cut off'?",
        "it": "Cosa mostra la coppia al passato 'married' e 'cut off'?",
        "pt": "O que mostra o par no passado 'married' e 'cut off'?",
    },
    "Both verbs are simple past: completed actions in the story. English myths usually stay in the past throughout.": {
        "es": "Ambos verbos están en pasado simple: acciones terminadas en la historia. Los mitos en inglés suelen quedarse en pasado.",
        "fr": "Les deux verbes sont au passé simple : actions achevées dans l'histoire. Les mythes anglais restent souvent au passé.",
        "de": "Beide Verben stehen im Simple Past: abgeschlossene Handlungen. Englische Mythen bleiben meist in der Vergangenheit.",
        "it": "Entrambi i verbi sono al past simple: azioni concluse nella storia. I miti inglesi restano di solito al passato.",
        "pt": "Ambos os verbos estão no passado simples: ações concluídas na história. Mitos em inglês costumam ficar no passado.",
    },
    "What does 'cut off' mean here?": {
        "es": "¿Qué significa 'cut off' aquí?",
        "fr": "Que signifie 'cut off' ici ?",
        "de": "Was bedeutet 'cut off' hier?",
        "it": "Cosa significa 'cut off' qui?",
        "pt": "O que significa 'cut off' aqui?",
    },
    "'Cut off' means she removed her tail — a dramatic change so she could live like a human on land.": {
        "es": "'Cut off' significa que se quitó la cola: un cambio dramático para vivir como humana en tierra.",
        "fr": "'Cut off' signifie qu'elle s'est enlevé la queue — un changement dramatique pour vivre comme une humaine sur terre.",
        "de": "'Cut off' bedeutet, dass sie ihren Schwanz entfernte — eine dramatische Veränderung, um wie ein Mensch auf dem Land zu leben.",
        "it": "'Cut off' significa che si tolse la coda — un cambiamento drammatico per vivere come un'umana sulla terra.",
        "pt": "'Cut off' significa que ela removeu a cauda — uma mudança dramática para viver como humana em terra.",
    },
    "Their children became the first people of Cambodia.": {
        "es": "Sus hijos se convirtieron en el primer pueblo de Camboya.",
        "fr": "Leurs enfants devinrent le premier peuple du Cambodge.",
        "de": "Ihre Kinder wurden das erste Volk Kambodschas.",
        "it": "I loro figli divennero il primo popolo della Cambogia.",
        "pt": "Seus filhos se tornaram o primeiro povo do Camboja.",
    },
    "According to the legend, where do Cambodian people come from?": {
        "es": "Según la leyenda, ¿de dónde vienen los camboyanos?",
        "fr": "Selon la légende, d'où viennent les Cambodgiens ?",
        "de": "Woher kommen die Kambodschaner laut der Legende?",
        "it": "Secondo la leggenda, da dove vengono i cambogiani?",
        "pt": "Segundo a lenda, de onde vêm os cambojanos?",
    },
    "From the children of the foreign prince and the dragon princess — that is the founding story of the land.": {
        "es": "De los hijos del príncipe extranjero y la princesa dragón: esa es la historia fundacional del país.",
        "fr": "Des enfants du prince étranger et de la princesse dragon — c'est l'histoire fondatrice du pays.",
        "de": "Von den Kindern des fremden Prinzen und der Drachenprinzessin — das ist die Gründungsgeschichte des Landes.",
        "it": "Dai figli del principe straniero e della principessa drago — questa è la storia fondativa del paese.",
        "pt": "Dos filhos do príncipe estrangeiro e da princesa dragão — essa é a história fundadora da terra.",
    },
    "Why use 'became' instead of 'become'?": {
        "es": "¿Por qué usar 'became' en lugar de 'become'?",
        "fr": "Pourquoi utiliser 'became' au lieu de 'become' ?",
        "de": "Warum 'became' statt 'become'?",
        "it": "Perché usare 'became' invece di 'become'?",
        "pt": "Por que usar 'became' em vez de 'become'?",
    },
    "'Became' is the past of 'become'. The legend is finished history, so English uses the past form.": {
        "es": "'Became' es el pasado de 'become'. La leyenda es historia terminada, así que el inglés usa el pasado.",
        "fr": "'Became' est le passé de 'become'. La légende est une histoire achevée, donc l'anglais utilise le passé.",
        "de": "'Became' ist die Vergangenheit von 'become'. Die Legende ist abgeschlossene Geschichte, deshalb steht die Vergangenheitsform.",
        "it": "'Became' è il passato di 'become'. La leggenda è storia conclusa, quindi l'inglese usa il passato.",
        "pt": "'Became' é o passado de 'become'. A lenda é história concluída, então o inglês usa o passado.",
    },
    "Even today, Khmer wedding customs remember the dragon princess.": {
        "es": "Aun hoy, las costumbres nupciales jemeres recuerdan a la princesa dragón.",
        "fr": "Même aujourd'hui, les coutumes de mariage khmères se souviennent de la princesse dragon.",
        "de": "Noch heute erinnern khmerische Hochzeitsbräuche an die Drachenprinzessin.",
        "it": "Ancora oggi i costumi nuziali khmer ricordano la principessa drago.",
        "pt": "Ainda hoje, os costumes de casamento khmer lembram a princesa dragão.",
    },
    "What are 'wedding customs'?": {
        "es": "¿Qué son las 'wedding customs'?",
        "fr": "Que sont les 'wedding customs' ?",
        "de": "Was sind 'wedding customs'?",
        "it": "Cosa sono le 'wedding customs'?",
        "pt": "O que são 'wedding customs'?",
    },
    "The traditional things people do at a wedding — clothes, music, steps and symbols that families keep.": {
        "es": "Las cosas tradicionales que se hacen en una boda: ropa, música, pasos y símbolos que las familias conservan.",
        "fr": "Les choses traditionnelles que l'on fait à un mariage — vêtements, musique, étapes et symboles que les familles gardent.",
        "de": "Die traditionellen Dinge bei einer Hochzeit — Kleidung, Musik, Schritte und Symbole, die Familien bewahren.",
        "it": "Le cose tradizionali che si fanno a un matrimonio — vestiti, musica, passi e simboli che le famiglie conservano.",
        "pt": "As coisas tradicionais que se fazem num casamento — roupas, música, passos e símbolos que as famílias guardam.",
    },
    "What does 'Even today' contrast with?": {
        "es": "¿Con qué contrasta 'Even today'?",
        "fr": "Avec quoi 'Even today' contraste-t-il ?",
        "de": "Womit kontrastiert 'Even today'?",
        "it": "Con cosa contrasta 'Even today'?",
        "pt": "Com o que 'Even today' contrasta?",
    },
    "It contrasts the ancient legend with the present: the story still shapes modern weddings.": {
        "es": "Contrasta la leyenda antigua con el presente: la historia aún forma las bodas modernas.",
        "fr": "Il contraste la légende ancienne avec le présent : l'histoire façonne encore les mariages modernes.",
        "de": "Es stellt die alte Legende der Gegenwart gegenüber: die Geschichte prägt noch moderne Hochzeiten.",
        "it": "Contrasta la leggenda antica con il presente: la storia plasma ancora i matrimoni moderni.",
        "pt": "Contrasta a lenda antiga com o presente: a história ainda molda os casamentos modernos.",
    },
    "Sang Sinxay was born with special powers and a brave heart.": {
        "es": "Sang Sinxay nació con poderes especiales y un corazón valiente.",
        "fr": "Sang Sinxay naquit avec des pouvoirs spéciaux et un cœur courageux.",
        "de": "Sang Sinxay wurde mit besonderen Kräften und einem mutigen Herzen geboren.",
        "it": "Sang Sinxay nacque con poteri speciali e un cuore coraggioso.",
        "pt": "Sang Sinxay nasceu com poderes especiais e um coração corajoso.",
    },
    "What does 'a brave heart' mean?": {
        "es": "¿Qué significa 'a brave heart'?",
        "fr": "Que signifie 'a brave heart' ?",
        "de": "Was bedeutet 'a brave heart'?",
        "it": "Cosa significa 'a brave heart'?",
        "pt": "O que significa 'a brave heart'?",
    },
    "It means he is courageous — not afraid to help others even when it is hard.": {
        "es": "Significa que es valiente: no teme ayudar a otros aunque sea difícil.",
        "fr": "Cela signifie qu'il est courageux — il n'a pas peur d'aider les autres même quand c'est dur.",
        "de": "Es bedeutet, dass er mutig ist — er hat keine Angst, anderen zu helfen, auch wenn es schwer ist.",
        "it": "Significa che è coraggioso — non ha paura di aiutare gli altri anche quando è difficile.",
        "pt": "Significa que ele é corajoso — não tem medo de ajudar os outros mesmo quando é difícil.",
    },
    "Why is 'was born' passive?": {
        "es": "¿Por qué 'was born' es pasiva?",
        "fr": "Pourquoi 'was born' est-il au passif ?",
        "de": "Warum ist 'was born' Passiv?",
        "it": "Perché 'was born' è passivo?",
        "pt": "Por que 'was born' é passivo?",
    },
    "'Was born' is a fixed past-passive for birth. We say someone was born, not 'borned'.": {
        "es": "'Was born' es una pasiva fija del pasado para el nacimiento. Decimos someone was born, no 'borned'.",
        "fr": "'Was born' est un passif figé pour la naissance. On dit someone was born, pas 'borned'.",
        "de": "'Was born' ist ein festes Passiv für die Geburt. Man sagt someone was born, nicht 'borned'.",
        "it": "'Was born' è un passivo fisso per la nascita. Si dice someone was born, non 'borned'.",
        "pt": "'Was born' é um passivo fixo para o nascimento. Dizemos someone was born, não 'borned'.",
    },
    "An ogre stole his aunt, so Sinxay set out on a long journey.": {
        "es": "Un ogro robó a su tía, así que Sinxay partió en un largo viaje.",
        "fr": "Un ogre vola sa tante, alors Sinxay partit pour un long voyage.",
        "de": "Ein Oger stahl seine Tante, also machte sich Sinxay auf eine lange Reise.",
        "it": "Un orco rapì sua zia, così Sinxay partì per un lungo viaggio.",
        "pt": "Um ogro roubou sua tia, então Sinxay partiu numa longa jornada.",
    },
    "What does 'set out on a journey' mean?": {
        "es": "¿Qué significa 'set out on a journey'?",
        "fr": "Que signifie 'set out on a journey' ?",
        "de": "Was bedeutet 'set out on a journey'?",
        "it": "Cosa significa 'set out on a journey'?",
        "pt": "O que significa 'set out on a journey'?",
    },
    "It means he started travelling with a clear purpose — here, to find his aunt.": {
        "es": "Significa que empezó a viajar con un propósito claro: aquí, encontrar a su tía.",
        "fr": "Cela signifie qu'il a commencé à voyager dans un but clair — ici, retrouver sa tante.",
        "de": "Es bedeutet, dass er mit klarem Ziel zu reisen begann — hier, um seine Tante zu finden.",
        "it": "Significa che iniziò a viaggiare con uno scopo chiaro — qui, trovare sua zia.",
        "pt": "Significa que ele começou a viajar com um propósito claro — aqui, encontrar a tia.",
    },
    "What does 'so' connect in this sentence?": {
        "es": "¿Qué conecta 'so' en esta oración?",
        "fr": "Que relie 'so' dans cette phrase ?",
        "de": "Was verbindet 'so' in diesem Satz?",
        "it": "Cosa collega 'so' in questa frase?",
        "pt": "O que 'so' liga nesta frase?",
    },
    "'So' shows result: the theft caused the journey. Cause first, result after 'so'.": {
        "es": "'So' muestra el resultado: el robo causó el viaje. Causa primero, resultado después de 'so'.",
        "fr": "'So' montre le résultat : le vol a causé le voyage. Cause d'abord, résultat après 'so'.",
        "de": "'So' zeigt die Folge: der Diebstahl verursachte die Reise. Ursache zuerst, Folge nach 'so'.",
        "it": "'So' mostra il risultato: il furto causò il viaggio. Causa prima, risultato dopo 'so'.",
        "pt": "'So' mostra o resultado: o roubo causou a jornada. Causa primeiro, resultado depois de 'so'.",
    },
    "He fought many dangers and never gave up on his family.": {
        "es": "Enfrentó muchos peligros y nunca abandonó a su familia.",
        "fr": "Il affronta de nombreux dangers et n'abandonna jamais sa famille.",
        "de": "Er kämpfte gegen viele Gefahren und gab seine Familie nie auf.",
        "it": "Affrontò molti pericoli e non abbandonò mai la sua famiglia.",
        "pt": "Ele enfrentou muitos perigos e nunca desistiu da família.",
    },
    "What does 'never gave up' mean?": {
        "es": "¿Qué significa 'never gave up'?",
        "fr": "Que signifie 'never gave up' ?",
        "de": "Was bedeutet 'never gave up'?",
        "it": "Cosa significa 'never gave up'?",
        "pt": "O que significa 'never gave up'?",
    },
    "He kept trying. 'Give up' means stop trying; 'never gave up' means he continued.": {
        "es": "Siguió intentando. 'Give up' es dejar de intentar; 'never gave up' significa que continuó.",
        "fr": "Il a continué d'essayer. 'Give up' signifie arrêter ; 'never gave up' signifie qu'il a persisté.",
        "de": "Er versuchte weiter. 'Give up' heißt aufhören; 'never gave up' heißt, er machte weiter.",
        "it": "Continuò a provare. 'Give up' significa smettere; 'never gave up' significa che perseverò.",
        "pt": "Ele continuou tentando. 'Give up' é parar de tentar; 'never gave up' significa que ele persistiu.",
    },
    "Are 'fought' and 'gave' regular past verbs?": {
        "es": "¿Son 'fought' y 'gave' verbos regulares en pasado?",
        "fr": "'Fought' et 'gave' sont-ils des verbes réguliers au passé ?",
        "de": "Sind 'fought' und 'gave' regelmäßige Vergangenheitsformen?",
        "it": "'Fought' e 'gave' sono verbi regolari al passato?",
        "pt": "'Fought' e 'gave' são verbos regulares no passado?",
    },
    "No — they are irregular. Fight → fought, give → gave. Learners must memorise them.": {
        "es": "No: son irregulares. Fight → fought, give → gave. Hay que memorizarlos.",
        "fr": "Non — ils sont irréguliers. Fight → fought, give → gave. Il faut les mémoriser.",
        "de": "Nein — sie sind unregelmäßig. Fight → fought, give → gave. Man muss sie lernen.",
        "it": "No — sono irregolari. Fight → fought, give → gave. Bisogna memorizzarli.",
        "pt": "Não — são irregulares. Fight → fought, give → gave. É preciso memorizá-los.",
    },
    "At last he rescued his aunt and returned home as a hero.": {
        "es": "Por fin rescató a su tía y volvió a casa como héroe.",
        "fr": "Enfin il sauva sa tante et rentra chez lui en héros.",
        "de": "Schließlich rettete er seine Tante und kehrte als Held nach Hause zurück.",
        "it": "Alla fine salvò sua zia e tornò a casa da eroe.",
        "pt": "Por fim ele resgatou a tia e voltou para casa como herói.",
    },
    "How does the epic end for Sinxay?": {
        "es": "¿Cómo termina la epopeya para Sinxay?",
        "fr": "Comment l'épopée se termine-t-elle pour Sinxay ?",
        "de": "Wie endet das Epos für Sinxay?",
        "it": "Come finisce l'epica per Sinxay?",
        "pt": "Como termina a epopeia para Sinxay?",
    },
    "He saves his aunt and goes home celebrated as a hero — the classic rescue ending.": {
        "es": "Salva a su tía y vuelve a casa celebrado como héroe: el final clásico de rescate.",
        "fr": "Il sauve sa tante et rentre célébré comme un héros — la fin classique de sauvetage.",
        "de": "Er rettet seine Tante und kehrt als gefeierter Held heim — das klassische Rettungsende.",
        "it": "Salva sua zia e torna a casa celebrato come eroe — il classico finale di salvataggio.",
        "pt": "Ele salva a tia e volta para casa celebrado como herói — o final clássico de resgate.",
    },
    "What does 'at last' signal?": {
        "es": "¿Qué señala 'at last'?",
        "fr": "Que signale 'at last' ?",
        "de": "Was signalisiert 'at last'?",
        "it": "Cosa segnala 'at last'?",
        "pt": "O que 'at last' sinaliza?",
    },
    "It signals the long wait is over: after many struggles, the success finally arrives.": {
        "es": "Señala que la larga espera terminó: tras muchos esfuerzos, llega el éxito.",
        "fr": "Il signale que la longue attente est finie : après bien des peines, le succès arrive enfin.",
        "de": "Es signalisiert, dass das lange Warten vorbei ist: nach vielen Mühen kommt der Erfolg.",
        "it": "Segnala che la lunga attesa è finita: dopo molte prove, arriva finalmente il successo.",
        "pt": "Sinaliza que a longa espera acabou: depois de muitas lutas, o sucesso finalmente chega.",
    },
    "Lao people still tell this epic to teach courage and loyalty.": {
        "es": "El pueblo lao aún cuenta esta epopeya para enseñar valor y lealtad.",
        "fr": "Le peuple lao raconte encore cette épopée pour enseigner le courage et la loyauté.",
        "de": "Das laoische Volk erzählt dieses Epos noch, um Mut und Loyalität zu lehren.",
        "it": "Il popolo lao racconta ancora questa epica per insegnare coraggio e lealtà.",
        "pt": "O povo lao ainda conta esta epopeia para ensinar coragem e lealdade.",
    },
    "What is an 'epic'?": {
        "es": "¿Qué es un 'epic'?",
        "fr": "Qu'est-ce qu'un 'epic' ?",
        "de": "Was ist ein 'epic'?",
        "it": "Cos'è un 'epic'?",
        "pt": "O que é um 'epic'?",
    },
    "A long heroic story about a nation's legendary hero — bigger than a short fairy tale.": {
        "es": "Una larga historia heroica sobre el héroe legendario de una nación — mayor que un cuento breve.",
        "fr": "Une longue histoire héroïque sur le héros légendaire d'une nation — plus grande qu'un court conte.",
        "de": "Eine lange Heldengeschichte über den legendären Helden einer Nation — größer als ein kurzes Märchen.",
        "it": "Una lunga storia eroica sul leggendario eroe di una nazione — più grande di una breve fiaba.",
        "pt": "Uma longa história heroica sobre o herói lendário de uma nação — maior que um conto curto.",
    },
    "Why use the infinitive 'to teach'?": {
        "es": "¿Por qué usar el infinitivo 'to teach'?",
        "fr": "Pourquoi utiliser l'infinitif 'to teach' ?",
        "de": "Warum der Infinitiv 'to teach'?",
        "it": "Perché usare l'infinito 'to teach'?",
        "pt": "Por que usar o infinitivo 'to teach'?",
    },
    "'To teach' shows purpose: they tell the story in order to teach courage and loyalty.": {
        "es": "'To teach' muestra el propósito: cuentan la historia para enseñar valor y lealtad.",
        "fr": "'To teach' montre le but : ils racontent l'histoire pour enseigner le courage et la loyauté.",
        "de": "'To teach' zeigt den Zweck: sie erzählen die Geschichte, um Mut und Loyalität zu lehren.",
        "it": "'To teach' mostra lo scopo: raccontano la storia per insegnare coraggio e lealtà.",
        "pt": "'To teach' mostra o propósito: contam a história para ensinar coragem e lealdade.",
    },
    "Watch the movie clip carefully — listen for how people really speak.": {
        "es": "Mira el clip de la película con atención: escucha cómo habla la gente de verdad.",
        "fr": "Regarde attentivement le clip du film — écoute comment les gens parlent vraiment.",
        "de": "Schau den Filmclip genau an — hör zu, wie Menschen wirklich sprechen.",
        "it": "Guarda attentamente il clip del film — ascolta come parlano davvero le persone.",
        "pt": "Assista ao clipe do filme com atenção — ouça como as pessoas realmente falam.",
    },
    "What does 'listen for' mean?": {
        "es": "¿Qué significa 'listen for'?",
        "fr": "Que signifie 'listen for' ?",
        "de": "Was bedeutet 'listen for'?",
        "it": "Cosa significa 'listen for'?",
        "pt": "O que significa 'listen for'?",
    },
    "'Listen for' means pay attention until you hear a specific word or sound, not just hear generally.": {
        "es": "'Listen for' significa prestar atención hasta oír una palabra o sonido concreto, no solo oír en general.",
        "fr": "'Listen for' signifie faire attention jusqu'à entendre un mot ou un son précis, pas seulement entendre en général.",
        "de": "'Listen for' heißt, aufmerksam zu sein, bis man ein bestimmtes Wort oder Geräusch hört — nicht nur allgemein hören.",
        "it": "'Listen for' significa prestare attenzione finché non senti una parola o un suono specifico, non solo udire in generale.",
        "pt": "'Listen for' significa prestar atenção até ouvir uma palavra ou som específico, não apenas ouvir de forma geral.",
    },
    "Why is 'how people really speak' useful for learners?": {
        "es": "¿Por qué es útil 'how people really speak' para los aprendices?",
        "fr": "Pourquoi 'how people really speak' est-il utile aux apprenants ?",
        "de": "Warum ist 'how people really speak' für Lernende nützlich?",
        "it": "Perché 'how people really speak' è utile per chi impara?",
        "pt": "Por que 'how people really speak' é útil para quem aprende?",
    },
    "Movie English is natural speech: reduced sounds, stress and everyday grammar you need beyond textbooks.": {
        "es": "El inglés de cine es habla natural: sonidos reducidos, acento y gramática cotidiana más allá de los libros.",
        "fr": "L'anglais des films est un parler naturel : sons réduits, accentuation et grammaire du quotidien au-delà des manuels.",
        "de": "Filmenglisch ist natürliche Sprache: reduzierte Laute, Betonung und Alltaggrammatik jenseits der Lehrbücher.",
        "it": "L'inglese dei film è parlato naturale: suoni ridotti, accento e grammatica quotidiana oltre i libri di testo.",
        "pt": "O inglês de filme é fala natural: sons reduzidos, ênfase e gramática do dia a dia além dos livros.",
    },
    "Heroes hide their powers and try to live a normal family life.": {
        "es": "Los héroes esconden sus poderes e intentan vivir una vida familiar normal.",
        "fr": "Les héros cachent leurs pouvoirs et essaient de vivre une vie de famille normale.",
        "de": "Helden verbergen ihre Kräfte und versuchen, ein normales Familienleben zu führen.",
        "it": "Gli eroi nascondono i loro poteri e cercano di vivere una vita familiare normale.",
        "pt": "Os heróis escondem seus poderes e tentam viver uma vida familiar normal.",
    },
    "What does 'live a normal family life' mean?": {
        "es": "¿Qué significa 'live a normal family life'?",
        "fr": "Que signifie 'live a normal family life' ?",
        "de": "Was bedeutet 'live a normal family life'?",
        "it": "Cosa significa 'live a normal family life'?",
        "pt": "O que significa 'live a normal family life'?",
    },
    "It means everyday home routines — school, work, dinner — without superhero drama.": {
        "es": "Significa la rutina diaria en casa: escuela, trabajo, cena, sin drama de superhéroes.",
        "fr": "Cela signifie les routines quotidiennes à la maison — école, travail, dîner — sans drame de super-héros.",
        "de": "Es bedeutet den Alltag zu Hause — Schule, Arbeit, Abendessen — ohne Superhelden-Drama.",
        "it": "Significa le routine quotidiane a casa — scuola, lavoro, cena — senza drammi da supereroe.",
        "pt": "Significa a rotina diária em casa — escola, trabalho, jantar — sem drama de super-herói.",
    },
    "Why are both verbs after 'and' in the present?": {
        "es": "¿Por qué están ambos verbos después de 'and' en presente?",
        "fr": "Pourquoi les deux verbes après 'and' sont-ils au présent ?",
        "de": "Warum stehen beide Verben nach 'and' im Präsens?",
        "it": "Perché entrambi i verbi dopo 'and' sono al presente?",
        "pt": "Por que ambos os verbos depois de 'and' estão no presente?",
    },
    "'Hide' and 'try' are present simple for habits and ongoing situations in the story setup.": {
        "es": "'Hide' y 'try' están en presente simple para hábitos y situaciones en la presentación de la historia.",
        "fr": "'Hide' et 'try' sont au présent simple pour des habitudes et situations dans la mise en place de l'histoire.",
        "de": "'Hide' und 'try' stehen im Simple Present für Gewohnheiten und laufende Situationen in der Geschichte.",
        "it": "'Hide' e 'try' sono al present simple per abitudini e situazioni nella presentazione della storia.",
        "pt": "'Hide' e 'try' estão no presente simples para hábitos e situações na apresentação da história.",
    },
    "Notice short spoken phrases like 'Come on!' and 'We've got to go.'": {
        "es": "Fíjate en frases cortas habladas como 'Come on!' y 'We've got to go.'",
        "fr": "Remarque les courtes phrases parlées comme 'Come on !' et 'We've got to go.'",
        "de": "Achte auf kurze gesprochene Wendungen wie 'Come on!' und 'We've got to go.'",
        "it": "Nota le brevi frasi parlate come 'Come on!' e 'We've got to go.'",
        "pt": "Note frases curtas faladas como 'Come on!' e 'We've got to go.'",
    },
    "When do people say 'Come on!'?": {
        "es": "¿Cuándo dice la gente 'Come on!'?",
        "fr": "Quand dit-on 'Come on !' ?",
        "de": "Wann sagt man 'Come on!'?",
        "it": "Quando si dice 'Come on!'?",
        "pt": "Quando as pessoas dizem 'Come on!'?",
    },
    "To urge someone to hurry, try harder, or follow — a friendly push, not a full sentence.": {
        "es": "Para urgir a alguien a apresurarse, esforzarse o seguir — un empujón amable, no una oración completa.",
        "fr": "Pour pousser quelqu'un à se dépêcher, essayer plus fort ou suivre — une poussée amicale, pas une phrase complète.",
        "de": "Um jemanden zu drängen, sich zu beeilen, mehr zu versuchen oder zu folgen — ein freundlicher Schubs, kein ganzer Satz.",
        "it": "Per spingere qualcuno ad affrettarsi, impegnarsi di più o seguire — una spinta amichevole, non una frase completa.",
        "pt": "Para urgenciar alguém a apressar-se, esforçar-se mais ou seguir — um empurrão amigável, não uma frase completa.",
    },
    "What does \"We've got to go\" mean in formal English?": {
        "es": "¿Qué significa \"We've got to go\" en inglés formal?",
        "fr": "Que signifie \"We've got to go\" en anglais formel ?",
        "de": "Was bedeutet \"We've got to go\" im formellen Englisch?",
        "it": "Cosa significa \"We've got to go\" in inglese formale?",
        "pt": "O que significa \"We've got to go\" em inglês formal?",
    },
    "It means 'We have to go' / 'We must leave.' Spoken English prefers 'have got to' for urgency.": {
        "es": "Significa 'We have to go' / 'We must leave.' El inglés hablado prefiere 'have got to' para la urgencia.",
        "fr": "Cela signifie 'We have to go' / 'We must leave.' L'anglais parlé préfère 'have got to' pour l'urgence.",
        "de": "Es bedeutet 'We have to go' / 'We must leave.' Gesprochenes Englisch bevorzugt 'have got to' für Dringlichkeit.",
        "it": "Significa 'We have to go' / 'We must leave.' L'inglese parlato preferisce 'have got to' per l'urgenza.",
        "pt": "Significa 'We have to go' / 'We must leave.' O inglês falado prefere 'have got to' para urgência.",
    },
    "Stress falls on the important words: GO, HELP, NOW — little words stay soft.": {
        "es": "El acento cae en las palabras importantes: GO, HELP, NOW — las palabras pequeñas se quedan suaves.",
        "fr": "L'accent tombe sur les mots importants : GO, HELP, NOW — les petits mots restent doux.",
        "de": "Die Betonung liegt auf den wichtigen Wörtern: GO, HELP, NOW — kleine Wörter bleiben weich.",
        "it": "L'accento cade sulle parole importanti: GO, HELP, NOW — le parole piccole restano soft.",
        "pt": "A ênfase cai nas palavras importantes: GO, HELP, NOW — as palavras pequenas ficam suaves.",
    },
    "What is word stress?": {
        "es": "¿Qué es el word stress?",
        "fr": "Qu'est-ce que le word stress ?",
        "de": "Was ist word stress?",
        "it": "Cos'è il word stress?",
        "pt": "O que é word stress?",
    },
    "The beat you say louder and longer. Content words (go, help, now) carry stress; a/the/to stay soft.": {
        "es": "El golpe que dices más fuerte y largo. Las palabras de contenido (go, help, now) llevan el acento; a/the/to se quedan suaves.",
        "fr": "Le temps que tu dis plus fort et plus long. Les mots de contenu (go, help, now) portent l'accent ; a/the/to restent doux.",
        "de": "Der Schlag, den du lauter und länger sagst. Inhaltswörter (go, help, now) tragen die Betonung; a/the/to bleiben weich.",
        "it": "Il battito che dici più forte e più lungo. Le parole di contenuto (go, help, now) portano l'accento; a/the/to restano soft.",
        "pt": "A batida que você diz mais forte e mais longa. Palavras de conteúdo (go, help, now) carregam a ênfase; a/the/to ficam suaves.",
    },
    "Why does English skip stress on 'little words'?": {
        "es": "¿Por qué el inglés omite el acento en las 'little words'?",
        "fr": "Pourquoi l'anglais saute-t-il l'accent sur les 'little words' ?",
        "de": "Warum lässt Englisch die Betonung bei 'little words' aus?",
        "it": "Perché l'inglese salta l'accento sulle 'little words'?",
        "pt": "Por que o inglês pula a ênfase nas 'little words'?",
    },
    "Articles and prepositions are grammar glue. Stressing content words helps listeners catch the message fast.": {
        "es": "Artículos y preposiciones son pegamento gramatical. Acentuar el contenido ayuda a captar el mensaje rápido.",
        "fr": "Articles et prépositions sont la colle grammaticale. Accentuer le contenu aide à saisir le message vite.",
        "de": "Artikel und Präpositionen sind Grammatik-Kleber. Inhaltswörter betonen hilft, die Botschaft schnell zu fassen.",
        "it": "Articoli e preposizioni sono colla grammaticale. Accentare il contenuto aiuta a cogliere il messaggio in fretta.",
        "pt": "Artigos e preposições são cola gramatical. Enfatizar o conteúdo ajuda a captar a mensagem rápido.",
    },
    "Replay the clip and shadow the lines out loud to make the phrases yours.": {
        "es": "Reproduce el clip y haz sombra de las líneas en voz alta para hacer tuyas las frases.",
        "fr": "Rejoue le clip et fais du shadowing à voix haute pour faire tiennes les phrases.",
        "de": "Spiele den Clip erneut und schatte die Zeilen laut nach, damit die Phrasen dir gehören.",
        "it": "Riguarda il clip e fai shadowing ad alta voce per fare tue le frasi.",
        "pt": "Reveja o clipe e faça shadowing em voz alta para tornar as frases suas.",
    },
    "What does 'shadow' mean in language learning?": {
        "es": "¿Qué significa 'shadow' en el aprendizaje de idiomas?",
        "fr": "Que signifie 'shadow' dans l'apprentissage des langues ?",
        "de": "Was bedeutet 'shadow' beim Sprachenlernen?",
        "it": "Cosa significa 'shadow' nell'apprendimento delle lingue?",
        "pt": "O que significa 'shadow' na aprendizagem de línguas?",
    },
    "Speak along with the audio a split-second behind it — copy rhythm, stress and emotion.": {
        "es": "Habla con el audio una fracción de segundo detrás: copia ritmo, acento y emoción.",
        "fr": "Parle avec l'audio une fraction de seconde derrière — copie rythme, accent et émotion.",
        "de": "Sprich mit dem Audio einen Bruchteil hinterher — kopiere Rhythmus, Betonung und Emotion.",
        "it": "Parla con l'audio una frazione di secondo dietro — copia ritmo, accento ed emozione.",
        "pt": "Fale com o áudio uma fração de segundo atrás — copie ritmo, ênfase e emoção.",
    },
    "Why replay after the explanations?": {
        "es": "¿Por qué reproducir de nuevo después de las explicaciones?",
        "fr": "Pourquoi rejouer après les explications ?",
        "de": "Warum nach den Erklärungen erneut abspielen?",
        "it": "Perché rivedere dopo le spiegazioni?",
        "pt": "Por que rever depois das explicações?",
    },
    "First watch for meaning, then study the language, then speak it. Repetition turns phrases into usable English.": {
        "es": "Primero mira por el significado, luego estudia la lengua, luego háblala. La repetición hace usable el inglés.",
        "fr": "D'abord regarder pour le sens, puis étudier la langue, puis la parler. La répétition rend l'anglais utilisable.",
        "de": "Zuerst auf Sinn schauen, dann Sprache studieren, dann sprechen. Wiederholung macht Phrasen nutzbar.",
        "it": "Prima guarda per il significato, poi studia la lingua, poi parlala. La ripetizione rende l'inglese usabile.",
        "pt": "Primeiro assista pelo significado, depois estude a língua, depois fale. A repetição torna o inglês usável.",
    },
}

# Keep the Unicode packs isolated and merge them into the same tier-1 lookup the
# verse list, pause card, spoken line and Ask AI all read from.
for _text, _translations in CURATED_EMBEDS_ZH_KM.items():
    CURATED_EMBEDS.setdefault(_text, {}).update(_translations)


_INDEX: dict[str, dict[str, str]] | None = None


def _index() -> dict[str, dict[str, str]]:
    global _INDEX
    if _INDEX is None:
        _INDEX = {normalize(key): value for key, value in CURATED_EMBEDS.items()}
    return _INDEX


def curated_embed(text: str, language: str) -> str:
    """Reviewed translation for an embed verse or teaching prompt, or ''."""
    if language not in CURATED_LANGUAGES:
        return ""
    return _index().get(normalize(text), {}).get(language, "")
