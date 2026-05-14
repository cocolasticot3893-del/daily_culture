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
st.set_page_config(page_title="Le Banquet des Muses", page_icon="🏛️", layout="centered")

# --- ESTHÉTIQUE GRÉCO-ROMAINE (Cinzel & Cormorant) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&display=swap');
    
    /* Fond couleur Marbre/Travertin antique */
    .stApp { background-color: #f4f1ea; }
    
    /* Typographie des titres - Inscriptions Romaines */
    h1, h2, h3 { font-family: 'Cinzel', serif; color: #4a3424; text-align: center; text-transform: uppercase; letter-spacing: 1px; }
    h1 { font-size: 3.2rem; border-bottom: 2px solid #800020; padding-bottom: 15px; margin-bottom: 40px; color: #800020; }
    
    /* Corps de texte élégant */
    p, div, span { font-family: 'Cormorant Garamond', serif; font-size: 1.3rem; line-height: 1.7; color: #2b2b2b; }
    
    /* Encadré Poésie façon parchemin */
    .poem-box { 
        font-family: 'Cormorant Garamond', serif; font-size: 1.45rem; line-height: 2; font-style: italic;
        padding: 25px; border: 1px solid #d3c4a3; white-space: pre-wrap; 
        color: #3b2f2f; margin: 25px 0; background-color: #fdfbf7; border-radius: 2px;
        box-shadow: inset 0 0 15px rgba(0,0,0,0.03);
    }
    
    /* Encadré Citation façon fronton */
    .quote-box { 
        text-align: center; font-family: 'Cinzel', serif; font-size: 1.4rem; color: #800020; 
        padding: 40px; margin-bottom: 50px; background: #fcfaf5; 
        border-radius: 2px; border-top: 3px double #d3c4a3; border-bottom: 3px double #d3c4a3;
        box-shadow: 0 10px 25px rgba(0,0,0,0.04);
    }
    
    /* Images bordées comme des fresques */
    [data-testid="stImage"] img { border-radius: 2px; box-shadow: 0 10px 25px rgba(0,0,0,0.15); margin-bottom: 25px; border: 3px solid #d3c4a3; object-fit: cover; max-height: 500px; width: 100%;}
    
    /* Boutons sculptés */
    .stButton button { width: 100%; border-radius: 2px; height: 50px; font-family: 'Cinzel', serif; font-weight: 600; border: 1px solid #d3c4a3; background-color: #fdfbf7; color: #4a3424; letter-spacing: 1px; }
    .stButton button:hover { border-color: #800020; color: #800020; }
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
    if not query: return None
    headers = {"User-Agent": "Le_Banquet_des_Muses/1.0 (contact@example.com)"}
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
            thumb = res2['thumbnail']['source']
            url = re.sub(r'\d+px-', '800px-', thumb) # On force une meilleure qualité
        
        if url and url.startswith("//"): url = "https:" + url
        return url
    except: pass
    return None

def fetch_image_cascade(res_dict, category):
    """Recherche Wikipedia en priorité, puis Fallback sur IA générative Pollinations"""
    primary_lang = "en" if category in ["Cinéma", "Musique", "Sciences"] else "fr"
    
    # Nettoyage sévère des mots-clés de recherche
    queries = [
        res_dict.get("image_query"),
        res_dict.get("titre"),
        res_dict.get("artiste"),
        res_dict.get("auteur"),
        res_dict.get("realisateur"),
        res_dict.get("philosophe"),
        res_dict.get("inventeur")
    ]
    queries = [str(q).split('\n')[0].strip() for q in queries if q and len(str(q)) > 2] # Évite les textes à rallonge

    # 1. Wikipedia
    for q in queries:
        img = get_wiki_image(q, primary_lang)
        if img: return img
        img = get_wiki_image(q, "fr" if primary_lang == "en" else "en")
        if img: return img
        
    # 2. IA Pollinations (Fallback Absolu)
    if queries:
        clean_query = re.sub(r'[^a-zA-Z0-9\s]', ' ', queries[0]).strip()
        ai_prompt = f"Cinematic elegant high quality aesthetic photography of {clean_query}"
        safe_prompt = urllib.parse.quote(ai_prompt)
        return f"https://image.pollinations.ai/prompt/{safe_prompt}?width=800&height=500&nologo=true"
        
    return None

@st.cache_data(show_spinner=False, ttl=86400*30)
def ask_deepseek(prompt, seed, retries=2):
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "Tu es un érudit français. Réponds STRICTEMENT en JSON pur et valide. Assure-toi que les champs 'auteur', 'philosophe' ou 'artiste' ne contiennent QUE le nom (pas de texte). Fournis des analyses très approfondies (10 phrases)."},
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
def get_content_item(category_name, date_str, offset, used_titles_str):
    prompts = {
        "Poésie": "{'titre': '...', 'auteur': 'Nom exact', 'contenu': 'Le poème entier', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Auteur'}",
        "Littérature": "{'titre': '...', 'auteur': 'Nom exact', 'contenu': 'Extrait marquant du livre', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Auteur'}",
        "Musique": "{'titre': '...', 'artiste': 'Nom exact', 'annee': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Artiste'}",
        "Sciences": "{'titre': '...', 'inventeur': 'Nom exact', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Invention ou Inventeur'}",
        "Philosophie": "{'concept': '...', 'philosophe': 'Nom exact', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Philosophe'}",
        "Cinéma": "{'titre': '...', 'realisateur': 'Nom exact', 'annee': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Titre du film original'}",
        "Architecture": "{'titre': '...', 'lieu': 'Nom exact', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Nom monument'}",
        "Mythologie": "{'titre': '...', 'origine': 'Civilisation', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Sujet du mythe'}",
        "Gastronomie": "{'titre': '...', 'origine': 'Lieu', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Nom du plat'}"
    }
    
    # Règle anti-doublon et anti-confusion poésie/littérature
    extra_rule = f"Règle stricte: NE PROPOSE PAS les œuvres suivantes ({used_titles_str}). "
    if category_name == "Littérature": extra_rule += "Propose un roman, essai ou pièce de théâtre, SURTOUT PAS DE POÉSIE. "
    
    prompt = f"Édition du {date_str} (Hachage {offset}). {extra_rule} Propose une œuvre fascinante pour la catégorie : {category_name}. Format JSON attendu : {prompts[category_name]}"
    
    res = ask_deepseek(prompt, f"{date_str}_{category_name}_{offset}")
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
    
    # Nettoyage basique si l'IA met du texte dans les champs d'auteur
    titre = str(data.get("titre") or data.get("concept") or "Inconnu").strip()
    auteur = str(data.get("auteur") or data.get("artiste") or data.get("realisateur") or data.get("philosophe") or data.get("inventeur") or data.get("origine") or data.get("lieu") or "").split('\n')[0].strip()
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
        
        if image: 
            st.image(image, use_container_width=True)
            
        if content_text: 
            st.markdown(f'<div class="poem-box">{content_text}</div>', unsafe_allow_html=True)
            
        st.write(analyse)
        
        st.write("")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("👍 J'aime", key=f"btn_l_{safe_key}", use_container_width=True): save_pref(label, titre, auteur, True, date_str)
        with c2:
            if st.button("👎 Bof", key=f"btn_d_{safe_key}", use_container_width=True): save_pref(label, titre, auteur, False, date_str)
        
        # Redirection YouTube Music forcée
        if label == "Musique":
            yt_link = f"https://music.youtube.com/search?q={urllib.parse.quote(auteur + ' ' + titre)}"
            st.link_button("🎧 Écouter sur YouTube Music", yt_link, use_container_width=True)
        elif wiki:
            st.link_button("📖 Approfondir", wiki, use_container_width=True)

def display_exposition(target_date, context_id):
    date_str = target_date.strftime("%Y-%m-%d")
    
    st.markdown(f"<p style='text-align: center; color: #7f8c8d; font-size: 1.3rem; font-style: italic;'>Édition du {target_date.strftime('%d %B %Y')}</p>", unsafe_allow_html=True)

    with st.spinner("Le curateur sélectionne les œuvres du banquet..."):
        quote = ask_deepseek(f"Citation inspirante sur la sagesse ou l'art. JSON: {{'citation':'...', 'auteur':'...'}}", date_str)
        
        # Traitement séquentiel pour nourrir la liste des doublons
        used_titles = []
        
        art = get_art_safe(date_str)
        if not art.get("erreur"): used_titles.append(art.get("titre", ""))
        
        blocks_config = [
            ("Poésie", 2, "#5a3a29", "📜"),
            ("Littérature", 3, "#800020", "📚"),
            ("Musique", 4, "#6b4423", "🎵"),
            ("Sciences", 5, "#2f4f4f", "🌍"),
            ("Philosophie", 6, "#4a3424", "🧠"),
            ("Cinéma", 7, "#3b2f2f", "🎬"),
            ("Architecture", 8, "#555555", "🏛️"),
            ("Mythologie", 9, "#8b4513", "⚡"),
            ("Gastronomie", 10, "#6b2737", "🍷")
        ]
        
        # Génération avec protection anti-doublon
        generated_data = {}
        for name, offset, _, _ in blocks_config:
            data = get_content_item(name, date_str, offset, ", ".join(used_titles))
            generated_data[name] = data
            if not data.get("erreur"):
                used_titles.append(data.get("titre", ""))
                # On ajoute aussi l'auteur pour éviter qu'il propose Rimbaud en poésie ET en littérature
                author_field = data.get("auteur") or data.get("artiste") or data.get("realisateur") or data.get("philosophe")
                if author_field: used_titles.append(author_field)

        # Affichage
        if not quote.get("erreur"):
            st.markdown(f"<div class='quote-box'>« {quote.get('citation')} »<br><small>— {quote.get('auteur')}</small></div>", unsafe_allow_html=True)
            
        render_block_safe("🖼️", "Beaux-Arts", art, date_str, context_id, color="#800020")
            
        for name, _, color, icon in blocks_config:
            render_block_safe(icon, name, generated_data[name], date_str, context_id, color)

# --- APP PRINCIPALE ---
st.title("Le Banquet des Muses")
t1, t2, t3 = st.tabs(["✨ Aujourd'hui", "📅 Archives", "⭐ Favoris"])

with t1: display_exposition(datetime.date.today(), context_id="today")
with t2:
    d = st.date_input("Date :", value=datetime.date.today() - datetime.timedelta(days=1), max_value=datetime.date.today())
    if d != datetime.date.today(): display_exposition(d, context_id="archive")
with t3:
    prefs = [p for p in load_prefs() if p.get("liked")]
    if not prefs: st.info("Aucun favori pour le moment.")
    else:
        for p in sorted(prefs, key=lambda x: x.get('date', ''), reverse=True):
            st.markdown(f"**{p.get('category')}** : {p.get('title')} *({p.get('author')})* — {p.get('date')}")
