-- Create all ref, core and mart tables.
-- Each run is a full refresh: these schemas are dropped and rebuilt so no
-- stale results survive a change of assumptions. Staging is kept because the
-- heat zone shapefile is loaded into it before this step.
-- All analysis geometry is stored in EPSG:7855 (GDA2020 MGA zone 55, metres).

DROP SCHEMA IF EXISTS mart CASCADE;
DROP SCHEMA IF EXISTS core CASCADE;
DROP SCHEMA IF EXISTS ref CASCADE;
CREATE SCHEMA ref;
CREATE SCHEMA core;
CREATE SCHEMA mart;

-- Reference layer ----------------------------------------------------------

CREATE TABLE ref.renewal_window (
    renewal_window_code  TEXT PRIMARY KEY,
    source_label         TEXT UNIQUE,
    source_value         SMALLINT,
    label                TEXT NOT NULL,
    sort_order           SMALLINT NOT NULL UNIQUE,
    start_year           SMALLINT,
    end_year             SMALLINT,
    horizon              TEXT NOT NULL
        CHECK (horizon IN ('near_term', 'medium_term', 'long_term', 'not_assessed')),
    is_near_term         BOOLEAN NOT NULL,
    CHECK (start_year IS NULL OR end_year >= start_year)
);
COMMENT ON TABLE ref.renewal_window IS
    'Source life expectancy bands mapped to renewal windows, horizons and years.';

CREATE TABLE ref.replacement_cost_band (
    cost_band_code  TEXT PRIMARY KEY,
    label           TEXT NOT NULL,
    dbh_range_cm    NUMRANGE NOT NULL,
    cost_aud        NUMERIC(10, 2) NOT NULL CHECK (cost_aud > 0),
    EXCLUDE USING gist (dbh_range_cm WITH &&)
);
COMMENT ON TABLE ref.replacement_cost_band IS
    'Assumed replacement cost by trunk diameter. Analyst estimates, not council rates.';

CREATE TABLE ref.excluded_precinct (
    precinct  TEXT PRIMARY KEY,
    reason    TEXT NOT NULL
);

CREATE TABLE ref.model_parameter (
    parameter    TEXT PRIMARY KEY,
    value        NUMERIC NOT NULL,
    unit         TEXT,
    description  TEXT NOT NULL
);

CREATE FUNCTION ref.param(p_name TEXT)
RETURNS NUMERIC
LANGUAGE sql
STABLE
AS $$
    SELECT value FROM ref.model_parameter WHERE parameter = p_name
$$;

-- Core layer ---------------------------------------------------------------

CREATE TABLE core.tree (
    tree_id          INTEGER PRIMARY KEY,
    common_name      TEXT,
    scientific_name  TEXT,
    genus            TEXT,
    family           TEXT,
    dbh_cm           NUMERIC CHECK (dbh_cm IS NULL OR dbh_cm > 0),
    age_description  TEXT,
    ule_label        TEXT,
    ule_value        SMALLINT,
    precinct         TEXT NOT NULL,
    located_in       TEXT,
    geom_wgs84       GEOMETRY(Point, 4326) NOT NULL,
    geom             GEOMETRY(Point, 7855) NOT NULL
);
CREATE INDEX tree_geom_gix ON core.tree USING gist (geom);
CREATE INDEX tree_precinct_idx ON core.tree (precinct);

COMMENT ON COLUMN core.tree.ule_value IS
    'Source code 10 to 50, not years remaining. Defaults to 50 when unassessed, so ule_label is authoritative.';

CREATE TABLE core.hvi_zone (
    sa1_code   TEXT PRIMARY KEY,
    sa2_name   TEXT,
    hvi_score  SMALLINT CHECK (hvi_score IS NULL OR hvi_score BETWEEN 1 AND 5),
    geom       GEOMETRY(MultiPolygon, 7855) NOT NULL
);
CREATE INDEX hvi_zone_geom_gix ON core.hvi_zone USING gist (geom);

COMMENT ON COLUMN core.hvi_zone.hvi_score IS
    'Heat Vulnerability Index quintile, 1 (low) to 5 (high). NULL where the source is 0 (unclassified).';

CREATE TABLE core.tree_feature (
    tree_id               INTEGER PRIMARY KEY REFERENCES core.tree (tree_id),
    renewal_window_code   TEXT NOT NULL REFERENCES ref.renewal_window (renewal_window_code),
    horizon               TEXT NOT NULL,
    is_assessed           BOOLEAN NOT NULL,
    is_near_term          BOOLEAN NOT NULL,
    precinct_in_scope     BOOLEAN NOT NULL,
    dbh_cm_model          NUMERIC NOT NULL,
    dbh_source            TEXT NOT NULL
        CHECK (dbh_source IN ('measured', 'imputed_genus_age', 'imputed_age', 'imputed_overall')),
    cost_band_code        TEXT NOT NULL REFERENCES ref.replacement_cost_band (cost_band_code),
    replacement_cost_aud  NUMERIC(10, 2) NOT NULL
);
CREATE INDEX tree_feature_window_idx ON core.tree_feature (renewal_window_code);

