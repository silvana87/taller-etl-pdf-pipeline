#!/bin/bash
# ============================================================
# setup.sh — Script OPCIONAL de configuración automática
# Taller: Antigravity en acción — Build with AI 2026
# ============================================================
# Este script automatiza todos los pasos de configuración
# de infraestructura descritos en el README.
#
# Es opcional — el README explica cómo hacer cada paso
# manualmente desde la consola de Google Cloud.
#
# Uso (desde Cloud Shell):
#   bash scripts/setup.sh
#
# Prerrequisitos:
#   - gcloud autenticado: gcloud auth login
#   - Proyecto configurado: gcloud config set project TU_PROJECT_ID
#   - Billing habilitado en el proyecto
# ============================================================

set -e

export PROJECT_ID=$(gcloud config get-value project)
export REGION="us-central1"
export BUCKET_NAME="${PROJECT_ID}-documentos"
export DATASET_NAME="documentos_procesados"
export TABLE_NAME="extracciones"
export FUNCTION_NAME="process-document"
export MEMORY="512MB"

echo ""
echo "=============================================="
echo " Antigravity en acción — Build with AI 2026"
echo " Setup automático de infraestructura"
echo "=============================================="
echo ""
echo "Proyecto : $PROJECT_ID"
echo "Región   : $REGION"
echo "Bucket   : $BUCKET_NAME"
echo "Dataset  : $DATASET_NAME"
echo "Función  : $FUNCTION_NAME"
echo ""

[ -z "$PROJECT_ID" ] && echo "❌ Error: PROJECT_ID no configurado. Ejecutá: gcloud config set project TU_ID" && exit 1

read -p "¿Confirmar? (y/n): " confirm
[ "$confirm" != "y" ] && echo "Cancelado." && exit 0

echo ""
echo "🔧 [1/5] Habilitando APIs..."
gcloud services enable \
    cloudfunctions.googleapis.com cloudbuild.googleapis.com \
    storage.googleapis.com bigquery.googleapis.com \
    aiplatform.googleapis.com eventarc.googleapis.com \
    run.googleapis.com pubsub.googleapis.com \
    --project=${PROJECT_ID}
echo "✅ APIs habilitadas."

echo ""
echo "🪣 [2/5] Creando bucket de Cloud Storage..."
if gsutil ls gs://${BUCKET_NAME} &>/dev/null; then
    echo "   ⚠️  El bucket ya existe. Saltando."
else
    gcloud storage buckets create gs://${BUCKET_NAME} \
        --location=${REGION} --uniform-bucket-level-access
    echo "✅ Bucket creado: gs://${BUCKET_NAME}"
fi

echo ""
echo "🔑 [3/5] Configurando permisos de Pub/Sub..."
gcloud beta services identity create --service=storage.googleapis.com --project=${PROJECT_ID} 2>/dev/null || true
GCS_SA=$(gcloud storage service-agent --project=${PROJECT_ID})
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${GCS_SA}" \
    --role="roles/pubsub.publisher" \
    --condition=None --quiet
echo "✅ Permisos configurados."

echo ""
echo "📊 [4/5] Configurando BigQuery..."
bq ls --project_id=${PROJECT_ID} ${DATASET_NAME} &>/dev/null || \
    bq mk --dataset --location=${REGION} ${PROJECT_ID}:${DATASET_NAME}
bq ls --project_id=${PROJECT_ID} ${DATASET_NAME}.${TABLE_NAME} &>/dev/null || \
    bq mk --table ${PROJECT_ID}:${DATASET_NAME}.${TABLE_NAME} bigquery/schema.json
echo "✅ BigQuery configurado."

echo ""
echo "⚡ [5/5] Desplegando Cloud Function (3-5 minutos)..."
gcloud functions deploy ${FUNCTION_NAME} \
    --gen2 --runtime=python311 --region=${REGION} \
    --source=./function \
    --entry-point=process_document \
    --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
    --trigger-event-filters="bucket=${BUCKET_NAME}" \
    --set-env-vars PROJECT_ID=${PROJECT_ID},REGION=${REGION} \
    --memory=${MEMORY} --timeout=300s --project=${PROJECT_ID}
echo "✅ Cloud Function desplegada."

echo ""
echo "=============================================="
echo " ✅ Setup completado"
echo "=============================================="
echo ""
echo "Próximo paso — subir un documento de prueba:"
echo "   gsutil cp samples/sample_invoice.pdf gs://${BUCKET_NAME}/"
echo ""
echo "Verificar resultados:"
echo "   bq query --use_legacy_sql=false 'SELECT * FROM \`${PROJECT_ID}.${DATASET_NAME}.${TABLE_NAME}\` LIMIT 5'"
echo ""
