"""
Pipeline ETL para procesamiento inteligente de documentos con Gemini y BigQuery
================================================================================
Taller: "Antigravity en acción: convierte documentos en datos con Gemini y BigQuery"
Autor: [Tu nombre]
Evento: WildWid AI 2026

Descripción:
    Cloud Function Gen2 que se activa automáticamente cuando se sube un archivo
    (PDF, JPG, PNG) a un bucket de Cloud Storage. El pipeline realiza:
    - EXTRACCIÓN: Descarga el archivo desde GCS
    - TRANSFORMACIÓN: Usa Gemini 2.5 Flash para extraer datos estructurados
    - CARGA: Inserta los datos en BigQuery

Variables de entorno requeridas:
    PROJECT_ID: ID del proyecto de Google Cloud
    REGION: Región de Google Cloud (default: us-central1)

Dependencias:
    Ver requirements.txt
"""

import os
import json
import traceback
from datetime import datetime, timezone
import functions_framework
from google.cloud import storage
from google.cloud import bigquery
import vertexai
from vertexai.generative_models import GenerativeModel, Part

# ============================================================
# CONFIGURACIÓN GLOBAL
# ============================================================
PROJECT_ID = os.environ.get("PROJECT_ID")
REGION = os.environ.get("REGION", "us-central1")

# Modelo de Gemini a usar para la extracción
# gemini-2.5-flash: rápido, multimodal, soporta PDF e imágenes
GEMINI_MODEL = "gemini-2.5-flash"

# Tipos de archivo soportados y sus MIME types
SUPPORTED_FORMATS = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png"
}

# Tamaño máximo de archivo: 10MB
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

# Dataset y tabla de BigQuery
BIGQUERY_DATASET = "documentos_procesados"
BIGQUERY_TABLE = "extracciones"

# Inicialización de Vertex AI al cargar el módulo
# Esto mejora el tiempo de respuesta en invocaciones subsecuentes (warm start)
if PROJECT_ID:
    try:
        vertexai.init(project=PROJECT_ID, location=REGION)
        print(f"Vertex AI inicializado: proyecto={PROJECT_ID}, región={REGION}")
    except Exception as init_err:
        print(f"Advertencia: No se pudo inicializar Vertex AI en carga del módulo: {init_err}")


# ============================================================
# PROMPT DE EXTRACCIÓN
# ============================================================
EXTRACTION_PROMPT = """Analiza este documento y extrae los siguientes campos en formato JSON válido.
Si un campo no existe en el documento, usa null.
Devuelve SOLO el JSON, sin texto adicional, sin markdown, sin backticks:
{
  "vendor_name": "nombre del proveedor o emisor del documento",
  "document_date": "fecha en formato YYYY-MM-DD",
  "document_number": "número de documento, factura o referencia",
  "total_amount": monto_total_como_numero_decimal,
  "currency": "código de moneda de 3 letras (USD, BOB, EUR, etc)",
  "line_items": [{"description": "descripción del item", "amount": monto_decimal}]
}"""


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def parse_gemini_response(text):
    """
    Parsea la respuesta de Gemini a un diccionario Python.

    Maneja casos comunes de respuestas mal formateadas:
    - Bloques de código markdown (```json ... ```)
    - Comillas simples en lugar de dobles
    - Espacios y saltos de línea extra

    Args:
        text (str): Texto de respuesta de Gemini

    Returns:
        dict: Datos extraídos del documento

    Raises:
        ValueError: Si el texto está vacío
        json.JSONDecodeError: Si no se puede parsear el JSON
    """
    if not text:
        raise ValueError("Gemini devolvió una respuesta vacía.")

    cleaned = text.strip()

    # Remover bloques de código markdown si existen
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    cleaned = cleaned.strip()

    # Intento 1: Parseo JSON estándar
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as json_err:
        print(f"Parseo JSON directo falló: {json_err}. Intentando evaluación Python...")

        # Intento 2: ast.literal_eval para sintaxis de diccionario Python (comillas simples)
        import ast
        try:
            val = ast.literal_eval(cleaned)
            if isinstance(val, dict):
                return val
        except Exception as ast_err:
            print(f"Parseo AST falló: {ast_err}")

        raise json_err


