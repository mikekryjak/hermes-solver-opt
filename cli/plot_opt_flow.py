#!/usr/bin/env python3
"""Draw the test4 campaign architecture and optimisation flow infographic.

Generates a publication-quality diagram illustrating:
- Three-tier storage: hermes-solver-opt, solver-opt-store, and $data
- The multi-rung evaluation ladder (Rung 0 -> Rung 1 -> Rung 2)
- Repeat counts and noise-bound gating on the transient
- Studies (S01, S02, S03) and deep-dive Investigations (I01, I02)
- The evidence-based decision gate and durable findings lifecycle

Usage:
    python cli/plot_opt_flow.py [output_path.png]
"""

import sys
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, FancyArrowPatch

# ---------------------------------------------------------------- palette ---
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#383734"
MUTED = "#6e6c65"
RULE = "#d8d7d0"
CARD_BG = "#ffffff"
CARD_ALT = "#f5f4ee"

BLUE = "#1a66c2"
BLUE_BG = "#e8f0fe"
BLUE_RULE = "#bcd0ee"

ORANGE = "#c84714"
ORANGE_BG = "#fceee6"
ORANGE_RULE = "#f5cdb8"

GREEN = "#138a5a"
GREEN_BG = "#e6f6ee"
GREEN_RULE = "#b7e4ce"

PURPLE = "#6a3db5"
PURPLE_BG = "#f2ecfa"
PURPLE_RULE = "#d7c6ee"

GOLD = "#a66e08"
GOLD_BG = "#fef8e7"
GOLD_RULE = "#f5e2a3"


