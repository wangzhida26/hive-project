# Yundu Life Retail — Enterprise Data Warehouse & Analytics Visualization System

[简体中文](README.md) | **English**

> Enterprise Project Practicum · Team 200A · Weeks 1–5: environment setup, data cleaning, 4-layer warehouse modeling, KPI system, sales forecasting, NL2SQL, visualization (Superset / ECharts / Streamlit) and one-command Docker deployment.

## Overview

A complete, end-to-end enterprise-grade data warehouse and business analytics system built for "Yundu Life", a fictional new-retail company. Raw CSV business data (6 source tables) flows through a layered warehouse (ODS → STG → DWD → DWS → ADS) and finally serves KPI dashboards, a data screen, a 7-day GMV forecast, and a natural-language querying app.

**Key numbers**

- 15,600 raw orders → 14,696 clean fact rows (all five dirty-data categories fixed at 100% fix rate)
- 4-layer warehouse + STG cleaning pipeline, star schema with 366 dynamic partitions (ORC)
- 11 unified KPI metrics, 6 ADS application tables, 5 DWS summary tables
- NL2SQL dual engine (rules + LangChain), 12-question live test log
- Full pipeline rebuild in 3m22s (`rebuild_pipeline.sh`)

## Architecture

```
Business CSV (6 source tables)
  → ODS  (raw landing zone, TEXTFILE)
  → STG  (3-stage cleaning pipeline, fully traceable)
  → DWD  (star schema: 1 fact + 4 dims, ORC, 366 date partitions)
  → DWS  (5 granularity-level daily summaries)
  → ADS  (6 application marts: KPI / GMV daily / category / store / channel / user value)
  → ├→ Superset dashboard (via MySQL report mirror)
     ├→ ECharts data screen (offline single-file, compliant China map)
     ├→ Streamlit NL2SQL Q&A app (Hive beeline / MySQL dual backend)
     └→ Python forecasting (3 models + 2 baselines, MAE/MAPE)
```

## Features

- **Data quality**: 5-dimension quality assessment + 3-stage cleaning pipeline (enum standardization, anomaly & format, split-merge & code mapping), all intermediate results traceable
- **Warehouse modeling**: star schema, naming conventions, dynamic partitioning, partition pruning verified with EXPLAIN
- **Analytics**: unified KPI system (GMV, AOV, repurchase rate, refund rate…), anomaly attribution (2024-11-06 GMV plunge), 7-day GMV forecast
- **AI integration**: NL2SQL with SQL guardrails and dual execution backends (`NL2SQL_BACKEND=hive|mysql`)
- **Visualization**: Apache Superset dashboard auto-configured via REST API; ECharts big screen (1920×1080, scale-adaptive, offline)
- **Deployment**: 6-service Docker Compose with healthchecks and `.env` secret injection; one-script full rebuild

## Quick Start

```bash
# 1. Prerequisites: Docker Desktop (WSL2), Git
cp .env.example .env        # fill in your passwords / keys

# 2. Start all services (MySQL / Hive / ClickHouse / Superset / Streamlit app)
docker compose up -d

# 3. Build the warehouse end-to-end (ODS → STG → DWD → DWS → ADS → mirror)
bash rebuild_pipeline.sh

# 4. Open the apps
#    Superset dashboard: http://localhost:8088
#    NL2SQL Q&A app:     http://localhost:8501
#    Data screen:        open screen/云购生活数据大屏.html in a browser
```

## Tech Stack

| Layer | Technology |
| --- | --- |
| Warehouse | Apache Hive 4.0, ORC, dynamic partitioning |
| Metadata / Mirror | MySQL 8.0 |
| Modeling | Python (statsmodels), pandas |
| NL2SQL | Rules engine + LangChain (LCEL) |
| BI | Apache Superset 6.1 (REST auto-setup) |
| Big screen | ECharts 5.5 (vendored, offline) |
| Q&A app | Streamlit + Plotly |
| Deployment | Docker Compose (6 services, healthcheck) |

## Repository Layout

```
ydsh-dw/
├── docker-compose.yml      # 6-service orchestration
├── rebuild_pipeline.sh     # one-command full rebuild (~3.5 min)
├── sql/                    # ods / quality / clean / dwd / dws / ads / analysis
├── analysis/               # forecasting, KPI sheet, MySQL mirror, Superset setup, stress test
├── nl2sql/                 # schema extractor, dual engine, 12-question test log
├── app/                    # Streamlit Q&A app (containerized)
├── screen/                 # ECharts data screen + vendor assets
└── docs/                   # requirement doc, cleaning report, architecture, deployment manual, API guide
```

## Documentation

- [需求文档 (Requirements, zh)](docs/需求文档.docx)
- [数据质量清洗报告 (Data Cleaning Report, zh)](docs/数据质量清洗报告.docx)
- [数仓架构设计文档 (Architecture Design, zh)](docs/数仓架构设计文档.docx)
- [部署手册 (Deployment Manual, zh)](docs/部署手册.docx)
- [API配置指南 (API Configuration Guide, zh)](docs/API配置指南.docx)

## Team

**Team 200A** — Qingdao City University

| Role | Member |
| --- | --- |
| Project Manager / Git | Chen Jinsong |
| Data Engineer | Wang Zhida |
| Data Analyst | Liu Chang |
| Visualization Engineer | Liu Zhengyang |

## License

For educational use in the Enterprise Project Practicum course.
