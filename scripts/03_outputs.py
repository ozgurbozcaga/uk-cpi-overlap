"""
scripts/03_outputs.py
---------------------
Generate publication-quality figures from pipeline CSVs in outputs/.

Reads:
    outputs/02_overlap_annual_summary.csv
    outputs/03_sectoral_decomposition_cps_covered.csv
    outputs/01_master_oha.csv

Writes to outputs/figures/:
    uk_cps_ets_overlap_annual.png / .svg
    uk_cps_sectoral_decomposition.png / .svg
    uk_installation_classification.png / .svg

Run from repo root:
    python scripts/03_outputs.py
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "outputs"
FIGURES = OUTPUTS / "figures"
FIGURES.mkdir(parents=True, exist_ok=True)

# ── Colour palette (World Bank) ──────────────────────────────────────────────
WB_DARK = "#002244"
WB_BLUE = "#0071BC"
WB_ACCENT = "#F4A261"
WB_LIGHT = "#B0C4DE"
WB_GRAY = "#888888"

# ── Style helper ─────────────────────────────────────────────────────────────

def apply_style(ax):
    """Apply clean publication style: no top/right spines, light y-grid."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, color="#D0D0D0", linewidth=0.5)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=11)


def save(fig, name):
    """Save figure as both PNG (300 dpi) and SVG."""
    fig.savefig(FIGURES / f"{name}.png", dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(FIGURES / f"{name}.svg", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"[figures] Saved: {name}.png / .svg")


# ── Figure A: Annual overlap bar chart ───────────────────────────────────────

def figure_annual_overlap():
    df = pd.read_csv(OUTPUTS / "02_overlap_annual_summary.csv")

    years = df["year"].astype(int).values
    oha_other = (df["not_applicable_tco2e"] + df["unknown_tco2e"]) / 1e6
    cps_covered = df["cps_covered_tco2e"] / 1e6
    chp_flag = df["chp_flag_tco2e"] / 1e6
    pct = df["overlap_share_of_oha"] * 100

    fig, ax = plt.subplots(figsize=(9, 5.5))

    x = range(len(years))
    bar_width = 0.55

    # Stacked: CPS Covered (bottom), CHP Flag (middle), Other OHA (top)
    b1 = ax.bar(x, cps_covered, bar_width, label="CPS Covered", color=WB_BLUE)
    b2 = ax.bar(x, chp_flag, bar_width, bottom=cps_covered, label="CHP Flag (sensitivity)", color=WB_ACCENT)
    b3 = ax.bar(x, oha_other, bar_width, bottom=cps_covered + chp_flag,
                label="Other UK ETS (not CPS)", color=WB_LIGHT)

    # Overlap percentage annotations — positioned at mid-height of CPS bar
    for i, (xi, p, cc) in enumerate(zip(x, pct, cps_covered)):
        ax.annotate(
            f"{p:.1f}%",
            xy=(xi, cc / 2),
            ha="center", va="center",
            fontsize=10, fontweight="bold", color="white",
        )

    ax.set_xticks(x)
    ax.set_xticklabels(years, fontsize=11)
    ax.set_ylabel("Verified emissions (MtCO\u2082e)", fontsize=11)
    ax.set_title(
        "UK ETS \u00d7 Carbon Price Support: Coverage Overlap (2021\u20132024)",
        fontsize=13, fontweight="bold", pad=14,
    )
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.legend(loc="upper right", fontsize=10, frameon=False)

    apply_style(ax)

    fig.text(
        0.5, -0.02,
        "Source: UK ETS Registry (DESNZ), HMRC CPS Statistics",
        ha="center", fontsize=9, color=WB_GRAY,
    )

    save(fig, "uk_cps_ets_overlap_annual")


# ── Figure B: Sectoral decomposition ────────────────────────────────────────

def figure_sectoral_decomposition():
    df = pd.read_csv(OUTPUTS / "03_sectoral_decomposition_cps_covered.csv")

    # Use latest year emissions
    em_col = "recorded_emissions_2024"
    df = df.sort_values(em_col, ascending=True)

    labels = df["regulator"] + " (" + df["n_installations"].astype(str) + " inst.)"
    values = df[em_col] / 1e6
    total = values.sum()
    pcts = values / total * 100

    colors = [WB_DARK, WB_BLUE, WB_ACCENT][:len(df)]

    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.barh(labels, values, color=colors, height=0.5)

    for bar, val, pct in zip(bars, values, pcts):
        ax.text(
            bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
            f"{val:,.1f} MtCO\u2082e ({pct:.1f}%)",
            va="center", fontsize=10, color=WB_DARK,
        )

    ax.set_xlabel("Verified emissions 2024 (MtCO\u2082e)", fontsize=11)
    ax.set_title(
        "CPS-Covered Emissions by Regulator (NACE 3511 \u2014 Electricity Production)",
        fontsize=12, fontweight="bold", pad=12,
    )
    ax.set_xlim(0, values.max() * 1.45)

    apply_style(ax)

    fig.text(
        0.5, -0.04,
        "Source: UK ETS Registry (DESNZ), HMRC CPS Statistics",
        ha="center", fontsize=9, color=WB_GRAY,
    )

    save(fig, "uk_cps_sectoral_decomposition")


# ── Figure C: Installation classification ────────────────────────────────────

def figure_installation_classification():
    df = pd.read_csv(OUTPUTS / "01_master_oha.csv")

    em_col = "recorded_emissions_2024"

    # Aggregate by cps_scope
    agg = (
        df.groupby("cps_scope")
        .agg(n_installations=("operator_id", "count"), emissions=(em_col, "sum"))
        .reset_index()
    )
    agg["emissions_mt"] = agg["emissions"] / 1e6

    # Define display order and labels
    order = ["CPS_COVERED", "CPS_CHP_FLAG", "CPS_NOT_APPLICABLE"]
    display = {
        "CPS_COVERED": "CPS Covered",
        "CPS_CHP_FLAG": "CHP Flag\n(sensitivity)",
        "CPS_NOT_APPLICABLE": "Not Applicable",
    }
    colors_map = {
        "CPS_COVERED": WB_BLUE,
        "CPS_CHP_FLAG": WB_ACCENT,
        "CPS_NOT_APPLICABLE": WB_LIGHT,
    }

    agg = agg.set_index("cps_scope").reindex(order).reset_index()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5), gridspec_kw={"wspace": 0.35})

    # Left panel: installation count
    labels = [display[s] for s in agg["cps_scope"]]
    colors = [colors_map[s] for s in agg["cps_scope"]]

    bars1 = ax1.bar(labels, agg["n_installations"], color=colors, width=0.55)
    for bar, n in zip(bars1, agg["n_installations"]):
        ax1.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 8,
            f"{n:,}",
            ha="center", va="bottom", fontsize=11, fontweight="bold", color=WB_DARK,
        )
    ax1.set_ylabel("Number of installations", fontsize=11)
    ax1.set_title("Installation count", fontsize=12, fontweight="bold")
    apply_style(ax1)

    # Right panel: emissions volume
    bars2 = ax2.bar(labels, agg["emissions_mt"], color=colors, width=0.55)
    for bar, val in zip(bars2, agg["emissions_mt"]):
        ax2.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
            f"{val:,.1f}",
            ha="center", va="bottom", fontsize=11, fontweight="bold", color=WB_DARK,
        )
    ax2.set_ylabel("Verified emissions 2024 (MtCO\u2082e)", fontsize=11)
    ax2.set_title("Emissions volume", fontsize=12, fontweight="bold")
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    apply_style(ax2)

    fig.suptitle(
        "UK ETS Installation Classification by CPS Scope",
        fontsize=13, fontweight="bold", y=1.02,
    )
    fig.text(
        0.5, -0.04,
        "Source: UK ETS Registry (DESNZ), HMRC CPS Statistics",
        ha="center", fontsize=9, color=WB_GRAY,
    )

    save(fig, "uk_installation_classification")


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Generating publication figures...")
    figure_annual_overlap()
    figure_sectoral_decomposition()
    figure_installation_classification()
    print(f"\nAll figures written to: {FIGURES}/")
