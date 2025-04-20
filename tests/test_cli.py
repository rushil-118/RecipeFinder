import io

from recipefinder.cli import main


def run(*argv):
    out = io.StringIO()
    code = main(list(argv), out=out)
    return code, out.getvalue()


def test_count():
    assert run("count", "Italian") == (0, "7\n")


def test_cuisines_lists_all():
    code, text = run("cuisines")
    assert code == 0 and text.splitlines()[0] == "French"


def test_quick_vegetarian():
    code, text = run("quick", "10", "--vegetarian")
    assert code == 0 and "Edamame" in text and "Spaghetti" not in text


def test_calories_unknown_cuisine_is_an_error():
    code, _ = run("calories", "Martian")
    assert code == 2


def test_missing_data_file_is_an_error(tmp_path):
    code, _ = run("--data", str(tmp_path / "nope.csv"), "cuisines")
    assert code == 1
