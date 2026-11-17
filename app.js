"use strict";

const CATEGORIES = [
  { id: "philo", name: "Philosophie & Epistemologie", icon: "ðŸ›", angle: "concepts fondateurs, logique, ethique, philosophie des sciences ou penseurs non occidentaux" },
  { id: "beaux-arts", name: "Beaux-Arts & Histoire de l'Art", icon: "ðŸŽ¨", angle: "ruptures picturales, composition, technique, iconologie et mouvements artistiques" },
  { id: "litterature", name: "Litterature Mondiale", icon: "ðŸ“–", angle: "oeuvres majeures, narration, courants litteraires mondiaux et figures oubliees" },
  { id: "architecture", name: "Architecture & Urbanisme", icon: "ðŸ“", angle: "ingenierie spatiale, materiaux, typologies architecturales et urbanisme" },
  { id: "musique", name: "Musique Savante & Jazz", icon: "ðŸŽ¼", angle: "contrepoint, harmonie, formes musicales, histoire du jazz et acoustique" },
  { id: "cinema", name: "Cinema d'Auteur & Montage", icon: "ðŸŽž", angle: "grammaire cinematographique, montage, mise en scene et mouvements mondiaux" },
  { id: "sciences", name: "Histoire des Sciences & Idees", icon: "ðŸ”­", angle: "paradigmes scientifiques, decouvertes fondamentales et controverses historiques" },
  { id: "mythologie", name: "Mythologie & Anthropologie", icon: "ðŸ—¿", angle: "structures symboliques, mythes compares, rituels et anthropologie culturelle" },
  { id: "geopolitique", name: "Histoire & Geopolitique", icon: "ðŸ§­", angle: "tournants historiques, civilisations, diplomatie et dynamiques spatiales" },
  { id: "theatre", name: "Theatre & Dramaturgie", icon: "ðŸŽ­", angle: "tragedie, dramaturgie, mise en scene et evolution de l'espace scenique" },
  { id: "photographie", name: "Photographie & Image", icon: "ðŸ“·", angle: "composition photographique, histoire du medium, reportage et esthetique visuelle" },
  { id: "design", name: "Design & Arts Decoratifs", icon: "ðŸª‘", angle: "design industriel, ergonomie, Bauhaus, artisanat et culture materielle" },
  { id: "numerique", name: "Arts Numeriques & Esthetique IA", icon: "ðŸ§¬", angle: "art generatif, cybernetique, nouveaux medias et esthetique computationnelle" },
  { id: "poesie", name: "Poesie & Rhetorique", icon: "âœ’", angle: "prosodie, figures de style, poetique comparee et traditions orales" }
];

const DB_NAME = "DailyCultureDB";
const DB_VERSION = 1;
const STORE_ENTRIES = "entries";

const SETTINGS_KEYS = {
  API_KEY: "dc_gemini_api_key",
  MODEL: "dc_gemini_model",
  CUSTOM_MODEL: "dc_gemini_custom_model",
  DEPTH: "dc_editorial_depth"
};

let dbInstance = null;
let allEntries = [];
let currentEntry = null;

function openDatabase() {
  return new Promise((resolve, reject) => {
    if (dbInstance) {
      resolve(dbInstance);
      return;
    }
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(STORE_ENTRIES)) {
        const store = db.createObjectStore(STORE_ENTRIES, { keyPath: "id" });
        store.createIndex("createdAt", "createdAt", { unique: false });
        store.createIndex("categoryId", "categoryId", { unique: false });
      }
    };
    request.onsuccess = (event) => {
      dbInstance = event.target.result;
      resolve(dbInstance);
    };
    request.onerror = (event) => reject(event.target.error);
  });
}

async function getAllEntries() {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_ENTRIES, "readonly");
    const store = tx.objectStore(STORE_ENTRIES);
    const req = store.getAll();
    req.onsuccess = () => {
      const sorted = (req.result || []).sort((a, b) => b.createdAt - a.createdAt);
      resolve(sorted);
    };
    req.onerror = () => reject(req.error);
  });
}

