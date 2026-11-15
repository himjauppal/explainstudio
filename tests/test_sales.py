from datetime import date
from decimal import Decimal
from unittest import TestCase

from analytics import summarize
from sales import DataError, load_stuttgart, load_upload


class SalesTests(TestCase):
    def test_stuttgart_totals_match_source(self):
        sales = load_stuttgart()
        daily, weekdays, menu, hours, revenue = summarize(
            sales, date(2013, 10, 4), date(2015, 11, 7), list(sales["dish"].unique())
        )
        self.assertEqual(len(daily), 760)
        self.assertEqual(daily["servings"].sum(), 95_429)
        self.assertEqual(len(weekdays), 7)
        self.assertEqual(menu["dish"].iloc[[0, -1]].tolist(), ["LAMM", "CALAMARI"])
        self.assertIsNone(hours)
        self.assertIsNone(revenue)

    def test_repeated_id_deduplicated_and_german_price_parsed(self):
        sales, removed = load_upload(
            b"line_id;date;dish;quantity;hour;unit_price\n"
            b"1;2025-01-01;Soup;2;12;4,50\n1;2025-01-01;Soup;2;12;4,50\n"
            b"2;2025-01-02;Cake;1;;\n"
        )
        self.assertEqual(removed, 1)
        start, end = date(2025, 1, 1), date(2025, 1, 2)
        daily, _, _, hours, revenue = summarize(sales, start, end, ["Soup"])
        self.assertEqual(daily["servings"].tolist(), [2, 0])
        self.assertEqual(hours["hour"].tolist(), [12])
        self.assertEqual(revenue, Decimal("9.00"))
        self.assertIsNone(summarize(sales, start, end, ["Soup", "Cake"])[-1])

    def test_upload_date_quantity_and_id_errors(self):
        cases = [
            (b"date,dish,quantity\n2025-02-30,Soup,3", "date, line"),
            (b"date,dish,quantity\n2025-02-01,Soup,", "quantity, line"),
            (b"line_id,date,dish,quantity\n1,2025-02-01,Soup,2\n1,2025-02-01,Soup,3", "conflicting"),
        ]
        for content, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(DataError, message):
                load_upload(content)

    def test_same_values_without_ids_can_be_distinct_sales(self):
        sales, removed = load_upload(
            b"date,dish,quantity\n2025-02-01,Soup,3\n2025-02-01,Soup,3"
        )
        self.assertEqual(len(sales), 2)
        self.assertEqual(removed, 0)
