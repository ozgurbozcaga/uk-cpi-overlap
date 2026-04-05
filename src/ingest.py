"""
src/ingest.py
-------------
Stage 1: Load and lightly validate all raw Excel files into clean DataFrames.

All column renaming and type coercion happens here so downstream modules
work with consistent, predictable field names regardless of how the source
files are structured or labelled.

No business logic lives in this module — that is for build_master.py and
classify_cps.py.
"""

import pandas as pd
from pathlib import Path
from config import FILES, EMISSION_YEARS


# ── Helpers ──────────────────────────────────────────────────────────────────

def _read_excel(path: Path, sheet: str = "Data", **kwargs) -> pd.DataFrame:
    """Read an Excel sheet with basic existence check."""
    if not path.exists():
        raise FileNotFoundError(
            f"Expected raw data file not found: {path}\n"
            f"Place the file in data/raw/ and re-run."
        )
    return pd.read_excel(path, sheet_name=sheet, **kwargs)


def _assert_columns(df: pd.DataFrame, required: list, source: str):
    """Raise clearly if expected columns are missing."""
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"[{source}] Missing expected columns: {missing}\n"
            f"Found: {list(df.columns)}"
        )


# ── Compliance Report ─────────────────────────────────────────────────────────

def load_compliance_report() -> pd.DataFrame:
    """
    Load the Compliance Report (Emissions and Surrenders).

    Returns one row per account (OHA or AOHA) with:
      - identifiers: operator_id, permit_id, installation_name, account_holder
      - metadata: regulator, account_type, account_status, first_year, last_year
      - emissions: recorded_emissions_{year} for each year in EMISSION_YEARS
      - compliance: surrender_status_{year} for each year
      - sector: nace_code, nace_description
    """
    path = FILES["compliance"]
    df = _read_excel(path, sheet="Data")

    # Rename raw columns to snake_case internal names
    rename = {
        "Regulator":                            "regulator",
        "Account Holder Name":                  "account_holder",
        "Account type":                         "account_type",
        "Account status":                       "account_status",
        "Operator ID":                          "operator_id",
        "Permit ID or Monitoring plan ID":      "permit_id",
        "Installation name":                    "installation_name",
        "First Year of Operation":              "first_year",
        "Last Year of Operation":               "last_year",
        "Cumulative emissions":                 "cumulative_emissions",
        "Cumulative surrenders":                "cumulative_surrenders",
        "NACE Code":                            "nace_code",
        "NACE Description":                     "nace_description",
    }
    # Add dynamic year columns
    for yr in EMISSION_YEARS:
        rename[f"Recorded emissions {yr}"]     = f"recorded_emissions_{yr}"
        rename[f"Static surrender status {yr}"] = f"surrender_status_{yr}"

    _assert_columns(df, list(rename.keys()), "compliance_report")
    df = df.rename(columns=rename)

    # Type coercion
    df["operator_id"] = pd.to_numeric(df["operator_id"], errors="coerce").astype("Int64")
    df["nace_code"]   = pd.to_numeric(df["nace_code"],   errors="coerce").astype("Int64")
    df["first_year"]  = pd.to_numeric(df["first_year"],  errors="coerce").astype("Int64")
    df["last_year"]   = pd.to_numeric(df["last_year"],   errors="coerce").astype("Int64")

    for yr in EMISSION_YEARS:
        df[f"recorded_emissions_{yr}"] = pd.to_numeric(
            df[f"recorded_emissions_{yr}"], errors="coerce"
        )

    # Standardise categorical fields
    df["account_type"]   = df["account_type"].str.strip().str.upper()
    df["account_status"] = df["account_status"].str.strip().str.upper()
    df["regulator"]      = df["regulator"].str.strip().str.upper()

    print(
        f"[ingest] Compliance report loaded: {len(df):,} rows "
        f"({(df.account_type == 'OPERATOR_HOLDING_ACCOUNT').sum():,} OHA, "
        f"{(df.account_type == 'AIRCRAFT_OPERATOR_HOLDING_ACCOUNT').sum():,} AOHA)"
    )
    return df


# ── OHA Allocations ───────────────────────────────────────────────────────────

