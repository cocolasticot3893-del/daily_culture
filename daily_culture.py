import streamlit as st
import requests
import random
import hashlib
import json
import datetime
import urllib.parse
from pathlib import Path

# --- CONFIGURATION STREAMLIT ---
st.set_page_config(page_title="L'Éveil Culturel", page_icon="🏛️", layout="centered")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=Source+Sans+Pro:wght@300;400;600&display=swap');
    
    .stApp { background-color: #f9f7f1; color: #2c3e50; }
    h1, h2, h3 { font-family: 'Playfair Display', serif; color: #1a252f; text-align: center; }
    h1 { font-size: 2.5rem; border-bottom: 2px solid #d4af37; padding-bottom: 20px; margin-bottom: 30px; }
    .stText, p, div { font-family: 'Source Sans Pro', sans-serif; font-size: 1.1rem; line-height: 1.6; }
    
    .culture-card {
        background: #ffffff; padding: 30px; border-radius: 8px;
        border-top: 4px solid #d4af37; box-shadow: 0 5px 15px rgba(0, 0, 0, 0.05);
        margin-bottom: 30px;
    }
    .card-title { font-family: 'Playfair Display', serif; font-size: 1.6rem; color: #1a252f; margin-bottom: 5px; }
    .card-subtitle { font-style: italic; color: #7f8c8d; margin-bottom: 15px; font-size: 1.05rem; border-bottom: 1px solid #eee; padding-bottom: 10px; }
    .poem-box { font-family: 'Playfair Display', serif; font-size: 1.15rem; line-height: 1.8; margin: 20px 0; padding-left: 20px; border-left: 2px solid #d4af37; white-space: pre-wrap; }
    .analysis-box { background-color: #fcfcfb; border-left: 3px solid #bdc3c7; padding: 15px; margin-top: 20px; font-size: 1.05rem; color: #34495e; border-radius: 0 4px 4px 0; }
    
    /* Liens et boutons */
    .deep-link { display: inline-block; margin-top: 15px; color: #d4af37; text-decoration: none; font-weight: 600; font-size: 1rem; }
    .deep-link:hover { text-decoration: underline; }
    
    [data-testid="stImage"] img { border-radius: 4px; box-shadow: 0 8px 20px rgba(0,0,0,0.15); margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- INITIALISATION DEEPSEEK API ---
DEEPSEEK_KEY = st.secrets.get("DEEPSEEK_API_KEY")

if not DEEPSEEK_KEY:
    st.error("❌ Clé API DeepSeek manquante dans les Secrets Streamlit.")
    st.stop()

# --- GESTION DES PRÉFÉRENCES (J'AIME / J'AIME PAS) ---
PREFS_FILE = Path("preferences.json")

def load_preferences():
    if PREFS_FILE.exists():
        with open(PREFS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_preference(category, title, feedback):
    prefs = load_preferences()
    # Éviter les doublons le même jour
    today = datetime.date.today().strftime("%Y-%m-%d")
    for p in prefs:
        if p["date"] == today and p["category"] == category and p["title"] == title:
            p["feedback"] = feedback # Met à jour si on change d'avis
            with open(PREFS_FILE, "w", encoding="utf-8") as f: json.dump(prefs, f, ensure_ascii=False, indent=4)
            return
            
    prefs.append({"date": today, "category": category, "title": title, "feedback": feedback})
    with open(PREFS_FILE, "w", encoding="utf-8") as f:
        json.dump(prefs, f, ensure_ascii=False, indent=4)
    st.toast(f"Préférence enregistrée : {feedback} pour {title} ! 💾")

# --- FONCTION API DEEPSEEK (AVEC MISE EN CACHE) ---
# Le décorateur @st.cache_data sauvegarde le résultat pour la journée.
# Si le "seed" est le même, la fonction ne relance pas l'API = 0 surcoût !
@st.cache_data(show_spinner=False, ttl=86400) # Cache expire après 24h
def ask_deepseek_json(prompt, seed):
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "Tu es un expert culturel français. Tu DOIS répondre exclusivement au format JSON valide, sans balises Markdown (` ```json `), uniquement l'objet JSON."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"} # Force le JSON strict sur DeepSeek
    }
    
    try:
        response = requests.post("[https://api.deepseek.com/chat/completions](https://api.deepseek.com/chat/completions)", headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        # Nettoyage si jamais DeepSeek ajoute quand même des balises
        clean_text = content.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_text)
    except Exception as e:
        return {"erreur": f"Erreur de génération : {str(e)}"}

@st.cache_data(show_spinner=False, ttl=86400)
def fetch_met_art(seed):
    # IDs d'oeuvres garanties d'avoir de belles images
    ids = [436535, 436528, 436532, 435882, 435809, 436533, 436529, 437112, 436121, 459123]
    random.seed(seed)
    obj_id = random.choice(ids)
    try:
        res = requests.get(f"[https://collectionapi.metmuseum.org/public/collection/v1/objects/](https://collectionapi.metmuseum.org/public/collection/v1/objects/){obj_id}", timeout=10)
        res.raise_for_status()
        art = res.json()
        
        # On passe à DeepSeek pour l'analyse
        prompt = f"Génère une analyse captivante (5 phrases) de l'œuvre '{art.get('title')}' de {art.get('artistDisplayName')}. Traduis le titre. Renvoie un JSON avec les clés: 'titre_fr', 'analyse'."
        ds_data = ask_deepseek_json(prompt, seed)
        
        return {
            "title": ds_data.get('titre_fr', art.get('title')),
            "author": art.get('artistDisplayName', 'Inconnu'),
            "image": art.get('primaryImageSmall'),
            "analyse": ds_data.get('analyse', 'Erreur analyse.'),
            "link": art.get('objectURL')
        }
    except:
        return {"erreur": True}

# --- GENERATION DES DONNÉES ---
today_str = datetime.date.today().strftime("%Y-%m-%d")
daily_seed = int(hashlib.md5(today_str.encode()).hexdigest(), 16) % (10**8)

def get_daily_content():
    with st.spinner("L'API DeepSeek prépare votre exposition (Mise en cache en cours...)"):
        # Art (MET API + DeepSeek)
        art = fetch_met_art(daily_seed)
        
        # Poésie
        prompt_poem = f"Graine : {daily_seed}. Choisis un poème magnifique de la littérature française classique. Renvoie un JSON avec : 'titre', 'auteur', 'poeme_entier' (le texte COMPLET du poème avec les retours à la ligne \\n), 'analyse' (5 phrases)."
        poem = ask_deepseek_json(prompt_poem, daily_seed + 1)
        
        # Musique
        prompt_song = f"Graine : {daily_seed}. Choisis une chanson culte. Renvoie un JSON avec : 'titre', 'artiste', 'annee', 'analyse' (5 phrases sur l'impact de la chanson)."
        song = ask_deepseek_json(prompt_song, daily_seed + 2)
        
        # Cinéma
        prompt_cine = f"Graine : {daily_seed}. Choisis un grand film classique ou d'auteur. Renvoie un JSON avec : 'titre', 'realisateur', 'annee', 'analyse' (5 phrases)."
        cine = ask_deepseek_json(prompt_cine, daily_seed + 3)
        
        # Philo
        prompt_philo = f"Graine : {daily_seed}. Choisis un concept philosophique applicable à la vie moderne. Renvoie un JSON avec : 'concept', 'philosophe', 'analyse' (5 phrases)."
        philo = ask_deepseek_json(prompt_philo, daily_seed + 4)
        
        return art, poem, song, cine, philo

# Chargement (depuis le cache si déjà fait aujourd'hui)
art_data, poem_data, song_data, cine_data, philo_data = get_daily_content()

# --- HELPER POUR RECHERCHES ---
def wiki_link(query):
    safe_query = urllib.parse.quote(query)
    return f"[https://fr.wikipedia.org/wiki/Spécial:Recherche?search=](https://fr.wikipedia.org/wiki/Spécial:Recherche?search=){safe_query}"

def yt_music_link(artist, title):
    safe_query = urllib.parse.quote(f"{artist} {title}")
    return f"[https://music.youtube.com/search?q=](https://music.youtube.com/search?q=){safe_query}"

# --- INTERFACE UTILISATEUR ---
st.title("L'Éveil Culturel")
st.markdown(f"<p style='text-align: center; color: #7f8c8d; font-style: italic; margin-top: -30px; margin-bottom: 40px;'>L'Exposition du {datetime.date.today().strftime('%d %B %Y')}</p>", unsafe_allow_html=True)

# 1. ART
if not art_data.get("erreur"):
    st.markdown(f"""
    <div class="culture-card">
        <div class="card-title">🖼️ {art_data.get('title')}</div>
        <div class="card-subtitle">{art_data.get('author')}</div>
    </div>
    """, unsafe_allow_html=True)
    if art_data.get("image"): st.image(art_data["image"])
    st.markdown(f'<div class="analysis-box">{art_data.get("analyse")}</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("👍", key="art_like"): save_preference("Art", art_data.get("title"), "Aime")
    with col2:
        if st.button("👎", key="art_dislike"): save_preference("Art", art_data.get("title"), "N'aime pas")
    with col3:
        st.markdown(f"<a href='{art_data.get('link')}' target='_blank' class='deep-link'>🔍 Voir l'œuvre sur le site du MET</a>", unsafe_allow_html=True)
    st.write("---")

# 2. POÉSIE
if not poem_data.get("erreur"):
    titre = poem_data.get('titre', 'Inconnu')
    auteur = poem_data.get('auteur', 'Inconnu')
    st.markdown(f"""
    <div class="culture-card">
        <div class="card-title">📜 {titre}</div>
        <div class="card-subtitle">{auteur}</div>
        <div class="poem-box">{poem_data.get('poeme_entier', 'Texte non disponible')}</div>
        <div class="analysis-box">{poem_data.get('analyse')}</div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("👍", key="poem_like"): save_preference("Poésie", titre, "Aime")
    with col2:
        if st.button("👎", key="poem_dislike"): save_preference("Poésie", titre, "N'aime pas")
    with col3:
        st.markdown(f"<a href='{wiki_link(auteur)}' target='_blank' class='deep-link'>📖 Découvrir {auteur} sur Wikipédia</a>", unsafe_allow_html=True)
    st.write("---")

# 3. MUSIQUE
if not song_data.get("erreur"):
    titre = song_data.get('titre', 'Inconnu')
    artiste = song_data.get('artiste', 'Inconnu')
    st.markdown(f"""
    <div class="culture-card">
        <div class="card-title">🎵 {titre}</div>
        <div class="card-subtitle">{artiste} ({song_data.get('annee', '')})</div>
        <div class="analysis-box">{song_data.get('analyse')}</div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("👍", key="song_like"): save_preference("Musique", titre, "Aime")
    with col2:
        if st.button("👎", key="song_dislike"): save_preference("Musique", titre, "N'aime pas")
    with col3:
        st.markdown(f"<a href='{yt_music_link(artiste, titre)}' target='_blank' class='deep-link'>🎧 Écouter sur YouTube Music</a>", unsafe_allow_html=True)
    st.write("---")

# 4. CINÉMA
if not cine_data.get("erreur"):
    titre = cine_data.get('titre', 'Inconnu')
    realisateur = cine_data.get('realisateur', 'Inconnu')
    st.markdown(f"""
    <div class="culture-card">
        <div class="card-title">🎬 {titre}</div>
        <div class="card-subtitle">{realisateur} ({cine_data.get('annee', '')})</div>
        <div class="analysis-box">{cine_data.get('analyse')}</div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("👍", key="cine_like"): save_preference("Cinéma", titre, "Aime")
    with col2:
        if st.button("👎", key="cine_dislike"): save_preference("Cinéma", titre, "N'aime pas")
    with col3:
        st.markdown(f"<a href='{wiki_link(titre + ' film')}' target='_blank' class='deep-link'>🎞️ Fiche du film sur Wikipédia</a>", unsafe_allow_html=True)
    st.write("---")

# 5. PHILOSOPHIE
if not philo_data.get("erreur"):
    concept = philo_data.get('concept', 'Inconnu')
    philosophe = philo_data.get('philosophe', 'Inconnu')
    st.markdown(f"""
    <div class="culture-card">
        <div class="card-title">🧠 {concept}</div>
        <div class="card-subtitle">{philosophe}</div>
        <div class="analysis-box">{philo_data.get('analyse')}</div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("👍", key="philo_like"): save_preference("Philosophie", concept, "Aime")
    with col2:
        if st.button("👎", key="philo_dislike"): save_preference("Philosophie", concept, "N'aime pas")
    with col3:
        st.markdown(f"<a href='{wiki_link(concept)}' target='_blank' class='deep-link'>📚 Approfondir ce concept</a>", unsafe_allow_html=True)
