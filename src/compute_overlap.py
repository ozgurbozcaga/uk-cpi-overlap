"""
src/compute_overlap.py
----------------------
Stage 4: Quantify the coverage overlap between the UK Carbon Price Support
(CPS) and the UK Emissions Trading Scheme (UK ETS).

Key insight from the policy design (CCL1/6):
  The CPS is a complement to the UK ETS, applied on top of ETS costs for
  fossil fuel electricity generators. Every installation classified as
  CPS_COVERED is, by definition, also within the UK ETS. The overlap is
  therefore 100% of CPS-covered emissions — but not 100% of UK ETS emissions
  (the ETS also covers industrial process emissions and aviation, which are
  outside CPS scope).

This module produces:
  1. Annual aggregate overlap table (primary output)
  2. Sensitivity bounds (lower: CPS_COVERED only; upper: + CPS_CHP_FLAG)
  3. Sectoral decomposition (by NACE code and regulator)
  4. Installation-level detail table
"""

import pandas as pd
from config import EMISSION_YEARS, CPS_COVERED, CPS_CHP_FLAG, CPS_NOT_APPLICABLE, CPS_AOHA


def compute_annual_overlap(
    df_classified: pd.DataFrame,
    df_aoha: pd.DataFrame = None,
) -> pd.DataFrame:
    """
    Compute the annual CPS/UK ETS coverage overlap for each emission year.

    Parameters
    ----------
    df_classified : output of classify_cps.classify_cps_scope()
    df_aoha       : master AOHA table (for UK ETS total denominator)

    Returns
    -------
    DataFrame with one row per year containing:
        year
        ukets_oha_total_tco2e       — all OHA verified emissions
        ukets_aoha_total_tco2e      — all AOHA verified emissions (if data provided)
        ukets_total_tco2e           — OHA + AOHA
        cps_covered_tco2e           — lower bound: CPS_COVERED only
        cps_upper_bound_tco2e       — upper bound: CPS_COVERED + CPS_CHP_FLAG
        chp_flag_tco2e              — CPS_CHP_FLAG emissions (the uncertain slice)
        not_applicable_tco2e        — OHA emissions outside CPS scope
        unknown_tco2e               — unclassified OHA emissions
        overlap_share_of_oha        — cps_covered / ukets_oha_total
        overlap_share_of_total_ukets — cps_covered / ukets_total
        upper_bound_share_of_oha    — upper / ukets_oha_total
    """
    records = []

    for yr in EMISSION_YEARS:
        col = f"recorded_emissions_{yr}"
        if col not in df_classified.columns:
            continue

        # ── OHA totals ──────────────────────────────────────────────────────
        oha_total = df_classified[col].sum(skipna=True)

        # By CPS scope
        scope_totals = (
            df_classified.groupby("cps_scope")[col]
            .sum()
        )

        cps_covered  = scope_totals.get(CPS_COVERED, 0.0)
        chp_flag     = scope_totals.get(CPS_CHP_FLAG, 0.0)
        not_applic   = scope_totals.get(CPS_NOT_APPLICABLE, 0.0)
        cps_unknown  = scope_totals.get("CPS_UNKNOWN", 0.0)
        upper_bound  = cps_covered + chp_flag

        # ── AOHA totals ─────────────────────────────────────────────────────
        aoha_total = 0.0
        if df_aoha is not None and col in df_aoha.columns:
            aoha_total = df_aoha[col].sum(skipna=True)

        ukets_total = oha_total + aoha_total

        records.append({
            "year":                          yr,
            "ukets_oha_total_tco2e":         oha_total,
            "ukets_aoha_total_tco2e":        aoha_total,
            "ukets_total_tco2e":             ukets_total,
            "cps_covered_tco2e":             cps_covered,
            "chp_flag_tco2e":                chp_flag,
            "cps_upper_bound_tco2e":         upper_bound,
            "not_applicable_tco2e":          not_applic,
            "unknown_tco2e":                 cps_unknown,
            # Shares — two denominators (OHA only; full UK ETS including AOHA)
            "overlap_share_of_oha":               cps_covered / oha_total   if oha_total   > 0 else None,
            "overlap_share_of_total_ukets":       cps_covered / ukets_total if ukets_total > 0 else None,
            "upper_bound_share_of_oha":           upper_bound / oha_total   if oha_total   > 0 else None,
            "upper_bound_share_of_total_ukets":   upper_bound / ukets_total if ukets_total > 0 else None,
        })

    result = pd.DataFrame(records)
    return result


