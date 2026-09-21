#!/usr/bin/env python3
"""The solver-optimisation deck: its content, and two ways of drawing it.

    python deck/deck.py --pptx deck/design-summary.pptx
    python deck/deck.py --preview deck/preview

The slides are data, in SLIDES below, and the two renderers are thin. That is
so the deck can be looked at on a machine with no PowerPoint and no
LibreOffice: the preview draws the same layout with matplotlib. The preview is
a check on the layout, not a rendering of the file -- the fonts differ, so
treat a tight fit there as tight, not as proven.

python-pptx is not in the Spack environment and must not be installed into it.
Make a throwaway one instead:

    python -m venv --system-site-packages /tmp/deckenv
    /tmp/deckenv/bin/pip install python-pptx
    /tmp/deckenv/bin/python deck/deck.py --pptx deck/design-summary.pptx

The palette and the type are the figures', so a figure dropped on a slide does
not look like a visitor. A slide holding a figure carries nothing else: the
figure has its own title and its own footnote.

Every number here comes from snes-space.tsv by way of option-space.md. If the
inventory is rebuilt, the numbers on these slides must be checked against it.
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIGURES = os.path.join(HERE, "..", "figures")

W, H = 13.333, 7.5
M = 0.8

SURFACE = "fcfcfb"
INK = "0b0b0b"
INK_2 = "52514e"
MUTED = "898781"
TILE = "f3f2ee"
RULE = "d8d7d0"
BLUE = "2a78d6"
ORANGE = "eb6834"
PAPER = "ffffff"
PALE = "e4e2dc"

HEAD = "Calibri"
BODY = "Calibri"

# Aspect ratio of each figure, so one can be placed without distorting it.
ASPECT = {
    "1-knob-count.png": 3080 / 1760,
    "2-conditional.png": 3080 / 1936,
    "3-live-config.png": 3080 / 1803,
    "4-space-size.png": 3080 / 2068,
}


def text(x, y, w, h, body, size=15, colour=INK_2, bold=False, font=BODY,
         align="l", valign="t", spacing=1.2):
    return dict(kind="text", x=x, y=y, w=w, h=h, text=body, size=size,
                colour=colour, bold=bold, font=font, align=align,
                valign=valign, spacing=spacing)


def rect(x, y, w, h, fill, line=None, round=False):
    return dict(kind="rect", x=x, y=y, w=w, h=h, fill=fill,
                line=line or fill, round=round)


def line(x, y, w, h, colour=MUTED, width=1.5, arrow=None):
    return dict(kind="line", x=x, y=y, w=w, h=h, colour=colour, width=width,
                arrow=arrow)


def image(name, y, height):
    w = height * ASPECT[name]
    return dict(kind="image", path=os.path.join(FIGURES, name),
                x=(W - w) / 2, y=y, w=w, h=height)


def bullets(x, y, w, h, items, size=13.5, colour=INK_2):
    return dict(kind="bullets", x=x, y=y, w=w, h=h, items=items, size=size,
                colour=colour)


def title(head):
    return text(M, 0.5, W - 2 * M, 0.72, head, size=32, colour=INK, bold=True,
                font=HEAD)


def stat_tile(x, y, w, value, label, note, colour=INK):
    return [
        rect(x, y, w, 2.25, TILE),
        text(x + 0.24, y + 0.16, w - 0.48, 0.82, value, size=34, colour=colour,
             bold=True, font=HEAD),
        text(x + 0.24, y + 1.12, w - 0.48, 0.34, label, size=13, colour=INK,
             bold=True),
        text(x + 0.24, y + 1.55, w - 0.48, 0.5, note, size=11, colour=MUTED),
    ]


def figure_slide(name, notes):
    return dict(background=SURFACE, notes=notes,
                elements=[image(name, 0.3, H - 0.6)])


# --- the deck ---------------------------------------------------------------
SLIDES = []

SLIDES.append(dict(background=INK, elements=[
    text(M, 2.3, W - 2 * M - 0.8, 1.7,
         "Searching the settings of a slow simulation",
         size=42, colour=PAPER, bold=True, font=HEAD, spacing=1.05),
    text(M, 4.15, W - 2 * M, 0.6,
         "A plan for automatic tuning, and where to take it next",
         size=18, colour="b9b7b0"),
    rect(M, 5.05, 1.5, 0.07, BLUE),
]))

_tile_w = (W - 2 * M - 0.5) / 3
SLIDES.append(dict(background=SURFACE, elements=[
    title("What the code does, and what it costs"),
    text(M, 1.55, W - 2 * M, 1.1,
         "A fusion reactor holds plasma at over a hundred million degrees. The "
         "exhaust leaving that plasma has to be cooled on its way out, or it "
         "destroys the metal wall it lands on. This code predicts whether a "
         "given reactor design manages that.", size=15),
    text(M, 3.05, W - 2 * M, 0.34,
         "Simulating a tenth of a second of plasma, on ten cores:",
         size=13, colour=MUTED),
    *stat_tile(M, 3.55, _tile_w, "~1 hour", "a smaller production case",
               "the cheapest thing worth running"),
    *stat_tile(M + _tile_w + 0.25, 3.55, _tile_w, "10s of hours",
               "a large case at full resolution", "the ones the science needs",
               colour=BLUE),
    *stat_tile(M + 2 * (_tile_w + 0.25), 3.55, _tile_w, "tens",
               "cases in a single study", "multiply by the row above"),
    text(M, 6.35, W - 2 * M, 0.5,
         "The speed of the code decides which questions can be asked at all.",
         size=15, colour=INK, bold=True),
]))

SLIDES.append(figure_slide(
    "1-knob-count.png",
    "865 tuning knobs across 850 distinct names, counted from the source that "
    "registers each option rather than from a manual. A further 66 options are "
    "monitors and views, which do not change the answer and are left out."))

SLIDES.append(figure_slide(
    "2-conditional.png",
    "Only 186 of the 865 exist unconditionally. One preconditioner choice "
    "decides whether 392 of them exist at all."))

SLIDES.append(figure_slide(
    "3-live-config.png",
    "The configuration in production today. 327 knobs are live in it, and the "
    "settings file we maintain describes 66 of those."))

SLIDES.append(figure_slide(
    "4-space-size.png",
    "A floor, not a size. A continuous knob is an interval rather than a list, "
    "and this treats every knob as independently settable, which the "
    "conditional structure says it is not."))

_rows = [
    ("hours", "One evaluation is expensive",
     "so the number of trials will be small, and a method that needs thousands "
     "of them is out.", BLUE),
    ("noisy", "The same settings run twice do not agree",
     "the measurement has spread, so a difference of a few per cent means "
     "nothing.", BLUE),
    ("wrong", "Fast can mean wrong",
     "a setting can be quick because it is cutting corners. Speed alone cannot "
     "be the score.", ORANGE),
    ("failed", "A failure is a result",
     "some settings make a run die or never finish. That is information, not a "
     "missing number.", BLUE),
]
_elements = [title("Why this is not ordinary tuning")]
_y = 1.75
for _tag, _head, _text, _colour in _rows:
    _elements += [
        rect(M, _y, 1.35, 0.5, _colour),
        text(M, _y, 1.35, 0.5, _tag, size=12.5, colour=PAPER, bold=True,
             align="c", valign="m"),
        text(M + 1.65, _y - 0.03, W - 2 * M - 1.65, 0.36, _head, size=16,
             colour=INK, bold=True),
        text(M + 1.65, _y + 0.36, W - 2 * M - 1.65, 0.56, _text, size=13,
             colour=INK_2, spacing=1.15),
    ]
    _y += 1.38
SLIDES.append(dict(background=SURFACE, elements=_elements))

_x0 = M + 2.3
_bar = W - _x0 - M - 1.25
_slices = [0.06, 0.42, 0.76]
_elements = [
    title("Testing on a slice, not a whole run"),
    text(_x0, 1.78, _bar, 0.3,
         "one long reference run, saving its state throughout",
         size=12, colour=MUTED),
    rect(_x0, 2.16, _bar, 0.52, TILE, line=RULE),
]
for _f in _slices:
    _elements.append(rect(_x0 + _f * _bar, 2.16, 0.3, 0.52, BLUE))
# A dashed drop from each slice to the rungs, so the rungs are visibly the
# same three positions and not three unrelated rows.
for _f in _slices:
    _elements.append(line(_x0 + _f * _bar + 0.15, 2.72, 0, 3.0,
                          colour="c7d9f2", width=1))
_y = 3.55
for _label, _width, _cost in [("screen many", 0.3, "seconds"),
                              ("test survivors", 1.15, "minutes"),
                              ("confirm finalists", None, "hours")]:
    _elements += [
        text(M, _y - 0.05, 2.1, 0.34, _label, size=13, colour=INK, align="r"),
        line(_x0, _y + 0.14, _bar, 0, colour="e1e0d9", width=1),
    ]
    if _width is None:
        _elements.append(rect(_x0, _y, _bar, 0.28, BLUE))
    else:
        for _f in _slices:
            _elements.append(rect(_x0 + _f * _bar, _y, _width, 0.28, BLUE))
    _elements.append(text(_x0 + _bar + 0.22, _y - 0.05, 1.0, 0.34, _cost,
                          size=12, colour=MUTED))
    _y += 1.0
_elements.append(text(
    M, 6.4, W - 2 * M, 1.0,
    "A slice restarts from a saved state and runs a short way. Several "
    "positions, because the simulation is hard in different ways at different "
    "stages. Cheap slices screen many candidates; only the survivors pay for "
    "the longer ones.", size=13.5))
SLIDES.append(dict(background=SURFACE, elements=_elements))

_boxes = [("Optimiser", "decides what to try next"),
          ("Runner", "prepares, launches, watches, measures"),
          ("Record", "one row per run, plus its evidence")]
_bw, _bh, _gap = 3.3, 1.45, 1.0
_start = (W - (3 * _bw + 2 * _gap)) / 2
_elements = [title("The system")]
for _i, (_head, _note) in enumerate(_boxes):
    _x = _start + _i * (_bw + _gap)
    _elements += [
        rect(_x, 2.0, _bw, _bh, TILE, line=RULE, round=True),
        text(_x + 0.15, 2.2, _bw - 0.3, 0.36, _head, size=16, colour=INK,
             bold=True, font=HEAD, align="c"),
        text(_x + 0.18, 2.66, _bw - 0.36, 0.72, _note, size=12.5,
             colour=INK_2, align="c", spacing=1.1),
    ]
    if _i < 2:
        _elements += [
            line(_x + _bw + 0.14, 2.8, _gap - 0.28, 0, arrow="end"),
            text(_x + _bw + 0.14, 2.24, _gap - 0.28, 0.4,
                 "a list of trials" if _i == 0 else "what happened",
                 size=9.5, colour=MUTED, align="c"),
        ]
_left = _start + _bw / 2
_right = _start + 2 * (_bw + _gap) + _bw / 2
_elements += [
    line(_right, 3.6, 0, 0.55),
    line(_left, 4.15, _right - _left, 0),
    line(_left, 3.6, 0, 0.55, arrow="start"),
    text(_left, 4.2, _right - _left, 0.3, "past results, as a short table",
         size=10, colour=MUTED, align="c"),
    bullets(M, 5.0, W - 2 * M, 2.2, [
        "The runner has no judgement in it, so it runs unattended, anywhere.",
        "The optimiser can be an algorithm, a language model, or a person "
        "writing a list. The runner cannot tell the difference, so it can be "
        "swapped without touching anything else.",
        "Speed and correctness are recorded side by side, never combined, so "
        "nothing can trade accuracy for time.",
    ]),
]
SLIDES.append(dict(background=SURFACE, elements=_elements))

_col = (W - 2 * M - 0.7) / 2
SLIDES.append(dict(background=SURFACE, elements=[
    title("What exists, and what does not"),
    text(M, 1.65, _col, 0.36, "Built and working", size=17, colour=BLUE,
         bold=True, font=HEAD),
    bullets(M, 2.25, _col, 4.6, [
        "Measurement. A finished run turns automatically into one row of "
        "numbers and a bundle of evidence.",
        "The record. One row per run, added to and never rewritten.",
        "Reference runs for three cases, with their saved states.",
        "The tool that cuts a slice and sets it up as a run.",
        "The loop itself. A four-trial campaign has been generated, run, "
        "measured and recorded with nobody watching.",
    ], size=14),
    text(M + _col + 0.7, 1.65, _col, 0.36, "Not built", size=17, colour=ORANGE,
         bold=True, font=HEAD),
    bullets(M + _col + 0.7, 2.25, _col, 3.4, [
        "Any optimiser at all. Every trial so far was a list written by hand.",
        "Any evidence that a slice predicts a full run.",
        "A description of more than a fifth of the settings that are live.",
    ], size=14),
]))

_questions = [
    "Does a slice predict a full run, and how should that be checked before it "
    "is trusted?",
    "What search method suits 865 mixed settings, most of which exist only "
    "when another setting has a particular value?",
    "Where, if anywhere, does a language model belong in the loop?",
    "How should a run that fails, or never finishes, be scored?",
]
_elements = [text(M, 0.9, W - 2 * M, 0.72, "What to work on together",
                  size=32, colour=PAPER, bold=True, font=HEAD)]
_y = 2.35
for _i, _q in enumerate(_questions):
    _elements += [
        text(M, _y - 0.03, 0.5, 0.4, str(_i + 1), size=18, colour=BLUE,
             bold=True, font=HEAD),
        text(M + 0.6, _y - 0.04, W - 2 * M - 0.6, 0.8, _q, size=16,
             colour=PALE, spacing=1.2),
    ]
    _y += 1.18
SLIDES.append(dict(background=INK, elements=_elements))


# --- renderers --------------------------------------------------------------
def write_pptx(out):
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.oxml.ns import qn

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
                    MSO_SHAPE.ROUNDED_RECTANGLE if element["round"]
                    else MSO_SHAPE.RECTANGLE,
                    Inches(element["x"]), Inches(element["y"]),
                    Inches(element["w"]), Inches(element["h"]))
                shape.fill.solid()
                shape.fill.fore_color.rgb = rgb(element["fill"])
                shape.line.color.rgb = rgb(element["line"])
                shape.line.width = Pt(0.75)
                shape.shadow.inherit = False
                if element["round"]:
                    shape.adjustments[0] = 0.08
                shape.text_frame.text = ""
            elif kind == "line":
                shape = slide.shapes.add_shape(
                    MSO_SHAPE.RECTANGLE,
                    Inches(element["x"]),
                    Inches(element["y"] - 0.008),
                    Inches(max(element["w"], 0.016)),
                    Inches(max(element["h"], 0.016)))
                shape.fill.solid()
                shape.fill.fore_color.rgb = rgb(element["colour"])
                shape.line.fill.background()
                shape.shadow.inherit = False
            elif kind == "image":
                slide.shapes.add_picture(
                    element["path"], Inches(element["x"]), Inches(element["y"]),
                    Inches(element["w"]), Inches(element["h"]))
            elif kind in ("text", "bullets"):
                box = slide.shapes.add_textbox(
                    Inches(element["x"]), Inches(element["y"]),
                    Inches(element["w"]), Inches(element["h"]))
                frame = box.text_frame
                frame.word_wrap = True
                frame.margin_left = frame.margin_right = 0
                frame.margin_top = frame.margin_bottom = 0
                items = ([element["text"]] if kind == "text"
                         else element["items"])
                for index, item in enumerate(items):
                    para = frame.paragraphs[0] if index == 0 else \
                        frame.add_paragraph()
                    if kind == "bullets":
                        properties = para._p.get_or_add_pPr()
                        properties.set("marL", "171450")
                        properties.set("indent", "-171450")
                        char = properties.makeelement(qn("a:buChar"), {})
                        char.set("char", "•")
                        properties.append(char)
                        para.space_after = Pt(9)
                        para.line_spacing = 1.2
                    else:
                        para.alignment = ALIGN[element["align"]]
                        para.line_spacing = element["spacing"]
                    run = para.add_run()
                    run.text = item
                    run.font.name = element.get("font", BODY)
                    run.font.size = Pt(element["size"])
                    run.font.bold = element.get("bold", False)
                    run.font.color.rgb = rgb(element["colour"])
                if kind == "text":
                    frame.vertical_anchor = ANCHOR[element["valign"]]
        if spec.get("notes"):
            slide.notes_slide.notes_text_frame.text = spec["notes"]

    pres.save(out)
    print(f"wrote {out} ({len(SLIDES)} slides)")


def write_preview(out_dir):
    """One PNG per slide, to be looked at."""

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(out_dir, exist_ok=True)
    for number, spec in enumerate(SLIDES, start=1):
        figure = _draw(spec)
        path = os.path.join(out_dir, f"slide-{number}.png")
        figure.savefig(path, dpi=110)
        plt.close(figure)
        print(f"wrote {path}")


def _draw(spec):
    """One slide drawn with matplotlib. Returns the figure."""

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, FancyBboxPatch, FancyArrow
    import matplotlib.image as mpimg

    align = {"l": "left", "c": "center", "r": "right"}

    fig = plt.figure(figsize=(W, H), dpi=110)
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
        elif kind == "line":
            if element["arrow"]:
                forward = element["arrow"] == "end"
                dx = element["w"] if forward else -element["w"]
                dy = element["h"] if forward else -element["h"]
                x = element["x"] if forward else element["x"] + element["w"]
                y = element["y"] if forward else element["y"] + element["h"]
                ax.add_patch(FancyArrow(
                    x, y, dx, dy, width=0.012, head_width=0.09,
                    head_length=0.12, length_includes_head=True,
                    color="#" + element["colour"], zorder=2))
            else:
                # Under the blocks it separates, never across them.
                ax.plot([element["x"], element["x"] + element["w"]],
                        [element["y"], element["y"] + element["h"]],
                        color="#" + element["colour"],
                        linewidth=element["width"], zorder=1)
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
        elif kind == "bullets":
            y = element["y"] + 0.06
            for item in element["items"]:
                wrapped = _wrap(item, element["w"] - 0.25, element["size"])
                ax.text(element["x"], y, "•", fontsize=element["size"],
                        color="#" + element["colour"], va="top", zorder=4)
                ax.text(element["x"] + 0.25, y, wrapped,
                        fontsize=element["size"] * 0.98,
                        color="#" + element["colour"], va="top",
                        linespacing=1.45, zorder=4)
                y += 0.32 + 0.26 * wrapped.count("\n") + 0.12

    return fig


def write_pdf(out):
    """The deck as one PDF, drawn by the same code as the preview."""

    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.backends.backend_pdf import PdfPages

    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    with PdfPages(out) as pdf:
        for spec in SLIDES:
            pdf.savefig(_draw(spec))
    print(f"wrote {out} ({len(SLIDES)} slides)")


def _wrap(s, width_inches, size, bold=False):
    """Break text to a width, using a rough advance per character."""

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
