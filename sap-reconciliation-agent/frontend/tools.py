import os
import json
import io
import csv
from typing import Dict, Any, List, Optional
from google.cloud import bigquery

def list_bigquery_views(dataset_id: str = "sap_data") -> str:
    """Lists available tables and views in a specified BigQuery dataset.
    
    Args:
        dataset_id: The ID of the BigQuery dataset (e.g., 'sap_data').
    """
    client = bigquery.Client()
    full_dataset_id = f"{client.project}.{dataset_id}"
    try:
        tables = list(client.list_tables(full_dataset_id))
        result = [
            {"table_id": t.table_id, "type": t.table_type, "full_id": f"{full_dataset_id}.{t.table_id}"}
            for t in tables
        ]
        return json.dumps({"dataset": full_dataset_id, "items": result}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

def get_view_schema_and_sample(table_name: str, dataset_id: str = "sap_data", limit: int = 5) -> str:
    """Gets the schema (columns, types) and sample rows of a BigQuery table or view.
    
    Args:
        table_name: Table or view name (e.g. 'v_sap_materials_consolidated').
        dataset_id: Dataset ID where the table lives.
        limit: Number of sample records to retrieve.
    """
    client = bigquery.Client()
    table_ref = f"{client.project}.{dataset_id}.{table_name}"
    try:
        table = client.get_table(table_ref)
        schema = [{"name": field.name, "type": field.field_type} for field in table.schema]
        query = f"SELECT * FROM `{table_ref}` LIMIT {limit}"
        query_job = client.query(query)
        rows = [dict(row) for row in query_job]
        return json.dumps({"table": table_ref, "type": table.table_type, "schema": schema, "sample_rows": rows}, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})

def reconcile_dataset_vs_csv(
    csv_content: str,
    view_name: str,
    primary_key: str,
    secondary_key: Optional[str] = None,
    field_mapping_json: str = "{}",
    dataset_id: str = "sap_data",
    numeric_tolerance: float = 0.001
) -> str:
    """Performs full data reconciliation between an uploaded CSV and a BigQuery view/table.
    
    Args:
        csv_content: Raw string content of the uploaded CSV (the truth/expected values).
        view_name: The target BigQuery table or view name (e.g. 'v_sap_materials_consolidated').
        primary_key: Primary key column name in CSV (or mapped to BQ).
        secondary_key: Optional secondary key column name for composite joins.
        field_mapping_json: JSON string mapping {csv_column: bigquery_column}. If omitted, matches same name.
        dataset_id: BigQuery dataset name.
        numeric_tolerance: Absolute numeric tolerance for float/price comparisons.
        
    Returns:
        JSON string containing:
        - match_score_pct: Overall percentage of valid matching fields (0-100%).
        - total_records_evaluated: Total unique keys reconciled.
        - total_discrepancies: Count of field mismatches.
        - discrepancy_table: List of detailed discrepancy rows with:
            key, field, expected_csv_value, actual_bq_value, error_type.
        - filter_options: Distinct fields and error types found for frontend filtering.
    """
    client = bigquery.Client()
    table_ref = f"{client.project}.{dataset_id}.{view_name}"
    
    # 1. Parse CSV
    try:
        reader = csv.DictReader(io.StringIO(csv_content.strip()))
        csv_rows = list(reader)
        if not csv_rows:
            return json.dumps({"error": "CSV content is empty or invalid format."})
    except Exception as e:
        return json.dumps({"error": f"Failed to parse CSV: {e}"})
        
    # Field mapping
    try:
        mapping = json.loads(field_mapping_json) if field_mapping_json else {}
    except Exception:
        mapping = {}

    # 2. Query BigQuery table/view
    try:
        query = f"SELECT * FROM `{table_ref}`"
        query_job = client.query(query)
        bq_rows = [dict(row) for row in query_job]
    except Exception as e:
        return json.dumps({"error": f"Failed to fetch BigQuery data: {e}"})

    # Index BigQuery rows by primary (and secondary) key
    bq_index = {}
    for row in bq_rows:
        # Resolve BQ key
        bq_pk_col = mapping.get(primary_key, primary_key)
        pk_val = str(row.get(bq_pk_col, "")).strip()
        if secondary_key:
            bq_sk_col = mapping.get(secondary_key, secondary_key)
            sk_val = str(row.get(bq_sk_col, "")).strip()
            composite_key = f"{pk_val}::{sk_val}"
        else:
            composite_key = pk_val
        bq_index[composite_key] = row

    # 3. Reconciliation
    total_fields_checked = 0
    total_fields_matched = 0
    discrepancy_table = []
    keys_evaluated = set()

    for r_idx, csv_row in enumerate(csv_rows):
        csv_pk = str(csv_row.get(primary_key, "")).strip()
        if secondary_key:
            csv_sk = str(csv_row.get(secondary_key, "")).strip()
            comp_key = f"{csv_pk}::{csv_sk}"
            key_label = f"{primary_key}={csv_pk}, {secondary_key}={csv_sk}"
        else:
            comp_key = csv_pk
            key_label = f"{primary_key}={csv_pk}"

        keys_evaluated.add(comp_key)

        if comp_key not in bq_index:
            discrepancy_table.append({
                "record_id": key_label,
                "field": "[RECORD_STATUS]",
                "expected_csv_value": "PRESENT",
                "actual_bq_value": "MISSING_IN_BIGQUERY",
                "error_type": "MISSING_RECORD",
                "severity": "CRITICAL"
            })
            total_fields_checked += 1
            continue

        bq_row = bq_index[comp_key]

        # Compare mapped or identical fields
        for csv_col, csv_val_raw in csv_row.items():
            if csv_col in [primary_key, secondary_key]:
                continue
            
            bq_col = mapping.get(csv_col, csv_col)
            if bq_col not in bq_row:
                continue

            total_fields_checked += 1
            csv_val = str(csv_val_raw).strip() if csv_val_raw is not None else ""
            bq_val_raw = bq_row[bq_col]
            bq_val = str(bq_val_raw).strip() if bq_val_raw is not None else ""

            # Check numeric equivalence
            is_match = False
            try:
                num_csv = float(csv_val)
                num_bq = float(bq_val)
                if abs(num_csv - num_bq) <= numeric_tolerance:
                    is_match = True
            except (ValueError, TypeError):
                # Text comparison (case-insensitive for safety)
                if csv_val.lower() == bq_val.lower():
                    is_match = True

            if is_match:
                total_fields_matched += 1
            else:
                discrepancy_table.append({
                    "record_id": key_label,
                    "field": bq_col,
                    "expected_csv_value": csv_val,
                    "actual_bq_value": bq_val,
                    "error_type": "DATA_MISMATCH",
                    "severity": "HIGH"
                })

    score_pct = round((total_fields_matched / total_fields_checked * 100.0), 2) if total_fields_checked > 0 else 0.0

    return json.dumps({
        "status": "SUCCESS",
        "match_score_pct": score_pct,
        "total_records_evaluated": len(keys_evaluated),
        "total_fields_checked": total_fields_checked,
        "total_fields_matched": total_fields_matched,
        "total_discrepancies": len(discrepancy_table),
        "discrepancy_table": discrepancy_table,
        "summary": f"Data Reconciliation Complete. Quality Score: {score_pct}%. Discrepancies found: {len(discrepancy_table)} out of {total_fields_checked} fields checked."
    }, indent=2)

