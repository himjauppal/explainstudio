"""Generate a repeatable POS example with fictional dates, sales and prices."""
import csv
from datetime import date, timedelta
from random import Random

from sales import DATA

MENU = {"Pasta": (14.50, 1.0), "Schnitzel": (17.90, 0.9), "Soup": (7.50, 0.65),
        "Salad": (11.90, 0.7), "Tiramisu": (6.50, 0.55)}


def generate():
    rng = Random(42)
    DATA.mkdir(exist_ok=True)
    with (DATA / "synthetic_pos.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(["line_id", "date", "hour", "dish", "quantity", "unit_price"])
        line_id = 0
        for offset in range(112):
            day = date(2025, 1, 6) + timedelta(days=offset)
            if day.weekday() == 0:
                continue
            for hour, demand in [(12, 6), (13, 8), (14, 4), (18, 7), (19, 10), (20, 8), (21, 3)]:
                for dish, (price, popularity) in MENU.items():
                    weekend = 1.35 if day.weekday() in (4, 5, 6) else 1.0
                    quantity = max(0, round(demand * popularity * weekend + rng.gauss(0, 1.7)))
                    if quantity:
                        line_id += 1
                        writer.writerow([line_id, day, hour, dish, quantity, f"{price:.2f}"])


if __name__ == "__main__":
    generate()
