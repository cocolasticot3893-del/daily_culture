"use strict";

const CATEGORIES = [
  { id: "philo", name: "Philosophie & Epistemologie", icon: "\u{1F3DB}", angle: "concepts fondateurs, logique, ethique, philosophie des sciences ou penseurs non occidentaux" },
  { id: "beaux-arts", name: "Beaux-Arts & Histoire de l'Art", icon: "\u{1F3A8}", angle: "ruptures picturales, composition, technique, iconologie et mouvements artistiques" },
  { id: "litterature", name: "Litterature Mondiale", icon: "\u{1F4D6}", angle: "oeuvres majeures, narration, courants litteraires mondiaux et figures oubliees" },
  { id: "architecture", name: "Architecture & Urbanisme", icon: "\u{1F4D0}", angle: "ingenierie spatiale, materiaux, typologies architecturales et urbanisme" },
  { id: "musique", name: "Musique Savante & Jazz", icon: "\u{1F3BC}", angle: "contrepoint, harmonie, formes musicales, histoire du jazz et acoustique" },
  { id: "cinema", name: "Cinema d'Auteur & Montage", icon: "\u{1F39E}", angle: "grammaire cinematographique, montage, mise en scene et mouvements mondiaux" },
  { id: "sciences", name: "Histoire des Sciences & Idees", icon: "\u{1F52D}", angle: "paradigmes scientifiques, decouvertes fondamentales et controverses historiques" },
  { id: "mythologie", name: "Mythologie & Anthropologie", icon: "\u{1F5FF}", angle: "structures symboliques, mythes compares, rituels et anthropologie culturelle" },
  { id: "geopolitique", name: "Histoire & Geopolitique", icon: "\u{1F9ED}", angle: "tournants historiques, civilisations, diplomatie et dynamiques spatiales" },
  { id: "theatre", name: "Theatre & Dramaturgie", icon: "\u{1F3AD}", angle: "tragedie, dramaturgie, mise en scene et evolution de l'espace scenique" },
  { id: "photographie", name: "Photographie & Image", icon: "\u{1F4F7}", angle: "composition photographique, histoire du medium, reportage et esthetique visuelle" },
  { id: "design", name: "Design & Arts Decoratifs", icon: "\u{1FA91}", angle: "design industriel, ergonomie, Bauhaus, artisanat et culture materielle" },
  { id: "numerique", name: "Arts Numeriques & Esthetique IA", icon: "\u{1F9EC}", angle: "art generatif, cybernetique, nouveaux medias et esthetique computationnelle" },
  { id: "poesie", name: "Poesie & Rhetorique", icon: "\u{2712}", angle: "prosodie, figures de style, poetique comparee et traditions orales" }
];

const DB_NAME = "DailyCultureDB";
const DB_VERSION = 1;
const STORE_ENTRIES = "entries";

const SETTINGS_KEYS = {
  API_KEY: "dc_gemini_api_key",
  MODEL: "dc_gemini_model",
  MODELS_CACHE: "dc_gemini_models_cache",
  MODELS_CACHE_TS: "dc_gemini_models_cache_ts",
  DEPTH: "dc_editorial_depth",
  BATCH_IDS: "dc_active_batch_ids"
};

const DEFAULT_FALLBACK_MODELS = [
  { id: "gemini-flash-latest", label: "gemini-flash-latest (Defaut stable)" },
  { id: "gemini-2.5-flash", label: "gemini-2.5-flash" },
  { id: "gemini-2.5-pro", label: "gemini-2.5-pro" }
];

const EXCLUDED_MODEL_TOKENS = [
  "embedding",
  "imagen",
  "veo",
  "tts",
  "audio",
  "robotics",
  "computer-use",
  "aqa",
  "bisect",
  "deep-research"
];

let dbInstance = null;
let allEntries = [];
let currentEntry = null;
let activeBatchIds = [];

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

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

/* ---------------- DISCOVERY DYNAMIQUE DES MODELES GEMINI ---------------- */

function getSettings() {
  return {
    apiKey: (localStorage.getItem(SETTINGS_KEYS.API_KEY) || "").trim(),
    activeModel: (localStorage.getItem(SETTINGS_KEYS.MODEL) || "gemini-flash-latest").trim(),
    depth: localStorage.getItem(SETTINGS_KEYS.DEPTH) || "dense"
  };
}

