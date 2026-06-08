"""
config.py — Configuration centralisée pour "Le Banquet des Muses".

Contient les dictionnaires de données pures (foci, templates JSON,
constantes de catégories, barrières sémantiques) extraits de daily_culture.py
pour alléger le fichier principal et améliorer la maintenabilité.
"""

from __future__ import annotations

# ============================================================
# CATÉGORIES — Définition unique (nom, couleur hex, icône)
# ============================================================
CATEGORIES: list[tuple[str, str, str]] = [
    ("Poésie", "#c5a059", "📜"),
    ("Littérature", "#800020", "📚"),
    ("Musique", "#2b2b2b", "🎵"),
    ("Sciences", "#4a6b5d", "🌍"),
    ("Philosophie", "#800020", "🧠"),
    ("Cinéma", "#1a1a1a", "🎬"),
    ("Architecture", "#555555", "🏛️"),
    ("Mythologie", "#c5a059", "⚡"),
    ("Gastronomie", "#800020", "🍷"),
    ("Sculpture", "#696969", "🗿"),
    ("Arts de la scène", "#8B0000", "🎭"),
    ("Photographie", "#2F4F4F", "📷"),
    ("Bande dessinée", "#B8860B", "🖋️"),
    ("Jeu vidéo", "#2E8B57", "🎮"),
]

# Catégories qui utilisent Wikipédia en anglais comme langue primaire
ENGLISH_PRIMARY_CATEGORIES: set[str] = {
    "Cinéma", "Musique", "Architecture", "Littérature",
    "Jeu vidéo", "Photographie", "Sculpture", "Beaux-Arts",
}

# Catégories exclues du fallback IA (placeholder élégant uniquement)
NO_AI_FALLBACK_CATEGORIES: set[str] = {"Architecture", "Sculpture"}

# Catégories abstraites avec prompt IA enrichi
ABSTRACT_CATEGORIES: set[str] = {"Philosophie", "Mythologie", "Poésie", "Sciences"}

# ============================================================
# FOCI QUOTIDIENS (sous-thèmes déterministes par date)
# ============================================================
FOCI: dict[str, list[str]] = {
    "Poésie": [
        "le Romantisme", "le Symbolisme", "le Surréalisme",
        "la poésie du 20ème siècle", "le Parnasse", "la Pléiade",
        "un poème mélancolique", "un sonnet classique",
        "la poésie lyrique", "un haïku ou poème court",
    ],
    "Littérature": [
        "un roman du 19e siècle", "un essai philosophique", "un conte",
        "le réalisme", "un lauréat du prix Nobel", "la littérature classique",
        "un roman épistolaire", "la littérature du 20e siècle",
    ],
    "Musique": [
        "le rock classique", "le jazz", "la musique symphonique", "la pop",
        "la soul", "la chanson française", "le piano solo", "l'opéra",
        "la musique baroque", "le blues",
    ],
    "Sciences": [
        "la physique quantique", "la biologie", "l'astronomie",
        "l'informatique", "les mathématiques", "la médecine",
        "la révolution industrielle", "l'antiquité scientifique",
        "la chimie", "les grandes inventions",
    ],
    "Philosophie": [
        "l'existentialisme", "le stoïcisme", "la philosophie des Lumières",
        "la Grèce antique", "le rationalisme", "la phénoménologie",
        "le nihilisme", "la métaphysique", "la philosophie politique",
        "l'éthique",
    ],
    "Cinéma": [
        "le Nouvel Hollywood", "la Nouvelle Vague", "le néoréalisme italien",
        "la science-fiction", "le film noir", "l'animation japonaise",
        "le thriller", "le drame historique", "le western",
    ],
    "Architecture": [
        "le gothique", "le style roman", "la Renaissance", "l'art déco",
        "le brutalisme", "l'Antiquité", "le modernisme",
        "l'architecture asiatique", "le baroque", "le néoclassicisme",
    ],
    "Mythologie": [
        "la mythologie nordique", "la mythologie grecque",
        "la mythologie égyptienne", "la mythologie romaine",
        "les mythes celtiques", "les légendes asiatiques",
        "la création du monde", "les héros mythologiques",
    ],
    "Gastronomie": [
        "un plat français", "la gastronomie italienne",
        "une spécialité japonaise", "un dessert classique",
        "la cuisine levantine", "les techniques culinaires",
        "la Méditerranée", "la cuisine végétale",
    ],
    "Sculpture": [
        "la Renaissance", "la Grèce antique", "la sculpture moderne",
        "l'art roman", "le monumental", "les bustes romains",
        "le marbre", "le bronze", "le néoclassicisme", "le baroque sculptural",
    ],
    "Arts de la scène": [
        "la tragédie grecque", "le ballet classique", "Molière",
        "Shakespeare", "l'opéra italien", "le théâtre de l'absurde",
        "la comédie musicale", "le kabuki", "la danse contemporaine",
    ],
    "Photographie": [
        "la photographie humaniste", "le photojournalisme", "le paysage",
        "le portrait", "la photographie de rue", "le surréalisme",
        "le pictorialisme", "le noir et blanc",
    ],
    "Bande dessinée": [
        "la BD franco-belge", "le roman graphique", "le manga classique",
        "le comic book", "la ligne claire", "la science-fiction",
        "la BD historique", "le one-shot",
    ],
    "Jeu vidéo": [
        "l'ère 16-bits", "les RPG classiques", "les jeux narratifs",
        "les pionniers", "les jeux indépendants", "les jeux de plateforme",
        "le point & click", "les jeux d'aventure",
    ],
}

