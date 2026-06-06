"""
database.py — Couche de persistance Supabase pour Le Banquet des Muses.

Remplace définitivement StorageManager (JSONBin.io + fichiers locaux).
Utilise l'API REST Supabase (PostgreSQL) via requêtes HTTP directes.

Tables :
  - seen_history       : Blacklist absolue anti-répétition (UNIQUE category+title)
  - user_preferences   : J'aime / Bof pour le profilage
  - daily_editions     : Cache des éditions quotidiennes (évite les appels DeepSeek redondants)

Résilience :
  - Circuit Breaker : Si Supabase est inaccessible, bascule en mode dégradé
    (mémoire locale) sans erreur fatale à l'écran.
  - Timeout unifié configurable via DB_TIMEOUT.
"""

from __future__ import annotations

import datetime
import logging
import time
from collections import Counter
from typing import Any, Optional

import requests
import streamlit as st

logger = logging.getLogger("banquet_des_muses")

# ------------------------------------------------------------------
# Configuration de résilience (importée depuis config.py)
# ------------------------------------------------------------------
from config import (  # noqa: E402 — import après logger
    DB_TIMEOUT,
    CIRCUIT_BREAKER_COOLDOWN,
    CIRCUIT_BREAKER_THRESHOLD,
)


class SupabaseClient:
    """Client de persistance cloud via Supabase (PostgreSQL).

    Utilise l'API REST de Supabase avec authentification par clé.
    Toutes les méthodes gèrent les timeouts et retournent des valeurs
    par défaut sûres en cas d'erreur réseau.

    Circuit Breaker intégré :
      - CLOSED   : fonctionnement normal
      - OPEN     : toutes les requêtes sont court-circuitées (fallback local)
      - HALF_OPEN : une requête test est autorisée après cooldown
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

        # Circuit Breaker state
        self._failure_count: int = 0
        self._last_failure_time: float = 0.0
        self._circuit_open: bool = False

        # Fallback : stockage local en mémoire (mode dégradé)
        self._local_seen: list[dict[str, Any]] = []
        self._local_prefs: list[dict[str, Any]] = []
        self._local_editions: dict[str, dict[str, Any]] = {}
        self._degraded: bool = False

    # ------------------------------------------------------------------
    # Circuit Breaker interne
    # ------------------------------------------------------------------
    def _is_circuit_open(self) -> bool:
        """Vérifie si le circuit breaker est OPEN.

        Returns:
            True si les requêtes doivent être court-circuitées.
        """
        if not self._circuit_open:
            return False
        # HALF_OPEN : on autorise une tentative après cooldown
        if time.monotonic() - self._last_failure_time > CIRCUIT_BREAKER_COOLDOWN:
            self._circuit_open = False
            self._failure_count = 0
            logger.info("Circuit Breaker → HALF_OPEN (tentative de reconnexion)")
            return False
        return True

    def _record_failure(self) -> None:
        """Enregistre un échec et ouvre le circuit si le seuil est atteint."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= CIRCUIT_BREAKER_THRESHOLD:
            self._circuit_open = True
            self._degraded = True
            logger.critical(
                "Circuit Breaker → OPEN après %d échecs consécutifs. "
                "Bascule en mode dégradé (mémoire locale).",
                self._failure_count,
            )

    def _record_success(self) -> None:
        """Réinitialise le compteur d'échecs après un succès."""
        if self._failure_count > 0:
            self._failure_count = 0
            self._circuit_open = False
            if self._degraded:
                logger.info("Circuit Breaker → CLOSED (connexion Supabase rétablie)")
                self._degraded = False

    # ------------------------------------------------------------------
    # Requêtes REST génériques (avec Circuit Breaker)
    # ------------------------------------------------------------------
    def _get(self, table: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Requête SELECT. Retourne une liste de dictionnaires.

        Si le circuit breaker est OPEN, retourne [] immédiatement.

        Args:
            table: Nom de la table Supabase.
            params: Paramètres de requête (filtres, limites, etc.).

        Returns:
            Liste de dictionnaires, ou [] en cas d'erreur/circuit ouvert.
        """
        if self._is_circuit_open():
            logger.warning("Circuit OPEN — GET %s court-circuité", table)
            return []
        url = f"{self.url}/rest/v1/{table}"
        try:
            resp = self._session.get(url, params=params or {}, timeout=DB_TIMEOUT)
            resp.raise_for_status()
            self._record_success()
            return resp.json() or []
        except requests.RequestException as exc:
            logger.error("Supabase GET %s échoué : %s", table, exc)
            self._record_failure()
            return []

    def _post(self, table: str, data: dict[str, Any]) -> bool:
        """Requête INSERT. Retourne True si succès.

        Si le circuit breaker est OPEN, stocke en mémoire locale.

        Args:
            table: Nom de la table Supabase.
            data: Dictionnaire des données à insérer.

        Returns:
            True si l'insertion a réussi (cloud ou local), False sinon.
        """
        if self._is_circuit_open():
            logger.warning("Circuit OPEN — POST %s stocké en local", table)
            self._store_local(table, data)
            return True  # Mode dégradé : on ne bloque pas l'utilisateur
        url = f"{self.url}/rest/v1/{table}"
        try:
            resp = self._session.post(url, json=data, timeout=DB_TIMEOUT)
            resp.raise_for_status()
            self._record_success()
            return True
        except requests.RequestException as exc:
            logger.error("Supabase POST %s échoué : %s", table, exc)
            self._record_failure()
            # Fallback local immédiat
            self._store_local(table, data)
            return True

    def _upsert(self, table: str, data: dict[str, Any]) -> bool:
        """Insert ou ignore si conflit (résolution 'ignore-duplicates').

        Si le circuit breaker est OPEN, stocke en mémoire locale.

        Args:
            table: Nom de la table Supabase.
            data: Dictionnaire des données à insérer.

        Returns:
            True si l'opération a réussi (cloud ou local), False sinon.
        """
        if self._is_circuit_open():
            logger.warning("Circuit OPEN — UPSERT %s stocké en local", table)
            self._store_local(table, data)
            return True
        url = f"{self.url}/rest/v1/{table}"
        headers: dict[str, str] = {
            **self._session.headers,
            "Prefer": "resolution=ignore-duplicates,return=minimal",
        }
        try:
            resp = self._session.post(url, json=data, headers=headers, timeout=DB_TIMEOUT)
            resp.raise_for_status()
            self._record_success()
            return True
        except requests.RequestException as exc:
            logger.error("Supabase UPSERT %s échoué : %s", table, exc)
            self._record_failure()
            self._store_local(table, data)
            return True

    # ------------------------------------------------------------------
    # Stockage local de fallback (mode dégradé)
    # ------------------------------------------------------------------
    def _store_local(self, table: str, data: dict[str, Any]) -> None:
        """Stocke une entrée dans le fallback mémoire local.

        Args:
            table: Nom de la table logique.
            data: Données à stocker.
        """
        if table == "seen_history":
            # Évite les doublons locaux sur (category, title)
            existing = any(
                s.get("category") == data.get("category")
                and s.get("title") == data.get("title")
                for s in self._local_seen
            )
            if not existing:
                self._local_seen.append(data)
        elif table == "user_preferences":
            self._local_prefs.append(data)
        elif table == "daily_editions":
            self._local_editions[data.get("edition_date", "")] = data.get(
                "edition_data", {}
            )

    # ------------------------------------------------------------------
    # seen_history  —  Blacklist anti-répétition
    # ------------------------------------------------------------------
    def get_seen_titles(self, category: str) -> list[str]:
        """Retourne tous les titres déjà vus dans une catégorie donnée.

        Pour la catégorie 'Citation', 'title' contient le texte intégral
        de la citation (UNIQUE). Pour les autres catégories, 'title'
        contient le titre de l'oeuvre.

        En mode dégradé, utilise le stockage local mémoire.

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
        # Fallback local si le cloud est vide (mode dégradé)
        if not rows and self._degraded:
            local_rows = [
                s for s in self._local_seen
                if s.get("category") == category
            ]
            local_rows.sort(key=lambda x: x.get("date_seen", ""), reverse=True)
            return [r["title"] for r in local_rows if r.get("title")]
        return [r["title"] for r in rows if r.get("title")]

    def get_seen_authors(self, category: str) -> list[str]:
        """Retourne tous les auteurs déjà vus dans une catégorie donnée.

        Pour la catégorie 'Citation', 'author' contient le nom de l'auteur.
        Pour les autres catégories, 'author' contient l'auteur de l'oeuvre.

        En mode dégradé, utilise le stockage local mémoire.

        Args:
            category: Nom de la catégorie.

        Returns:
            Liste des auteurs (strings), ou [] si aucun.
        """
        params: dict[str, Any] = {
            "select": "author",
            "category": f"eq.{category}",
            "limit": 1000,
            "order": "date_seen.desc",
        }
        rows: list[dict[str, Any]] = self._get("seen_history", params)
        if not rows and self._degraded:
            local_rows = [
                s for s in self._local_seen
                if s.get("category") == category
            ]
            local_rows.sort(key=lambda x: x.get("date_seen", ""), reverse=True)
            return [r["author"] for r in local_rows if r.get("author")]
        return [r["author"] for r in rows if r.get("author")]

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

        En mode dégradé, utilise le stockage local mémoire.

        Returns:
            Liste des dictionnaires de préférences, ou [].
        """
        rows = self._get("user_preferences", {"limit": 1000, "order": "date_str.desc"})
        if not rows and self._degraded:
            return sorted(
                self._local_prefs,
                key=lambda x: x.get("date_str", ""),
                reverse=True,
            )
        return rows

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

        En mode dégradé, utilise le stockage local mémoire.

        Returns:
            Liste des 5 catégories les plus aimées, ou [].
        """
        rows: list[dict[str, Any]] = self._get(
            "user_preferences",
            {"select": "category", "liked": "eq.true", "limit": 200},
        )
        if not rows and self._degraded:
            rows = [p for p in self._local_prefs if p.get("liked")]
        counter: Counter[str] = Counter(r["category"] for r in rows if r.get("category"))
        return [cat for cat, _ in counter.most_common(5)]

    def get_disliked_authors(self) -> list[str]:
        """Analyse les Bof pour identifier les auteurs à éviter.

        En mode dégradé, utilise le stockage local mémoire.

        Returns:
            Liste des auteurs non aimés (sans doublons), ou [].
        """
        rows: list[dict[str, Any]] = self._get(
            "user_preferences",
            {"select": "author", "liked": "eq.false", "limit": 200},
        )
        if not rows and self._degraded:
            rows = [p for p in self._local_prefs if not p.get("liked")]
        authors: list[str] = [r["author"] for r in rows if r.get("author")]
        return list(set(authors))

    # ------------------------------------------------------------------
    # daily_editions  —  Cache pour éviter les appels DeepSeek redondants
    # ------------------------------------------------------------------
    def get_edition(self, edition_date: str) -> Optional[dict[str, Any]]:
        """Récupère une édition mise en cache.

        En mode dégradé, utilise le stockage local mémoire.

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
        # Fallback local
        if self._degraded and edition_date in self._local_editions:
            return self._local_editions[edition_date]
        return None

    def save_edition(self, edition_date: str, edition_data: dict[str, Any]) -> bool:
        """Sauvegarde ou met à jour une édition (merging sur conflit).

        En mode dégradé, stocke en mémoire locale.

        Args:
            edition_date: Date au format "YYYY-MM-DD".
            edition_data: Dictionnaire complet de l'édition.

        Returns:
            True si la sauvegarde a réussi, False sinon.
        """
        if self._is_circuit_open():
            logger.warning("Circuit OPEN — save_edition %s stocké en local", edition_date)
            self._local_editions[edition_date] = edition_data
            return True
        url = f"{self.url}/rest/v1/daily_editions"
        headers: dict[str, str] = {
            **self._session.headers,
            "Prefer": "resolution=merge-duplicates,return=minimal",
        }
        data: dict[str, Any] = {"edition_date": edition_date, "edition_data": edition_data}
        try:
            resp = self._session.post(url, json=data, headers=headers, timeout=DB_TIMEOUT)
            resp.raise_for_status()
            self._record_success()
            return True
        except requests.RequestException as exc:
            logger.error("Supabase save_edition %s échoué : %s", edition_date, exc)
            self._record_failure()
            # Fallback local
            self._local_editions[edition_date] = edition_data
            return True
