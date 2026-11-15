"""Validate sales exports and turn them into a common set of columns."""
import csv
import io
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent / "data"
PRODUCTS = ("CALAMARI", "FISCH", "GARNELEN", "HAEHNCHEN", "KOEFTE", "LAMM", "STEAK")
REQUIRED = {"date", "dish", "quantity"}


class DataError(ValueError):
    def __init__(self, english, german):
        self.english = english
        self.german = german
        super().__init__(english)


def load_stuttgart():
    columns = ["DEMAND_DATE", *PRODUCTS]
    raw = pd.read_csv(DATA / "stuttgart.csv", sep=";", usecols=columns)
    raw["DEMAND_DATE"] = pd.to_datetime(raw["DEMAND_DATE"], format="%m.%d.%Y")
    if raw.isna().any().any() or raw["DEMAND_DATE"].duplicated().any():
        raise ValueError("Unexpected missing data or duplicate dates in Stuttgart source")
    return raw.rename(columns={"DEMAND_DATE": "date"}).melt(
        "date", var_name="dish", value_name="quantity"
    )


def load_upload(content):
    """Read the documented POS schema and return (sales, duplicates removed)."""
    try:
        body = content.decode("utf-8-sig")
        header = next(csv.reader(io.StringIO(body)), [])
        dialect = ";" if ";" in body.splitlines()[0] and len(header) == 1 else ","
        reader = csv.reader(io.StringIO(body), delimiter=dialect, strict=True)
        columns = [value.strip().lower() for value in next(reader, [])]
    except (UnicodeError, csv.Error, IndexError) as error:
        raise DataError("Save the file as UTF-8 CSV.", "Datei als UTF-8-CSV speichern.") from error
    if len(columns) != len(set(columns)):
        raise DataError("Column names must be unique.", "Spaltennamen müssen eindeutig sein.")
    missing = ", ".join(sorted(REQUIRED - set(columns)))
    if missing:
        raise DataError(f"Missing columns: {missing}.", f"Fehlende Spalten: {missing}.")
    rows, line_numbers = [], []
    try:
        for row in reader:
            if not row or (len(row) == 1 and not row[0].strip()):
                continue
            if len(row) != len(columns):
                raise DataError(
                    f"Line {reader.line_num} has the wrong number of fields.",
                    f"Zeile {reader.line_num} enthält zu viele oder zu wenige Felder.",
                )
            rows.append([value.strip() for value in row])
            line_numbers.append(reader.line_num)
    except csv.Error as error:
        raise DataError("Invalid CSV syntax.", "Ungültiges CSV-Format.") from error
    if not rows:
        raise DataError("The file has no sales rows.", "Die Datei enthält keine Verkaufszeilen.")

    sales = pd.DataFrame(rows, columns=columns, index=line_numbers)

    def validate(column, valid, expected, expected_de):
        invalid = sales.index[~valid]
        if len(invalid):
            lines = ", ".join(map(str, invalid[:5]))
            raise DataError(
                f"{column}, line(s) {lines}: {expected}.",
                f"{column}, Zeile(n) {lines}: {expected_de}.",
            )

    dates = pd.to_datetime(sales["date"], format="%Y-%m-%d", errors="coerce")
    validate("date", dates.notna() & sales["date"].str.fullmatch(r"\d{4}-\d{2}-\d{2}"),
             "enter a valid date in YYYY-MM-DD format", "gültiges Datum im Format JJJJ-MM-TT eingeben")
    validate("dish", sales["dish"].ne(""), "enter a dish name", "Gericht eingeben")
    sales["date"] = dates
    numeric_fields = {
        "quantity": (r"[0-9]{1,9}", "enter a whole number from 0 to 999999999", "ganze Zahl von 0 bis 999999999 eingeben"),
        "hour": (r"(?:[01]?[0-9]|2[0-3])", "enter an hour from 0 to 23", "Stunde von 0 bis 23 eingeben"),
        "unit_price": (r"[0-9]{1,9}(?:\.[0-9]{1,2})?", "enter a EUR price such as 12.50", "EUR-Preis wie 12,50 eingeben"),
    }
    for column, (pattern, expected, expected_de) in numeric_fields.items():
        if column not in sales:
            continue
        values = sales[column]
        if column == "unit_price" and dialect == ";":
            values = values.str.replace(",", ".", regex=False)
        valid = values.str.fullmatch(pattern)
        if column != "quantity":
            valid |= values.eq("")
        validate(column, valid, expected, expected_de)
        sales[column] = pd.to_numeric(values.replace("", None)).astype("Int64" if column != "unit_price" else "Float64")

    removed = 0
    if "line_id" in sales:
        validate("line_id", sales["line_id"].ne(""), "enter a unique sales line ID", "eindeutige Verkaufszeilen-ID eingeben")
        unique = sales.drop_duplicates()
        conflict = unique["line_id"].duplicated(keep=False)
        if conflict.any():
            validate("line_id", ~sales["line_id"].isin(unique.loc[conflict, "line_id"]),
                     "the same ID has conflicting values", "dieselbe ID hat widersprüchliche Werte")
        removed = len(sales) - len(unique)
        sales = unique
    keep = ["date", "dish", "quantity", "hour", "unit_price"]
    return sales[[column for column in keep if column in sales]].reset_index(drop=True), removed