function populateModelDropdown(modelsList, preferredModelId) {
  const select = document.getElementById("modelSelect");
  const list = Array.isArray(modelsList) && modelsList.length ? modelsList : DEFAULT_FALLBACK_MODELS;

  select.innerHTML = "";
  for (const m of list) {
    const opt = document.createElement("option");
    opt.value = m.id;
    opt.textContent = m.label || m.id;
    select.appendChild(opt);
  }

  const availableIds = new Set(list.map((m) => m.id));
  if (preferredModelId && availableIds.has(preferredModelId)) {
    select.value = preferredModelId;
  } else if (availableIds.has("gemini-flash-latest")) {
    select.value = "gemini-flash-latest";
  } else if (availableIds.has("gemini-2.5-flash")) {
    select.value = "gemini-2.5-flash";
  } else {
    select.value = list[0].id;
  }

  localStorage.setItem(SETTINGS_KEYS.MODEL, select.value);
}

async function syncGeminiModels(forceRefresh = false) {
  const apiKey = (document.getElementById("apiKeyInput").value || localStorage.getItem(SETTINGS_KEYS.API_KEY) || "").trim();
  const statusEl = document.getElementById("modelsStatusText");
  const currentSelected = localStorage.getItem(SETTINGS_KEYS.MODEL) || "gemini-flash-latest";

  if (!apiKey) {
    populateModelDropdown(DEFAULT_FALLBACK_MODELS, currentSelected);
    if (statusEl) statusEl.textContent = "Renseignez votre cle API pour charger la liste en direct.";
    return DEFAULT_FALLBACK_MODELS;
  }

  const cachedRaw = localStorage.getItem(SETTINGS_KEYS.MODELS_CACHE);
  const cachedTs = Number(localStorage.getItem(SETTINGS_KEYS.MODELS_CACHE_TS) || "0");
  const cacheValid = cachedRaw && Date.now() - cachedTs < 6 * 3600 * 1000;

  if (!forceRefresh && cacheValid) {
    try {
      const parsedCache = JSON.parse(cachedRaw);
      populateModelDropdown(parsedCache, currentSelected);
      if (statusEl) statusEl.textContent = `${parsedCache.length} modeles actifs (cache local).`;
      return parsedCache;
    } catch (_) {}
  }

  if (statusEl) statusEl.textContent = "Synchronisation GET /v1beta/models en cours...";

  try {
    const resp = await fetch(`https://generativelanguage.googleapis.com/v1beta/models?key=${encodeURIComponent(apiKey)}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const payload = await resp.json();
    const rawModels = Array.isArray(payload.models) ? payload.models : [];

    const filtered = rawModels
      .filter((m) => Array.isArray(m.supportedGenerationMethods) && m.supportedGenerationMethods.includes("generateContent"))
      .map((m) => {
        const cleanId = String(m.name || "").replace(/^models\//, "");
        return { id: cleanId, displayName: m.displayName || cleanId };
      })
      .filter((m) => {
        const lower = m.id.toLowerCase();
        if (!lower.startsWith("gemini-")) return false;
        return !EXCLUDED_MODEL_TOKENS.some((tok) => lower.includes(tok));
      })
      .sort((a, b) => {
        if (a.id === "gemini-flash-latest") return -1;
        if (b.id === "gemini-flash-latest") return 1;
        return b.id.localeCompare(a.id);
      })
      .map((m) => ({
        id: m.id,
        label: m.displayName && m.displayName !== m.id ? `${m.id} (${m.displayName})` : m.id
      }));

    if (!filtered.length) throw new Error("Aucun modele generateContent retourne.");

    localStorage.setItem(SETTINGS_KEYS.MODELS_CACHE, JSON.stringify(filtered));
    localStorage.setItem(SETTINGS_KEYS.MODELS_CACHE_TS, String(Date.now()));
    populateModelDropdown(filtered, currentSelected);
    if (statusEl) statusEl.textContent = `${filtered.length} modeles synchronises avec succes.`;
    return filtered;
  } catch (err) {
    populateModelDropdown(DEFAULT_FALLBACK_MODELS, currentSelected);
    if (statusEl) statusEl.textContent = `Mode secours actif (${err.message}).`;
    return DEFAULT_FALLBACK_MODELS;
  }
}

/* ---------------- PIPELINE D'IMAGES WIKIMEDIA COMMONS + WIKIPEDIA ---------------- */

function isValidRasterImageUrl(url) {
  if (!url || typeof url !== "string") return false;
  const clean = url.split("?")[0].toLowerCase();
  if (
    clean.includes("icon_") ||
    clean.includes("question_book") ||
    clean.includes("flag_of_") ||
    clean.includes("commons-logo") ||
    clean.includes("disambig")
  ) {
    return false;
  }
  return /\.(jpg|jpeg|png|webp)$/.test(clean);
}

async function queryWikimediaCommons(searchQuery) {
  if (!searchQuery) return null;
  const endpoint = `https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrsearch=${encodeURIComponent(
    "filetype:bitmap " + searchQuery
  )}&gsrnamespace=6&gsrlimit=6&prop=imageinfo&iiprop=url&iiurlwidth=800&format=json&origin=*`;

  try {
    const resp = await fetch(endpoint);
    if (!resp.ok) return null;
    const data = await resp.json();
    const pages = Object.values(data?.query?.pages || {}).sort((a, b) => (a.index || 99) - (b.index || 99));
    for (const p of pages) {
      const info = Array.isArray(p.imageinfo) ? p.imageinfo[0] : null;
      const candidateUrl = info?.thumburl || info?.url;
      if (isValidRasterImageUrl(candidateUrl)) {
        return {
          imageUrl: candidateUrl,
          pageUrl: info?.descriptionurl || `https://commons.wikimedia.org/wiki/${encodeURIComponent(p.title)}`
        };
      }
    }
  } catch (_) {
    return null;
  }
  return null;
}

