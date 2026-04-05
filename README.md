# UK CPS / UK ETS Coverage Overlap Analysis

Tier 1 facility-level overlap analysis between the UK Carbon Price Support (CPS) and the UK Emissions Trading Scheme (UK ETS), produced for the World Bank *State and Trends of Carbon Pricing* report. The pipeline ingests UK ETS registry data, classifies each installation's CPS scope using HMRC CCL1/6 rules, and quantifies the annual coverage overlap in tCO2e for 2021--2024.

---

## Instruments

**UK Emissions Trading Scheme (UK ETS)**
Cap-and-trade system that replaced UK participation in the EU ETS from 1 January 2021. Covers power generation, energy-intensive industry, and domestic aviation. Administered by the Environment Agency (England), SEPA (Scotland), NRW (Wales), DAERA (Northern Ireland), and OPRED (offshore).

**Carbon Price Support (CPS)**
An HMRC-administered top-up tax on fossil fuels used for electricity generation in Great Britain, introduced in 2013 under the Climate Change Levy (Excise Notice CCL1/6). Functions as a price floor for carbon in the power sector: generators pay the CPS rate on top of their UK ETS compliance cost, bringing the effective carbon price to the CPS target level. Applies only to GB (excludes Northern Ireland and offshore). Does not cover aviation, industrial process emissions, or non-combustion activities.

---

## Methodology

### Approach

This is a **Tier 1 direct facility matching** analysis. Both instruments operate at the installation level via the UK ETS registry, so overlap can be identified by classifying each Operator Holding Account (OHA) as inside or outside CPS scope.

### Data join

The compliance report (verified emissions 2021--2024) is joined to OHA allocation files (2025--2026) on `operator_id`. The allocation files provide the `regulated_activity` field required for classification. Join achieves **100% match rate** (757/757 OHA installations matched).

### Classification logic

Each OHA installation is assigned a `cps_scope` label using a priority-ordered rule set based on CCL1/6:

| Rule | Condition | Classification |
|------|-----------|----------------|
| R0 | Aircraft Operator Holding Account | CPS_AOHA |
| R1 | DAERA regulator (Northern Ireland) | CPS_NOT_APPLICABLE |
| R2 | OPRED regulator (offshore) | CPS_NOT_APPLICABLE |
| R3 | No regulated_activity AND no NACE code | CPS_UNKNOWN |
| R4 | NACE 3530 (steam/CHP) + COMBUSTION_OF_FUELS | **CPS_CHP_FLAG** |
| R5 | NACE 3511 (electricity) + COMBUSTION_OF_FUELS | **CPS_COVERED** |
| R6 | COMBUSTION_OF_FUELS + other NACE | CPS_NOT_APPLICABLE |
| R7 | Non-combustion regulated activity | CPS_NOT_APPLICABLE |
| R8 | No activity data but NACE 3511 | CPS_COVERED |
| R9 | No activity data but NACE 3530 | CPS_CHP_FLAG |
| R10 | Everything else | CPS_UNKNOWN |

### Overlap definition

CPS coverage is a **strict subset** of UK ETS coverage -- every CPS-liable installation is also an ETS-regulated OHA. The overlap therefore equals the total verified emissions of CPS-classified installations. The overlap share is expressed against two denominators: OHA-only (stationary installations) and full UK ETS (OHA + AOHA including aviation).

### CHP sensitivity treatment

CHP stations (NACE 3530, rule R4/R9) are flagged separately as `CPS_CHP_FLAG`. Under CCL1/6 s.9, CPS applies only to the non-qualifying electricity fraction of CHP output, which requires CHPQA certificate data not available here. The **lower bound** uses CPS_COVERED only; the **upper bound** adds CPS_CHP_FLAG.

---

## Results

### Annual overlap summary (2021--2024)

| Year | UK ETS OHA (MtCO2e) | CPS Covered (MtCO2e) | CHP Flag (MtCO2e) | Overlap Share of OHA |
|------|---------------------:|----------------------:|--------------------:|---------------------:|
| 2021 | 104.4 | 47.7 | 0.3 | 45.7% |
| 2022 | 102.9 | 48.6 | 0.3 | 47.2% |
| 2023 | 87.9 | 37.3 | 0.4 | 42.5% |
| 2024 | 76.6 | 30.5 | 0.3 | 39.9% |