async function saveEntry(entry) {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_ENTRIES, "readwrite");
    const store = tx.objectStore(STORE_ENTRIES);
    const req = store.put(entry);
    req.onsuccess = () => resolve(entry);
    req.onerror = () => reject(req.error);
  });
}

async function deleteEntryById(id) {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_ENTRIES, "readwrite");
    const store = tx.objectStore(STORE_ENTRIES);
    const req = store.delete(id);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

function getSettings() {
  const modelChoice = localStorage.getItem(SETTINGS_KEYS.MODEL) || "gemini-2.5-flash";
  const customModel = localStorage.getItem(SETTINGS_KEYS.CUSTOM_MODEL) || "";
  return {
    apiKey: (localStorage.getItem(SETTINGS_KEYS.API_KEY) || "").trim(),
    modelChoice,
    customModel,
    activeModel: modelChoice === "CUSTOM" && customModel.trim() ? customModel.trim() : modelChoice,
    depth: localStorage.getItem(SETTINGS_KEYS.DEPTH) || "dense"
  };
}

function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.remove("show"), 2600);
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function getTodayDateString() {
  return new Date().toISOString().slice(0, 10);
}

function computeStreak(entries) {
  if (!entries.length) return 0;
  const uniqueDays = [...new Set(entries.map((e) => e.dateKey))].sort().reverse();
  const today = getTodayDateString();
  const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);

  if (uniqueDays[0] !== today && uniqueDays[0] !== yesterday) {
    return 0;
  }

  let streak = 1;
  for (let i = 0; i < uniqueDays.length - 1; i++) {
    const d1 = new Date(uniqueDays[i] + "T00:00:00Z");
    const d2 = new Date(uniqueDays[i + 1] + "T00:00:00Z");
    const diffDays = Math.round((d1 - d2) / 86400000);
    if (diffDays === 1) {
      streak++;
    } else {
      break;
    }
  }
  return streak;
}

function selectWeightedCategory(entries) {
  const counts = {};
  for (const cat of CATEGORIES) counts[cat.id] = 0;
  for (const item of entries) {
    if (counts[item.categoryId] !== undefined) {
      counts[item.categoryId]++;
    }
  }

  const weights = CATEGORIES.map((cat) => {
    const n = counts[cat.id] || 0;
    return 1 / (1 + n * n);
  });

  const totalWeight = weights.reduce((acc, w) => acc + w, 0);
  let r = Math.random() * totalWeight;
  for (let i = 0; i < CATEGORIES.length; i++) {
    r -= weights[i];
    if (r <= 0) return CATEGORIES[i];
  }
  return CATEGORIES[0];
}