async function queryWikipediaLeadImage(lang, searchQuery) {
  if (!searchQuery) return null;
  const endpoint = `https://${lang}.wikipedia.org/w/api.php?action=query&generator=search&gsrsearch=${encodeURIComponent(
    searchQuery
  )}&gsrlimit=4&prop=pageimages|info&piprop=thumbnail&inprop=url&pithumbsize=800&format=json&origin=*`;

  try {
    const resp = await fetch(endpoint);
    if (!resp.ok) return null;
    const data = await resp.json();
    const pages = Object.values(data?.query?.pages || {}).sort((a, b) => (a.index || 99) - (b.index || 99));
    for (const p of pages) {
      const thumb = p?.thumbnail?.source;
      if (isValidRasterImageUrl(thumb)) {
        return {
          imageUrl: thumb,
          pageUrl: p.fullurl || `https://${lang}.wikipedia.org/wiki/${encodeURIComponent(p.title)}`
        };
      }
    }
  } catch (_) {
    return null;
  }
  return null;
}

function verifyImageLoads(url, timeoutMs = 8000) {
  // Verifie que l'URL repond (HTTP 200 + decodage) via un objet Image : pas de contrainte CORS
  return new Promise((resolve) => {
    if (!url) return resolve(false);
    const img = new Image();
    img.referrerPolicy = "no-referrer";
    const timer = setTimeout(() => { img.src = ""; resolve(false); }, timeoutMs);
    img.onload = () => { clearTimeout(timer); resolve(img.naturalWidth > 0); };
    img.onerror = () => { clearTimeout(timer); resolve(false); };
    img.src = url;
  });
}

async function queryWikipediaSummary(lang, title) {
  if (!title) return null;
  try {
    const resp = await fetch(
      `https://${lang}.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(title.replace(/ /g, "_"))}?redirect=true`
    );
    if (!resp.ok) return null;
    const data = await resp.json();
    const url = data?.thumbnail?.source || data?.originalimage?.source;
    if (!isValidRasterImageUrl(url)) return null;
    return { imageUrl: url, pageUrl: data?.content_urls?.desktop?.page || `https://${lang}.wikipedia.org/wiki/${encodeURIComponent(title)}` };
  } catch (_) {
    return null;
  }
}

async function resolveSubjectIllustration(item) {
  const strategies = [
    () => queryWikipediaSummary("en", item.wikipediaTitleEn),
    () => queryWikipediaSummary("fr", item.wikipediaTitleFr),
    () => queryWikipediaLeadImage("en", item.imageSearchQueryEn || item.wikipediaTitleEn),
    () => queryWikimediaCommons(item.imageSearchQueryEn),
    () => queryWikipediaLeadImage("fr", item.wikipediaTitleFr || item.title)
  ];
  for (const run of strategies) {
    const hit = await run();
    if (hit && (await verifyImageLoads(hit.imageUrl))) return hit;
  }
  return null;
}

/* ---------------- UTILITAIRES ---------------- */

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

  if (uniqueDays[0] !== today && uniqueDays[0] !== yesterday) return 0;

  let streak = 1;
  for (let i = 0; i < uniqueDays.length - 1; i++) {
    const d1 = new Date(uniqueDays[i] + "T00:00:00Z");
    const d2 = new Date(uniqueDays[i + 1] + "T00:00:00Z");
    if (Math.round((d1 - d2) / 86400000) === 1) streak++;
    else break;
  }
  return streak;
}

