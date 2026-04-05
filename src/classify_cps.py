"""
src/classify_cps.py
-------------------
Stage 3: Classify each installation's CPS scope status.

Classification is based on HMRC Excise Notice CCL1/6 (updated Sep 2023):
https://www.gov.uk/government/publications/excise-notice-ccl16-a-guide-to-carbon-price-floor

The output column `cps_scope` takes one of these values (defined in config.py):

  CPS_COVERED        — Fossil fuel electricity generation, GB regulator, in scope
  CPS_CHP_FLAG       — Combustion + steam/CHP sector: complex partial treatment,
                       flagged separately for sensitivity analysis
  CPS_NOT_APPLICABLE — Outside CPF scope (Northern Ireland, offshore, process emissions)
  CPS_AOHA           — Aviation accounts, CPS never applies
  CPS_UNKNOWN        — Insufficient data to classify

Rule logic (applied in order, first match wins):
  R0  AOHA accounts → CPS_AOHA
  R1  DAERA regulator (Northern Ireland) → CPS_NOT_APPLICABLE  [CCL1/6 s.6.4]
  R2  OPRED regulator (offshore) → CPS_NOT_APPLICABLE          [CCL1/6 s.2.2]
  R3  regulated_activity AND nace_code both missing → CPS_UNKNOWN
  R4  NACE 3530 (steam/AC supply) + COMBUSTION_OF_FUELS → CPS_CHP_FLAG
      These are likely CHP stations — CPS applies only on the non-qualifying
      electricity fraction (s.9 of CCL1/6), which we cannot compute here.
  R5  NACE 3511 (electricity production) + COMBUSTION_OF_FUELS → CPS_COVERED
  R6  regulated_activity = COMBUSTION_OF_FUELS + NACE not 3511/3530
      → CPS_NOT_APPLICABLE (industrial combustion, not primary power generation)
  R7  regulated_activity ≠ COMBUSTION_OF_FUELS (process activities: cement, steel,
      glass, chemicals, etc.) → CPS_NOT_APPLICABLE
  R8  regulated_activity missing but NACE 3511 → CPS_COVERED
      (closed installations pre-2025 with no allocation record)
  R9  regulated_activity missing but NACE 3530 → CPS_CHP_FLAG
  R10 Everything else → CPS_UNKNOWN

Notes on what is NOT encoded here (requires additional data):
  - The <2MW small generator exemption (s.6.1): we do not have capacity data.
    In practice, all UK ETS installations are above the ETS threshold, which
    implies capacity well above 2MW for thermal generators.
  - Stand-by generator exclusion (s.6.3): not identifiable from this data.
  - CCS abatement (s.8): no CCS power stations are currently operational in UK.
  - The CHP partial treatment (s.9): flagged via CPS_CHP_FLAG for separate analysis.
"""

import pandas as pd
from config import (
    REGULATOR_EXEMPT,
    NACE_ELECTRICITY,
    NACE_STEAM_CHP,
    ACTIVITY_COMBUSTION,
    CPS_COVERED,
    CPS_CHP_FLAG,
    CPS_NOT_APPLICABLE,
    CPS_AOHA,
    CPS_UNKNOWN,
)


