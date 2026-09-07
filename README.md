# specextract

Read a website's design system out of the browser and write it down.

Reading a page's CSS file tells you almost nothing now: it is minified, or
it is a thousand utility classes, or the numbers are in variables three
files away. The only place the real values exist is the browser, after it
has resolved everything - so that is where the measuring happens.

No headless browser, no Playwright, no npm. One Python file, two steps, one
copy-paste.

## Workflow

**1. Generate the probe and run it in the browser.**

```
py -3 spec.py --probe > probe.js
```

Open the page you want to measure, open DevTools (F12), paste the contents
of `probe.js` into the Console, and press Enter. It prints one JSON blob and
returns a reminder string. Copy the JSON blob - just the object, starting at
`{` and ending at the matching `}` - into a file, e.g. `measured.json`.

(If you also grab the returned reminder string underneath it by accident,
that's fine - `spec.py` ignores anything after the JSON object rather than
failing on it.)

**2. Turn the measurement into a reference doc.**

```
py -3 spec.py measured.json
```

This writes `REFERENCE.md` in the current directory: page-level colors and
type, a table of every distinct type style the probe found, the palette and
font list rolled up, spacing, border radii, transition curves, and a
gradient sample if the page uses one.

You can also pipe the paste straight in instead of saving a file first:

```
py -3 spec.py -
```

## What the probe measures

It walks the rendered DOM and reads `getComputedStyle` - what the browser
actually painted, not what the stylesheet claims - for:

- distinct type styles (tag, size, weight, letter-spacing, line-height,
  color, font), deduplicated so a page with thousands of elements still
  produces roughly a dozen rows, not thousands
- border radii, transitions, max-widths and section padding, each tallied
  by frequency
- gradients (count + a sample)
- `:root` CSS custom properties (count)
- page background/text/font and overall page height / section count

## CLI reference

```
py -3 spec.py --probe              print the measuring script and exit
py -3 spec.py measured.json        write REFERENCE.md from a measurement
py -3 spec.py -                    same, but read the measurement from stdin
py -3 spec.py measured.json -o out.md
                                    write to a different path (directories
                                    are created if needed)
py -3 spec.py measured.json --stats
                                    also print the summary counts as JSON
py -3 spec.py measured.json --no-summary
                                    leave the Summary/Palette/Fonts rollups
                                    out of REFERENCE.md
py -3 spec.py --version            print the version and exit
```

Exit code is `0` on success, `2` on any input problem (missing file, invalid
JSON, a measurement with no type data, or an output path that can't be
written). Error messages go to stderr and try to say what's actually wrong
rather than just "failed".

### Handling a bad paste

Copy-pasting out of a browser console is the one unreliable step in this
tool, so `spec.py` is deliberately forgiving about it:

- a BOM at the start of the file is stripped automatically
- lines that got prefixed with `> ` by a terminal replaying the paste are
  un-prefixed before parsing
- if the probe's own return-value string ended up copied in underneath the
  JSON (easy to do - the console prints both), the trailing text is ignored
  rather than treated as a syntax error
- a genuine JSON syntax error is reported with the line and column, not
  just "invalid JSON"
- a measurement that parses but has the wrong shape (e.g. `type` isn't a
  list, or a tally field isn't a list of `[value, count]` pairs) is
  normalized rather than crashing - the malformed part is dropped and the
  rest of the report still renders

## Report sections

`REFERENCE.md` always has Page, Type, Space, Shape, Motion and Substituting
sections (Surface is added only when the page has gradients). By default it
also includes:

- **Summary** - a one-glance count of type styles, distinct fonts, distinct
  colors, `:root` variables, radii, transition curves, gradients, sections
  and page height. If a page uses more than three distinct fonts, this
  section says so.
- **Palette** - every distinct color seen (page background/text plus every
  type row's color), most-used first.
- **Fonts** - every distinct font family seen, most-used first.

Pass `--no-summary` to leave these three out and get just the original
Page/Type/Space/Shape/Motion/Substituting report.

## Development

```
py -3 -m pip install pytest
py -3 -m pytest -q
```

Tests live in `tests/`, with sample measurements (a minimal one-type-row
fixture and a richer multi-font/gradient/radius fixture, plus malformed and
edge-case inputs) in `tests/fixtures/`.