function selectWeightedCategories(entries, count = 3) {
  const counts = {};
  for (const cat of CATEGORIES) counts[cat.id] = 0;
  for (const item of entries) {
    if (counts[item.categoryId] !== undefined) counts[item.categoryId]++;
  }

  const pool = [...CATEGORIES];
  const selected = [];

  for (let k = 0; k < count && pool.length > 0; k++) {
    const weights = pool.map((cat) => 1 / (1 + Math.pow(counts[cat.id] || 0, 2)));
    const totalWeight = weights.reduce((acc, w) => acc + w, 0);
    let r = Math.random() * totalWeight;
    let chosenIdx = 0;
    for (let i = 0; i < pool.length; i++) {
      r -= weights[i];
      if (r <= 0) {
        chosenIdx = i;
        break;
      }
    }
    selected.push(pool[chosenIdx]);
    pool.splice(chosenIdx, 1);
  }
  return selected;
}

/* ---------------- APPEL API GEMINI AVEC RETRY & FALLBACK ---------------- */

function parseGeminiJsonSafe(rawText) {
  const cleaned = String(rawText)
    .trim()
    .replace(/^```json\s*/i, "")
    .replace(/^```\s*/i, "")
    .replace(/\s*```$/i, "")
    .trim();
  return JSON.parse(cleaned);
}

function extractGeminiText(data) {
  const cand = data?.candidates?.[0];
  const parts = Array.isArray(cand?.content?.parts) ? cand.content.parts : [];
  // Ignore les parts "thought" (modeles a raisonnement) et concatene le texte utile
  const text = parts.filter((p) => !p.thought && typeof p.text === "string").map((p) => p.text).join("");
  if (!text) {
    const reason = cand?.finishReason || data?.promptFeedback?.blockReason || "inconnue";
    throw new Error(`Reponse vide de l'API Gemini (finishReason=${reason}).`);
  }
  if (cand?.finishReason === "MAX_TOKENS") {
    throw new Error("JSON tronque par l'API Gemini (finishReason=MAX_TOKENS).");
  }
  return text;
}

async function callGeminiGenerate(modelId, apiKey, prompt, responseSchema, maxTokens) {
  const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(
    modelId
  )}:generateContent?key=${encodeURIComponent(apiKey)}`;

  let response;
  try {
    response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contents: [{ role: "user", parts: [{ text: prompt }] }],
        generationConfig: {
          temperature: 0.85,
          maxOutputTokens: maxTokens,
          responseMimeType: "application/json",
          responseSchema
        }
      })
    });
  } catch (netErr) {
    const err = new Error(`[${modelId}] Erreur reseau : ${netErr.message}`);
    err.status = 0;
    throw err;
  }

  if (!response.ok) {
    let errDetail = "";
    try {
      const errJson = await response.json();
      errDetail = errJson?.error?.message || JSON.stringify(errJson).slice(0, 300);
    } catch (_) {}
    const err = new Error(`[${modelId}] HTTP ${response.status}${errDetail ? " : " + errDetail : ""}`);
    err.status = response.status;
    throw err;
  }

  const data = await response.json();
  const rawText = extractGeminiText(data);
  try {
    return parseGeminiJsonSafe(rawText);
  } catch (parseErr) {
    throw new Error(`[${modelId}] JSON invalide : ${parseErr.message}`);
  }
}

const ENTRY_SCHEMA = {
  type: "OBJECT",
  properties: {
    categoryId: { type: "STRING" },
    title: { type: "STRING" },
    hook: { type: "STRING" },
    era: { type: "STRING" },
    wikipediaTitleEn: { type: "STRING", description: "Titre exact de l'article Wikipedia anglophone de l'oeuvre/monument/personnage central" },
    wikipediaTitleFr: { type: "STRING", description: "Titre exact de l'article Wikipedia francophone correspondant" },
    imageSearchQueryEn: { type: "STRING", description: "2 a 4 mots-cles en ANGLAIS designant l'oeuvre ou la figure concrete" },
    imageCaption: { type: "STRING" },
    thesis: { type: "STRING" },
    context: { type: "STRING" },
    keyWorkAnalysis: { type: "STRING" },
    contemporaryResonance: { type: "STRING" },
    quote: { type: "STRING" },
    quoteAuthor: { type: "STRING" },
    furtherReading: { type: "STRING" },
    quiz: {
      type: "OBJECT",
      properties: {
        question: { type: "STRING" },
        options: { type: "ARRAY", items: { type: "STRING" } },
        correctIndex: { type: "INTEGER" },
        explanation: { type: "STRING" }
      },
      required: ["question", "options", "correctIndex", "explanation"]
    },
    flashcards: {
      type: "ARRAY",
      items: {
        type: "OBJECT",
        properties: { front: { type: "STRING" }, back: { type: "STRING" } },
        required: ["front", "back"]
      }
    }
  },
  required: [
    "categoryId", "title", "hook", "era", "wikipediaTitleEn", "wikipediaTitleFr", "imageSearchQueryEn",
    "imageCaption", "thesis", "context", "keyWorkAnalysis", "contemporaryResonance",
    "quote", "quoteAuthor", "furtherReading", "quiz", "flashcards"
  ]
};

/**
 * Un seul appel Gemini structure pour N categories (1 a 3) : latence /3, pas de 429 en rafale.
 */
async function generateCulturalEntries(categoryObjs) {
  const settings = getSettings();
  if (!settings.apiKey) {
    throw new Error("Cle API Gemini manquante. Renseignez-la dans l'onglet Config.");
  }

  const recentTitles = allEntries.slice(0, 40).map((e) => e.title);
  const exclusionClause = recentTitles.length
    ? `Sujets deja traites a exclure strictement : ${recentTitles.join(" | ")}.`
    : "Aucun sujet precedent.";

  const deep = settings.depth === "deep";
  const depthInstruction = deep
    ? "Format lecture 6 minutes : analyse approfondie, nuancee et academique (environ 140 a 190 mots par section principale)."
    : "Format lecture 3 minutes : synthese dense, incisive, sans remplissage (environ 70 a 100 mots par section principale).";

  const catLines = categoryObjs
    .map((c, i) => `${i + 1}. categoryId="${c.id}" - domaine "${c.name}" (angle : ${c.angle})`)
    .join("\n");

  const prompt = `Tu es un erudit, historien des idees et critique d'art de niveau universitaire.
