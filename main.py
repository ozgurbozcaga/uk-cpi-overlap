"""
main.py
-------
Pipeline entry point. Run this to execute all five stages end-to-end.

Usage:
    python main.py

Or from Claude Code / terminal:
    cd uk-cpi-overlap
    python main.py
"""

import sys
from pathlib import Path

# Allow imports from src/ without installing as a package
sys.path.insert(0, str(Path(__file__).parent))

from src.ingest import load_compliance_report, load_all_oha_allocations, load_aoha_allocations
from src.build_master import build_master_oha, build_master_aoha
from src.classify_cps import classify_cps_scope
from src.compute_overlap import (
    compute_annual_overlap,
    compute_sectoral_decomposition,
    compute_installation_detail,
    print_overlap_summary,
)
from src.outputs import write_all_outputs
from config import CPS_COVERED


def run_pipeline():
    print("=" * 65)
    print("UK CPS / UK ETS Coverage Overlap Pipeline")
    print("=" * 65)

    # ── Stage 1: Ingest ────────────────────────────────────────────
    print("\n[Stage 1] Loading raw data...")
    compliance  = load_compliance_report()
    oha_allocs  = load_all_oha_allocations()

    # ── Stage 2: Build master tables ──────────────────────────────
    print("\n[Stage 2] Building master tables...")
    master_oha  = build_master_oha(compliance, oha_allocs)
    master_aoha = build_master_aoha(compliance)

    # ── Stage 3: Classify CPS scope ───────────────────────────────
    print("\n[Stage 3] Classifying CPS scope...")
    classified = classify_cps_scope(master_oha)

    # ── Stage 4: Compute overlap ──────────────────────────────────
    print("\n[Stage 4] Computing coverage overlap...")
    overlap_annual = compute_annual_overlap(classified, master_aoha)
    decomp_covered = compute_sectoral_decomposition(classified, scope_filter=CPS_COVERED)
    detail         = compute_installation_detail(classified)

    print_overlap_summary(overlap_annual)

    # ── Stage 5: Write outputs ─────────────────────────────────────
    print("\n[Stage 5] Writing outputs...")
    write_all_outputs(
        master_oha   = classified,
        overlap_annual = overlap_annual,
        decomp_covered = decomp_covered,
        detail         = detail,
    )

    print("\n✓ Pipeline complete.")


if __name__ == "__main__":
    run_pipeline()
