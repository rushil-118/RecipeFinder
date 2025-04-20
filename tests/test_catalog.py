import pytest

from recipefinder.catalog import Catalog, Recipe, load_recipes


@pytest.fixture
def catalog():
    return Catalog(load_recipes())


def test_packaged_csv_loads():
    assert len(load_recipes()) == 37


def test_cuisines_are_sorted_and_unique(catalog):
    assert catalog.cuisines() == ["French", "Indian", "Italian", "Japanese", "Mexican", "Thai"]


def test_count_ignores_case_and_whitespace(catalog):
    assert catalog.count_by_cuisine("italian") == catalog.count_by_cuisine(" ITALIAN ") == 7


def test_unknown_cuisine_counts_zero(catalog):
    assert catalog.count_by_cuisine("Martian") == 0
    assert catalog.names_by_cuisine("Martian") == []


def test_names_sorted(catalog):
    names = catalog.names_by_cuisine("Thai")
    assert names == sorted(names)
    assert "Pad Thai" in names


def test_quick_is_fastest_first_and_within_limit(catalog):
    result = catalog.quick(15)
    assert result and all(r.minutes <= 15 for r in result)
    assert [r.minutes for r in result] == sorted(r.minutes for r in result)


def test_quick_vegetarian_filter(catalog):
    result = catalog.quick(30, vegetarian_only=True)
    assert result and all(r.vegetarian for r in result)
    assert len(result) < len(catalog.quick(30))


def test_average_calories():
    tiny = Catalog([Recipe("a", "X", 5, 100, True), Recipe("b", "x", 5, 201, False)])
    assert tiny.average_calories("X") == 150.5
    assert tiny.average_calories("nope") is None


def test_bad_rows_are_reported_with_line_number(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("name,cuisine,minutes,calories,vegetarian\nSoup,French,ten,100,true\n")
    with pytest.raises(ValueError, match="line 2"):
        load_recipes(bad)


def test_bad_boolean_rejected(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("name,cuisine,minutes,calories,vegetarian\nSoup,French,10,100,maybe\n")
    with pytest.raises(ValueError):
        load_recipes(bad)