async function generateCulturalEntry(categoryObj) {
  const settings = getSettings();
  if (!settings.apiKey) {
    throw new Error("Cle API Gemini manquante. Renseignez-la dans l'onglet Config.");
  }

  const recentTitles = allEntries.slice(0, 35).map((e) => e.title);
  const exclusionClause = recentTitles.length
    ? `Sujets deja traites a exclure strictement : ${recentTitles.join(" | ")}.`
    : "Aucun sujet precedent.";

  const depthInstruction =
    settings.depth === "deep"
      ? "Redige une analyse approfondie, nuancee et academique (environ 130 a 180 mots par section principale), en explicitant les termes techniques rares entre parentheses."
      : "Redige une synthese dense, incisive et sans remplissage (environ 70 a 100 mots par section principale), en explicitant les termes techniques rares entre parentheses.";

  const prompt = `Tu es un erudit, historien des idees et critique d'art de niveau universitaire.
Genere une fiche de culture generale pointue dans le domaine : "${categoryObj.name}" (angle : ${categoryObj.angle}).
Evite les lieux communs scolaires : privilegie une oeuvre pivot, un concept precis, un tournant meconnu ou un penseur exigeant.
${depthInstruction}
${exclusionClause}
Langue : francais soutenu, precis et clair.`;

  const responseSchema = {
    type: "OBJECT",
    properties: {
      title: { type: "STRING", description: "Titre precis et evocateur du sujet" },
      hook: { type: "STRING", description: "Phrase d'accroche conceptuelle en une ligne" },
      era: { type: "STRING", description: "Epoque, siecle ou courant exact" },
      thesis: { type: "STRING", description: "These centrale et essence du concept ou de l'oeuvre" },
      context: { type: "STRING", description: "Genese historique, intellectuelle ou technique" },
      keyWorkAnalysis: { type: "STRING", description: "Analyse concrete d'une oeuvre, experience ou formulation pivot" },
      contemporaryResonance: { type: "STRING", description: "Pourquoi ce sujet eclaire les enjeux actuels" },
      quote: { type: "STRING", description: "Citation authentique et exacte liee au sujet" },
      quoteAuthor: { type: "STRING", description: "Auteur et oeuvre source de la citation" },
      furtherReading: { type: "STRING", description: "Reference primaire precise pour approfondir" },
      quiz: {
        type: "OBJECT",
        properties: {
          question: { type: "STRING", description: "Question de comprehension conceptuelle" },
          options: {
            type: "ARRAY",
            items: { type: "STRING" },
            description: "Exactement 3 propositions distinctes"
          },
          correctIndex: { type: "INTEGER", description: "Index 0, 1 ou 2 de la bonne reponse" },
          explanation: { type: "STRING", description: "Justification concise" }
        },
        required: ["question", "options", "correctIndex", "explanation"]
      },
      flashcards: {
        type: "ARRAY",
        description: "Exactement 3 flashcards atomiques optimisees pour Anki FSRS",
        items: {
          type: "OBJECT",
          properties: {
            front: { type: "STRING", description: "Question atomique courte" },
            back: { type: "STRING", description: "Reponse directe et concise" }
          },
          required: ["front", "back"]
        }
      }
    },
    required: [
      "title",
      "hook",
      "era",
      "thesis",
      "context",
      "keyWorkAnalysis",
      "contemporaryResonance",
      "quote",
      "quoteAuthor",
      "furtherReading",
      "quiz",
      "flashcards"
    ]
  };

  const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(
    settings.activeModel
  )}:generateContent?key=${encodeURIComponent(settings.apiKey)}`;

  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      contents: [{ role: "user", parts: [{ text: prompt }] }],
      generationConfig: {
        temperature: 0.85,
        responseMimeType: "application/json",
        responseSchema
      }
    })
  });

  if (!response.ok) {
    let errDetail = `Erreur HTTP ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson?.error?.message) {
        errDetail = errJson.error.message;
      }
    } catch (_) {}
    throw new Error(`API Gemini : ${errDetail}`);
  }

  const data = await response.json();
  const rawText = data?.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!rawText) {
    throw new Error("Reponse vide recue depuis l'API Gemini.");
  }

  const parsed = JSON.parse(rawText);
  const now = Date.now();

  return {
    id: `dc_${now}_${Math.random().toString(36).slice(2, 7)}`,
    dateKey: getTodayDateString(),
    createdAt: now,
    categoryId: categoryObj.id,
    categoryName: categoryObj.name,
    categoryIcon: categoryObj.icon,
    modelUsed: settings.activeModel,
    favorite: false,
    quizAnsweredIndex: null,
    ...parsed
  };
}

function buildAnkiTsv(entriesList) {
  const rows = [];
  for (const item of entriesList) {
    if (!Array.isArray(item.flashcards)) continue;
    const tag = `daily_culture::${item.categoryId}`;
    for (const fc of item.flashcards) {
      const front = `${fc.front} [${item.title}]`.replace(/\t|\r?\n/g, " ");
      const back = `${fc.back}`.replace(/\t|\r?\n/g, " ");
      rows.push(`${front}\t${back}\t${tag}`);
    }
  }
  return rows.join("\n");
}

