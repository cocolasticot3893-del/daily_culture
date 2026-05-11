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

# CSS allégé (On laisse Streamlit gérer le responsive mobile nativement)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=Source+Sans+Pro:wght@300;400;600&display=swap');
    
    h1, h2, h3 { font-family: 'Playfair Display', serif; color: #1a252f; text-align: center; }
    h1 { font-size: 2.5rem; border-bottom: 2px solid #d4af37; padding-bottom: 20px; margin-bottom: 30px; }
    
    p, div, span { font-family: 'Source Sans Pro', sans-serif; font-size: 1.1rem; line-height: 1.6; }
    
    .poem-box { 
        font-family: 'Playfair Display', serif; font-size: 1.2rem; line-height: 1.8; 
        padding-left: 20px; border-left: 3px solid #d4af37; white-space: pre-wrap; 
        color: #2c3e50; margin: 20px 0; background-color: #faf9f6; padding: 15px; border-radius: 0 8px 8px 0;
    }
    
    .quote-box { 
        text-align: center; font-family: 'Playfair Display', serif; font-size: 1.4rem; 
        font-style: italic; color: #b8860b; padding: 25px; margin-bottom: 30px; 
        background: #fdfbf7; border-radius: 12px; border: 1px solid #f0ece1; 
    }
    
    img { border-radius: 8px; width: 100%; object-fit: contain; max-height: 450px; margin-bottom: 15px; }
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

@st.cache_data(show_spinner=False, ttl=86400*30)
def ask_deepseek(prompt, seed, retries=2):
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "Tu es un érudit français. Réponds UNIQUEMENT par un objet JSON pur et valide. Pas de markdown, pas d'introduction. Assure-toi de fournir des analyses très détaillées."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }
    
    for i in range(retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=40)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return extract_json(content)
        except Exception as e:
            time.sleep(2)
            if i == retries - 1: return {"erreur": True, "details": str(e)}

# --- FONCTIONS DE CONTENU (Analyses longues & Liens Wiki exacts) ---
@st.cache_data(show_spinner=False, ttl=86400*30)
def get_quote(seed): return ask_deepseek(f"Graine {seed}. Citation inspirante courte. JSON: {{'citation': '...', 'auteur': '...'}}", seed)

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_art(seed):
    random.seed(seed)
    ids = [436535, 436528, 436532, 435882, 435809, 436533, 436529, 437112, 436121, 459123, 436101, 436534]
    try:
        r = requests.get(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{random.choice(ids)}", timeout=10)
        art = r.json()
        ds = ask_deepseek(f"Analyse approfondie et détaillée (8 à 10 phrases) de '{art.get('title')}' par {art.get('artistDisplayName')}. JSON: {{'titre_fr': '...', 'analyse': '...', 'lien_wiki': 'URL exacte Wikipédia de l\'artiste si possible'}}", seed)
        return {"title": ds.get('titre_fr', art.get('title')), "author": art.get('artistDisplayName', 'Inconnu'), "image": art.get('primaryImageSmall'), "analyse": ds.get('analyse', 'Erreur.'), "link_api": art.get('objectURL'), "lien_wiki": ds.get('lien_wiki')}
    except: return {"erreur": True}

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_poem(seed): return ask_deepseek(f"Graine {seed}. Beau poème français. JSON: {{'titre': '...', 'auteur': '...', 'poeme_entier': 'Texte avec \\n', 'analyse': 'Analyse littéraire approfondie (8 à 10 phrases)', 'lien_wiki': 'URL exacte de la page Wikipédia de l\'auteur'}}", seed+1)

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_song(seed): return ask_deepseek(f"Graine {seed}. Chanson culte internationale ou française. JSON: {{'titre': '...', 'artiste': '...', 'annee': '...', 'analyse': 'Analyse musicale et historique approfondie (8 à 10 phrases)'}}", seed+2)

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_movie(seed): return ask_deepseek(f"Graine {seed}. Chef-d'œuvre du cinéma. JSON: {{'titre': '...', 'realisateur': '...', 'annee': '...', 'analyse': 'Analyse cinématographique approfondie (8 à 10 phrases)', 'lien_wiki': 'URL exacte Wikipédia du film ou réalisateur'}}", seed+3)

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_philo(seed): return ask_deepseek(f"Graine {seed}. Concept philosophique majeur. JSON: {{'concept': '...', 'philosophe': '...', 'analyse': 'Explication détaillée et application moderne (8 à 10 phrases)', 'lien_wiki': 'URL exacte Wikipédia du concept'}}", seed+4)

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_arch(seed): return ask_deepseek(f"Graine {seed}. Monument ou courant architectural. JSON: {{'titre': '...', 'lieu': '...', 'analyse': 'Analyse architecturale et historique (8 à 10 phrases)', 'lien_wiki': 'URL exacte Wikipédia'}}", seed+5)

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_myth(seed): return ask_deepseek(f"Graine {seed}. Mythe, légende ou divinité. JSON: {{'titre': '...', 'origine': '...', 'analyse': 'Récit détaillé et symbolique (8 à 10 phrases)', 'lien_wiki': 'URL exacte Wikipédia'}}", seed+6)

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_sci(seed): return ask_deepseek(f"Graine {seed}. Découverte ou invention scientifique. JSON: {{'titre': '...', 'inventeur': '...', 'analyse': 'Explication scientifique détaillée et impact (8 à 10 phrases)', 'lien_wiki': 'URL exacte Wikipédia'}}", seed+7)

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_gastro(seed): return ask_deepseek(f"Graine {seed}. Plat emblématique ou ingrédient. JSON: {{'titre': '...', 'origine': '...', 'analyse': 'Histoire culinaire détaillée (8 à 10 phrases)', 'lien_wiki': 'URL exacte Wikipédia'}}", seed+8)


# --- GÉNÉRATEUR D'EXPORT OFFLINE ---
def generate_offline_html(date_str, quote, art, poem, song, movie, philo, arch, myth, sci, gastro):
    def make_card(title, author, content, analysis):
        if not title: return ""
        return f"""
        <div class="card">
            <h2>{title}</h2>
            <div class="author">{author}</div>
            {f'<div class="poem">{content}</div>' if content else ''}
            <div class="analysis">{analysis}</div>
        </div>"""

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
        
        {f'<div class="card"><h2>🖼️ {art.get("title", "")}</h2><div class="author">{art.get("author", "")}</div><img src="{art.get("image", "")}" alt="Oeuvre"><div class="analysis">{art.get("analyse", "")}</div></div>' if not art.get("erreur") else ''}
        {make_card('🏛️ Architecture: ' + arch.get('titre', ''), arch.get('lieu', ''), None, arch.get('analyse', '')) if not arch.get("erreur") else ''}
        {make_card('📜 ' + poem.get('titre', ''), poem.get('auteur', ''), poem.get('poeme_entier', ''), poem.get('analyse', '')) if not poem.get("erreur") else ''}
        {make_card('⚡ ' + myth.get('titre', ''), myth.get('origine', ''), None, myth.get('analyse', '')) if not myth.get("erreur") else ''}
        {make_card('🧠 ' + philo.get('concept', ''), philo.get('philosophe', ''), None, philo.get('analyse', '')) if not philo.get("erreur") else ''}
        {make_card('🌍 Science: ' + sci.get('titre', ''), sci.get('inventeur', ''), None, sci.get('analyse', '')) if not sci.get("erreur") else ''}
        {make_card('🎵 ' + song.get('titre', ''), f"{song.get('artiste', '')} ({song.get('annee', '')})", None, song.get('analyse', '')) if not song.get("erreur") else ''}
        {make_card('🍷 Gastronomie: ' + gastro.get('titre', ''), gastro.get('origine', ''), None, gastro.get('analyse', '')) if not gastro.get("erreur") else ''}
        {make_card('🎬 ' + movie.get('titre', ''), f"{movie.get('realisateur', '')} ({movie.get('annee', '')})", None, movie.get('analyse', '')) if not movie.get("erreur") else ''}
    </body>
    </html>
    """
    return html_content

# --- RENDU DE L'EXPOSITION (Optimisé pour Mobile) ---
def display_exposition(target_date):
    date_str = target_date.strftime("%Y-%m-%d")
    seed = int(hashlib.md5(date_str.encode()).hexdigest(), 16) % (10**8)
    
    st.markdown(f"<p style='text-align: center; color: #7f8c8d; margin-bottom: 20px;'>Édition du {target_date.strftime('%d/%m/%Y')}</p>", unsafe_allow_html=True)

    with st.spinner("Rédaction des analyses approfondies par votre curateur..."):
        quote_data = get_quote(seed)
        art_data = get_art(seed)
        arch_data = get_arch(seed)
        poem_data = get_poem(seed)
        myth_data = get_myth(seed)
        philo_data = get_philo(seed)
        sci_data = get_sci(seed)
        song_data = get_song(seed)
        gastro_data = get_gastro(seed)
        movie_data = get_movie(seed)

    # Bouton d'export global
    html_export = generate_offline_html(target_date.strftime('%d/%m/%Y'), quote_data, art_data, poem_data, song_data, movie_data, philo_data, arch_data, myth_data, sci_data, gastro_data)
    st.download_button(label="📥 Sauvegarder pour lecture hors-ligne", data=html_export, file_name=f"Eveil_Culturel_{date_str}.html", mime="text/html", use_container_width=True)
    st.write("---")

    # HELPER D'AFFICHAGE NATIVE STREAMLIT (Mobile Friendly)
    def render_native_card(icon, cat, title, sub, content, analysis, url, link_txt):
        with st.container(border=True):
            st.subheader(f"{icon} {title}")
            st.markdown(f"*{sub}*")
            
            if content: 
                st.markdown(f'<div class="poem-box">{content}</div>', unsafe_allow_html=True)
            
            st.write(analysis)
            
            st.write("") # Espace
            c1, c2 = st.columns(2)
            with c1:
                if st.button("👍 J'aime", key=f"l_{cat}_{date_str}", use_container_width=True): save_pref(cat, title, sub, True, date_str)
            with c2:
                if st.button("👎 Bof", key=f"d_{cat}_{date_str}", use_container_width=True): save_pref(cat, title, sub, False, date_str)
            
            if url: 
                st.link_button(link_txt, url, use_container_width=True)

    def fallback_wiki(query):
        return f"https://fr.wikipedia.org/wiki/Spécial:Recherche?search={urllib.parse.quote(query)}"

    # 1. CITATION
    if not quote_data.get("erreur"): st.markdown(f"<div class='quote-box'>« {quote_data.get('citation', '')} »<br><span style='font-size:1rem; color:#7f8c8d;'>— {quote_data.get('auteur', '')}</span></div>", unsafe_allow_html=True)

    # 2. ARTS VISUELS (Peinture + Architecture)
    if not art_data.get("erreur"):
        with st.container(border=True):
            st.subheader(f"🖼️ {art_data['title']}")
            st.markdown(f"*{art_data['author']}*")
            if art_data.get("image"): st.image(art_data["image"])
            st.write(art_data["analyse"])
            
            st.write("")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("👍 J'aime", key=f"l_art_{date_str}", use_container_width=True): save_pref("Art", art_data["title"], art_data["author"], True, date_str)
            with c2:
                if st.button("👎 Bof", key=f"d_art_{date_str}", use_container_width=True): save_pref("Art", art_data["title"], art_data["author"], False, date_str)
            
            url_wiki = art_data.get("lien_wiki") or fallback_wiki(art_data['author'])
            st.link_button("📖 Découvrir l'artiste (Wikipédia)", url_wiki, use_container_width=True)
            if art_data.get("link_api"): st.link_button("🔍 Voir l'œuvre au MET", art_data["link_api"], use_container_width=True)

    if not arch_data.get("erreur"): render_native_card("🏛️", "Architecture", arch_data.get("titre", ""), arch_data.get("lieu", ""), None, arch_data.get("analyse", ""), arch_data.get("lien_wiki") or fallback_wiki(arch_data.get('titre', '')), "🏛️ Explorer le monument (Wikipédia)")

    # 3. LETTRES & PENSÉES (Poésie + Mythologie + Philo)
    if not poem_data.get("erreur"): render_native_card("📜", "Poésie", poem_data.get("titre", ""), poem_data.get("auteur", ""), poem_data.get("poeme_entier", ""), poem_data.get("analyse", ""), poem_data.get("lien_wiki") or fallback_wiki(poem_data.get('auteur', '')), "📖 Découvrir l'auteur (Wikipédia)")
    if not myth_data.get("erreur"): render_native_card("⚡", "Mythologie", myth_data.get("titre", ""), myth_data.get("origine", ""), None, myth_data.get("analyse", ""), myth_data.get("lien_wiki") or fallback_wiki(myth_data.get('titre', '')), "⚡ Découvrir le mythe (Wikipédia)")
    if not philo_data.get("erreur"): render_native_card("🧠", "Philosophie", philo_data.get("concept", ""), philo_data.get("philosophe", ""), None, philo_data.get("analyse", ""), philo_data.get("lien_wiki") or fallback_wiki(philo_data.get('concept', '')), "📚 Approfondir (Wikipédia)")

    # 4. MONDE & DÉCOUVERTES (Science + Gastronomie)
    if not sci_data.get("erreur"): render_native_card("🌍", "Science", sci_data.get("titre", ""), sci_data.get("inventeur", ""), None, sci_data.get("analyse", ""), sci_data.get("lien_wiki") or fallback_wiki(sci_data.get('titre', '')), "🌍 Comprendre l'invention (Wikipédia)")
    if not gastro_data.get("erreur"): render_native_card("🍷", "Gastronomie", gastro_data.get("titre", ""), gastro_data.get("origine", ""), None, gastro_data.get("analyse", ""), gastro_data.get("lien_wiki") or fallback_wiki(gastro_data.get('titre', '')), "🍷 L'histoire du plat (Wikipédia)")

    # 5. DIVERTISSEMENTS CULTES (Musique + Cinéma)
    if not song_data.get("erreur"): 
        yt_url = f"https://music.youtube.com/search?q={urllib.parse.quote(song_data.get('artiste', '') + ' ' + song_data.get('titre', ''))}"
        render_native_card("🎵", "Musique", song_data.get("titre", ""), f"{song_data.get('artiste', '')} ({song_data.get('annee', '')})", None, song_data.get("analyse", ""), yt_url, "🎧 Écouter (YouTube Music)")
    
    if not movie_data.get("erreur"): render_native_card("🎬", "Cinéma", movie_data.get("titre", ""), f"{movie_data.get('realisateur', '')} ({movie_data.get('annee', '')})", None, movie_data.get("analyse", ""), movie_data.get("lien_wiki") or fallback_wiki(movie_data.get('titre', '')), "🎞️ Fiche du film (Wikipédia)")

# --- ONGLETS PRINCIPAUX ---
st.title("L'Éveil Culturel")

tab_today, tab_archive, tab_fav = st.tabs(["✨ Aujourd'hui", "📅 Archives", "⭐ Favoris"])

with tab_today: display_exposition(datetime.date.today())

with tab_archive:
    st.markdown("### Voyager dans le temps")
    st.info("Sélectionnez une date passée pour recréer l'exposition de ce jour-là.")
    selected_date = st.date_input("Choisir une date :", value=datetime.date.today() - datetime.timedelta(days=1), max_value=datetime.date.today())
    if selected_date != datetime.date.today():
        st.write("---")
        display_exposition(selected_date)
    else: st.warning("Pour voir l'exposition d'aujourd'hui, utilisez l'onglet '✨ Aujourd'hui'.")

with tab_fav:
    st.header("⭐ Votre collection")
    prefs = load_prefs()
    liked_items = [p for p in prefs if p.get("liked") == True]
    if not liked_items: st.info("Aucun favori pour l'instant.")
    else:
        liked_items.sort(key=lambda x: x["date"], reverse=True)
        for item in liked_items: st.markdown(f"**{item['category']}** : {item['title']} *(par {item['author']})* - `Sauvegardé le {item['date']}`")