def get_gemini_extraction(document_part):
    """
    Llama a Gemini Vision para extraer datos estructurados del documento.
    Reintenta una vez si la respuesta no es JSON válido.

    Args:
        document_part (Part): Parte del documento para Vertex AI

    Returns:
        dict: Datos extraídos del documento

    Raises:
        RuntimeError: Si Gemini falla después de 2 intentos
    """
    model = GenerativeModel(GEMINI_MODEL)
    max_attempts = 2

    for attempt in range(max_attempts):
        try:
            print(f"Llamando a Gemini {GEMINI_MODEL} (intento {attempt + 1}/{max_attempts})...")
            response = model.generate_content([document_part, EXTRACTION_PROMPT])

            if not response.text:
                raise ValueError("Gemini devolvió una respuesta de texto vacía.")

            print(f"Respuesta de Gemini: {response.text}")
            parsed_json = parse_gemini_response(response.text)
            print(f"Datos extraídos correctamente: {list(parsed_json.keys())}")
            return parsed_json

        except Exception as e:
            print(f"Intento {attempt + 1} de Gemini falló: {e}")
            if attempt == max_attempts - 1:
                raise RuntimeError(f"Extracción con Gemini falló después de {max_attempts} intentos: {e}")


def transform_extracted_data(extracted_data, file_name, processed_at):
    """
    Transforma y limpia los datos extraídos por Gemini para
    que sean compatibles con el schema de BigQuery.

    Args:
        extracted_data (dict): Datos crudos de Gemini
        file_name (str): Nombre del archivo procesado
        processed_at (str): Timestamp de procesamiento

    Returns:
        dict: Fila lista para insertar en BigQuery
    """
    # vendor_name: limpiar espacios
    vendor_name = extracted_data.get("vendor_name")
    if isinstance(vendor_name, str):
        vendor_name = vendor_name.strip() or None

    # document_date: asegurar formato YYYY-MM-DD o None
    document_date = extracted_data.get("document_date")
    if document_date in [None, "null", "None", ""]:
        document_date_val = None
    else:
        document_date_val = str(document_date).strip()

    # document_number: convertir a string o None
    document_number = extracted_data.get("document_number")
    if document_number in [None, "null", "None", ""]:
        document_number_val = None
    else:
        document_number_val = str(document_number).strip()

    # total_amount: convertir a float, manejar símbolos de moneda
    total_amount = extracted_data.get("total_amount")
    if total_amount in [None, "null", "None", ""]:
        total_amount_val = None
    else:
        try:
            if isinstance(total_amount, str):
                # Remover símbolos comunes: $, €, Bs, comas
                clean_amount = total_amount.replace('$', '').replace(',', '').replace('Bs', '').strip()
                total_amount_val = float(clean_amount)
            else:
                total_amount_val = float(total_amount)
        except Exception as amt_err:
            print(f"Advertencia: No se pudo convertir total_amount '{total_amount}' a float: {amt_err}")
            total_amount_val = None

    # currency: limpiar y convertir a mayúsculas
    currency = extracted_data.get("currency")
    if isinstance(currency, str):
        currency = currency.strip().upper() or None

    # line_items: serializar como JSON string para BigQuery tipo JSON
    line_items_data = extracted_data.get("line_items")
    if line_items_data is not None:
        line_items_str = json.dumps(line_items_data, ensure_ascii=False)
    else:
        line_items_str = None

    return {
        "file_name": file_name,
        "processed_at": processed_at,
        "vendor_name": vendor_name,
        "document_date": document_date_val,
        "document_number": document_number_val,
        "total_amount": total_amount_val,
        "currency": currency,
        "line_items": line_items_str,
        "processing_status": "success"
    }


def insert_to_bigquery(row):
    """
    Inserta una fila en la tabla de BigQuery.

    Args:
        row (dict): Fila a insertar, debe coincidir con el schema de la tabla

    Raises:
        RuntimeError: Si la inserción falla
    """
    bq_client = bigquery.Client()
    project_id = os.environ.get("PROJECT_ID")
    table_id = f"{project_id}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}"

    print(f"Insertando en BigQuery tabla: {table_id}")
    errors = bq_client.insert_rows_json(table_id, [row])

    if errors:
        raise RuntimeError(f"Error al insertar en BigQuery: {errors}")

    print(f"Inserción en BigQuery exitosa para: {row.get('file_name')}")


# ============================================================
# ENTRYPOINT DE LA CLOUD FUNCTION
# ============================================================

