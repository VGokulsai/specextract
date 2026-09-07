"""Read a website's design system out of the browser and write it down.

Reading a page's CSS file tells you almost nothing now: it is minified, or it
is a thousand utility classes, or the numbers are in variables three files
away. The only place the real values exist is the browser, after it has
resolved everything - so that is where the measuring has to happen.

No headless browser, no Playwright, no npm. Two steps and a copy-paste:

    py -3 spec.py --probe > probe.js     the measuring script
    ...paste it into the site's DevTools console (F12), copy the output...
    py -3 spec.py measured.json          writes REFERENCE.md

The probe reads computed styles, which is what the page actually renders, not
what its stylesheet claims. That difference is the whole point: a screenshot
lets you guess the tracking, this reports it.

`measured.json` can also be `-` to read the paste from stdin. If DevTools'
own return-value string got copied in after the JSON blob (an easy mistake -
console.log's output and the script's return value both print), that trailing
text is ignored rather than treated as a syntax error. Pass `--stats` to also
print the summary counts as JSON, or `--no-summary` to leave the rollups out
of REFERENCE.md.
"""

import argparse
import collections
import io
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VERSION = "0.2.0"

PROBE = r"""
/* Paste into the DevTools console on the page you want to measure.
   It prints one JSON blob. Copy all of it into a file and run:
       py -3 spec.py that-file.json                                        */
(() => {
  const css = (el) => getComputedStyle(el);
  const seen = new Map();

  // One row per distinct combination, not per element: a page has thousands
  // of elements and about nine typographic decisions.
  document.querySelectorAll("h1,h2,h3,h4,p,a,li,button,span,code").forEach((el) => {
    const t = (el.textContent || "").trim();
    if (!t || el.children.length > 2) return;
    const c = css(el);
    const key = [c.fontSize, c.fontWeight, c.letterSpacing, c.lineHeight,
                 c.fontFamily.split(",")[0]].join("|");
    if (seen.has(key)) return;
    seen.set(key, { tag: el.tagName, size: c.fontSize, weight: c.fontWeight,
                    tracking: c.letterSpacing, leading: c.lineHeight,
                    color: c.color, font: c.fontFamily.split(",")[0].trim(),
                    sample: t.slice(0, 40) });
  });

  const tally = (values) => {
    const n = {};
    values.forEach((v) => { n[v] = (n[v] || 0) + 1; });
    return Object.entries(n).sort((a, b) => b[1] - a[1]).slice(0, 10);
  };

  const radii = [], transitions = [], widths = [], pads = [], gradients = [];
  document.querySelectorAll("*").forEach((el) => {
    const c = css(el);
    if (c.borderRadius && c.borderRadius !== "0px") radii.push(c.borderRadius);
    if (c.transition && c.transition !== "all 0s ease 0s") transitions.push(c.transition);
    if (c.maxWidth && c.maxWidth !== "none") widths.push(c.maxWidth);
    if (c.backgroundImage && c.backgroundImage.includes("gradient"))
      gradients.push(c.backgroundImage.slice(0, 120));
  });
  document.querySelectorAll("section,main>div,header,footer").forEach((el) => {
    const c = css(el);
    if (c.paddingTop !== "0px") pads.push(c.paddingTop + " / " + c.paddingLeft);
  });

  const vars = {};
  for (const sheet of document.styleSheets) {
    let rules; try { rules = sheet.cssRules; } catch (e) { continue; }
    for (const r of rules || []) {
      if (r.selectorText && /(^|,\s*):root/.test(r.selectorText)) {
        for (const p of r.style) if (p.startsWith("--"))
          vars[p] = r.style.getPropertyValue(p).trim();
      }
    }
  }

  const body = css(document.body);
  const out = {
    url: location.href,
    title: document.title,
    page: { background: body.backgroundColor, color: body.color,
            font: body.fontFamily.split(",")[0].trim(),
            size: body.fontSize, leading: body.lineHeight },
    type: [...seen.values()].sort((a, b) => parseFloat(b.size) - parseFloat(a.size)),
    radii: tally(radii),
    transitions: tally(transitions),
    maxWidths: tally(widths),
    sectionPadding: tally(pads),
    gradients: { count: gradients.length, sample: gradients[0] || "" },
    variableCount: Object.keys(vars).length,
    height: document.body.scrollHeight,
    sections: document.querySelectorAll("section").length,
  };
  console.log(JSON.stringify(out, null, 1));
  return "copy the JSON above into a file, then: py -3 spec.py that-file.json";
})();
"""


