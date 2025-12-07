-- Load the tree register CSV into staging, then into core.tree.
-- The file is semicolon delimited. Staging mirrors all 20 source columns in
-- order because \copy maps by position. Planting dates are not loaded, as
-- about a third carry the placeholder year 1900.

DROP TABLE IF EXISTS staging.trees_raw;
CREATE TABLE staging.trees_raw (
    com_id                        TEXT,
    common_name                   TEXT,
    scientific_name               TEXT,
    genus                         TEXT,
    family                        TEXT,
    diameter_breast_height        TEXT,
    year_planted                  TEXT,
    date_planted                  TEXT,
    age_description               TEXT,
    useful_life_expectency        TEXT,
    useful_life_expectency_value  TEXT,
    precinct                      TEXT,
    located_in                    TEXT,
    uploaddate                    TEXT,
    coordinatelocation            TEXT,
    latitude                      TEXT,
    longitude                     TEXT,
    easting                       TEXT,
    northing                      TEXT,
    geolocation                   TEXT
);

\copy staging.trees_raw FROM 'data/trees_raw.csv' WITH (FORMAT csv, DELIMITER ';', HEADER true, NULL '', ENCODING 'UTF8')

INSERT INTO core.tree (
    tree_id, common_name, scientific_name, genus, family, dbh_cm,
    age_description, ule_label, ule_value, precinct, located_in,
    geom_wgs84, geom
)
SELECT
    s.com_id::INTEGER,
    NULLIF(TRIM(s.common_name), ''),
    NULLIF(TRIM(s.scientific_name), ''),
    NULLIF(TRIM(s.genus), ''),
    NULLIF(TRIM(s.family), ''),
    CASE
        WHEN s.diameter_breast_height::NUMERIC <= 0 THEN NULL
        WHEN s.diameter_breast_height::NUMERIC > ref.param('dbh_outlier_threshold_cm') THEN NULL
        ELSE s.diameter_breast_height::NUMERIC
    END,
    NULLIF(TRIM(s.age_description), ''),
    NULLIF(TRIM(s.useful_life_expectency), ''),
    s.useful_life_expectency_value::SMALLINT,
    TRIM(s.precinct),
    NULLIF(TRIM(s.located_in), ''),
    pt.geom_wgs84,
    ST_Transform(pt.geom_wgs84, 7855)
FROM staging.trees_raw AS s
CROSS JOIN LATERAL (
    SELECT ST_SetSRID(
               ST_MakePoint(s.longitude::DOUBLE PRECISION, s.latitude::DOUBLE PRECISION),
               4326) AS geom_wgs84
) AS pt
WHERE s.latitude IS NOT NULL
  AND s.longitude IS NOT NULL
  AND s.precinct IS NOT NULL;

ANALYZE core.tree;
