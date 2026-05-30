# Prompt de Antigravity CLI
## Taller: Antigravity en acción — Build with AI 2026

Este archivo contiene el prompt utilizado en la **Parte B del taller**
para generar el código del pipeline ETL con Antigravity CLI.

---

## ¿Cómo usarlo?

1. Abrí tu terminal y ejecutá:
```bash
agy
```

2. Una vez dentro de la interfaz interactiva, pegá el prompt completo de la sección siguiente.

3. Antigravity generará `main.py` y `requirements.txt` automáticamente.

---

## ⚠️ Ajustes manuales necesarios después de generar

Antigravity puede generar el código con modelos o versiones desactualizadas.
Antes de subir los archivos, verificar y corregir:

### 1. Modelo de Gemini
```python
# ❌ Modelos deprecados — NO usar:
model = GenerativeModel("gemini-1.5-pro-vision")
model = GenerativeModel("gemini-1.5-pro")

# ✅ Modelo correcto:
model = GenerativeModel("gemini-2.5-flash")
```

### 2. Versiones en requirements.txt
```
# ✅ Versiones validadas y compatibles:
google-cloud-storage==2.14.0
google-cloud-bigquery==3.25.0
google-cloud-aiplatform==1.67.1
vertexai==1.67.1
functions-framework==3.5.0
```

### 3. Memoria de la Cloud Function
Gemini 2.5 Flash requiere al menos 512MB de memoria.
Asegurarse de incluir `--memory=512MB` en el comando de deploy.

---

## Prompt completo

Copiá y pegá esto dentro de la interfaz de `agy`:

```
Crea una Cloud Function en Python 3.11 llamada `process_document` que implemente
un pipeline ETL completo para procesar documentos desde Google Cloud Storage.

## CONTEXTO DE INFRAESTRUCTURA
- Cloud Function Gen2 ya desplegada en us-central1
- Trigger: evento de Cloud Storage cuando se finaliza la subida de un archivo
- Variables de entorno disponibles:
  - PROJECT_ID: ID del proyecto de Google Cloud
  - REGION: us-central1
- Memoria asignada: 512MB (requerido por Gemini 2.5 Flash)

## MODELO DE IA
- Usar EXACTAMENTE: GenerativeModel("gemini-2.5-flash")
- NO usar gemini-1.5-pro-vision ni gemini-1.5-pro (están deprecados)
- Importar desde: vertexai.generative_models

## PIPELINE ETL

### E — EXTRACCIÓN
- Leer el evento de Cloud Storage: bucket y nombre del archivo
- Validar que el archivo sea PDF, JPG o PNG — salir con error si no lo es
- Validar que el archivo no supere 10MB
- Descargar el archivo desde GCS con google-cloud-storage

### T — TRANSFORMACIÓN
- Preparar el archivo como Part.from_data() para Vertex AI
- Enviar a Gemini 2.5 Flash con este prompt exacto:
  "Analiza este documento y extrae los siguientes campos en formato JSON válido.
   Si un campo no existe en el documento, usa null.
   Devuelve SOLO el JSON, sin texto adicional, sin markdown, sin backticks:
   {
     "vendor_name": "nombre del proveedor o emisor del documento",
     "document_date": "fecha en formato YYYY-MM-DD",
     "document_number": "número de documento, factura o referencia",
     "total_amount": monto_total_como_numero_decimal,
     "currency": "código de moneda de 3 letras (USD, BOB, EUR, etc)",
     "line_items": [{"description": "descripción del item", "amount": monto_decimal}]
   }"
- Si el JSON no es válido, reintentar una vez
- Limpiar los datos:
  - total_amount: convertir a float, remover $, €, Bs, comas
  - document_date: string YYYY-MM-DD o None
  - currency: uppercase (USD, BOB, EUR)
  - line_items: serializar como json.dumps()

### L — CARGA
- Dataset: documentos_procesados
- Tabla: extracciones
- Schema exacto:
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
- Usar bq_client.insert_rows_json()

## MANEJO DE ERRORES
- Si cualquier etapa falla, insertar registro en BigQuery con processing_status="error"
  y todos los campos de extracción en null
- Loggear con print() para Cloud Logging
- NO lanzar excepciones al final (evita reintentos automáticos de GCF)

## DEPENDENCIAS — requirements.txt con estas versiones EXACTAS:
google-cloud-storage==2.14.0
google-cloud-bigquery==3.25.0
google-cloud-aiplatform==1.67.1
vertexai==1.67.1
functions-framework==3.5.0
```
