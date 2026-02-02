#!/bin/bash
# =============================================================================
# Create BigQuery Metadata Tables for Query Generator
# =============================================================================

set -e  # Exit on error

PROJECT_ID="yotam-395120"
DATASET="peerplay"

echo "=================================================="
echo "Creating BigQuery Metadata Tables"
echo "Project: ${PROJECT_ID}"
echo "Dataset: ${DATASET}"
echo "=================================================="
echo ""

# Check if gcloud is installed
if ! command -v bq &> /dev/null; then
    echo "❌ Error: 'bq' command not found. Please install Google Cloud SDK."
    echo "   Visit: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if dataset exists, create if not
echo "Checking if dataset ${DATASET} exists..."
if ! bq ls -d "${PROJECT_ID}:${DATASET}" &> /dev/null; then
    echo "Dataset ${DATASET} not found. Creating..."
    bq mk --dataset "${PROJECT_ID}:${DATASET}"
    echo "✓ Dataset created"
else
    echo "✓ Dataset exists"
fi

echo ""
echo "Creating tables from bigquery_setup.sql..."
echo ""

# Execute the SQL file
bq query \
  --use_legacy_sql=false \
  --project_id="${PROJECT_ID}" \
  < bigquery_setup.sql

echo ""
echo "=================================================="
echo "✓ Tables created successfully!"
echo "=================================================="
echo ""
echo "Created tables:"
echo "  1. ${PROJECT_ID}.${DATASET}.query_gen_guardrails"
echo "  2. ${PROJECT_ID}.${DATASET}.query_gen_tables"
echo "  3. ${PROJECT_ID}.${DATASET}.query_gen_columns"
echo "  4. ${PROJECT_ID}.${DATASET}.query_gen_known_metrics"
echo ""
echo "Sample data inserted:"
echo "  - 1 guardrail (partition filtering)"
echo "  - 1 table (verification_service_events)"
echo "  - 2 metrics (total_revenue, purchase_revenue)"
echo ""
echo "Next steps:"
echo "  1. Add more data using INSERT statements"
echo "  2. Run: python setup_vectordb.py --from-bigquery"
echo "  3. Test queries: python main.py query 'your query here'"
echo ""
