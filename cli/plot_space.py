"""Draw the shape of a solver parameter space from a TSV inventory.

Reads a tab-separated file with these columns (role and n_values optional):

    option  kind  default  family  object  depends  source  help  role  n_values

and writes:

    1-knob-count.png    how many knobs there are, by the type of value
    2-conditional.png   how much of the space is gated by a parent choice
    3-live-config.png   how many knobs one named configuration exposes
    4-space-size.png    how many configurations the whole space allows

Usage:
    python plot_space.py <input.tsv> [output_dir] [--config a=b,c=d]

`--config` names one point in the space, as parent=value pairs. Figure 3 is
drawn only when it is given. The script plots whatever TSV it is handed;
every number on every figure is computed from the input.
"""
import sys
import os
import math
from collections import Counter, OrderedDict

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D

# ---------------------------------------------------------------- palette ---
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
TILE = "#f3f2ee"
DEEMPH = "#d8d7d0"          # de-emphasis fill: blocks that are not the point

BLUE = "#2a78d6"
BLUE_L = "#5598e7"
ORANGE = "#eb6834"
AQUA = "#1baf7a"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "sans-serif"],
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "text.color": INK,
    "axes.edgecolor": BASELINE,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.grid": False,
})

DPI = 220

# ------------------------------------------------- counting assumptions -----
# Distinct values a knob of each kind contributes to the product, used only
# where the input does not state a count. Printed on the figure that uses it.
VALUES_PER_KIND = OrderedDict([
    ("bool", 2),
    ("enum", 4),
    ("list", 4),
    ("int", 8),
    ("real", 10),
    ("string", 1),     # not searched
    ("array", 1),      # not searched
])

# Families supplied by the calling code rather than the solver library.
HOST_FAMILIES = {"bout"}

# Headline groups: label, sub-label, member kinds, accent colour.
GROUPS = [
    ("Binary", "bool", ["bool"], AQUA),
    ("Discrete", "int, enum, list", ["int", "enum", "list"], ORANGE),
    ("Continuous", "real", ["real"], BLUE),
    ("Free-form", "string, array", ["string", "array"], DEEMPH),
]

KIND_ORDER = ["bool", "int", "real", "enum", "list", "array", "string"]


# ---------------------------------------------------- text measurement ------
def _renderer(fig):
    fig.canvas.draw()
    return fig.canvas.get_renderer()


def fig_text_w(fig, s, fontsize, weight="normal"):
    """Width of a string as a fraction of figure width."""
    t = fig.text(0, 0, s, fontsize=fontsize, fontweight=weight, alpha=0)
    bb = t.get_window_extent(renderer=_renderer(fig))
    t.remove()
    return bb.width / fig.bbox.width


def wrap(fig, s, fontsize, max_w, weight="normal"):
    """Break a string into lines that each fit within max_w (figure fraction)."""
    lines, cur = [], ""
    for word in s.split():
        trial = word if not cur else cur + " " + word
        if fig_text_w(fig, trial, fontsize, weight) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return "\n".join(lines)


def ax_text_w(ax, s, fontsize, weight="normal"):
    """Width of a string in x-data units on ax."""
    t = ax.text(0, 0, s, fontsize=fontsize, fontweight=weight, alpha=0)
    bb = t.get_window_extent(renderer=_renderer(ax.figure))
    t.remove()
    p0, p1 = ax.transData.inverted().transform([(0, 0), (bb.width, 0)])
    return abs(p1[0] - p0[0])


def bare(ax):
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])


def fmt_int(n):
    return "{:,}".format(int(n))


def bar_axes(ax, xmax):
    ax.set_xlim(0, xmax)
    ax.tick_params(axis="x", labelsize=13)
    ax.tick_params(axis="y", length=0)
    ax.xaxis.grid(True, color=GRID, lw=1.0, zorder=0)
    ax.set_axisbelow(True)
    for s in ["top", "right", "left"]:
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)


