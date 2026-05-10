#!/bin/bash
API="https://kakapo-back-production.up.railway.app"
TOKEN="kakapo-admin-2026"

QUERIES=(
  "cancer+immunotherapy+checkpoint+inhibitor"
  "CRISPR+gene+therapy+clinical+trial"
  "mRNA+vaccine+COVID+efficacy"
  "Alzheimer+amyloid+beta+treatment"
  "heart+failure+SGLT2+inhibitor"
  "lung+cancer+immunotherapy+nivolumab"
  "breast+cancer+HER2+trastuzumab"
  "diabetes+type2+GLP1+receptor"
  "multiple+sclerosis+interferon+beta"
  "rheumatoid+arthritis+TNF+inhibitor"
  "prostate+cancer+enzalutamide"
  "leukemia+CAR+T+cell+therapy"
  "stroke+thrombolysis+tPA"
  "kidney+disease+progression+biomarkers"
  "Parkinson+dopamine+treatment"
  "sepsis+ICU+antibiotic+resistance"
  "obesity+bariatric+surgery+outcomes"
  "COVID+long+haul+symptoms"
  "atrial+fibrillation+anticoagulation"
  "hepatitis+B+antiviral+treatment"
)

for query in "${QUERIES[@]}"; do
  echo "=== $query ==="
  curl -s --max-time 300 -X POST "$API/ingest/europepmc?query=$query&max_results=50&fetch_full_text=true&year_from=2018&year_to=2026" \
    -H "X-Admin-Token: $TOKEN" | python3 -m json.tool | grep -E "total_created|total_fetched|duration"
  echo ""
done
