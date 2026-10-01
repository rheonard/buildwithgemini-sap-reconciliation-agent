import os
import sys
import json
import uuid
import httpx
import google.auth
import google.auth.transport.requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from tools import (
    list_bigquery_views,
    get_view_schema_and_sample,
    reconcile_dataset_vs_csv,
    sync_corrections_to_sap,
    reset_simulation_data
)

app = FastAPI(title="Google Cloud | SAP S/4HANA Data Governance Gateway")

DEMO_CSV_PATH = os.environ.get("DEMO_CSV_PATH", os.path.join(CURRENT_DIR, "sap_materials_100_truth.csv"))
AGENT_RUNTIME_ID = os.environ.get(
    "AGENT_ENGINE_RESOURCE_NAME",
    "projects/788260306257/locations/us-east1/reasoningEngines/3954721223761461248"
)
A2A_ENDPOINT = f"https://us-east1-aiplatform.googleapis.com/reasoningEngines/v1/{AGENT_RUNTIME_ID}/api/a2a/app"

_creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
_context_store = {}

def get_auth_token():
    _creds.refresh(google.auth.transport.requests.Request())
    return _creds.token

@app.post("/api/reset_simulation")
async def reset_simulation_api(request: Request):
    try:
        body = await request.json() if (await request.body()) else {}
    except:
        body = {}
    dataset_id = body.get("dataset_id", "sap_data")
    table_name = body.get("table_name", "sap_materials_100")
    res_str = reset_simulation_data(dataset_id=dataset_id, table_name=table_name)
    return JSONResponse(json.loads(res_str))

@app.get("/api/load_demo_csv")
async def get_demo_csv(reset_bq: bool = True):
    try:
        if reset_bq:
            reset_simulation_data()
        with open(DEMO_CSV_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        return JSONResponse({
            "status": "SUCCESS",
            "filename": "sap_materials_100_truth.csv",
            "csv_content": content,
            "bq_reset": reset_bq,
            "expected_accuracy": "85.0%",
            "discrepancies": 120
        })
    except Exception as e:
        return JSONResponse({"status": "ERROR", "message": str(e)}, status_code=500)

@app.post("/api/reconcile")
async def reconcile_api(request: Request):
    data = await request.json()
    csv_content = data.get("csv_content", "")
    view_name = data.get("view_name", "v_sap_materials_100")
    primary_key = data.get("primary_key", "material_id")
    secondary_key = data.get("secondary_key", "plant_id")
    field_mapping = data.get("field_mapping_json", "{}")
    dataset_id = data.get("dataset_id", "sap_data")

    res_str = reconcile_dataset_vs_csv(
        csv_content=csv_content,
        view_name=view_name,
        primary_key=primary_key,
        secondary_key=secondary_key,
        field_mapping_json=field_mapping,
        dataset_id=dataset_id
    )
    return JSONResponse(json.loads(res_str))

@app.post("/api/sync_sap")
async def sync_sap_api(request: Request):
    data = await request.json()
    approved = data.get("approved_corrections", [])
    expert_user = data.get("expert_user", "Ing. Carlos Mendoza (Lead SAP MM / Data Governance)")
    justification = data.get("justification", "Autorizado por auditoría de calidad de datos")
    table_name = data.get("table_name", "sap_materials_100")
    dataset_id = data.get("dataset_id", "sap_data")
    sap_client = data.get("sap_client", "PRD-100 (S/4HANA Enterprise)")
    authorization_token = data.get("authorization_token", "SAP-AUTH-SEC-892147")

    res_str = sync_corrections_to_sap(
        approved_corrections_json=json.dumps(approved),
        expert_user=expert_user,
        justification=justification,
        dataset_id=dataset_id,
        table_name=table_name,
        sap_client=sap_client,
        authorization_token=authorization_token
    )
    return JSONResponse(json.loads(res_str))

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    message = data.get("message", "")
    user_id = data.get("user_id", "default_user")

    try:
        token = get_auth_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        ctx_id = _context_store.get(user_id)
        msg_payload = {
            "role": "user",
            "parts": [{"text": message}],
            "messageId": str(uuid.uuid4())
        }
        if ctx_id:
            msg_payload["contextId"] = ctx_id

        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/send",
            "params": {
                "message": msg_payload
            }
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(A2A_ENDPOINT, headers=headers, json=payload)
            resp_data = resp.json()

            result = resp_data.get("result", {})
            if "contextId" in result:
                _context_store[user_id] = result["contextId"]

            parts_out = []
            for art in result.get("artifacts", []):
                for p in art.get("parts", []):
                    if "text" in p:
                        parts_out.append({"kind": "text", "text": p["text"]})
                    elif p.get("kind") == "text":
                        parts_out.append({"kind": "text", "text": p.get("text", "")})

            if not parts_out:
                if "error" in resp_data:
                    parts_out.append({"kind": "text", "text": f"Error del agente: {resp_data['error']}"})
                else:
                    parts_out.append({"kind": "text", "text": "Mensaje procesado por el agente desplegado en Agent Platform."})

            return JSONResponse({"parts": parts_out})
    except Exception as e:
        return JSONResponse({"parts": [{"kind": "text", "text": f"Error comunicando con Agent Platform: {e}"}]})

static_dir = os.path.join(CURRENT_DIR, "static")
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
