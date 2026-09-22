# specextract

Reads a website's design system out of the browser and writes it down as
`REFERENCE.md`: type scale, tracking, colors, fonts, spacing, radii, easing, and
what is missing. It measures computed styles, the values the page actually
renders, not what the stylesheet claims.

Reading a site's CSS file tells you little now: it is minified, or a thousand
utility classes, or the numbers live in variables three files away. The only
place the resolved values exist is the browser, so that is where the measuring
happens.

```
py -3 spec.py --probe > probe.js     print the browser script
# paste probe.js into the site's DevTools console (F12), save the output
py -3 spec.py measured.json          write REFERENCE.md
py -3 spec.py - --stats              read the paste from stdin, print counts
py -3 spec.py measured.json --no-summary   skip the rollup sections
```

## What it is not

No headless browser, no Playwright, no npm. The probe is copy-pasted into
DevTools by hand, so there is no automation of the browser step and no login
handling. It does not judge whether a design is good; it reports the numbers so
you can. It reads type, color, spacing, radii, motion and CSS variables, not
layout structure or component markup.

## What it reports

`REFERENCE.md` covers the page defaults, a type table (size, weight, tracking in
px and em, leading, font), palette, fonts, section padding, max widths, border
radii, transition curves, and any gradients. Tracking is converted to em because
that is the number that transfers between sizes; -2.4px means nothing until you
know it was measured at 48px. The summary flags a page using more than three
fonts.

## Handling the paste

DevTools prints both the `console.log` output and the script's return string, so
the file often has trailing text after the JSON. It is parsed with `raw_decode`,
which stops at the end of the first JSON value and ignores the rest. A BOM and
`> ` line prefixes are stripped. A file that will not parse is reported as a bad
file, not as a page with no design.

## Tests

50 tests across `tests/test_cli.py`, `test_parsing.py`, `test_render.py` and
`test_units.py`. Run them with `py -3 -m pytest`. Version 0.2.0, stdlib only.
