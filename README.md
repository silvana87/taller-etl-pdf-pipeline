# Antigravity en acción: convierte documentos en datos con Gemini y BigQuery

**Taller práctico — WildWid AI 2026**

Pipeline ETL serverless que procesa documentos automáticamente usando **Gemini 2.5 Flash** para extracción inteligente de datos y **BigQuery** para almacenamiento estructurado — todo orquestado con **Antigravity CLI**.

---

## 🏗️ Arquitectura

```
📄 Documento (PDF / JPG / PNG)
        ↓  [usuario sube el archivo]
☁️  Cloud Storage
        ↓  [trigger automático via Eventarc]
⚡  Cloud Functions Gen2
        ↓  [llamada a la API]
🤖  Gemini 2.5 Flash (Vertex AI)
        ↓  [datos estructurados en JSON]
📊  BigQuery
```

---

## 📋 Prerrequisitos

### Conocimientos
- Familiaridad básica con la terminal / línea de comandos
- Conocimiento básico de Python
- Haber usado Google Cloud al menos una vez

### Cuentas y accesos
- Cuenta de Google (Gmail personal sirve)
- **Proyecto de GCP con billing habilitado**
  - Cuenta nueva: $300 en créditos gratuitos por 90 días
  - Costo estimado del taller: menos de $0.10
- **Antigravity CLI instalado** (para la Parte B del taller)

