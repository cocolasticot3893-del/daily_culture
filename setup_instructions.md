# Guide d'Installation — Le Banquet des Muses

## Architecture

```
daily_culture.py    → Interface Streamlit (UI, prompts DeepSeek, moteur média)
database.py         → Couche de persistance Supabase (CRUD)
schema.sql          → Script SQL pour créer les tables
```

---

## 1. Créer un Projet Supabase (Gratuit)

1. Va sur [https://supabase.com](https://supabase.com) et crée un compte.
2. Crée un **nouveau projet** :
   - **Name** : `banquet-des-muses` (ou le nom de ton choix)
   - **Database Password** : Choisis un mot de passe fort
   - **Region** : Choisis `EU West` (France) ou la plus proche
   - **Pricing Plan** : **Free** (500 Mo, API illimitée)
3. Attends la fin du provisioning (< 2 minutes).

---

## 2. Créer les Tables

1. Dans le dashboard Supabase, va dans **SQL Editor**.
2. Clique sur **New Query**.
3. Copie-colle l'intégralité du fichier [`schema.sql`](schema.sql).
4. Clique sur **Run**.
5. Vérifie que les 3 tables sont créées : va dans **Table Editor** → tu dois voir `seen_history`, `user_preferences`, `daily_editions`.

---

## 3. Récupérer les Clés API Supabase

1. Dans le dashboard Supabase, va dans **Project Settings** → **API**.
2. Copie les deux valeurs suivantes :

| Secret Streamlit | Valeur |
|-----------------|--------|
| `SUPABASE_URL` | **Project URL** (ex: `https://xxxxx.supabase.co`) |
| `SUPABASE_KEY` | **anon public** (ou **service_role** pour éviter RLS) |

> ⚠️ **Recommandation** : Utilise la clé `service_role` pour une application mono-utilisateur comme la tienne. Elle a tous les droits. Pour une app multi-utilisateurs, utilise la clé `anon` avec Row Level Security (RLS).

---

## 4. Obtenir une Clé DeepSeek

1. Va sur [https://platform.deepseek.com](https://platform.deepseek.com).
2. Crée un compte et génère une **API Key**.
3. Copie la clé (commence par `sk-...`).

---

## 5. Configurer les Secrets Streamlit

### Pour Streamlit Cloud (Déploiement)

1. Va sur [https://share.streamlit.io](https://share.streamlit.io).
2. Sélectionne ton dépôt.
3. Dans **Settings** → **Secrets**, ajoute :

```toml
DEEPSEEK_API_KEY = "sk-ta_cle_deepseek_ici"

SUPABASE_URL = "https://xxxxx.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.ta_cle_supabase_ici"
```

### Pour le développement local (`.streamlit/secrets.toml`)

Crée un fichier `.streamlit/secrets.toml` à la racine du projet :

```toml
DEEPSEEK_API_KEY = "sk-ta_cle_deepseek_ici"

SUPABASE_URL = "https://xxxxx.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.ta_cle_supabase_ici"
```

> ⚠️ Ajoute `.streamlit/` au `.gitignore` pour ne pas exposer tes clés.

---

## 6. Installer les Dépendances

```bash
pip install -r requirements.txt
```

Le fichier [`requirements.txt`](requirements.txt) contient :
- `streamlit` (≥ 1.35.0)
- `requests` (≥ 2.31.0)

> Aucun besoin d'installer `supabase-py` : le client utilise directement l'API REST via `requests`.

---

## 7. Lancer l'Application

```bash
streamlit run daily_culture.py
```

L'application s'ouvre sur `http://localhost:8501`.

---

## 8. Automatisation avec MacroDroid

Pour que l'édition soit prête à 8h00 chaque matin :

1. Configure un réveil externe (MacroDroid sur Android, ou crontab sur serveur).
2. La première requête HTTP à l'URL Streamlit déclenchera la génération complète.
3. Les lectures suivantes (même dans la journée) liront directement le cache Supabase, sans appel DeepSeek redondant.

---

## 9. Vérifier le Bon Fonctionnement

| Fonctionnalité | Comment vérifier |
|---------------|-----------------|
| Persistance | Génère une édition → redémarre l'app → l'onglet Aujourd'hui charge depuis le cache Supabase |
| Anti-répétition | Vérifie la table `seen_history` dans Supabase Table Editor : les titres doivent s'accumuler |
| Favoris | Clique sur "J'aime" → va dans l'onglet Favoris → le vote est listé |
| Recommandation | Vote "J'aime" plusieurs fois dans une catégorie → le lendemain, DeepSeek reçoit une orientation |

---

## Dépannage

### "Clés manquantes dans les Secrets Streamlit"
→ Vérifie que les 3 secrets sont bien présents :
- `DEEPSEEK_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_KEY`

### L'application est lente
→ C'est normal pour la **première édition du jour** (14 appels DeepSeek + 1 citation + 1 MET Museum).
→ Les jours suivants, tout est lu depuis le cache Supabase (instantané).

### Les images ne s'affichent pas
→ Vérifie dans Supabase Table Editor que les URLs d'images sont bien stockées.
→ Les catégories Architecture et Sculpture n'ont délibérément **pas** d'images IA (placeholder élégant à la place).

### Erreur "relation does not exist"
→ Tu n'as pas exécuté le [`schema.sql`](schema.sql) dans Supabase. Va dans **SQL Editor** et lance le script.
