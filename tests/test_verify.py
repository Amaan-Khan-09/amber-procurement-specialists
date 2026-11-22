from amber.docs import Document, Page
from amber.verify import match_level, verify

DOC = Document("sheet", "sheet.pdf", pages=[
    Page(1, "Industrial Diesel Generator Set\nStandby rating 2000 kW / 2500 kVA"),
    Page(2, "Engine speed: 1800 rpm\nTurbo-\ncharged and after-\ncooled engine"),
    Page(3, "Voltage   480Y/277\n  Frequency  60   Hz\nFuel consumption 139.6 gph"),
])


def test_exact_quote_on_cited_page():
    c = verify(DOC, "Standby rating 2000 kW / 2500 kVA", page=1)
    assert c and c.page == 1 and c.match == "exact"


def test_wrong_page_is_corrected_to_real_page():
    c = verify(DOC, "Engine speed: 1800 rpm", page=3)
    assert c and c.page == 2


def test_invented_quote_is_rejected():
    assert verify(DOC, "Tier 4 Final certified", page=1) is None


def test_wrong_number_never_passes():
    assert verify(DOC, "Engine speed: 1500 rpm") is None
    assert verify(DOC, "Fuel consumption 139.0 gph") is None


def test_hyphenated_line_break_is_joined():
    c = verify(DOC, "Turbocharged and aftercooled engine")
    assert c and c.page == 2 and c.match == "normalized"


def test_table_spacing_is_tolerated():
    c = verify(DOC, "Frequency 60 Hz")
    assert c and c.page == 3


def test_curly_quotes_and_dashes_unified():
    assert match_level("“critical” type – side inlet", 'silencer of the "critical" type - side inlet') == "normalized"


def test_table_row_quote_matches_within_window_but_wrong_number_fails():
    page = "Ratings          Standby      Prime\nkW               2000         1810\nkVA              2500         2263"
    assert match_level("Standby kVA 2500", page) == "table"
    assert match_level("Standby kVA 25000", page) is None
    assert match_level("Standby kVA 2400", page) is None


def test_fuzzy_only_for_long_wordy_quotes():
    page = "The enclosure shall be weatherproof and rodent proof with lockable doors"
    assert match_level("enclosure shall be weatherprof and rodent proof", page) == "fuzzy"
    assert match_level("weatherprof", page) is None


def test_word_quote_across_interleaved_columns():
    page = ("Exhaust System  60 Hz   Alternator Specifications  60 Hz\nExhaust flow at rated kW,  Type  4-Pole, Rotating-Field\n"
            "m3/min. (cfm)  443 (15635)  Exciter type  Brushless, Permanent-\nExhaust temperature at rated kW at  Magnet Pilot Exciter\n")
    assert match_level("Exciter type  Brushless, Permanent- Magnet Pilot Exciter", page) == "table"
    assert match_level("Exciter type  Brushless, Permanent- Magnet Pilot Exciter", "Exciter type: static, brush type") is None
    assert match_level("Brushless exciter", page) is None  # too few words for this rule
