# Product Requirements Document
## Melbourne Urban Forest Renewal Capital Plan

| | |
|---|---|
| **Author** | Sri Vishnu Ram Aethu Venkatesan |
| **Status** | Draft |
| **Purpose** | Portfolio project supporting application to a Victorian Government asset management role |
| **Last updated** | 2026-09-28 |

---

## 1. Executive Summary

Council asset registers record condition and life-expectancy data for individual assets, but rarely translate that into a forward-looking capital plan. This project builds a **precinct-level renewal forecast** for the City of Melbourne's ~82,000-tree urban forest, using each tree's assessed useful life expectancy, weighted by neighbourhood heat vulnerability, to identify where a **"canopy cliff"** — a disproportionate cluster of trees hitting end-of-life in the same near-term window — is forming, and what a staggered renewal schedule now would cost to prevent it.

## 2. Problem Statement

Melbourne's council-managed urban forest carries a legacy of single-era avenue and park planting from the 19th and early 20th centuries. Council already audits each tree's useful life expectancy, but that data isn't translated into a forward-looking capital plan — renewal spend is still allocated reactively rather than modelled years ahead. Left unaddressed, entire precincts planted in the same era will hit end-of-life within the same narrow window, forcing a sudden, unbudgeted replacement spike and a temporary collapse in canopy cover — hitting the most heat-vulnerable suburbs hardest.

## 3. Goals

- Produce a defensible, repeatable **renewal-priority ranking** across precincts, not a one-off visual.
- Demonstrate **advanced spatial-database competency**: utilizing PostGIS for spatial joins (trees → heat vulnerability zones) and spatial clustering (e.g., `ST_ClusterDBSCAN`) to identify hyper-localised "micro-cliffs" that cross administrative boundaries.
- Surface a specific, checkable finding: which areas face a canopy cliff, roughly what it will cost, and how that intersects with heat vulnerability.
- Produce output in the form an actual asset planner would present to a capital-works decision: a ranked list, a cost-over-time view, a Bivariate Choropleth map, and a one-page brief.

## 4. Non-Goals

