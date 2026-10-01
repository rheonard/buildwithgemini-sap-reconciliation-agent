# My agent: SAP BigQuery Data Reconciliation Agent (SAP Data QA Concierge)
One-liner: A conversational data quality and reconciliation agent that helps data engineers and business analysts validate SAP consolidated/base views in BigQuery against uploaded source-of-truth CSV/Excel files using dynamic key matching, discrepancy tables, and overall accuracy scoring.

Tool coverage:
- Memory: Remembers mapping templates between SAP views and standard CSV formats, past reconciliation reports, user preferences, and business validation rules.
- Tools: BigQuery query executor (fetching views/tables), CSV parser & validator, reconciliation engine (primary/secondary key join & field-by-field diff).
- Catalog/UI: Discrepancy comparison tables rendered via A2UI/FastAPI (showing Source vs BigQuery values, mismatch flags), filters by dataset/view and CSV columns, accuracy score card summary.
- Image gen: Visual dashboard summary / infographic badge of data quality health status.
- Sandbox: Python code sandbox for running high-speed matching algorithms, complex tolerance validations, and computing statistical accuracy scores.

Recommended for every project: memory, storage, tools, image generation, A2UI
Agent-specific / stretch (pick what fits): Code sandbox for high-performance reconciliation calculations, Cloud Run frontend with file upload interface, BigQuery API integration.
