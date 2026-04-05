"""
config.py
---------
Central configuration for the UK CPS / UK ETS coverage overlap pipeline.
All file paths and classification constants live here so nothing is
hard-coded in the pipeline modules.
"""

from pathlib import Path

# ── Directory layout ────────────────────────────────────────────────────────
ROOT        = Path(__file__).parent
DATA_RAW    = ROOT / "data" / "raw"
OUTPUTS     = ROOT / "outputs"

# ── Raw input files (place Excel files in data/raw/) ────────────────────────
FILES = {
    # Compliance report: emissions + surrenders, 2021-2024, all OHAs + AOHAs
    "compliance": DATA_RAW / "20250611_Compliance_Report_Emissions_and_Surrenders.xlsx",

    # OHA allocations — add more years here as new files are downloaded
    "oha_alloc_2025": DATA_RAW / "uk_ets_Standard_Report_OHA_Participants_Allocations_2025_20260310010000000.xlsx",
    "oha_alloc_2026": DATA_RAW / "uk_ets_Standard_Report_OHA_Participants_Allocations_2026_20260310010000000.xlsx",

    # AOHA allocations
    "aoha_alloc_2025": DATA_RAW / "uk_ets_Standard_Report_AOHA_Participants_Allocations_2025_20260310010000000.xlsx",
    "aoha_alloc_2026": DATA_RAW / "uk_ets_Standard_Report_AOHA_Participants_Allocations_2026_20260310010000000.xlsx",
}

# ── Emission years present in the compliance report ─────────────────────────
EMISSION_YEARS = [2021, 2022, 2023, 2024]

# ── Regulator geography mapping ─────────────────────────────────────────────
# Used by classify_cps.py to determine CPF applicability.
# CPF covers Great Britain only (EA = England, NRW = Wales, SEPA = Scotland).
# DAERA = Northern Ireland  → CPF does NOT apply (s.6.4 of CCL1/6).
# OPRED = offshore petroleum → CPF does NOT apply (s.2.2 of CCL1/6).

REGULATOR_GB     = {"EA", "NRW", "SEPA"}   # Carbon Price Floor applies
REGULATOR_EXEMPT = {
    "DAERA": "northern_ireland",   # Explicitly excluded by CCL1/6 s.6.4
    "OPRED": "offshore",           # Outside 12-mile territorial limit
}

# ── NACE codes relevant to CPS classification ────────────────────────────────
# Source: https://ec.europa.eu/competition/mergers/cases/index/nace_all.html
NACE_ELECTRICITY   = 3511   # Production of electricity — primary CPS target
NACE_STEAM_CHP     = 3530   # Steam and air conditioning supply — CHP candidates

# ── UK ETS regulated activity codes ─────────────────────────────────────────
# These come from the OHA Allocations "Regulated activity" field.
ACTIVITY_COMBUSTION = "COMBUSTION_OF_FUELS"

# ── CPS classification labels ────────────────────────────────────────────────
# These are the values written into the `cps_scope` column on the master table.
CPS_COVERED          = "CPS_COVERED"          # Fossil fuel electricity gen, GB, ≥2MW
CPS_CHP_FLAG         = "CPS_CHP_FLAG"         # CHP — complex treatment, flagged for sensitivity
CPS_NOT_APPLICABLE   = "CPS_NOT_APPLICABLE"   # Outside CPF scope (DAERA / OPRED / process)
CPS_AOHA             = "CPS_AOHA"             # Aviation — CPS never applies
CPS_UNKNOWN          = "CPS_UNKNOWN"          # Missing data — cannot classify
