-- ============================================================
-- Schéma Supabase (PostgreSQL) pour "Le Banquet des Muses"
-- ============================================================
-- Exécute ces commandes dans l'éditeur SQL du dashboard Supabase
-- (https://app.supabase.com > project > SQL Editor)
-- ============================================================

-- ------------------------------------------------------------
-- Table 1 : seen_history
-- Blacklist absolue anti-répétition.
-- Enregistre TOUTES les oeuvres générées pour ne jamais les
-- reproposer.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS seen_history (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    author TEXT DEFAULT '',
    date_seen DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    -- Contrainte unique : évite les doublons même en cas
    -- de double appel API
    UNIQUE(category, title)
);

-- Index pour les requêtes par catégorie (get_seen_titles)
CREATE INDEX IF NOT EXISTS idx_seen_history_category
    ON seen_history(category);

-- Index pour le tri chronologique
CREATE INDEX IF NOT EXISTS idx_seen_history_date
    ON seen_history(date_seen DESC);


-- ------------------------------------------------------------
-- Table 2 : user_preferences
-- Enregistre les votes J'aime (liked=true) et Bof (liked=false)
-- pour le profilage utilisateur.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_preferences (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    author TEXT DEFAULT '',
    liked BOOLEAN NOT NULL,
    date_str DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index pour agréger les catégories aimées
CREATE INDEX IF NOT EXISTS idx_user_preferences_liked
    ON user_preferences(liked);

-- Index pour le tri par date
CREATE INDEX IF NOT EXISTS idx_user_preferences_date
    ON user_preferences(date_str DESC);


-- ------------------------------------------------------------
-- Table 3 : daily_editions
-- Cache persistant des éditions quotidiennes.
-- Une ligne par date, contenant le JSON complet de l'édition.
-- Évite les appels redondants à l'API DeepSeek.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS daily_editions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    edition_date DATE UNIQUE NOT NULL,
    edition_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index pour la recherche par date (get_edition)
CREATE INDEX IF NOT EXISTS idx_daily_editions_date
    ON daily_editions(edition_date);


-- ------------------------------------------------------------
-- Fonction utilitaire : mise à jour automatique de updated_at
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Appliquer le trigger sur daily_editions
DROP TRIGGER IF EXISTS trigger_daily_editions_updated_at
    ON daily_editions;
CREATE TRIGGER trigger_daily_editions_updated_at
    BEFORE UPDATE ON daily_editions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- ------------------------------------------------------------
-- Politiques Row Level Security (RLS)
-- Par défaut, tout est accessible avec la clé API (service_role).
-- Si tu souhaites restreindre, active RLS et ajoute des politiques.
-- Pour une app mono-utilisateur, laisser désactivé.
-- ------------------------------------------------------------
-- ALTER TABLE seen_history ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE daily_editions ENABLE ROW LEVEL SECURITY;
