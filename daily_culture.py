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

# CSS allégé et Typographie Premium
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&family=Source+Sans+Pro:wght@300;400;600&display=swap');
    
    h1, h2, h3 { font-family: 'Playfair Display', serif; color: #1a252f; text-align: center; }
    h1 { font-size: 2.8rem; border-bottom: 2px solid #d4af37; padding-bottom: 20px; margin-bottom: 30px; }
    
    p, div, span { font-family: 'Source Sans Pro', sans-serif; font-size: 1.15rem; line-height: 1.7; }
    
    .poem-box { 
        font-family: 'Playfair Display', serif; font-size: 1.25rem; line-height: 1.9; 
        padding-left: 20px; border-left: 3px solid #d4af37; white-space: pre-wrap; 
        color: #2c3e50; margin: 20px 0; background-color: #faf9f6; padding: 25px; border-radius: 0 8px 8px 0;
    }
    
    .quote-box { 
        text-align: center; font-family: 'Playfair Display', serif; font-size: 1.5rem; 
        font-style: italic; color: #b8860b; padding: 30px; margin-bottom: 40px; 
        background: #fdfbf7; border-radius: 12px; border: 1px solid #f0ece1; 
        box-shadow: 0 4px 15px rgba(0,0,0,0.03);
    }
    
    /* On force les images Streamlit à avoir des bords arrondis élégants */
    [data-testid="stImage"] img { border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); margin-bottom: 20px; }
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

# --- FONCTIONS HELPERS (API Wikipédia & JSON) ---
def extract_json(text):
    try:
        match = re.search(r'\{.*\}', text.strip(), re.DOTALL)
        if match: return json.loads(match.group(0))
        return json.loads(text)
    except Exception as e:
        raise ValueError(f"Impossible de parser le JSON: {str(e)}")

def get_wiki_image(query):
    """Cherche l'image principale d'un sujet sur Wikipédia via l'API publique."""
    if not query: return None
    try:
        # 1. Trouver le titre exact de la page
        search_url = f"https://fr.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&utf8=&format=json&srlimit=1"
        res = requests.get(search_url, timeout=5).json()
        if not res.get('query', {}).get('search'): return None
        page_title = res['query']['search'][0]['title']
        
        # 2. Récupérer l'URL de l'image (thumbnail grand format)
        img_url = f"https://fr.wikipedia.org/w/api.php?action=query&titles={urllib.parse.quote(page_title)}&prop=pageimages&format=json&pithumbsize=800"
        res2 = requests.get(img_url, timeout=5).json()
        pages = res2.get('query', {}).get('pages', {})
        for page_id in pages:
            if 'thumbnail' in pages[page_id]:
                return pages[page_id]['thumbnail']['source']
    except: pass
    return None

@st.cache_data(show_spinner=False, ttl=86400*30)
def ask_deepseek(prompt, seed, retries=2):
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "Tu es un érudit français. Réponds UNIQUEMENT par un objet JSON pur. Fais des analyses passionnantes et très détaillées (8 à 10 phrases)."},
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

