"""Loading the recipe CSV and answering questions about it."""
import csv
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DATA = Path(__file__).parent / "data" / "recipes.csv"


@dataclass(frozen=True)
class Recipe:
    name: str
    cuisine: str
    minutes: int
    calories: int
    vegetarian: bool


def load_recipes(path=DEFAULT_DATA):
    """Read recipes from a CSV file. Raises ValueError naming the bad line."""
    recipes = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            line = reader.line_num
            try:
                recipes.append(Recipe(
                    name=row["name"].strip(),
                    cuisine=row["cuisine"].strip(),
                    minutes=int(row["minutes"]),
                    calories=int(row["calories"]),
                    vegetarian=_parse_bool(row["vegetarian"]),
                ))
            except (KeyError, ValueError, AttributeError) as exc:
                raise ValueError(f"{path}: bad row on line {line}: {exc}") from exc
    return recipes


def _parse_bool(text):
    value = text.strip().lower()
    if value not in ("true", "false"):
        raise ValueError(f"expected true or false, got {text!r}")
    return value == "true"


class Catalog:
    """In-memory queries over a list of recipes. Cuisine matching ignores case."""

    def __init__(self, recipes):
        self._recipes = list(recipes)

    def __len__(self):
        return len(self._recipes)

    def cuisines(self):
        return sorted({r.cuisine for r in self._recipes})

    def _by_cuisine(self, cuisine):
        wanted = cuisine.strip().lower()
        return [r for r in self._recipes if r.cuisine.lower() == wanted]

    def count_by_cuisine(self, cuisine):
        return len(self._by_cuisine(cuisine))

    def names_by_cuisine(self, cuisine):
        return sorted(r.name for r in self._by_cuisine(cuisine))

    def quick(self, max_minutes, vegetarian_only=False):
        """Recipes ready within max_minutes, fastest first."""
        found = [r for r in self._recipes
                 if r.minutes <= max_minutes and (r.vegetarian or not vegetarian_only)]
        return sorted(found, key=lambda r: (r.minutes, r.name))

    def average_calories(self, cuisine):
        """Mean calories for a cuisine, or None if the cuisine has no recipes."""
        matches = self._by_cuisine(cuisine)
        if not matches:
            return None
        return round(sum(r.calories for r in matches) / len(matches), 1)