# ============================================================
# TEMPLATES JSON PAR CATÉGORIE (pour le prompt DeepSeek)
# ============================================================
JSON_TEMPLATES: dict[str, str] = {
    "Poésie": (
        '{"titre": "...", "auteur": "...", '
        '"poeme_entier": "Texte integral traduit en francais contemporain moderne. '
        "Si l'original est en vieux francais, le traduire impérativement "
        'en francais actuel fluide, tout en conservant le rythme poetique.", '
        '"analyse": "...", "lien_wiki": "...", "image_query": "Auteur Wikipedia"}'
    ),
    "Littérature": (
        '{"titre": "...", "auteur": "...", '
        '"extrait": "Extrait de roman ou essai en francais contemporain. '
        "Si le texte original est en vieux francais, l'adapter "
        'en francais moderne fluide et accessible.", '
        '"analyse": "...", "lien_wiki": "...", "image_query": "Livre Wikipedia"}'
    ),
    "Musique": (
        '{"titre": "...", "artiste": "...", "annee": "...", '
        '"analyse": "...", "lien_wiki": "...", "image_query": "Artiste musical"}'
    ),
    "Sciences": (
        '{"titre": "...", "inventeur": "...", '
        '"analyse": "...", "lien_wiki": "...", "image_query": "Invention"}'
    ),
    "Philosophie": (
        '{"concept": "...", "philosophe": "...", '
        '"analyse": "...", "lien_wiki": "...", '
        '"image_query": "Philosophe Wikipedia"}'
    ),
    "Cinéma": (
        '{"titre": "...", "realisateur": "...", "annee": "...", '
        '"analyse": "...", "lien_wiki": "...", "image_query": "Film Wikipedia"}'
    ),
    "Architecture": (
        '{"titre": "...", '
        '"architecte": "...", '
        '"analyse": "...", "lien_wiki": "...", '
        '"image_query": "Nom du monument, Architecte, Ville, Pays"}'
    ),
    "Mythologie": (
        '{"titre": "...", "origine": "...", '
        '"analyse": "...", "lien_wiki": "...", "image_query": "Divinite"}'
    ),
    "Gastronomie": (
        '{"titre": "...", "origine": "...", '
        '"analyse": "...", "lien_wiki": "...", "image_query": "Plat"}'
    ),
    "Sculpture": (
        '{"titre": "...", '
        '"sculpteur": "...", '
        '"analyse": "...", "lien_wiki": "...", '
        '"image_query": "Titre de l\'oeuvre, Nom de l\'Artiste, Lieu de conservation"}'
    ),
    "Arts de la scène": (
        '{"titre": "...", "auteur": "...", '
        '"analyse": "...", "lien_wiki": "...", '
        '"image_query": "Piece de theatre ou ballet"}'
    ),
    "Photographie": (
        '{"titre": "...", "photographe": "...", '
        '"analyse": "...", "lien_wiki": "...", '
        '"image_query": "Titre exact photographie"}'
    ),
    "Bande dessinée": (
        '{"titre": "...", "auteur": "...", '
        '"analyse": "...", "lien_wiki": "...", "image_query": "Serie BD"}'
    ),
    "Jeu vidéo": (
        '{"titre": "...", "studio": "...", '
        '"analyse": "...", "lien_wiki": "...", '
        '"image_query": "Titre jeu video"}'
    ),
}