def px(value):
    try:
        return float(str(value).replace("px", ""))
    except Exception:
        return None


def em(size, tracking):
    """Tracking in em, which is the number that transfers. -2.4px means
    nothing until you know it was measured at 48px."""
    a, b = px(size), px(tracking)
    if not a or b is None:
        return ""
    return "%+.3fem" % (b / a)


def esc_cell(value):
    """A gradient sample or a font name can contain a literal '|' or a
    newline; either one silently breaks a markdown table if not escaped."""
    text = str(value)
    text = text.replace("|", "\\|")
    text = " ".join(text.split())
    return text


def table(rows, header):
    out = ["| " + " | ".join(header) + " |",
           "|" + "|".join(["---"] * len(header)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(esc_cell(c) for c in row) + " |")
    return "\n".join(out)


def clean_json_text(text):
    """Undo the paste artifacts DevTools consoles actually produce, before
    handing the result to the JSON parser."""
    text = text.lstrip("﻿")
    # Some terminals/consoles prefix wrapped or replayed lines with "> ".
    lines = text.splitlines()
    if lines and all(line.startswith("> ") or not line.strip() for line in lines
                      if line.strip()):
        lines = [line[2:] if line.startswith("> ") else line for line in lines]
        text = "\n".join(lines)
    return text


def parse_measured(raw):
    """Parse the probe's pasted output. Raises ValueError with a message
    meant to be shown directly to the person who pasted it."""
    text = clean_json_text(raw)
    if not text.strip():
        raise ValueError("the file is empty")

    decoder = json.JSONDecoder()
    stripped = text.lstrip()
    try:
        data, end = decoder.raw_decode(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError("not valid JSON (line %d, column %d): %s"
                          % (exc.lineno, exc.colno, exc.msg))

    # raw_decode stops at the end of the first JSON value and ignores
    # whatever comes after - which is exactly what you want when the
    # probe's own return-value string ("copy the JSON above...") got
    # copied into the file along with the console.log output above it.

    if not isinstance(data, dict):
        raise ValueError("expected a JSON object ({...}) but got %s - paste"
                          " the probe's output including the outer braces"
                          % type(data).__name__)
    return data


def normalize(data):
    """Coerce fields to the shapes render() expects, so a hand-edited or
    partially-pasted measurement degrades gracefully instead of crashing."""
    out = dict(data)

    type_list = out.get("type")
    if not isinstance(type_list, list):
        type_list = []
    out["type"] = [e for e in type_list if isinstance(e, dict)]

    for key in ("radii", "transitions", "maxWidths", "sectionPadding"):
        pairs = out.get(key)
        clean = []
        if isinstance(pairs, list):
            for item in pairs:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    clean.append((item[0], item[1]))
        out[key] = clean

    if not isinstance(out.get("page"), dict):
        out["page"] = {}
    if not isinstance(out.get("gradients"), dict):
        out["gradients"] = {}

    try:
        out["variableCount"] = int(out.get("variableCount") or 0)
    except (TypeError, ValueError):
        out["variableCount"] = 0

    return out


def palette(data):
    """Distinct colors seen on the page - the body and every type row -
    tallied by how often each one turns up, most common first."""
    counts = collections.Counter()
    page = data.get("page") or {}
    for key in ("background", "color"):
        value = page.get(key)
        if value:
            counts[value] += 1
    for entry in data.get("type") or []:
        value = entry.get("color")
        if value:
            counts[value] += 1
    return counts.most_common()


def fonts(data):
    """Distinct font families, tallied the same way as palette()."""
    counts = collections.Counter()
    page = data.get("page") or {}
    if page.get("font"):
        counts[page["font"]] += 1
    for entry in data.get("type") or []:
        value = entry.get("font")
        if value:
            counts[value] += 1
    return counts.most_common()


def compute_stats(data):
    """A one-glance summary: enough to answer 'is this page disciplined or
    sprawling' without reading the rest of the report."""
    return {
        "typeStyles": len(data.get("type") or []),
        "distinctFonts": len(fonts(data)),
        "distinctColors": len(palette(data)),
        "cssVariables": data.get("variableCount", 0),
        "radii": len(data.get("radii") or []),
        "transitions": len(data.get("transitions") or []),
        "gradients": (data.get("gradients") or {}).get("count", 0),
        "sections": data.get("sections", 0),
        "pageHeightPx": data.get("height", 0),
    }


def render(data, include_summary=True):
    page = data.get("page") or {}
    type_rows = []
    for entry in (data.get("type") or [])[:12]:
        type_rows.append([entry.get("tag", ""), entry.get("size", ""),
                          entry.get("weight", ""),
                          entry.get("tracking", "normal"),
                          em(entry.get("size"), entry.get("tracking")) or "-",
                          entry.get("leading", ""), "`%s`" % entry.get("font", "")])

    out = []
    out.append("# REFERENCE - %s" % (data.get("title") or data.get("url", "")))
    out.append("")
    out.append("Measured from computed styles at %s, not estimated from a"
               % (data.get("url") or "the page"))
    out.append("screenshot. Every number below is one the page reported.")
    out.append("")
    out.append("Rebuild from this file. If a value is not written down here it")
    out.append("was not understood, and it will be wrong in the rebuild in a")
    out.append("way nobody can point at.")
    out.append("")

    if include_summary:
        stats = compute_stats(data)
        out.append("## Summary")
        out.append("")
        out.append(table([
            ["type styles", stats["typeStyles"]],
            ["distinct fonts", stats["distinctFonts"]],
            ["distinct colors", stats["distinctColors"]],
            [":root variables", stats["cssVariables"]],
            ["border radii", stats["radii"]],
            ["transition curves", stats["transitions"]],
            ["gradients", stats["gradients"]],
            ["sections", stats["sections"]],
            ["page height", "%spx" % stats["pageHeightPx"]],
        ], ["metric", "count"]))
        out.append("")
        if stats["distinctFonts"] > 3:
            out.append("%d distinct fonts is a lot for one page; most sites"
                       % stats["distinctFonts"])
            out.append("that read as considered use two - one for display, one")
            out.append("for text.")
            out.append("")

    out.append("## Page")
    out.append("")
    out.append(table([["background", page.get("background", "")],
                      ["text", page.get("color", "")],
                      ["body font", page.get("font", "")],
                      ["body size / leading", "%s / %s"
                       % (page.get("size", ""), page.get("leading", ""))],
                      [":root variables", data.get("variableCount", 0)],
                      ["page height", "%spx over %s sections"
                       % (data.get("height", "?"), data.get("sections", "?"))]],
                     ["", "value"]))
    out.append("")

    out.append("## Type")
    out.append("")
    out.append(table(type_rows, ["tag", "size", "weight", "tracking", "in em",
                                 "leading", "font"]))
    out.append("")
    tracked = [(px(e.get("size")), em(e.get("size"), e.get("tracking")))
               for e in (data.get("type") or []) if px(e.get("size"))]
    tracked = [t for t in tracked if t[1]]
    if len(tracked) >= 2:
        big, small = tracked[0], tracked[-1]
        out.append("Tracking at %gpx is %s and at %gpx is %s. If it tightens as"
                   % (big[0], big[1], small[0], small[1]))
        out.append("size grows, that single rule is most of why large type on")
        out.append("this page looks right and most amateur hero text does not.")
        out.append("")

    if include_summary:
        colors = palette(data)
        out.append("## Palette")
        out.append("")
        if colors:
            out.append(table([[c, n] for c, n in colors[:10]],
                             ["color", "uses"]))
        else:
            out.append("No colors captured beyond the page default.")
        out.append("")

        font_list = fonts(data)
        out.append("## Fonts")
        out.append("")
        if font_list:
            out.append(table([["`%s`" % f, n] for f, n in font_list],
                             ["font", "uses"]))
        else:
            out.append("No fonts captured.")
        out.append("")

    out.append("## Space")
    out.append("")
    pads = data.get("sectionPadding") or []
    if pads:
        out.append("Section padding, most common first (vertical / horizontal):")
        out.append("")
        for value, count in pads[:5]:
            out.append("- `%s` x%d" % (value, count))
        out.append("")
    widths = data.get("maxWidths") or []
    if widths:
        out.append("Max widths: " + ", ".join("`%s` x%d" % (v, n)
                                              for v, n in widths[:5]))
        out.append("")

    out.append("## Shape")
    out.append("")
    radii = data.get("radii") or []
    if radii:
        out.append(table([[("pill" if (px(v) or 0) > 999 else v), n]
                          for v, n in radii[:6]], ["radius", "uses"]))
        out.append("")

    out.append("## Motion")
    out.append("")
    transitions = data.get("transitions") or []
    if transitions:
        curves = collections.Counter()
        for value, count in transitions:
            for part in str(value).split(","):
                if "cubic-bezier" in part or "ease" in part:
                    piece = part.strip().split(" ")
                    curves[" ".join(piece[-2:]) if len(piece) > 1
                           else part.strip()] += count
        for curve, count in curves.most_common(4):
            out.append("- `%s` x%d" % (curve.strip(), count))
        out.append("")
        out.append("Few curves and few durations across a whole page is the")
        out.append("discipline worth copying, more than any single easing.")
        out.append("")

    gradients = data.get("gradients") or {}
    if gradients.get("count"):
        out.append("## Surface")
        out.append("")
        out.append("%d elements carry a gradient. One of them:" % gradients["count"])
        out.append("")
        out.append("```css")
        out.append(gradients.get("sample", ""))
        out.append("```")
        out.append("")
        out.append("Count them and you learn nothing. Read the opacity: low")
        out.append("percentages are a light source, not decoration.")
        out.append("")

    out.append("## Substituting")
    out.append("")
    out.append("Rebuild layout, type scale, tracking, spacing, radii and easing")
    out.append("to these numbers. Substitute the palette, the fonts and every")
    out.append("word - inheriting someone's colours is the one part of this")
    out.append("that teaches nothing. Write copy at matching string lengths so")
    out.append("lines break in the same places and the layout is tested rather")
    out.append("than flattered.")
    out.append("")
    return "\n".join(out)


def load_measured_text(path):
    """Read the raw text of the pasted measurement, from a file or stdin."""
    if path == "-":
        return sys.stdin.read()
    with io.open(path, encoding="utf-8-sig") as fh:
        return fh.read()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("measured", nargs="?",
                     help="the JSON the probe printed, or - to read stdin")
    ap.add_argument("--probe", action="store_true",
                    help="print the browser script and exit")
    ap.add_argument("-o", "--out", default="REFERENCE.md")
    ap.add_argument("--stats", action="store_true",
                    help="also print the summary counts as JSON to stdout")
    ap.add_argument("--no-summary", action="store_true",
                    help="omit the Summary/Palette/Fonts rollups from the output")
    ap.add_argument("--version", action="version",
                    version="specextract %s" % VERSION)
    args = ap.parse_args()

    if args.probe:
        sys.stdout.write(PROBE)
        return 0

    if not args.measured:
        print("  Two steps:", file=sys.stderr)
        print("    py -3 spec.py --probe > probe.js", file=sys.stderr)
        print("    paste probe.js into DevTools (F12), save the output as"
              " measured.json", file=sys.stderr)
        print("    py -3 spec.py measured.json", file=sys.stderr)
        return 2

    try:
        raw = load_measured_text(args.measured)
    except OSError as exc:
        print("  could not read %s: %s" % (args.measured, exc.strerror or exc),
              file=sys.stderr)
        return 2

    try:
        data = parse_measured(raw)
    except ValueError as exc:
        print("  could not read %s: %s" % (args.measured, exc), file=sys.stderr)
        print("  That is a file that would not parse, not a page with no design.",
              file=sys.stderr)
        return 2

    data = normalize(data)

    if not data.get("type"):
        print("  The measurement has no type data in it. Paste the whole JSON,",
              file=sys.stderr)
        print("  including the outer braces.", file=sys.stderr)
        return 2

    text = render(data, include_summary=not args.no_summary)

    out_dir = os.path.dirname(args.out)
    try:
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with io.open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    except OSError as exc:
        print("  could not write %s: %s" % (args.out, exc.strerror or exc),
              file=sys.stderr)
        return 2

    print("  %s  (%d type rows, %d :root variables)"
          % (args.out, len(data.get("type") or []), data.get("variableCount", 0)))

    if args.stats:
        print(json.dumps(compute_stats(data), indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
