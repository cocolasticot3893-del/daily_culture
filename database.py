"""
database.py — Couche de persistance Supabase pour Le Banquet des Muses.

Remplace définitivement StorageManager (JSONBin.io + fichiers locaux).
Utilise l'API REST Supabase (PostgreSQL) via requêtes HTTP directes.

Tables :
  - seen_history       : Blacklist absolue anti-répétition (UNIQUE category+title)
  - user_preferences   : J'aime / Bof pour le profilage
  - daily_editions     : Cache des éditions quotidiennes (évite les appels DeepSeek redondants)
"""

from __future__ import annotations

import datetime
from collections import Counter
from typing import Optional

import requests
import streamlit as st


class SupabaseClient:
    """Client de persistance cloud via Supabase (PostgreSQL).

    Utilise l'API REST de Supabase avec authentification par clé.
    Toutes les méthodes gèrent les timeouts et retournent des valeurs
    par défaut sûres en cas d'erreur réseau.
    """

    def __init__(self) -> None:
        self.url: str = st.secrets["SUPABASE_URL"].rstrip("/")
        self.key: str = st.secrets["SUPABASE_KEY"]
        self._session = requests.Session()
        self._session.headers.update({
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        })

    # ------------------------------------------------------------------
    # Requêtes REST génériques
    # ------------------------------------------------------------------
    def _get(self, table: str, params: dict | None = None) -> list[dict]:
        """Requête SELECT. Retourne une liste de dictionnaires."""
        url = f"{self.url}/rest/v1/{table}"
        try:
            resp = self._session.get(url, params=params or {}, timeout=10)
            resp.raise_for_status()
            return resp.json() or []
        except requests.RequestException:
            return []

    def _post(self, table: str, data: dict) -> bool:
        """Requête INSERT. Retourne True si succès."""
        url = f"{self.url}/rest/v1/{table}"
        try:
            resp = self._session.post(url, json=data, timeout=10)
            resp.raise_for_status()
            return True
        except requests.RequestException:
            return False

    def _upsert(self, table: str, data: dict) -> bool:
        """Insert ou ignore si conflit (résolution 'ignore-duplicates')."""
        url = f"{self.url}/rest/v1/{table}"
        headers = {
            **self._session.headers,
            "Prefer": "resolution=ignore-duplicates,return=minimal",
        }
        try:
            resp = self._session.post(url, json=data, headers=headers, timeout=10)
            resp.raise_for_status()
            return True
        except requests.RequestException:
            return False

    # ------------------------------------------------------------------
    # seen_history  —  Blacklist anti-répétition
    # ------------------------------------------------------------------
    def get_seen_titles(self, category: str) -> list[str]:
        """Retourne tous les titres déjà vus dans une catégorie donnée."""
        params = {
            "select": "title",
            "category": f"eq.{category}",
            "limit": 1000,
            "order": "date_seen.desc",
        }
        rows = self._get("seen_history", params)
        return [r["title"] for r in rows if r.get("title")]

    def add_to_seen(
        self,
        category: str,
        title: str,
        author: str = "",
        date_seen: str | None = None,
    ) -> bool:
        """Enregistre une œuvre dans l'historique (ignore les doublons)."""
        if not title or title == "Inconnu":
            return False
        data = {
            "category": category,
            "title": title,
            "author": author or "",
            "date_seen": date_seen or datetime.date.today().isoformat(),
        }
        return self._upsert("seen_history", data)

    # ------------------------------------------------------------------
    # user_preferences  —  J'aime / Bof
    # ------------------------------------------------------------------
    def get_preferences(self) -> list[dict]:
        """Retourne toutes les préférences utilisateur."""
        return self._get("user_preferences", {"limit": 1000, "order": "date_str.desc"})

    def save_preference(
        self,
        category: str,
        title: str,
        author: str,
        liked: bool,
        date_str: str,
    ) -> bool:
        """Enregistre un vote J'aime (True) ou Bof (False)."""
        data = {
            "category": category,
            "title": title,
            "author": author or "",
            "liked": liked,
            "date_str": date_str,
        }
        return self._post("user_preferences", data)

    # ------------------------------------------------------------------
    # Profilage de recommandation
    # ------------------------------------------------------------------
    def get_liked_genres(self) -> list[str]:
        """Analyse les J'aime pour identifier les 5 catégories préférées."""
        rows = self._get(
            "user_preferences",
            {"select": "category", "liked": "eq.true", "limit": 200},
        )
        counter = Counter(r["category"] for r in rows if r.get("category"))
        return [cat for cat, _ in counter.most_common(5)]

    def get_disliked_authors(self) -> list[str]:
        """Analyse les Bof pour identifier les auteurs à éviter."""
        rows = self._get(
            "user_preferences",
            {"select": "author", "liked": "eq.false", "limit": 200},
        )
        authors = [r["author"] for r in rows if r.get("author")]
        return list(set(authors))

    # ------------------------------------------------------------------
    # daily_editions  —  Cache pour éviter les appels DeepSeek redondants
    # ------------------------------------------------------------------
    def get_edition(self, edition_date: str) -> Optional[dict]:
        """Récupère une édition mise en cache. Retourne None si absente."""
        params = {
            "select": "edition_data",
            "edition_date": f"eq.{edition_date}",
            "limit": 1,
        }
        rows = self._get("daily_editions", params)
        if rows and rows[0].get("edition_data"):
            return rows[0]["edition_data"]
        return None

    def save_edition(self, edition_date: str, edition_data: dict) -> bool:
        """Sauvegarde ou met à jour une édition (merging sur conflit)."""
        url = f"{self.url}/rest/v1/daily_editions"
        headers = {
            **self._session.headers,
            "Prefer": "resolution=merge-duplicates,return=minimal",
        }
        data = {"edition_date": edition_date, "edition_data": edition_data}
        try:
            resp = self._session.post(url, json=data, headers=headers, timeout=10)
            resp.raise_for_status()
            return True
        except requests.RequestException:
            return False
