"""
daily_culture.py — Application principale "Le Banquet des Muses".

Point d'entrée Streamlit. Contient :
  - CSS Premium Gréco-Romain
  - Appels DeepSeek (prompts enrichis)
  - Moteur média (Wikipédia + Pollinations.ai)
  - Interface utilisateur (onglets, blocs, boutons)

La persistance est déléguée à database.py (Supabase).
"""

from __future__ import annotations

import datetime
import json
import random
import re
import urllib.parse
from typing import Optional

import requests
import streamlit as st

from database import SupabaseClient

# ============================================================
# CONFIGURATION STREAMLIT
# ============================================================
st.set_page_config(
    page_title="Le Banquet des Muses",
    page_icon="🏛️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ============================================================
# CSS PREMIUM (Style Gréco-Romain)
# ============================================================
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&display=swap');

.stApp { background-color: #f4f1ea; color: #2b2b2b; }

h1, h2, h3 { font-family: 'Cinzel', serif; color: #1a1a1a; text-align: center; }
h1 { font-size: 3rem; border-bottom: 2px solid #800020; padding-bottom: 20px; margin-bottom: 40px; }

p, div, span { font-family: 'Cormorant Garamond', serif; font-size: 1.3rem; line-height: 1.7; }

.poem-box {
    font-family: 'Cormorant Garamond', serif; font-size: 1.4rem; line-height: 1.9;
    padding-left: 25px; border-left: 3px solid #800020; white-space: pre-wrap;
    color: #1a1a1a; margin: 25px 0; background-color: #fdfbf7; padding: 25px;
    box-shadow: inset 0 0 10px rgba(0,0,0,0.03);
}

.quote-box {
    text-align: center; font-family: 'Cinzel', serif; font-size: 1.4rem;
    color: #800020; padding: 40px; margin-bottom: 50px;
    background: #fdfbf7; border: 1px solid #d4c4a8;
    box-shadow: 0 4px 15px rgba(0,0,0,0.05);
}

[data-testid="stImage"] img {
    border-radius: 4px;
    box-shadow: 0 8px 25px rgba(0,0,0,0.15);
    margin-bottom: 25px;
    border: 2px solid #d4c4a8;
}

.stButton button {
    width: 100%; border-radius: 4px; height: 50px;
    font-family: 'Cinzel', serif; font-weight: 600; letter-spacing: 1px;
}

[data-testid="stLinkButton"] a {
    background-color: #111827 !important;
    border: 1px solid #800020 !important;
    border-radius: 4px !important;
    text-decoration: none !important;
}
[data-testid="stLinkButton"] a p {
    color: #fdfbf7 !important;
    font-family: 'Cinzel', serif !important;
    font-weight: 600 !important;
    letter-spacing: 1px !important;
    margin: 0 !important;
}
[data-testid="stLinkButton"] a:hover {
    background-color: #800020 !important;
}

.placeholder-art {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    padding: 60px 20px; margin-bottom: 25px;
    background: linear-gradient(135deg, #fdfbf7 0%, #f4f1ea 100%);
    border: 2px solid #d4c4a8; border-radius: 4px;
    font-family: 'Cinzel', serif; color: #800020; text-align: center;
}
.placeholder-art .shield { font-size: 4rem; margin-bottom: 15px; }
.placeholder-art .subtitle {
    font-family: 'Cormorant Garamond', serif; font-style: italic;
    color: #555; font-size: 1.1rem; margin-top: 8px;
}
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
# VÉRIFICATION DES SECRETS
# ============================================================
REQUIRED_SECRETS = ["DEEPSEEK_API_KEY", "SUPABASE_URL", "SUPABASE_KEY"]
missing_secrets = [s for s in REQUIRED_SECRETS if s not in st.secrets]
if missing_secrets:
    st.error(
        "❌ **Clés manquantes dans les Secrets Streamlit :** "
        f"{', '.join(missing_secrets)}. "
        "Consultez le guide d'installation pour configurer Supabase."
    )
    st.stop()

DEEPSEEK_KEY: str = st.secrets["DEEPSEEK_API_KEY"]

# ============================================================
# INSTANCIATION DU CLIENT SUPABASE
# ============================================================
db = SupabaseClient()


# ============================================================
# HELPER JSON
# ============================================================
def extract_json(text: str) -> dict:
    """Extrait le premier objet JSON d'une chaîne de caractères."""
    try:
        match = re.search(r"\{.*\}", text.strip(), re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(text)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raise ValueError(f"Erreur de parsing JSON : {exc}") from exc


# ============================================================
# MOTEUR MÉDIA — Images sécurisées HTTPS
# ============================================================
def _normalize_url(raw_url: str | None) -> str | None:
    """Garantit que l'URL commence par 'https://'."""
    if not raw_url:
        return None
    url = str(raw_url)
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("http://"):
        url = url.replace("http://", "https://", 1)
    elif not url.startswith("https://"):
        url = "https://" + url
    return url


def get_wiki_image_secure(query: str, lang: str = "fr") -> Optional[str]:
    """Récupère une image Wikipédia avec garantie HTTPS.

    Retourne None si aucune image trouvée.
    """
    if not query or not query.strip():
        return None
    query = str(query).strip()
    headers = {"User-Agent": "BanquetDesMuses/7.0"}
    try:
        # Recherche de la page
        search_url = (
            f"https://{lang}.wikipedia.org/w/api.php"
            f"?action=query&list=search&srsearch={urllib.parse.quote(query)}"
            f"&utf8=&format=json&srlimit=1"
        )
        resp = requests.get(search_url, headers=headers, timeout=8)
        resp.raise_for_status()
        search_data = resp.json()
        if not search_data.get("query", {}).get("search"):
            return None
        page_title = search_data["query"]["search"][0]["title"]

        # Résumé de la page
        summary_url = (
            f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/"
            f"{urllib.parse.quote(page_title.replace(' ', '_'))}"
        )
        resp2 = requests.get(summary_url, headers=headers, timeout=8)
        resp2.raise_for_status()
        summary_data = resp2.json()

        raw_url = (
            summary_data.get("originalimage", {}).get("source")
            or summary_data.get("thumbnail", {}).get("source")
        )
        return _normalize_url(raw_url)

    except (requests.RequestException, json.JSONDecodeError, KeyError):
        return None


def fetch_image_cascade(res_dict: dict, category: str) -> Optional[str]:
    """Chaîne de récupération d'image avec règles métier.

    - Wikipédia en priorité (langue adaptée à la catégorie)
    - Architecture & Sculpture → pas de fallback IA (placeholder élégant)
    - Catégories abstraites → Pollinations avec prompt enrichi
    """
    primary_lang = (
        "en"
        if category
        in [
            "Cinéma", "Musique", "Architecture", "Littérature",
            "Jeu vidéo", "Photographie", "Sculpture", "Beaux-Arts",
        ]
        else "fr"
    )

    titre = res_dict.get("titre", "")
    auteur = (
        res_dict.get("auteur")
        or res_dict.get("artiste")
        or res_dict.get("sculpteur")
        or res_dict.get("realisateur")
        or res_dict.get("philosophe")
        or res_dict.get("inventeur")
        or ""
    )

    # Requêtes par ordre de pertinence
    queries_raw = [
        res_dict.get("image_query"),
        f"{titre} {auteur}".strip(),
        titre,
    ]
    queries = [str(q) for q in queries_raw if q and len(str(q)) > 2]

    # 1. Wikipédia (langue primaire puis secondaire)
    for q in queries:
        img = get_wiki_image_secure(q, primary_lang)
        if img:
            return img
        secondary = "fr" if primary_lang == "en" else "en"
        img = get_wiki_image_secure(q, secondary)
        if img:
            return img

    # 2. Règle stricte : Architecture & Sculpture → pas d'IA
    if category in ["Architecture", "Sculpture"]:
        return None

    # 3. Fallback Pollinations.ai
    if not queries:
        return None

    clean_query = re.sub(r"[^a-zA-Z0-9\s]", " ", f"{titre} {auteur}").strip()
    if not clean_query:
        clean_query = str(queries[0])

    if category in ["Philosophie", "Mythologie", "Poésie"]:
        ai_prompt = (
            f"Cinematic oil painting style, dramatic lighting, museum quality, "
            f"masterpiece elegant illustration of {clean_query}, {category} concept, "
            f"highly detailed, art gallery aesthetics"
        )
    else:
        ai_prompt = (
            f"Masterpiece elegant illustration of {clean_query}, "
            f"{category} concept, highly detailed"
        )

    safe_prompt = urllib.parse.quote(ai_prompt)
    return f"https://image.pollinations.ai/prompt/{safe_prompt}?width=800&height=500&nologo=true"


# ============================================================
# FOCUS QUOTIDIEN (déterministe par date)
# ============================================================
def get_daily_focus(category_name: str, date_str: str) -> str:
    """Sélection déterministe du sous-thème du jour via seed basée sur la date."""
    seed_val = int(date_str.replace("-", ""))
    rng = random.Random(seed_val)

    foci = {
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
    return rng.choice(foci.get(category_name, ["une oeuvre incontournable"]))


# ============================================================
# MOTEUR DE RECOMMENDATION
# ============================================================
def build_avoid_clause(category: str) -> str:
    """Construit la clause d'exclusion absolue pour le prompt DeepSeek."""
    titles = db.get_seen_titles(category)
    if not titles:
        return ""
    sample = titles[-60:]  # Limite de contexte
    lines = "\n".join(f"  - {t}" for t in sample)
    return (
        "\n\nLISTE D'EXCLUSION ABSOLUE (ne surtout PAS proposer ces oeuvres, deja vues) :\n"
        f"{lines}"
    )


def build_reco_clause() -> str:
    """Construit la clause de recommandation basée sur les préférences."""
    liked = db.get_liked_genres()
    disliked = db.get_disliked_authors()
    parts = []
    if liked:
        parts.append(
            "ORIENTATION RECOMMANDATION : L'utilisateur appreciate particulierement "
            f"les categories suivantes : {', '.join(liked)}. "
            "Inspire-toi de ces centres d'interet."
        )
    if disliked:
        parts.append(
            "EVITEMENT : L'utilisateur a indique ne pas apprecier les artistes "
            f"suivants : {', '.join(disliked)}. Evite de les proposer."
        )
    return "\n\n".join(parts)


# ============================================================
# APPEL DEEPSEEK
# ============================================================
@st.cache_data(show_spinner=False, ttl=3600)
def ask_deepseek(prompt: str, cache_salt: str) -> dict:
    """Interroge DeepSeek avec garantie de réponse JSON."""
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": (
                    "Tu es un erudit classique, conservateur de musee et critique d'art. "
                    "Tu fournis des analyses profondes (8 a 12 phrases).\n\n"
                    "REGLE ABSOLUE : TU DOIS PROPOSER DES OEUVRES REELLES ET "
                    "HISTORIQUEMENT EXACTES. AUCUNE INVENTION OU HALLUCINATION "
                    "DE TITRE/AUTEUR N'EST TOLEREE.\n\n"
                    "REGLE DE REALISME HISTORIQUE POUR ARCHITECTURE ET SCULPTURE : "
                    "Tu NE DOIS proposer QUE des oeuvres REELLES, EXISTANTES et "
                    "HISTORIQUEMENT ATTRIBUÉES. Aucune invention. Si tu ne connais "
                    "pas d'oeuvre correspondant aux criteres, retourne "
                    '{"erreur": true}.\n\n'
                    "Reponds STRICTEMENT en JSON pur, sans texte avant ni apres."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
        "max_tokens": 2048,
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=90)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return extract_json(content)
    except Exception:
        return {"erreur": True}


# ============================================================
# CITATION QUOTIDIENNE
# ============================================================
@st.cache_data(show_spinner=False, ttl=3600)
def fetch_quote_data(date_str: str) -> dict:
    """Génère la citation du jour avec évitement des auteurs récents."""
    seen_authors = db.get_seen_titles("Citation")
    avoid_clause = ""
    if seen_authors:
        recent = seen_authors[-15:]
        avoid_clause = (
            " INTERDICTION ABSOLUE de proposer un auteur parmi les suivants "
            f"(deja cites recemment) : {', '.join(recent)}."
        )
    prompt = (
        f"Donne une citation antique ou classique marquante, profonde et inspirante "
        f"pour l'edition du {date_str}.{avoid_clause}\n\n"
        'JSON attendu : {"citation": "...", "auteur": "..."}'
    )
    data = ask_deepseek(prompt, f"{date_str}_quote")
    if data and data.get("auteur"):
        db.add_to_seen("Citation", data["auteur"], date_seen=date_str)
    return data


# ============================================================
# CONTENU PAR CATÉGORIE
# ============================================================
@st.cache_data(show_spinner=False, ttl=3600)
def get_content_item(category_name: str, date_str: str) -> dict:
    """Génère une oeuvre pour une catégorie avec anti-repetition et recommandation."""

    # Templates JSON
    json_templates = {
        "Poesie": (
            '{"titre": "...", "auteur": "...", '
            '"poeme_entier": "Texte integral traduit en francais contemporain moderne. '
            "Si l'original est en vieux francais, le traduire impérativement "
            'en francais actuel fluide, tout en conservant le rythme poetique.", '
            '"analyse": "...", "lien_wiki": "...", "image_query": "Auteur Wikipedia"}'
        ),
        "Litterature": (
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
        "Cinema": (
            '{"titre": "...", "realisateur": "...", "annee": "...", '
            '"analyse": "...", "lien_wiki": "...", "image_query": "Film Wikipedia"}'
        ),
        "Architecture": (
            '{"titre": "Nom exact et REEL", "lieu": "...", "architecte": "...", '
            '"analyse": "...", "lien_wiki": "...", '
            '"image_query": "Nom complet exact pour Wikipedia"}'
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
            '{"titre": "Nom exact et REEL", '
            '"sculpteur": "Sculpteur historique VERITABLE", '
            '"analyse": "...", "lien_wiki": "...", '
            '"image_query": "Nom de la sculpture Wikipedia"}'
        ),
        "Arts de la scene": (
            '{"titre": "...", "auteur": "...", '
            '"analyse": "...", "lien_wiki": "...", '
            '"image_query": "Piece de theatre ou ballet"}'
        ),
        "Photographie": (
            '{"titre": "...", "photographe": "...", '
            '"analyse": "...", "lien_wiki": "...", '
            '"image_query": "Titre exact photographie"}'
        ),
        "Bande dessinee": (
            '{"titre": "...", "auteur": "...", '
            '"analyse": "...", "lien_wiki": "...", "image_query": "Serie BD"}'
        ),
        "Jeu video": (
            '{"titre": "...", "studio": "...", '
            '"analyse": "...", "lien_wiki": "...", '
            '"image_query": "Titre jeu video"}'
        ),
    }

    focus = get_daily_focus(category_name, date_str)

    # Anti-repetition
    avoid_clause = build_avoid_clause(category_name)

    # Profil de recommandation
    reco_clause = build_reco_clause()

    # Barrieres semantiques anti-doublons
    semantic_barrier = ""
    if category_name == "Litterature":
        semantic_barrier = (
            "\n\nBARRIERE SEMANTIQUE STRICTE : Tu es dans la categorie LITTERATURE. "
            "Tu NE DOIS ABSOLUMENT PAS proposer de poesie, de poeme, de recueil de "
            "poesie, ni de piece de theatre. Tu dois proposer UNIQUEMENT un roman, "
            "un essai, un conte ou un recit en prose."
        )
    elif category_name == "Poesie":
        semantic_barrier = (
            "\n\nBARRIERE SEMANTIQUE STRICTE : Tu es dans la categorie POESIE. "
            "Tu NE DOIS ABSOLUMENT PAS proposer de roman, d'essai, de conte ou "
            "de recit en prose. Tu dois proposer UNIQUEMENT un poeme ou un recueil "
            "de poesie."
        )
    elif category_name == "Arts de la scene":
        semantic_barrier = (
            "\n\nBARRIERE SEMANTIQUE STRICTE : Tu es dans la categorie "
            "ARTS DE LA SCENE. Tu NE DOIS PAS proposer de piece de theatre qui "
            "serait deja classable en Litterature. Concentre-toi sur la mise en "
            "scene, la performance, la danse, l'opera ou le ballet."
        )

    # Normalisation linguistique
    normalization_rule = ""
    if category_name in ["Poesie", "Litterature"]:
        normalization_rule = (
            "\n\nREGLE DE LISIBILITE OBLIGATOIRE : "
            "Si l'oeuvre originale est ecrite en vieux francais, moyen francais, "
            "ou toute forme linguistique archaique, tu DOIS imperativement la "
            "traduire ou l'adapter en francais contemporain fluide et accessible. "
            "Conserve la structure poetique, le rythme et la puissance emotionnelle "
            "de l'original. Le resultat doit etre comprehensible par un lecteur "
            "moderne sans effort."
        )

    # Assemblage du prompt
    json_example = json_templates.get(
        category_name,
        '{"titre": "...", "analyse": "..."}',
    )
    prompt = (
        f"Edition du {date_str}. Propose une NOUVELLE oeuvre REELLE et HISTORIQUE "
        f"pour la categorie : {category_name}.\n\n"
        f"Theme du jour impose : {focus}.\n"
        f"{avoid_clause}"
        f"{reco_clause}"
        f"{semantic_barrier}"
        f"{normalization_rule}"
        f"\n\nFormat strictement respecte : {json_example}"
    )

    res = ask_deepseek(prompt, f"{date_str}_{category_name}")
    if res.get("erreur"):
        return res

    # Image
    res["image"] = fetch_image_cascade(res, category_name)

    # Historique
    titre = res.get("titre") or res.get("concept") or "Inconnu"
    auteur = (
        res.get("auteur")
        or res.get("artiste")
        or res.get("sculpteur")
        or res.get("realisateur")
        or res.get("philosophe")
        or res.get("inventeur")
        or res.get("photographe")
        or res.get("studio")
        or ""
    )
    db.add_to_seen(category_name, titre, auteur, date_str)

    return res


# ============================================================
# BEAUX-ARTS (MET Museum)
# ============================================================
@st.cache_data(show_spinner=False, ttl=3600)
def get_art_safe(date_str: str) -> dict:
    """Oeuvre du MET Museum analysee par DeepSeek."""
    random.seed(int(date_str.replace("-", "")))
    object_ids = [
        436535, 436528, 436532, 435882, 435809,
        436533, 436529, 437112, 436121, 459123,
        437392, 437826, 438017, 435987, 436155,
    ]
    try:
        obj_id = random.choice(object_ids)
        resp = requests.get(
            f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{obj_id}",
            timeout=15,
        ).json()

        title = resp.get("title", "Oeuvre d'art")
        artist = resp.get("artistDisplayName", "Artiste inconnu")
        image_url = _normalize_url(
            resp.get("primaryImageSmall") or resp.get("primaryImage")
        )

        ds = ask_deepseek(
            f"Analyse artistique approfondie de l'oeuvre '{title}' par {artist}. "
            f'JSON attendu : {{"titre_fr": "...", "analyse": "...", '
            f'"lien_wiki": "..."}}',
            f"{date_str}_art",
        )

        return {
            "titre": ds.get("titre_fr", title),
            "auteur": artist,
            "image": image_url or "",
            "analyse": ds.get("analyse", ""),
            "lien_wiki": ds.get("lien_wiki") or resp.get("objectURL", ""),
        }
    except Exception:
        return {"erreur": True}


# ============================================================
# AFFICHAGE — Bloc de contenu
# ============================================================
def render_block_safe(
    icon: str,
    label: str,
    data: dict,
    date_str: str,
    context_id: str,
    color: str = "#c5a059",
) -> None:
    """Affiche un bloc oeuvre complet (titre, image, analyse, boutons)."""
    if not data or data.get("erreur"):
        return

    titre = data.get("titre") or data.get("concept") or "Inconnu"
    auteur = (
        data.get("auteur")
        or data.get("artiste")
        or data.get("realisateur")
        or data.get("philosophe")
        or data.get("inventeur")
        or data.get("origine")
        or data.get("lieu")
        or data.get("sculpteur")
        or data.get("photographe")
        or data.get("studio")
        or data.get("architecte")
        or ""
    )
    analyse = data.get("analyse") or ""
    image_url = data.get("image")
    wiki = data.get("lien_wiki")
    content_text = data.get("poeme_entier") or data.get("extrait")
    safe_key = f"{label}_{date_str}_{context_id}"

    with st.container(border=True):
        st.markdown(
            f"""
            <div style="text-align: center; margin-bottom: 25px;">
                <span style="color: {color}; font-family: 'Cinzel', serif;
                      font-weight: 700; text-transform: uppercase;
                      letter-spacing: 3px; font-size: 1rem;">
                    {icon} {label}
                </span>
                <h2 style="margin: 15px 0 5px 0; font-size: 2.4rem;
                    color: #1a1a1a;">
                    {titre}
                </h2>
                <h4 style="font-family: 'Cormorant Garamond', serif;
                    font-style: italic; color: #555; font-size: 1.4rem;
                    font-weight: normal; margin-top: 0;">
                    {auteur}
                </h4>
                <hr style="width: 60px; margin: 20px auto;
                    border: 1px solid {color};">
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Image ou placeholder
        if image_url:
            st.image(image_url, use_container_width=True)
        elif label in ["Architecture", "Sculpture"]:
            st.markdown(
                f"""
                <div class="placeholder-art">
                    <div class="shield">🏛️</div>
                    <h3 style="color: #800020; margin: 10px 0;">{titre}</h3>
                    <p style="font-family: 'Cormorant Garamond', serif;
                        color: #555; font-style: italic;">
                        {auteur}
                    </p>
                    <div class="subtitle">
                        Aucune image reelle disponible &mdash;
                        l'oeuvre est authentifiee
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if content_text:
            st.markdown(
                f'<div class="poem-box">{content_text}</div>',
                unsafe_allow_html=True,
            )

        st.write(analyse)

        # Boutons
        st.write("")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("👍 J'aime", key=f"btn_l_{safe_key}"):
                db.save_preference(label, titre, auteur, True, date_str)
                st.toast("Ajoute aux favoris ! ⭐")
        with c2:
            if st.button("👎 Bof", key=f"btn_d_{safe_key}"):
                db.save_preference(label, titre, auteur, False, date_str)
                st.toast("Preference enregistree ✨")

        if wiki:
            if label == "Musique":
                btn_label = "🎧 Ecouter (YouTube Music)"
                query = urllib.parse.quote(f"{auteur} {titre}")
                wiki = f"https://music.youtube.com/search?q={query}"
            else:
                btn_label = "📖 Approfondir"
            st.link_button(btn_label, wiki, use_container_width=True)


# ============================================================
# EXPOSITION COMPLÈTE
# ============================================================
def display_exposition(target_date: datetime.date, context_id: str) -> None:
    """Affiche l'exposition complete pour une date donnee."""
    date_str = target_date.strftime("%Y-%m-%d")

    st.markdown(
        f"<p style='text-align: center; color: #555; font-size: 1.4rem; "
        f"font-style: italic;'>Edition du "
        f"{target_date.strftime('%d %B %Y')}</p>",
        unsafe_allow_html=True,
    )

    # Cache : l'edition existe-t-elle deja en base ?
    edition_cache = db.get_edition(date_str)

    if edition_cache:
        quote = edition_cache.get("quote", {})
        art = edition_cache.get("art", {})
        blocks_data = edition_cache.get("blocks", {})
    else:
        with st.spinner("Les Muses preparent le banquet..."):
            quote = fetch_quote_data(date_str)
            art = get_art_safe(date_str)

            categories = [
                ("Poesie", "#c5a059", "📜"),
                ("Litterature", "#800020", "📚"),
                ("Musique", "#2b2b2b", "🎵"),
                ("Sciences", "#4a6b5d", "🌍"),
                ("Philosophie", "#800020", "🧠"),
                ("Cinema", "#1a1a1a", "🎬"),
                ("Architecture", "#555555", "🏛️"),
                ("Mythologie", "#c5a059", "⚡"),
                ("Gastronomie", "#800020", "🍷"),
                ("Sculpture", "#696969", "🗿"),
                ("Arts de la scene", "#8B0000", "🎭"),
                ("Photographie", "#2F4F4F", "📷"),
                ("Bande dessinee", "#B8860B", "🖋️"),
                ("Jeu video", "#2E8B57", "🎮"),
            ]
            blocks_data = {}
            for name, _color, _icon in categories:
                blocks_data[name] = get_content_item(name, date_str)

            # Sauvegarder en cache pour les lectures futures
            db.save_edition(
                date_str,
                {"quote": quote, "art": art, "blocks": blocks_data},
            )

    # Citation
    if quote and not quote.get("erreur"):
        st.markdown(
            f"<div class='quote-box'>« {quote.get('citation')} »"
            f"<br><br><small>&mdash; {quote.get('auteur')}</small></div>",
            unsafe_allow_html=True,
        )

    # Beaux-Arts
    render_block_safe("🖼️", "Beaux-Arts", art, date_str, context_id, color="#800020")

    # 14 categories
    display_categories = [
        ("Poesie", "#c5a059", "📜"),
        ("Litterature", "#800020", "📚"),
        ("Musique", "#2b2b2b", "🎵"),
        ("Sciences", "#4a6b5d", "🌍"),
        ("Philosophie", "#800020", "🧠"),
        ("Cinema", "#1a1a1a", "🎬"),
        ("Architecture", "#555555", "🏛️"),
        ("Mythologie", "#c5a059", "⚡"),
        ("Gastronomie", "#800020", "🍷"),
        ("Sculpture", "#696969", "🗿"),
        ("Arts de la scene", "#8B0000", "🎭"),
        ("Photographie", "#2F4F4F", "📷"),
        ("Bande dessinee", "#B8860B", "🖋️"),
        ("Jeu video", "#2E8B57", "🎮"),
    ]
    for name, color, icon in display_categories:
        data = blocks_data.get(name, {})
        render_block_safe(icon, name, data, date_str, context_id, color)


# ============================================================
# APPLICATION PRINCIPALE
# ============================================================
st.title("Le Banquet des Muses")

t1, t2, t3 = st.tabs(["✨ Aujourd'hui", "📅 Archives", "⭐ Favoris"])

# Onglet 1 : Aujourd'hui
with t1:
    display_exposition(datetime.date.today(), context_id="today")

# Onglet 2 : Archives
with t2:
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    d = st.date_input(
        "Choisissez une date :",
        value=yesterday,
        max_value=datetime.date.today(),
        min_value=datetime.date(2025, 1, 1),
    )
    if d != datetime.date.today():
        display_exposition(d, context_id="archive")

# Onglet 3 : Favoris
with t3:
    st.success(
        "☁️ **Sauvegarde Cloud activee** &mdash; Vos favoris sont stockes "
        "de maniere permanente sur Supabase. Ils survivent aux redemarrages "
        "du serveur !"
    )

    prefs = db.get_preferences()
    liked = [p for p in prefs if p.get("liked")]

    if not liked:
        st.info(
            "Aucun favori pour le moment. Allez donner un 👍 "
            "a vos oeuvres preferees !"
        )
    else:
        st.write(f"**{len(liked)} oeuvre(s) favorite(s)** enregistree(s)")
        for p in sorted(liked, key=lambda x: x.get("date_str", ""), reverse=True):
            with st.container(border=True):
                st.markdown(
                    f"**{p.get('category', '?')}** : {p.get('title', '?')} "
                    f"*({p.get('author', '?')})*"
                )
                st.caption(f"Sauvegarde le {p.get('date_str', '?')}")
