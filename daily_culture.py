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

# CSS Premium (Style Gréco-Romain) et Correction Boutons
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&display=swap');
    
    .stApp { background-color: #f4f1ea; color: #2b2b2b; }
    
    h1, h2, h3 { font-family: 'Cinzel', serif; color: #1a1a1a; text-align: center; }
    h1 { font-size: 3rem; border-bottom: 2px solid #800020; padding-bottom: 20px; margin-bottom: 40px; }
    
    p, div, span { font-family: 'Cormorant Garamond', serif; font-size: 1.3rem; line-height: 1.7; }
    
    .poem-box { 
        font-family: 'Cormorant Garamond', serif; font-size: 1.4rem; line-height: 1.9; 
        padding-left: 25px; border-left: 3px solid #800020; white-space: pre-wrap; 
        color: #1a1a1a; margin: 25px 0; background-color: #fdfbf7; padding: 25px; 
        box-shadow: inset 0 0 10px rgba(0,0,0,0.03);
    }
    
    .quote-box { 
        text-align: center; font-family: 'Cinzel', serif; font-size: 1.4rem; 
        color: #800020; padding: 40px; margin-bottom: 50px; 
        background: #fdfbf7; border: 1px solid #d4c4a8; 
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    }
    
    [data-testid="stImage"] img { 
        border-radius: 4px; 
        box-shadow: 0 8px 25px rgba(0,0,0,0.15); 
        margin-bottom: 25px; 
        border: 2px solid #d4c4a8;
    }
    
    .stButton button { 
        width: 100%; border-radius: 4px; height: 50px; 
        font-family: 'Cinzel', serif; font-weight: 600; letter-spacing: 1px;
    }
    
    [data-testid="stLinkButton"] a {
        background-color: #111827 !important;
        border: 1px solid #800020 !important;
        border-radius: 4px !important;
        text-decoration: none !important;
    }
    [data-testid="stLinkButton"] a p {
        color: #fdfbf7 !important;
        font-family: 'Cinzel', serif !important;
        font-weight: 600 !important;
        letter-spacing: 1px !important;
        margin: 0 !important;
    }
    [data-testid="stLinkButton"] a:hover {
        background-color: #800020 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- SECURITÉ & CLÉS API ---
def has_secret(key):
    try: return key in st.secrets
    except: return False

if not has_secret("DEEPSEEK_API_KEY"):
    st.error("❌ CLÉ API MANQUANTE : Ajoutez 'DEEPSEEK_API_KEY' dans les Secrets.")
    st.stop()
DEEPSEEK_KEY = st.secrets["DEEPSEEK_API_KEY"]

# --- CLOUD STORAGE MANAGER (JSONBin.io) ---
class StorageManager:
    def __init__(self):
        self.use_cloud = has_secret("JSONBIN_MASTER_KEY") and has_secret("JSONBIN_BIN_ID")
        
        if self.use_cloud:
            self.headers = {"X-Master-Key": st.secrets["JSONBIN_MASTER_KEY"], "Content-Type": "application/json"}
            self.bin_url = f"https://api.jsonbin.io/v3/b/{st.secrets['JSONBIN_BIN_ID']}"
        else:
            self.local_prefs = Path("mes_favoris.json")
            self.local_history = Path("seen_history.json")

    def get_data(self):
        if self.use_cloud:
            return self._fetch_cloud()
        else:
            p = json.loads(self.local_prefs.read_text(encoding="utf-8")) if self.local_prefs.exists() else []
            h = json.loads(self.local_history.read_text(encoding="utf-8")) if self.local_history.exists() else {}
            return {"prefs": p, "history": h}

    @staticmethod
    @st.cache_data(show_spinner=False, ttl=3600) # Cache 1 heure pour ne pas spammer l'API
    def _fetch_cloud():
        url = f"https://api.jsonbin.io/v3/b/{st.secrets['JSONBIN_BIN_ID']}/latest"
        headers = {"X-Master-Key": st.secrets["JSONBIN_MASTER_KEY"]}
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                return res.json().get("record", {"prefs": [], "history": {}})
        except: pass
        return {"prefs": [], "history": {}}

    def save_data(self, data):
        if self.use_cloud:
            try:
                requests.put(self.bin_url, headers=self.headers, json=data, timeout=10)
                self._fetch_cloud.clear() # On vide le cache Streamlit pour forcer le rafraîchissement au prochain get_data()
            except: pass
        else:
            self.local_prefs.write_text(json.dumps(data.get("prefs", []), ensure_ascii=False, indent=4), encoding="utf-8")
            self.local_history.write_text(json.dumps(data.get("history", {}), ensure_ascii=False, indent=4), encoding="utf-8")

# Initialisation Globale du Manager
storage = StorageManager()

def load_prefs():
    return storage.get_data().get("prefs", [])

def save_pref(category, title, author, is_liked, date_str):
    data = storage.get_data()
    prefs = data.setdefault("prefs", [])
    
    for p in prefs:
        if p.get("category") == category and p.get("title") == title:
            p["liked"] = is_liked
            storage.save_data(data)
            st.toast("Préférence mise à jour ! ✨")
            return
            
    prefs.append({"date": date_str, "category": category, "title": title, "author": author, "liked": is_liked})
    storage.save_data(data)
    if is_liked: st.toast("Ajouté aux favoris ! ⭐")

def load_history():
    return storage.get_data().get("history", {})

def save_to_history(category, title):
    if not title or title == "Inconnu": return
    data = storage.get_data()
    history = data.setdefault("history", {})
    
    if category not in history: history[category] = []
    if title not in history[category]:
        history[category].append(title)
        history[category] = history[category][-30:] 
        storage.save_data(data)

# --- FONCTIONS HELPERS ---
def extract_json(text):
    try:
        match = re.search(r'\{.*\}', text.strip(), re.DOTALL)
        if match: return json.loads(match.group(0))
        return json.loads(text)
    except Exception as e:
        raise ValueError("JSON Error")

def get_wiki_image(query, lang="fr"):
    if not query: return None
    headers = {"User-Agent": "Banquet_Des_Muses_App/5.0"}
    try:
        search_url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(str(query))}&utf8=&format=json&srlimit=1"
        res = requests.get(search_url, headers=headers, timeout=8).json()
        if not res.get('query', {}).get('search'): return None
        page_title = res['query']['search'][0]['title']
        
        summary_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(page_title.replace(' ', '_'))}"
        res2 = requests.get(summary_url, headers=headers, timeout=8).json()
        
        url = res2.get('originalimage', {}).get('source') or res2.get('thumbnail', {}).get('source')
        if url and url.startswith("//"): url = "https:" + url
        return url
    except: return None

def fetch_image_cascade(res_dict, category):
    primary_lang = "en" if category in ["Cinéma", "Musique", "Architecture", "Littérature", "Jeu vidéo", "Photographie"] else "fr"
    queries = [
        res_dict.get("image_query"), res_dict.get("titre"), res_dict.get("artiste"),
        res_dict.get("auteur"), res_dict.get("realisateur"), res_dict.get("philosophe"),
        res_dict.get("inventeur"), res_dict.get("concept"), res_dict.get("sculpteur"),
        res_dict.get("photographe"), res_dict.get("studio")
    ]
    queries = [str(q) for q in queries if q and len(str(q)) > 2]

    for q in queries:
        img = get_wiki_image(q, primary_lang)
        if img: return img
        img = get_wiki_image(q, "fr" if primary_lang == "en" else "en")
        if img: return img
        
    if queries:
        clean_query = re.sub(r'[^a-zA-Z0-9\s]', ' ', str(queries[0])).strip()
        safe_prompt = urllib.parse.quote(f"Cinematic elegant high quality photography of {clean_query} for a {category} magazine")
        return f"https://image.pollinations.ai/prompt/{safe_prompt}?width=800&height=500&nologo=true"
    return None

def get_daily_focus(category_name, date_str):
    seed_val = int(date_str.replace("-", ""))
    rng = random.Random(seed_val)
    foci = {
        "Poésie": ["le Romantisme", "le Symbolisme", "le Surréalisme", "la poésie du 20ème siècle", "le Parnasse", "la Renaissance (Pléiade)", "un poème mélancolique", "un sonnet classique", "l'amour", "la nature"],
        "Littérature": ["un roman du 19e siècle", "une pièce de théâtre antique", "un essai philosophique", "un conte philosophique", "un roman d'anticipation", "le réalisme", "le naturalisme", "un chef-d'oeuvre du 20e siècle", "un lauréat du prix Nobel", "la littérature classique"],
        "Musique": ["le rock des années 70", "le jazz classique", "la musique classique (symphonie)", "la pop des années 80", "la soul ou le R&B", "le hip-hop", "la chanson française", "le blues", "le piano solo", "l'opéra"],
        "Sciences": ["la physique quantique", "la biologie", "l'astronomie", "la chimie", "l'informatique", "les mathématiques", "la médecine", "la révolution industrielle", "l'antiquité scientifique", "la thermodynamique"],
        "Philosophie": ["l'existentialisme", "le stoïcisme", "la philosophie des Lumières", "la Grèce antique", "le rationalisme", "l'empirisme", "la phénoménologie", "le nihilisme", "la philosophie politique", "la métaphysique"],
        "Cinéma": ["le Nouvel Hollywood", "la Nouvelle Vague", "l'expressionnisme", "le néoréalisme italien", "la science-fiction", "le film noir", "les années 50", "l'animation japonaise", "le thriller", "le drame historique"],
        "Architecture": ["le gothique", "le style roman", "la Renaissance", "l'art déco", "le brutalisme", "l'Antiquité", "le modernisme", "l'architecture asiatique", "les gratte-ciels", "le baroque"],
        "Mythologie": ["la mythologie nordique", "la mythologie grecque", "la mythologie égyptienne", "la mythologie romaine", "les mythes celtiques", "les légendes asiatiques", "la Mésopotamie", "les héros", "les créatures mythologiques", "la création du monde"],
        "Gastronomie": ["un plat français", "la gastronomie italienne", "une spécialité japonaise", "un dessert classique", "un plat épicé", "les fromages et vins", "la cuisine levantine", "les techniques culinaires", "la cuisine mexicaine", "la Méditerranée"],
        "Sculpture": ["la Renaissance", "la Grèce antique", "la sculpture moderne", "l'art roman", "le monumental", "les bustes romains", "le marbre", "le bronze", "l'art abstrait", "le néoclassicisme"],
        "Arts de la scène": ["la tragédie grecque", "le ballet classique", "Molière", "Shakespeare", "l'opéra italien", "le théâtre de l'absurde", "la comédie musicale", "le théâtre du 20e siècle", "le kabuki", "la danse contemporaine"],
        "Photographie": ["la photographie humaniste", "le photojournalisme", "le paysage", "le portrait", "la photographie de rue", "le surréalisme", "le pictorialisme", "la guerre", "le noir et blanc", "la mode"],
        "Bande dessinée": ["la BD franco-belge", "le roman graphique", "le manga classique", "le comic book", "la ligne claire", "la science-fiction", "la BD historique", "les pionniers du 9e art", "les auteurs européens", "le manga seinen"],
        "Jeu vidéo": ["l'ère 16-bits", "les RPG classiques", "les jeux narratifs", "les pionniers", "les jeux indépendants", "les jeux de plateforme", "la stratégie", "la 3D naissante", "le point & click", "l'aventure épique"]
    }
    return rng.choice(foci.get(category_name, ["une œuvre incontournable"]))

@st.cache_data(show_spinner=False, ttl=86400*30)
def ask_deepseek(prompt, date_str):
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "Tu es un érudit classique. Analyses profondes (10 phrases). Pour la poésie, donne TOUJOURS le poème en ENTIER. Réponds STRICTEMENT en JSON pur."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        return extract_json(response.json()["choices"][0]["message"]["content"])
    except Exception as e:
        return {"erreur": True}

# --- FONCTIONS DE CONTENU ---
@st.cache_data(show_spinner=False, ttl=86400*30)
def get_content_item(category_name, date_str):
    prompts = {
        "Poésie": "{'titre': '...', 'auteur': '...', 'poeme_entier': 'Le texte INTÉGRAL du poème', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Auteur'}",
        "Littérature": "{'titre': '...', 'auteur': '...', 'extrait': 'Extrait de roman/essai...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Livre ou Auteur'}",
        "Musique": "{'titre': '...', 'artiste': '...', 'annee': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Artiste musical'}",
        "Sciences": "{'titre': '...', 'inventeur': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Invention'}",
        "Philosophie": "{'concept': '...', 'philosophe': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Philosophe'}",
        "Cinéma": "{'titre': '...', 'realisateur': '...', 'annee': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Film'}",
        "Architecture": "{'titre': '...', 'lieu': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Monument'}",
        "Mythologie": "{'titre': '...', 'origine': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Divinité'}",
        "Gastronomie": "{'titre': '...', 'origine': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Plat'}",
        "Sculpture": "{'titre': '...', 'sculpteur': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Nom de la sculpture'}",
        "Arts de la scène": "{'titre': '...', 'auteur': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Pièce de théâtre ou ballet'}",
        "Photographie": "{'titre': '...', 'photographe': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Titre de la photographie'}",
        "Bande dessinée": "{'titre': '...', 'auteur': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Série BD'}",
        "Jeu vidéo": "{'titre': '...', 'studio': '...', 'analyse': '...', 'lien_wiki': '...', 'image_query': 'Titre du jeu vidéo'}"
    }
    
    focus = get_daily_focus(category_name, date_str)
    history = load_history().get(category_name, [])
    avoid_clause = f" INTERDICTION ABSOLUE de proposer ces œuvres (déjà vues) : {', '.join(history)}." if history else ""
        
    prompt_complet = f"Édition du {date_str}. Propose une NOUVELLE œuvre pour : {category_name}. Thème du jour imposé : {focus}.{avoid_clause} Format strictement respecté : {prompts[category_name]}"
    
    res = ask_deepseek(prompt_complet, f"{date_str}_{category_name}")
    if not res.get("erreur"):
        res["image"] = fetch_image_cascade(res, category_name)
        titre_oeuvre = res.get("titre") or res.get("concept")
        save_to_history(category_name, titre_oeuvre)
        
    return res

@st.cache_data(show_spinner=False, ttl=86400*30)
def get_art_safe(date_str):
    random.seed(int(date_str.replace("-", "")))
    ids = [436535, 436528, 436532, 435882, 435809, 436533, 436529, 437112, 436121, 459123]
    try:
        r = requests.get(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{random.choice(ids)}", timeout=15).json()
        ds = ask_deepseek(f"Analyse de '{r.get('title')}' par {r.get('artistDisplayName')}. JSON: {{'titre_fr': '...', 'analyse': '...', 'lien_wiki': '...'}}", date_str)
        return {"titre": ds.get('titre_fr', r.get('title')), "auteur": r.get('artistDisplayName'), "image": r.get('primaryImageSmall'), "analyse": ds.get('analyse'), "lien_wiki": ds.get('lien_wiki') or r.get('objectURL')}
    except: return {"erreur": True}

# --- AFFICHAGE ---
def render_block_safe(icon, label, data, date_str, context_id, color="#c5a059"):
    if not data or data.get("erreur"): return
    
    titre = data.get("titre") or data.get("concept") or "Inconnu"
    auteur = data.get("auteur") or data.get("artiste") or data.get("realisateur") or data.get("philosophe") or data.get("inventeur") or data.get("origine") or data.get("lieu") or data.get("sculpteur") or data.get("photographe") or data.get("studio") or ""
    analyse = data.get("analyse") or ""
    image = data.get("image")
    wiki = data.get("lien_wiki")
    content_text = data.get("poeme_entier") or data.get("extrait")
    safe_key = f"{label}_{date_str}_{context_id}"

    with st.container(border=True):
        st.markdown(f"""
            <div style="text-align: center; margin-bottom: 25px;">
                <span style="color: {color}; font-family: 'Cinzel', serif; font-weight: 700; text-transform: uppercase; letter-spacing: 3px; font-size: 1rem;">{icon} {label}</span>
                <h2 style="margin: 15px 0 5px 0; font-size: 2.4rem; color: #1a1a1a;">{titre}</h2>
                <h4 style="font-family: 'Cormorant Garamond', serif; font-style: italic; color: #555; font-size: 1.4rem; font-weight: normal; margin-top: 0;">{auteur}</h4>
                <hr style="width: 60px; margin: 20px auto; border: 1px solid {color};">
            </div>
        """, unsafe_allow_html=True)
        
        if image: st.image(image, use_container_width=True)
        if content_text: st.markdown(f'<div class="poem-box">{content_text}</div>', unsafe_allow_html=True)
        st.write(analyse)
        
        st.write("")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("👍 J'aime", key=f"btn_l_{safe_key}"): save_pref(label, titre, auteur, True, date_str)
        with c2:
            if st.button("👎 Bof", key=f"btn_d_{safe_key}"): save_pref(label, titre, auteur, False, date_str)
        
        if wiki:
            if label == "Musique":
                btn_label = "🎧 Écouter (YouTube Music)"
                query = urllib.parse.quote(f"{auteur} {titre}")
                wiki = f"https://music.youtube.com/search?q={query}"
            else:
                btn_label = "📖 Approfondir"
            st.link_button(btn_label, wiki, use_container_width=True)

def display_exposition(target_date, context_id):
    date_str = target_date.strftime("%Y-%m-%d")
    st.markdown(f"<p style='text-align: center; color: #555; font-size: 1.4rem; font-style: italic;'>Édition du {target_date.strftime('%d %B %Y')}</p>", unsafe_allow_html=True)

    with st.spinner("Les Muses préparent le banquet..."):
        quote = ask_deepseek(f"Citation antique ou classique pour le {date_str}. JSON: {{'citation':'...', 'auteur':'...'}}", date_str)
        art = get_art_safe(date_str)
        
        blocks = [
            ("Poésie", "#c5a059", "📜"), ("Littérature", "#800020", "📚"), ("Musique", "#2b2b2b", "🎵"),
            ("Sciences", "#4a6b5d", "🌍"), ("Philosophie", "#800020", "🧠"), ("Cinéma", "#1a1a1a", "🎬"),
            ("Architecture", "#555555", "🏛️"), ("Mythologie", "#c5a059", "⚡"), ("Gastronomie", "#800020", "🍷"),
            ("Sculpture", "#696969", "🗿"), ("Arts de la scène", "#8B0000", "🎭"), ("Photographie", "#2F4F4F", "📷"),
            ("Bande dessinée", "#B8860B", "🖋️"), ("Jeu vidéo", "#2E8B57", "🎮")
        ]
        
        if not quote.get("erreur"):
            st.markdown(f"<div class='quote-box'>« {quote.get('citation')} »<br><br><small>— {quote.get('auteur')}</small></div>", unsafe_allow_html=True)
            
        render_block_safe("🖼️", "Beaux-Arts", art, date_str, context_id, color="#800020")
            
        for name, color, icon in blocks:
            data = get_content_item(name, date_str)
            render_block_safe(icon, name, data, date_str, context_id, color)

# --- APP PRINCIPALE ---
st.title("Le Banquet des Muses")
t1, t2, t3 = st.tabs(["✨ Aujourd'hui", "📅 Archives", "⭐ Favoris"])

with t1: display_exposition(datetime.date.today(), context_id="today")

with t2:
    d = st.date_input("Date :", value=datetime.date.today() - datetime.timedelta(days=1), max_value=datetime.date.today())
    if d != datetime.date.today(): display_exposition(d, context_id="archive")
with t3:
    if storage.use_cloud:
        st.success("☁️ Sauvegarde Cloud activée. Vos favoris et votre historique sont protégés à vie !")
    else:
        st.warning("⚠️ **Mode Local** : L'hébergement gratuit efface la mémoire chaque nuit. Pour une sauvegarde à vie, ajoutez des clés JSONBin.io dans vos Secrets Streamlit.")
    
    prefs = [p for p in load_prefs() if p.get("liked")]
    if not prefs: st.info("Aucun favori pour le moment. Allez donner un 👍 à vos œuvres préférées !")
    else:
        for p in sorted(prefs, key=lambda x: x.get('date', ''), reverse=True):
            with st.container(border=True):
                st.markdown(f"**{p.get('category')}** : {p.get('title')} *({p.get('author')})*")
                st.caption(f"Sauvegardé le {p.get('date')}")
