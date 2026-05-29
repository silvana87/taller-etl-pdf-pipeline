import os
import json
import traceback
from datetime import datetime, timezone
import functions_framework
from google.cloud import storage
from google.cloud import bigquery
import vertexai
from vertexai.generative_models import GenerativeModel, Part

# Global/Module level lazy initialization
# The Vertex AI client initialization will happen during module load or on first invocation
PROJECT_ID = os.environ.get("PROJECT_ID")
REGION = os.environ.get("REGION", "us-central1")

if PROJECT_ID:
    try:
        vertexai.init(project=PROJECT_ID, location=REGION)
        print(f"Vertex AI initialized with project: {PROJECT_ID}, region: {REGION}")
    except Exception as init_err:
        print(f"Warning: Failed to initialize Vertex AI at module load: {init_err}")

def parse_gemini_response(text):
    """
    Parses the response text from Gemini into a Python dictionary.
    Handles potential markdown formatting (backticks, JSON block wrappers)
    and falls back to ast.literal_eval for single-quoted dict-like responses.
    """
    if not text:
        raise ValueError("Empty response text received from Gemini.")
    
    cleaned = text.strip()
    
    # Remove markdown code block wraps (e.g. ```json ... ```)
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
        
    cleaned = cleaned.strip()
    
    # Attempt 1: Standard JSON parsing
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as json_err:
        print(f"Direct JSON parsing failed: {json_err}. Attempting python dict evaluation...")
        
        # Attempt 2: Use ast.literal_eval for Python dictionary syntax (single quotes)
        import ast
        try:
            val = ast.literal_eval(cleaned)
            if isinstance(val, dict):
                return val
        except Exception as ast_err:
            print(f"AST dict parsing failed: {ast_err}")
            
        # Re-raise original JSON decode error if both fail
        raise json_err

def get_gemini_extraction(document_part, prompt):
    """
    Calls the Gemini Vision model to extract structured data.
    If the response JSON is invalid, it retries exactly once with the same prompt.
    """
    model = GenerativeModel("gemini-2.5-flash")
    max_attempts = 2
    
    for attempt in range(max_attempts):
        try:
            print(f"Calling Gemini Vision (attempt {attempt + 1}/{max_attempts})...")
            response = model.generate_content([document_part, prompt])
            
            # Check for safety blocks or empty responses
            if not response.text:
                raise ValueError("Gemini returned an empty text response.")
                
            print(f"Raw Gemini response: {response.text}")
            parsed_json = parse_gemini_response(response.text)
            return parsed_json
            
        except Exception as e:
            print(f"Gemini attempt {attempt + 1} failed: {e}")
            if attempt == max_attempts - 1:
                # Re-raise the exception on the last attempt
                raise RuntimeError(f"Gemini extraction failed after {max_attempts} attempts: {e}")

