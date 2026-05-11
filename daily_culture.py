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

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=Source+Sans+Pro:wght@300;400;600&display=swap');
    
    .stApp { background-color: #fcfbf9; color: #2c3e50; }
    h1, h2, h3 { font-family: 'Playfair Display', serif; color: #1a252f; text-align: center; }
    h1 { font-size: 2.5rem; border-bottom: 2px solid #d4af37; padding-bottom: 20px; margin-bottom: 30px; }
    
    .culture-card { 
        background: #ffffff; padding: 30px; border-radius: 12px; 
        border-top: 4px solid #d4af37; box-shadow: 0 8px 24px rgba(0,0,0,0.06); 
        margin-bottom: 25px; transition: transform 0.2s;
    }
    .culture-card:hover { transform: translateY(-3px); }
    
    .card-title { font-family: 'Playfair Display', serif; font-size: 1.8rem; color: #1a252f; margin-bottom: 5px; }
    .card-subtitle { font-family: 'Source Sans Pro', sans-serif; font-style: italic; color: #7f8c8d; font-size: 1.1rem; border-bottom: 1px solid #f0f0f0; padding-bottom: 15px; margin-bottom: 20px; }
    
    .content-box { font-family: 'Source Sans Pro', sans-serif; font-size: 1.15rem; line-height: 1.7; margin-bottom: 20px; }
    .poem-box { font-family: 'Playfair Display', serif; font-size: 1.2rem; line-height: 1.8; padding-left: 20px; border-left: 3px solid #d4af37; white-space: pre-wrap; color: #2c3e50; margin-bottom: 20px; }
    .analysis-box { background-color: #f9f9f9; border-left: 4px solid #bdc3c7; padding: 18px; font-family: 'Source Sans Pro', sans-serif; font-size: 1.05rem; color: #455a64; border-radius: 0 6px 6px 0; }
    
    .quote-box { text-align: center; font-family: 'Playfair Display', serif; font-size: 1.4rem; font-style: italic; color: #b8860b; padding: 20px; margin-bottom: 40px; background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.03); }
    
    .deep-link { display: inline-flex; align-items: center; color: #d4af37; text-decoration: none; font-weight: 600; font-size: 1rem; margin-top: 10px; }
    .deep-link:hover { color: #b8860b; text-decoration: underline; }
    
    img { border-radius: 6px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); width: 100%; object-fit: contain; max-height: 500px; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- SECURITÉ & CLÉS API ---
DEEPSEEK_KEY = st.secrets.get("DEEPSEEK_API_KEY")

if not DEEPSEEK_KEY:
    st.error("❌ CLÉ API MANQUANTE : Ajoutez 'DEEPSEEK_API_KEY' dans les Secrets de Streamlit.")
    st.stop()

# --- GESTION DES FAVORIS (Base de données locale JSON) ---
PREFS_FILE = Path("mes_favoris.json")

def load_prefs():
    if PREFS_FILE.exists():
        try:
            with open(PREFS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

def save_pref(category, title, author, is_liked):
    prefs = load_prefs()
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    # Mettre à jour si existe déjà, sinon ajouter
    for p in prefs:
        if p["category"] == category and p["title"] == title:
            p["liked"] = is_liked
            with open(PREFS_FILE, "w", encoding="utf-8") as f: json.dump(prefs, f, ensure_ascii=False, indent=4)
            msg = "Ajouté aux favoris ! ⭐" if is_liked else "Retiré des favoris 🗑️"
            st.toast(msg)
            return

    prefs.append({"date": today, "category": category, "title": title, "author": author, "liked": is_liked})
    with open(PREFS_FILE, "w", encoding="utf-8") as f: json.dump(prefs, f, ensure_ascii=False, indent=4)
    if is_liked: st.toast("Ajouté aux favoris ! ⭐")

# --- FONCTION BLINDÉE POUR L'API DEEPSEEK ---
def extract_json(text):
    """Cherche et extrait un bloc JSON valide même s'il est noyé dans du texte."""
    try:
        match = re.search(r'\{.*\}', text.strip(), re.DOTALL)
        if match: return json.loads(match.group(0))
        return json.loads(text) # Fallback classique
    except Exception as e:
        raise ValueError(f"Impossible de parser le JSON: {str(e)}")

@st.cache_data(show_spinner=False, ttl=86400)
def ask_deepseek(prompt, seed, retries=2):
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "Tu es un érudit français. Réponds UNIQUEMENT par un objet JSON pur et valide. Pas de markdown, pas d'introduction."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }
    
    for i in range(retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=25)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return extract_json(content)
        except Exception as e:
            time.sleep(2) # Backoff avant de réessayer
            if i == retries - 1:
                return {"erreur": True, "details": str(e)}

# --- FONCTIONS DE CONTENU (Cachées individuellement pour isoler les pannes) ---
@st.cache_data(show_spinner=False, ttl=86400)
def get_quote(seed):
    prompt = f"Graine {seed}. Donne une citation inspirante et très courte sur la vie, l'art ou la connaissance. JSON attendu: {{'citation': '...', 'auteur': '...'}}"
    return ask_deepseek(prompt, seed)

@st.cache_data(show_spinner=False, ttl=86400)
def get_art(seed):
    random.seed(seed)
    # Liste d'œuvres du MET avec de belles images publiques garanties
    ids = [436535, 436528, 436532, 435882, 435809, 436533, 436529, 437112, 436121, 459123, 436101, 436534]
    obj_id = random.choice(ids)
    try:
        r = requests.get(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{obj_id}", timeout=10)
        r.raise_for_status()
        art = r.json()
        
        prompt = f"Fais une analyse passionnante (4 à 5 phrases) du tableau '{art.get('title')}' de {art.get('artistDisplayName')}. Traduis le titre en français. JSON attendu: {{'titre_fr': '...', 'analyse': '...'}}"
        ds = ask_deepseek(prompt, seed)
        
        return {
            "title": ds.get('titre_fr', art.get('title', 'Inconnu')),
            "author": art.get('artistDisplayName', 'Artiste inconnu'),
            "image": art.get('primaryImageSmall'),
            "analyse": ds.get('analyse', 'Analyse non disponible.'),
            "link": art.get('objectURL', '')
        }
    except Exception as e:
        return {"erreur": True, "details": str(e)}

@st.cache_data(show_spinner=False, ttl=86400)
def get_poem(seed):
    prompt = f"Graine {seed}. Choisis un magnifique poème français. JSON attendu: {{'titre': '...', 'auteur': '...', 'poeme_entier': 'Texte avec \\n', 'analyse': '4 phrases'}}"
    return ask_deepseek(prompt, seed)

@st.cache_data(show_spinner=False, ttl=86400)
def get_song(seed):
    prompt = f"Graine {seed}. Choisis une chanson internationale culte. JSON attendu: {{'titre': '...', 'artiste': '...', 'annee': '...', 'analyse': '4 phrases'}}"
    return ask_deepseek(prompt, seed)

@st.cache_data(show_spinner=False, ttl=86400)
def get_movie(seed):
    prompt = f"Graine {seed}. Choisis un chef-d'œuvre du cinéma. JSON attendu: {{'titre': '...', 'realisateur': '...', 'annee': '...', 'analyse': '4 phrases'}}"
    return ask_deepseek(prompt, seed)

@st.cache_data(show_spinner=False, ttl=86400)
def get_philo(seed):
    prompt = f"Graine {seed}. Explique un concept philosophique utile au quotidien. JSON attendu: {{'concept': '...', 'philosophe': '...', 'analyse': '4 phrases'}}"
    return ask_deepseek(prompt, seed)

# --- HELPERS D'AFFICHAGE & LIENS ---
def make_wiki_url(query):
    return f"https://fr.wikipedia.org/wiki/Spécial:Recherche?search={urllib.parse.quote(query)}"

def make_yt_url(query):
    return f"https://music.youtube.com/search?q={urllib.parse.quote(query)}"

def render_card(icon, category, title, subtitle, content, analysis, link_url, link_text):
    """Fonction générique pour dessiner une belle carte culturelle avec boutons d'action."""
    st.markdown(f"""
        <div class="culture-card">
            <div class="card-title">{icon} {title}</div>
            <div class="card-subtitle">{subtitle}</div>
    """, unsafe_allow_html=True)
    
    if content: # Principalement pour le poème
        st.markdown(f'<div class="poem-box">{content}</div>', unsafe_allow_html=True)
        
    st.markdown(f'<div class="analysis-box">{analysis}</div>', unsafe_allow_html=True)
    
    # Zone des boutons (Interactive Streamlit)
    st.write("") # Petit espace
    c1, c2, c3 = st.columns([1, 1, 4])
    with c1:
        if st.button("👍 J'aime", key=f"like_{title}"): save_pref(category, title, subtitle, True)
    with c2:
        if st.button("👎 Bof", key=f"dislike_{title}"): save_pref(category, title, subtitle, False)
    with c3:
        if link_url:
            st.markdown(f'<a href="{link_url}" target="_blank" class="deep-link">{link_text}</a>', unsafe_allow_html=True)
            
    st.markdown('</div>', unsafe_allow_html=True)

# --- APPLICATION PRINCIPALE ---
today_str = datetime.date.today().strftime("%Y-%m-%d")
# Graine unique par jour pour stabiliser les résultats aléatoires
seed = int(hashlib.md5(today_str.encode()).hexdigest(), 16) % (10**8)

st.title("L'Éveil Culturel")

# Navigation par Onglets
tab_today, tab_fav = st.tabs(["✨ L'Exposition du Jour", "⭐ Mes Favoris"])

with tab_today:
    st.markdown(f"<p style='text-align: center; color: #7f8c8d; margin-bottom: 30px;'>Édition du {datetime.date.today().strftime('%d/%m/%Y')}</p>", unsafe_allow_html=True)

    with st.spinner("Le curateur assemble votre exposition (Ceci est instantané si déjà en cache)..."):
        # Récupération parallèle (si l'un échoue, il n'empêche pas les autres de charger)
        quote_data = get_quote(seed)
        art_data = get_art(seed)
        poem_data = get_poem(seed)
        song_data = get_song(seed)
        movie_data = get_movie(seed)
        philo_data = get_philo(seed)

    # 0. CITATION
    if not quote_data.get("erreur"):
        st.markdown(f"<div class='quote-box'>« {quote_data.get('citation', '')} »<br><span style='font-size:1rem; color:#7f8c8d;'>— {quote_data.get('auteur', '')}</span></div>", unsafe_allow_html=True)

    # 1. ART
    if not art_data.get("erreur"):
        st.markdown(f'<div class="culture-card"><div class="card-title">🖼️ {art_data["title"]}</div><div class="card-subtitle">{art_data["author"]}</div>', unsafe_allow_html=True)
        if art_data.get("image"): st.image(art_data["image"])
        st.markdown(f'<div class="analysis-box">{art_data["analyse"]}</div>', unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns([1, 1, 4])
        with c1:
            if st.button("👍 J'aime", key="like_art"): save_pref("Art", art_data["title"], art_data["author"], True)
        with c2:
            if st.button("👎 Bof", key="dislike_art"): save_pref("Art", art_data["title"], art_data["author"], False)
        with c3:
            if art_data.get("link"): st.markdown(f'<a href="{art_data["link"]}" target="_blank" class="deep-link">🔍 Voir en HD sur le site du MET</a>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # 2. POÉSIE
    if not poem_data.get("erreur"):
        render_card("📜", "Poésie", poem_data.get("titre", "Inconnu"), poem_data.get("auteur", "Inconnu"), poem_data.get("poeme_entier", ""), poem_data.get("analyse", ""), make_wiki_url(poem_data.get("auteur", "")), "📖 Découvrir l'auteur (Wikipédia)")

    # 3. MUSIQUE
    if not song_data.get("erreur"):
        titre = song_data.get("titre", "Inconnu")
        artiste = song_data.get("artiste", "Inconnu")
        render_card("🎵", "Musique", titre, f"{artiste} ({song_data.get('annee', '')})", None, song_data.get("analyse", ""), make_yt_url(f"{artiste} {titre}"), "🎧 Écouter sur YouTube Music")

    # 4. CINÉMA
    if not movie_data.get("erreur"):
        titre = movie_data.get("titre", "Inconnu")
        realisateur = movie_data.get("realisateur", "Inconnu")
        render_card("🎬", "Cinéma", titre, f"{realisateur} ({movie_data.get('annee', '')})", None, movie_data.get("analyse", ""), make_wiki_url(f"{titre} film"), "🎞️ Fiche du film (Wikipédia)")

    # 5. PHILOSOPHIE
    if not philo_data.get("erreur"):
        concept = philo_data.get("concept", "Inconnu")
        render_card("🧠", "Philosophie", concept, philo_data.get("philosophe", "Inconnu"), None, philo_data.get("analyse", ""), make_wiki_url(concept), "📚 Approfondir ce concept")

with tab_fav:
    st.header("⭐ Votre collection personnelle")
    st.write("Retrouvez ici toutes les œuvres que vous avez aimées.")
    
    prefs = load_prefs()
    liked_items = [p for p in prefs if p.get("liked") == True]
    
    if not liked_items:
        st.info("Vous n'avez pas encore de favoris. Cliquez sur 👍 aujourd'hui pour commencer votre collection !")
    else:
        # Trier par date décroissante
        liked_items.sort(key=lambda x: x["date"], reverse=True)
        for item in liked_items:
            st.markdown(f"**{item['category']}** : {item['title']} *(par {item['author']})* - `Sauvegardé le {item['date']}`")
