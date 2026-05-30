# Antigravity en acción: convierte documentos en datos con Gemini y BigQuery

**Taller práctico — Build with AI 2026**

Pipeline ETL serverless que procesa documentos automáticamente usando **Gemini 2.5 Flash** para extracción inteligente de datos y **BigQuery** para almacenamiento estructurado — todo orquestado con **Antigravity CLI** en Google Cloud Functions Gen2.

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

Antes de comenzar el taller, asegurate de tener todo lo siguiente listo.
Esto es importante: si saltás este paso, es probable que te trabés durante el taller.

---

### ✅ 1. Verificar Python

Python 3.11 o superior es necesario para ejecutar el código localmente si lo necesitás.

```bash
python --version
# Debe mostrar: Python 3.11.x o superior
```

Si no lo tenés: [descargar Python](https://www.python.org/downloads/)

---

### ✅ 2. Verificar gcloud CLI

**gcloud CLI** es la herramienta de línea de comandos oficial de Google Cloud.
Te permite crear y administrar recursos de GCP desde tu terminal.

```bash
gcloud --version
# Debe mostrar: Google Cloud SDK x.x.x
```

Si no lo tenés: [instalar gcloud CLI](https://cloud.google.com/sdk/docs/install)

Una vez instalado, autenticarte:
```bash
gcloud auth login
# Abre el navegador para iniciar sesión con tu cuenta de Google
```

---

### ✅ 3. Verificar Antigravity CLI

**Antigravity CLI** (`agy`) es la herramienta de terminal lanzada por Google en el I/O 2026.
Reemplaza a Gemini CLI y permite interactuar con agentes de IA directamente desde la terminal.
En este taller la usamos para generar el código del pipeline con un solo prompt.

```bash
agy --version
# Debe mostrar: 1.0.x o superior
```

Si no lo tenés:
```bash
curl -fsSL https://antigravity.google/cli/install.sh | bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
agy --version
```

Una vez instalado, autenticarte:
```bash
agy auth login
# Abre el navegador para iniciar sesión con tu cuenta de Google
```

---

### ✅ 4. Verificar tu proyecto en Google Cloud Console

**Google Cloud Console** es la interfaz web donde administrás todos tus recursos de GCP.
Accedé en: [console.cloud.google.com](https://console.cloud.google.com)

Verificar lo siguiente:

**a) Tenés un proyecto activo**

- Arriba a la izquierda en la consola, hacé click en el selector de proyectos
- Si no tenés uno, click en **"Nuevo proyecto"**
  - Nombre sugerido: `taller-etl-pipeline`
  - Anotá el **Project ID** — lo vas a necesitar durante el taller

**b) El proyecto tiene facturación habilitada**

> ⚠️ Sin facturación activa, Cloud Functions y Vertex AI no funcionan.

- Ir a **Facturación** en el menú de la consola
- Verificar que el proyecto esté vinculado a una cuenta de facturación
- Si es cuenta nueva de GCP: recibís **$300 en créditos gratuitos por 90 días**
- El costo real del taller es **menos de $0.10**

**c) Configurar el proyecto en gcloud**

```bash
gcloud config set project TU_PROJECT_ID
gcloud config get-value project
# Debe mostrar tu Project ID
```

---

### ✅ 5. Clonar este repositorio

```bash
git clone git@github.com:silvana87/taller-etl-pdf-pipeline.git
cd taller-etl-pdf-pipeline
```

---

### Resumen de verificación

Antes de continuar, ejecutá estos comandos y asegurate de que todos funcionan:

```bash
python --version        # Python 3.11+
gcloud --version        # Google Cloud SDK
gcloud config get-value project  # Tu Project ID
agy --version           # Antigravity CLI 1.0+
```

Si todo muestra resultados correctos, ¡estás listo para el taller! 🚀

---

## 📁 Estructura del repositorio