- Not a public-facing visualization tool (that already exists — Melbourne's "Urban Forest Visual"). This project answers the internal capital-planning question that tool doesn't.
- Not a claim of precise, audited replacement costs — those aren't publicly available, and the PRD explicitly requires stating this as an assumption (see §9).
- Not a live/production system — a single-run analytical pipeline producing static outputs is sufficient scope.

## 5. Audience / Stakeholders

Framed as if built for:
- **Primary:** a Council asset planning / capital works team deciding where next year's tree-renewal budget goes.
- **Secondary (real-world):** a hiring panel for a Victorian Government asset management role, evaluating whether this demonstrates real asset-analysis thinking.

## 6. Data Requirements

| Requirement | Source | Status |
|---|---|---|
| Tree register: location, species, DBH, planting year, life-expectancy | [Trees, with species and dimensions (Urban Forest)](https://data.melbourne.vic.gov.au/explore/dataset/trees-with-species-and-dimensions-urban-forest/) — City of Melbourne, ~82,064 records | Verified live; API endpoint confirmed |
| Neighbourhood heat vulnerability, SA1-level | [Metropolitan Melbourne Heat Vulnerability Index 2018](https://discover.data.vic.gov.au/dataset/metropolitan-melbourne-heat-vulnerability-index-2018) — Dept. of Transport and Planning, HVI 1–5 by quintile | Verified to exist; manual download required (SHP/GDB/MIF) |
| Replacement cost per tree by size class | No public source identified | **Assumption required** — see §9; investigate the Burnley Method or i-Tree as a defensible alternative to flat guesses |

## 7. Functional Requirements

| ID | Requirement |
|---|---|
| FR1 | System shall ingest the tree register and normalise it into a structured schema (species, DBH, planting year, life-expectancy fields, precinct, geometry). |
| FR2 | System shall bucket each tree into a renewal-window band (e.g. 0–5, 6–10, 11–20, 20+ years) derived from its life-expectancy value. |
| FR3 | System shall assign each tree an estimated replacement cost based on trunk diameter class. |
| FR4 | System shall use PostGIS to spatially join each tree to the HVI polygon it falls within, attaching an HVI score (1–5) and SA1 code. |
| FR5 | System shall employ spatial clustering (e.g., `ST_ClusterDBSCAN`) to identify high-density "micro-cliffs" of trees sharing the same near-term end-of-life window. |
| FR6 | System shall aggregate trees by precinct × renewal window into count, total estimated cost, average HVI, and compute a density metric (near-term tree loss per hectare). |
| FR7 | System shall compute an area-normalized canopy-cliff score per precinct as `concentration_ratio × near_term_cost_per_hectare × heat_weight`, and rank precincts descending. |
| FR8 | System shall produce a precinct-level cost-over-time chart, and generate spatial outputs (GeoJSON) rendered as a Bivariate Choropleth map (Heat Vulnerability vs. Renewal Cost). |
| FR9 | System shall output a one-page written brief summarising the top at-risk precincts and a recommended staggered renewal approach. |

## 8. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR1 | Spatial operations (joins, clustering) must be executed entirely within the database engine (PostGIS SQL) utilizing GiST indexes, rather than pulling raw data into application memory (e.g., Python/pandas). |
| NFR2 | The system shall be entirely reproducible via Docker/docker-compose, allowing reviewers to spin up the PostGIS database and run the pipeline with a single command without manual dependency configuration. |
| NFR3 | Every modelling assumption (cost estimates, life-expectancy interpretation) shall be documented in the README/brief, not silently embedded. |
| NFR4 | Code shall be understandable and explainable by the author without external reference — this is a portfolio artifact, not a black box. |

## 9. Assumptions & Limitations

State these explicitly in the final report, not just the code comments:

1. **Life-expectancy scale is undocumented.** The source field `useful_life_expectency_value` is described by the publisher only as "derived from the Useful Life Expectency column" — the exact unit/scale isn't published. Validate the real distribution before trusting any bucketing.
2. **The life-expectancy assessment itself is stated by Council to be last updated in 2009.** This is Council's own documented data-recency limitation.
3. **Replacement costs are assumed, not sourced.** No public City of Melbourne procurement figure exists for tree replacement cost; whatever figures are used must be labelled as an estimate.
4. **HVI is from 2018.** Treat it as the most recent available layer, not a real-time measure — note the age when interpreting results against current conditions.

## 10. System / Data Architecture

```
trees                 -- one row per tree (id, species, DBH, planting year,
                          life-expectancy fields, precinct, geom POINT)
tree_heat_join         -- tree id -> SA1 code -> HVI score
precinct_forecast      -- precinct x renewal_window -> count, cost, avg HVI, cliff_score
```

- **Docker / Docker-Compose:** For complete pipeline reproducibility.
- **PostgreSQL + PostGIS:** For storage, indexing, spatial joins (`ST_Intersects`), and advanced spatial analytics (`ST_ClusterDBSCAN`).
- **Python (pandas/sqlalchemy):** Purely as an orchestration and ETL tool (downloading, cleaning, loading to DB, and rendering final outputs).
- **Folium / Kepler.gl / QGIS:** For rendering the final GeoJSON outputs into a Bivariate Choropleth map, alongside Matplotlib/Plotly for temporal charts.

## 11. Methodology Detail

**Renewal window bucketing:** map `useful_life_expectency_value` into bands; cut points must be set from the real observed distribution, not assumed in advance.

**Cost estimation:** map `diameter_breast_height` into a size class, each with an assumed AUD replacement cost — ideally grounded in a recognised valuation method (e.g. Burnley Method) rather than invented figures.

**Canopy cliff index (as implemented, superseding the original score):**
```
pct_cost_density    = percentile rank of near-term replacement cost per hectare
pct_near_term_share = percentile rank of the share of trees due within 20 years
pct_heat            = percentile rank of average HVI
cliff_index         = 100 x weighted mean of the three percentiles (equal weights by default)
```
Interpretation: a precinct scores highest when a large share of its trees fall due together in the near term, the *density* of that cost is high, and its residents are more heat vulnerable.

Why the original score was replaced:
- The original `concentration_ratio` always selected a medium- or long-term window, never a near-term one, so it did not measure a near-term cliff.
- The multiplicative `heat_weight` only ranged from 1.2 to 1.54 across inner Melbourne, so heat barely affected the ranking.

Percentile ranks give each component comparable influence. Precincts with fewer than 100 trees are reported but not ranked. Weights live in `ref.model_parameter` and are stress tested in the rank sensitivity analysis (Q8).

**Near-term horizon:** broadened from 0 to 5 years to 0 to 20 years. The source bands start at "< 10 years", which holds only 0.8 percent of trees. 20 years matches a council long-term capital plan.

**Staggered renewal (FR9):** the levelled budget is the smallest constant annual spend whose cumulative total never falls behind cumulative reactive need. See `sql/09_build_capex_profile.sql`.

## 12. Milestones

| Phase | Deliverable |
|---|---|
| 0 | Docker-compose environment (PostGIS + Python container) set up |
| 1 | Automated ETL script to download and load CSV/Shapefiles into PostGIS |
| 2 | SQL scripts written for schema creation, feature engineering, and GiST indexing |
| 3 | In-database spatial joins and DBSCAN clustering implemented |
| 4 | Area-normalized forecast + cliff score computed via SQL |
| 5 | GeoJSON outputs exported and rendered into Bivariate Choropleth maps and charts |
| 6 | Findings validated against real-world expectations |
| 7 | One-page brief written |
| 8 | Repo pushed to GitHub with incremental commit history and reproducibility instructions |

## 13. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Life-expectancy field scale is misunderstood, producing nonsense buckets | Validate distribution before trusting output (Phase 3/§9) |
| Invented cost figures undermine credibility in interview | State clearly as an assumption; research a real valuation method if time allows |
| Real HVI shapefile field names differ from assumed schema | Inspect shapefile fields directly before writing the join logic against them |
| Project reads as "just a groupby with a database attached" | Implement `ST_ClusterDBSCAN` to find micro-cliffs and output professional Bivariate Choropleth maps |

## 14. Success Criteria

- Pipeline runs end-to-end on real data (not synthetic fixtures) without manual patching.
- Cliff ranking is spatially and historically plausible on inspection.
- Every number in the final brief is traceable to either real source data or an explicitly labelled assumption.
- Author can explain every design decision (schema, bucketing, join method, scoring formula) without notes.

## 15. Open Questions

- **Resolved:** `useful_life_expectency` has five text bands plus NULL. `useful_life_expectency_value` is a 10 to 50 code that defaults to 50 when unassessed, so the text field is authoritative.
- **Resolved:** the HVI shapefile join key is `SA1_MAIN16`, the score is `HVI_INDEX` (0 means unclassified), and the CRS is GDA94 (EPSG:4283).
- **Open:** a citable tree valuation method, such as Burnley or i-Tree, to replace the assumed cost bands in `ref.replacement_cost_band`.
