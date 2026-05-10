import streamlit as st
import google.generativeai as genai
import requests
import random
import hashlib
import json
import datetime
import time

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
    model = genai.GenerativeModel('gemini-flash-latest')
else:
    st.error("❌ Clé API Gemini manquante. Veuillez vérifier les Secrets Streamlit.")
    st.stop()

# --- FONCTIONS DE RÉSILIENCE ---
def ask_gemini_text(prompt, max_retries=3):
    """Pour les réponses textuelles simples (comme l'analyse d'Art)."""
    full_prompt = f"Règle absolue : Réponds uniquement en français.\n{prompt}"
    for attempt in range(max_retries):
        try:
            response = model.generate_content(full_prompt)
            if response.text: return response.text
        except Exception as e:
            time.sleep(2 ** attempt)
    return "❌ L'analyse est indisponible pour le moment."

def ask_gemini_json(prompt, max_retries=3):
    """Force Gemini à renvoyer un dictionnaire structuré (Idéal pour l'extraction de données)."""
    full_prompt = f"Règle absolue : Tu dois répondre UNIQUEMENT avec un objet JSON valide en français, sans aucun formatage Markdown ni texte autour.\n\n{prompt}"
    for attempt in range(max_retries):
        try:
            response = model.generate_content(full_prompt)
            # Nettoyage au cas où Gemini ajoute des balises ```json ... ```
            clean_text = response.text.replace('```json', '').replace('```', '').strip()
            return json.loads(clean_text)
        except Exception as e:
            time.sleep(2 ** attempt)
    return None

def fetch_json_api(url, max_retries=3, timeout=10):
    """Pour les appels APIs classiques."""
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
             return {"title": "Œuvre indisponible", "author": "API Déconnectée", "image": None, "analysis": "Impossible de contacter le musée."}

        title = art.get('title', 'Inconnue')
        artist = art.get('artistDisplayName', 'Inconnu')
        
        prompt = f"Fais une analyse artistique très approfondie et détaillée (environ 6 à 8 phrases) de l'œuvre '{title}' de {artist}. Traduis le titre en français dans ton texte."
        analysis = ask_gemini_text(prompt)
        return {"title": title, "author": artist, "image": art.get('primaryImageSmall'), "analysis": analysis}

    def get_poem(self):
        prompt = f"Graine : {self.seed}. Choisis un poème célèbre de la littérature classique FRANÇAISE (Hugo, Baudelaire, Musset...). Renvoie un JSON avec : 'titre', 'auteur', 'extrait' (les 8 à 10 premiers vers), et 'analyse' (une analyse profonde de 6 à 8 phrases sur le sens et le style)."
        data = ask_gemini_json(prompt)
        if data: return data
        return {"titre": "Le Dormeur du val", "auteur": "Arthur Rimbaud", "extrait": "C'est un trou de verdure...", "analyse": "Erreur de chargement."}

    def get_cinema(self):
        prompt = f"Graine : {self.seed}. Choisis un chef-d'œuvre incontournable du cinéma mondial. Renvoie un JSON avec : 'titre', 'realisateur', 'annee', et 'analyse' (une critique fascinante et détaillée de 6 à 8 phrases sur sa réalisation et son impact)."
        data = ask_gemini_json(prompt)
        if data: return data
        return {"titre": "Film indisponible", "realisateur": "Inconnu", "annee": "", "analyse": "Erreur."}

    def get_philosophy(self):
        prompt = f"Graine : {self.seed}. Choisis un concept philosophique majeur. Renvoie un JSON avec : 'concept', 'philosophe', et 'analyse' (une explication poussée de 6 à 8 phrases montrant comment l'appliquer dans la vie quotidienne moderne)."
        data = ask_gemini_json(prompt)
        if data: return data
        return {"concept": "Concept indisponible", "philosophe": "Inconnu", "analyse": "Erreur."}

    def get_song(self):
        prompt = f"Graine : {self.seed}. Choisis une chanson légendaire (française ou internationale). Renvoie un JSON avec : 'titre', 'artiste', 'annee', et 'analyse' (une analyse détaillée de 6 à 8 phrases explorant le sens profond des paroles et l'impact culturel du morceau)."
        data = ask_gemini_json(prompt)
        if data: return data
        return {"titre": "Chanson indisponible", "artiste": "Inconnu", "annee": "", "analyse": "Erreur."}

# --- INTERFACE ---
app = CultureApp()

st.title("🏛️ L'Éveil Culturel")
st.write(f"### Votre dose de savoir du {datetime.date.today().strftime('%d/%m/%Y')}")

with st.spinner("Le curateur rédige des analyses approfondies..."):
    art_data = app.get_art()
    philo_data = app.get_philosophy()
    poem_data = app.get_poem()
    cine_data = app.get_cinema()
    song_data = app.get_song()

# Disposition en 2 colonnes bien équilibrées
col1, col2 = st.columns(2)

with col1:
    st.markdown(f'<div class="culture-card"><h3>🖼️ Art : {art_data["title"]}</h3><p><i>{art_data["author"]}</i></p></div>', unsafe_allow_html=True)
    if art_data["image"]: st.image(art_data["image"], use_column_width=True)
    st.info(art_data['analysis'])

    st.markdown(f'<div class="culture-card"><h3>🧠 Philosophie : {philo_data["concept"]}</h3><p><i>{philo_data["philosophe"]}</i></p></div>', unsafe_allow_html=True)
    st.info(philo_data['analysis'])

with col2:
    st.markdown(f'<div class="culture-card"><h3>📜 Poésie : {poem_data["titre"]}</h3><p><i>{poem_data["auteur"]}</i></p></div>', unsafe_allow_html=True)
    st.text(poem_data["extrait"])
    st.info(poem_data['analyse'])

    st.markdown(f'<div class="culture-card"><h3>🎵 Chanson : {song_data["titre"]}</h3><p><i>{song_data["artiste"]} ({song_data["annee"]})</i></p></div>', unsafe_allow_html=True)
    st.info(song_data['analyse'])

    st.markdown(f'<div class="culture-card"><h3>🎬 Cinéma : {cine_data["titre"]}</h3><p><i>{cine_data["realisateur"]} ({cine_data["annee"]})</i></p></div>', unsafe_allow_html=True)
    st.info(cine_data['analyse'])
