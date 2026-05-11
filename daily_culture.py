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
import base64

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

# --- FONCTION BLINDÉE POUR L'API DEEPSEEK ---
def extract_json(text):
    try:
        match = re.search(r'\{.*\}', text.strip(), re.DOTALL)
        if match: return json.loads(match.group(0))
        return json.loads(text)
    except Exception as e:
        raise ValueError(f"Impossible de parser le JSON: {str(e)}")

@st.cache_data(show_spinner=False, ttl=86400*30) # Cache de 30 jours pour les archives !
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
            time.sleep(2)
            if i == retries - 1: return {"erreur": True, "details": str(e)}

# --- FONCTIONS DE CONTENU ---
@st.cache_data(show_spinner=False, ttl=86400*30)
def get_quote(seed):
    return ask_deepseek(f"Graine {seed}. Donne une citation inspirante et très courte. JSON: {{'citation': '...', 'auteur': '...'}}", seed)

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_art(seed):
    random.seed(seed)
    ids = [436535, 436528, 436532, 435882, 435809, 436533, 436529, 437112, 436121, 459123, 436101, 436534]
    obj_id = random.choice(ids)
    try:
        r = requests.get(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{obj_id}", timeout=10)
        r.raise_for_status()
        art = r.json()
        ds = ask_deepseek(f"Analyse passionnante (4 phrases) du tableau '{art.get('title')}' de {art.get('artistDisplayName')}. JSON: {{'titre_fr': '...', 'analyse': '...'}}", seed)
        return {
            "title": ds.get('titre_fr', art.get('title', 'Inconnu')),
            "author": art.get('artistDisplayName', 'Inconnu'),
            "image": art.get('primaryImageSmall'),
            "analyse": ds.get('analyse', 'Analyse non disponible.'),
            "link": art.get('objectURL', '')
        }
    except Exception as e: return {"erreur": True, "details": str(e)}

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_poem(seed): return ask_deepseek(f"Graine {seed}. Choisis un poème français. JSON: {{'titre': '...', 'auteur': '...', 'poeme_entier': 'Texte avec \\n', 'analyse': '4 phrases'}}", seed)

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_song(seed): return ask_deepseek(f"Graine {seed}. Choisis une chanson internationale culte. JSON: {{'titre': '...', 'artiste': '...', 'annee': '...', 'analyse': '4 phrases'}}", seed)

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_movie(seed): return ask_deepseek(f"Graine {seed}. Choisis un grand film. JSON: {{'titre': '...', 'realisateur': '...', 'annee': '...', 'analyse': '4 phrases'}}", seed)

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_philo(seed): return ask_deepseek(f"Graine {seed}. Concept philosophique. JSON: {{'concept': '...', 'philosophe': '...', 'analyse': '4 phrases'}}", seed)

# --- GÉNÉRATEUR D'EXPORT OFFLINE ---
def generate_offline_html(date_str, quote, art, poem, song, movie, philo):
    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>L'Éveil Culturel - {date_str}</title>
        <style>
            body {{ font-family: 'Georgia', serif; background-color: #fcfbf9; color: #2c3e50; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }}
            h1 {{ text-align: center; border-bottom: 2px solid #d4af37; padding-bottom: 10px; }}
            .quote {{ text-align: center; font-style: italic; font-size: 1.2em; color: #b8860b; margin: 30px 0; }}
            .card {{ background: white; padding: 20px; border-radius: 8px; border-left: 4px solid #d4af37; margin-bottom: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
            h2 {{ margin-top: 0; color: #1a252f; }}
            .author {{ color: #7f8c8d; font-style: italic; border-bottom: 1px solid #eee; padding-bottom: 10px; margin-bottom: 15px; }}
            .poem {{ white-space: pre-wrap; font-size: 1.1em; border-left: 2px solid #eee; padding-left: 15px; }}
            .analysis {{ background: #f9f9f9; padding: 15px; border-radius: 5px; margin-top: 15px; }}
            img {{ max-width: 100%; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <h1>🏛️ L'Éveil Culturel</h1>
        <p style="text-align: center;">Édition du {date_str}</p>
        
        <div class="quote">« {quote.get('citation', '')} »<br><small>— {quote.get('auteur', '')}</small></div>
        
        <div class="card">
            <h2>🖼️ {art.get('title', '')}</h2>
            <div class="author">{art.get('author', '')}</div>
            {f'<img src="{art["image"]}" alt="Oeuvre">' if art.get("image") else ''}
            <div class="analysis">{art.get('analyse', '')}</div>
        </div>

        <div class="card">
            <h2>📜 {poem.get('titre', '')}</h2>
            <div class="author">{poem.get('auteur', '')}</div>
            <div class="poem">{poem.get('poeme_entier', '')}</div>
            <div class="analysis">{poem.get('analyse', '')}</div>
        </div>

        <div class="card">
            <h2>🧠 {philo.get('concept', '')}</h2>
            <div class="author">{philo.get('philosophe', '')}</div>
            <div class="analysis">{philo.get('analyse', '')}</div>
        </div>
        
        <div class="card">
            <h2>🎵 {song.get('titre', '')}</h2>
            <div class="author">{song.get('artiste', '')} ({song.get('annee', '')})</div>
            <div class="analysis">{song.get('analyse', '')}</div>
        </div>

        <div class="card">
            <h2>🎬 {movie.get('titre', '')}</h2>
            <div class="author">{movie.get('realisateur', '')} ({movie.get('annee', '')})</div>
            <div class="analysis">{movie.get('analyse', '')}</div>
        </div>
        <p style="text-align:center; color:#bdc3c7; margin-top:50px;">Généré par DeepSeek & Streamlit</p>
    </body>
    </html>
    """
    return html_content

# --- RENDU DE L'EXPOSITION ---
def display_exposition(target_date):
    date_str = target_date.strftime("%Y-%m-%d")
    seed = int(hashlib.md5(date_str.encode()).hexdigest(), 16) % (10**8)
    
    st.markdown(f"<p style='text-align: center; color: #7f8c8d; margin-bottom: 20px;'>Édition du {target_date.strftime('%d/%m/%Y')}</p>", unsafe_allow_html=True)

    with st.spinner("Le curateur assemble l'exposition (Instantané si déjà en cache)..."):
        quote_data = get_quote(seed)
        art_data = get_art(seed)
        poem_data = get_poem(seed)
        song_data = get_song(seed)
        movie_data = get_movie(seed)
        philo_data = get_philo(seed)

    # Bouton d'export
    html_export = generate_offline_html(target_date.strftime('%d/%m/%Y'), quote_data, art_data, poem_data, song_data, movie_data, philo_data)
    st.download_button(
        label="📥 Sauvegarder pour lecture hors-ligne (HTML/PDF)",
        data=html_export,
        file_name=f"Eveil_Culturel_{date_str}.html",
        mime="text/html",
        use_container_width=True
    )
    st.write("---")

    # Affichage des contenus (comme avant)
    if not quote_data.get("erreur"):
        st.markdown(f"<div class='quote-box'>« {quote_data.get('citation', '')} »<br><span style='font-size:1rem; color:#7f8c8d;'>— {quote_data.get('auteur', '')}</span></div>", unsafe_allow_html=True)

    if not art_data.get("erreur"):
        st.markdown(f'<div class="culture-card"><div class="card-title">🖼️ {art_data["title"]}</div><div class="card-subtitle">{art_data["author"]}</div>', unsafe_allow_html=True)
        if art_data.get("image"): st.image(art_data["image"])
        st.markdown(f'<div class="analysis-box">{art_data["analyse"]}</div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 1, 4])
        with c1:
            if st.button("👍", key=f"l_art_{date_str}"): save_pref("Art", art_data["title"], art_data["author"], True, date_str)
        with c2:
            if st.button("👎", key=f"d_art_{date_str}"): save_pref("Art", art_data["title"], art_data["author"], False, date_str)
        with c3:
            if art_data.get("link"): st.markdown(f'<a href="{art_data["link"]}" target="_blank" class="deep-link">🔍 Voir en HD sur le site du MET</a>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    def render_card(icon, cat, title, sub, content, analysis, url, link_txt):
        st.markdown(f'<div class="culture-card"><div class="card-title">{icon} {title}</div><div class="card-subtitle">{sub}</div>', unsafe_allow_html=True)
        if content: st.markdown(f'<div class="poem-box">{content}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="analysis-box">{analysis}</div><br>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 1, 4])
        with c1:
            if st.button("👍", key=f"l_{cat}_{date_str}"): save_pref(cat, title, sub, True, date_str)
        with c2:
            if st.button("👎", key=f"d_{cat}_{date_str}"): save_pref(cat, title, sub, False, date_str)
        with c3:
            if url: st.markdown(f'<a href="{url}" target="_blank" class="deep-link">{link_txt}</a>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    if not poem_data.get("erreur"): render_card("📜", "Poésie", poem_data.get("titre", ""), poem_data.get("auteur", ""), poem_data.get("poeme_entier", ""), poem_data.get("analyse", ""), f"https://fr.wikipedia.org/wiki/Spécial:Recherche?search={urllib.parse.quote(poem_data.get('auteur', ''))}", "📖 Découvrir l'auteur")
    if not song_data.get("erreur"): render_card("🎵", "Musique", song_data.get("titre", ""), f"{song_data.get('artiste', '')} ({song_data.get('annee', '')})", None, song_data.get("analyse", ""), f"https://music.youtube.com/search?q={urllib.parse.quote(song_data.get('artiste', '') + ' ' + song_data.get('titre', ''))}", "🎧 Écouter")
    if not movie_data.get("erreur"): render_card("🎬", "Cinéma", movie_data.get("titre", ""), f"{movie_data.get('realisateur', '')} ({movie_data.get('annee', '')})", None, movie_data.get("analyse", ""), f"https://fr.wikipedia.org/wiki/Spécial:Recherche?search={urllib.parse.quote(movie_data.get('titre', '') + ' film')}", "🎞️ Fiche du film")
    if not philo_data.get("erreur"): render_card("🧠", "Philosophie", philo_data.get("concept", ""), philo_data.get("philosophe", ""), None, philo_data.get("analyse", ""), f"https://fr.wikipedia.org/wiki/Spécial:Recherche?search={urllib.parse.quote(philo_data.get('concept', ''))}", "📚 Approfondir")


# --- APPLICATION PRINCIPALE ---
st.title("L'Éveil Culturel")

tab_today, tab_archive, tab_fav = st.tabs(["✨ Aujourd'hui", "📅 Archives", "⭐ Favoris"])

with tab_today:
    display_exposition(datetime.date.today())

with tab_archive:
    st.markdown("### Voyager dans le temps")
    st.info("Sélectionnez une date passée. L'intelligence artificielle recréera exactement l'exposition qui a été (ou aurait été) générée ce jour-là.")
    selected_date = st.date_input("Choisir une date :", value=datetime.date.today() - datetime.timedelta(days=1), max_value=datetime.date.today())
    
    if selected_date != datetime.date.today():
        st.write("---")
        display_exposition(selected_date)
    else:
        st.warning("Pour voir l'exposition d'aujourd'hui, utilisez l'onglet '✨ Aujourd'hui'.")

with tab_fav:
    st.header("⭐ Votre collection")
    prefs = load_prefs()
    liked_items = [p for p in prefs if p.get("liked") == True]
    
    if not liked_items:
        st.info("Aucun favori pour l'instant.")
    else:
        liked_items.sort(key=lambda x: x["date"], reverse=True)
        for item in liked_items:
            st.markdown(f"**{item['category']}** : {item['title']} *(par {item['author']})* - `Sauvegardé le {item['date']}`")
