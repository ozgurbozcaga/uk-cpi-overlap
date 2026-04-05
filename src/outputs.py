"""
src/outputs.py
--------------
Stage 5: Write all pipeline outputs to the outputs/ directory.

Output files:
  01_master_oha.csv               — master OHA installation table (with cps_scope)
  02_overlap_annual_summary.csv   — annual aggregate overlap estimates
  03_sectoral_decomposition.csv   — breakdown by NACE / regulator
  04_installation_detail.csv      — full installation-level detail
  05_chp_flag_installations.csv   — CHP_FLAG subset for sensitivity analysis
"""

import pandas as pd
from pathlib import Path
from config import OUTPUTS, CPS_CHP_FLAG


def ensure_outputs_dir():
    OUTPUTS.mkdir(parents=True, exist_ok=True)


def write_all_outputs(
    master_oha: pd.DataFrame,
    overlap_annual: pd.DataFrame,
    decomp_covered: pd.DataFrame,
    detail: pd.DataFrame,
):
    """
    Write all standard pipeline outputs to the outputs/ directory.

    Parameters mirror the outputs of compute_overlap.py functions.
    """
    ensure_outputs_dir()

    # 01 Master OHA
    path_01 = OUTPUTS / "01_master_oha.csv"
    master_oha.to_csv(path_01, index=False)
    print(f"[outputs] Written: {path_01}  ({len(master_oha):,} rows)")

    # 02 Annual overlap summary
    path_02 = OUTPUTS / "02_overlap_annual_summary.csv"
    overlap_annual.to_csv(path_02, index=False)
    print(f"[outputs] Written: {path_02}  ({len(overlap_annual)} rows)")

    # 03 Sectoral decomposition (CPS_COVERED)
    path_03 = OUTPUTS / "03_sectoral_decomposition_cps_covered.csv"
    decomp_covered.to_csv(path_03, index=False)
    print(f"[outputs] Written: {path_03}  ({len(decomp_covered)} rows)")

    # 04 Installation detail
    path_04 = OUTPUTS / "04_installation_detail.csv"
    detail.to_csv(path_04, index=False)
    print(f"[outputs] Written: {path_04}  ({len(detail):,} rows)")

    # 05 CHP flag subset
    chp_subset = master_oha[master_oha["cps_scope"] == CPS_CHP_FLAG].copy()
    path_05 = OUTPUTS / "05_chp_flag_installations.csv"
    chp_subset.to_csv(path_05, index=False)
    print(f"[outputs] Written: {path_05}  ({len(chp_subset):,} rows)")

    print(f"\n[outputs] All files written to: {OUTPUTS}/")
