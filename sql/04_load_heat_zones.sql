-- Load Heat Vulnerability Index zones into core.hvi_zone.
-- Source CRS is GDA94 (EPSG:4283); geometry is reprojected once to EPSG:7855.
-- HVI_INDEX 0 marks zones with no residents and is stored as NULL.

INSERT INTO core.hvi_zone (sa1_code, sa2_name, hvi_score, geom)
SELECT
    s.sa1_main16,
    s.sa2_name16,
    NULLIF(s.hvi_index::SMALLINT, 0),
    ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Transform(s.geom, 7855)), 3))
FROM staging.hvi_zones_raw AS s;

ANALYZE core.hvi_zone;
