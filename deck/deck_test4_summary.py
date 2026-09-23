#!/usr/bin/env python3
"""Build the 4-slide test4 hackathon summary presentation.

Generates PowerPoint (.pptx), PDF (.pdf), and preview PNGs:
- Slide 1: The Solver Parameter Space (865 knobs)
- Slide 2: test4 Optimisation Flow & Architecture (infographic)
- Slide 3: Study S01: Jacobian Lag Screening (Figure B.2 from S01)
- Slide 4: Study S03: Layered Options & Controller Gains (Figure B.2 from S03)

Usage:
    /tmp/deckenv/bin/python deck/deck_test4_summary.py --pptx deck/test4-summary.pptx --pdf deck/test4-summary.pdf
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIGURES = os.path.join(ROOT, "figures")

W, H = 13.333, 7.5
M = 0.8

SURFACE = "fcfcfb"
INK = "0b0b0b"
INK_2 = "403f3c"
MUTED = "73716b"
TILE = "f5f4ee"
RULE = "d8d7d0"
BLUE = "1a66c2"
ORANGE = "c84714"
GREEN = "138a5a"
PURPLE = "6a3db5"
PAPER = "ffffff"

HEAD = "Calibri"
BODY = "Calibri"

ASPECT = {
    "1-knob-count.png": 3080 / 1760,
    "test4-opt-flow.png": 3520 / 1980,
    "s01-overview.png": 2835 / 1260,
    "s03-overview.png": 2835 / 1575,
}


def text(x, y, w, h, body, size=15, colour=INK_2, bold=False, font=BODY,
         align="l", valign="t", spacing=1.2):
    return dict(kind="text", x=x, y=y, w=w, h=h, text=body, size=size,
                colour=colour, bold=bold, font=font, align=align,
                valign=valign, spacing=spacing)


def rect(x, y, w, h, fill, line=None, round=False):
    return dict(kind="rect", x=x, y=y, w=w, h=h, fill=fill,
                line=line or fill, round=round)


def image_fit(name, max_x, max_y, max_w, max_h):
    aspect = ASPECT[name]
    if max_w / max_h > aspect:
        h = max_h
        w = h * aspect
    else:
        w = max_w
        h = w / aspect
    x = max_x + (max_w - w) / 2
    y = max_y + (max_h - h) / 2
    return dict(kind="image", path=os.path.join(FIGURES, name),
                x=x, y=y, w=w, h=h)


# =============================================================================
# SLIDES DEFINITION
# =============================================================================
SLIDES = []

# -----------------------------------------------------------------------------
# SLIDE 1: The Solver Parameter Space (Figure 1)
# -----------------------------------------------------------------------------
SLIDES.append(dict(
    background=SURFACE,
    notes=(
        "Hermes-3 simulates plasma transport in the edge region of fusion reactors, "
        "modelling how hot exhaust gas is cooled before touching divertor walls.\n\n"
        "The underlying PETSc nonlinear solver stack exposes 865 tunable parameters — "
        "comprising boolean flags, discrete choices, continuous tolerances, and algorithm selectors. "
        "831 of these define a vast combinatorial space of potential solver configurations.\n\n"
        "Historically, fusion simulations have relied on hand-tuned, conservative defaults "
        "dating back years. Manual tuning in an 865-dimensional space is impossible.\n\n"
        "To systematically unlock simulation throughput without sacrificing physics accuracy, "
        "we designed an automated, evidence-based exploration framework."
    ),
    elements=[
        image_fit("1-knob-count.png", 0.4, 0.3, W - 0.8, H - 0.6)
    ]
))

# -----------------------------------------------------------------------------
# SLIDE 2: test4 Optimisation Flow & Architecture (Infographic)
# -----------------------------------------------------------------------------
SLIDES.append(dict(
    background=SURFACE,
    notes=(
        "This slide presents the core architecture and optimisation methodology developed during "
        "the hackathon, applied to the test4-jacobian campaign.\n\n"
        "1. Three-Tier Storage: We cleanly decouple the public automation framework (hermes-solver-opt) "
        "from the immutable private evidence store (solver-opt-store) and the transient simulation "
        "working directories ($data/cases/). Raw simulation dumps (~1 GB each) are pruned promptly "
        "after diagnostic extraction.\n\n"
        "2. Multi-Rung Evaluation Ladder: Full 100 ms simulations take up to 17 hours. We designed "
        "a multi-rung ladder where Rung 0 screens dozens of candidates on fast 200-second slices. "
        "Survivors advance to Rung 1 (1000-second intermediate windows) to test stability, and only top "
        "finalists run full 100 ms simulations on Rung 2.\n\n"
        "3. Strict Noise & Repeat Control: On the stiff 2.65 ms transient cliff, numerical path "
        "bifurcations produce up to 15% run-to-run variation. Every cell is sampled across 3 to 10 repeats, "
        "and no speedup claim is accepted unless it strictly clears repeat noise.\n\n"
        "4. Studies, Investigations & Promotion Gates: Hypotheses are structured into numbered studies "
        "(S01, S02, S03) and deep-dive investigations (I01, I02). Candidate settings must pass a 3-part gate: "
        "physics agreement (<0.04% profile deviation), noise clearance, and cross-rung consistency. "
        "Promoted findings are committed to durable findings logs and graduate back into default solver recipes."
    ),
    elements=[
        image_fit("test4-opt-flow.png", 0.4, 0.3, W - 0.8, H - 0.6)
    ]
))

# -----------------------------------------------------------------------------
# SLIDE 3: Study S01: Jacobian Lag Screening (Figure B.2 from S01)
# -----------------------------------------------------------------------------
SLIDES.append(dict(
    background=SURFACE,
    notes=(
        "Study S01 screened 22 candidate solver configurations across 167 runs using our "
        "multi-rung ladder, focusing on the Jacobian lag parameter.\n\n"
        "For years, standard practice assumed that lagging the Jacobian matrix — rebuilding it only "
        "every 3 nonlinear steps (lag 3) — saved time by amortising expensive numerical matrix assemblies.\n\n"
        "Our data completely overturned this dogma: updating the Jacobian at every step (lag 1) converges "
        "significantly faster per Newton iteration, easily compensating for assembly cost.\n\n"
        "Results: Lag 1 achieved 1.8x speedup on Rung 0, 1.3x–1.4x on Rung 1, and 1.8x on the full "
        "simulation (Rung 2). Crucially, during the stiff 2.0–3.0 ms cliff window, lag 1 was 5.6x faster.\n\n"
        "Physics verification: Separatrix and divertor target profiles matched the baseline to within "
        "<0.04% relative error, confirming that this 1.8x speedup comes with zero loss of scientific fidelity."
    ),
    elements=[
        text(M, 0.40, W - 2 * M, 0.50,
             "Study S01: Jacobian Lag Screening",
             size=24, colour=INK, bold=True, font=HEAD),
        text(M, 0.90, W - 2 * M, 0.35,
             "Overturning production dogma: updating the Jacobian every step (lag 1) beats default lag 3 by 1.3x–2.6x with <0.04% physics error",
             size=12, colour=MUTED, font=BODY),
        image_fit("s01-overview.png", M, 1.35, W - 2 * M, H - 1.65)
    ]
))

# -----------------------------------------------------------------------------
# SLIDE 4: Study S03: Layered Options & Controller Gains (Figure B.2 from S03)
# -----------------------------------------------------------------------------
SLIDES.append(dict(
    background=SURFACE,
    notes=(
        "Study S03 investigated whether we could compound our S01 gains by tuning the PETSc adaptive "
        "timestep controller across 898 runs.\n\n"
        "We discovered that the default PI controller was excessively conservative following difficult "
        "nonlinear steps, needlessly throttling the timestep during the stiff 2–6 ms transient.\n\n"
        "By pairing lag 1 with tuned controller gains (kI=0.3, kP=0.7) and modified failure backoff, "
        "the simulation accelerates dramatically across all rungs:\n\n"
        "• On the 2–3 ms transient cliff (tested across 10 repeats), the tuned recipe delivered 10x to 16x speedup.\n"
        "• On Rung 1 slices, speedup reached up to 26x over baseline.\n"
        "• On the full 0–100 ms simulation (Rung 2), the compounded recipe delivered a 2.5x to 2.9x reduction in wall-clock time.\n\n"
        "This translates directly to scientific productivity: multi-day production divertor simulations "
        "finish in a fraction of the time, while preserving exact profile agreement at divertor targets."
    ),
    elements=[
        text(M, 0.40, W - 2 * M, 0.50,
             "Study S03: Layered Options & Controller Gains",
             size=24, colour=INK, bold=True, font=HEAD),
        text(M, 0.90, W - 2 * M, 0.35,
             "Compounding wins: pairing lag 1 with tuned PID controller gains yields up to 26x transient speedup and 2.5x full-run win",
             size=12, colour=MUTED, font=BODY),
        image_fit("s03-overview.png", M, 1.35, W - 2 * M, H - 1.65)
    ]
))


# =============================================================================
# PPTX & PDF GENERATION
# =============================================================================
def write_pptx(out):
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.enum.shapes import MSO_SHAPE

    def rgb(value):
        return RGBColor.from_string(value.upper())

    ALIGN = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}
    ANCHOR = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE}

    pres = Presentation()
    pres.slide_width = Inches(W)
    pres.slide_height = Inches(H)
    blank = pres.slide_layouts[6]

    for spec in SLIDES:
        slide = pres.slides.add_slide(blank)
        fill = slide.background.fill
        fill.solid()
        fill.fore_color.rgb = rgb(spec["background"])

        for element in spec["elements"]:
            kind = element["kind"]
            if kind == "rect":
                shape = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE if element["round"] else MSO_SHAPE.RECTANGLE,
                    Inches(element["x"]), Inches(element["y"]),
                    Inches(element["w"]), Inches(element["h"]))
                shape.fill.solid()
                shape.fill.fore_color.rgb = rgb(element["fill"])
                shape.line.color.rgb = rgb(element["line"])
                shape.line.width = Pt(0.75)
                shape.shadow.inherit = False
                shape.text_frame.text = ""
            elif kind == "image":
                slide.shapes.add_picture(
                    element["path"], Inches(element["x"]), Inches(element["y"]),
                    Inches(element["w"]), Inches(element["h"]))
            elif kind == "text":
                box = slide.shapes.add_textbox(
                    Inches(element["x"]), Inches(element["y"]),
                    Inches(element["w"]), Inches(element["h"]))
                frame = box.text_frame
                frame.word_wrap = True
                frame.margin_left = frame.margin_right = 0
                frame.margin_top = frame.margin_bottom = 0
                para = frame.paragraphs[0]
                para.alignment = ALIGN[element["align"]]
                para.line_spacing = element["spacing"]
                run = para.add_run()
                run.text = element["text"]
                run.font.name = element.get("font", BODY)
                run.font.size = Pt(element["size"])
                run.font.bold = element.get("bold", False)
                run.font.color.rgb = rgb(element["colour"])
                frame.vertical_anchor = ANCHOR[element["valign"]]

        if spec.get("notes"):
            slide.notes_slide.notes_text_frame.text = spec["notes"]

    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    pres.save(out)
    print(f"wrote PowerPoint presentation: {out} ({len(SLIDES)} slides)")


def _wrap(s, width_inches, size, bold=False):
    per_char = size / 72.0 * (0.50 if bold else 0.47)
    limit = max(int(width_inches / per_char), 8)
    out, line_ = [], ""
    for word in s.split():
        trial = (line_ + " " + word).strip()
        if len(trial) <= limit or not line_:
            line_ = trial
        else:
            out.append(line_)
            line_ = word
    out.append(line_)
    return "\n".join(out)


def _draw(spec):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, FancyBboxPatch
    import matplotlib.image as mpimg

    align = {"l": "left", "c": "center", "r": "right"}

    fig = plt.figure(figsize=(W, H), dpi=140)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.axis("off")
    ax.add_patch(Rectangle((0, 0), W, H, color="#" + spec["background"]))

    for element in spec["elements"]:
        kind = element["kind"]
        if kind == "rect":
            shape = (FancyBboxPatch(
                (element["x"] + 0.08, element["y"] + 0.08),
                element["w"] - 0.16, element["h"] - 0.16,
                boxstyle="round,pad=0.08,rounding_size=0.1")
                if element["round"] else
                Rectangle((element["x"], element["y"]),
                          element["w"], element["h"]))
            shape.set_facecolor("#" + element["fill"])
            shape.set_edgecolor("#" + element["line"])
            shape.set_linewidth(0.8)
            shape.set_zorder(2)
            ax.add_patch(shape)
        elif kind == "image":
            ax.imshow(mpimg.imread(element["path"]),
                      extent=(element["x"], element["x"] + element["w"],
                              element["y"] + element["h"], element["y"]),
                      aspect="auto", zorder=3)
        elif kind == "text":
            x = {"l": element["x"], "c": element["x"] + element["w"] / 2,
                 "r": element["x"] + element["w"]}[element["align"]]
            y = (element["y"] + element["h"] / 2
                 if element["valign"] == "m" else element["y"] + 0.06)
            ax.text(x, y, _wrap(element["text"], element["w"],
                                element["size"], element.get("bold")),
                    ha=align[element["align"]],
                    va="center" if element["valign"] == "m" else "top",
                    fontsize=element["size"] * 0.98,
                    fontweight="bold" if element.get("bold") else "normal",
                    color="#" + element["colour"],
                    linespacing=element["spacing"] * 1.15, zorder=4)

    return fig


def write_preview(out_dir):
    import matplotlib.pyplot as plt
    os.makedirs(out_dir, exist_ok=True)
    for number, spec in enumerate(SLIDES, start=1):
        figure = _draw(spec)
        path = os.path.join(out_dir, f"slide-{number}.png")
        figure.savefig(path, dpi=140)
        plt.close(figure)
        print(f"wrote preview image: {path}")


def write_pdf(out):
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.backends.backend_pdf import PdfPages

    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    with PdfPages(out) as pdf:
        for spec in SLIDES:
            figure = _draw(spec)
            pdf.savefig(figure)
            import matplotlib.pyplot as plt
            plt.close(figure)
    print(f"wrote PDF deck: {out} ({len(SLIDES)} slides)")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pdf", help="write the deck as one PDF here")
    parser.add_argument("--pptx", help="write the PowerPoint file here")
    parser.add_argument("--preview", help="write one PNG per slide here")
    args = parser.parse_args()
    if not (args.pdf or args.pptx or args.preview):
        parser.error("give --pdf, --pptx or --preview")
    if args.preview:
        write_preview(args.preview)
    if args.pdf:
        write_pdf(args.pdf)
    if args.pptx:
        write_pptx(args.pptx)
    return 0


if __name__ == "__main__":
    sys.exit(main())