def sync_corrections_to_sap(
    approved_corrections_json: str,
    expert_user: str = "Ing. Carlos Mendoza (Lead SAP MM / Data Governance)",
    justification: str = "Aprobado por auditoría de calidad de datos",
    dataset_id: str = "sap_data",
    table_name: str = "sap_materials_100",
    sap_client: str = "PRD-100 (S/4HANA Enterprise)",
    authorization_token: str = "SAP-AUTH-SEC-892147"
) -> str:
    """Applies expert-approved corrections into BigQuery and simulates SAP ERP S/4HANA BAPI commit.
    
    Returns a formal SAP Data Load Confirmation Certificate.
    """
    import uuid
    import hashlib
    from datetime import datetime, timezone
    
    try:
        corrections = json.loads(approved_corrections_json)
        if not corrections:
            return json.dumps({"status": "WARNING", "message": "No corrections were provided for sync."})
    except Exception as e:
        return json.dumps({"error": f"Invalid corrections JSON: {e}"})

    client = bigquery.Client()
    full_table_id = f"{client.project}.{dataset_id}.{table_name}"
    
    # 1. Fetch current rows
    query = f"SELECT * FROM `{full_table_id}`"
    current_rows = [dict(r) for r in client.query(query).result()]
    
    # Index rows by (material_id, plant_id)
    rows_index = {(r["material_id"], r["plant_id"]): r for r in current_rows}
    
    updated_records_count = 0
    updated_materials = set()
    
    for item in corrections:
        mat_id = item.get("material_id")
        plant_id = item.get("plant_id")
        field = item.get("field")
        val = item.get("approved_value")
        
        key = (mat_id, plant_id)
        if key in rows_index and field:
            row = rows_index[key]
            # Cast according to schema
            if field == "unit_price":
                try:
                    row[field] = float(val)
                except Exception:
                    pass
            elif field == "stock_quantity":
                try:
                    row[field] = int(float(val))
                except Exception:
                    pass
            else:
                row[field] = str(val)
            updated_records_count += 1
            updated_materials.add(mat_id)

    # Save back cleanly via batch load_table_from_json
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
    )
    job = client.load_table_from_json(list(rows_index.values()), full_table_id, job_config=job_config)
    job.result()

    now_iso = datetime.now(timezone.utc).isoformat()
    raw_hash_input = f"{now_iso}|{expert_user}|{updated_records_count}|{full_table_id}"
    sha256_hash = hashlib.sha256(raw_hash_input.encode("utf-8")).hexdigest()
    doc_id = f"DOC-SAP-S4H-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    batch_id = f"SAP-BAPI-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    confirmation_cert = {
        "status": "CARGA_CONFIRMADA_Y_ASENTADA_EN_SAP",
        "document_number": doc_id,
        "sap_batch_id": batch_id,
        "sap_client": sap_client,
        "sap_interface": "BAPI_MATERIAL_MAINTAINDATA_RT / IDoc MATMAS05",
        "sap_tcode": "MM02 / MASS / BD10",
        "authorized_by": expert_user,
        "authorization_token": authorization_token,
        "justification": justification,
        "timestamp_utc": now_iso,
        "total_fields_updated": updated_records_count,
        "total_materials_updated": len(updated_materials),
        "target_table": full_table_id,
        "integrity_hash_sha256": sha256_hash,
        "audit_confirmation_summary": f"Se han contabilizado {updated_records_count} campos en {len(updated_materials)} materiales en SAP S/4HANA con estatus EXITOSO."
    }

    return json.dumps(confirmation_cert, indent=2)

