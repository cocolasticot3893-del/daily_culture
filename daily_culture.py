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

# CSS Premium et Adaptatif
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&family=Source+Sans+Pro:wght@300;400;600&display=swap');
    
    h1, h2, h3 { font-family: 'Playfair Display', serif; color: #1a252f; text-align: center; }
    h1 { font-size: 3rem; border-bottom: 3px solid #d4af37; padding-bottom: 25px; margin-bottom: 40px; }
    
    p, div, span { font-family: 'Source Sans Pro', sans-serif; font-size: 1.15rem; line-height: 1.8; }
    
    .category-header {
        text-align: center;
        margin-bottom: 30px;
        padding: 20px 0;
        border-radius: 10px;
    }
    
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
    
    /* Harmonisation des images */
    [data-testid="stImage"] img { 
        border-radius: 12px; 
        box-shadow: 0 12px 30px rgba(0,0,0,0.12); 
        margin-bottom: 25px; 
        border: 1px solid #eee;
    }
    
    /* Boutons et Liens */
    .stButton button { width: 100%; border-radius: 8px; height: 50px; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

# --- SECURITÉ & CLÉS API ---
DEEPSEEK_KEY = st.secrets.get("DEEPSEEK_API_KEY")
if not DEEPSEEK_KEY:
    st.error("❌ CLÉ API MANQUANTE : Ajoutez 'DEEPSEEK_API_KEY' dans les Secrets de Streamlit.")
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
        if p["category"] == category and p["title"] == title:
            p["liked"] = is_liked
            with open(PREFS_FILE, "w", encoding="utf-8") as f: json.dump(prefs, f, ensure_ascii=False, indent=4)
            msg = "Ajouté aux favoris ! ⭐" if is_liked else "Retiré des favoris 🗑️"
            st.toast(msg)
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
    """Cherche l'image principale sur Wikipédia avec une logique de repli robuste."""
    if not query: return None
    headers = {"User-Agent": "L_Eveil_Culturel_App/1.1 (contact@example.com)"}
    try:
        # 1. Recherche du titre exact
        search_url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&utf8=&format=json&srlimit=1"
        res = requests.get(search_url, headers=headers, timeout=8).json()
        if not res.get('query', {}).get('search'): return None
        page_title = res['query']['search'][0]['title']
        
        # 2. Appel à l'API REST moderne
        summary_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(page_title.replace(' ', '_'))}"
        res2 = requests.get(summary_url, headers=headers, timeout=8).json()
        
        if 'originalimage' in res2:
            return res2['originalimage']['source']
        elif 'thumbnail' in res2:
            thumb = res2['thumbnail']['source']
            return re.sub(r'\d+px-', '1000px-', thumb) # Meilleure résolution
    except: pass
    return None

@st.cache_data(show_spinner=False, ttl=86400*30)
def ask_deepseek(prompt, seed, retries=2):
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "Tu es un expert culturel français. Tu fournis des analyses très approfondies (10 phrases) et des métadonnées précises. Réponds en JSON pur."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }
    for i in range(retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=45)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return extract_json(content)
        except Exception as e:
            time.sleep(2)
            if i == retries - 1: return {"erreur": True, "details": str(e)}

# --- FONCTIONS DE CONTENU (Version 8.2 avec image_query) ---
@st.cache_data(show_spinner=False, ttl=86400*30)
def get_quote(seed): return ask_deepseek(f"Graine {seed}. Citation inspirante courte. JSON: {{'citation': '...', 'auteur': '...'}}", seed)

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_art(seed):
    random.seed(seed)
    ids = [436535, 436528, 436532, 435882, 435809, 436533, 436529, 437112, 436121, 459123, 436101, 436534]
    try:
        r = requests.get(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{random.choice(ids)}", timeout=12)
        art = r.json()
        prompt = f"Analyse approfondie de '{art.get('title')}' par {art.get('artistDisplayName')}. JSON: {{'titre_fr': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Meilleur terme recherche image Wikipédia'}}"
        ds = ask_deepseek(prompt, seed)
        return {"titre": ds.get('titre_fr', art.get('title')), "auteur": art.get('artistDisplayName', 'Inconnu'), "image": art.get('primaryImageSmall'), "analyse": ds.get('analyse', 'Erreur.'), "lien_wiki": ds.get('lien_wiki') or art.get('objectURL')}
    except: return {"erreur": True}

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_content_item(category_name, seed_offset):
    prompts = {
        "Poésie": "Poème français célèbre. JSON: {'titre': '...', 'auteur': '...', 'poeme_entier': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Nom auteur ou oeuvre pour image'}",
        "Musique": "Chanson culte. JSON: {'titre': '...', 'artiste': '...', 'annee': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Artiste ou album cover'}",
        "Cinéma": "Chef-d'œuvre cinéma. JSON: {'titre': '...', 'realisateur': '...', 'annee': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Nom film original movie'}",
        "Philosophie": "Concept philosophique. JSON: {'concept': '...', 'philosophe': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Portrait du philosophe'}",
        "Architecture": "Monument mondial. JSON: {'titre': '...', 'lieu': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Nom exact monument'}",
        "Mythologie": "Mythe ou divinité. JSON: {'titre': '...', 'origine': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Nom divinité'}",
        "Science": "Invention majeure. JSON: {'titre': '...', 'inventeur': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Nom invention ou inventeur'}",
        "Gastronomie": "Plat emblématique. JSON: {'titre': '...', 'origine': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Nom plat gastronomique'}"
    }
    seed = st.session_state.daily_seed + seed_offset
    res = ask_deepseek(f"Graine {seed}. {prompts[category_name]}", seed)
    if not res.get("erreur"):
        lang = "en" if category_name in ["Musique", "Cinéma"] else "fr"
        res["image"] = get_wiki_image(res.get("image_query") or res.get("titre") or res.get("concept"), lang=lang)
    return res

# --- RENDU DE L'EXPOSITION ---
def display_exposition(target_date):
    date_str = target_date.strftime("%Y-%m-%d")
    st.session_state.daily_seed = int(hashlib.md5(date_str.encode()).hexdigest(), 16) % (10**8)
    
    st.markdown(f"<p style='text-align: center; color: #7f8c8d; font-size: 1.3rem; font-style: italic;'>Le curateur présente l'édition du {target_date.strftime('%d %B %Y')}</p>", unsafe_allow_html=True)

    with st.spinner("Recherche des raretés culturelles..."):
        quote_data = get_quote(st.session_state.daily_seed)
        art_data = get_art(st.session_state.daily_seed)
        arch_data = get_content_item("Architecture", 10)
        poem_data = get_content_item("Poésie", 20)
        myth_data = get_content_item("Mythologie", 30)
        philo_data = get_content_item("Philosophie", 40)
        sci_data = get_content_item("Science", 50)
        song_data = get_content_item("Musique", 60)
        gastro_data = get_content_item("Gastronomie", 70)
        movie_data = get_content_item("Cinéma", 80)

    # 1. CITATION
    if not quote_data.get("erreur"):
        st.markdown(f"<div class='quote-box'>« {quote_data.get('citation', '')} »<br><span style='font-size:1.2rem; color:#7f8c8d;'>— {quote_data.get('auteur', '')}</span></div>", unsafe_allow_html=True)

    # HELPER D'AFFICHAGE
    def render_block(icon, cat_label, title, sub, analysis, img_url, wiki_url, content=None, color="#d4af37"):
        with st.container(border=True):
            st.markdown(f"""
                <div style="text-align: center; margin-bottom: 25px;">
                    <span style="color: {color}; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; font-size: 0.9rem;">{icon} {cat_label}</span>
                    <h2 style="margin: 10px 0 5px 0; font-size: 2.2rem;">{title}</h2>
                    <h4 style="font-style: italic; color: #7f8c8d; font-weight: normal; margin-top: 0;">{sub}</h4>
                    <hr style="width: 50px; margin: 15px auto; border: 1px solid {color};">
                </div>
            """, unsafe_allow_html=True)
            
            if img_url: st.image(img_url, use_container_width=True)
            if content: st.markdown(f'<div class="poem-box">{content}</div>', unsafe_allow_html=True)
            st.write(analysis)
            
            st.write("")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("👍 J'aime", key=f"l_{cat_label}_{date_str}", use_container_width=True): save_pref(cat_label, title, sub, True, date_str)
            with c2:
                if st.button("👎 Bof", key=f"d_{cat_label}_{date_str}", use_container_width=True): save_pref(cat_label, title, sub, False, date_str)
            
            if wiki_url: 
                label = "🎧 Écouter" if cat_label == "Musique" else "📖 Approfondir"
                st.link_button(label, wiki_url, use_container_width=True)

    # AFFICHAGE DES SECTIONS
    if not art_data.get("erreur"): render_block("🖼️", "Beaux-Arts", art_data["titre"], art_data["auteur"], art_data["analyse"], art_data["image"], art_data["lien_wiki"], color="#b8860b")
    if not arch_data.get("erreur"): render_block("🏛️", "Architecture", arch_data["titre"], arch_data["lieu"], arch_data["analyse"], arch_data["image"], arch_data["lien_wiki"], color="#2c3e50")
    if not poem_data.get("erreur"): render_block("📜", "Poésie", poem_data["titre"], poem_data["auteur"], poem_data["analyse"], poem_data["image"], poem_data["lien_wiki"], content=poem_data["poeme_entier"], color="#8e44ad")
    if not myth_data.get("erreur"): render_block("⚡", "Mythologie", myth_data["titre"], myth_data["origine"], myth_data["analyse"], myth_data["image"], myth_data["lien_wiki"], color="#e67e22")
    if not philo_data.get("erreur"): render_block("🧠", "Philosophie", philo_data["concept"], philo_data["philosophe"], philo_data["analyse"], philo_data["image"], philo_data["lien_wiki"], color="#16a085")
    if not sci_data.get("erreur"): render_block("🌍", "Science", sci_data["titre"], sci_data["inventeur"], sci_data["analyse"], sci_data["image"], sci_data["lien_wiki"], color="#2980b9")
    if not song_data.get("erreur"): render_block("🎵", "Musique", song_data["titre"], f"{song_data['artiste']} ({song_data['annee']})", song_data["analyse"], song_data["image"], song_data["lien_wiki"], color="#c0392b")
    if not gastro_data.get("erreur"): render_block("🍷", "Gastronomie", gastro_data["titre"], gastro_data["origine"], gastro_data["analyse"], gastro_data["image"], gastro_data["lien_wiki"], color="#27ae60")
    if not movie_data.get("erreur"): render_block("🎬", "Cinéma", movie_data["titre"], f"{movie_data['realisateur']} ({movie_data['annee']})", movie_data["analyse"], movie_data["image"], movie_data["lien_wiki"], color="#34495e")

# --- INTERFACE ---
st.title("L'Éveil Culturel")
tab_today, tab_archive, tab_fav = st.tabs(["✨ Aujourd'hui", "📅 Archives", "⭐ Favoris"])

with tab_today: display_exposition(datetime.date.today())
with tab_archive:
    selected_date = st.date_input("Choisir une date :", value=datetime.date.today() - datetime.timedelta(days=1), max_value=datetime.date.today())
    if selected_date != datetime.date.today():
        st.write("---")
        display_exposition(selected_date)
with tab_fav:
    st.header("⭐ Votre collection")
    prefs = load_prefs()
    liked_items = [p for p in prefs if p.get("liked") == True]
    if not liked_items: st.info("Aucun favori pour l'instant.")
    else:
        liked_items.sort(key=lambda x: x["date"], reverse=True)
        for item in liked_items: st.markdown(f"**{item['category']}** : {item['title']} *(par {item['author']})* - `Sauvegardé le {item['date']}`")
