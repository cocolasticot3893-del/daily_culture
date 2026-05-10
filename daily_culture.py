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

# Custom CSS pour un look "Art & Culture"
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

# Gestion des clés API (à mettre dans .streamlit/secrets.toml en prod)
GEMINI_API_KEY = st.sidebar.text_input("Clé Gemini API", type="password")
TMDB_API_KEY = st.sidebar.text_input("Clé TMDB API (Optionnel)", type="password")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-pro')
else:
    st.warning("Veuillez entrer votre clé API Gemini dans la barre latérale pour activer les analyses.")

# --- LOGIQUE DE SEED (REPRODUCTIBILITÉ ML) ---
def get_daily_seed():
    today = datetime.date.today().strftime("%Y-%m-%d")
    return int(hashlib.md5(today.encode()).hexdigest(), 16) % (10**8)

# --- PROVIDERS DE CONTENU ---

class CultureApp:
    def __init__(self):
        self.seed = get_daily_seed()
        random.seed(self.seed)
        self.history_file = Path("culture_history.json")

    def analyze_with_gemini(self, prompt):
        if not GEMINI_API_KEY: return "Analyse indisponible (Clé API manquante)."
        try:
            response = model.generate_content(f"En tant qu'expert culturel, fais une analyse très courte (3 phrases max) et percutante de : {prompt}")
            return response.text
        except: return "Erreur lors de la génération de l'analyse."

    def get_poem(self):
        # PoetryDB API
        res = requests.get("https://poetrydb.org/poemcount/20")
        poems = res.json()
        poem = random.choice(poems)
        analysis = self.analyze_with_gemini(f"le poème '{poem['title']}' de {poem['author']}")
        return {"type": "Poésie", "title": poem['title'], "author": poem['author'], "content": "\n".join(poem['lines'][:10]) + "...", "analysis": analysis}

    def get_art(self):
        # MET Museum API
        # On cherche des peintures célèbres (ID arbitraire pour l'exemple)
        obj_id = random.choice([436535, 436528, 436532, 435882, 435809]) 
        res = requests.get(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{obj_id}")
        art = res.json()
        analysis = self.analyze_with_gemini(f"l'oeuvre {art['title']} de {art['artistDisplayName']}")
        return {"type": "Art", "title": art['title'], "author": art['artistDisplayName'], "image": art['primaryImageSmall'], "analysis": analysis}

    def get_cinema(self):
        # Mock si pas d'API TMDB, sinon call TMDB
        classics = [
            {"title": "Citizen Kane", "dir": "Orson Welles", "year": "1941"},
            {"title": "Les Sept Samouraïs", "dir": "Akira Kurosawa", "year": "1954"},
            {"title": "2001, l'Odyssée de l'espace", "dir": "Stanley Kubrick", "year": "1968"}
        ]
        movie = random.choice(classics)
        analysis = self.analyze_with_gemini(f"le film {movie['title']} de {movie['dir']}")
        return {"type": "Cinéma", "title": movie['title'], "author": movie['dir'], "year": movie['year'], "analysis": analysis}

    def get_philosophy(self):
        concepts = [
            {"concept": "L'Allégorie de la Caverne", "author": "Platon"},
            {"concept": "L'Impératif Catégorique", "author": "Kant"},
            {"concept": "L'Amor Fati", "author": "Nietzsche"}
        ]
        philo = random.choice(concepts)
        analysis = self.analyze_with_gemini(f"le concept philosophique de {philo['concept']} par {philo['author']}")
        return {"type": "Philosophie", "title": philo['concept'], "author": philo['author'], "analysis": analysis}

    def save_to_history(self, data):
        history = []
        if self.history_file.exists():
            with open(self.history_file, 'r') as f: history = json.load(f)
        
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        if not any(d['date'] == today_str for d in history):
            history.append({"date": today_str, "content": data})
            with open(self.history_file, 'w') as f: json.dump(history, f)

# --- INTERFACE UTILISATEUR ---

app = CultureApp()

st.title("🏛️ L'Éveil Culturel")
st.subheader(f"Votre dose de savoir du {datetime.date.today().strftime('%d %B %Y')}")

tabs = st.tabs(["✨ Aujourd'hui", "📚 Historique", "⚙️ Paramètres"])

with tabs[0]:
    # Génération des données du jour
    col1, col2 = st.columns([1, 1])
    
    data_today = []
    
    with col1:
        # Bloc Art
        art = app.get_art()
        st.markdown(f'<div class="culture-card"><h3>🖼️ Art : {art["title"]}</h3><p><i>{art["author"]}</i></p></div>', unsafe_allow_html=True)
        if art["image"]: st.image(art["image"], use_column_width=True)
        st.info(f"**Analyse :** {art['analysis']}")
        data_today.append(art)

        # Bloc Philo
        philo = app.get_philosophy()
        st.markdown(f'<div class="culture-card"><h3>🧠 Philo : {philo["title"]}</h3><p><i>{philo["author"]}</i></p></div>', unsafe_allow_html=True)
        st.info(f"**Analyse :** {philo['analysis']}")
        data_today.append(philo)

    with col2:
        # Bloc Poésie
        poem = app.get_poem()
        st.markdown(f'<div class="culture-card"><h3>📜 Poésie : {poem["title"]}</h3><p><i>{poem["author"]}</i></p></div>', unsafe_allow_html=True)
        st.text(poem["content"])
        st.info(f"**Analyse :** {poem['analysis']}")
        data_today.append(poem)

        # Bloc Cinéma
        cine = app.get_cinema()
        st.markdown(f'<div class="culture-card"><h3>🎬 Cinéma : {cine["title"]}</h3><p><i>{cine["author"]} ({cine["year"]})</i></p></div>', unsafe_allow_html=True)
        st.info(f"**Analyse :** {cine['analysis']}")
        data_today.append(cine)

    if st.button("Enregistrer cette journée dans l'historique"):
        app.save_to_history(data_today)
        st.success("Journée sauvegardée !")

with tabs[1]:
    st.header("Vos découvertes passées")
    if app.history_file.exists():
        with open(app.history_file, 'r') as f:
            hist_data = json.load(f)
            for day in reversed(hist_data):
                with st.expander(f"📅 Journée du {day['date']}"):
                    for item in day['content']:
                        st.write(f"**{item['type']}** : {item['title']} ({item['author']})")
    else:
        st.write("Aucun historique pour le moment.")

with tabs[2]:
    st.header("Configuration")
    st.write("L'application utilise le hachage de la date actuelle comme `random.seed` pour garantir que vous voyez le même contenu toute la journée.")
    if st.button("Effacer l'historique"):
        if app.history_file.exists(): app.history_file.unlink()
        st.rerun()