def compute_sectoral_decomposition(
    df_classified: pd.DataFrame,
    scope_filter: str = None,
) -> pd.DataFrame:
    """
    Decompose emissions by NACE code and regulator for a given scope.

    Parameters
    ----------
    df_classified : output of classify_cps_scope()
    scope_filter  : if provided, filter to one cps_scope value before aggregating
                    (e.g. CPS_COVERED, CPS_CHP_FLAG). If None, use all rows.

    Returns
    -------
    DataFrame with columns:
        nace_code, nace_description, regulator, cps_scope,
        n_installations,
        emissions_{yr} for each year in EMISSION_YEARS
    """
    df = df_classified.copy()
    if scope_filter:
        df = df[df["cps_scope"] == scope_filter]

    emission_cols = [f"recorded_emissions_{yr}" for yr in EMISSION_YEARS
                     if f"recorded_emissions_{yr}" in df.columns]

    group_cols = ["nace_code", "nace_description", "regulator", "cps_scope"]
    agg = {col: "sum" for col in emission_cols}
    agg["operator_id"] = "count"

    decomp = (
        df.groupby(group_cols, dropna=False)
        .agg(agg)
        .rename(columns={"operator_id": "n_installations"})
        .reset_index()
        .sort_values(
            f"recorded_emissions_{EMISSION_YEARS[-1]}",
            ascending=False,
            na_position="last",
        )
    )
    return decomp


def compute_installation_detail(df_classified: pd.DataFrame) -> pd.DataFrame:
    """
    Return an installation-level detail table with all key fields.

    This is the most granular output — useful for spot-checking individual
    facilities and for the formal methodology appendix.
    """
    emission_cols   = [f"recorded_emissions_{yr}" for yr in EMISSION_YEARS
                       if f"recorded_emissions_{yr}" in df_classified.columns]
    surrender_cols  = [f"surrender_status_{yr}" for yr in EMISSION_YEARS
                       if f"surrender_status_{yr}" in df_classified.columns]
    alloc_cols      = [c for c in df_classified.columns if c.startswith("alloc_")]

    keep = (
        ["operator_id", "permit_id", "account_holder", "installation_name",
         "regulator", "account_status", "first_year", "last_year",
         "nace_code", "nace_description", "regulated_activity",
         "cps_scope", "cps_scope_rule"]
        + emission_cols
        + surrender_cols
        + alloc_cols
    )
    keep = [c for c in keep if c in df_classified.columns]
    return df_classified[keep].copy()


def print_overlap_summary(overlap_df: pd.DataFrame):
    """
    Pretty-print the annual overlap results.

    Two denominator perspectives are shown:
      - Share of OHA total: what fraction of stationary installation emissions
        are jointly covered by both instruments
      - Share of UK ETS total (OHA + AOHA): what fraction of all UK ETS
        covered emissions are also covered by CPS — the right denominator
        for State & Trends 'share of ETS covered emissions' reporting
    """
    print("\n── UK ETS / CPS Coverage Overlap — Annual Summary ──────────────────────")

    # ── Block 1: Absolute emissions ──────────────────────────────────────────
    print(f"\n  Emissions (tCO2e)")
    print(f"  {'Year':<6} {'OHA':>15} {'AOHA':>12} {'OHA+AOHA':>15} "
          f"{'CPS Covered':>14} {'CHP Flag':>12} {'Upper Bound':>14}")
    print("  " + "─" * 92)
    for _, row in overlap_df.iterrows():
        print(
            f"  {int(row.year):<6} "
            f"{row.ukets_oha_total_tco2e:>15,.0f} "
            f"{row.ukets_aoha_total_tco2e:>12,.0f} "
            f"{row.ukets_total_tco2e:>15,.0f} "
            f"{row.cps_covered_tco2e:>14,.0f} "
            f"{row.chp_flag_tco2e:>12,.0f} "
            f"{row.cps_upper_bound_tco2e:>14,.0f}"
        )

    # ── Block 2: Overlap shares — two denominators ───────────────────────────
    print(f"\n  Overlap shares")
    print(f"  {'Year':<6} {'Covered/OHA':>14} {'Upper/OHA':>12} "
          f"{'Covered/Total':>15} {'Upper/Total':>13}")
    print("  " + "─" * 65)
    for _, row in overlap_df.iterrows():
        print(
            f"  {int(row.year):<6} "
            f"{row.overlap_share_of_oha:>13.1%} "
            f"{row.upper_bound_share_of_oha:>12.1%} "
            f"{row.overlap_share_of_total_ukets:>14.1%} "
            f"{row.upper_bound_share_of_total_ukets:>13.1%}"
        )

    print(
        "\n  Notes:"
        "\n    CPS Covered  = Lower bound — CPS_COVERED installations only (excludes CHP)"
        "\n    CHP Flag     = CPS_CHP_FLAG installations (partial CPS treatment, uncertain)"
        "\n    Upper Bound  = CPS Covered + CHP Flag"
        "\n    /OHA         = denominator is UK ETS stationary installations only"
        "\n    /Total       = denominator is full UK ETS (OHA + AOHA)"
        "\n    CPS never applies to aviation (AOHA), so /Total will always be lower than /OHA"
    )


if __name__ == "__main__":
    from src.build_master import build_master_oha, build_master_aoha
    from src.classify_cps import classify_cps_scope

    master_oha  = build_master_oha()
    master_aoha = build_master_aoha()
    classified  = classify_cps_scope(master_oha)

    overlap  = compute_annual_overlap(classified, master_aoha)
    decomp   = compute_sectoral_decomposition(classified, scope_filter=CPS_COVERED)

    print_overlap_summary(overlap)

    print("\n── Sectoral decomposition (CPS_COVERED) ────────────────────")
    print(decomp.to_string(index=False))