# --- FONCTIONS DE CONTENU ---
@st.cache_data(show_spinner=False, ttl=86400*30)
def get_quote(seed): return ask_deepseek(f"Graine {seed}. Citation inspirante courte. JSON: {{'citation': '...', 'auteur': '...'}}", seed)

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_art(seed):
    random.seed(seed)
    ids = [436535, 436528, 436532, 435882, 435809, 436533, 436529, 437112, 436121, 459123, 436101, 436534]
    try:
        r = requests.get(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{random.choice(ids)}", timeout=10)
        art = r.json()
        ds = ask_deepseek(f"Analyse approfondie (8 à 10 phrases) de '{art.get('title')}' par {art.get('artistDisplayName')}. JSON: {{'titre_fr': '...', 'analyse': '...', 'lien_wiki': 'URL exacte Wikipédia artiste'}}", seed)
        return {"titre": ds.get('titre_fr', art.get('title')), "auteur": art.get('artistDisplayName', 'Inconnu'), "image": art.get('primaryImageSmall'), "analyse": ds.get('analyse', 'Erreur.'), "lien_wiki": ds.get('lien_wiki') or art.get('objectURL')}
    except: return {"erreur": True}

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_poem(seed): 
    res = ask_deepseek(f"Graine {seed}. Poème français. JSON: {{'titre': '...', 'auteur': '...', 'poeme_entier': 'Texte avec \\n', 'analyse': 'Analyse approfondie (8 à 10 phrases)', 'lien_wiki': 'URL Wikipédia auteur'}}", seed+1)
    if not res.get("erreur"): res["image"] = get_wiki_image(res.get("auteur"))
    return res

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_song(seed): 
    res = ask_deepseek(f"Graine {seed}. Chanson culte. JSON: {{'titre': '...', 'artiste': '...', 'annee': '...', 'analyse': 'Analyse approfondie (8 à 10 phrases)'}}", seed+2)
    if not res.get("erreur"): res["image"] = get_wiki_image(f"{res.get('artiste')} groupe chanteur")
    return res

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_movie(seed): 
    res = ask_deepseek(f"Graine {seed}. Chef-d'œuvre cinéma. JSON: {{'titre': '...', 'realisateur': '...', 'annee': '...', 'analyse': 'Analyse approfondie (8 à 10 phrases)', 'lien_wiki': 'URL Wikipédia'}}", seed+3)
    if not res.get("erreur"): res["image"] = get_wiki_image(f"{res.get('titre')} film {res.get('realisateur')}")
    return res

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_philo(seed): 
    res = ask_deepseek(f"Graine {seed}. Concept philosophique. JSON: {{'concept': '...', 'philosophe': '...', 'analyse': 'Explication détaillée (8 à 10 phrases)', 'lien_wiki': 'URL Wikipédia'}}", seed+4)
    if not res.get("erreur"): res["image"] = get_wiki_image(res.get("philosophe"))
    return res

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_arch(seed): 
    res = ask_deepseek(f"Graine {seed}. Monument ou courant architectural. JSON: {{'titre': '...', 'lieu': '...', 'analyse': 'Analyse détaillée (8 à 10 phrases)', 'lien_wiki': 'URL Wikipédia'}}", seed+5)
    if not res.get("erreur"): res["image"] = get_wiki_image(res.get("titre"))
    return res

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_myth(seed): 
    res = ask_deepseek(f"Graine {seed}. Mythe ou divinité. JSON: {{'titre': '...', 'origine': '...', 'analyse': 'Récit détaillé (8 à 10 phrases)', 'lien_wiki': 'URL Wikipédia'}}", seed+6)
    if not res.get("erreur"): res["image"] = get_wiki_image(res.get("titre"))
    return res

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_sci(seed): 
    res = ask_deepseek(f"Graine {seed}. Invention scientifique. JSON: {{'titre': '...', 'inventeur': '...', 'analyse': 'Explication détaillée (8 à 10 phrases)', 'lien_wiki': 'URL Wikipédia'}}", seed+7)
    if not res.get("erreur"): res["image"] = get_wiki_image(res.get("inventeur") or res.get("titre"))
    return res

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_gastro(seed): 
    res = ask_deepseek(f"Graine {seed}. Plat ou ingrédient. JSON: {{'titre': '...', 'origine': '...', 'analyse': 'Histoire détaillée (8 à 10 phrases)', 'lien_wiki': 'URL Wikipédia'}}", seed+8)
    if not res.get("erreur"): res["image"] = get_wiki_image(res.get("titre") + " plat gastronomie")
    return res

# --- GÉNÉRATEUR D'EXPORT OFFLINE ---
def generate_offline_html(date_str, quote, art, poem, song, movie, philo, arch, myth, sci, gastro):
    def make_card(title, author, content, analysis, img_url):
        if not title: return ""
        return f"""
        <div class="card">
            <h2>{title}</h2>
            <div class="author">{author}</div>
            {f'<img src="{img_url}" alt="Illustration">' if img_url else ''}
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
            h2 {{ margin-top: 0; color: #1a252f; text-align: center; }}
            .author {{ color: #7f8c8d; font-style: italic; text-align: center; margin-bottom: 20px; font-size: 1.1em; }}
            .poem {{ white-space: pre-wrap; font-size: 1.1em; border-left: 2px solid #eee; padding-left: 15px; margin-bottom: 20px; }}
            img {{ width: 100%; border-radius: 8px; margin-bottom: 20px; max-height: 400px; object-fit: cover; }}
        </style>
    </head>
    <body>
        <h1>🏛️ L'Éveil Culturel</h1>
        <p style="text-align: center;">Édition du {date_str}</p>
        <div class="quote">« {quote.get('citation', '')} »<br><small>— {quote.get('auteur', '')}</small></div>
        
        {make_card('🖼️ ' + art.get('titre', ''), art.get('auteur', ''), None, art.get('analyse', ''), art.get('image')) if not art.get("erreur") else ''}
        {make_card('🏛️ ' + arch.get('titre', ''), arch.get('lieu', ''), None, arch.get('analyse', ''), arch.get('image')) if not arch.get("erreur") else ''}
        {make_card('📜 ' + poem.get('titre', ''), poem.get('auteur', ''), poem.get('poeme_entier', ''), poem.get('analyse', ''), poem.get('image')) if not poem.get("erreur") else ''}
        {make_card('⚡ ' + myth.get('titre', ''), myth.get('origine', ''), None, myth.get('analyse', ''), myth.get('image')) if not myth.get("erreur") else ''}
        {make_card('🧠 ' + philo.get('concept', ''), philo.get('philosophe', ''), None, philo.get('analyse', ''), philo.get('image')) if not philo.get("erreur") else ''}
        {make_card('🌍 ' + sci.get('titre', ''), sci.get('inventeur', ''), None, sci.get('analyse', ''), sci.get('image')) if not sci.get("erreur") else ''}
        {make_card('🎵 ' + song.get('titre', ''), f"{song.get('artiste', '')} ({song.get('annee', '')})", None, song.get('analyse', ''), song.get('image')) if not song.get("erreur") else ''}
        {make_card('🍷 ' + gastro.get('titre', ''), gastro.get('origine', ''), None, gastro.get('analyse', ''), gastro.get('image')) if not gastro.get("erreur") else ''}
        {make_card('🎬 ' + movie.get('titre', ''), f"{movie.get('realisateur', '')} ({movie.get('annee', '')})", None, movie.get('analyse', ''), movie.get('image')) if not movie.get("erreur") else ''}
    </body>
    </html>
    """
    return html_content

# --- RENDU DE L'EXPOSITION (Optimisé pour Mobile) ---
def display_exposition(target_date):
    date_str = target_date.strftime("%Y-%m-%d")
    seed = int(hashlib.md5(date_str.encode()).hexdigest(), 16) % (10**8)
    
    st.markdown(f"<p style='text-align: center; color: #7f8c8d; margin-bottom: 30px; font-size: 1.2rem;'>Édition du {target_date.strftime('%d/%m/%Y')}</p>", unsafe_allow_html=True)

    with st.spinner("Votre curateur recherche les œuvres et illustrations..."):
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

    html_export = generate_offline_html(target_date.strftime('%d/%m/%Y'), quote_data, art_data, poem_data, song_data, movie_data, philo_data, arch_data, myth_data, sci_data, gastro_data)
    st.download_button(label="📥 Sauvegarder l'édition complète", data=html_export, file_name=f"Eveil_Culturel_{date_str}.html", mime="text/html", use_container_width=True)
    st.write("---")

    # HELPER D'AFFICHAGE NATIVE AVEC TITRES PREMIUM ET IMAGES
    def render_native_card(icon, cat, title, sub, content, analysis, image_url, url, link_txt):
        with st.container(border=True):
            # Design du titre très visuel
            st.markdown(f"""
                <div style="text-align: center; margin-bottom: 25px;">
                    <h2 style="font-family: 'Playfair Display', serif; font-size: 2rem; color: #1a252f; margin-bottom: 5px;">{icon} {title}</h2>
                    <h4 style="font-family: 'Source Sans Pro', sans-serif; font-style: italic; color: #b8860b; margin-top: 0; font-size: 1.2rem; font-weight: normal;">{sub}</h4>
                    <hr style="width: 60px; margin: 15px auto 0 auto; border: 1.5px solid #d4af37; border-radius: 2px;">
                </div>
            """, unsafe_allow_html=True)
            
            if image_url: 
                st.image(image_url, use_container_width=True)
                
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

    # AFFICHAGE DES SECTIONS
    if not quote_data.get("erreur"): st.markdown(f"<div class='quote-box'>« {quote_data.get('citation', '')} »<br><span style='font-size:1.1rem; color:#7f8c8d;'>— {quote_data.get('auteur', '')}</span></div>", unsafe_allow_html=True)

    if not art_data.get("erreur"): render_native_card("🖼️", "Art", art_data.get("titre", ""), art_data.get("auteur", ""), None, art_data.get("analyse", ""), art_data.get("image"), art_data.get("lien_wiki") or fallback_wiki(art_data.get('auteur', '')), "📖 Découvrir l'artiste")
    if not arch_data.get("erreur"): render_native_card("🏛️", "Architecture", arch_data.get("titre", ""), arch_data.get("lieu", ""), None, arch_data.get("analyse", ""), arch_data.get("image"), arch_data.get("lien_wiki") or fallback_wiki(arch_data.get('titre', '')), "🏛️ Explorer le monument")
    if not poem_data.get("erreur"): render_native_card("📜", "Poésie", poem_data.get("titre", ""), poem_data.get("auteur", ""), poem_data.get("poeme_entier", ""), poem_data.get("analyse", ""), poem_data.get("image"), poem_data.get("lien_wiki") or fallback_wiki(poem_data.get('auteur', '')), "📖 Découvrir l'auteur")
    if not myth_data.get("erreur"): render_native_card("⚡", "Mythologie", myth_data.get("titre", ""), myth_data.get("origine", ""), None, myth_data.get("analyse", ""), myth_data.get("image"), myth_data.get("lien_wiki") or fallback_wiki(myth_data.get('titre', '')), "⚡ Découvrir le mythe")
    if not philo_data.get("erreur"): render_native_card("🧠", "Philosophie", philo_data.get("concept", ""), philo_data.get("philosophe", ""), None, philo_data.get("analyse", ""), philo_data.get("image"), philo_data.get("lien_wiki") or fallback_wiki(philo_data.get('concept', '')), "📚 Approfondir le concept")
    if not sci_data.get("erreur"): render_native_card("🌍", "Science", sci_data.get("titre", ""), sci_data.get("inventeur", ""), None, sci_data.get("analyse", ""), sci_data.get("image"), sci_data.get("lien_wiki") or fallback_wiki(sci_data.get('titre', '')), "🌍 Comprendre l'invention")
    
    if not song_data.get("erreur"): 
        yt_url = f"https://music.youtube.com/search?q={urllib.parse.quote(song_data.get('artiste', '') + ' ' + song_data.get('titre', ''))}"
        render_native_card("🎵", "Musique", song_data.get("titre", ""), f"{song_data.get('artiste', '')} ({song_data.get('annee', '')})", None, song_data.get("analyse", ""), song_data.get("image"), yt_url, "🎧 Écouter (YouTube Music)")
    
    if not gastro_data.get("erreur"): render_native_card("🍷", "Gastronomie", gastro_data.get("titre", ""), gastro_data.get("origine", ""), None, gastro_data.get("analyse", ""), gastro_data.get("image"), gastro_data.get("lien_wiki") or fallback_wiki(gastro_data.get('titre', '')), "🍷 L'histoire du plat")
    if not movie_data.get("erreur"): render_native_card("🎬", "Cinéma", movie_data.get("titre", ""), f"{movie_data.get('realisateur', '')} ({movie_data.get('annee', '')})", None, movie_data.get("analyse", ""), movie_data.get("image"), movie_data.get("lien_wiki") or fallback_wiki(movie_data.get('titre', '')), "🎞️ Fiche du film")

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
