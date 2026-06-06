"""
daily_culture.py — Application principale "Le Banquet des Muses".

Point d'entrée Streamlit. Contient :
  - CSS Premium Gréco-Romain
  - Appels DeepSeek (prompts enrichis) avec retry tenacity
  - Moteur média (Wikipédia + Pollinations.ai) avec retry
  - Interface utilisateur (onglets, blocs, boutons, partage)
  - Progression dynamique via st.status()

La persistance est déléguée à database.py (Supabase).
La configuration statique est externalisée dans config.py.
"""

from __future__ import annotations

import datetime
import json
import logging
import random
import re
import urllib.parse
from typing import Any, Optional

import requests
import streamlit as st
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import (
    ABSTRACT_CATEGORIES,
    CATEGORIES,
    ENGLISH_PRIMARY_CATEGORIES,
    FOCI,
    JSON_TEMPLATES,
    MET_OBJECT_IDS,
    NO_AI_FALLBACK_CATEGORIES,
    NORMALIZATION_RULES,
    REQUIRED_SECRETS,
    RETRY_CONFIG,
    SEMANTIC_BARRIERS,
)
from database import SupabaseClient

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger("banquet_des_muses")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)s — %(message)s"
    ))
    logger.addHandler(handler)

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
# CSS PREMIUM (Style Gréco-Romain) — mis en cache
# ============================================================
@st.cache_resource
def _get_css() -> str:
    """Retourne le bloc CSS complet (mis en cache pour éviter le re-rendu)."""
    return """
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

.error-block {
    text-align: center; padding: 40px 20px; margin: 25px 0;
    background: #fdfbf7; border: 1px solid #d4c4a8;
    border-left: 4px solid #800020;
    font-family: 'Cormorant Garamond', serif;
}
.error-block .muse-icon { font-size: 3rem; margin-bottom: 10px; }
.error-block .error-title {
    font-family: 'Cinzel', serif; color: #800020;
    font-size: 1.3rem; margin-bottom: 8px;
}
.error-block .error-detail {
    color: #555; font-style: italic; font-size: 1.1rem;
}
</style>
"""

st.markdown(_get_css(), unsafe_allow_html=True)