# ------------------------------------------------------------------ data ----
def load(path):
    df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    need = ["option", "kind", "family", "depends"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise SystemExit("input is missing columns: %s" % ", ".join(missing))
    for c in df.columns:
        df[c] = df[c].fillna("").astype(str).str.strip()
    df = df[df["option"] != ""].copy()
    df["kind"] = df["kind"].str.lower()
    df["family"] = df["family"].str.lower()
    if "n_values" not in df.columns:
        df["n_values"] = ""

    n_rows = len(df)
    n_diag = 0
    if "role" in df.columns:
        df["role"] = df["role"].str.lower()
        n_diag = int((df["role"] == "diagnostic").sum())
        df = df[df["role"] != "diagnostic"]
    n_names = df["option"].nunique()
    print("read %d rows; set aside %d diagnostics; plotting %d tuning rows "
          "(%d distinct option names)" % (n_rows, n_diag, len(df), n_names))
    return df.reset_index(drop=True)


def clauses(depends):
    """[(parent, {allowed values})] for a depends string."""
    out = []
    for cl in str(depends).split(","):
        cl = cl.strip()
        if not cl or "=" not in cl:
            continue
        var, _, vals = cl.partition("=")
        out.append((var.strip(),
                    set(v.strip() for v in vals.split("|") if v.strip())))
    return out


def gating_var(depends):
    c = clauses(depends)
    return c[0][0] if c else ""


def is_live(depends, config):
    for var, allowed in clauses(depends):
        if config.get(var) not in allowed:
            return False
    return True


def n_values_of(row):
    """How many values a knob offers: the source's count where it gives one."""
    stated = str(row.get("n_values", "")).strip()
    if stated:
        try:
            v = int(float(stated))
            if v > 1:
                return v
        except ValueError:
            pass
    return VALUES_PER_KIND.get(row["kind"], 1)


def log10_configs(sub):
    return sum(math.log10(n_values_of(r)) for _, r in sub.iterrows()
               if n_values_of(r) > 1)


# ============================================================ figure one ====
def fig_counts(df, out):
    total = len(df)
    counts = Counter(df["kind"])
    known = set(sum([g[2] for g in GROUPS], []))
    other = sum(v for k, v in counts.items() if k not in known)

    items = [(lab, sub, sum(counts.get(k, 0) for k in kinds), col)
             for lab, sub, kinds, col in GROUPS]
    if other:
        items.append(("Other", "unclassified", other, DEEMPH))
    items = [it for it in items if it[2] > 0]
    searchable = total - sum(n for lab, _, n, _ in items
                             if lab in ("Free-form", "Other"))
    n_host = int(df["family"].isin(HOST_FAMILIES).sum())
    build = None
    if "in_build" in df.columns:
        b = df["in_build"].str.strip().str.lower()
        build = dict(confirmed=int((b != "not found").sum()),
                     lib=int((b == "yes").sum()),
                     host=int((b == "bout").sum()),
                     missing=int((b == "not found").sum()))

    fig = plt.figure(figsize=(14, 8.0), dpi=DPI)
    L, R = 0.05, 0.965

    fig.text(L, 0.962, "The solver parameter space", fontsize=30,
             fontweight="bold", va="top", color=INK)
    fig.text(L, 0.898,
             wrap(fig, "Every knob the nonlinear solver stack exposes, "
                       "counted by the type of value it takes.", 17, R - L),
             fontsize=17, va="top", color=INK_2, linespacing=1.4)

    hero = fmt_int(total)
    fig.text(L, 0.790, hero, fontsize=100, fontweight="bold", va="top",
             color=INK)
    hw = fig_text_w(fig, hero, 100, "bold")
    fig.text(L + hw + 0.016, 0.672, "tuneable\nknobs", fontsize=24,
             va="center", ha="left", color=INK_2, linespacing=1.2)
    fig.text(L, 0.545,
             wrap(fig, "%s of them take a value worth searching. %s come "
                       "from the calling code's own input file; the rest are "
                       "the solver library's."
                       % (fmt_int(searchable), fmt_int(n_host)), 16, R - L),
             fontsize=16, va="top", color=MUTED, linespacing=1.45)

    n = len(items)
    gap = 0.018
    w = (R - L - gap * (n - 1)) / n
    y0, h = 0.185, 0.285
    for i, (label, sub, cnt, colour) in enumerate(items):
        ax = fig.add_axes([L + i * (w + gap), y0, w, h])
        bare(ax)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.add_patch(Rectangle((0, 0), 1, 1, facecolor=TILE, edgecolor="none"))
        ax.add_patch(Rectangle((0, 0.955), 1, 0.045, facecolor=colour,
                               edgecolor="none"))
        ax.text(0.06, 0.83, fmt_int(cnt), fontsize=52, fontweight="bold",
                va="top", color=INK)
        ax.text(0.06, 0.40, label, fontsize=19, fontweight="bold", va="top",
                color=INK)
        ax.text(0.06, 0.25, sub, fontsize=14.5, va="top", color=INK_2)
        ax.text(0.06, 0.115, "%.0f%% of all knobs" % (100.0 * cnt / total),
                fontsize=14, va="top", color=MUTED)

    foot = ("One knob per row of the inventory. Counts are exact; nothing "
            "on this figure is estimated.")
    if build:
        foot += (" %s of the %s are confirmed present in the library build "
                 "actually linked: %s solver-library names found in it plus "
                 "%s from the calling code. The other %s are mostly "
                 "preconditioners this build does not compile, so absence "
                 "here is weaker evidence than presence."
                 % (fmt_int(build["confirmed"]), fmt_int(total),
                    fmt_int(build["lib"]), fmt_int(build["host"]),
                    fmt_int(build["missing"])))
    fig.text(L, 0.140, wrap(fig, foot, 13.5, R - L), fontsize=13.5,
             va="top", color=MUTED, linespacing=1.55)

    fig.savefig(out, dpi=DPI)
    plt.close(fig)
    return dict(total=total, items=items, searchable=searchable,
                by_kind=dict(counts), host=n_host, build=build)


# ============================================================ figure two ====
def fig_conditional(df, out):
    total = len(df)
    df = df.copy()
    df["gate"] = df["depends"].map(gating_var)

    uncond = int((df["gate"] == "").sum())
    cond = total - uncond
    by_var = Counter(df.loc[df["gate"] != "", "gate"]).most_common()

    fig = plt.figure(figsize=(14, 8.8), dpi=DPI)
    L, R = 0.05, 0.965
    fig.text(L, 0.963, "Most of the space does not exist yet", fontsize=30,
             fontweight="bold", va="top", color=INK)
    fig.text(L, 0.900,
             wrap(fig, "A knob is only real once its parent option is set to "
                       "the right value. Block width is the number of knobs.",
                  17, R - L),
             fontsize=17, va="top", color=INK_2, linespacing=1.4)

    ax = fig.add_axes([L, 0.225, 0.895, 0.600])
    bare(ax)
    ax.set_xlim(0, total)
    ax.set_ylim(0, 4.80)
    gap = total * 0.0022
    RH = 0.58

    def block(x, w, y, colour, label=None, sub=None, fs=15, light=False,
              g=None):
        gg = gap if g is None else g
        ax.add_patch(Rectangle((x + gg / 2, y), max(w - gg, 0), RH,
                               facecolor=colour, edgecolor="none"))
        if label is None:
            return True
        need = ax_text_w(ax, label, fs, "bold")
        if sub:
            need = max(need, ax_text_w(ax, sub, fs - 2))
        if need + total * 0.022 > w:
            return False
        tc = "#ffffff" if light else INK
        if sub:
            ax.text(x + w / 2, y + RH * 0.62, label, fontsize=fs,
                    fontweight="bold", ha="center", va="center", color=tc)
            ax.text(x + w / 2, y + RH * 0.27, sub, fontsize=fs - 2,
                    ha="center", va="center", color=tc)
        else:
            ax.text(x + w / 2, y + RH * 0.5, label, fontsize=fs,
                    fontweight="bold", ha="center", va="center", color=tc)
        return True

    def key_row(items, lead_in, y, fs=12.5, side=0.105):
        """A flowed key for blocks too narrow to carry their own label.

        `side` is the swatch size in inches, converted to each axis's own
        data units so the swatch stays square.
        """
        if not items:
            return
        bb = ax.get_window_extent(renderer=_renderer(fig))
        dpi = fig.dpi
        sw = side * dpi / bb.width * (ax.get_xlim()[1] - ax.get_xlim()[0])
        sh = side * dpi / bb.height * (ax.get_ylim()[1] - ax.get_ylim()[0])
        pad, lead = total * 0.006, total * 0.024
        x, yy, indent = 0.0, y, 0.0
        ax.text(x, yy, lead_in, fontsize=fs, ha="left", va="center",
                color=MUTED)
        x = indent = ax_text_w(ax, lead_in, fs) + lead
        for name, cnt, col in items:
            label = "%s  %s" % (name, fmt_int(cnt))
            need = sw + pad + ax_text_w(ax, label, fs)
            if x + need > total:
                x, yy = indent, yy - sh * 2.2
            ax.add_patch(Rectangle((x, yy - sh / 2), sw, sh,
                                   facecolor=col, edgecolor="none"))
            ax.text(x + sw + pad, yy, label, fontsize=fs, ha="left",
                    va="center", color=INK_2)
            x += need + lead

    y1, y2, y3, y4 = 4.07, 3.04, 1.98, 0.80

    block(0, total, y1, "#e6e5de", "all %s knobs" % fmt_int(total), None, 18)

    block(0, uncond, y2, DEEMPH, "always present",
          "%s  (%.0f%%)" % (fmt_int(uncond), 100.0 * uncond / total), 16)
    block(uncond, cond, y2, BLUE, "exist only under some type choice",
          "%s  (%.0f%%)" % (fmt_int(cond), 100.0 * cond / total), 16,
          light=True)

    # row 3: which parent option switches the block on
    block(0, uncond, y3, "#efeee9")
    x, lead3 = uncond, []
    for i, (name, cnt) in enumerate(by_var):
        col = BLUE if i % 2 == 0 else BLUE_L
        if not block(x, cnt, y3, col, name, fmt_int(cnt), 13.5, light=True):
            lead3.append((name, cnt, col))
        x += cnt

    # row 4: the mutually exclusive values of that parent
    block(0, uncond, y4, "#efeee9")
    x = uncond
    n_children = 0
    for i, (var, _) in enumerate(by_var):
        kids = Counter(df.loc[df["gate"] == var, "depends"]).most_common()
        n_children += len(kids)
        for j, (dep, cnt) in enumerate(kids):
            val = dep.split("=", 1)[1] if "=" in dep else dep
            short = val.split("|")[0] + (u"…" if "|" in val else "")
            col = BLUE if (i + j) % 2 == 0 else BLUE_L
            block(x, cnt, y4, col, short, fmt_int(cnt), 12.5, light=True,
                  g=total * 0.0009)
            x += cnt
    # hairline separators where the blocks are too thin to carry a gap
    x = uncond
    for var, _ in by_var:
        for dep, cnt in Counter(df.loc[df["gate"] == var,
                                       "depends"]).most_common():
            ax.plot([x, x], [y4, y4 + RH], color=SURFACE, lw=1.4, zorder=3)
            x += cnt

    caps = [(y1, "1.  the whole space"),
            (y2, "2.  does it exist by default?"),
            (y3, "3.  which parent option switches it on"),
            (y4, u"4.  which value of that parent — %d blocks, and only "
                 u"one value per parent can be chosen" % n_children)]
    for y, txt in caps:
        ax.text(0, y + RH + 0.085, txt, fontsize=13.5, color=MUTED,
                va="bottom")
    key_row(lead3, "Narrow blocks in row 3, in order:", 0.32, 12.5)

    top_var, top_n = by_var[0]
    top_blocks = Counter(df.loc[df["gate"] == top_var, "depends"])
    biggest = max(top_blocks.values())
    stated = df.loc[df["option"] == top_var, "n_values"]
    stated = stated.iloc[0].strip() if len(stated) else ""
    nv = ("accepts %s values, %d of which bring knobs of their own"
          % (stated, len(top_blocks))) if stated else \
         ("has %d values that bring knobs of their own" % len(top_blocks))

    fig.text(L, 0.185,
             wrap(fig, u"%s alone gates %s of the %s knobs — %.0f%% of "
                       u"the space. It %s, and they are mutually exclusive: "
                       u"choose one and you keep at most %s of those knobs "
                       u"and delete the rest."
                       % (top_var, fmt_int(top_n), fmt_int(total),
                          100.0 * top_n / total, nv, fmt_int(biggest)),
                  16, R - L),
             fontsize=16, va="top", color=INK_2, linespacing=1.45)
    fig.text(L, 0.052,
             "The parent is read from the depends column. A knob with no "
             "depends entry counts as always present.",
             fontsize=13.5, va="top", color=MUTED)

    fig.savefig(out, dpi=DPI)
    plt.close(fig)
    return dict(uncond=uncond, cond=cond, by_var=by_var, top=(top_var, top_n),
                biggest=biggest, n_children=n_children)


# ========================================================== figure three ====
def fig_live(df, config, out):
    total = len(df)
    live = df[df["depends"].map(lambda d: is_live(d, config))]
    n_live = len(live)
    counts = Counter(live["kind"])
    pairs = sorted(counts.items(), key=lambda t: -t[1])
    kinds = [k for k, _ in pairs]
    vals = [v for _, v in pairs]

    df2 = df.copy()
    df2["gate"] = df2["depends"].map(gating_var)
    by_var = Counter(df2.loc[df2["gate"] != "", "gate"]).most_common()
    top_var = by_var[0][0]
    blocks = Counter(df2.loc[df2["gate"] == top_var, "depends"])
    here = sum(c for d, c in blocks.items()
               if config.get(top_var) in dict(clauses(d)).get(top_var, set()))
    best_dep, best_n = max(blocks.items(), key=lambda kv: kv[1])
    best_val = best_dep.split("=", 1)[1].split("|")[0]

    fig = plt.figure(figsize=(14, 8.2), dpi=DPI)
    L, R = 0.05, 0.965

    fig.text(L, 0.962, "One point in that space is already this big",
             fontsize=30, fontweight="bold", va="top", color=INK)
    cfg = u"   ·   ".join("%s = %s" % (k, v) for k, v in config.items())
    fig.text(L, 0.898,
             wrap(fig, "The configuration being run today: " + cfg, 15.5,
                  R - L),
             fontsize=15.5, va="top", color=INK_2, linespacing=1.5)

    hero = fmt_int(n_live)
    fig.text(L, 0.775, hero, fontsize=100, fontweight="bold", va="top",
             color=BLUE)
    hw = fig_text_w(fig, hero, 100, "bold")
    fig.text(L + hw + 0.020, 0.700,
             wrap(fig, u"tuning knobs are live in this one configuration, "
                       u"before anyone changes a single type choice — "
                       u"%.0f%% of the %s in the whole space."
                       % (100.0 * n_live / total, fmt_int(total)),
                  18, R - (L + hw + 0.020)),
             fontsize=18, va="center", ha="left", color=INK, linespacing=1.45)

    fig.text(L, 0.545, "What kind of value those %s knobs take" % hero,
             fontsize=17, fontweight="bold", va="top", color=INK)

    ax = fig.add_axes([0.115, 0.200, 0.80, 0.300])
    y = list(range(len(kinds)))[::-1]
    ax.barh(y, vals, height=0.55, color=BLUE, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels(kinds, fontsize=16, color=INK)
    bar_axes(ax, max(vals) * 1.14)
    for yy, v in zip(y, vals):
        ax.text(v + max(vals) * 0.014, yy, fmt_int(v), va="center", ha="left",
                fontsize=15, color=INK_2)

    fig.text(L, 0.125,
             wrap(fig, u"Change %s from %s to %s and %s of these knobs vanish "
                       u"while %s different ones appear. The space does not "
                       u"just move — it changes shape."
                       % (top_var, config.get(top_var, "?"), best_val,
                          fmt_int(here), fmt_int(best_n)), 16, R - L),
             fontsize=16, va="top", color=INK_2, linespacing=1.45)
    fig.text(L, 0.048,
             "Live means every clause of the knob's depends column is "
             "satisfied by the configuration named above.",
             fontsize=13.5, va="top", color=MUTED)

    fig.savefig(out, dpi=DPI)
    plt.close(fig)
    return dict(n_live=n_live, by_kind=dict(counts),
                by_family=dict(Counter(live["family"])),
                swap=(top_var, here, best_val, best_n))


# =========================================================== figure four ====
def fig_size(df, out):
    fams = sorted(df["family"].unique(),
                  key=lambda f: -log10_configs(df[df["family"] == f]))
    vals = [log10_configs(df[df["family"] == f]) for f in fams]
    grand = log10_configs(df)
    n_real = int((df["kind"] == "real").sum())
    enums = df[df["kind"] == "enum"]
    n_enum = len(enums)
    n_stated = int((enums["n_values"].str.strip() != "").sum())

    fig = plt.figure(figsize=(14, 9.4), dpi=DPI)
    L, R = 0.05, 0.965

    fig.text(L, 0.968, "How big that makes the whole space", fontsize=30,
             fontweight="bold", va="top", color=INK)
    fig.text(L, 0.910,
             wrap(fig, "Give every knob a deliberately coarse number of "
                       "values and multiply.", 17, R - L),
             fontsize=17, va="top", color=INK_2, linespacing=1.4)

    base_fs, base_y = 84, 0.845
    fig.text(L, base_y, "10", fontsize=base_fs, fontweight="bold", va="top",
             color=INK)
    bw = fig_text_w(fig, "10", base_fs, "bold")
    exp = "%d" % round(grand)
    fig.text(L + bw + 0.005, base_y + 0.004, exp, fontsize=46,
             fontweight="bold", va="top", color=BLUE)
    ew = fig_text_w(fig, exp, 46, "bold")

    cap_x = L + bw + ew + 0.030
    fig.text(cap_x, 0.782,
             wrap(fig, "distinct configurations, under the assumptions at "
                       "the foot of this figure.", 18, R - cap_x),
             fontsize=18, va="center", color=INK, linespacing=1.45)
    fig.text(L, 0.690,
             wrap(fig, u"For scale: about 10⁸⁰ atoms in the "
                       u"observable universe, and 10⁶ evaluations in a "
                       u"very generous compute budget.", 16, R - L),
             fontsize=16, va="top", color=INK_2, linespacing=1.45)

    ax = fig.add_axes([0.125, 0.270, 0.795, 0.355])
    y = list(range(len(fams)))[::-1]
    cols = [ORANGE if f in HOST_FAMILIES else BLUE for f in fams]
    ax.barh(y, vals, height=0.55, color=cols, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels(fams, fontsize=15, color=INK)
    bar_axes(ax, max(vals) * 1.15 if vals else 1)
    ax.set_xlabel(u"log₁₀ of the configurations that family alone "
                  u"allows", fontsize=14.5, color=INK_2, labelpad=8)
    for yy, v in zip(y, vals):
        ax.text(v + max(vals) * 0.012, yy, "10$^{%d}$" % round(v),
                va="center", ha="left", fontsize=13.5, color=INK_2)
    if any(f in HOST_FAMILIES for f in fams):
        ax.legend(handles=[Line2D([], [], marker="s", ls="", ms=11,
                                  color=BLUE, label="solver library"),
                           Line2D([], [], marker="s", ls="", ms=11,
                                  color=ORANGE, label="calling code")],
                  loc="lower right", frameon=False, fontsize=14,
                  labelcolor=INK_2, handletextpad=0.5)

    assumed = ",  ".join("%s = %d" % (k, v)
                         for k, v in VALUES_PER_KIND.items() if v > 1)
    foot = ("Assumed values per knob:  %s.  Strings and arrays count as 1: "
            "they are not searched. Every knob is treated as independently "
            "settable, which the conditional structure says it is not, so "
            "this is the size of the box that contains the tree. %d of the "
            "%d enums state their choice count in the source and use it; the "
            "other %d are registered at run time, the source does not say, "
            "and they are assumed to offer %d. The %d real-valued knobs are "
            "each sampled at %d points; a real knob is an interval, not a "
            "list, so the true space is uncountable and this figure is a "
            "floor." % (assumed, n_stated, n_enum, n_enum - n_stated,
                        VALUES_PER_KIND["enum"], n_real,
                        VALUES_PER_KIND["real"]))
    fig.text(L, 0.165, wrap(fig, foot, 13.5, R - L), fontsize=13.5,
             va="top", color=MUTED, linespacing=1.55)

    fig.savefig(out, dpi=DPI)
    plt.close(fig)
    return dict(grand=grand, fams=list(zip(fams, vals)), n_real=n_real,
                n_enum=n_enum, n_stated=n_stated)


# ================================================================== main ====
def parse_config(text):
    cfg = OrderedDict()
    for part in text.split(","):
        part = part.strip()
        if part and "=" in part:
            k, _, v = part.partition("=")
            cfg[k.strip()] = v.strip()
    return cfg


def main():
    args = [a for a in sys.argv[1:]]
    config = None
    if "--config" in args:
        i = args.index("--config")
        config = parse_config(args[i + 1])
        del args[i:i + 2]
    if not args:
        raise SystemExit(__doc__)
    src = args[0]
    out_dir = args[1] if len(args) > 1 else os.path.dirname(
        os.path.abspath(src))
    os.makedirs(out_dir, exist_ok=True)

    df = load(src)
    r1 = fig_counts(df, os.path.join(out_dir, "1-knob-count.png"))
    r2 = fig_conditional(df, os.path.join(out_dir, "2-conditional.png"))
    r3 = fig_live(df, config, os.path.join(out_dir, "3-live-config.png")) \
        if config else None
    r4 = fig_size(df, os.path.join(out_dir, "4-space-size.png"))

    print("\nknobs: %d" % len(df))
    print("by kind: %s" % sorted(r1["by_kind"].items(), key=lambda t: -t[1]))
    print("by family: %s" % Counter(df["family"]).most_common())
    print("groups: %s" % [(l, n) for l, _, n, _ in r1["items"]])
    print("always present %d  gated %d  child blocks %d"
          % (r2["uncond"], r2["cond"], r2["n_children"]))
    print("gating parents: %s" % r2["by_var"])
    print("biggest single child block: %d" % r2["biggest"])
    if r3:
        print("live: %d  %s" % (r3["n_live"],
                                sorted(r3["by_kind"].items(),
                                       key=lambda t: -t[1])))
        print("live by family: %s" % sorted(r3["by_family"].items(),
                                            key=lambda t: -t[1]))
        print("swap: %s" % (r3["swap"],))
    print("log10 total: %.1f   reals %d   enums %d (%d stated)"
          % (r4["grand"], r4["n_real"], r4["n_enum"], r4["n_stated"]))
    for f, v in r4["fams"]:
        print("   %-14s 10^%.1f" % (f, v))


if __name__ == "__main__":
    main()