function buildObsidianMarkdown(entry) {
  const fcLines = (entry.flashcards || [])
    .map((fc) => `- **Q :** ${fc.front}\n  - **R :** ${fc.back}`)
    .join("\n");

  return `---
title: "${entry.title.replace(/"/g, '\\"')}"
category: "${entry.categoryName}"
era: "${entry.era}"
date: ${entry.dateKey}
tags: [daily-culture, ${entry.categoryId}]
---

# ${entry.title}
> *${entry.hook}*

## These & Essence
${entry.thesis}

## Contexte & Genese
${entry.context}

## Oeuvre ou Concept Pivot
${entry.keyWorkAnalysis}

## Resonance Contemporaine
${entry.contemporaryResonance}

> "${entry.quote}" â€” **${entry.quoteAuthor}**

**Approfondissement :** ${entry.furtherReading}

## Flashcards Atomiques (FSRS)
${fcLines}
`;
}

function triggerFileDownload(filename, content, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function renderEntryCard(entry) {
  const container = document.getElementById("todayContent");
  if (!entry) {
    container.innerHTML = `
      <div class="card" style="text-align:center; padding:32px 18px;">
        <p style="font-size:1.05rem; font-weight:600; margin-bottom:8px;">Aucune fiche chargee</p>
        <p style="color:var(--text-muted); font-size:0.9rem; margin-bottom:18px;">
          Selectionnez un domaine ou lancez un tirage equilibre propulse par Gemini.
        </p>
        <button class="btn-primary" onclick="document.getElementById('generateBtn').click()">Generer ma fiche culturelle</button>
      </div>`;
    return;
  }

  const options = Array.isArray(entry.quiz?.options) ? entry.quiz.options.slice(0, 3) : [];
  const answered = entry.quizAnsweredIndex !== null && entry.quizAnsweredIndex !== undefined;

  const quizHtml = options
    .map((opt, idx) => {
      let cls = "quiz-option";
      if (answered) {
        if (idx === entry.quiz.correctIndex) cls += " correct";
        else if (idx === entry.quizAnsweredIndex) cls += " wrong";
      }
      return `<button class="${cls}" data-quiz-idx="${idx}" ${answered ? "disabled" : ""}>${escapeHtml(opt)}</button>`;
    })
    .join("");

  const flashcardsHtml = (entry.flashcards || [])
    .map(
      (fc, i) => `
      <div class="flashcard-item" onclick="this.classList.toggle('revealed')">
        <div class="flashcard-q">Q${i + 1}. ${escapeHtml(fc.front)}</div>
        <div class="flashcard-a">${escapeHtml(fc.back)}</div>
      </div>`
    )
    .join("");

  container.innerHTML = `
    <article class="card">
      <div class="meta-row">
        <span class="badge">${escapeHtml(entry.categoryIcon)} ${escapeHtml(entry.categoryName)}</span>
        <span class="era-tag">${escapeHtml(entry.era)} â€¢ ${escapeHtml(entry.dateKey)}</span>
      </div>

      <h1 class="article-title">${escapeHtml(entry.title)}</h1>
      <p class="article-hook">${escapeHtml(entry.hook)}</p>

      <div class="section-block">
        <div class="section-label">These & Essence</div>
        <p class="section-text">${escapeHtml(entry.thesis)}</p>
      </div>

      <div class="section-block">
        <div class="section-label">Contexte & Genese</div>
        <p class="section-text">${escapeHtml(entry.context)}</p>
      </div>

      <div class="section-block">
        <div class="section-label">Oeuvre ou Concept Pivot</div>
        <p class="section-text">${escapeHtml(entry.keyWorkAnalysis)}</p>
      </div>

      <div class="section-block">
        <div class="section-label">Resonance Contemporaine</div>
        <p class="section-text">${escapeHtml(entry.contemporaryResonance)}</p>
      </div>

      <blockquote class="quote-box">
        "${escapeHtml(entry.quote)}"
        <footer>â€” ${escapeHtml(entry.quoteAuthor)}</footer>
      </blockquote>

      <div class="section-block">
        <div class="section-label">Piste d'approfondissement</div>
        <p class="section-text" style="font-size:0.88rem; color:var(--text-muted);">${escapeHtml(entry.furtherReading)}</p>
      </div>

      <div class="section-block" style="margin-top:20px; padding-top:16px; border-top:1px solid var(--border);">
        <div class="section-label">Verification Conceptuelle</div>
        <p style="font-weight:600; font-size:0.94rem; margin-bottom:6px;">${escapeHtml(entry.quiz?.question)}</p>
        ${quizHtml}
        ${
          answered
            ? `<div class="quiz-explanation">${escapeHtml(entry.quiz?.explanation)}</div>`
            : ""
        }
      </div>

      <div class="section-block" style="margin-top:20px; padding-top:16px; border-top:1px solid var(--border);">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <div class="section-label" style="margin:0;">Flashcards Atomiques (toucher pour reveler)</div>
          <button id="copyAnkiBtn" class="btn-secondary btn-sm">Copier Anki TSV</button>
        </div>
        ${flashcardsHtml}
      </div>

      <div class="action-toolbar">
        <button id="toggleFavBtn" class="btn-secondary btn-sm">
          ${entry.favorite ? "â˜… Dans les favoris" : "â˜† Ajouter aux favoris"}
        </button>
        <button id="exportMdBtn" class="btn-secondary btn-sm">Export Obsidian (.md)</button>
        <button id="deleteEntryBtn" class="btn-secondary btn-sm" style="margin-left:auto; color:#ffa198;">Supprimer</button>
      </div>
    </article>`;

  container.querySelectorAll("[data-quiz-idx]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const idx = Number(btn.getAttribute("data-quiz-idx"));
      entry.quizAnsweredIndex = idx;
      await saveEntry(entry);
      renderEntryCard(entry);
    });
  });

  document.getElementById("toggleFavBtn").addEventListener("click", async () => {
    entry.favorite = !entry.favorite;
    await saveEntry(entry);
    await refreshState(entry.id);
    showToast(entry.favorite ? "Ajoute aux favoris" : "Retire des favoris");
  });

  document.getElementById("copyAnkiBtn").addEventListener("click", async () => {
    const tsv = buildAnkiTsv([entry]);
    try {
      await navigator.clipboard.writeText(tsv);
      showToast("Flashcards copiees au format Anki TSV");
    } catch (_) {
      triggerFileDownload(`${entry.dateKey}-${entry.categoryId}.tsv`, tsv, "text/tab-separated-values");
    }
  });

  document.getElementById("exportMdBtn").addEventListener("click", () => {
    const md = buildObsidianMarkdown(entry);
    const slug = entry.title
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 45);
    triggerFileDownload(`${entry.dateKey}-${slug || "fiche"}.md`, md, "text/markdown;charset=utf-8");
  });

  document.getElementById("deleteEntryBtn").addEventListener("click", async () => {
    await deleteEntryById(entry.id);
    currentEntry = null;
    await refreshState();
    showToast("Fiche supprimee");
  });
}

