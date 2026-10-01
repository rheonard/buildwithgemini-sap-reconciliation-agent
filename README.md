<div align="center">

# 📊 SAP S/4HANA & BigQuery Data Reconciliation Agent
### Automated Data Quality, Field Validation & Expert Authorization Governance

An enterprise agentic application built on Google Cloud with the **Agent Development Kit (ADK)**, **agents-cli**, **Vertex AI Agent Engine**, and **Google Cloud Run**.

![Google Cloud](https://img.shields.io/badge/Google%20Cloud-Vertex%20AI%20Agent%20Engine-4285F4?logo=googlecloud&logoColor=white)
![BigQuery](https://img.shields.io/badge/Google%20Cloud-BigQuery-4285F4?logo=googlecloud&logoColor=white)
![Cloud Run](https://img.shields.io/badge/Google%20Cloud-Cloud%20Run-4285F4?logo=googlecloud&logoColor=white)
![A2A Protocol](https://img.shields.io/badge/Protocol-A2A%20v0.3%20JSON--RPC-blue)
![Built with ADK](https://img.shields.io/badge/Built%20with-ADK%20%2B%20agents--cli-34A853)

</div>

---

## 🌟 Overview

Enterprise migrations and daily operations between **SAP ERP (S/4HANA)** and **Google Cloud BigQuery** require strict data reconciliation. This project provides an end-to-end intelligent agent and web governance portal to:

1. **Inspect BigQuery Datasets & Views**: Dynamically query datasets, tables, consolidated views, schemas, and sample records.
2. **Reconcile Source-of-Truth CSV/Excel against BigQuery Views**:
   - Compare 100+ material records across 10 fields with composite keys (`material_id`, `plant_id`).
   - Detect numeric and categorical discrepancies with configurable tolerances.
   - Calculate precision scores (e.g. 85.0% data accuracy).
3. **Interactive Data Quality Dashboard**:
   - Google Material Design 3 interface with dynamic filters by SAP Plant (`PL01`, `PL02`, `PL03`), error type, and field.
   - Simulation generator to calibrate discrepancy states for validation testing.
4. **Human-in-the-Loop Expert Authorization & SAP S/4HANA Commit**:
   - Review and select discrepancies for correction.
   - Expert approval workflow (Lead SAP MM / Data Governance).
   - Atomic batch update into BigQuery (`load_table_from_json`) simulating SAP S/4HANA BAPI (`BAPI_MATERIAL_MAINTAINDATA_RT`) and IDoc (`MATMAS05`).
   - Issuance of formal **Certificado Oficial de Carga y Asentamiento SAP** with SHA-256 cryptographic audit hash and downloadable JSON receipt.
5. **Conversational Agent (A2A Protocol)**:
   - Floating Gemini Assistant drawer communicating directly with the reasoning engine over the Agent-to-Agent protocol.

---

## 🏗️ Architecture

```
                 +-------------------------------------------------------+
                 |       Google Material Design 3 Web Frontend           |
                 |      (FastAPI + Cloud Run / Local Port 8080)          |
                 +-------------------------------------------------------+
                                    |                     |
         Reconciliation / Sync      |                     | A2A JSON-RPC (Bearer Auth)
                                    v                     v
                 +---------------------+       +------------------------------------+
                 | Google BigQuery     |       | Vertex AI Agent Engine             |
                 | Dataset: sap_data   |<----->| (Reasoning Engine / ADK Agent)     |
                 | Table: sap_materials|       | - list_bigquery_views              |
                 | View: v_sap_...     |       | - get_view_schema_and_sample       |
                 +---------------------+       | - reconcile_dataset_vs_csv         |
                                               | - sync_corrections_to_sap          |
                                               +------------------------------------+
```

---

## 📁 Repository Structure

```
.
├── sap-reconciliation-agent/
│   ├── app/
│   │   ├── agent.py                 # ADK Agent definition & prompt
│   │   └── tools.py                 # BigQuery tools, reconciliation & SAP sync logic
│   ├── frontend/
│   │   ├── static/
│   │   │   └── index.html           # Material Design 3 dashboard & Gemini chat drawer
│   │   ├── server.py                # Cloud Run FastAPI server
│   │   ├── local_server.py          # Local development server
│   │   ├── requirements.txt         # Frontend dependencies
│   │   └── Dockerfile               # Production container definition
│   ├── sap_materials_100_truth.csv  # 100-row reference dataset with 10 columns
│   ├── agents-cli-manifest.yaml     # Agent deployment manifest
│   └── pyproject.toml               # Python project configuration
├── project_brief.md                 # Project brief & tool coverage specification
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- `gcloud` CLI authenticated to Google Cloud:
  ```bash
  gcloud auth login
  gcloud auth application-default login
  gcloud config set project <YOUR_PROJECT_ID>
  ```
- `uv` package manager:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

### Local Development

1. **Install agent dependencies:**
   ```bash
   cd sap-reconciliation-agent
   uv sync
   ```

2. **Start the local governance server:**
   ```bash
   python3 frontend/local_server.py
   ```
   Open your browser at `http://localhost:8080`.

3. **Deploy to Vertex AI Agent Engine:**
   ```bash
   uv run agents-cli deploy --project <YOUR_PROJECT_ID>
   ```

4. **Deploy the Frontend to Google Cloud Run:**
   ```bash
   gcloud run deploy sap-reconciliation-frontend \
     --source frontend/ \
     --region us-east1 \
     --allow-unauthenticated \
     --set-env-vars AGENT_ENGINE_RESOURCE_NAME=<YOUR_AGENT_RESOURCE_NAME>
   ```

---

## 🛡️ License

Apache-2.0