Genere exactement ${categoryObjs.length} fiche(s) de culture generale pointue, une par domaine ci-dessous, dans cet ordre, en recopiant le categoryId :
${catLines}
Evite les lieux communs scolaires : privilegie une oeuvre pivot, un concept precis, un tournant meconnu ou un penseur exigeant. Les sujets doivent etre distincts.
${depthInstruction} Explicite les termes techniques rares entre parentheses.
Chaque fiche : 1 quiz a 4 options, 3 a 5 flashcards. wikipediaTitleEn/Fr doivent etre des titres d'articles Wikipedia existants illustres (oeuvre, monument, portrait).
${exclusionClause}
Langue : francais soutenu, precis et clair.`;

  const responseSchema = {
    type: "OBJECT",
    properties: { entries: { type: "ARRAY", items: ENTRY_SCHEMA } },
    required: ["entries"]
  };
  const maxTokens = Math.min(65536, (deep ? 9000 : 5000) * categoryObjs.length + 8000);

  const candidateModels = [settings.activeModel, "gemini-flash-latest", "gemini-2.5-flash"].filter(
    (v, idx, arr) => v && arr.indexOf(v) === idx
  );

  let parsed = null;
  let usedModel = null;
  const errors = [];
  for (const candidate of candidateModels) {
    for (let attempt = 0; attempt < 2 && !parsed; attempt++) {
      try {
        const out = await callGeminiGenerate(candidate, settings.apiKey, prompt, responseSchema, maxTokens);
        if (!Array.isArray(out?.entries) || !out.entries.length) throw new Error(`[${candidate}] tableau entries vide`);
        parsed = out.entries;
        usedModel = candidate;
      } catch (err) {
        errors.push(err.message);
        if (err.status === 400 || err.status === 401 || err.status === 403) break; // inutile de retenter ce modele
        if (err.status === 429 || err.status === 503 || err.status === 500) {
          await sleep(2000 * Math.pow(2, attempt) + Math.random() * 800);
        } else {
          break;
        }
      }
    }
    if (parsed) break;
  }

  if (!parsed) {
    throw new Error(`API Gemini : ${errors.join(" || ") || "Echec de generation"}`);
  }

  const now = Date.now();
  const results = await Promise.all(
    parsed.slice(0, categoryObjs.length).map(async (item, idx) => {
      const cat = categoryObjs.find((c) => c.id === item.categoryId) || categoryObjs[idx] || categoryObjs[0];
      const media = await resolveSubjectIllustration(item);
      return {
        ...item,
        id: `dc_${now}_${idx}_${Math.random().toString(36).slice(2, 7)}`,
        dateKey: getTodayDateString(),
        createdAt: now - idx,
        readingDuration: deep ? "6 min" : "3 min",
        categoryId: cat.id,
        categoryName: cat.name,
        categoryIcon: cat.icon,
        modelUsed: usedModel,
        imageUrl: media?.imageUrl || null,
        imageSourceUrl: media?.pageUrl || null,
        favorite: false,
        quizAnsweredIndex: null
      };
    })
  );
  return results;
}

/* ---------------- EXPORTS ANKI & OBSIDIAN ---------------- */

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

  const imgLine = entry.imageUrl ? `\n![${entry.imageCaption || entry.title}](${entry.imageUrl})\n` : "";

  return `---