```
taller-etl-pdf-pipeline/
│
├── function/
│   ├── main.py              ← Pipeline ETL completo (generado con Antigravity CLI)
│   └── requirements.txt     ← Dependencias Python (versiones validadas)
│
├── bigquery/
│   └── schema.json          ← Schema de la tabla de BigQuery
│
├── scripts/
│   ├── setup.sh             ← Script opcional: configura todo automáticamente
│   ├── cleanup.sh           ← Eliminar todos los recursos al finalizar
│   └── test.sh              ← Probar el pipeline subiendo un documento
│
├── docs/
│   └── antigravity-prompt.md ← Prompt del taller + ajustes necesarios documentados
│
├── samples/
│   └── sample_invoice.pdf   ← Documento de prueba
│
└── README.md
```

---

## 🚀 Guía paso a paso del taller

### PARTE A — Infraestructura desde Google Cloud Console

En esta parte configuramos todos los componentes de Google Cloud usando la interfaz web.
No se requiere escribir código todavía.

---

#### Paso 1 — Habilitar las APIs necesarias

> **¿Qué son las APIs?**
> En Google Cloud, cada servicio (Storage, BigQuery, Cloud Functions, etc.) tiene una API
> que hay que activar antes de usarla. Es como dar permiso para usar ese servicio en tu proyecto.

1. Ir a **APIs y servicios → Biblioteca** en la consola
2. Buscar y habilitar las siguientes APIs una por una:
   - **Cloud Functions API**
   - **Cloud Build API**
   - **Cloud Storage API**
   - **BigQuery API**
   - **Vertex AI API**
   - **Eventarc API**
   - **Cloud Run API**
   - **Cloud Pub/Sub API**

> 💡 **Alternativa rápida desde Cloud Shell** (ver nota sobre Cloud Shell más abajo):
> ```bash
> export PROJECT_ID=$(gcloud config get-value project)
> gcloud services enable \
>     cloudfunctions.googleapis.com cloudbuild.googleapis.com \
>     storage.googleapis.com bigquery.googleapis.com \
>     aiplatform.googleapis.com eventarc.googleapis.com \
>     run.googleapis.com pubsub.googleapis.com
> ```

---

#### Paso 2 — Crear el bucket de Cloud Storage

> **¿Qué es Cloud Storage?**
> Es el servicio de almacenamiento de archivos de Google Cloud, similar a Google Drive
> pero para aplicaciones. Los archivos se organizan en "buckets" (contenedores).
> En nuestro pipeline, aquí es donde se suben los documentos a procesar.

1. Ir a **Cloud Storage → Buckets**
2. Click en **"Crear bucket"**
3. Completar la configuración:

| Campo | Valor |
|---|---|
| Nombre | `{PROJECT_ID}-documentos` (reemplazar con tu Project ID) |
| Región | `us-central1` |
| Clase de almacenamiento | Standard |
| Control de acceso | Uniforme |
| Protección de datos | Sin protección adicional |

4. Click en **"Crear"**

---

#### Paso 3 — Crear el dataset y tabla en BigQuery

> **¿Qué es BigQuery?**
> Es el data warehouse de Google Cloud. Permite almacenar y consultar grandes volúmenes
> de datos con SQL. Aquí van a quedar todos los datos extraídos de los documentos,
> listos para analizar o conectar a un dashboard.

**Crear el dataset:**
1. Ir a **BigQuery → SQL Workspace**
2. Click en los tres puntos `⋮` al lado de tu proyecto
3. Click en **"Crear dataset"**
4. Configurar:

| Campo | Valor |
|---|---|
| ID del dataset | `documentos_procesados` |
| Ubicación | `us-central1` |
| Vencimiento | Sin vencimiento |

5. Click en **"Crear dataset"**

**Crear la tabla:**
1. Click en los tres puntos `⋮` al lado del dataset `documentos_procesados`
2. Click en **"Crear tabla"**
3. Configurar:

| Campo | Valor |
|---|---|
| Nombre de la tabla | `extracciones` |
| Schema | Editar como texto |

4. Pegar el siguiente schema en el editor:

```json
[
  {"name": "file_name", "type": "STRING", "mode": "REQUIRED"},
  {"name": "processed_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
  {"name": "vendor_name", "type": "STRING", "mode": "NULLABLE"},
  {"name": "document_date", "type": "DATE", "mode": "NULLABLE"},
  {"name": "document_number", "type": "STRING", "mode": "NULLABLE"},
  {"name": "total_amount", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "currency", "type": "STRING", "mode": "NULLABLE"},
  {"name": "line_items", "type": "JSON", "mode": "NULLABLE"},
  {"name": "processing_status", "type": "STRING", "mode": "NULLABLE"}
]
```

5. Click en **"Crear tabla"**

---

#### Paso 4 — Configurar permisos de Pub/Sub (Cloud Shell obligatorio)

> **¿Qué es Cloud Shell?**
> Es una terminal de Linux que Google pone a tu disposición directamente en el navegador,
> sin instalar nada. Está preconfigurada con gcloud y ya autenticada con tu cuenta.
> Para abrirla: click en el ícono `>_` en la esquina superior derecha de la consola de GCP.

> **¿Por qué este paso?**
> Para que Cloud Functions se active automáticamente cuando se sube un archivo,
> usa un sistema de mensajería llamado Pub/Sub. La cuenta de servicio de Cloud Storage
> necesita permiso para publicar en ese sistema. Sin este paso, el trigger no funciona.

Abrir **Cloud Shell** y ejecutar:

```bash
export PROJECT_ID=$(gcloud config get-value project)

# Crear la identidad de servicio de Cloud Storage
gcloud beta services identity create \
    --service=storage.googleapis.com \
    --project=${PROJECT_ID}

# Obtener la cuenta de servicio de GCS
export GCS_SA=$(gcloud storage service-agent --project=${PROJECT_ID})
echo "Cuenta de servicio: ${GCS_SA}"

# Asignar el rol de Pub/Sub Publisher
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${GCS_SA}" \
    --role="roles/pubsub.publisher" \
    --condition=None
```

✅ Si muestra `Updated IAM policy`, el permiso fue asignado correctamente.

---

#### Paso 5 — Crear la Cloud Function vacía (Cloud Shell)

> **¿Qué es Cloud Functions?**
> Es un servicio serverless de Google Cloud que te permite ejecutar código sin gestionar
> servidores. Solo subís el código y Google se encarga del resto. En nuestro pipeline,
> es el "cerebro" que se activa cuando llega un documento y ejecuta todo el proceso ETL.

> **¿Por qué la creamos vacía primero?**
> Queremos tener toda la infraestructura lista antes de agregar el código.
> En la Parte B generamos el código con Antigravity CLI y lo subimos a esta función.

En **Cloud Shell**, ejecutar:

