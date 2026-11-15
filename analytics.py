"""Sales summaries over the selected date range and menu items."""
import duckdb
import pandas as pd


def summarize(sales, start, end, dishes):
    with duckdb.connect() as db:
        db.register("sales", sales)
        dates = sales.loc[sales["date"].between(pd.Timestamp(start), pd.Timestamp(end)), ["date"]]
        db.register("recorded", dates)
        db.execute(
            """
            CREATE TEMP TABLE selected AS
            SELECT * FROM sales
            WHERE date BETWEEN ? AND ? AND dish IN (SELECT unnest(?))
            """,
            [start, end, dishes],
        )
        daily = db.sql("""
            SELECT r.date, coalesce(sum(s.quantity), 0)::BIGINT AS servings
            FROM (SELECT DISTINCT date FROM recorded) r
            LEFT JOIN selected s USING (date)
            GROUP BY r.date ORDER BY r.date
        """).df()
        db.register("daily", daily)
        weekdays = db.sql("""
            SELECT isodow(date) AS weekday, avg(servings) AS servings
            FROM daily GROUP BY weekday ORDER BY weekday
        """).df()
        menu = db.sql("""
            SELECT dish, sum(quantity)::BIGINT AS servings
            FROM selected GROUP BY dish ORDER BY servings DESC, dish
        """).df()
        hours = None
        if "hour" in sales:
            hours = db.sql("""
                SELECT hour, sum(quantity)::BIGINT AS servings
                FROM selected WHERE hour IS NOT NULL GROUP BY hour ORDER BY hour
            """).df()
        revenue = None
        if "unit_price" in sales:
            revenue = db.sql("""
                SELECT CASE WHEN count(*) = count(unit_price)
                THEN sum(quantity * cast(unit_price AS DECIMAL(18, 2))) END
                FROM selected
            """).fetchone()[0]
        return daily, weekdays, menu, hours, revenue
