#!/bin/bash
# Run the canopy cliff pipeline end to end.
#
# Usage:
#   scripts/run_pipeline.sh               run every step
#   scripts/run_pipeline.sh --from STEP   resume from a step
#   scripts/run_pipeline.sh --list        list step names

set -euo pipefail
cd "$(dirname "$0")/.."

: "${DATABASE_URL:?DATABASE_URL must be set}"

STEPS=(
  "create_schemas:sql:sql/00_create_schemas.sql"
  "load_heat_shapefile:shell:scripts/load_heat_vulnerability_index.sh"
  "create_tables:sql:sql/01_create_tables.sql"
  "load_reference_data:sql:sql/02_load_reference_data.sql"
  "load_trees:sql:sql/03_load_trees.sql"
  "load_heat_zones:sql:sql/04_load_heat_zones.sql"
  "build_tree_features:sql:sql/05_build_tree_features.sql"
  "join_heat_zones:sql:sql/06_join_trees_to_heat_zones.sql"
  "detect_micro_cliffs:sql:sql/07_detect_micro_cliffs.sql"
  "build_scorecard:sql:sql/08_build_precinct_scorecard.sql"
  "build_capex_profile:sql:sql/09_build_capex_profile.sql"
  "quality_checks:sql:sql/99_run_quality_checks.sql"
  "export_tables:python:analysis/export_tables.py"
  "rank_sensitivity:python:analysis/rank_sensitivity.py"
  "charts:python:analysis/charts.py"
  "maps:python:analysis/maps.py"
)

start_from=""
case "${1:-}" in
  --from) start_from="${2:?--from requires a step name}" ;;
  --list) printf '%s\n' "${STEPS[@]%%:*}"; exit 0 ;;
  "") ;;
  *) echo "Unknown argument: $1" >&2; exit 2 ;;
esac

if [[ -n "$start_from" ]] && ! printf '%s\n' "${STEPS[@]%%:*}" | grep -qx "$start_from"; then
  echo "Unknown step: $start_from (see --list)" >&2
  exit 2
fi

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

run_step() {
  case "$1" in
    sql)    psql "$DATABASE_URL" --quiet -v ON_ERROR_STOP=1 -f "$2" ;;
    shell)  bash "$2" ;;
    python) python "$2" ;;
  esac
}

active=$([[ -z "$start_from" ]] && echo 1 || echo 0)
pipeline_start=$SECONDS

for entry in "${STEPS[@]}"; do
  IFS=: read -r name kind target <<< "$entry"
  [[ "$name" == "$start_from" ]] && active=1
  [[ "$active" == 1 ]] || continue

  log "START $name"
  step_start=$SECONDS
  run_step "$kind" "$target"
  log "DONE  $name in $((SECONDS - step_start))s"
done

log "Pipeline finished in $((SECONDS - pipeline_start))s"
