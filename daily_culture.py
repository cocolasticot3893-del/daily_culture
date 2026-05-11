import streamlit as st
import requests
import random
import hashlib
import json
import datetime
import urllib.parse
import time
import re
from pathlib import Path

# --- CONFIGURATION STREAMLIT ---
st.set_page_config(page_title="L'Éveil Culturel", page_icon="🏛️", layout="centered")

# CSS Premium, Adaptatif et Typographie
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&family=Source+Sans+Pro:wght@300;400;600&display=swap');
    
    h1, h2, h3 { font-family: 'Playfair Display', serif; color: #1a252f; text-align: center; }
    h1 { font-size: 3rem; border-bottom: 3px solid #d4af37; padding-bottom: 25px; margin-bottom: 40px; }
    
    p, div, span { font-family: 'Source Sans Pro', sans-serif; font-size: 1.15rem; line-height: 1.8; }
    
    .poem-box { 
        font-family: 'Playfair Display', serif; font-size: 1.3rem; line-height: 2; 
        padding-left: 25px; border-left: 4px solid #d4af37; white-space: pre-wrap; 
        color: #1a252f; margin: 25px 0; background-color: #fcfcf9; padding: 25px; border-radius: 0 12px 12px 0;
        box-shadow: inset 0 0 10px rgba(0,0,0,0.02);
    }
    
    .quote-box { 
        text-align: center; font-family: 'Playfair Display', serif; font-size: 1.6rem; 
        font-style: italic; color: #b8860b; padding: 40px; margin-bottom: 50px; 
        background: #fdfbf7; border-radius: 15px; border: 1px solid #f0ece1; 
        box-shadow: 0 10px 25px rgba(0,0,0,0.03);
    }
    
    [data-testid="stImage"] img { 
        border-radius: 12px; 
        box-shadow: 0 12px 30px rgba(0,0,0,0.12); 
        margin-bottom: 25px; 
    }
    
    .stButton button { width: 100%; border-radius: 8px; height: 50px; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

# --- SECURITÉ & CLÉS API ---
DEEPSEEK_KEY = st.secrets.get("DEEPSEEK_API_KEY")
if not DEEPSEEK_KEY:
    st.error("❌ CLÉ API MANQUANTE : Ajoutez 'DEEPSEEK_API_KEY' dans les Secrets.")
    st.stop()

# --- GESTION DES FAVORIS ---
PREFS_FILE = Path("mes_favoris.json")

def load_prefs():
    if PREFS_FILE.exists():
        try:
            with open(PREFS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

def save_pref(category, title, author, is_liked, date_str):
    prefs = load_prefs()
    for p in prefs:
        if p.get("category") == category and p.get("title") == title:
            p["liked"] = is_liked
            with open(PREFS_FILE, "w", encoding="utf-8") as f: json.dump(prefs, f, ensure_ascii=False, indent=4)
            st.toast("Préférence mise à jour ! ✨")
            return
    prefs.append({"date": date_str, "category": category, "title": title, "author": author, "liked": is_liked})
    with open(PREFS_FILE, "w", encoding="utf-8") as f: json.dump(prefs, f, ensure_ascii=False, indent=4)
    if is_liked: st.toast("Ajouté aux favoris ! ⭐")

# --- FONCTIONS HELPERS ---
def extract_json(text):
    try:
        match = re.search(r'\{.*\}', text.strip(), re.DOTALL)
        if match: return json.loads(match.group(0))
        return json.loads(text)
    except Exception as e:
        raise ValueError(f"Impossible de parser le JSON: {str(e)}")

def get_wiki_image(query, lang="fr"):
    """Cherche l'image principale sur Wikipédia avec une identité applicative."""
    if not query: return None
    headers = {"User-Agent": "L_Eveil_Culturel_App/2.0 (contact@example.com)"}
    try:
        # Recherche du titre exact
        search_url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&utf8=&format=json&srlimit=1"
        res = requests.get(search_url, headers=headers, timeout=10).json()
        if not res.get('query', {}).get('search'): return None
        page_title = res['query']['search'][0]['title']
        
        # API REST pour l'image
        summary_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(page_title.replace(' ', '_'))}"
        res2 = requests.get(summary_url, headers=headers, timeout=10).json()
        
        if 'originalimage' in res2:
            return res2['originalimage']['source']
        elif 'thumbnail' in res2:
            return res2['thumbnail']['source']
    except: pass
    return None

def fetch_image_cascade(res_dict, category):
    """Système de recherche d'images en cascade (FR -> EN -> Auteur)."""
    # Pour le cinéma et la musique, on tente l'anglais immédiatement car les droits d'images y sont plus souples
    primary_lang = "en" if category in ["Cinéma", "Musique", "Architecture"] else "fr"
    
    queries = [
        res_dict.get("image_query"),
        res_dict.get("titre"),
        res_dict.get("artiste"),
        res_dict.get("auteur"),
        res_dict.get("realisateur"),
        res_dict.get("concept")
    ]
    queries = [q for q in queries if q and len(str(q)) > 2]

    for q in queries:
        # Test Langue primaire
        img = get_wiki_image(q, primary_lang)
        if img: return img
        # Test Langue secondaire
        img = get_wiki_image(q, "fr" if primary_lang == "en" else "en")
        if img: return img
    return None

@st.cache_data(show_spinner=False, ttl=86400*30)
def ask_deepseek(prompt, seed, retries=2):
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "Tu es un expert culturel mondial. Tu fournis des analyses de 10 phrases riches. RÈGLE CRITIQUE : Ignore les numéros de tirage/ID fournis, ne les mentionne jamais. Réponds UNIQUEMENT en JSON pur."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }
    for i in range(retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return extract_json(content)
        except Exception as e:
            time.sleep(2)
            if i == retries - 1: return {"erreur": True, "details": str(e)}

# --- FONCTIONS DE CONTENU ---
@st.cache_data(show_spinner=False, ttl=86400*30)
def get_content_item(category_name, seed_offset):
    prompts = {
        "Poésie": "{'titre': '...', 'auteur': '...', 'poeme_entier': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Auteur'}",
        "Musique": "{'titre': '...', 'artiste': '...', 'annee': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Artiste Chanson'}",
        "Cinéma": "{'titre': '...', 'realisateur': '...', 'annee': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Titre Film Original'}",
        "Philosophie": "{'concept': '...', 'philosophe': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Philosophe'}",
        "Architecture": "{'titre': '...', 'lieu': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Monument'}",
        "Mythologie": "{'titre': '...', 'origine': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Sujet Mythe'}",
        "Science": "{'titre': '...', 'inventeur': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Invention'}",
        "Gastronomie": "{'titre': '...', 'origine': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Plat nom exact'}"
    }
    seed = st.session_state.daily_seed + seed_offset
    prompt = f"Génération #{seed}. Catégorie: {category_name}. Règle : Ne cite pas ce numéro. Format JSON : {prompts[category_name]}"
    
    res = ask_deepseek(prompt, seed)
    if not res.get("erreur"):
        res["image"] = fetch_image_cascade(res, category_name)
    return res

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_art_safe(seed):
    random.seed(seed)
    ids = [436535, 436528, 436532, 435882, 435809, 436533, 436529, 437112, 436121, 459123, 436101, 436534]
    try:
        r = requests.get(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{random.choice(ids)}", timeout=15)
        art = r.json()
        prompt = f"Analyse approfondie de '{art.get('title')}' par {art.get('artistDisplayName')}. JSON: {{'titre_fr': '...', 'analyse': '...', 'lien_wiki': '...'}}"
        ds = ask_deepseek(prompt, seed)
        return {
            "titre": ds.get('titre_fr', art.get('title', 'Sans Titre')),
            "auteur": art.get('artistDisplayName', 'Anonyme'),
            "image": art.get('primaryImageSmall'),
            "analyse": ds.get('analyse', 'Analyse en cours...'),
            "lien_wiki": ds.get('lien_wiki') or art.get('objectURL')
        }
    except: return {"erreur": True}

# --- RENDU DE L'EXPOSITION ---
def display_exposition(target_date):
    date_str = target_date.strftime("%Y-%m-%d")
    st.session_state.daily_seed = int(hashlib.md5(date_str.encode()).hexdigest(), 16) % (10**8)
    
    st.markdown(f"<p style='text-align: center; color: #7f8c8d; font-size: 1.3rem; font-style: italic;'>Édition du {target_date.strftime('%d %B %Y')}</p>", unsafe_allow_html=True)

    with st.spinner("Votre curateur parcourt les bibliothèques du monde..."):
        quote_data = ask_deepseek(f"Citation courte inspirante #{st.session_state.daily_seed}. JSON: {{'citation':'', 'auteur':''}}", st.session_state.daily_seed)
        art_data = get_art_safe(st.session_state.daily_seed)
        # Séquence de chargement
        arch = get_content_item("Architecture", 1)
        poem = get_content_item("Poésie", 2)
        myth = get_content_item("Mythologie", 3)
        philo = get_content_item("Philosophie", 4)
        sci = get_content_item("Science", 5)
        song = get_content_item("Musique", 6)
        gastro = get_content_item("Gastronomie", 7)
        movie = get_content_item("Cinéma", 8)

    # 1. CITATION
    if not quote_data.get("erreur"):
        st.markdown(f"<div class='quote-box'>« {quote_data.get('citation', '')} »<br><span style='font-size:1.2rem; color:#7f8c8d;'>— {quote_data.get('auteur', '')}</span></div>", unsafe_allow_html=True)

    def render_block_safe(icon, label, data, color="#d4af37"):
        if data.get("erreur"): return
        
        # Gestion sécurisée des clés (pour éviter KeyError)
        titre = data.get("titre") or data.get("concept") or "Inconnu"
        auteur = data.get("auteur") or data.get("artiste") or data.get("realisateur") or data.get("philosophe") or data.get("inventeur") or data.get("origine") or data.get("lieu") or ""
        analyse = data.get("analyse") or "Analyse indisponible."
        image = data.get("image")
        wiki = data.get("lien_wiki")
        poem_text = data.get("poeme_entier")

        with st.container(border=True):
            st.markdown(f"""
                <div style="text-align: center; margin-bottom: 25px;">
                    <span style="color: {color}; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; font-size: 0.9rem;">{icon} {label}</span>
                    <h2 style="margin: 10px 0 5px 0; font-size: 2.2rem;">{titre}</h2>
                    <h4 style="font-style: italic; color: #7f8c8d; font-weight: normal; margin-top: 0;">{auteur}</h4>
                    <hr style="width: 50px; margin: 15px auto; border: 1px solid {color};">
                </div>
            """, unsafe_allow_html=True)
            
            if image: st.image(image, use_container_width=True)
            if poem_text: st.markdown(f'<div class="poem-box">{poem_text}</div>', unsafe_allow_html=True)
            st.write(analyse)
            
            st.write("")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("👍 J'aime", key=f"l_{label}_{titre}", use_container_width=True): save_pref(label, titre, auteur, True, date_str)
            with c2:
                if st.button("👎 Bof", key=f"d_{label}_{titre}", use_container_width=True): save_pref(label, titre, auteur, False, date_str)
            
            if wiki:
                btn_label = "🎧 Écouter" if label == "Musique" else "📖 Approfondir"
                st.link_button(btn_label, wiki, use_container_width=True)

    # AFFICHAGE DES BLOCS
    if not art_data.get("erreur"): render_block_safe("🖼️", "Beaux-Arts", art_data, color="#b8860b")
    render_block_safe("🏛️", "Architecture", arch, color="#2c3e50")
    render_block_safe("📜", "Poésie", poem, color="#8e44ad")
    render_block_safe("⚡", "Mythologie", myth, color="#e67e22")
    render_block_safe("🧠", "Philosophie", philo, color="#16a085")
    render_block_safe("🌍", "Science", sci, color="#2980b9")
    render_block_safe("🎵", "Musique", song, color="#c0392b")
    render_block_safe("🍷", "Gastronomie", gastro, color="#27ae60")
    render_block_safe("🎬", "Cinéma", movie, color="#34495e")

# --- INTERFACE ---
st.title("L'Éveil Culturel")
tab_today, tab_archive, tab_fav = st.tabs(["✨ Aujourd'hui", "📅 Archives", "⭐ Favoris"])

with tab_today: display_exposition(datetime.date.today())
with tab_archive:
    sel_date = st.date_input("Choisir une date :", value=datetime.date.today() - datetime.timedelta(days=1), max_value=datetime.date.today())
    if sel_date != datetime.date.today():
        st.write("---")
        display_exposition(sel_date)
with tab_fav:
    st.header("⭐ Votre collection")
    prefs = load_prefs()
    liked = [p for p in prefs if p.get("liked")]
    if not liked: st.info("Aucun favori pour l'instant.")
    else:
        liked.sort(key=lambda x: x.get("date", ""), reverse=True)
        for item in liked:
            st.markdown(f"**{item.get('category')}** : {item.get('title')} *({item.get('author')})* — {item.get('date')}")
