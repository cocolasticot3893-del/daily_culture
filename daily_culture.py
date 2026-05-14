import streamlit as st
import requests
import random
import hashlib
import json
import datetime
import urllib.parse
import time
import re
import io
from pathlib import Path

# Tentative d'import de gTTS pour l'audio
try:
    from gtts import gTTS
    HAS_GTTS = True
except ImportError:
    HAS_GTTS = False

# --- CONFIGURATION STREAMLIT ---
st.set_page_config(page_title="L'Éveil Culturel", page_icon="🏛️", layout="centered")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&family=Source+Sans+Pro:wght@300;400;600&display=swap');
    
    h1, h2, h3 { font-family: 'Playfair Display', serif; color: #1a252f; text-align: center; }
    h1 { font-size: 3rem; border-bottom: 3px solid #d4af37; padding-bottom: 25px; margin-bottom: 40px; }
    p, div, span { font-family: 'Source Sans Pro', sans-serif; font-size: 1.15rem; line-height: 1.8; }
    
    .poem-box { 
        font-family: 'Playfair Display', serif; font-size: 1.3rem; line-height: 2; 
        padding-left: 25px; border-left: 4px solid #d4af37; white-space: pre-wrap; 
        color: #1a252f; margin: 25px 0; background-color: #fcfcf9; padding: 25px; border-radius: 0 12px 12px 0;
        box-shadow: inset 0 0 10px rgba(0,0,0,0.02);
    }
    
    .quote-box { 
        text-align: center; font-family: 'Playfair Display', serif; font-size: 1.6rem; font-style: italic; color: #b8860b; padding: 40px; margin-bottom: 50px; background: #fdfbf7; border-radius: 15px; border: 1px solid #f0ece1; box-shadow: 0 10px 25px rgba(0,0,0,0.03);
    }
    
    [data-testid="stImage"] img { border-radius: 12px; box-shadow: 0 12px 30px rgba(0,0,0,0.12); margin-bottom: 25px; border: 1px solid #eee; object-fit: cover; max-height: 500px; width: 100%;}
    .stButton button { width: 100%; border-radius: 8px; height: 50px; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

if not HAS_GTTS:
    st.warning("💡 Installez `gTTS` (`pip install gTTS`) pour activer la lecture audio des œuvres !")

# --- SECURITÉ & CLÉS API ---
DEEPSEEK_KEY = st.secrets.get("DEEPSEEK_API_KEY")
if not DEEPSEEK_KEY:
    st.error("❌ CLÉ API MANQUANTE : Ajoutez 'DEEPSEEK_API_KEY' dans les Secrets.")
    st.stop()

# --- GESTION DES FAVORIS & SYSTÈME DE RECOMMANDATION (RAG) ---
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
        if p.get("category") == category and p.get("title") == title:
            p["liked"] = is_liked
            with open(PREFS_FILE, "w", encoding="utf-8") as f: json.dump(prefs, f, ensure_ascii=False, indent=4)
            st.toast("Préférence mise à jour ! ✨")
            return
    prefs.append({"date": date_str, "category": category, "title": title, "author": author, "liked": is_liked})
    with open(PREFS_FILE, "w", encoding="utf-8") as f: json.dump(prefs, f, ensure_ascii=False, indent=4)
    if is_liked: st.toast("Ajouté aux favoris ! ⭐")

def build_preference_context(category):
    """Analyse l'historique pour influencer l'IA et interdire les répétitions."""
    prefs = load_prefs()
    cat_prefs = [p for p in prefs if p.get("category") == category]
    
    likes = [p.get("title") for p in cat_prefs if p.get("liked") is True][-3:] # Les 3 derniers aimés
    all_seen = [p.get("title") for p in cat_prefs] # Tout ce qui a été vu
    
    context = ""
    if likes: context += f"Pour information, l'utilisateur a adoré ces œuvres similaires : {', '.join(likes)}. "
    if all_seen: context += f"RÈGLE ABSOLUE : Il t'est STRICTEMENT INTERDIT de reproposer l'une de ces œuvres : {', '.join(all_seen)}. Cherche de la nouveauté. "
    return context

# --- FONCTIONS HELPERS ---
def extract_json(text):
    try:
        match = re.search(r'\{.*\}', text.strip(), re.DOTALL)
        if match: return json.loads(match.group(0))
        return json.loads(text)
    except Exception as e:
        raise ValueError(f"Impossible de parser le JSON: {str(e)}")

def get_wiki_image(query, lang="fr"):
    if not query: return None
    headers = {"User-Agent": "L_Eveil_Culturel_App/4.0"}
    try:
        search_url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(str(query))}&utf8=&format=json&srlimit=1"
        res = requests.get(search_url, headers=headers, timeout=8).json()
        if not res.get('query', {}).get('search'): return None
        page_title = res['query']['search'][0]['title']
        
        summary_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(page_title.replace(' ', '_'))}"
        res2 = requests.get(summary_url, headers=headers, timeout=8).json()
        
        url = None
        if 'originalimage' in res2: url = res2['originalimage']['source']
        elif 'thumbnail' in res2: url = res2['thumbnail']['source'].replace(r'\d+px-', '800px-')
        if url and url.startswith("//"): url = "https:" + url
        return url
    except: pass
    return None

def get_smart_image(res_dict, category):
    """Moteur Hybride : Wikipéda (Factuel) ou IA Générative Pollinations (Abstrait)"""
    prompt_ia = res_dict.get("prompt_image_ia")
    
    # 1. Pour les concepts poétiques et abstraits, l'IA produit de plus belles images
    if category in ["Poésie", "Philosophie", "Mythologie", "Littérature"] and prompt_ia:
        safe_prompt = urllib.parse.quote(f"{prompt_ia}, cinematic, aesthetic, highly detailed")
        return f"https://image.pollinations.ai/prompt/{safe_prompt}?width=800&height=500&nologo=true"
        
    # 2. Pour le concret, on tente Wikipédia
    query = res_dict.get("recherche_wiki") or res_dict.get("titre")
    if query:
        lang = "en" if category in ["Cinéma", "Musique", "Sciences"] else "fr"
        img = get_wiki_image(query, lang)
        if not img: img = get_wiki_image(query, "fr" if lang=="en" else "en")
        if img: return img
        
    # 3. Fallback IA si Wikipédia n'a rien trouvé du tout
    if prompt_ia:
        safe_prompt = urllib.parse.quote(f"{prompt_ia}, realistic photography")
        return f"https://image.pollinations.ai/prompt/{safe_prompt}?width=800&height=500&nologo=true"
    
    return None

@st.cache_data(show_spinner=False, ttl=86400*30)
def generate_audio(text):
    if not HAS_GTTS or not text: return None
    try:
        tts = gTTS(text, lang='fr')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        return fp.getvalue()
    except: return None

@st.cache_data(show_spinner=False, ttl=86400*30)
def ask_deepseek(prompt, seed, retries=2):
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "Tu es un expert culturel français. Tu fournis des analyses très approfondies (10 phrases). Réponds en JSON pur. N'inclus aucun code Markdown ni ID de génération dans ton texte final."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }
    for i in range(retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return extract_json(content)
        except Exception as e:
            time.sleep(2)
            if i == retries - 1: return {"erreur": True, "details": str(e)}

# --- FONCTIONS DE CONTENU ---
@st.cache_data(show_spinner=False, ttl=86400*30)
def get_met_pool():
    """Récupère dynamiquement les IDs des milliers de chefs-d'œuvre du MET !"""
    try:
        r = requests.get("https://collectionapi.metmuseum.org/public/collection/v1/search?isHighlight=true&hasImages=true&q=art", timeout=10).json()
        return r.get("objectIDs", [436535, 436528, 435809])
    except: return [436535, 436528, 435809]

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_art_safe(date_str):
    seed_val = int(date_str.replace("-", ""))
    random.seed(seed_val)
    ids_pool = get_met_pool()
    try:
        r = requests.get(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{random.choice(ids_pool)}", timeout=15).json()
        context = build_preference_context("Beaux-Arts")
        ds = ask_deepseek(f"{context} Analyse détaillée de '{r.get('title')}' par {r.get('artistDisplayName')}. JSON: {{'titre_fr': '...', 'analyse': '...', 'lien_wiki': '...'}}", date_str)
        return {"titre": ds.get('titre_fr', r.get('title')), "auteur": r.get('artistDisplayName', 'Anonyme'), "image": r.get('primaryImageSmall'), "analyse": ds.get('analyse', ''), "lien_wiki": ds.get('lien_wiki') or r.get('objectURL')}
    except: return {"erreur": True}

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_content_item(category_name, date_str):
    json_format = "{'titre': '...', 'auteur': '...', 'contenu': '...', 'analyse': '...', 'lien_wiki': '...', 'recherche_wiki': 'Nom exact pour photo', 'prompt_image_ia': 'Description visuelle très détaillée en ANGLAIS pour générer une illustration (ex: A cinematic shot of a glowing potion in a dark laboratory)'}"
    
    context = build_preference_context(category_name)
    prompt = f"Édition du {date_str}. {context} Propose une œuvre/concept incontournable pour la catégorie : {category_name}. Pour 'contenu', mets le poème/l'extrait si pertinent, sinon vide. Format attendu : {json_format}"
    
    res = ask_deepseek(prompt, f"{date_str}_{category_name}") # Seed unique par catégorie
    if not res.get("erreur"):
        res["image"] = get_smart_image(res, category_name)
    return res

# --- AFFICHAGE ---
def render_block_safe(icon, label, data, date_str, context_id, color="#d4af37"):
    if not data or data.get("erreur"): return
    
    titre = data.get("titre") or "Inconnu"
    auteur = data.get("auteur") or data.get("artiste") or data.get("realisateur") or data.get("philosophe") or data.get("inventeur") or data.get("origine") or data.get("lieu") or ""
    analyse = data.get("analyse") or "Analyse indisponible."
    image = data.get("image")
    wiki = data.get("lien_wiki")
    content_text = data.get("contenu") or data.get("poeme_entier") or data.get("extrait")
    
    safe_key = f"{label}_{date_str}_{context_id}"

    with st.container(border=True):
        st.markdown(f"""
            <div style="text-align: center; margin-bottom: 25px;">
                <span style="color: {color}; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; font-size: 0.9rem;">{icon} {label}</span>
                <h2 style="margin: 10px 0 5px 0; font-size: 2.2rem;">{titre}</h2>
                <h4 style="font-style: italic; color: #7f8c8d; font-weight: normal; margin-top: 0;">{auteur}</h4>
                <hr style="width: 50px; margin: 15px auto; border: 1px solid {color};">
            </div>
        """, unsafe_allow_html=True)
        
        if image: st.image(image, use_container_width=True)
        
        if content_text: 
            st.markdown(f'<div class="poem-box">{content_text}</div>', unsafe_allow_html=True)
            # Ajout du Lecteur Audio si texte long !
            if HAS_GTTS:
                audio_bytes = generate_audio(f"{titre}, par {auteur}. {content_text}")
                if audio_bytes: st.audio(audio_bytes, format='audio/mp3')
                
        st.write(analyse)
        
        # Audio de l'analyse (Optionnel mais génial)
        if HAS_GTTS and not content_text:
            audio_bytes = generate_audio(analyse)
            if audio_bytes: st.audio(audio_bytes, format='audio/mp3')
        
        st.write("")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("👍 J'aime", key=f"btn_l_{safe_key}"): save_pref(label, titre, auteur, True, date_str)
        with c2:
            if st.button("👎 Bof", key=f"btn_d_{safe_key}"): save_pref(label, titre, auteur, False, date_str)
        
        if wiki:
            btn_label = "🎧 Écouter" if label == "Musique" else "📖 Approfondir"
            if label == "Musique" and "wikipedia" not in wiki.lower():
                 wiki = f"https://music.youtube.com/search?q={urllib.parse.quote(auteur + ' ' + titre)}"
            st.link_button(btn_label, wiki, use_container_width=True)

def display_exposition(target_date, context_id):
    date_str = target_date.strftime("%Y-%m-%d")
    
    st.markdown(f"<p style='text-align: center; color: #7f8c8d; font-size: 1.3rem; font-style: italic;'>Édition du {target_date.strftime('%d %B %Y')}</p>", unsafe_allow_html=True)

    with st.spinner("Analyse de vos goûts et curation en cours..."):
        quote = ask_deepseek(f"Citation courte. JSON: {{'citation':'...', 'auteur':'...'}}", date_str)
        art = get_art_safe(date_str)
        
        # Le NOUVEL ORDRE
        blocks = [
            ("Poésie", "#8e44ad", "📜"),
            ("Littérature", "#d35400", "📚"),
            ("Musique", "#c0392b", "🎵"),
            ("Sciences", "#2980b9", "🌍"),
            ("Philosophie", "#16a085", "🧠"),
            ("Cinéma", "#34495e", "🎬"),
            ("Architecture", "#2c3e50", "🏛️"),
            ("Mythologie", "#e67e22", "⚡"),
            ("Gastronomie", "#27ae60", "🍷")
        ]
        
        if not quote.get("erreur"):
            st.markdown(f"<div class='quote-box'>« {quote.get('citation')} »<br><small>— {quote.get('auteur')}</small></div>", unsafe_allow_html=True)
            
        render_block_safe("🖼️", "Beaux-Arts", art, date_str, context_id, color="#b8860b")
            
        for name, color, icon in blocks:
            data = get_content_item(name, date_str)
            render_block_safe(icon, name, data, date_str, context_id, color)

# --- APP PRINCIPALE ---
st.title("L'Éveil Culturel")
t1, t2, t3 = st.tabs(["✨ Aujourd'hui", "📅 Archives", "⭐ Favoris"])

with t1: display_exposition(datetime.date.today(), context_id="today")
with t2:
    d = st.date_input("Date :", value=datetime.date.today() - datetime.timedelta(days=1), max_value=datetime.date.today())
    if d != datetime.date.today(): display_exposition(d, context_id="archive")
with t3:
    prefs = [p for p in load_prefs() if p.get("liked")]
    if not prefs: st.info("Aucun favori enregistré.")
    else:
        for p in sorted(prefs, key=lambda x: x.get('date', ''), reverse=True):
            st.markdown(f"**{p.get('category')}** : {p.get('title')} *({p.get('author')})* — {p.get('date')}")
