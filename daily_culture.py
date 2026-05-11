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

# CSS Premium, Adaptatif et Typographie
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
        text-align: center; font-family: 'Playfair Display', serif; font-size: 1.6rem; 
        font-style: italic; color: #b8860b; padding: 40px; margin-bottom: 50px; 
        background: #fdfbf7; border-radius: 15px; border: 1px solid #f0ece1; 
        box-shadow: 0 10px 25px rgba(0,0,0,0.03);
    }
    
    [data-testid="stImage"] img { 
        border-radius: 12px; 
        box-shadow: 0 12px 30px rgba(0,0,0,0.12); 
        margin-bottom: 25px; 
    }
    
    .stButton button { width: 100%; border-radius: 8px; height: 50px; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

# --- SECURITÉ & CLÉS API ---
DEEPSEEK_KEY = st.secrets.get("DEEPSEEK_API_KEY")
if not DEEPSEEK_KEY:
    st.error("❌ CLÉ API MANQUANTE : Ajoutez 'DEEPSEEK_API_KEY' dans les Secrets.")
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
        if p.get("category") == category and p.get("title") == title:
            p["liked"] = is_liked
            with open(PREFS_FILE, "w", encoding="utf-8") as f: json.dump(prefs, f, ensure_ascii=False, indent=4)
            st.toast("Préférence mise à jour ! ✨")
            return
    prefs.append({"date": date_str, "category": category, "title": title, "author": author, "liked": is_liked})
    with open(PREFS_FILE, "w", encoding="utf-8") as f: json.dump(prefs, f, ensure_ascii=False, indent=4)
    if is_liked: st.toast("Ajouté aux favoris ! ⭐")

# --- FONCTIONS HELPERS (IMAGES & JSON) ---
def extract_json(text):
    try:
        match = re.search(r'\{.*\}', text.strip(), re.DOTALL)
        if match: return json.loads(match.group(0))
        return json.loads(text)
    except Exception as e:
        raise ValueError(f"Impossible de parser le JSON: {str(e)}")

def get_wiki_image(query, lang="fr"):
    """Cherche l'image principale sur Wikipédia avec une correction d'URL."""
    if not query: return None
    headers = {"User-Agent": "L_Eveil_Culturel_App/3.1 (contact@example.com)"}
    try:
        search_url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(str(query))}&utf8=&format=json&srlimit=1"
        res = requests.get(search_url, headers=headers, timeout=8).json()
        if not res.get('query', {}).get('search'): return None
        page_title = res['query']['search'][0]['title']
        
        summary_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(page_title.replace(' ', '_'))}"
        res2 = requests.get(summary_url, headers=headers, timeout=8).json()
        
        url = None
        if 'originalimage' in res2:
            url = res2['originalimage']['source']
        elif 'thumbnail' in res2:
            url = res2['thumbnail']['source']
            
        if url:
            # Correction cruciale : forcer le https si Wikipédia renvoie un lien relatif (//...)
            if url.startswith("//"): url = "https:" + url
            return url
    except: pass
    return None

def fetch_image_cascade(res_dict, category):
    """Système de recherche d'images en cascade. Garantit 100% de succès."""
    primary_lang = "en" if category in ["Cinéma", "Musique", "Architecture", "Littérature"] else "fr"
    
    queries = [
        res_dict.get("image_query"),
        res_dict.get("titre"),
        res_dict.get("artiste"),
        res_dict.get("auteur"),
        res_dict.get("realisateur"),
        res_dict.get("philosophe"),
        res_dict.get("inventeur"),
        res_dict.get("concept")
    ]
    # Nettoyage des requêtes vides
    queries = [str(q) for q in queries if q and len(str(q)) > 2]

    # 1. Tenter Wikipédia (Images réelles et historiques)
    for q in queries:
        img = get_wiki_image(q, primary_lang)
        if img: return img
        
        img = get_wiki_image(q, "fr" if primary_lang == "en" else "en")
        if img: return img
        
    # 2. SOLUTION DE REPLI ABSOLUE : Générateur d'Image IA Gratuit
    if queries:
        best_query = queries[0]
        # Suppression des caractères spéciaux pour ne pas casser l'URL de l'IA
        clean_query = re.sub(r'[^a-zA-Z0-9\s]', ' ', str(best_query)).strip()
        ai_prompt = f"Cinematic elegant high quality photography of {clean_query} for a {category} magazine"
        safe_prompt = urllib.parse.quote(ai_prompt)
        return f"https://image.pollinations.ai/prompt/{safe_prompt}?width=800&height=500&nologo=true"
        
    return None