title: "${entry.title.replace(/"/g, '\\"')}"
category: "${entry.categoryName}"
era: "${entry.era}"
duration: "${entry.readingDuration || "3 min"}"
date: ${entry.dateKey}
tags: [daily-culture, ${entry.categoryId}]
---

# ${entry.title}
> *${entry.hook}*
${imgLine}
## These & Essence
${entry.thesis}

## Contexte & Genese
${entry.context}

## Oeuvre ou Concept Pivot
${entry.keyWorkAnalysis}

## Resonance Contemporaine
${entry.contemporaryResonance}

> "${entry.quote}" - **${entry.quoteAuthor}**

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

/* ---------------- RENDU INTERFACE ---------------- */

function getBatchEntries() {
  if (activeBatchIds.length > 1) {
    const found = activeBatchIds
      .map((id) => allEntries.find((e) => e.id === id))
      .filter(Boolean);
    if (found.length > 1) return found;
  }
  const todayStr = getTodayDateString();
  return allEntries
    .filter((e) => e.dateKey === todayStr)
    .sort((a, b) => a.createdAt - b.createdAt)
    .slice(-3);
}

function renderTrioTabs() {
  const tabsEl = document.getElementById("trioTabs");
  const batch = getBatchEntries();

  if (batch.length <= 1) {
    tabsEl.style.display = "none";
    tabsEl.innerHTML = "";
    return;
  }

  tabsEl.style.display = "grid";
  tabsEl.style.gridTemplateColumns = `repeat(${Math.min(batch.length, 3)}, 1fr)`;

  tabsEl.innerHTML = batch
    .map((item, idx) => {
      const isActive = currentEntry && currentEntry.id === item.id;
      return `
        <button type="button" class="trio-tab ${isActive ? "active" : ""}" data-trio-id="${item.id}">
          <span class="trio-tab-num">Sujet ${idx + 1} &#8226; ${escapeHtml(item.categoryIcon)}</span>
          <span class="trio-tab-title">${escapeHtml(item.title)}</span>
        </button>`;
    })
    .join("");

  tabsEl.querySelectorAll("[data-trio-id]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-trio-id");
      const found = allEntries.find((e) => e.id === id);
      if (found) {
        currentEntry = found;
        renderTrioTabs();
        renderEntryCard(found);
      }
    });
  });
}