@functions_framework.cloud_event
def process_document(cloud_event):
    """
    Entrypoint de la Cloud Function Gen2.
    Se activa con el evento: google.cloud.storage.object.v1.finalized

    Pipeline ETL:
        1. EXTRACCIÓN: Valida y descarga el archivo desde GCS
        2. TRANSFORMACIÓN: Extrae datos estructurados con Gemini Vision
        3. CARGA: Inserta los datos en BigQuery

    En caso de error en cualquier etapa, inserta un registro de error
    en BigQuery con processing_status='error' para trazabilidad.

    Args:
        cloud_event: CloudEvent con datos del objeto de GCS
    """
    file_name = "unknown"
    processed_at = datetime.now(timezone.utc).isoformat()

    try:
        # ----------------------------------------
        # EXTRACCIÓN - Paso 1: Obtener datos del evento
        # ----------------------------------------
        data = cloud_event.data
        if not data:
            raise ValueError("El CloudEvent no contiene datos.")

        bucket_name = data.get("bucket")
        file_name = data.get("name")

        if not bucket_name or not file_name:
            raise ValueError(f"Faltan bucket o nombre de archivo en el evento. Datos: {data}")

        print(f"Procesando archivo: gs://{bucket_name}/{file_name}")

        # ----------------------------------------
        # EXTRACCIÓN - Paso 2: Validar tipo de archivo
        # ----------------------------------------
        file_extension = None
        file_name_lower = file_name.lower()
        for ext in SUPPORTED_FORMATS:
            if file_name_lower.endswith(ext):
                file_extension = ext
                break

        if not file_extension:
            raise ValueError(
                f"Formato no soportado: {file_name}. "
                f"Formatos soportados: {list(SUPPORTED_FORMATS.keys())}"
            )

        mime_type = SUPPORTED_FORMATS[file_extension]
        print(f"Tipo de archivo detectado: {mime_type}")

        # ----------------------------------------
        # EXTRACCIÓN - Paso 3: Descargar archivo desde GCS
        # ----------------------------------------
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        blob.reload()

        file_size = blob.size or 0
        if file_size > MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"Archivo demasiado grande: {file_size} bytes. "
                f"Máximo permitido: {MAX_FILE_SIZE_BYTES} bytes (10MB)"
            )

        print(f"Descargando archivo: {file_size} bytes...")
        file_bytes = blob.download_as_bytes()
        print(f"Archivo descargado correctamente.")

        # ----------------------------------------
        # TRANSFORMACIÓN - Paso 4: Preparar documento para Gemini
        # ----------------------------------------
        document_part = Part.from_data(
            data=file_bytes,
            mime_type=mime_type
        )

        # Fallback de inicialización de Vertex AI si no se inicializó al cargar
        if not PROJECT_ID:
            project_id = os.environ.get("PROJECT_ID")
            region = os.environ.get("REGION", "us-central1")
            vertexai.init(project=project_id, location=region)

        # ----------------------------------------
        # TRANSFORMACIÓN - Paso 5: Extraer datos con Gemini
        # ----------------------------------------
        extracted_data = get_gemini_extraction(document_part)

        # ----------------------------------------
        # TRANSFORMACIÓN - Paso 6: Limpiar y formatear datos
        # ----------------------------------------
        row_to_insert = transform_extracted_data(extracted_data, file_name, processed_at)
        print(f"Datos transformados: {row_to_insert}")

        # ----------------------------------------
        # CARGA - Paso 7: Insertar en BigQuery
        # ----------------------------------------
        insert_to_bigquery(row_to_insert)
        print(f"Pipeline ETL completado exitosamente para: {file_name}")

    except Exception as e:
        # ----------------------------------------
        # MANEJO DE ERRORES
        # Siempre insertar registro de error en BigQuery para trazabilidad
        # ----------------------------------------
        error_msg = f"Error en pipeline ETL para {file_name}: {str(e)}"
        print(error_msg)
        traceback.print_exc()

        error_row = {
            "file_name": file_name,
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "vendor_name": None,
            "document_date": None,
            "document_number": None,
            "total_amount": None,
            "currency": None,
            "line_items": None,
            "processing_status": "error"
        }

        try:
            insert_to_bigquery(error_row)
            print(f"Registro de error insertado en BigQuery para: {file_name}")
        except Exception as bq_err:
            print(f"Error crítico: No se pudo insertar registro de error en BigQuery: {bq_err}")

    # Retornar sin lanzar excepciones para evitar reintentos innecesarios de GCF
    return
