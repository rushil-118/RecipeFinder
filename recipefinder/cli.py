"""Command-line interface: python -m recipefinder <command>."""
import argparse
import sys

from recipefinder.catalog import DEFAULT_DATA, Catalog, load_recipes


def build_parser():
    parser = argparse.ArgumentParser(prog="recipefinder", description="Query a CSV of recipes.")
    parser.add_argument("--data", default=str(DEFAULT_DATA), help="path to the recipes CSV")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("cuisines", help="list all cuisines")

    count = sub.add_parser("count", help="how many recipes a cuisine has")
    count.add_argument("cuisine")

    names = sub.add_parser("names", help="recipe names for a cuisine")
    names.add_argument("cuisine")

    quick = sub.add_parser("quick", help="recipes ready within a time limit")
    quick.add_argument("max_minutes", type=int)
    quick.add_argument("--vegetarian", action="store_true", help="vegetarian recipes only")

    calories = sub.add_parser("calories", help="average calories for a cuisine")
    calories.add_argument("cuisine")
    return parser


def main(argv=None, out=None):
    out = out or sys.stdout
    args = build_parser().parse_args(argv)
    try:
        catalog = Catalog(load_recipes(args.data))
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.command == "cuisines":
        print("\n".join(catalog.cuisines()), file=out)
    elif args.command == "count":
        print(catalog.count_by_cuisine(args.cuisine), file=out)
    elif args.command == "names":
        print("\n".join(catalog.names_by_cuisine(args.cuisine)), file=out)
    elif args.command == "quick":
        for r in catalog.quick(args.max_minutes, args.vegetarian):
            print(f"{r.minutes:>3} min  {r.name} ({r.cuisine})", file=out)
    elif args.command == "calories":
        average = catalog.average_calories(args.cuisine)
        if average is None:
            print(f"error: no recipes for cuisine {args.cuisine!r}", file=sys.stderr)
            return 2
        print(average, file=out)
    return 0