CREATE TABLE core.tree_hvi (
    tree_id           INTEGER PRIMARY KEY REFERENCES core.tree (tree_id),
    sa1_code          TEXT REFERENCES core.hvi_zone (sa1_code),
    hvi_score         SMALLINT,
    match_method      TEXT NOT NULL CHECK (match_method IN ('within', 'nearest', 'unmatched')),
    match_distance_m  NUMERIC
);

CREATE TABLE core.tree_cluster (
    tree_id     INTEGER PRIMARY KEY REFERENCES core.tree (tree_id),
    horizon     TEXT NOT NULL,
    cluster_id  INTEGER
);
CREATE INDEX tree_cluster_idx ON core.tree_cluster (horizon, cluster_id);

COMMENT ON COLUMN core.tree_cluster.cluster_id IS
    'DBSCAN cluster number, unique within a horizon. NULL means the tree is not in a cluster.';

-- Mart layer ---------------------------------------------------------------

CREATE TABLE mart.micro_cliff (
    horizon                TEXT NOT NULL,
    cluster_id             INTEGER NOT NULL,
    cluster_rank           INTEGER NOT NULL,
    tree_count             INTEGER NOT NULL,
    replacement_cost_aud   NUMERIC(12, 2) NOT NULL,
    footprint_m2           NUMERIC NOT NULL,
    trees_per_ha           NUMERIC NOT NULL,
    dominant_genus         TEXT,
    dominant_genus_share   NUMERIC,
    precinct               TEXT,
    located_in             TEXT,
    avg_hvi_score          NUMERIC,
    geom                   GEOMETRY(Polygon, 7855) NOT NULL,
    PRIMARY KEY (horizon, cluster_id)
);
CREATE INDEX micro_cliff_geom_gix ON mart.micro_cliff USING gist (geom);

CREATE TABLE mart.precinct_area (
    precinct    TEXT PRIMARY KEY,
    tree_count  INTEGER NOT NULL,
    area_ha     NUMERIC NOT NULL CHECK (area_ha > 0),
    geom        GEOMETRY(Polygon, 7855) NOT NULL
);
COMMENT ON TABLE mart.precinct_area IS
    'Convex hull of each precinct''s trees. An approximation, as no official boundaries are published.';

CREATE TABLE mart.precinct_window (
    precinct              TEXT NOT NULL,
    renewal_window_code   TEXT NOT NULL REFERENCES ref.renewal_window (renewal_window_code),
    tree_count            INTEGER NOT NULL,
    tree_share            NUMERIC NOT NULL,
    replacement_cost_aud  NUMERIC(14, 2) NOT NULL,
    imputed_cost_share    NUMERIC,
    avg_hvi_score         NUMERIC,
    PRIMARY KEY (precinct, renewal_window_code)
);

CREATE TABLE mart.precinct_scorecard (
    precinct                     TEXT PRIMARY KEY,
    tree_count                   INTEGER NOT NULL,
    area_ha                      NUMERIC NOT NULL,
    near_term_trees              INTEGER NOT NULL,
    near_term_share              NUMERIC NOT NULL,
    near_term_cost_aud           NUMERIC(14, 2) NOT NULL,
    near_term_cost_per_ha        NUMERIC NOT NULL,
    near_term_trees_per_ha       NUMERIC NOT NULL,
    scheduled_cost_aud           NUMERIC(14, 2) NOT NULL,
    not_assessed_cost_aud        NUMERIC(14, 2) NOT NULL,
    avg_hvi_score                NUMERIC,
    hvi_classified_share         NUMERIC NOT NULL,
    near_term_clustered_share    NUMERIC,
    not_assessed_share           NUMERIC NOT NULL,
    imputed_dbh_share            NUMERIC NOT NULL,
    low_confidence               BOOLEAN NOT NULL,
    pct_cost_density             NUMERIC,
    pct_near_term_share          NUMERIC,
    pct_heat                     NUMERIC,
    cliff_index                  NUMERIC CHECK (cliff_index BETWEEN 0 AND 100),
    cliff_rank                   INTEGER,
    CHECK (low_confidence = (cliff_rank IS NULL))
);
COMMENT ON COLUMN mart.precinct_scorecard.cliff_index IS
    'Priority score 0 to 100. NULL for precincts too small to rank reliably.';

CREATE TABLE mart.capex_profile (
    precinct                  TEXT NOT NULL,
    year_offset               SMALLINT NOT NULL,
    reactive_cost_aud         NUMERIC(14, 2) NOT NULL,
    cumulative_reactive_aud   NUMERIC(14, 2) NOT NULL,
    levelled_budget_aud       NUMERIC(14, 2) NOT NULL,
    cumulative_levelled_aud   NUMERIC(14, 2) NOT NULL,
    PRIMARY KEY (precinct, year_offset)
);
COMMENT ON TABLE mart.capex_profile IS
    'Annual renewal spend by year from assessment. Precinct All precincts holds the city total.';
