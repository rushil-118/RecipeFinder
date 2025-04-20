# Recipe Finder

A small command-line program that answers questions about a CSV of recipes: how many a cuisine has,
which ones, what is ready quickly, and the average calories.

## Run
```bash
pip install -r requirements-dev.txt
python -m recipefinder cuisines
python -m recipefinder count Italian
python -m recipefinder names Thai
python -m recipefinder quick 20 --vegetarian
python -m recipefinder calories Indian
python -m recipefinder --data my.csv cuisines     # use your own file
pytest
```

CSV format: `name,cuisine,minutes,calories,vegetarian` (vegetarian is `true` or `false`).