def create_infographic(out_path):
    fig_w, fig_h = 16.0, 9.0
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=220)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    ax.axis("off")

    # Base background
    ax.add_patch(Rectangle((0, 0), fig_w, fig_h, facecolor=SURFACE, edgecolor="none", zorder=0))

    # Helper: rounded card
    def card(x, y, w, h, bg=CARD_BG, border=RULE, lw=1.0, round_r=0.10, z=1):
        box = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={round_r}",
                             facecolor=bg, edgecolor=border, linewidth=lw, zorder=z)
        ax.add_patch(box)
        return box

    # Helper: pill badge (top-left positioned)
    def pill_tl(x, top_y, text, bg=BLUE_BG, fg=BLUE, border=None, fs=8.5, bold=True, pad_x=0.12, pad_y=0.06, z=4):
        w = len(text) * (fs * 0.0092) + pad_x * 2
        h = (fs * 0.024) + pad_y * 2
        y = top_y - h
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.08",
                             facecolor=bg, edgecolor=border or bg, linewidth=0.8, zorder=z)
        ax.add_patch(box)
        ax.text(x + w / 2, y + h / 2, text, fontsize=fs, fontweight="bold" if bold else "normal",
                color=fg, ha="center", va="center", zorder=z + 1, fontfamily="sans-serif")
        return x + w, y

    # Helper: arrow
    def flow_arrow(x1, y1, x2, y2, color=BLUE, lw=1.5, ls="-", z=4):
        arrow = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=11,
                                color=color, linewidth=lw, linestyle=ls, zorder=z)
        ax.add_patch(arrow)
        return arrow

    # =========================================================================
    # HEADER BANNER
    # =========================================================================
    ax.text(0.65, 8.52, "Hermes-3 Solver Optimisation: Architecture & Flow",
            fontsize=20, fontweight="bold", color=INK, fontfamily="sans-serif")
    ax.text(0.65, 8.24, "The test4 Campaign: multi-tier repositories, rung-based screening, noise-aware evaluation, and durable findings",
            fontsize=10.5, color=MUTED, fontfamily="sans-serif")

    pill_tl(13.4, 8.55, "CAMPAIGN: test4-jacobian", bg=PURPLE_BG, fg=PURPLE, border=PURPLE_RULE, fs=9.5)

    # Dividing rule under header
    ax.plot([0.65, 15.35], [8.08, 8.08], color=RULE, lw=1.0, zorder=2)

    # =========================================================================
    # COLUMN 1: REPOSITORIES & STORAGE (Left, x: 0.65 -> 4.95, w=4.3)
    # =========================================================================
    c1_x, c1_w = 0.65, 4.3
    card(c1_x, 0.72, c1_w, 7.18, bg=CARD_ALT, border=RULE, lw=1.0)
    ax.text(c1_x + 0.22, 7.62, "1. Three-Tier Architecture", fontsize=13, fontweight="bold", color=INK)
    ax.text(c1_x + 0.22, 7.40, "Clear separation of framework, evidence, and transient cases", fontsize=8.5, color=MUTED)

    # Tier 1: hermes-solver-opt
    t1_y, t1_h = 5.25, 1.95
    card(c1_x + 0.18, t1_y, c1_w - 0.36, t1_h, bg=CARD_BG, border=BLUE_RULE, lw=1.2)
    rx, by = pill_tl(c1_x + 0.32, t1_y + t1_h - 0.14, "hermes-solver-opt", bg=BLUE_BG, fg=BLUE, fs=9)
    ax.text(rx + 0.12, (t1_y + t1_h - 0.14 + by) / 2, "(Public framework)", fontsize=8.5, color=MUTED, va="center")
    ax.text(c1_x + 0.32, by - 0.10,
            "• Automation tools: runner, slice tools, validators\n"
            "• Living requirements: R1–R38 with stable IDs\n"
            "• Task tracking: beads issue tracker (Dolt DB)\n"
            "• Architectural findings: campaigns/test4-jacobian/findings.md",
            fontsize=8.3, color=INK_2, linespacing=1.35, va="top")

    # Tier 2: solver-opt-store
    t2_y, t2_h = 2.95, 2.15
    card(c1_x + 0.18, t2_y, c1_w - 0.36, t2_h, bg=CARD_BG, border=GREEN_RULE, lw=1.2)
    rx, by = pill_tl(c1_x + 0.32, t2_y + t2_h - 0.14, "solver-opt-store", bg=GREEN_BG, fg=GREEN, fs=9)
    ax.text(rx + 0.12, (t2_y + t2_h - 0.14 + by) / 2, "(Private evidence)", fontsize=8.5, color=MUTED, va="center")
    ax.text(c1_x + 0.32, by - 0.10,
            "• Central immutable index: one row per run\n"
            "• Run bundles: step logs, residual shares, traces\n"
            "• Study manifests: S01, S02, S03 (.toml budgets)\n"
            "• Standardised reporting: 10-section analysis,\n"
            "  auto-generated briefs, HTML and PDF reports",
            fontsize=8.3, color=INK_2, linespacing=1.35, va="top")

    # Tier 3: $data/cases/
    t3_y, t3_h = 0.85, 1.95
    card(c1_x + 0.18, t3_y, c1_w - 0.36, t3_h, bg=CARD_BG, border=ORANGE_RULE, lw=1.2)
    rx, by = pill_tl(c1_x + 0.32, t3_y + t3_h - 0.14, "$data/cases/", bg=ORANGE_BG, fg=ORANGE, fs=9)
    ax.text(rx + 0.12, (t3_y + t3_h - 0.14 + by) / 2, "(Transient storage)", fontsize=8.5, color=MUTED, va="center")
    ax.text(c1_x + 0.32, by - 0.10,
            "• Simulation working directories & seeds\n"
            "• Raw BOUT++ dumps (~1 GB per run)\n"
            "• Diagnostic extraction pipeline before deletion\n"
            "• Dumps pruned promptly to bound disk usage",
            fontsize=8.3, color=INK_2, linespacing=1.35, va="top")

    # Inter-tier connecting arrows
    flow_arrow(c1_x + c1_w / 2, t1_y, c1_x + c1_w / 2, t2_y + t2_h, color=BLUE, lw=1.3)
    flow_arrow(c1_x + c1_w / 2, t2_y, c1_x + c1_w / 2, t3_y + t3_h, color=GREEN, lw=1.3)

    # =========================================================================
    # COLUMN 2: THE MULTI-RUNG EVALUATION ENGINE (Middle, x: 5.15 -> 10.35, w=5.2)
    # =========================================================================
    c2_x, c2_w = 5.15, 5.2
    card(c2_x, 0.72, c2_w, 7.18, bg=CARD_ALT, border=RULE, lw=1.0)
    ax.text(c2_x + 0.22, 7.62, "2. test4 Evaluation Ladder & Noise Gate", fontsize=13, fontweight="bold", color=INK)
    ax.text(c2_x + 0.22, 7.40, "Cheap slices filter candidates; only survivors pay for full simulation", fontsize=8.5, color=MUTED)

    # Target context banner
    card(c2_x + 0.18, 6.75, c2_w - 0.36, 0.50, bg=PURPLE_BG, border=PURPLE_RULE, lw=1.0)
    ax.text(c2_x + 0.30, 7.00, "Target Problem: test4 transient (2–6 ms holds 92% of full simulation time)",
            fontsize=8.5, fontweight="bold", color=PURPLE, va="center")

    # Rung 0 Card (Top)
    r0_y, r0_h = 4.95, 1.65
    card(c2_x + 0.18, r0_y, c2_w - 0.36, r0_h, bg=CARD_BG, border=BLUE_RULE, lw=1.2)
    rx, by = pill_tl(c2_x + 0.30, r0_y + r0_h - 0.12, "Rung 0", bg=BLUE, fg="#ffffff", fs=8.5)
    ax.text(rx + 0.12, (r0_y + r0_h - 0.12 + by) / 2, "Screen Many: short slices (3.0–3.2 ms, 4.0–4.1 ms)",
            fontsize=8.8, fontweight="bold", color=INK, va="center")
    ax.text(c2_x + 0.30, by - 0.10,
            "• Cost: ~200 s per run (seeded from saved reference states)\n"
            "• Purpose: screen 20+ candidate solver settings cheaply\n"
            "• Output: eliminates 80%+ of ineffective configurations fast",
            fontsize=8.3, color=INK_2, linespacing=1.35, va="top")

    # Rung 1 Card (Middle)
    r1_y, r1_h = 3.30, 1.50
    card(c2_x + 0.18, r1_y, c2_w - 0.36, r1_h, bg=CARD_BG, border=BLUE_RULE, lw=1.2)
    rx, by = pill_tl(c2_x + 0.30, r1_y + r1_h - 0.12, "Rung 1", bg=BLUE, fg="#ffffff", fs=8.5)
    ax.text(rx + 0.12, (r1_y + r1_h - 0.12 + by) / 2, "Test Survivors: intermediate slices (3.0–4.0 ms, 4.0–5.0 ms)",
            fontsize=8.8, fontweight="bold", color=INK, va="center")
    ax.text(c2_x + 0.30, by - 0.10,
            "• Cost: ~1000 s per run (~5x Rung 0)\n"
            "• Purpose: verify that Rung 0 speedups persist over longer horizons\n"
            "• Cross-rung check: confirm rank order agreement before promotion",
            fontsize=8.3, color=INK_2, linespacing=1.35, va="top")

    # Rung 2 Card (Bottom)
    r2_y, r2_h = 1.95, 1.20
    card(c2_x + 0.18, r2_y, c2_w - 0.36, r2_h, bg=CARD_BG, border=BLUE_RULE, lw=1.2)
    rx, by = pill_tl(c2_x + 0.30, r2_y + r2_h - 0.12, "Rung 2", bg=BLUE, fg="#ffffff", fs=8.5)
    ax.text(rx + 0.12, (r2_y + r2_h - 0.12 + by) / 2, "Confirm Finalists: full simulation (0.0–100.0 ms)",
            fontsize=8.8, fontweight="bold", color=INK, va="center")
    ax.text(c2_x + 0.30, by - 0.10,
            "• Cost: 2500 s to 17 hours (full production turnaround)\n"
            "• Purpose: prove real scientific throughput gain across full physics",
            fontsize=8.3, color=INK_2, linespacing=1.35, va="top")

    # Ladder downward filter arrows (on the right margin of Col 2)
    flow_arrow(c2_x + c2_w - 0.40, r0_y + 0.1, c2_x + c2_w - 0.40, r1_y + r1_h - 0.1, color=BLUE, lw=1.6)
    flow_arrow(c2_x + c2_w - 0.40, r1_y + 0.1, c2_x + c2_w - 0.40, r2_y + r2_h - 0.1, color=BLUE, lw=1.6)
    ax.text(c2_x + c2_w - 0.46, 4.15, "Promote\nWinners", fontsize=7.8, color=BLUE, fontweight="bold", ha="right", va="center")
    ax.text(c2_x + c2_w - 0.46, 2.65, "Confirm\nFinalists", fontsize=7.8, color=BLUE, fontweight="bold", ha="right", va="center")

    # Noise & Repeat Control Card
    rep_y, rep_h = 0.85, 0.95
    card(c2_x + 0.18, rep_y, c2_w - 0.36, rep_h, bg=GOLD_BG, border=GOLD_RULE, lw=1.1)
    rx, by = pill_tl(c2_x + 0.30, rep_y + rep_h - 0.10, "Noise & Repeat Control", bg=GOLD, fg="#ffffff", fs=8)
    ax.text(c2_x + 0.30, by - 0.08,
            "• 3 to 10 repeats per cell: measures numerical path noise on the 2.65 ms cliff\n"
            "• Strict noise floor: 15% bound on Rung 0. No claim without clearing spread!",
            fontsize=8.2, color=INK_2, linespacing=1.3, va="top")

    # =========================================================================
    # COLUMN 3: STUDIES, DECISIONS & FINDINGS (Right, x: 10.55 -> 15.35, w=4.8)
    # =========================================================================
    c3_x, c3_w = 10.55, 4.8
    card(c3_x, 0.72, c3_w, 7.18, bg=CARD_ALT, border=RULE, lw=1.0)
    ax.text(c3_x + 0.22, 7.62, "3. Studies & Decision Protocol", fontsize=13, fontweight="bold", color=INK)
    ax.text(c3_x + 0.22, 7.40, "Hypothesis testing, gate criteria, and durable learning", fontsize=8.5, color=MUTED)

    # Combined Studies & Investigations Card
    s_y, s_h = 3.65, 3.60
    card(c3_x + 0.18, s_y, c3_w - 0.36, s_h, bg=CARD_BG, border=GREEN_RULE, lw=1.2)
    rx, by = pill_tl(c3_x + 0.30, s_y + s_h - 0.12, "Campaign Studies & Investigations", bg=GREEN_BG, fg=GREEN, fs=9)

    # S01
    s01_top = by - 0.08
    rx, by1 = pill_tl(c3_x + 0.30, s01_top, "S01", bg=BLUE, fg="#ffffff", fs=8)
    ax.text(rx + 0.10, (s01_top + by1) / 2, "Jacobian Lag Screening (22 settings, 167 runs)",
            fontsize=8.2, fontweight="bold", color=INK, va="center")
    ax.text(c3_x + 0.30, by1 - 0.06,
            "• Overturned production dogma: lag 1 beats lag 3 by 1.3x–2.6x\n"
            "• Identified timestep controller gains as the next major lever",
            fontsize=8.0, color=INK_2, linespacing=1.25, va="top")

    # S02
    s02_top = by1 - 0.42
    rx, by2 = pill_tl(c3_x + 0.30, s02_top, "S02", bg=MUTED, fg="#ffffff", fs=8)
    ax.text(rx + 0.10, (s02_top + by2) / 2, "Repeat Noise & Path Bifurcation",
            fontsize=8.2, fontweight="bold", color=INK, va="center")
    ax.text(c3_x + 0.30, by2 - 0.06,
            "• Quantified run-to-run spread on the stiff 2.65 ms solver cliff",
            fontsize=8.0, color=INK_2, linespacing=1.25, va="top")

    # S03
    s03_top = by2 - 0.30
    rx, by3 = pill_tl(c3_x + 0.30, s03_top, "S03", bg=GREEN, fg="#ffffff", fs=8)
    ax.text(rx + 0.10, (s03_top + by3) / 2, "Layered Options & Controller Gains (898 runs)",
            fontsize=8.2, fontweight="bold", color=INK, va="center")
    ax.text(c3_x + 0.30, by3 - 0.06,
            "• Explored kI/kP gain plane; layered lag 1 + tuned PID gains\n"
            "• Achieved up to 26x transient speedup and 2.5x full-run win!",
            fontsize=8.0, color=INK_2, linespacing=1.25, va="top")

    # Investigations sub-section inside this card
    inv_top = by3 - 0.40
    rx, by_inv = pill_tl(c3_x + 0.30, inv_top, "I01 / I02", bg=PURPLE, fg="#ffffff", fs=8)
    ax.text(rx + 0.10, (inv_top + by_inv) / 2, "Targeted Diagnostic Investigations",
            fontsize=8.2, fontweight="bold", color=PURPLE, va="center")
    ax.text(c3_x + 0.30, by_inv - 0.06,
            "• I01: core-edge residual; I02: direct solver round-off divergence",
            fontsize=8.0, color=INK_2, linespacing=1.25, va="top")

    # Promotion Decision Gate Card
    g_y, g_h = 2.18, 1.32
    card(c3_x + 0.18, g_y, c3_w - 0.36, g_h, bg=CARD_BG, border=ORANGE_RULE, lw=1.2)
    rx, by = pill_tl(c3_x + 0.30, g_y + g_h - 0.10, "Promotion Decision Gate", bg=ORANGE_BG, fg=ORANGE, fs=8.5)
    ax.text(c3_x + 0.30, by - 0.08,
            "1. Physics verification: separatrix & target profiles match < 0.04%\n"
            "2. Repeat clearance: speedup strictly exceeds declared noise bound\n"
            "3. Cross-rung consistency: Rung 0 speedup confirmed on Rung 1\n"
            "Action: PROMOTE to next rung, REJECT, or QUARANTINE",
            fontsize=8.0, color=INK_2, linespacing=1.3, va="top")

    # Durable Findings Storage Card
    f_y, f_h = 0.85, 1.18
    card(c3_x + 0.18, f_y, c3_w - 0.36, f_h, bg=CARD_BG, border=BLUE_RULE, lw=1.2)
    rx, by = pill_tl(c3_x + 0.30, f_y + f_h - 0.10, "Durable Findings Log", bg=BLUE_BG, fg=BLUE, fs=8.5)
    ax.text(c3_x + 0.30, by - 0.08,
            "• Structured records: date, status, scope, evidence, actionable rule\n"
            "• Recorded in campaigns/test4-jacobian/findings.md and root findings.md\n"
            "• Graduated into production solver recipe defaults and requirements",
            fontsize=8.0, color=INK_2, linespacing=1.3, va="top")

    # Direct vertical connectors in Column 3
    # Ladder -> Studies
    flow_arrow(c2_x + c2_w - 0.05, 5.75, c3_x + 0.15, 5.75, color=GREEN, lw=1.6)
    # Studies -> Decision Gate (straight vertical line)
    flow_arrow(c3_x + c3_w / 2, s_y, c3_x + c3_w / 2, g_y + g_h, color=ORANGE, lw=1.6)
    # Decision Gate -> Durable Findings (straight vertical line)
    flow_arrow(c3_x + c3_w / 2, g_y, c3_x + c3_w / 2, f_y + f_h, color=BLUE, lw=1.6)

    # Loopback arrow from Findings back to Column 1 (Graduating into framework)
    loop_y = 0.52
    ax.plot([c3_x + 0.8, c3_x + 0.8, c1_x + c1_w - 0.3, c1_x + c1_w - 0.3],
            [f_y, loop_y, loop_y, t1_y], color=BLUE, lw=1.2, ls="--", zorder=3)
    pill_tl(4.9, loop_y + 0.14, "Graduated findings update framework requirements & production defaults",
            bg=CARD_BG, fg=BLUE, border=BLUE_RULE, fs=8.0)

    # =========================================================================
    # FOOTER HIGHLIGHT BAR
    # =========================================================================
    card(0.65, 0.10, 14.7, 0.42, bg=INK, border=INK, lw=1.0)
    ax.text(8.0, 0.31,
            "HEADLINE ACHIEVEMENT: 865-knob space  →  S01 lag sweep (1.3x–2.6x)  →  S03 layered gains (up to 26x transient / 2.5x full run)  →  Zero physics loss (<0.04%)",
            fontsize=9.0, fontweight="bold", color="#ffffff", ha="center", va="center")

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    plt.savefig(out_path, dpi=220, facecolor=SURFACE)
    plt.close(fig)
    print(f"wrote infographic to {out_path}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "figures/test4-opt-flow.png"
    create_infographic(out)
