import streamlit as st
import google.generativeai as genai
import requests
import random
import hashlib
import json
import datetime
import time

# --- CONFIGURATION STREAMLIT ---
# On passe en mode 'centered' pour un effet "page de livre" plutôt que tableau de bord
st.set_page_config(page_title="L'Éveil Culturel", page_icon="🏛️", layout="centered")

# --- CSS INSPIRÉ DES GALERIES D'ART ---
st.markdown("""
    <style>
    /* Importation de polices élégantes */
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=Source+Sans+Pro:wght@300;400;600&display=swap');
    
    /* Fond couleur parchemin clair / mur de musée */
    .stApp {
        background-color: #f9f7f1;
        color: #2c3e50;
    }
    
    /* Typographie des titres */
    h1, h2, h3 {
        font-family: 'Playfair Display', serif;
        color: #1a252f;
        text-align: center;
    }
    
    h1 {
        font-size: 3rem;
        border-bottom: 2px solid #d4af37; /* Ligne dorée */
        padding-bottom: 20px;
        margin-bottom: 40px;
    }

    /* Style des textes */
    .stText, p, li, div {
        font-family: 'Source Sans Pro', sans-serif;
        font-size: 1.15rem;
        line-height: 1.6;
    }

    /* Le design des Cartes Culturelles */
    .culture-card {
        background: #ffffff;
        padding: 40px;
        border-radius: 8px;
        border-top: 4px solid #d4af37; /* Touche or/moutarde */
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05); /* Ombre douce et moderne */
        margin-bottom: 30px;
        transition: transform 0.3s ease;
    }
    
    .culture-card:hover {
        transform: translateY(-5px); /* Petit effet de soulèvement au survol */
    }

    /* Titres à l'intérieur des cartes */
    .card-title {
        font-family: 'Playfair Display', serif;
        font-size: 1.8rem;
        color: #1a252f;
        margin-bottom: 5px;
        text-align: left;
    }
    
    .card-subtitle {
        font-style: italic;
        color: #7f8c8d;
        margin-bottom: 25px;
        font-size: 1.1rem;
        border-bottom: 1px solid #eee;
        padding-bottom: 15px;
    }

    /* Zone d'analyse (fond grisé très léger) */
    .analysis-box {
        background-color: #fcfcfb;
        border-left: 3px solid #bdc3c7;
        padding: 20px;
        margin-top: 25px;
        font-size: 1.05rem;
        color: #34495e;
        border-radius: 0 4px 4px 0;
    }
    
    /* Mettre l'image du tableau en valeur */
    [data-testid="stImage"] img {
        border-radius: 4px;
        box-shadow: 0 8px 20px rgba(0,0,0,0.15);
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- INITIALISATION GEMINI ---
GEMINI_KEY = st.secrets.get("GEMINI_API_KEY")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-flash-latest')
else:
    st.error("❌ Clé API Gemini manquante. Veuillez vérifier les Secrets Streamlit.")
    st.stop()

# --- FONCTIONS DE RÉSILIENCE ---
def ask_gemini_text(prompt, max_retries=3):
    full_prompt = f"Règle absolue : Réponds uniquement en français.\n{prompt}"
    for attempt in range(max_retries):
        try:
            response = model.generate_content(full_prompt)
            if response.text: return response.text
        except Exception:
            time.sleep(2 ** attempt)
    return "L'analyse est indisponible pour le moment."

def ask_gemini_json(prompt, max_retries=3):
    full_prompt = f"Règle absolue : Tu dois répondre UNIQUEMENT avec un objet JSON valide en français, sans aucun formatage Markdown.\n\n{prompt}"
    for attempt in range(max_retries):
        try:
            response = model.generate_content(full_prompt)
            clean_text = response.text.replace('```json', '').replace('```', '').strip()
            return json.loads(clean_text)
        except Exception:
            time.sleep(2 ** attempt)
    return None

def fetch_json_api(url, max_retries=3, timeout=10):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except:
            time.sleep(2 ** attempt)
    return None

# --- LOGIQUE MÉTIER ---
class CultureApp:
    def __init__(self):
        today = datetime.date.today().strftime("%Y-%m-%d")
        self.seed = int(hashlib.md5(today.encode()).hexdigest(), 16) % (10**8)
        random.seed(self.seed)

    def get_art(self):
        ids = [436535, 436528, 436532, 435882, 435809, 436533, 436529]
        obj_id = random.choice(ids)
        art = fetch_json_api(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{obj_id}")
        
        if not art:
             return {"title": "Œuvre indisponible", "author": "API Déconnectée", "image": None, "analyse": "Impossible de contacter le musée."}

        title = art.get('title', 'Inconnue')
        artist = art.get('artistDisplayName', 'Inconnu')
        
        prompt = f"Fais une analyse artistique de 5 à 7 phrases de l'œuvre '{title}' de {artist}. Traduis le titre en français."
        analysis = ask_gemini_text(prompt)
        return {"title": title, "author": artist, "image": art.get('primaryImageSmall'), "analyse": analysis}

    def get_poem(self):
        prompt = f"Graine : {self.seed}. Choisis un poème de la littérature française. Renvoie un JSON avec : 'titre', 'auteur', 'extrait', et 'analyse'."
        data = ask_gemini_json(prompt)
        if data: return data
        return {"titre": "Le Dormeur du val", "auteur": "Arthur Rimbaud", "extrait": "C'est un trou de verdure...", "analyse": "Texte non chargé."}

    def get_cinema(self):
        prompt = f"Graine : {self.seed}. Choisis un chef-d'œuvre du cinéma. Renvoie un JSON avec : 'titre', 'realisateur', 'annee', et 'analyse'."
        data = ask_gemini_json(prompt)
        if data: return data
        return {"titre": "Film indisponible", "realisateur": "Inconnu", "annee": "", "analyse": "Erreur."}

    def get_philosophy(self):
        prompt = f"Graine : {self.seed}. Choisis un concept philosophique. Renvoie un JSON avec : 'concept', 'philosophe', et 'analyse'."
        data = ask_gemini_json(prompt)
        if data: return data
        return {"concept": "Concept indisponible", "philosophe": "Inconnu", "analyse": "Erreur."}

    def get_song(self):
        prompt = f"Graine : {self.seed}. Choisis une chanson légendaire. Renvoie un JSON avec : 'titre', 'artiste', 'annee', et 'analyse'."
        data = ask_gemini_json(prompt)
        if data: return data
        return {"titre": "Chanson indisponible", "artiste": "Inconnu", "annee": "", "analyse": "Erreur."}

# --- INTERFACE ---
app = CultureApp()

st.title("L'Éveil Culturel")
st.markdown(f"<p style='text-align: center; color: #7f8c8d; font-style: italic; margin-top: -30px; margin-bottom: 50px;'>L'Exposition du {datetime.date.today().strftime('%d %B %Y')}</p>", unsafe_allow_html=True)

with st.spinner("Le curateur dispose les œuvres dans la galerie..."):
    art_data = app.get_art()
    philo_data = app.get_philosophy()
    poem_data = app.get_poem()
    cine_data = app.get_cinema()
    song_data = app.get_song()

# --- AFFICHAGE MAGNIFIÉ ---

# 1. ART
st.markdown(f"""
<div class="culture-card">
    <div class="card-title">🖼️ {art_data.get('title', 'Sans titre')}</div>
    <div class="card-subtitle">{art_data.get('author', 'Inconnu')}</div>
</div>
""", unsafe_allow_html=True)
if art_data.get("image"):
    st.image(art_data["image"])
st.markdown(f'<div class="analysis-box">{art_data.get("analyse", art_data.get("analysis", "Analyse indisponible."))}</div>', unsafe_allow_html=True)
st.write("---")

# 2. PHILOSOPHIE
st.markdown(f"""
<div class="culture-card">
    <div class="card-title">🧠 {philo_data.get('concept', 'Concept inconnu')}</div>
    <div class="card-subtitle">{philo_data.get('philosophe', 'Auteur inconnu')}</div>
    <div class="analysis-box">{philo_data.get("analyse", philo_data.get("analysis", "Analyse indisponible."))}</div>
</div>
""", unsafe_allow_html=True)

# 3. POÉSIE
extrait_html = poem_data.get('extrait', 'Extrait non disponible').replace('\n', '<br>')
st.markdown(f"""
<div class="culture-card">
    <div class="card-title">📜 {poem_data.get('titre', 'Poème inconnu')}</div>
    <div class="card-subtitle">{poem_data.get('auteur', 'Auteur inconnu')}</div>
    <div style="font-family: 'Playfair Display', serif; font-size: 1.2rem; line-height: 1.8; margin: 20px 0; padding-left: 20px; border-left: 2px solid #eee;">
        {extrait_html}
    </div>
    <div class="analysis-box">{poem_data.get("analyse", poem_data.get("analysis", "Analyse indisponible."))}</div>
</div>
""", unsafe_allow_html=True)

# 4. MUSIQUE
st.markdown(f"""
<div class="culture-card">
    <div class="card-title">🎵 {song_data.get('titre', 'Chanson inconnue')}</div>
    <div class="card-subtitle">{song_data.get('artiste', 'Artiste inconnu')} ({song_data.get('annee', '')})</div>
    <div class="analysis-box">{song_data.get("analyse", song_data.get("analysis", "Analyse indisponible."))}</div>
</div>
""", unsafe_allow_html=True)

# 5. CINÉMA
st.markdown(f"""
<div class="culture-card">
    <div class="card-title">🎬 {cine_data.get('titre', 'Film inconnu')}</div>
    <div class="card-subtitle">{cine_data.get('realisateur', 'Réalisateur inconnu')} ({cine_data.get('annee', '')})</div>
    <div class="analysis-box">{cine_data.get("analyse", cine_data.get("analysis", "Analyse indisponible."))}</div>
</div>
""", unsafe_allow_html=True)