function renderEntryCard(entry) {
  const container = document.getElementById("todayContent");
  if (!entry) {
    container.innerHTML = `
      <div class="card" style="text-align:center; padding:32px 18px;">
        <p style="font-size:1.05rem; font-weight:600; margin-bottom:8px;">Menu du jour vierge</p>
        <p style="color:var(--text-muted); font-size:0.9rem; margin-bottom:18px;">
          Generez votre selection quotidienne de 3 sujets illustres parmi les 14 domaines culturels.
        </p>
        <button class="btn-primary" onclick="document.getElementById('generateBtn').click()">Generer les 3 sujets du jour</button>
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

  const heroImageHtml = entry.imageUrl
    ? `
      <figure class="hero-figure">
        <img src="${escapeHtml(entry.imageUrl)}" alt="${escapeHtml(entry.imageCaption || entry.title)}" referrerpolicy="no-referrer" loading="lazy" onerror="this.parentElement.style.display='none'" />
        <figcaption class="hero-figcaption">
          <span>${escapeHtml(entry.imageCaption || entry.title)}</span>
          ${
            entry.imageSourceUrl
              ? `<a href="${escapeHtml(entry.imageSourceUrl)}" target="_blank" rel="noopener" style="color:var(--gold); text-decoration:none; flex-shrink:0;">Source &#8599;</a>`
              : ""
          }
        </figcaption>
      </figure>`
    : "";

  container.innerHTML = `
    <article class="card">
      <div class="meta-row">
        <span class="badge">${escapeHtml(entry.categoryIcon)} ${escapeHtml(entry.categoryName)}</span>
        <span class="era-tag">${escapeHtml(entry.era)} &#8226; ${escapeHtml(entry.readingDuration || "3 min")}</span>
      </div>

      <h1 class="article-title">${escapeHtml(entry.title)}</h1>
      <p class="article-hook">${escapeHtml(entry.hook)}</p>

      ${heroImageHtml}

      <div class="section-block">
        <div class="section-label">These &amp; Essence</div>
        <p class="section-text">${escapeHtml(entry.thesis)}</p>
      </div>

      <div class="section-block">
        <div class="section-label">Contexte &amp; Genese</div>
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
        <footer>&#8212; ${escapeHtml(entry.quoteAuthor)}</footer>
      </blockquote>

      <div class="section-block">
        <div class="section-label">Piste d'approfondissement</div>
        <p class="section-text" style="font-size:0.88rem; color:var(--text-muted);">${escapeHtml(entry.furtherReading)}</p>
      </div>

      <div class="section-block" style="margin-top:20px; padding-top:16px; border-top:1px solid var(--border);">
        <div class="section-label">Verification Conceptuelle</div>
        <p style="font-weight:600; font-size:0.94rem; margin-bottom:6px;">${escapeHtml(entry.quiz?.question)}</p>
        ${quizHtml}
        ${answered ? `<div class="quiz-explanation">${escapeHtml(entry.quiz?.explanation)}</div>` : ""}
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
          ${entry.favorite ? "&#9733; Dans les favoris" : "&#9734; Ajouter aux favoris"}
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
    activeBatchIds = activeBatchIds.filter((id) => id !== entry.id);
    localStorage.setItem(SETTINGS_KEYS.BATCH_IDS, JSON.stringify(activeBatchIds));
    currentEntry = null;
    await refreshState();
    showToast("Fiche supprimee");
  });
}

