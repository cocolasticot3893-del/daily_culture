import streamlit as st
import google.generativeai as genai
import requests
import random
import hashlib
import json
import datetime
from pathlib import Path

# --- CONFIGURATION ---
st.set_page_config(page_title="L'Éveil Culturel", page_icon="🏛️", layout="wide")

# Custom CSS pour le style
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;1,400&family=Lato:wght@300;400&display=swap');
    .main { background-color: #fdfbf7; }
    h1, h2, h3 { font-family: 'Playfair Display', serif; color: #1a1a1a; }
    .stText, p, li { font-family: 'Lato', sans-serif; font-size: 1.1rem; }
    .culture-card {
        background-color: white;
        padding: 25px;
        border-radius: 15px;
        border-left: 5px solid #b8860b;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- GESTION DES CLÉS API (Priorité aux Secrets Streamlit) ---
GEMINI_KEY = st.secrets.get("GEMINI_API_KEY")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-pro')
else:
    st.error("❌ Clé API Gemini non trouvée dans les Secrets. Vérifiez votre configuration Streamlit Cloud.")
    st.stop()

# --- LOGIQUE DE SEED ---
def get_daily_seed():
    today = datetime.date.today().strftime("%Y-%m-%d")
    return int(hashlib.md5(today.encode()).hexdigest(), 16) % (10**8)

class CultureApp:
    def __init__(self):
        self.seed = get_daily_seed()
        random.seed(self.seed)
        self.history_file = Path("culture_history.json")

    def ask_gemini(self, prompt):
        try:
            response = model.generate_content(prompt)
            return response.text
        except:
            return "Désolé, l'analyse est indisponible pour le moment."

    def get_poem(self):
        # PoetryDB (Données souvent en anglais)
        res = requests.get("https://poetrydb.org/poemcount/20")
        poems = res.json()
        poem = random.choice(poems)
        # On demande à Gemini de traduire ou de présenter en français
        prompt = f"""Voici un poème : Titre '{poem['title']}', Auteur '{poem['author']}'. 
        Contenu : {' '.join(poem['lines'][:10])}. 
        TRADUIS le titre en français. FAIS une analyse rapide de 3 lignes en français. 
        PROPOSE une version française ou un poème français équivalent si celui-ci est trop complexe."""
        analysis = self.ask_gemini(prompt)
        return {"type": "Poésie", "title": poem['title'], "author": poem['author'], "content": "\n".join(poem['lines'][:8]), "analysis": analysis}

    def get_art(self):
        # Liste d'IDs d'oeuvres célèbres du MET
        ids = [436535, 436528, 436532, 435882, 435809, 436533, 436529]
        obj_id = random.choice(ids)
        res = requests.get(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{obj_id}")
        art = res.json()
        prompt = f"Analyse en français l'œuvre '{art.get('title', 'Inconnue')}' de {art.get('artistDisplayName', 'Inconnu')}. Traduis le titre si nécessaire."
        analysis = self.ask_gemini(prompt)
        return {"type": "Art", "title": art.get('title'), "author": art.get('artistDisplayName'), "image": art.get('primaryImageSmall'), "analysis": analysis}

    def get_cinema(self):
        # On demande à Gemini de CHOISIR le film en fonction de la seed pour avoir de la variété
        prompt = f"""En fonction de la graine aléatoire {self.seed}, choisis un chef-d'œuvre du cinéma mondial (classique ou moderne). 
        Donne : Le titre, le réalisateur, l'année et une analyse passionnante de 3 phrases, le tout en français."""
        response = self.ask_gemini(prompt)
        return {"type": "Cinéma", "title": "Focus du jour", "author": "Réalisateur", "analysis": response}

    def get_philosophy(self):
        # On demande à Gemini un concept philo basé sur la seed
        prompt = f"En fonction de la graine {self.seed}, présente un concept philosophique célèbre, son auteur et une application concrète dans la vie moderne. En français."
        response = self.ask_gemini(prompt)
        return {"type": "Philosophie", "title": "Pensée du jour", "author": "Philosophe", "analysis": response}

# --- INTERFACE ---
app = CultureApp()

st.title("🏛️ L'Éveil Culturel")
st.write(f"### Votre dose de savoir du {datetime.date.today().strftime('%d/%m/%Y')}")

tab1, tab2 = st.tabs(["✨ Aujourd'hui", "📚 Historique"])

with tab1:
    col1, col2 = st.columns(2)
    
    with col1:
        art = app.get_art()
        st.markdown(f'<div class="culture-card"><h3>🖼️ Art : {art["title"]}</h3><p><i>{art["author"]}</i></p></div>', unsafe_allow_html=True)
        if art["image"]: st.image(art["image"])
        st.write(art['analysis'])

        philo = app.get_philosophy()
        st.markdown(f'<div class="culture-card"><h3>🧠 Philosophie</h3></div>', unsafe_allow_html=True)
        st.write(philo['analysis'])

    with col2:
        poem = app.get_poem()
        st.markdown(f'<div class="culture-card"><h3>📜 Poésie : {poem["title"]}</h3><p><i>{poem["author"]}</i></p></div>', unsafe_allow_html=True)
        st.text(poem["content"])
        st.info(poem['analysis'])

        cine = app.get_cinema()
        st.markdown(f'<div class="culture-card"><h3>🎬 Cinéma</h3></div>', unsafe_allow_html=True)
        st.write(cine['analysis'])

with tab2:
    st.write("L'historique sera bientôt disponible ici.")