function renderLists() {
  const query = (document.getElementById("searchInput").value || "").toLowerCase().trim();
  const catFilter = document.getElementById("archiveCategoryFilter").value;

  const filtered = allEntries.filter((item) => {
    const matchCat = catFilter === "ALL" || item.categoryId === catFilter;
    if (!matchCat) return false;
    if (!query) return true;
    const blob = `${item.title} ${item.hook} ${item.thesis} ${item.categoryName} ${item.quoteAuthor}`.toLowerCase();
    return blob.includes(query);
  });

  const archivesContainer = document.getElementById("archivesList");
  if (!filtered.length) {
    archivesContainer.innerHTML = `<div class="card" style="text-align:center; color:var(--text-muted);">Aucune fiche correspondante.</div>`;
  } else {
    archivesContainer.innerHTML = filtered
      .map(
        (item) => `
        <div class="list-item" data-open-id="${item.id}">
          <div class="meta-row" style="margin-bottom:4px;">
            <span class="badge">${escapeHtml(item.categoryIcon)} ${escapeHtml(item.categoryName)}</span>
            <span class="era-tag">${escapeHtml(item.dateKey)} ${item.favorite ? "â˜…" : ""}</span>
          </div>
          <div class="list-item-title">${escapeHtml(item.title)}</div>
          <div class="list-item-sub">${escapeHtml(item.hook)}</div>
        </div>`
      )
      .join("");
  }

  const favs = allEntries.filter((e) => e.favorite);
  const favContainer = document.getElementById("favoritesList");
  if (!favs.length) {
    favContainer.innerHTML = `<div class="card" style="text-align:center; color:var(--text-muted);">Aucun favori enregistre.</div>`;
  } else {
    favContainer.innerHTML = favs
      .map(
        (item) => `
        <div class="list-item" data-open-id="${item.id}">
          <div class="meta-row" style="margin-bottom:4px;">
            <span class="badge">${escapeHtml(item.categoryIcon)} ${escapeHtml(item.categoryName)}</span>
            <span class="era-tag">${escapeHtml(item.dateKey)} â˜…</span>
          </div>
          <div class="list-item-title">${escapeHtml(item.title)}</div>
          <div class="list-item-sub">${escapeHtml(item.hook)}</div>
        </div>`
      )
      .join("");
  }

  document.querySelectorAll("[data-open-id]").forEach((el) => {
    el.addEventListener("click", () => {
      const id = el.getAttribute("data-open-id");
      const found = allEntries.find((e) => e.id === id);
      if (found) {
        currentEntry = found;
        renderEntryCard(found);
        switchView("today");
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    });
  });
}

function updateHeaderStats() {
  document.getElementById("totalCountBadge").textContent = `${allEntries.length} fiche${allEntries.length > 1 ? "s" : ""}`;
  document.getElementById("streakBadge").textContent = `${computeStreak(allEntries)}j`;
  const formatter = new Intl.DateTimeFormat("fr-FR", { weekday: "long", day: "numeric", month: "long" });
  document.getElementById("todayDateLabel").textContent = formatter.format(new Date());
}

async function refreshState(preferredId = null) {
  allEntries = await getAllEntries();
  updateHeaderStats();

  if (preferredId) {
    currentEntry = allEntries.find((e) => e.id === preferredId) || allEntries[0] || null;
  } else if (!currentEntry && allEntries.length > 0) {
    currentEntry = allEntries[0];
  }

  renderEntryCard(currentEntry);
  renderLists();
}

function switchView(targetName) {
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
  document.getElementById(`view-${targetName}`).classList.add("active");
  document.querySelector(`.nav-btn[data-target="${targetName}"]`).classList.add("active");
}

function populateCategorySelectors() {
  const catSelect = document.getElementById("categorySelect");
  const filterSelect = document.getElementById("archiveCategoryFilter");

  for (const cat of CATEGORIES) {
    const opt1 = document.createElement("option");
    opt1.value = cat.id;
    opt1.textContent = `${cat.icon} ${cat.name}`;
    catSelect.appendChild(opt1);

    const opt2 = document.createElement("option");
    opt2.value = cat.id;
    opt2.textContent = `${cat.icon} ${cat.name}`;
    filterSelect.appendChild(opt2);
  }
}

function loadSettingsIntoForm() {
  const s = getSettings();
  document.getElementById("apiKeyInput").value = s.apiKey;
  document.getElementById("modelSelect").value = s.modelChoice;
  document.getElementById("customModelInput").value = s.customModel;
  document.getElementById("depthSelect").value = s.depth;
  document.getElementById("customModelGroup").style.display = s.modelChoice === "CUSTOM" ? "block" : "none";
}

document.addEventListener("DOMContentLoaded", async () => {
  populateCategorySelectors();
  loadSettingsIntoForm();

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("./sw.js").catch(() => {});
  }

  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchView(btn.getAttribute("data-target")));
  });

  document.getElementById("generateBtn").addEventListener("click", async () => {
    const btn = document.getElementById("generateBtn");
    const container = document.getElementById("todayContent");
    const chosenId = document.getElementById("categorySelect").value;
    const categoryObj =
      chosenId === "AUTO"
        ? selectWeightedCategory(allEntries)
        : CATEGORIES.find((c) => c.id === chosenId) || CATEGORIES[0];

    btn.disabled = true;
    container.innerHTML = `
      <div class="card loader">
        <div class="spinner"></div>
        <div style="font-weight:600; color:var(--text-main);">Synthese en cours via Gemini...</div>
        <div style="font-size:0.84rem; margin-top:4px;">Domaine : ${escapeHtml(categoryObj.name)}</div>
      </div>`;

    try {
      const entry = await generateCulturalEntry(categoryObj);
      await saveEntry(entry);
      await refreshState(entry.id);
      showToast("Nouvelle fiche generee");
    } catch (err) {
      container.innerHTML = `
        <div class="card" style="border-color:var(--danger);">
          <div style="color:#ffa198; font-weight:700; margin-bottom:6px;">Echec de generation</div>
          <p style="font-size:0.9rem; color:var(--text-muted);">${escapeHtml(err.message)}</p>
        </div>`;
    } finally {
      btn.disabled = false;
    }
  });

  document.getElementById("searchInput").addEventListener("input", renderLists);
  document.getElementById("archiveCategoryFilter").addEventListener("change", renderLists);

  document.getElementById("modelSelect").addEventListener("change", (e) => {
    document.getElementById("customModelGroup").style.display = e.target.value === "CUSTOM" ? "block" : "none";
  });

  document.getElementById("saveSettingsBtn").addEventListener("click", () => {
    localStorage.setItem(SETTINGS_KEYS.API_KEY, document.getElementById("apiKeyInput").value.trim());
    localStorage.setItem(SETTINGS_KEYS.MODEL, document.getElementById("modelSelect").value);
    localStorage.setItem(SETTINGS_KEYS.CUSTOM_MODEL, document.getElementById("customModelInput").value.trim());
    localStorage.setItem(SETTINGS_KEYS.DEPTH, document.getElementById("depthSelect").value);
    showToast("Parametres enregistres");
  });

  document.getElementById("exportAllAnkiBtn").addEventListener("click", () => {
    if (!allEntries.length) {
      showToast("Aucune fiche a exporter");
      return;
    }
    const tsv = buildAnkiTsv(allEntries);
    triggerFileDownload(`daily-culture-anki-${getTodayDateString()}.tsv`, tsv, "text/tab-separated-values");
  });

  document.getElementById("exportJsonBtn").addEventListener("click", () => {
    const payload = JSON.stringify({ exportedAt: new Date().toISOString(), entries: allEntries }, null, 2);
    triggerFileDownload(`daily-culture-backup-${getTodayDateString()}.json`, payload, "application/json");
  });

  document.getElementById("importJsonInput").addEventListener("change", async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      const list = Array.isArray(parsed) ? parsed : parsed.entries;
      if (!Array.isArray(list)) throw new Error("Format JSON invalide.");
      for (const item of list) {
        if (item && item.id && item.title) {
          await saveEntry(item);
        }
      }
      await refreshState();
      showToast(`${list.length} fiche(s) importee(s)`);
    } catch (err) {
      showToast(`Erreur import : ${err.message}`);
    } finally {
      e.target.value = "";
    }
  });

  await refreshState();
});