def load_oha_allocations(year: int) -> pd.DataFrame:
    """
    Load OHA (Operator Holding Account) allocations for a given year.

    Returns one row per installation with:
      - operator_id (join key to compliance report)
      - installation_id, installation_name, permit_id
      - regulated_activity  ← critical for CPS classification
      - regulator
      - alloc_entitlement_{year}, alloc_delivered_{year}
    """
    key = f"oha_alloc_{year}"
    if key not in FILES:
        raise KeyError(f"No file configured for OHA allocations year {year}. Add to config.FILES.")

    path = FILES[key]
    df = _read_excel(path, sheet="Data")

    expected = [
        "Account Holder Name", "Installation ID", "Installation Name",
        "Permit ID", "Regulated activity", "First Year of Operation", "Regulator",
        f"Allocation Entitlement_{year}", f"Allocation Delivered_{year}",
    ]
    _assert_columns(df, expected, f"oha_alloc_{year}")

    rename = {
        "Account Holder Name":              "account_holder",
        "Installation ID":                  "operator_id",
        "Installation Name":                "installation_name",
        "Permit ID":                        "permit_id",
        "Regulated activity":               "regulated_activity",
        "First Year of Operation":          "first_year",
        "Regulator":                        "regulator",
        f"Allocation Entitlement_{year}":   f"alloc_entitlement_{year}",
        f"Allocation Delivered_{year}":     f"alloc_delivered_{year}",
    }
    df = df.rename(columns=rename)

    df["operator_id"] = pd.to_numeric(df["operator_id"], errors="coerce").astype("Int64")
    df["regulated_activity"] = df["regulated_activity"].str.strip().str.upper()
    df["regulator"] = df["regulator"].str.strip().str.upper()

    # Keep only the columns we need from this file
    keep = [
        "operator_id", "permit_id", "regulated_activity",
        f"alloc_entitlement_{year}", f"alloc_delivered_{year}",
    ]
    df = df[keep].drop_duplicates(subset=["operator_id"])

    print(f"[ingest] OHA allocations {year} loaded: {len(df):,} installations")
    return df


def load_all_oha_allocations(years: list = None) -> pd.DataFrame:
    """
    Load and merge OHA allocations across all configured years.
    Produces one row per installation with allocation columns for each year.
    """
    if years is None:
        # Infer from FILES keys
        years = sorted(
            int(k.split("_")[-1]) for k in FILES if k.startswith("oha_alloc_")
        )

    dfs = []
    for yr in years:
        try:
            dfs.append(load_oha_allocations(yr))
        except (KeyError, FileNotFoundError) as e:
            print(f"[ingest] Warning — skipping OHA {yr}: {e}")

    if not dfs:
        raise RuntimeError("No OHA allocation files could be loaded.")

    # Merge on operator_id; regulated_activity should be stable across years
    merged = dfs[0]
    for df in dfs[1:]:
        # Drop regulated_activity from subsequent years (take from first)
        yr_cols = [c for c in df.columns if c.startswith("alloc_")]
        merged = merged.merge(
            df[["operator_id"] + yr_cols],
            on="operator_id",
            how="outer",
        )

    print(f"[ingest] OHA allocations merged: {len(merged):,} unique installations across {years}")
    return merged


# ── AOHA Allocations ──────────────────────────────────────────────────────────

def load_aoha_allocations(year: int) -> pd.DataFrame:
    """
    Load AOHA (Aircraft Operator Holding Account) allocations for a given year.

    Aviation is outside CPS scope entirely, but we load this for completeness
    and to compute total UK ETS coverage denominators.

    Note: the 2026 export appears to contain only the account holder name
    column — this is a known data quality issue in the source file.
    """
    key = f"aoha_alloc_{year}"
    if key not in FILES:
        raise KeyError(f"No file configured for AOHA allocations year {year}.")

    path = FILES[key]
    df = _read_excel(path, sheet="Data")

    # Check if this is the degraded 2026 export (single column)
    if len(df.columns) == 1:
        print(
            f"[ingest] Warning — AOHA {year} file appears incomplete "
            f"(only 1 column found). Returning stub with account_holder only."
        )
        df = df.rename(columns={df.columns[0]: "account_holder"})
        df["alloc_data_available"] = False
        return df

    # Full file
    rename = {
        "Account Holder Name":              "account_holder",
        "Aircraft Operator ID":             "operator_id",
        "Monitoring plan ID":               "permit_id",
        "First Year of Operation":          "first_year",
        "Regulator":                        "regulator",
        f"Allocation Entitlement_{year}":   f"alloc_entitlement_{year}",
        f"Allocation Delivered_{year}":     f"alloc_delivered_{year}",
    }
    available = {k: v for k, v in rename.items() if k in df.columns}
    df = df.rename(columns=available)

    if "operator_id" in df.columns:
        df["operator_id"] = pd.to_numeric(df["operator_id"], errors="coerce").astype("Int64")

    df["alloc_data_available"] = True
    print(f"[ingest] AOHA allocations {year} loaded: {len(df):,} aircraft operators")
    return df


# ── Entry point for quick validation ─────────────────────────────────────────

if __name__ == "__main__":
    compliance  = load_compliance_report()
    oha_allocs  = load_all_oha_allocations()
    aoha_2025   = load_aoha_allocations(2025)
    aoha_2026   = load_aoha_allocations(2026)

    print("\n── Summary ──────────────────────────────────────────")
    print(f"Compliance report rows : {len(compliance):,}")
    print(f"OHA allocation rows    : {len(oha_allocs):,}")
    print(f"AOHA 2025 rows         : {len(aoha_2025):,}")
    print(f"AOHA 2026 rows         : {len(aoha_2026):,}")
