import os

import spec

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def load(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8-sig") as fh:
        raw = fh.read()
    return spec.normalize(spec.parse_measured(raw))


def test_render_minimal_has_core_sections():
    text = spec.render(load("minimal.json"))
    assert text.startswith("# REFERENCE - Example")
    for heading in ("## Page", "## Type", "## Space", "## Shape", "## Motion",
                    "## Substituting"):
        assert heading in text


def test_render_includes_summary_by_default():
    text = spec.render(load("minimal.json"))
    assert "## Summary" in text
    assert "## Palette" in text
    assert "## Fonts" in text


def test_render_can_omit_summary():
    text = spec.render(load("minimal.json"), include_summary=False)
    assert "## Summary" not in text
    assert "## Palette" not in text
    assert "## Fonts" not in text
    # the rest of the report is unaffected
    assert "## Type" in text


def test_render_full_flags_many_fonts():
    text = spec.render(load("full.json"))
    assert "distinct fonts is a lot" in text


def test_render_full_includes_gradient_surface_section():
    text = spec.render(load("full.json"))
    assert "## Surface" in text
    assert "linear-gradient" in text


def test_render_no_gradients_omits_surface_section():
    text = spec.render(load("minimal.json"))
    assert "## Surface" not in text


def test_render_type_table_row_count_capped_at_twelve():
    data = {
        "title": "Many sizes",
        "type": [{"tag": "P", "size": "%dpx" % n, "weight": "400",
                  "tracking": "0px", "leading": "1.4", "color": "#111",
                  "font": "Inter", "sample": "x"} for n in range(15)],
    }
    text = spec.render(data)
    type_section = text.split("## Type")[1].split("## ")[0]
    data_rows = [l for l in type_section.splitlines() if l.startswith("| ")]
    # header row + at most 12 data rows, never all 15
    assert len(data_rows) == 1 + 12


def test_render_tracking_prose_present_with_multiple_sizes():
    text = spec.render(load("full.json"))
    assert "Tracking at" in text


def test_render_produces_valid_markdown_tables_with_special_font_names():
    # font names containing '|' should not corrupt the table structure
    data = load("minimal.json")
    data["type"][0]["font"] = "Weird|Font"
    text = spec.render(data)
    assert "Weird\\|Font" in text
