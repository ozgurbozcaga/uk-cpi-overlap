"""
tests/test_pipeline.py
-----------------------
Sanity checks for the UK CPS/ETS overlap pipeline.

Run with:  pytest tests/
"""

import sys
from pathlib import Path
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.classify_cps import classify_cps_scope
from config import (
    CPS_COVERED, CPS_CHP_FLAG, CPS_NOT_APPLICABLE,
    CPS_AOHA, CPS_UNKNOWN,
    EMISSION_YEARS,
)


# ── Fixtures: synthetic mini DataFrames ───────────────────────────────────────

def make_row(**kwargs) -> dict:
    """Base row template — override any field via kwargs."""
    base = {
        "operator_id":          1000000,
        "permit_id":            "UK-E-IN-00001",
        "account_holder":       "Test Company",
        "installation_name":    "Test Plant",
        "regulator":            "EA",
        "account_type":         "OPERATOR_HOLDING_ACCOUNT",
        "account_status":       "OPEN",
        "first_year":           2021,
        "last_year":            None,
        "nace_code":            3511,
        "nace_description":     "Production of electricity",
        "regulated_activity":   "COMBUSTION_OF_FUELS",
        "cumulative_emissions": 100_000,
        "cumulative_surrenders": 100_000,
    }
    for yr in EMISSION_YEARS:
        base[f"recorded_emissions_{yr}"] = 25_000
        base[f"surrender_status_{yr}"]   = "A"
    base.update(kwargs)
    return base


def df_from_rows(rows: list) -> pd.DataFrame:
    return pd.DataFrame(rows)


# ── Classification rule tests ────────────────────────────────────────────────

class TestCPSClassification:

    def test_r0_aoha_never_cps(self):
        rows = [make_row(account_type="AIRCRAFT_OPERATOR_HOLDING_ACCOUNT")]
        df = classify_cps_scope(df_from_rows(rows))
        assert df.iloc[0]["cps_scope"] == CPS_AOHA

    def test_r1_daera_not_applicable(self):
        rows = [make_row(regulator="DAERA")]
        df = classify_cps_scope(df_from_rows(rows))
        assert df.iloc[0]["cps_scope"] == CPS_NOT_APPLICABLE
        assert df.iloc[0]["cps_scope_rule"] == "R1_northern_ireland"

    def test_r2_opred_not_applicable(self):
        rows = [make_row(regulator="OPRED")]
        df = classify_cps_scope(df_from_rows(rows))
        assert df.iloc[0]["cps_scope"] == CPS_NOT_APPLICABLE
        assert df.iloc[0]["cps_scope_rule"] == "R2_offshore"

    def test_r3_no_data_unknown(self):
        rows = [make_row(regulated_activity=None, nace_code=None)]
        df = classify_cps_scope(df_from_rows(rows))
        assert df.iloc[0]["cps_scope"] == CPS_UNKNOWN

    def test_r4_chp_flag(self):
        rows = [make_row(nace_code=3530, nace_description="Steam and air conditioning supply")]
        df = classify_cps_scope(df_from_rows(rows))
        assert df.iloc[0]["cps_scope"] == CPS_CHP_FLAG
        assert df.iloc[0]["cps_scope_rule"] == "R4_chp_nace3530_combustion"

    def test_r5_electricity_combustion_covered(self):
        rows = [make_row(nace_code=3511, regulated_activity="COMBUSTION_OF_FUELS")]
        df = classify_cps_scope(df_from_rows(rows))
        assert df.iloc[0]["cps_scope"] == CPS_COVERED
        assert df.iloc[0]["cps_scope_rule"] == "R5_electricity_combustion"

    def test_r6_industrial_combustion_not_applicable(self):
        rows = [make_row(nace_code=2351, nace_description="Manufacture of cement",
                         regulated_activity="COMBUSTION_OF_FUELS")]
        df = classify_cps_scope(df_from_rows(rows))
        assert df.iloc[0]["cps_scope"] == CPS_NOT_APPLICABLE
        assert df.iloc[0]["cps_scope_rule"] == "R6_industrial_combustion"

    def test_r7_process_activity_not_applicable(self):
        rows = [make_row(nace_code=2410, regulated_activity="PRODUCTION_OF_PIG_IRON_OR_STEEL")]
        df = classify_cps_scope(df_from_rows(rows))
        assert df.iloc[0]["cps_scope"] == CPS_NOT_APPLICABLE
        assert df.iloc[0]["cps_scope_rule"] == "R7_process_activity"

    def test_r8_nace3511_no_activity(self):
        rows = [make_row(nace_code=3511, regulated_activity=None)]
        df = classify_cps_scope(df_from_rows(rows))
        assert df.iloc[0]["cps_scope"] == CPS_COVERED
        assert df.iloc[0]["cps_scope_rule"] == "R8_nace3511_no_activity"

    def test_r9_nace3530_no_activity(self):
        rows = [make_row(nace_code=3530, regulated_activity=None)]
        df = classify_cps_scope(df_from_rows(rows))
        assert df.iloc[0]["cps_scope"] == CPS_CHP_FLAG
        assert df.iloc[0]["cps_scope_rule"] == "R9_nace3530_no_activity"


# ── Overlap computation tests ─────────────────────────────────────────────────

class TestOverlapComputation:

    def test_overlap_never_exceeds_oha_total(self):
        """CPS covered emissions must always be ≤ total OHA emissions."""
        from src.compute_overlap import compute_annual_overlap
        rows = [
            make_row(operator_id=1, nace_code=3511, regulated_activity="COMBUSTION_OF_FUELS"),
            make_row(operator_id=2, nace_code=2351, regulated_activity="COMBUSTION_OF_FUELS"),
        ]
        df = classify_cps_scope(df_from_rows(rows))
        overlap = compute_annual_overlap(df)
        for _, row in overlap.iterrows():
            assert row["cps_covered_tco2e"] <= row["ukets_oha_total_tco2e"]

    def test_all_electricity_covered(self):
        """If all installations are electricity+combustion, CPS covered = OHA total."""
        from src.compute_overlap import compute_annual_overlap
        rows = [
            make_row(operator_id=i, nace_code=3511, regulated_activity="COMBUSTION_OF_FUELS")
            for i in range(5)
        ]
        df = classify_cps_scope(df_from_rows(rows))
        overlap = compute_annual_overlap(df)
        for _, row in overlap.iterrows():
            assert abs(row["cps_covered_tco2e"] - row["ukets_oha_total_tco2e"]) < 1.0

    def test_shares_between_zero_and_one(self):
        from src.compute_overlap import compute_annual_overlap
        rows = [
            make_row(operator_id=1, nace_code=3511, regulated_activity="COMBUSTION_OF_FUELS"),
            make_row(operator_id=2, nace_code=2351, regulated_activity="PRODUCTION_OF_CEMENT_CLINKER"),
        ]
        df = classify_cps_scope(df_from_rows(rows))
        overlap = compute_annual_overlap(df)
        for _, row in overlap.iterrows():
            assert 0.0 <= row["overlap_share_of_oha"] <= 1.0
