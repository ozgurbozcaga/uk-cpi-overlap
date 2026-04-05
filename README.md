# UK CPS / UK ETS Coverage Overlap Pipeline

Estimates the coverage overlap between the UK Carbon Price Support (CPS)
and the UK Emissions Trading Scheme (UK ETS) at installation level.

This is the first module of a broader carbon pricing instrument overlap
analysis for the World Bank State & Trends of Carbon Pricing publication.

---

## Background

The UK Carbon Price Support (CCL1/6) is a top-up tax applied to fossil
fuels used for electricity generation in Great Britain. Because UK ETS
also covers the same power generation installations, every CPS-covered
tonne is also under the UK ETS — the overlap is by policy design.

The analytical task is therefore not to *identify* whether overlap exists
(it does, definitionally) but to *quantify* exactly how many tCO2e are
jointly covered, and to identify the uncertain slice (CHP installations).

---

## Data Sources

Place the following files in `data/raw/` before running:

| File | Source | Description |
|------|--------|-------------|
| `20250611_Compliance_Report_Emissions_and_Surrenders.xlsx` | UK ETS Registry | Verified emissions + surrenders per installation, 2021–2024 |
| `uk_ets_Standard_Report_OHA_Participants_Allocations_2025_*.xlsx` | UK ETS Registry | OHA allocations + regulated activity, 2025 |
| `uk_ets_Standard_Report_OHA_Participants_Allocations_2026_*.xlsx` | UK ETS Registry | OHA allocations + regulated activity, 2026 |
| `uk_ets_Standard_Report_AOHA_Participants_Allocations_2025_*.xlsx` | UK ETS Registry | AOHA allocations, 2025 |
| `uk_ets_Standard_Report_AOHA_Participants_Allocations_2026_*.xlsx` | UK ETS Registry | AOHA allocations, 2026 |

**Data is gitignored** — never commit source files to version control.

---

## Setup

```bash
git clone <your-repo>
cd uk-cpi-overlap
pip install -r requirements.txt
# Copy raw data files to data/raw/
python main.py
```

---

## Pipeline Stages

```
Stage 1  src/ingest.py          Load and validate all raw Excel files
Stage 2  src/build_master.py    Join compliance report + OHA allocations
Stage 3  src/classify_cps.py    Classify each installation's CPS scope
Stage 4  src/compute_overlap.py Quantify annual coverage overlap
Stage 5  src/outputs.py         Write output files to outputs/
```

---

## CPS Classification Rules

Rules are applied in order; first match wins. See `src/classify_cps.py`
for full documentation and `config.py` for constants.

| Rule | Condition | Classification |
|------|-----------|----------------|
| R0 | Aircraft Operator Holding Account | CPS_AOHA |
| R1 | DAERA regulator (Northern Ireland) | CPS_NOT_APPLICABLE |
| R2 | OPRED regulator (offshore) | CPS_NOT_APPLICABLE |
| R3 | No regulated_activity AND no NACE code | CPS_UNKNOWN |
| R4 | NACE 3530 + COMBUSTION_OF_FUELS | **CPS_CHP_FLAG** |
| R5 | NACE 3511 + COMBUSTION_OF_FUELS | **CPS_COVERED** |
| R6 | COMBUSTION_OF_FUELS + other NACE | CPS_NOT_APPLICABLE |
| R7 | Non-combustion regulated activity | CPS_NOT_APPLICABLE |
| R8 | No activity data but NACE 3511 | CPS_COVERED |
| R9 | No activity data but NACE 3530 | CPS_CHP_FLAG |
| R10 | Everything else | CPS_UNKNOWN |

**CHP sensitivity analysis**: The lower bound uses CPS_COVERED only.
The upper bound adds CPS_CHP_FLAG. CHP stations (NACE 3530) are covered
only on their non-qualifying electricity fraction (CCL1/6 s.9), which
requires CHPQA certificate data not available here.

---

## Outputs

| File | Description |
|------|-------------|
| `01_master_oha.csv` | Master installation table with cps_scope flag |
| `02_overlap_annual_summary.csv` | Annual aggregate overlap estimates |
| `03_sectoral_decomposition_cps_covered.csv` | Breakdown by NACE / regulator |
| `04_installation_detail.csv` | Full installation-level detail |
| `05_chp_flag_installations.csv` | CHP_FLAG subset for sensitivity analysis |

---

## Tests

```bash
pytest tests/
```

---

## Policy Reference

- CCL1/6: https://www.gov.uk/government/publications/excise-notice-ccl16-a-guide-to-carbon-price-floor
- UK ETS Registry: https://www.gov.uk/guidance/uk-ets-registry-how-to-register

---

## Next Steps

- [ ] Add HMRC CPS revenue data to cross-validate covered fuel volumes
- [ ] Obtain CHPQA register to resolve CHP_FLAG installations
- [ ] Extend to EU ETS × national carbon tax overlap cases