### Software
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) instalado y autenticado
- [Antigravity CLI](https://antigravity.google/download) instalado:
```bash
curl -fsSL https://antigravity.google/cli/install.sh | bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
agy --version
```

---

## 🚀 Setup rápido

### Opción A — Script automático (recomendado)

```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/taller-doc-pipeline
cd taller-doc-pipeline

# 2. Configurar el proyecto GCP
gcloud config set project TU_PROJECT_ID

# 3. Ejecutar el setup completo
bash scripts/setup.sh
```

### Opción B — Paso a paso (para el taller)

Ver la sección [Guía paso a paso](#-guía-paso-a-paso) más abajo.

---

## 📁 Estructura del repositorio

```
taller-doc-pipeline/
│
├── function/
│   ├── main.py              ← Pipeline ETL (generado con Antigravity CLI)
│   └── requirements.txt     ← Dependencias Python (versiones validadas)
│
├── bigquery/
│   └── schema.json          ← Schema de la tabla de BigQuery
│
├── scripts/
│   ├── setup.sh             ← Setup completo automatizado
│   ├── cleanup.sh           ← Eliminar todos los recursos
│   └── test.sh              ← Probar el pipeline con un documento
│
├── docs/
│   └── antigravity-prompt.md ← Prompt usado en el taller + ajustes necesarios
│
├── samples/
│   └── sample_invoice.pdf   ← Documento de prueba
│
└── README.md
```

---

## 📖 Guía paso a paso

### PARTE A — Infraestructura desde la Consola de Google Cloud

#### 1. Crear el bucket de Cloud Storage

1. Ir a **Cloud Storage → Buckets**
2. Click en **"Crear bucket"**
3. Configurar:
   - **Nombre:** `{PROJECT_ID}-documentos`
   - **Región:** `us-central1`
   - **Clase:** Standard
   - **Control de acceso:** Uniforme
4. Click en **"Crear"**

#### 2. Crear el dataset y tabla en BigQuery

1. Ir a **BigQuery → SQL Workspace**
2. Click en `⋮` al lado del proyecto → **"Crear dataset"**
3. Configurar:
   - **ID:** `documentos_procesados`
   - **Ubicación:** `us-central1`
4. Click en `⋮` al lado del dataset → **"Crear tabla"**
5. Configurar:
   - **Nombre:** `extracciones`
   - **Schema:** Editar como texto → pegar el contenido de `bigquery/schema.json`

#### 3. Configurar permisos (Cloud Shell)

> ⚠️ Este paso es obligatorio. Sin estos permisos el trigger de Eventarc no funciona.

Abrir **Cloud Shell** (`>_` en la consola) y ejecutar:

```bash
export PROJECT_ID=$(gcloud config get-value project)

# Crear la identidad de servicio de Cloud Storage
gcloud beta services identity create \
    --service=storage.googleapis.com \
    --project=${PROJECT_ID}

# Obtener la cuenta de servicio
export GCS_SA=$(gcloud storage service-agent --project=${PROJECT_ID})

# Asignar rol de Pub/Sub Publisher
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${GCS_SA}" \
    --role="roles/pubsub.publisher" \
    --condition=None
```

#### 4. Crear la Cloud Function vacía (Cloud Shell)

```bash
# Crear carpeta del proyecto
mkdir -p ~/taller-doc-pipeline
cd ~/taller-doc-pipeline

# Crear archivos placeholder
cat > main.py << 'EOF'
def process_document(event, context):
    print("Placeholder - será reemplazado con el código generado por Antigravity")
EOF

touch requirements.txt

# Habilitar APIs necesarias
gcloud services enable \
    cloudfunctions.googleapis.com cloudbuild.googleapis.com \
    storage.googleapis.com bigquery.googleapis.com \
    aiplatform.googleapis.com eventarc.googleapis.com \
    run.googleapis.com pubsub.googleapis.com

# Desplegar Cloud Function vacía
gcloud functions deploy process-document \
    --gen2 \
    --runtime=python311 \
    --region=us-central1 \
    --source=. \
    --entry-point=process_document \
    --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
    --trigger-event-filters="bucket=${PROJECT_ID}-documentos" \
    --set-env-vars PROJECT_ID=${PROJECT_ID},REGION=us-central1 \
    --memory=512MB \
    --timeout=300s
```

---

### PARTE B — Generar el código con Antigravity CLI

#### 5. Generar el pipeline ETL con Antigravity

En tu terminal local:

```bash
agy
```

Una vez dentro de la interfaz interactiva, pegar el prompt completo de `docs/antigravity-prompt.md`.

Antigravity generará:
- `main.py` — el pipeline ETL completo
- `requirements.txt` — las dependencias

#### 6. Subir el código al Cloud Shell y redesplegar

**Desde Cloud Shell** (click en `⋮` → "Subir"):
1. Subir `main.py` y `requirements.txt`
2. Mover a la carpeta correcta:

```bash
mv ~/main.py ~/taller-doc-pipeline/main.py
mv ~/requirements.txt ~/taller-doc-pipeline/requirements.txt

# Verificar que el modelo es correcto
grep "gemini" ~/taller-doc-pipeline/main.py
# Debe mostrar: gemini-2.5-flash
```

3. Redesplegar con el código real:

```bash
cd ~/taller-doc-pipeline

gcloud functions deploy process-document \
    --gen2 \
    --runtime=python311 \
    --region=us-central1 \
    --source=. \
    --entry-point=process_document \
    --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
    --trigger-event-filters="bucket=${PROJECT_ID}-documentos" \
    --set-env-vars PROJECT_ID=${PROJECT_ID},REGION=us-central1 \
    --memory=512MB \
    --timeout=300s
```

---

### PARTE C — Verificar resultados

#### 7. Subir un documento de prueba

```bash
gsutil cp samples/sample_invoice.pdf gs://${PROJECT_ID}-documentos/
```

O desde la consola: **Cloud Storage → Bucket → Subir archivos**

#### 8. Verificar datos en BigQuery

```bash
bq query --use_legacy_sql=false \
  "SELECT file_name, vendor_name, document_date, total_amount, currency, processing_status
   FROM \`${PROJECT_ID}.documentos_procesados.extracciones\`
   ORDER BY processed_at DESC
   LIMIT 5"
```

O desde la consola: **BigQuery → documentos_procesados → extracciones → Vista previa**

#### 9. Ver logs de la Cloud Function

```bash
gcloud functions logs read process-document \
    --region=us-central1 \
    --gen2 \
    --limit=50
```

---

## 🧹 Cleanup — Eliminar recursos al finalizar

```bash
bash scripts/cleanup.sh
```

O manualmente:

```bash
export PROJECT_ID=$(gcloud config get-value project)

# Eliminar Cloud Function
gcloud functions delete process-document --region=us-central1 --gen2 --quiet

# Eliminar bucket
gsutil -m rm -r gs://${PROJECT_ID}-documentos

# Eliminar dataset de BigQuery
bq rm -r -f --dataset ${PROJECT_ID}:documentos_procesados
```

---

## 🔧 Troubleshooting

### Error: "container failed to start on port 8080"
**Causa:** Versiones incompatibles en `requirements.txt`
**Solución:** Usar exactamente las versiones validadas de `function/requirements.txt`

### Error: "ImportError: cannot import name 'storage' from google.cloud"
**Causa:** Conflicto entre versiones de `google-cloud-storage` y `google-cloud-aiplatform`
**Solución:** Usar `google-cloud-storage==2.14.0` y `google-cloud-aiplatform==1.67.1`

### Error: "The Cloud Storage service account is unable to publish to Pub/Sub"
**Causa:** La cuenta de servicio de GCS no tiene permisos de Pub/Sub Publisher
**Solución:** Ejecutar el Paso 3 de configuración de permisos

### Warning: "Memory limit of 244 MiB exceeded"
**Causa:** La función se desplegó con la memoria por defecto (256MB)
**Solución:** Redesplegar con `--memory=512MB`

### Error al crear trigger de Eventarc desde la consola
**Causa:** Bug conocido de la consola — la lista de eventos no carga correctamente
**Solución:** Usar el comando `gcloud functions deploy` desde Cloud Shell

---

## 💰 Costos estimados

| Recurso | Costo por el taller |
|---|---|
| Cloud Functions (512MB, 90 min) | ~$0.05 |
| Cloud Storage (subir archivos de prueba) | ~$0.01 |
| BigQuery (consultas del taller) | $0.00 (free tier) |
| Gemini 2.5 Flash (10-20 documentos) | ~$0.03 |
| **Total** | **~$0.09** |

> Los $300 de créditos de una cuenta GCP nueva cubren ampliamente el taller.

---

## 📚 Recursos adicionales

- [Documentación de Antigravity CLI](https://antigravity.google/docs/cli-overview)
- [Vertex AI Generative Models](https://cloud.google.com/vertex-ai/docs/generative-ai/model-reference/gemini)
- [Cloud Functions Gen2](https://cloud.google.com/functions/docs/concepts/version-comparison)
- [BigQuery Streaming Inserts](https://cloud.google.com/bigquery/docs/streaming-data-into-bigquery)
- [Eventarc con Cloud Storage](https://cloud.google.com/eventarc/docs/run/quickstart-storage)

---

## 🎯 ¿Qué podés construir a partir de esto?

| Caso de uso | Cómo escalar |
|---|---|
| 📊 Dashboard de gastos | Conectar BigQuery a Looker Studio |
| 🔔 Alertas de montos altos | Agregar Cloud Pub/Sub + notificaciones |
| 🗂️ Clasificador de documentos | Extender el prompt de Gemini |
| 🔄 Pipeline multiempresa | Agregar campo `company_id` al schema |
| 🤖 Agente de auditoría | Combinar con ADK para análisis automático |

---

*Taller presentado en WildWid AI 2026*