def classify_cps_scope(master_oha: pd.DataFrame) -> pd.DataFrame:
    """
    Add a `cps_scope` column to the master OHA table.

    Parameters
    ----------
    master_oha : output of build_master.build_master_oha()

    Returns
    -------
    Same DataFrame with two new columns:
        cps_scope       — classification label (see module docstring)
        cps_scope_rule  — which rule triggered the classification (for audit)
    """
    df = master_oha.copy()

    # Initialise
    df["cps_scope"]      = CPS_UNKNOWN
    df["cps_scope_rule"] = "R10_default"

    # Convenience boolean masks
    is_aoha     = df["account_type"] == "AIRCRAFT_OPERATOR_HOLDING_ACCOUNT"
    is_daera    = df["regulator"] == "DAERA"
    is_opred    = df["regulator"] == "OPRED"
    is_gb       = df["regulator"].isin({"EA", "NRW", "SEPA"})

    has_activity = df["regulated_activity"].notna()
    has_nace     = df["nace_code"].notna()

    is_combustion  = df["regulated_activity"] == ACTIVITY_COMBUSTION
    is_nace_3511   = df["nace_code"] == NACE_ELECTRICITY
    is_nace_3530   = df["nace_code"] == NACE_STEAM_CHP

    # ── Apply rules in priority order ────────────────────────────────────────

    # R0: Aviation
    mask_r0 = is_aoha
    df.loc[mask_r0, "cps_scope"]      = CPS_AOHA
    df.loc[mask_r0, "cps_scope_rule"] = "R0_aoha"

    # R1: Northern Ireland
    mask_r1 = ~mask_r0 & is_daera
    df.loc[mask_r1, "cps_scope"]      = CPS_NOT_APPLICABLE
    df.loc[mask_r1, "cps_scope_rule"] = "R1_northern_ireland"

    # R2: Offshore
    mask_r2 = ~mask_r0 & ~mask_r1 & is_opred
    df.loc[mask_r2, "cps_scope"]      = CPS_NOT_APPLICABLE
    df.loc[mask_r2, "cps_scope_rule"] = "R2_offshore"

    # Remaining rows: GB regulators only
    remaining = ~mask_r0 & ~mask_r1 & ~mask_r2

    # R3: Both activity and NACE missing — cannot classify
    mask_r3 = remaining & ~has_activity & ~has_nace
    df.loc[mask_r3, "cps_scope"]      = CPS_UNKNOWN
    df.loc[mask_r3, "cps_scope_rule"] = "R3_no_data"

    # R4: CHP candidates (steam sector + combustion activity)
    mask_r4 = remaining & ~mask_r3 & has_activity & is_combustion & has_nace & is_nace_3530
    df.loc[mask_r4, "cps_scope"]      = CPS_CHP_FLAG
    df.loc[mask_r4, "cps_scope_rule"] = "R4_chp_nace3530_combustion"

    # R5: Clear CPS coverage (electricity + combustion, GB)
    mask_r5 = remaining & ~mask_r3 & ~mask_r4 & has_activity & is_combustion & has_nace & is_nace_3511
    df.loc[mask_r5, "cps_scope"]      = CPS_COVERED
    df.loc[mask_r5, "cps_scope_rule"] = "R5_electricity_combustion"

    # R6: Combustion activity but not electricity/steam sector → industrial combustion
    mask_r6 = remaining & ~mask_r3 & ~mask_r4 & ~mask_r5 & has_activity & is_combustion
    df.loc[mask_r6, "cps_scope"]      = CPS_NOT_APPLICABLE
    df.loc[mask_r6, "cps_scope_rule"] = "R6_industrial_combustion"

    # R7: Non-combustion regulated activity (process emissions)
    mask_r7 = remaining & ~mask_r3 & ~mask_r4 & ~mask_r5 & ~mask_r6 & has_activity & ~is_combustion
    df.loc[mask_r7, "cps_scope"]      = CPS_NOT_APPLICABLE
    df.loc[mask_r7, "cps_scope_rule"] = "R7_process_activity"

    # R8: No allocation match (pre-2025 closed OHAs) but NACE 3511
    mask_r8 = remaining & ~mask_r3 & ~mask_r4 & ~mask_r5 & ~mask_r6 & ~mask_r7 & ~has_activity & is_nace_3511
    df.loc[mask_r8, "cps_scope"]      = CPS_COVERED
    df.loc[mask_r8, "cps_scope_rule"] = "R8_nace3511_no_activity"

    # R9: No allocation match but NACE 3530
    mask_r9 = remaining & ~mask_r3 & ~mask_r4 & ~mask_r5 & ~mask_r6 & ~mask_r7 & ~mask_r8 & ~has_activity & is_nace_3530
    df.loc[mask_r9, "cps_scope"]      = CPS_CHP_FLAG
    df.loc[mask_r9, "cps_scope_rule"] = "R9_nace3530_no_activity"

    # R10: Everything else remains CPS_UNKNOWN (set at initialisation)

    _print_classification_summary(df)
    return df


def _print_classification_summary(df: pd.DataFrame):
    """Print a concise classification breakdown."""
    print("\n── CPS classification summary ──────────────────────────────")
    breakdown = df.groupby(["cps_scope", "cps_scope_rule"]).size().reset_index(name="n_installations")
    print(breakdown.to_string(index=False))

    print("\nCPS scope totals:")
    print(df["cps_scope"].value_counts(dropna=False).to_string())


def get_cps_sensitivity_bounds(df_classified: pd.DataFrame) -> dict:
    """
    Return lower and upper bound installation sets for sensitivity analysis.

    Lower bound (conservative): CPS_COVERED only
    Upper bound (inclusive):    CPS_COVERED + CPS_CHP_FLAG

    Parameters
    ----------
    df_classified : output of classify_cps_scope()

    Returns
    -------
    dict with keys 'lower' and 'upper', each a boolean Series
    """
    lower = df_classified["cps_scope"] == CPS_COVERED
    upper = df_classified["cps_scope"].isin([CPS_COVERED, CPS_CHP_FLAG])
    return {"lower": lower, "upper": upper}


if __name__ == "__main__":
    from src.build_master import build_master_oha
    master = build_master_oha()
    classified = classify_cps_scope(master)
    bounds = get_cps_sensitivity_bounds(classified)
    print(f"\nLower bound (CPS_COVERED only)      : {bounds['lower'].sum():,} installations")
    print(f"Upper bound (+ CPS_CHP_FLAG)        : {bounds['upper'].sum():,} installations")