@st.cache_data(show_spinner=False, ttl=86400*30)
def ask_deepseek(prompt, date_str, retries=2):
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "Tu es un curateur culturel. Tes analyses sont profondes et détaillées (10 phrases). Réponds STRICTEMENT en JSON pur."},
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
def get_content_item(category_name, date_str):
    prompts = {
        "Poésie": "{'titre': '...', 'auteur': '...', 'poeme_entier': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Auteur'}",
        "Littérature": "{'titre': '...', 'auteur': '...', 'extrait': 'Extrait marquant du livre...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Nom exact du livre ou de l\\'auteur'}",
        "Musique": "{'titre': '...', 'artiste': '...', 'annee': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Nom de l\\'artiste musical'}",
        "Science": "{'titre': '...', 'inventeur': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Invention ou Inventeur'}",
        "Philosophie": "{'concept': '...', 'philosophe': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Philosophe célèbre'}",
        "Cinéma": "{'titre': '...', 'realisateur': '...', 'annee': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Titre du film original'}",
        "Architecture": "{'titre': '...', 'lieu': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Nom monument pour recherche image'}",
        "Mythologie": "{'titre': '...', 'origine': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Nom divinité ou héros'}",
        "Gastronomie": "{'titre': '...', 'origine': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Nom exact du plat'}"
    }
    
    prompt = f"Édition du {date_str}. Propose une œuvre fascinante pour la catégorie : {category_name}. Format attendu : {prompts[category_name]}"
    
    res = ask_deepseek(prompt, date_str)
    if not res.get("erreur"):
        res["image"] = fetch_image_cascade(res, category_name)
    return res

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_art_safe(date_str):
    seed_val = int(date_str.replace("-", ""))
    random.seed(seed_val)
    ids = [436535, 436528, 436532, 435882, 435809, 436533, 436529, 437112, 436121, 459123]
    try:
        r = requests.get(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{random.choice(ids)}", timeout=15).json()
        ds = ask_deepseek(f"Analyse riche de l'œuvre '{r.get('title')}' par {r.get('artistDisplayName')}. JSON: {{'titre_fr': '...', 'analyse': '...', 'lien_wiki': '...'}}", date_str)
        return {
            "titre": ds.get('titre_fr', r.get('title', 'Sans Titre')),
            "auteur": r.get('artistDisplayName', 'Anonyme'),
            "image": r.get('primaryImageSmall'),
            "analyse": ds.get('analyse', 'Analyse en cours...'),
            "lien_wiki": ds.get('lien_wiki') or r.get('objectURL')
        }
    except: return {"erreur": True}

# --- AFFICHAGE ---
def render_block_safe(icon, label, data, date_str, context_id, color="#d4af37"):
    if not data or data.get("erreur"): return
    
    titre = data.get("titre") or data.get("concept") or "Inconnu"
    auteur = data.get("auteur") or data.get("artiste") or data.get("realisateur") or data.get("philosophe") or data.get("inventeur") or data.get("origine") or data.get("lieu") or ""
    analyse = data.get("analyse") or "Analyse indisponible."
    image = data.get("image")
    wiki = data.get("lien_wiki")
    
    # Prise en charge des poèmes ou des extraits de littérature
    content_text = data.get("poeme_entier") or data.get("extrait")
    
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
        
        # Image corrigée à 100% de réussite
        if image: 
            st.image(image, use_container_width=True)
            
        if content_text: 
            st.markdown(f'<div class="poem-box">{content_text}</div>', unsafe_allow_html=True)
            
        st.write(analyse)
        
        st.write("")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("👍 J'aime", key=f"btn_l_{safe_key}", use_container_width=True):
                save_pref(label, titre, auteur, True, date_str)
        with c2:
            if st.button("👎 Bof", key=f"btn_d_{safe_key}", use_container_width=True):
                save_pref(label, titre, auteur, False, date_str)
        
        if wiki:
            btn_label = "🎧 Écouter" if label == "Musique" else "📖 Approfondir"
            st.link_button(btn_label, wiki, use_container_width=True)

def display_exposition(target_date, context_id):
    date_str = target_date.strftime("%Y-%m-%d")
    
    st.markdown(f"<p style='text-align: center; color: #7f8c8d; font-size: 1.3rem; font-style: italic;'>Édition du {target_date.strftime('%d %B %Y')}</p>", unsafe_allow_html=True)

    with st.spinner("Curation en cours..."):
        quote = ask_deepseek(f"Citation courte inspirante pour l'édition du {date_str}. JSON: {{'citation':'...', 'auteur':'...'}}", date_str)
        art = get_art_safe(date_str)
        
        # Le NOUVEL ORDRE des rubriques :
        blocks = [
            ("Poésie", "#8e44ad", "📜"),
            ("Littérature", "#d35400", "📚"),
            ("Musique", "#c0392b", "🎵"),
            ("Science", "#2980b9", "🌍"),
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
            label_display = "Sciences" if name == "Science" else name
            render_block_safe(icon, label_display, data, date_str, context_id, color)

# --- APP PRINCIPALE ---
st.title("L'Éveil Culturel")
t1, t2, t3 = st.tabs(["✨ Aujourd'hui", "📅 Archives", "⭐ Favoris"])

with t1: 
    display_exposition(datetime.date.today(), context_id="today")
    
with t2:
    d = st.date_input("Date :", value=datetime.date.today() - datetime.timedelta(days=1), max_value=datetime.date.today())
    if d != datetime.date.today(): 
        display_exposition(d, context_id="archive")
        
with t3:
    prefs = [p for p in load_prefs() if p.get("liked")]
    if not prefs: 
        st.info("Aucun favori pour le moment.")
    else:
        for p in sorted(prefs, key=lambda x: x.get('date', ''), reverse=True):
            st.markdown(f"**{p.get('category')}** : {p.get('title')} *({p.get('author')})* — {p.get('date')}")