```bash
export PROJECT_ID=$(gcloud config get-value project)

# Crear carpeta del proyecto en Cloud Shell
mkdir -p ~/taller-etl-pdf-pipeline
cd ~/taller-etl-pdf-pipeline

# Crear archivos placeholder temporales
cat > main.py << 'EOF'
def process_document(event, context):
    print("Placeholder - será reemplazado con el código generado por Antigravity CLI")
EOF

touch requirements.txt

# Desplegar la Cloud Function vacía
# --gen2: usa Cloud Functions de 2da generación (más potente, corre sobre Cloud Run)
# --memory=512MB: Gemini 2.5 Flash requiere al menos 512MB de memoria
# --timeout=300s: 5 minutos máximo de ejecución por documento
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

⏳ Este paso tarda entre 3 y 5 minutos. Al terminar debería mostrar `State: ACTIVE`.

---

### PARTE B — Generar el código con Antigravity CLI

En esta parte usamos Antigravity CLI para generar el código del pipeline ETL
con un solo prompt en lenguaje natural.

---

#### Paso 6 — Generar el pipeline ETL

En tu **terminal local** (no Cloud Shell), ejecutar:

```bash
agy
```

Una vez dentro de la interfaz interactiva de Antigravity, pegar el prompt completo
que encontrás en `docs/antigravity-prompt.md`.

Antigravity va a generar dos archivos:
- `main.py` — el pipeline ETL completo
- `requirements.txt` — las dependencias Python

> ⚠️ **Ajuste importante después de generar:**
> Antigravity puede generar el código con versiones o modelos deprecados.
> Antes de subir, verificar que el modelo sea `gemini-2.5-flash`:
> ```python
> # ✅ Correcto
> model = GenerativeModel("gemini-2.5-flash")
> ```

---

#### Paso 7 — Subir el código al Cloud Shell y redesplegar

**Subir los archivos al Cloud Shell:**

1. En Cloud Shell, click en los tres puntos `⋮` → **"Subir"**
2. Seleccionar `main.py` y `requirements.txt` desde tu máquina
3. Moverlos a la carpeta correcta:

```bash
mv ~/main.py ~/taller-etl-pdf-pipeline/main.py
mv ~/requirements.txt ~/taller-etl-pdf-pipeline/requirements.txt

# Verificar que el modelo es correcto
grep "gemini" ~/taller-etl-pdf-pipeline/main.py
# Debe mostrar: gemini-2.5-flash
```

**Redesplegar con el código real:**

```bash
cd ~/taller-etl-pdf-pipeline

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

#### Paso 8 — Subir un documento de prueba

**Desde la consola web:**
1. Ir a **Cloud Storage → Buckets**
2. Abrir el bucket `{PROJECT_ID}-documentos`
3. Click en **"Subir archivos"**
4. Subir cualquier PDF, JPG o PNG (podés usar `samples/sample_invoice.pdf`)

**Desde Cloud Shell:**
```bash
gsutil cp ~/taller-etl-pdf-pipeline/samples/sample_invoice.pdf \
    gs://${PROJECT_ID}-documentos/
```

---

#### Paso 9 — Verificar los datos en BigQuery

> Esperá entre 15 y 30 segundos después de subir el documento para que el pipeline
> termine de procesar.

**Desde la consola web:**
1. Ir a **BigQuery → SQL Workspace**
2. Expandir `documentos_procesados`
3. Click en `extracciones`
4. Click en **"Vista previa"** para ver las filas

**Desde Cloud Shell:**
```bash
bq query --use_legacy_sql=false \
  "SELECT file_name, vendor_name, document_date, total_amount, currency, processing_status
   FROM \`${PROJECT_ID}.documentos_procesados.extracciones\`
   ORDER BY processed_at DESC
   LIMIT 5"
```

---

#### Paso 10 — Ver los logs de la Cloud Function

> Los logs te muestran qué hizo la función paso a paso: descarga del archivo,
> llamada a Gemini, inserción en BigQuery, o cualquier error que haya ocurrido.

**Desde la consola web:**
1. Ir a **Cloud Functions**
2. Click en `process-document`
3. Click en la pestaña **"Registros"**

**Desde Cloud Shell:**
```bash
gcloud functions logs read process-document \
    --region=us-central1 \
    --gen2 \
    --limit=50
```

---

### PARTE D — Cleanup (al finalizar el taller)

> ⚠️ **Importante:** Eliminar los recursos al terminar para evitar costos innecesarios.
> Con los créditos gratuitos de GCP esto no es crítico, pero es una buena práctica.

```bash
bash scripts/cleanup.sh
```

O manualmente desde Cloud Shell:

```bash
export PROJECT_ID=$(gcloud config get-value project)

# Eliminar Cloud Function
gcloud functions delete process-document --region=us-central1 --gen2 --quiet

# Eliminar bucket y su contenido
gsutil -m rm -r gs://${PROJECT_ID}-documentos

# Eliminar dataset de BigQuery
bq rm -r -f --dataset ${PROJECT_ID}:documentos_procesados
```