# ============================================================
# VÉRIFICATION DES SECRETS
# ============================================================
missing_secrets: list[str] = [s for s in REQUIRED_SECRETS if s not in st.secrets]
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
# HELPER JSON — Moteur de Parsing Ultra-Robuste
# ============================================================
def _sanitize_json_string(raw: str) -> str:
    """Nettoie et répare une chaîne JSON malformée provenant d'un LLM.

    Gère les problèmes courants :
    - Blocs de code markdown ```json ... ```
    - Retours à la ligne non échappés dans les chaînes
    - Guillemets doubles orphelins/imbriqués dans les valeurs texte
    - Caractères de contrôle invalides
    - Virgules trailing avant }

    Args:
        raw: Chaîne brute potentiellement contenant du JSON malformé.

    Returns:
        Chaîne nettoyée prête pour json.loads().
    """
    text = raw.strip()

    # 1. Suppression des blocs de code markdown
    text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```\s*$", "", text)

    # 2. Extraction du premier objet JSON si du texte l'entoure
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)

    # 3. Suppression des caractères de contrôle (sauf \n, \t, \r légitimes)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)

    # 4. Réparation des virgules trailing avant } ou ]
    text = re.sub(r",(\s*[}\]])", r"\1", text)

    # 5. Tentative de réparation des guillemets doubles non échappés
    #    dans les valeurs de chaînes (pattern: "valeur avec "mot" interne")
    #    On utilise une approche conservative : on ne touche qu'aux cas
    #    où un guillemet apparaît après un caractère non-échappement
    #    dans une valeur string.
    def _fix_nested_quotes(match_obj: re.Match[str]) -> str:
        key: str = match_obj.group(1)
        value: str = match_obj.group(2)
        # Échappe les guillemets doubles dans la valeur
        fixed_value: str = value.replace('"', '\\"')
        return f'"{key}": "{fixed_value}"'

    # Pattern: "key": "value with possible "nested" quotes"
    text = re.sub(
        r'"(?P<key>[^"]+)":\s*"(?P<value>.*?)"(?=\s*[,}\]])',
        _fix_nested_quotes,
        text,
        flags=re.DOTALL,
    )

    return text


def extract_json(text: str) -> dict[str, Any]:
    """Extrait et parse le premier objet JSON d'une chaîne de caractères.

    Utilise un pipeline de sanitization robuste pour gérer les sorties
    malformées des LLMs (DeepSeek, etc.) : blocs markdown, retours à la
    ligne non échappés, guillemets orphelins, caractères de contrôle.

    Args:
        text: Chaîne contenant potentiellement du JSON.

    Returns:
        Dictionnaire parsé.

    Raises:
        ValueError: Si le JSON est irrécupérable après sanitization.
    """
    if not text or not text.strip():
        raise ValueError("Chaîne JSON vide ou None")

    errors: list[str] = []

    # Tentative 1 : Parsing direct
    try:
        match = re.search(r"\{.*\}", text.strip(), re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(text)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        errors.append(f"direct: {exc}")

    # Tentative 2 : Après sanitization
    try:
        sanitized: str = _sanitize_json_string(text)
        return json.loads(sanitized)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        errors.append(f"sanitized: {exc}")

    # Tentative 3 : Dernière chance — réparation agressive
    try:
        # Supprime tous les guillemets non échappés problématiques
        aggressive: str = re.sub(
            r'(?<!\\)"(?=(?:[^"]*"[^"]*")*[^"]*$)',
            "'",
            text,
        )
        match = re.search(r"\{.*\}", aggressive, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(aggressive)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        errors.append(f"aggressive: {exc}")

    raise ValueError(
        f"Erreur de parsing JSON après 3 tentatives : {' | '.join(errors)}"
    )


# ============================================================
# MOTEUR MÉDIA — Images sécurisées HTTPS
# ============================================================
def _normalize_url(raw_url: str | None) -> str | None:
    """Garantit que l'URL commence par 'https://'.

    Args:
        raw_url: URL brute potentiellement non sécurisée.

    Returns:
        URL normalisée ou None si l'entrée est vide.
    """
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


@retry(
    stop=stop_after_attempt(RETRY_CONFIG["max_attempts"]),
    wait=wait_exponential(
        multiplier=2,
        min=RETRY_CONFIG["min_wait"],
        max=RETRY_CONFIG["max_wait"],
    ),
    retry=retry_if_exception_type((requests.RequestException, json.JSONDecodeError)),
)
def get_wiki_image_secure(query: str, lang: str = "fr") -> Optional[str]:
    """Récupère une image Wikipédia avec garantie HTTPS et retry.

    Args:
        query: Terme de recherche.
        lang: Code de langue Wikipédia (défaut: "fr").

    Returns:
        URL de l'image ou None si aucune image trouvée.
    """
    if not query or not query.strip():
        return None
    query = str(query).strip()
    headers = {"User-Agent": "BanquetDesMuses/7.0"}
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


def fetch_image_cascade(res_dict: dict[str, Any], category: str) -> Optional[str]:
    """Chaîne de récupération d'image avec règles métier.

    - Wikipédia en priorité (langue adaptée à la catégorie)
    - Architecture & Sculpture → pas de fallback IA (placeholder élégant)
    - Catégories abstraites → Pollinations avec prompt enrichi

    Args:
        res_dict: Dictionnaire de l'oeuvre (contient titre, auteur, image_query).
        category: Nom de la catégorie.

    Returns:
        URL de l'image ou None.
    """
    primary_lang = "en" if category in ENGLISH_PRIMARY_CATEGORIES else "fr"

    titre: str = res_dict.get("titre", "")
    auteur: str = (
        res_dict.get("auteur")
        or res_dict.get("artiste")
        or res_dict.get("sculpteur")
        or res_dict.get("realisateur")
        or res_dict.get("philosophe")
        or res_dict.get("inventeur")
        or ""
    )

    # Requêtes par ordre de pertinence
    queries_raw: list[Any] = [
        res_dict.get("image_query"),
        f"{titre} {auteur}".strip(),
        titre,
    ]
    queries: list[str] = [str(q) for q in queries_raw if q and len(str(q)) > 2]

    # 1. Wikipédia (langue primaire puis secondaire)
    try:
        for q in queries:
            try:
                img = get_wiki_image_secure(q, primary_lang)
                if img:
                    return img
                secondary = "fr" if primary_lang == "en" else "en"
                img = get_wiki_image_secure(q, secondary)
                if img:
                    return img
            except (requests.RequestException, json.JSONDecodeError):
                logger.warning("Échec récupération image Wikipédia pour : %s", q)
                continue
    except Exception:
        logger.exception(
            "Crash réseau dans fetch_image_cascade — toutes les tentatives "
            "Wikipédia ont échoué (timeout, RetryError, etc.). "
            "Bascule vers fallback ou placeholder."
        )

    # 2. Règle stricte : Architecture & Sculpture → pas d'IA
    if category in NO_AI_FALLBACK_CATEGORIES:
        return None

    # 3. Fallback Pollinations.ai
    if not queries:
        return None

    clean_query: str = re.sub(r"[^a-zA-Z0-9\s]", " ", f"{titre} {auteur}").strip()
    if not clean_query:
        clean_query = str(queries[0])

    if category in ABSTRACT_CATEGORIES:
        ai_prompt: str = (
            f"Cinematic oil painting style, dramatic lighting, museum quality, "
            f"masterpiece elegant illustration of {clean_query}, {category} concept, "
            f"highly detailed, art gallery aesthetics"
        )
    else:
        ai_prompt: str = (
            f"Masterpiece elegant illustration of {clean_query}, "
            f"{category} concept, highly detailed"
        )

    safe_prompt: str = urllib.parse.quote(ai_prompt)
    return f"https://image.pollinations.ai/prompt/{safe_prompt}?width=800&height=500&nologo=true"


# ============================================================
# FOCUS QUOTIDIEN (déterministe par date)
# ============================================================
def get_daily_focus(category_name: str, date_str: str) -> str:
    """Sélection déterministe du sous-thème du jour via seed basée sur la date.

    Args:
        category_name: Nom de la catégorie.
        date_str: Date au format "YYYY-MM-DD".

    Returns:
        Sous-thème choisi aléatoirement de manière déterministe.
    """
    seed_val = int(date_str.replace("-", ""))
    rng = random.Random(seed_val)
    return rng.choice(FOCI.get(category_name, ["une oeuvre incontournable"]))


# ============================================================
# MOTEUR DE RECOMMENDATION
# ============================================================
def build_avoid_clause(category: str) -> str:
    """Construit la clause d'exclusion absolue pour le prompt DeepSeek.

    Args:
        category: Nom de la catégorie.

    Returns:
        Texte de clause d'exclusion ou chaîne vide.
    """
    titles: list[str] = db.get_seen_titles(category)
    if not titles:
        return ""
    sample: list[str] = titles[-60:]  # Limite de contexte
    lines: str = "\n".join(f"  - {t}" for t in sample)
    return (
        "\n\nLISTE D'EXCLUSION ABSOLUE (ne surtout PAS proposer ces oeuvres, deja vues) :\n"
        f"{lines}"
    )


def build_reco_clause() -> str:
    """Construit la clause de recommandation basée sur les préférences.

    Returns:
        Texte de clause de recommandation ou chaîne vide.
    """
    liked: list[str] = db.get_liked_genres()
    disliked: list[str] = db.get_disliked_authors()
    parts: list[str] = []
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
# APPEL DEEPSEEK — avec retry et gestion du cache des erreurs
# ============================================================
@retry(
    stop=stop_after_attempt(RETRY_CONFIG["max_attempts"]),
    wait=wait_exponential(
        multiplier=2,
        min=RETRY_CONFIG["min_wait"],
        max=RETRY_CONFIG["max_wait"],
    ),
    retry=retry_if_exception_type((requests.RequestException, ValueError)),
)
def _call_deepseek(prompt: str) -> dict[str, Any]:
    """Effectue l'appel HTTP à l'API DeepSeek (sans cache).

    Args:
        prompt: Prompt complet à envoyer.

    Returns:
        Dictionnaire JSON de la réponse.

    Raises:
        requests.RequestException: En cas d'échec réseau.
        ValueError: En cas d'erreur de parsing JSON.
    """
    url = "https://api.deepseek.com/chat/completions"
    headers: dict[str, str] = {
        "Authorization": f"Bearer {DEEPSEEK_KEY}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
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
    resp = requests.post(url, headers=headers, json=payload, timeout=90)
    resp.raise_for_status()
    content: str = resp.json()["choices"][0]["message"]["content"]
    return extract_json(content)


@st.cache_data(show_spinner=False, ttl=3600)
def ask_deepseek(prompt: str, cache_salt: str) -> dict[str, Any]:
    """Interroge DeepSeek avec garantie de réponse JSON et cache.

    ATTENTION : Les réponses d'erreur ({"erreur": True}) ne sont PAS mises en cache
    pour permettre un retry immédiat au prochain appel.

    Args:
        prompt: Prompt à envoyer à DeepSeek.
        cache_salt: Sel de cache (ex: date + catégorie).

    Returns:
        Dictionnaire JSON de la réponse, ou {"erreur": True} si échec.
    """
    try:
        result: dict[str, Any] = _call_deepseek(prompt)
        # Ne pas mettre en cache les réponses d'erreur
        if result.get("erreur"):
            st.cache_data.clear()
            logger.warning("DeepSeek a retourné une erreur pour : %s", cache_salt)
        return result
    except (requests.RequestException, ValueError) as exc:
        logger.error("Échec appel DeepSeek (%s) : %s", cache_salt, exc)
        return {"erreur": True}


# ============================================================
# CITATION QUOTIDIENNE
# ============================================================
@st.cache_data(show_spinner=False, ttl=3600)
def fetch_quote_data(date_str: str) -> dict[str, Any]:
    """Génère la citation du jour avec évitement des textes et auteurs récents.

    La colonne 'title' stocke le texte intégral de la citation (UNIQUE),
    la colonne 'author' stocke le nom de l'auteur.

    Args:
        date_str: Date au format "YYYY-MM-DD".

    Returns:
        Dictionnaire contenant "citation" et "auteur", ou {"erreur": True}.
    """
    # Récupération des textes de citations déjà vus (dans title)
    seen_texts: list[str] = db.get_seen_titles("Citation")
    # Récupération des auteurs récents (dans author)
    seen_authors: list[str] = db.get_seen_authors("Citation")

    avoid_parts: list[str] = []

    if seen_texts:
        recent_texts: list[str] = seen_texts[-30:]
        avoid_parts.append(
            "INTERDICTION ABSOLUE de recycler un texte connu en lui attribuant "
            "un faux auteur. Voici les citations DEJA PUBLIEES (tu ne dois "
            "en reproduire AUCUNE, meme partiellement) :\n"
            + "\n".join(f"  - \"{t[:120]}{'...' if len(t)>120 else ''}\""
                        for t in recent_texts)
        )

    if seen_authors:
        recent_authors: list[str] = seen_authors[-15:]
        avoid_parts.append(
            "INTERDICTION ABSOLUE de proposer un auteur parmi les suivants "
            f"(deja cites recemment) : {', '.join(recent_authors)}."
        )

    avoid_clause: str = "\n\n".join(avoid_parts)
    if avoid_clause:
        avoid_clause = "\n\n" + avoid_clause

    prompt: str = (
        f"Donne une citation antique ou classique marquante, profonde et inspirante "
        f"pour l'edition du {date_str}.{avoid_clause}\n\n"
        "REGLE D'INTEGRITE HISTORIQUE : Tu dois faire preuve d'une rigueur "
        "historique absolue. INTERDICTION ABSOLUE d'attribuer une citation "
        "celebre a quelqu'un d'autre que son veritable auteur. Chaque citation "
        "doit etre authentique et verifiable.\n\n"
        'JSON attendu : {"citation": "...", "auteur": "..."}'
    )
    data: dict[str, Any] = ask_deepseek(prompt, f"{date_str}_quote")
    if data and data.get("citation") and data.get("auteur"):
        # Stocke le TEXTE dans title (UNIQUE) et l'AUTEUR dans author
        db.add_to_seen("Citation", data["citation"], data["auteur"], date_seen=date_str)
    return data


# ============================================================
# CONTENU PAR CATÉGORIE
# ============================================================
@st.cache_data(show_spinner=False, ttl=3600)
def get_content_item(category_name: str, date_str: str) -> dict[str, Any]:
    """Génère une oeuvre pour une catégorie avec anti-repetition et recommandation.

    Args:
        category_name: Nom de la catégorie.
        date_str: Date au format "YYYY-MM-DD".

    Returns:
        Dictionnaire de l'oeuvre générée, ou {"erreur": True}.
    """
    focus: str = get_daily_focus(category_name, date_str)

    # Anti-repetition
    avoid_clause: str = build_avoid_clause(category_name)

    # Profil de recommandation
    reco_clause: str = build_reco_clause()

    # Barrieres semantiques anti-doublons
    semantic_barrier: str = SEMANTIC_BARRIERS.get(category_name, "")

    # Normalisation linguistique
    normalization_rule: str = NORMALIZATION_RULES.get(category_name, "")

    # Assemblage du prompt
    json_example: str = JSON_TEMPLATES.get(
        category_name,
        '{"titre": "...", "analyse": "..."}',
    )
    prompt: str = (
        f"Edition du {date_str}. Propose une NOUVELLE oeuvre REELLE et HISTORIQUE "
        f"pour la categorie : {category_name}.\n\n"
        f"Theme du jour impose : {focus}.\n"
        f"{avoid_clause}"
        f"{reco_clause}"
        f"{semantic_barrier}"
        f"{normalization_rule}"
        f"\n\nFormat strictement respecte : {json_example}"
    )

    res: dict[str, Any] = ask_deepseek(prompt, f"{date_str}_{category_name}")
    if res.get("erreur"):
        return res

    # Image
    res["image"] = fetch_image_cascade(res, category_name)

    # Historique
    titre: str = res.get("titre") or res.get("concept") or "Inconnu"
    auteur: str = (
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
@retry(
    stop=stop_after_attempt(RETRY_CONFIG["max_attempts"]),
    wait=wait_exponential(
        multiplier=2,
        min=RETRY_CONFIG["min_wait"],
        max=RETRY_CONFIG["max_wait"],
    ),
    retry=retry_if_exception_type((requests.RequestException, KeyError)),
)
@st.cache_data(show_spinner=False, ttl=3600)
def get_art_safe(date_str: str) -> dict[str, Any]:
    """Oeuvre du MET Museum analysée par DeepSeek, avec retry.

    Args:
        date_str: Date au format "YYYY-MM-DD".

    Returns:
        Dictionnaire de l'oeuvre d'art, ou {"erreur": True}.
    """
    random.seed(int(date_str.replace("-", "")))
    try:
        obj_id: int = random.choice(MET_OBJECT_IDS)
        resp: dict[str, Any] = requests.get(
            f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{obj_id}",
            timeout=15,
        ).json()

        title: str = resp.get("title", "Oeuvre d'art")
        artist: str = resp.get("artistDisplayName", "Artiste inconnu")
        image_url: str | None = _normalize_url(
            resp.get("primaryImageSmall") or resp.get("primaryImage")
        )

        ds: dict[str, Any] = ask_deepseek(
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
    except Exception as exc:
        logger.error("Échec récupération MET Museum : %s", exc)
        return {"erreur": True}


# ============================================================
# AFFICHAGE — Bloc de contenu
# ============================================================
def render_block_safe(
    icon: str,
    label: str,
    data: dict[str, Any],
    date_str: str,
    context_id: str,
    color: str = "#c5a059",
) -> None:
    """Affiche un bloc oeuvre complet (titre, image, analyse, boutons).

    En cas d'erreur, affiche un bloc stylisé "Les Muses sont en retard..."
    au lieu d'un silence gênant.

    Args:
        icon: Emoji/icône de la catégorie.
        label: Nom de la catégorie.
        data: Dictionnaire de l'oeuvre.
        date_str: Date au format "YYYY-MM-DD".
        context_id: Identifiant de contexte (ex: "today", "archive").
        color: Couleur hexadécimale du thème de la catégorie.
    """
    if not data or data.get("erreur"):
        st.markdown(
            f"""
            <div class="error-block">
                <div class="muse-icon">{icon}</div>
                <div class="error-title">{label} — Les Muses sont en retard...</div>
                <div class="error-detail">
                    Les Parques n'ont pas encore filé cette oeuvre aujourd'hui.
                    Revenez dans quelques instants, le savoir antique se mérite.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    titre: str = data.get("titre") or data.get("concept") or "Inconnu"
    auteur: str = (
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
    analyse: str = data.get("analyse") or ""
    image_url: str | None = data.get("image")
    wiki: str | None = data.get("lien_wiki")
    content_text: str | None = data.get("poeme_entier") or data.get("extrait")
    safe_key: str = f"{label}_{date_str}_{context_id}"

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
        elif label in NO_AI_FALLBACK_CATEGORIES:
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
                btn_label: str = "🎧 Ecouter (YouTube Music)"
                query: str = urllib.parse.quote(f"{auteur} {titre}")
                wiki = f"https://music.youtube.com/search?q={query}"
            else:
                btn_label = "📖 Approfondir"
            st.link_button(btn_label, wiki, use_container_width=True)


# ============================================================
# EXPOSITION COMPLÈTE
# ============================================================
def display_exposition(target_date: datetime.date, context_id: str) -> None:
    """Affiche l'exposition complète pour une date donnée.

    Utilise st.status() pour montrer la progression en temps réel
    pendant la génération des 14 catégories.

    Args:
        target_date: Date de l'édition.
        context_id: Identifiant de contexte (ex: "today", "archive").
    """
    date_str: str = target_date.strftime("%Y-%m-%d")

    st.markdown(
        f"<p style='text-align: center; color: #555; font-size: 1.4rem; "
        f"font-style: italic;'>Edition du "
        f"{target_date.strftime('%d %B %Y')}</p>",
        unsafe_allow_html=True,
    )

    # Cache : l'edition existe-t-elle deja en base ?
    edition_cache: dict[str, Any] | None = db.get_edition(date_str)

    if edition_cache:
        quote: dict[str, Any] = edition_cache.get("quote", {})
        art: dict[str, Any] = edition_cache.get("art", {})
        blocks_data: dict[str, Any] = edition_cache.get("blocks", {})
    else:
        # Progression dynamique avec st.status()
        with st.status(
            "🏛️ Les Muses préparent le banquet...",
            expanded=True,
        ) as status:
            st.write("📜 **Citation du jour** — en cours...")
            quote = fetch_quote_data(date_str)
            st.write("✅ Citation du jour — prête")

            st.write("🖼️ **Beaux-Arts (MET Museum)** — en cours...")
            art = get_art_safe(date_str)
            st.write("✅ Beaux-Arts — prêt")

            blocks_data = {}
            total: int = len(CATEGORIES)
            for idx, (name, _color, _icon) in enumerate(CATEGORIES, start=1):
                st.write(f"⏳ **{name}** ({idx}/{total}) — en cours...")
                blocks_data[name] = get_content_item(name, date_str)
                st.write(f"✅ **{name}** ({idx}/{total}) — prête")

            status.update(
                label="🎉 Le banquet est servi ! Les Muses ont parlé.",
                state="complete",
                expanded=False,
            )

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

    # 14 catégories
    for name, color, icon in CATEGORIES:
        data = blocks_data.get(name, {})
        render_block_safe(icon, name, data, date_str, context_id, color)


# ============================================================
# BOUTON PARTAGE
# ============================================================
def _render_share_button(target_date: datetime.date) -> None:
    """Affiche un bouton de partage pour l'édition du jour.

    Utilise la Web Share API (navigator.share) sur mobile,
    ou copie le lien dans le presse-papier sur desktop.

    Args:
        target_date: Date de l'édition à partager.
    """
    date_str: str = target_date.strftime("%Y-%m-%d")
    share_text: str = (
        f"🏛️ Le Banquet des Muses — Édition du {date_str}\n\n"
        f"Découvre l'exposition culturelle du jour : "
        f"poésie, littérature, musique, philosophie et bien plus !\n\n"
        f"📜 « {st.session_state.get('current_quote', 'La culture est le seul bien qui s\'accroît quand on le partage.')} »"
    )

    # JavaScript pour Web Share API avec fallback clipboard
    share_js: str = f"""
    <div style="text-align: center; margin: 30px 0 10px 0;">
        <button onclick="shareEdition()" style="
            background: none; border: 1px solid #800020; border-radius: 4px;
            padding: 12px 30px; font-family: 'Cinzel', serif;
            font-size: 1rem; color: #800020; cursor: pointer;
            transition: all 0.3s ease;
        " onmouseover="this.style.background='#800020'; this.style.color='#fdfbf7';"
         onmouseout="this.style.background='none'; this.style.color='#800020';">
            📤 Partager cette édition
        </button>
    </div>
    <script>
    function shareEdition() {{
        const text = `{share_text}`;
        if (navigator.share) {{
            navigator.share({{
                title: 'Le Banquet des Muses',
                text: text,
                url: window.location.href,
            }}).catch(() => {{}});
        }} else {{
            navigator.clipboard.writeText(text + '\\n' + window.location.href)
                .then(() => {{
                    const btn = event.target;
                    const orig = btn.textContent;
                    btn.textContent = '✅ Lien copié !';
                    setTimeout(() => {{ btn.textContent = orig; }}, 2000);
                }})
                .catch(() => {{}});
        }}
    }}
    </script>
    """
    st.markdown(share_js, unsafe_allow_html=True)


# ============================================================
# APPLICATION PRINCIPALE
# ============================================================
st.title("Le Banquet des Muses")

t1, t2, t3 = st.tabs(["✨ Aujourd'hui", "📅 Archives", "⭐ Favoris"])

# Onglet 1 : Aujourd'hui
with t1:
    today: datetime.date = datetime.date.today()
    display_exposition(today, context_id="today")
    _render_share_button(today)

# Onglet 2 : Archives
with t2:
    yesterday: datetime.date = datetime.date.today() - datetime.timedelta(days=1)
    d: datetime.date = st.date_input(
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

    prefs: list[dict[str, Any]] = db.get_preferences()
    liked: list[dict[str, Any]] = [p for p in prefs if p.get("liked")]

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

