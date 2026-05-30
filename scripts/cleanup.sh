#!/bin/bash
# ============================================================
# cleanup.sh — Eliminar todos los recursos del taller
# Taller: Antigravity en acción — Build with AI 2026
# ============================================================
# Ejecutar al finalizar el taller para evitar costos.
# Esta acción es IRREVERSIBLE.
# ============================================================

export PROJECT_ID=$(gcloud config get-value project)

echo ""
echo "⚠️  CLEANUP — Se eliminarán todos los recursos del taller"
echo ""
echo "   gs://${PROJECT_ID}-documentos"
echo "   ${PROJECT_ID}:documentos_procesados"
echo "   Cloud Function: process-document"
echo ""
read -p "Escribí 'eliminar' para confirmar: " confirm
[ "$confirm" != "eliminar" ] && echo "Cancelado." && exit 0

echo ""
echo "🗑️  Eliminando Cloud Function..."
gcloud functions delete process-document --region=us-central1 --gen2 --quiet || true

echo "🗑️  Eliminando bucket..."
gsutil -m rm -r gs://${PROJECT_ID}-documentos || true

echo "🗑️  Eliminando dataset de BigQuery..."
bq rm -r -f --dataset ${PROJECT_ID}:documentos_procesados || true

echo ""
echo "✅ Recursos eliminados. No se generarán costos adicionales."
echo ""