@functions_framework.cloud_event
def process_document(cloud_event):
    """
    Cloud Function Gen2 Entrypoint triggered by a Cloud Storage object finalization event.
    """
    # 1. Extraction initialization
    file_name = "unknown"
    processed_at = datetime.now(timezone.utc).isoformat()
    
    try:
        data = cloud_event.data
        if not data:
            raise ValueError("CloudEvent data is empty.")
            
        bucket_name = data.get("bucket")
        file_name = data.get("name")
        
        if not bucket_name or not file_name:
            raise ValueError(f"Missing bucket or name in event data. Data received: {data}")
            
        print(f"Processing event for bucket: {bucket_name}, file: {file_name}")
        
        # Validate file extension and determine MIME type
        file_name_lower = file_name.lower()
        if file_name_lower.endswith('.pdf'):
            mime_type = 'application/pdf'
        elif file_name_lower.endswith('.jpg') or file_name_lower.endswith('.jpeg'):
            mime_type = 'image/jpeg'
        elif file_name_lower.endswith('.png'):
            mime_type = 'image/png'
        else:
            raise ValueError(f"Unsupported file format: {file_name}. Only PDF, JPG, and PNG files are supported.")
            
        # Download the file from GCS using google-cloud-storage
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        
        # Reload blob to fetch metadata (size)
        blob.reload()
        file_size = blob.size or 0
        
        # Enforce size limit (up to 10MB)
        max_size_bytes = 10 * 1024 * 1024
        if file_size > max_size_bytes:
            raise ValueError(f"File size {file_size} bytes exceeds the maximum supported size of 10MB.")
            
        print(f"Downloading file of size {file_size} bytes...")
        file_bytes = blob.download_as_bytes()
        
        # 2. Transformation
        # Prepare GCS file data part for Vertex AI Generative Model
        document_part = Part.from_data(
            data=file_bytes,
            mime_type=mime_type
        )
        
        # Exact prompt required for extraction
        prompt = """Analiza este documento y extrae los siguientes campos en formato JSON válido. 
   Si un campo no existe en el documento, usa null.
   Devuelve SOLO el JSON, sin texto adicional, sin markdown, sin backticks:
   {
     'vendor_name': 'nombre del proveedor o emisor del documento',
     'document_date': 'fecha en formato YYYY-MM-DD',
     'document_number': 'número de documento, factura o referencia',
     'total_amount': 'monto total como número decimal',
     'currency': 'código de moneda de 3 letras (USD, BOB, EUR, etc)',
     'line_items': [{'description': 'descripción del item', 'amount': monto_decimal}]
   }"""
        
        # Make sure project initialization is complete
        if not PROJECT_ID:
            # Fallback lazy init inside the execution loop
            project_id = os.environ.get("PROJECT_ID")
            region = os.environ.get("REGION", "us-central1")
            vertexai.init(project=project_id, location=region)
            
        # Retrieve parsed JSON from Gemini
        extracted_data = get_gemini_extraction(document_part, prompt)
        
        # Format/Clean specific fields
        vendor_name = extracted_data.get("vendor_name")
        if isinstance(vendor_name, str):
            vendor_name = vendor_name.strip()
            
        # Clean document_date: ensure string or None
        document_date = extracted_data.get("document_date")
        if document_date in [None, "null", "None", ""]:
            document_date_val = None
        else:
            document_date_val = str(document_date).strip()
            
        document_number = extracted_data.get("document_number")
        if document_number in [None, "null", "None", ""]:
            document_number_val = None
        else:
            document_number_val = str(document_number).strip()
            
        # Parse total_amount to float if possible
        total_amount = extracted_data.get("total_amount")
        if total_amount in [None, "null", "None", ""]:
            total_amount_val = None
        else:
            try:
                if isinstance(total_amount, str):
                    clean_amount = total_amount.replace('$', '').replace(',', '').strip()
                    total_amount_val = float(clean_amount)
                else:
                    total_amount_val = float(total_amount)
            except Exception as amt_err:
                print(f"Warning: Could not cast total_amount '{total_amount}' to float. Setting to None. Error: {amt_err}")
                total_amount_val = None
                
        currency = extracted_data.get("currency")
        if isinstance(currency, str):
            currency = currency.strip()
            
        # line_items must be inserted as a serialized JSON string
        line_items_data = extracted_data.get("line_items")
        if line_items_data is not None:
            line_items_str = json.dumps(line_items_data)
        else:
            line_items_str = None
            
        # Create row dictionary matching the exact table schema
        row_to_insert = {
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
        
        # 3. Load to BigQuery
        bq_client = bigquery.Client()
        project_id = os.environ.get("PROJECT_ID")
        table_id = f"{project_id}.documentos_procesados.extracciones"
        
        print(f"Inserting success record into BigQuery: {row_to_insert}")
        errors = bq_client.insert_rows_json(table_id, [row_to_insert])
        if errors:
            raise RuntimeError(f"BigQuery insertion failed: {errors}")
            
        print(f"Successfully processed document '{file_name}' and loaded details into BigQuery.")
        
    except Exception as e:
        # Error handling path: Log the error and insert failure record in BigQuery
        error_msg = f"Error in ETL pipeline for file {file_name}: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        
        # Prepare error logging row (all extracted fields set to null, status set to 'error')
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
            bq_client = bigquery.Client()
            project_id = os.environ.get("PROJECT_ID")
            table_id = f"{project_id}.documentos_procesados.extracciones"
            
            print(f"Inserting error record into BigQuery: {error_row}")
            errors = bq_client.insert_rows_json(table_id, [error_row])
            if errors:
                print(f"Failed to insert error log record in BigQuery: {errors}")
            else:
                print(f"Successfully recorded error status in BigQuery for {file_name}.")
        except Exception as bq_err:
            print(f"Critical error: Failed to insert error record in BigQuery: {bq_err}")
            
    # Exit cleanly without raising exceptions to prevent GCF execution failure / retries
    return