The declining overlap share (47.2% in 2022 to 39.9% in 2024) is consistent with UK power sector decarbonisation: coal phase-out and increased renewable penetration reduce fossil-fuel electricity generation faster than other ETS-covered sectors contract.

CPS-covered installations are concentrated under the England regulator (EA): 159 of 203 installations, accounting for 80.3% of CPS-covered emissions in 2024. NRW (Wales) contributes 14.3% and SEPA (Scotland) 5.3%.

The 16 CHP-flagged installations add only 0.3 MtCO2e (< 1% of OHA total), so the sensitivity range is narrow.

### Figures

Publication-quality figures are in [`outputs/figures/`](outputs/figures/):

- **`uk_cps_ets_overlap_annual`** -- Stacked bar chart of UK ETS OHA emissions decomposed by CPS scope, with overlap percentage annotated (2021--2024)
- **`uk_cps_sectoral_decomposition`** -- CPS-covered emissions by regulator (EA/NRW/SEPA)
- **`uk_installation_classification`** -- Dual-panel: installation count and emissions volume by CPS classification

---

## Data Sources

| Source | Description | Files |
|--------|-------------|-------|
| UK ETS Registry (DESNZ) | Compliance report: verified emissions and surrenders, 2021--2024 | `20250611_Compliance_Report_Emissions_and_Surrenders.xlsx` |
| UK ETS Registry (DESNZ) | OHA allocation files, 2025--2026 | `uk_ets_Standard_Report_OHA_Participants_Allocations_*.xlsx` |
| UK ETS Registry (DESNZ) | AOHA allocation files, 2025--2026 | `uk_ets_Standard_Report_AOHA_Participants_Allocations_*.xlsx` |
| HMRC | CPS rates and policy framework | Excise Notice CCL1/6 |

Raw data files are gitignored and must be placed in `data/raw/` before running.

---

## Repo Structure

```
uk-cpi-overlap/
├── main.py                  # Pipeline entry point (stages 1-5)
├── config.py                # Paths, constants, classification labels
├── requirements.txt         # Python dependencies
├── src/
│   ├── ingest.py            # Stage 1: Load and validate raw Excel files
│   ├── build_master.py      # Stage 2: Join compliance + OHA allocations
│   ├── classify_cps.py      # Stage 3: Classify CPS scope per installation
│   ├── compute_overlap.py   # Stage 4: Compute annual overlap aggregates
│   └── outputs.py           # Stage 5: Write CSVs to outputs/
├── scripts/
│   └── 03_outputs.py        # Generate publication figures from CSVs
├── tests/
│   └── test_pipeline.py
├── data/
│   └── raw/                 # Raw Excel files (gitignored)
└── outputs/
    ├── 01_master_oha.csv
    ├── 02_overlap_annual_summary.csv
    ├── 03_sectoral_decomposition_cps_covered.csv
    ├── 04_installation_detail.csv
    ├── 05_chp_flag_installations.csv
    └── figures/
        ├── uk_cps_ets_overlap_annual.png / .svg
        ├── uk_cps_sectoral_decomposition.png / .svg
        └── uk_installation_classification.png / .svg
```

---

## How to Run

```bash
# Install dependencies
pip install -r requirements.txt --break-system-packages

# Place raw Excel files in data/raw/ (see Data Sources above)

# Run the pipeline (stages 1-5: ingest, join, classify, compute, write CSVs)
python3 main.py

# Generate publication figures from the CSVs
python3 scripts/03_outputs.py
```

Dependencies: `pandas>=2.0.0`, `openpyxl>=3.1.0`, `xlrd>=2.0.1`, `matplotlib` (for figures only).

---

## Policy Reference

- [Excise Notice CCL1/6: Carbon Price Floor](https://www.gov.uk/government/publications/excise-notice-ccl16-a-guide-to-carbon-price-floor)
- [UK ETS Registry guidance](https://www.gov.uk/guidance/uk-ets-registry-how-to-register)

---

## Next Steps

- [ ] Add HMRC CPS revenue data to cross-validate covered fuel volumes
- [ ] Obtain CHPQA register to resolve CHP_FLAG installations
- [ ] Extend to EU ETS x national carbon tax overlap cases