---

## 🔧 Troubleshooting

### Error: "container failed to start on port 8080"
**Causa:** Versiones incompatibles en `requirements.txt`
**Solución:** Usar exactamente las versiones del archivo `function/requirements.txt` de este repo

### Error: "ImportError: cannot import name 'storage' from google.cloud"
**Causa:** Conflicto entre versiones de `google-cloud-storage` y `google-cloud-aiplatform`
**Solución:** Usar `google-cloud-storage==2.14.0` con `google-cloud-aiplatform==1.67.1`

### Error: "The Cloud Storage service account is unable to publish to Pub/Sub"
**Causa:** Faltan los permisos del Paso 4
**Solución:** Ejecutar los comandos del Paso 4 en Cloud Shell

### Warning: "Memory limit of 244 MiB exceeded"
**Causa:** La función se desplegó sin el flag `--memory=512MB`
**Solución:** Redesplegar incluyendo `--memory=512MB`

### Error al crear trigger de Eventarc desde la consola web
**Causa:** Bug conocido — la consola no muestra todos los tipos de eventos disponibles
**Solución:** Usar el comando `gcloud functions deploy` desde Cloud Shell (Paso 5)

### La función se desplegó pero no se activa al subir archivos
**Causa:** Los archivos del Paso 7 pueden haberse subido a la carpeta incorrecta
**Solución:**
```bash
# Verificar que los archivos están en la carpeta correcta
ls ~/taller-etl-pdf-pipeline/
cat ~/taller-etl-pdf-pipeline/main.py | head -5
```

---

## 💰 Costos estimados

| Recurso | Costo aproximado por el taller |
|---|---|
| Cloud Functions (512MB, ~90 min) | ~$0.05 |
| Cloud Storage (archivos de prueba) | ~$0.01 |
| BigQuery (consultas del taller) | $0.00 (free tier 1TB/mes) |
| Gemini 2.5 Flash (10-20 documentos) | ~$0.03 |
| **Total** | **~$0.09** |

> Los $300 de créditos de una cuenta GCP nueva cubren ampliamente este taller.
> Si ya tenés una cuenta existente, el costo real es menor a $0.10.

---

## 📚 Recursos adicionales

- [Antigravity CLI — Documentación oficial](https://antigravity.google/docs/cli-overview)
- [Gemini 2.5 Flash — Referencia del modelo](https://cloud.google.com/vertex-ai/docs/generative-ai/model-reference/gemini)
- [Cloud Functions Gen2 — Documentación](https://cloud.google.com/functions/docs/concepts/version-comparison)
- [BigQuery — Streaming inserts](https://cloud.google.com/bigquery/docs/streaming-data-into-bigquery)
- [Eventarc con Cloud Storage](https://cloud.google.com/eventarc/docs/run/quickstart-storage)

---

## 🎯 ¿Qué podés construir a partir de esto?

| Caso de uso | Cómo escalar lo aprendido |
|---|---|
| 📊 Dashboard de gastos | Conectar BigQuery a Looker Studio |
| 🔔 Alertas de montos altos | Agregar Cloud Pub/Sub + notificaciones por email |
| 🗂️ Clasificador de documentos | Extender el prompt de Gemini para clasificar el tipo |
| 🔄 Pipeline multiempresa | Agregar campo `company_id` al schema de BigQuery |
| 🤖 Agente de auditoría | Combinar con ADK para análisis automático de inconsistencias |
| 📱 App móvil | Agregar un frontend que suba fotos de documentos desde el celular |

---

*Taller presentado en **Build with AI 2026***
*Repositorio: [github.com/silvana87/taller-etl-pdf-pipeline](https://github.com/silvana87/taller-etl-pdf-pipeline)*
