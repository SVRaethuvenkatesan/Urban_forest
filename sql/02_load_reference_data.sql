-- Load reference data. Every modelling assumption is defined here.

-- Near term covers the first 20 years, matching a council long term capital
-- plan. The open ended top band is capped at 60 years.
INSERT INTO ref.renewal_window
    (renewal_window_code, source_label, source_value, label, sort_order,
     start_year, end_year, horizon, is_near_term)
VALUES
    ('lt10',         '< 10 years',    10, 'Under 10 years', 1,  1, 10, 'near_term',    TRUE),
    ('y11_20',       '11 - 20 years', 20, '11 to 20 years', 2, 11, 20, 'near_term',    TRUE),
    ('y21_30',       '21 - 30 years', 30, '21 to 30 years', 3, 21, 30, 'medium_term',  FALSE),
    ('y31_40',       '31 - 40 years', 40, '31 to 40 years', 4, 31, 40, 'medium_term',  FALSE),
    ('gt40',         '> 41 years',    50, 'Over 40 years',  5, 41, 60, 'long_term',    FALSE),
    ('not_assessed', NULL,          NULL, 'Not assessed',   6, NULL, NULL, 'not_assessed', FALSE);

-- Replacement cost per tree, covering removal, supply and establishment.
INSERT INTO ref.replacement_cost_band (cost_band_code, label, dbh_range_cm, cost_aud)
VALUES
    ('young',       'Young, up to 15 cm',        numrange(0, 15, '[]'),    400),
    ('semi_mature', 'Semi mature, 15 to 40 cm',  numrange(15, 40, '(]'),  1200),
    ('mature',      'Mature, 40 to 80 cm',       numrange(40, 80, '(]'),  3000),
    ('veteran',     'Veteran, over 80 cm',       numrange(80, NULL, '()'), 6000);

INSERT INTO ref.excluded_precinct (precinct, reason)
VALUES
    ('Richmond',       'City of Yarra tree, not a City of Melbourne precinct.'),
    ('Brunswick',      'City of Merri-bek tree, not a City of Melbourne precinct.'),
    ('Brunswick West', 'City of Merri-bek tree, not a City of Melbourne precinct.');

INSERT INTO ref.model_parameter (parameter, value, unit, description)
VALUES
    ('dbh_outlier_threshold_cm',      300, 'cm',     'Larger DBH values are treated as entry errors.'),
    ('imputation_min_sample',           5, 'trees',  'Minimum measured trees for a genus and age median.'),
    ('hvi_fallback_max_distance_m',    50, 'm',      'Search radius for trees outside every heat zone.'),
    ('dbscan_eps_m',                   15, 'm',      'DBSCAN radius, chosen from the k distance plot.'),
    ('dbscan_min_points',               5, 'trees',  'Minimum trees in a DBSCAN cluster.'),
    ('micro_cliff_buffer_m',            5, 'm',      'Buffer around a cluster to approximate canopy.'),
    ('low_confidence_tree_threshold', 100, 'trees',  'Precincts below this size are not ranked.'),
    ('weight_cost_density',             1, 'weight', 'Index weight on near term cost per hectare.'),
    ('weight_near_term_share',          1, 'weight', 'Index weight on near term share of trees.'),
    ('weight_heat',                     1, 'weight', 'Index weight on average heat vulnerability.');
