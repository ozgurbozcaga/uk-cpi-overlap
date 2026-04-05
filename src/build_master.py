"""
src/build_master.py
-------------------
Stage 2: Join the compliance report with OHA allocation data to produce
the master installation table.

The compliance report carries emissions history and NACE codes.
The OHA allocations file carries the `regulated_activity` field, which is
essential for CPS classification. The join key is operator_id (called
'Operator ID' in the compliance report and 'Installation ID' in allocations).

Outputs:
  master_oha   — one row per OHA installation
  master_aoha  — one row per AOHA (aviation) account
  master_all   — combined table for total UK ETS denominators
"""

import pandas as pd
from config import EMISSION_YEARS
from src.ingest import load_compliance_report, load_all_oha_allocations


def build_master_oha(
    compliance: pd.DataFrame = None,
    oha_allocs: pd.DataFrame = None,
) -> pd.DataFrame:
    """
    Build the master OHA table by joining the compliance report
    with OHA allocation data.

    Parameters
    ----------
    compliance : pre-loaded compliance DataFrame (loads fresh if None)
    oha_allocs : pre-loaded OHA allocations DataFrame (loads fresh if None)

    Returns
    -------
    DataFrame with one row per OHA installation, columns:
        operator_id, permit_id, account_holder, installation_name,
        regulator, account_type, account_status, first_year, last_year,
        nace_code, nace_description,
        recorded_emissions_{yr} for yr in EMISSION_YEARS,
        surrender_status_{yr}  for yr in EMISSION_YEARS,
        cumulative_emissions, cumulative_surrenders,
        regulated_activity,
        alloc_entitlement_{yr}, alloc_delivered_{yr} (where available)
    """
    if compliance is None:
        compliance = load_compliance_report()
    if oha_allocs is None:
        oha_allocs = load_all_oha_allocations()

    # Restrict compliance to OHAs only
    oha_compliance = compliance[
        compliance["account_type"] == "OPERATOR_HOLDING_ACCOUNT"
    ].copy()

    print(f"[build_master] OHA rows in compliance report: {len(oha_compliance):,}")

    # Join: left join keeps all OHAs from compliance report.
    # Some installations may not appear in the allocations file (e.g. if they
    # closed before 2025) — regulated_activity will be NaN for those.
    master = oha_compliance.merge(
        oha_allocs,
        on="operator_id",
        how="left",
        suffixes=("", "_alloc"),
    )

    # Where permit_id was duplicated by the join, keep the compliance version
    if "permit_id_alloc" in master.columns:
        master = master.drop(columns=["permit_id_alloc"])

    # Diagnostics
    matched = master["regulated_activity"].notna().sum()
    unmatched = master["regulated_activity"].isna().sum()
    print(
        f"[build_master] Join result: {len(master):,} rows | "
        f"{matched:,} matched to allocations | "
        f"{unmatched:,} unmatched (regulated_activity = NaN)"
    )
    if unmatched > 0:
        unmatched_regs = master.loc[
            master["regulated_activity"].isna(), "regulator"
        ].value_counts()
        print(f"[build_master] Unmatched by regulator:\n{unmatched_regs.to_string()}")

    return master


def build_master_aoha(compliance: pd.DataFrame = None) -> pd.DataFrame:
    """
    Build the master AOHA table (aviation accounts).

    AOHA accounts are outside CPS scope but included for total
    UK ETS denominator calculations.
    """
    if compliance is None:
        compliance = load_compliance_report()

    aoha = compliance[
        compliance["account_type"] == "AIRCRAFT_OPERATOR_HOLDING_ACCOUNT"
    ].copy()

    print(f"[build_master] AOHA rows: {len(aoha):,}")
    return aoha


def build_master_all(
    master_oha: pd.DataFrame = None,
    master_aoha: pd.DataFrame = None,
) -> pd.DataFrame:
    """
    Combine OHA and AOHA into a single table for UK ETS total calculations.
    AOHA rows will have regulated_activity = NaN (not applicable).
    """
    if master_oha is None:
        master_oha = build_master_oha()
    if master_aoha is None:
        master_aoha = build_master_aoha()

    combined = pd.concat([master_oha, master_aoha], ignore_index=True, sort=False)
    print(f"[build_master] Master all-accounts table: {len(combined):,} rows")
    return combined


def summarise_join_quality(master_oha: pd.DataFrame):
    """
    Print a diagnostic summary of join quality and data completeness.
    Useful for running interactively in Claude Code or a notebook.
    """
    print("\n── Join quality report ─────────────────────────────────────")

    n_total = len(master_oha)
    n_with_activity = master_oha["regulated_activity"].notna().sum()
    n_with_nace = master_oha["nace_code"].notna().sum()

    print(f"Total OHA rows             : {n_total:,}")
    print(f"With regulated_activity    : {n_with_activity:,} ({n_with_activity/n_total:.1%})")
    print(f"With NACE code             : {n_with_nace:,} ({n_with_nace/n_total:.1%})")

    print("\nRegulated activity breakdown:")
    print(master_oha["regulated_activity"].value_counts(dropna=False).to_string())

    print("\nNACE code top 15:")
    nace_counts = (
        master_oha.groupby(["nace_code", "nace_description"])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
        .head(15)
    )
    print(nace_counts.to_string(index=False))

    print("\nRegulator breakdown:")
    print(master_oha["regulator"].value_counts(dropna=False).to_string())

    print("\nAccount status breakdown:")
    print(master_oha["account_status"].value_counts(dropna=False).to_string())

    # Emissions completeness per year
    print("\nEmissions data completeness by year:")
    for yr in EMISSION_YEARS:
        col = f"recorded_emissions_{yr}"
        if col in master_oha.columns:
            n = master_oha[col].notna().sum()
            total = master_oha[col].sum(skipna=True)
            print(f"  {yr}: {n:,} non-null rows | {total:,.0f} tCO2e total")


if __name__ == "__main__":
    master_oha  = build_master_oha()
    master_aoha = build_master_aoha()
    master_all  = build_master_all(master_oha, master_aoha)
    summarise_join_quality(master_oha)
