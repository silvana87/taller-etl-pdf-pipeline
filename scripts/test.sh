#!/bin/bash
# ============================================================
# test.sh — Probar el pipeline subiendo un documento
# Taller: Antigravity en acción — Build with AI 2026
# ============================================================
# Uso: bash scripts/test.sh [ruta/al/archivo.pdf]
# ============================================================

export PROJECT_ID=$(gcloud config get-value project)
SAMPLE_FILE=${1:-"samples/sample_invoice.pdf"}

[ ! -f "$SAMPLE_FILE" ] && echo "❌ Archivo no encontrado: $SAMPLE_FILE" && exit 1

echo ""
echo "🧪 Subiendo: $SAMPLE_FILE"
gsutil cp "$SAMPLE_FILE" gs://${PROJECT_ID}-documentos/

echo "⏳ Esperando procesamiento (30 segundos)..."
sleep 30

echo ""
echo "📊 Resultados en BigQuery:"
bq query --use_legacy_sql=false \
    "SELECT file_name, vendor_name, document_date, total_amount, currency, processing_status
     FROM \`${PROJECT_ID}.documentos_procesados.extracciones\`
     ORDER BY processed_at DESC LIMIT 5"

echo ""
echo "📋 Logs de la Cloud Function:"
echo "   gcloud functions logs read process-document --region=us-central1 --gen2 --limit=30"
echo ""
