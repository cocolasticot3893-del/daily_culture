import streamlit as st
import google.generativeai as genai
import requests
import random
import hashlib
import json
import datetime
import time
from pathlib import Path

# --- CONFIGURATION STREAMLIT ---
st.set_page_config(page_title="L'Éveil Culturel", page_icon="🏛️", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;1,400&family=Lato:wght@300;400&display=swap');
    .main { background-color: #fdfbf7; }
    h1, h2, h3 { font-family: 'Playfair Display', serif; color: #1a1a1a; }
    .stText, p, li { font-family: 'Lato', sans-serif; font-size: 1.1rem; }
    .culture-card {
        background-color: white; padding: 25px; border-radius: 15px;
        border-left: 5px solid #b8860b; box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    .error-text { color: #d9534f; font-size: 0.9em; }
    </style>
    """, unsafe_allow_html=True)

# --- INITIALISATION GEMINI ---
GEMINI_KEY = st.secrets.get("GEMINI_API_KEY")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    # Utilisation de la dernière version Flash pour rapidité et fiabilité
    model = genai.GenerativeModel('gemini-flash-latest')
else:
    st.error("❌ Clé API Gemini manquante. Veuillez vérifier les Secrets Streamlit.")
    st.stop()

# --- FONCTIONS DE RÉSILIENCE (RETRY & BACKOFF) ---
def ask_gemini_with_retry(prompt, max_retries=3):
    """Envoie une requête à Gemini avec relance automatique en cas d'échec."""
    full_prompt = f"Règle absolue : Tu dois répondre UNIQUEMENT en français.\n\n{prompt}"
    
    for attempt in range(max_retries):
        try:
            response = model.generate_content(full_prompt)
            if response.text:
                return response.text
        except Exception as e:
            if attempt == max_retries - 1:
                return f"<span class='error-text'>❌ Analyse échouée après {max_retries} tentatives (Erreur: {str(e)})</span>"
            time.sleep(2 ** attempt) # Exponential backoff : attend 1s, puis 2s, puis 4s
            
    return "<span class='error-text'>❌ L'IA a retourné une réponse vide.</span>"

def fetch_json_with_retry(url, max_retries=3, timeout=10):
    """Récupère un JSON avec gestion des timeouts et relances."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status() # Lève une erreur si status n'est pas 200
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                return None # Retourne None si échec total
            time.sleep(2 ** attempt)
    return None

# --- LOGIQUE MÉTIER ---
class CultureApp:
    def __init__(self):
        # La seed du jour garantit la stabilité sur 24h
        today = datetime.date.today().strftime("%Y-%m-%d")
        self.seed = int(hashlib.md5(today.encode()).hexdigest(), 16) % (10**8)
        random.seed(self.seed)

    def get_poem(self):
        data = fetch_json_with_retry("https://poetrydb.org/poemcount/20")
        
        # Fallback si l'API PoetryDB est hors ligne
        if not data:
            return {
                "type": "Poésie", "title": "Le Dormeur du val (Mode Secours)", 
                "author": "Arthur Rimbaud", 
                "content": "C'est un trou de verdure où chante une rivière...\nAccrochant follement aux herbes des haillons...",
                "analysis": "Une magnifique réflexion sur la mort et la guerre, servie en mode hors-ligne."
            }
            
        poem = random.choice(data)
        lines_preview = "\n".join(poem.get('lines', [])[:8])
        
        prompt = f"Analyse brièvement (3 phrases) ce poème de {poem['author']} intitulé '{poem['title']}'. Traduis le titre s'il est en anglais."
        analysis = ask_gemini_with_retry(prompt)
        
        return {"type": "Poésie", "title": poem.get('title', 'Inconnu'), "author": poem.get('author', 'Inconnu'), "content": lines_preview, "analysis": analysis}

    def get_art(self):
        ids = [436535, 436528, 436532, 435882, 435809, 436533, 436529]
        obj_id = random.choice(ids)
        art = fetch_json_with_retry(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{obj_id}")
        
        # Fallback si l'API MET échoue
        if not art:
             return {"type": "Art", "title": "Œuvre indisponible", "author": "API Déconnectée", "image": None, "analysis": "Impossible de contacter le musée."}

        title = art.get('title', 'Inconnue')
        artist = art.get('artistDisplayName', 'Inconnu')
        
        prompt = f"Fais une analyse artistique très courte et captivante (3 phrases max) de l'œuvre '{title}' de {artist}. Traduis le titre en français dans ton texte."
        analysis = ask_gemini_with_retry(prompt)
        
        return {"type": "Art", "title": title, "author": artist, "image": art.get('primaryImageSmall'), "analysis": analysis}

    def get_cinema(self):
        prompt = f"En te basant sur la graine aléatoire {self.seed}, choisis un film culte du cinéma mondial. Présente-le au format 'Titre (Année) - Réalisateur' puis donne une critique concise et fascinante de 3 lignes."
        analysis = ask_gemini_with_retry(prompt)
        return {"type": "Cinéma", "title": "La Sélection du Curateur", "analysis": analysis}

    def get_philosophy(self):
        prompt = f"En te basant sur la graine {self.seed}, choisis un concept philosophique célèbre. Donne le nom du concept, le philosophe associé, et explique-le simplement en 3 phrases en montrant comment l'appliquer aujourd'hui."
        analysis = ask_gemini_with_retry(prompt)
        return {"type": "Philosophie", "title": "La Pensée du Curateur", "analysis": analysis}

# --- INTERFACE ---
app = CultureApp()

st.title("🏛️ L'Éveil Culturel")
st.write(f"### Votre dose de savoir du {datetime.date.today().strftime('%d/%m/%Y')}")

# On génère toutes les données en avance pour gérer les colonnes proprement
with st.spinner("Le curateur prépare votre sélection du jour... (Cela peut prendre quelques secondes)"):
    art_data = app.get_art()
    philo_data = app.get_philosophy()
    poem_data = app.get_poem()
    cine_data = app.get_cinema()

col1, col2 = st.columns(2)

with col1:
    st.markdown(f'<div class="culture-card"><h3>🖼️ Art : {art_data["title"]}</h3><p><i>{art_data["author"]}</i></p></div>', unsafe_allow_html=True)
    if art_data["image"]: st.image(art_data["image"], use_column_width=True)
    st.info(art_data['analysis'])

    st.markdown(f'<div class="culture-card"><h3>🧠 Philosophie</h3></div>', unsafe_allow_html=True)
    st.info(philo_data['analysis'])

with col2:
    st.markdown(f'<div class="culture-card"><h3>📜 Poésie : {poem_data["title"]}</h3><p><i>{poem_data["author"]}</i></p></div>', unsafe_allow_html=True)
    st.text(poem_data["content"])
    st.info(poem_data['analysis'])

    st.markdown(f'<div class="culture-card"><h3>🎬 Cinéma</h3></div>', unsafe_allow_html=True)
    st.info(cine_data['analysis'])