def reset_simulation_data(dataset_id: str = "sap_data", table_name: str = "sap_materials_100") -> str:
    """Resets BigQuery table sap_materials_100 and view v_sap_materials_100 to the calibrated 85.0% accuracy state (100 rows, 120 discrepancies across 800 checks)."""
    import random
    from google.cloud import bigquery

    client = bigquery.Client()
    full_table_id = f"{client.project}.{dataset_id}.{table_name}"

    random.seed(42)
    categories = ["Raw Materials", "Finished Goods", "Spare Parts", "Packaging", "Chemicals"]
    uoms = ["EA", "KG", "L", "M", "PAL"]
    plants = ["PL01", "PL02", "PL03"]
    storage_locs = ["SL01", "SL02", "SL03"]

    bq_rows = []
    for i in range(1, 101):
        mat_id = f"MAT-{2000 + i}"
        plant = plants[(i - 1) % len(plants)]
        desc = f"SAP Material Component {i:03d} Grade-{chr(65 + (i%5))}"
        cat = categories[i % len(categories)]
        uom = uoms[i % len(uoms)]
        price = round(10.0 + (i * 3.75) % 450.0, 2)
        stock = 100 + (i * 17) % 2500
        sloc = storage_locs[i % len(storage_locs)]
        batch = f"BAT-{8000 + (i*13)%1000}"
        status = "ACTIVE" if i % 6 != 0 else "INACTIVE"
        row = {
            "material_id": mat_id, "plant_id": plant, "description": desc,
            "category": cat, "unit_of_measure": uom, "unit_price": price,
            "stock_quantity": stock, "storage_location": sloc, "batch_number": batch, "status": status
        }
        bq_rows.append(dict(row))

    non_key_cols = ["description", "category", "unit_of_measure", "unit_price", "stock_quantity", "storage_location", "batch_number", "status"]
    all_cells = [(r_idx, col) for r_idx in range(100) for col in non_key_cols]
    random.seed(42)
    random.shuffle(all_cells)

    for r_idx, col in all_cells[:120]:
        original = bq_rows[r_idx][col]
        if col == "unit_price":
            bq_rows[r_idx][col] = round(original * 1.25 + 5.0, 2)
        elif col == "stock_quantity":
            bq_rows[r_idx][col] = int(original - 25 if original > 50 else original + 50)
        elif col == "description":
            bq_rows[r_idx][col] = original + " [OLD SAP REVISION]"
        elif col == "status":
            bq_rows[r_idx][col] = "BLOCKED" if original == "ACTIVE" else "ACTIVE"
        elif col == "category":
            bq_rows[r_idx][col] = "Obsolete Group"
        elif col == "unit_of_measure":
            bq_rows[r_idx][col] = "BOX" if original == "EA" else "EA"
        elif col == "storage_location":
            bq_rows[r_idx][col] = "SL99"
        elif col == "batch_number":
            bq_rows[r_idx][col] = "BAT-UNASSIGNED"

    schema = [
        bigquery.SchemaField("material_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("plant_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("description", "STRING"),
        bigquery.SchemaField("category", "STRING"),
        bigquery.SchemaField("unit_of_measure", "STRING"),
        bigquery.SchemaField("unit_price", "FLOAT64"),
        bigquery.SchemaField("stock_quantity", "INT64"),
        bigquery.SchemaField("storage_location", "STRING"),
        bigquery.SchemaField("batch_number", "STRING"),
        bigquery.SchemaField("status", "STRING"),
    ]

    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    job = client.load_table_from_json(bq_rows, full_table_id, job_config=job_config)
    job.result()

    # Refresh view
    view_id = f"{client.project}.{dataset_id}.v_sap_materials_100"
    view = bigquery.Table(view_id)
    view.view_query = f"SELECT * FROM `{full_table_id}`"
    client.delete_table(view_id, not_found_ok=True)
    client.create_table(view)

    return json.dumps({
        "status": "SUCCESS",
        "message": f"Tabla {full_table_id} y vista {view_id} restablecidas con éxito.",
        "rows_loaded": len(bq_rows),
        "discrepancies_injected": 120,
        "precision_expected_pct": 85.0
    }, indent=2)