# ============================================================
# BARRIÈRES SÉMANTIQUES (anti-confusion entre catégories)
# ============================================================
SEMANTIC_BARRIERS: dict[str, str] = {
    "Littérature": (
        "\n\nBARRIERE SEMANTIQUE STRICTE : Tu es dans la categorie LITTERATURE. "
        "Tu NE DOIS ABSOLUMENT PAS proposer de poesie, de poeme, de recueil de "
        "poesie, ni de piece de theatre. Tu dois proposer UNIQUEMENT un roman, "
        "un essai, un conte ou un recit en prose."
    ),
    "Poésie": (
        "\n\nBARRIERE SEMANTIQUE STRICTE : Tu es dans la categorie POESIE. "
        "Tu NE DOIS ABSOLUMENT PAS proposer de roman, d'essai, de conte ou "
        "de recit en prose. Tu dois proposer UNIQUEMENT un poeme ou un recueil "
        "de poesie."
    ),
    "Arts de la scène": (
        "\n\nBARRIERE SEMANTIQUE STRICTE : Tu es dans la categorie "
        "ARTS DE LA SCENE. Tu NE DOIS PAS proposer de piece de theatre qui "
        "serait deja classable en Litterature. Concentre-toi sur la mise en "
        "scene, la performance, la danse, l'opera ou le ballet."
    ),
}

# ============================================================
# RÈGLES DE NORMALISATION LINGUISTIQUE
# ============================================================
NORMALIZATION_RULES: dict[str, str] = {
    "Poésie": (
        "\n\nREGLE DE LISIBILITE OBLIGATOIRE : "
        "Si l'oeuvre originale est ecrite en vieux francais, moyen francais, "
        "ou toute forme linguistique archaique, tu DOIS imperativement la "
        "traduire ou l'adapter en francais contemporain fluide et accessible. "
        "Conserve la structure poetique, le rythme et la puissance emotionnelle "
        "de l'original. Le resultat doit etre comprehensible par un lecteur "
        "moderne sans effort."
    ),
    "Littérature": (
        "\n\nREGLE DE LISIBILITE OBLIGATOIRE : "
        "Si l'oeuvre originale est ecrite en vieux francais, moyen francais, "
        "ou toute forme linguistique archaique, tu DOIS imperativement la "
        "traduire ou l'adapter en francais contemporain fluide et accessible. "
        "Conserve la structure poetique, le rythme et la puissance emotionnelle "
        "de l'original. Le resultat doit etre comprehensible par un lecteur "
        "moderne sans effort."
    ),
}

# ============================================================
# CONFIGURATION DES RETRIES (tenacity)
# ============================================================
RETRY_CONFIG: dict[str, int] = {
    "min_wait": 4,      # secondes
    "max_wait": 30,     # secondes
    "max_attempts": 3,
}

# ============================================================
# CONFIGURATION DE RÉSILIENCE BASE DE DONNÉES
# ============================================================
DB_TIMEOUT: int = 8  # secondes — timeout unifié pour toutes les requêtes Supabase
CIRCUIT_BREAKER_THRESHOLD: int = 3  # échecs consécutifs avant ouverture du circuit
CIRCUIT_BREAKER_COOLDOWN: float = 30.0  # secondes avant tentative HALF_OPEN

# ============================================================
# SECRETS REQUIS
# ============================================================
REQUIRED_SECRETS: list[str] = ["DEEPSEEK_API_KEY", "SUPABASE_URL", "SUPABASE_KEY"]

# ============================================================
# OBJETS MET MUSEUM (seed déterministe)
# ============================================================
MET_OBJECT_IDS: list[int] = [
    436535, 436528, 436532, 435882, 435809,
    436533, 436529, 437112, 436121, 459123,
    437392, 437826, 438017, 435987, 436155,
]