function buildListItemHtml(item) {
  const thumbHtml = item.imageUrl
    ? `<img class="list-thumb" src="${escapeHtml(item.imageUrl)}" alt="" referrerpolicy="no-referrer" loading="lazy" onerror="this.style.display='none'" />`
    : "";
  return `
    <div class="list-item" data-open-id="${item.id}">
      ${thumbHtml}
      <div class="list-body">
        <div class="meta-row" style="margin-bottom:3px;">
          <span class="badge">${escapeHtml(item.categoryIcon)} ${escapeHtml(item.categoryName)}</span>
          <span class="era-tag">${escapeHtml(item.dateKey)} ${item.favorite ? "&#9733;" : ""}</span>
        </div>
        <div class="list-item-title">${escapeHtml(item.title)}</div>
        <div class="list-item-sub">${escapeHtml(item.hook)}</div>
      </div>
    </div>`;
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
  archivesContainer.innerHTML = !filtered.length
    ? `<div class="card" style="text-align:center; color:var(--text-muted);">Aucune fiche correspondante.</div>`
    : filtered.map(buildListItemHtml).join("");

  const favs = allEntries.filter((e) => e.favorite);
  const favContainer = document.getElementById("favoritesList");
  favContainer.innerHTML = !favs.length
    ? `<div class="card" style="text-align:center; color:var(--text-muted);">Aucun favori enregistre.</div>`
    : favs.map(buildListItemHtml).join("");

  document.querySelectorAll("[data-open-id]").forEach((el) => {
    el.addEventListener("click", () => {
      const id = el.getAttribute("data-open-id");
      const found = allEntries.find((e) => e.id === id);
      if (found) {
        currentEntry = found;
        renderTrioTabs();
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

  renderTrioTabs();
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
    opt1.textContent = `+ 1 fiche : ${cat.icon} ${cat.name}`;
    catSelect.appendChild(opt1);

    const opt2 = document.createElement("option");
    opt2.value = cat.id;
    opt2.textContent = `${cat.icon} ${cat.name}`;
    filterSelect.appendChild(opt2);
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  populateCategorySelectors();

  try {
    const savedBatch = JSON.parse(localStorage.getItem(SETTINGS_KEYS.BATCH_IDS) || "[]");
    if (Array.isArray(savedBatch)) activeBatchIds = savedBatch;
  } catch (_) {}

  const s = getSettings();
  document.getElementById("apiKeyInput").value = s.apiKey;
  document.getElementById("depthSelect").value = s.depth;

  await syncGeminiModels(false);

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("./sw.js").catch(() => {});
  }

  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchView(btn.getAttribute("data-target")));
  });

  document.getElementById("categorySelect").addEventListener("change", (e) => {
    const btn = document.getElementById("generateBtn");
    btn.textContent = e.target.value === "TRIO" ? "G\u00e9n\u00e9rer (3)" : "G\u00e9n\u00e9rer (1)";
  });

  document.getElementById("generateBtn").addEventListener("click", async () => {
    const btn = document.getElementById("generateBtn");
    const container = document.getElementById("todayContent");
    const chosenId = document.getElementById("categorySelect").value;
    const isTrio = chosenId === "TRIO";

    const targetCategories = isTrio
      ? selectWeightedCategories(allEntries, 3)
      : [CATEGORIES.find((c) => c.id === chosenId) || CATEGORIES[0]];

    btn.disabled = true;
    if (isTrio) {
      activeBatchIds = [];
      document.getElementById("trioTabs").style.display = "none";
    }

    const generatedThisRun = [];

    try {
      btn.textContent = "En cours...";
      container.innerHTML = `
        <div class="card loader">
          <div class="spinner"></div>
          <div style="font-weight:600; color:var(--text-main);">
            ${targetCategories.map((c) => escapeHtml(c.icon) + " " + escapeHtml(c.name)).join(" &middot; ")}
          </div>
          <div style="font-size:0.82rem; margin-top:6px; color:var(--gold);">
            Synthese Gemini (1 requete) + illustrations Wikipedia/Wikimedia verifiees...
          </div>
        </div>`;

      const entries = await generateCulturalEntries(targetCategories);
      for (const entry of entries) {
        await saveEntry(entry);
        generatedThisRun.push(entry);
        if (isTrio) activeBatchIds.push(entry.id);
      }
      if (isTrio) localStorage.setItem(SETTINGS_KEYS.BATCH_IDS, JSON.stringify(activeBatchIds));
      await refreshState(generatedThisRun[0].id);

      showToast(isTrio ? "Menu du jour (3 sujets) pret" : "Nouvelle fiche generee");
    } catch (err) {
      if (generatedThisRun.length > 0) {
        await refreshState(generatedThisRun[0].id);
        showToast(`${generatedThisRun.length}/${targetCategories.length} sujet(s) generes (${err.message})`);
      } else {
        container.innerHTML = `
          <div class="card" style="border-color:var(--danger);">
            <div style="color:#ffa198; font-weight:700; margin-bottom:6px;">Echec de generation</div>
            <p style="font-size:0.9rem; color:var(--text-muted);">${escapeHtml(err.message)}</p>
          </div>`;
      }
    } finally {
      btn.disabled = false;
      btn.textContent = isTrio ? "G\u00e9n\u00e9rer (3)" : "G\u00e9n\u00e9rer (1)";
    }
  });

  document.getElementById("searchInput").addEventListener("input", renderLists);
  document.getElementById("archiveCategoryFilter").addEventListener("change", renderLists);

  document.getElementById("purgeCacheBtn").addEventListener("click", async () => {
    try {
      if ("serviceWorker" in navigator) {
        const regs = await navigator.serviceWorker.getRegistrations();
        await Promise.all(regs.map((r) => r.unregister()));
      }
      if (window.caches) {
        const keys = await caches.keys();
        await Promise.all(keys.map((k) => caches.delete(k)));
      }
      localStorage.removeItem(SETTINGS_KEYS.MODELS_CACHE);
      localStorage.removeItem(SETTINGS_KEYS.MODELS_CACHE_TS);
      showToast("Cache PWA purge - rechargement...");
      setTimeout(() => location.reload(), 800);
    } catch (err) {
      showToast(`Echec purge cache : ${err.message}`);
    }
  });

  document.getElementById("refreshModelsBtn").addEventListener("click", async () => {
    await syncGeminiModels(true);
    showToast("Liste des modeles actualisee");
  });

  document.getElementById("saveSettingsBtn").addEventListener("click", async () => {
    localStorage.setItem(SETTINGS_KEYS.API_KEY, document.getElementById("apiKeyInput").value.trim());
    localStorage.setItem(SETTINGS_KEYS.MODEL, document.getElementById("modelSelect").value);
    localStorage.setItem(SETTINGS_KEYS.DEPTH, document.getElementById("depthSelect").value);
    await syncGeminiModels(true);
    showToast("Parametres et modeles enregistres");
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
        if (item && item.id && item.title) await saveEntry(item);
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