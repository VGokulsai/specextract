import os

import pytest

import spec

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def read_fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8-sig") as fh:
        return fh.read()


def test_parse_measured_valid_json():
    data = spec.parse_measured(read_fixture("minimal.json"))
    assert data["url"] == "https://example.com"
    assert len(data["type"]) == 1


def test_parse_measured_rejects_malformed_json():
    with pytest.raises(ValueError):
        spec.parse_measured(read_fixture("malformed.json"))


def test_parse_measured_rejects_non_object_top_level():
    with pytest.raises(ValueError, match="JSON object"):
        spec.parse_measured(read_fixture("not_object.json"))


def test_parse_measured_rejects_empty_input():
    with pytest.raises(ValueError, match="empty"):
        spec.parse_measured("   \n  ")


def test_parse_measured_tolerates_trailing_console_text():
    # DevTools prints the console.log JSON *and then* the script's return
    # value below it; both can end up copy-pasted into the same file.
    data = spec.parse_measured(read_fixture("trailing_garbage.json"))
    assert data["url"] == "https://example.com"
    assert len(data["type"]) == 1


def test_parse_measured_strips_console_reprint_prefix():
    raw = '> {"url": "https://example.com", "type": [{"tag": "H1"}]}'
    data = spec.parse_measured(raw)
    assert data["url"] == "https://example.com"


def test_normalize_coerces_non_list_type_to_empty():
    data = spec.normalize({"type": "not a list"})
    assert data["type"] == []


def test_normalize_drops_non_dict_type_entries():
    data = spec.normalize({"type": [{"tag": "H1"}, "garbage", 3]})
    assert data["type"] == [{"tag": "H1"}]


def test_normalize_coerces_malformed_tally_pairs():
    data = spec.normalize({"radii": ["not-a-pair", ["8px", 2], ["a", "b", "c"]]})
    assert data["radii"] == [("8px", 2)]


def test_normalize_defaults_page_and_gradients_when_wrong_type():
    data = spec.normalize({"page": "nope", "gradients": None})
    assert data["page"] == {}
    assert data["gradients"] == {}


def test_normalize_coerces_bad_variable_count():
    data = spec.normalize({"variableCount": "many"})
    assert data["variableCount"] == 0


def test_normalize_keeps_good_variable_count():
    data = spec.normalize({"variableCount": 12})
    assert data["variableCount"] == 12


def test_palette_dedupes_and_counts():
    data = spec.normalize(spec.parse_measured(read_fixture("full.json")))
    colors = spec.palette(data)
    names = [c for c, _ in colors]
    assert len(names) == len(set(names))
    assert sum(n for _, n in colors) >= len(data["type"])


def test_fonts_counts_page_and_type_entries():
    data = spec.normalize(spec.parse_measured(read_fixture("full.json")))
    font_list = dict(spec.fonts(data))
    assert "Söhne" in font_list
    # page font (Söhne) + H1 + H2 all use "Söhne" -> counted 3 times
    assert font_list["Söhne"] == 3


def test_compute_stats_matches_fixture_full():
    data = spec.normalize(spec.parse_measured(read_fixture("full.json")))
    stats = spec.compute_stats(data)
    assert stats["typeStyles"] == 5
    assert stats["distinctFonts"] == 4
    assert stats["cssVariables"] == 42
    assert stats["gradients"] == 3
    assert stats["sections"] == 7
    assert stats["pageHeightPx"] == 8400
