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
import logging
from collections import Counter
from typing import Any, Optional

import requests
import streamlit as st

logger = logging.getLogger("banquet_des_muses")


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
    def _get(self, table: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Requête SELECT. Retourne une liste de dictionnaires.

        Args:
            table: Nom de la table Supabase.
            params: Paramètres de requête (filtres, limites, etc.).

        Returns:
            Liste de dictionnaires, ou [] en cas d'erreur.
        """
        url = f"{self.url}/rest/v1/{table}"
        try:
            resp = self._session.get(url, params=params or {}, timeout=10)
            resp.raise_for_status()
            return resp.json() or []
        except requests.RequestException as exc:
            logger.error("Supabase GET %s échoué : %s", table, exc)
            return []

    def _post(self, table: str, data: dict[str, Any]) -> bool:
        """Requête INSERT. Retourne True si succès.

        Args:
            table: Nom de la table Supabase.
            data: Dictionnaire des données à insérer.

        Returns:
            True si l'insertion a réussi, False sinon.
        """
        url = f"{self.url}/rest/v1/{table}"
        try:
            resp = self._session.post(url, json=data, timeout=10)
            resp.raise_for_status()
            return True
        except requests.RequestException as exc:
            logger.error("Supabase POST %s échoué : %s", table, exc)
            return False

    def _upsert(self, table: str, data: dict[str, Any]) -> bool:
        """Insert ou ignore si conflit (résolution 'ignore-duplicates').

        Args:
            table: Nom de la table Supabase.
            data: Dictionnaire des données à insérer.

        Returns:
            True si l'opération a réussi, False sinon.
        """
        url = f"{self.url}/rest/v1/{table}"
        headers: dict[str, str] = {
            **self._session.headers,
            "Prefer": "resolution=ignore-duplicates,return=minimal",
        }
        try:
            resp = self._session.post(url, json=data, headers=headers, timeout=10)
            resp.raise_for_status()
            return True
        except requests.RequestException as exc:
            logger.error("Supabase UPSERT %s échoué : %s", table, exc)
            return False

    # ------------------------------------------------------------------
    # seen_history  —  Blacklist anti-répétition
    # ------------------------------------------------------------------
    def get_seen_titles(self, category: str) -> list[str]:
        """Retourne tous les titres déjà vus dans une catégorie donnée.

        Args:
            category: Nom de la catégorie.

        Returns:
            Liste des titres (strings), ou [] si aucun.
        """
        params: dict[str, Any] = {
            "select": "title",
            "category": f"eq.{category}",
            "limit": 1000,
            "order": "date_seen.desc",
        }
        rows: list[dict[str, Any]] = self._get("seen_history", params)
        return [r["title"] for r in rows if r.get("title")]

    def add_to_seen(
        self,
        category: str,
        title: str,
        author: str = "",
        date_seen: str | None = None,
    ) -> bool:
        """Enregistre une œuvre dans l'historique (ignore les doublons).

        Args:
            category: Nom de la catégorie.
            title: Titre de l'oeuvre.
            author: Auteur de l'oeuvre (optionnel).
            date_seen: Date au format "YYYY-MM-DD" (défaut: aujourd'hui).

        Returns:
            True si l'enregistrement a réussi, False sinon.
        """
        if not title or title == "Inconnu":
            return False
        data: dict[str, Any] = {
            "category": category,
            "title": title,
            "author": author or "",
            "date_seen": date_seen or datetime.date.today().isoformat(),
        }
        return self._upsert("seen_history", data)

    # ------------------------------------------------------------------
    # user_preferences  —  J'aime / Bof
    # ------------------------------------------------------------------
    def get_preferences(self) -> list[dict[str, Any]]:
        """Retourne toutes les préférences utilisateur.

        Returns:
            Liste des dictionnaires de préférences, ou [].
        """
        return self._get("user_preferences", {"limit": 1000, "order": "date_str.desc"})

    def save_preference(
        self,
        category: str,
        title: str,
        author: str,
        liked: bool,
        date_str: str,
    ) -> bool:
        """Enregistre un vote J'aime (True) ou Bof (False).

        Args:
            category: Nom de la catégorie.
            title: Titre de l'oeuvre.
            author: Auteur de l'oeuvre.
            liked: True pour J'aime, False pour Bof.
            date_str: Date au format "YYYY-MM-DD".

        Returns:
            True si l'enregistrement a réussi, False sinon.
        """
        data: dict[str, Any] = {
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
        """Analyse les J'aime pour identifier les 5 catégories préférées.

        Returns:
            Liste des 5 catégories les plus aimées, ou [].
        """
        rows: list[dict[str, Any]] = self._get(
            "user_preferences",
            {"select": "category", "liked": "eq.true", "limit": 200},
        )
        counter: Counter[str] = Counter(r["category"] for r in rows if r.get("category"))
        return [cat for cat, _ in counter.most_common(5)]

    def get_disliked_authors(self) -> list[str]:
        """Analyse les Bof pour identifier les auteurs à éviter.

        Returns:
            Liste des auteurs non aimés (sans doublons), ou [].
        """
        rows: list[dict[str, Any]] = self._get(
            "user_preferences",
            {"select": "author", "liked": "eq.false", "limit": 200},
        )
        authors: list[str] = [r["author"] for r in rows if r.get("author")]
        return list(set(authors))

    # ------------------------------------------------------------------
    # daily_editions  —  Cache pour éviter les appels DeepSeek redondants
    # ------------------------------------------------------------------
    def get_edition(self, edition_date: str) -> Optional[dict[str, Any]]:
        """Récupère une édition mise en cache.

        Args:
            edition_date: Date au format "YYYY-MM-DD".

        Returns:
            Dictionnaire de l'édition, ou None si absente.
        """
        params: dict[str, Any] = {
            "select": "edition_data",
            "edition_date": f"eq.{edition_date}",
            "limit": 1,
        }
        rows: list[dict[str, Any]] = self._get("daily_editions", params)
        if rows and rows[0].get("edition_data"):
            return rows[0]["edition_data"]
        return None

    def save_edition(self, edition_date: str, edition_data: dict[str, Any]) -> bool:
        """Sauvegarde ou met à jour une édition (merging sur conflit).

        Args:
            edition_date: Date au format "YYYY-MM-DD".
            edition_data: Dictionnaire complet de l'édition.

        Returns:
            True si la sauvegarde a réussi, False sinon.
        """
        url = f"{self.url}/rest/v1/daily_editions"
        headers: dict[str, str] = {
            **self._session.headers,
            "Prefer": "resolution=merge-duplicates,return=minimal",
        }
        data: dict[str, Any] = {"edition_date": edition_date, "edition_data": edition_data}
        try:
            resp = self._session.post(url, json=data, headers=headers, timeout=10)
            resp.raise_for_status()
            return True
        except requests.RequestException as exc:
            logger.error("Supabase save_edition %s échoué : %s", edition_date, exc)
            return False
