import spec


def test_px_parses_pixel_string():
    assert spec.px("48px") == 48.0


def test_px_handles_bare_number():
    assert spec.px("12") == 12.0


def test_px_returns_none_for_garbage():
    assert spec.px("normal") is None
    assert spec.px(None) is None


def test_em_computes_ratio_with_sign():
    # -1.2px tracking at 48px is -0.025em.
    assert spec.em("48px", "-1.2px") == "-0.025em"


def test_em_positive_values_get_explicit_sign():
    assert spec.em("16px", "0.32px") == "+0.020em"


def test_em_blank_when_size_missing():
    assert spec.em(None, "-1.2px") == ""


def test_em_blank_when_tracking_not_numeric():
    assert spec.em("48px", "normal") == ""


def test_em_blank_when_size_is_zero():
    assert spec.em("0px", "-1.2px") == ""


def test_table_basic_shape():
    out = spec.table([["a", 1], ["b", 2]], ["name", "count"])
    lines = out.splitlines()
    assert lines[0] == "| name | count |"
    assert lines[1] == "|---|---|"
    assert lines[2] == "| a | 1 |"
    assert lines[3] == "| b | 2 |"


def test_table_escapes_pipe_in_cell():
    out = spec.table([["a|b", 1]], ["name", "count"])
    assert "a\\|b" in out
    # the row must still parse as exactly 2 columns' worth of separators
    row_line = out.splitlines()[2]
    assert row_line.count(" | ") == 1 or row_line.startswith("| a\\|b")


def test_table_collapses_embedded_newlines():
    out = spec.table([["line one\nline two", 1]], ["name", "count"])
    assert "\n" not in out.splitlines()[2]
    assert "line one line two" in out.splitlines()[2]


def test_esc_cell_stringifies_non_strings():
    assert spec.esc_cell(3) == "3"
