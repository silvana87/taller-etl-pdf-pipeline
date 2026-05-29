# Prompt de Antigravity CLI
## Taller: Antigravity en acción - WildWid AI 2026

Este archivo contiene el prompt utilizado en el **Bloque 3, Parte B** del taller
para generar el código del pipeline ETL con Antigravity CLI.

---

## ¿Cómo usarlo?

1. Abrí tu terminal y ejecutá:
```bash
agy
```

2. Una vez dentro de la interfaz interactiva, pegá el prompt completo de abajo.

3. Antigravity generará `main.py` y `requirements.txt` automáticamente.

---

## ⚠️ Ajustes manuales necesarios después de generar el código

Antigravity puede generar el código con versiones o modelos deprecados.
Antes de deployar, verificar y corregir lo siguiente:

### 1. Modelo de Gemini
```python
# ❌ Modelos deprecados — NO usar:
model = GenerativeModel("gemini-1.5-pro-vision")  # deprecado
model = GenerativeModel("gemini-1.5-pro")          # deprecado

# ✅ Modelo correcto — usar este:
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

```
Crea una Cloud Function en Python 3.11 llamada `process_document` que implemente 
un pipeline ETL completo para procesar documentos desde Google Cloud Storage.

## CONTEXTO DE INFRAESTRUCTURA
- La función ya está desplegada en Cloud Functions Gen2
- El trigger es un evento de Cloud Storage cuando se sube un archivo nuevo
- Las variables de entorno disponibles son:
  - PROJECT_ID: ID del proyecto de Google Cloud
  - REGION: us-central1
- La función debe tener 512MB de memoria (Gemini 2.5 Flash lo requiere)

## MODELO DE IA
- Usar Gemini 2.5 Flash: GenerativeModel("gemini-2.5-flash")
- NO usar gemini-1.5-pro-vision ni gemini-1.5-pro (están deprecados)

## PIPELINE ETL

### EXTRACCIÓN
- Recibir el evento de Cloud Storage con el nombre del bucket y del archivo
- Descargar el archivo (PDF o imagen JPG/PNG) desde GCS usando google-cloud-storage
- Soportar archivos de hasta 10MB
- Si el archivo no es PDF, JPG o PNG, registrar un error y salir sin fallar

### TRANSFORMACIÓN
- Enviar el archivo a Gemini 2.5 Flash usando vertexai
- Usar este prompt exacto para la extracción:
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
- Parsear el JSON devuelto por Gemini
- Si el JSON no es válido, reintentar una vez más con el mismo prompt
- Limpiar los datos:
  - total_amount: convertir a float, remover símbolos $, €, Bs, comas
  - document_date: asegurar formato YYYY-MM-DD o None
  - currency: convertir a mayúsculas
  - line_items: serializar como string JSON

### CARGA
- Insertar el registro en BigQuery usando google-cloud-bigquery
- Dataset: documentos_procesados
- Tabla: extracciones
- Schema exacto de la tabla:
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
- line_items debe insertarse como string JSON serializado
- document_date debe insertarse como string en formato YYYY-MM-DD o None si es null

## MANEJO DE ERRORES
- Capturar cualquier excepción en todo el pipeline
- Si ocurre un error, insertar igualmente en BigQuery con:
  - processing_status: "error"
  - file_name: nombre del archivo
  - processed_at: timestamp actual
  - todos los demás campos en null
- Loggear todos los errores con print() para que aparezcan en Cloud Logging
- NO lanzar excepciones al final para evitar reintentos innecesarios de GCF

## DEPENDENCIAS
Generar también el archivo requirements.txt con estas versiones exactas
(son las únicas versiones compatibles entre sí en Cloud Functions Gen2):
google-cloud-storage==2.14.0
google-cloud-bigquery==3.25.0
google-cloud-aiplatform==1.67.1
vertexai==1.67.1
functions-framework==3.5.0
```
