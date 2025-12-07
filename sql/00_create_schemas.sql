-- Enable PostGIS and create the pipeline schemas.
--   staging  raw source data as delivered
--   ref      reference data and model assumptions
--   core     cleaned trees, heat zones and tree level features
--   mart     analysis ready outputs read by the reporting layer

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS ref;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS mart;
