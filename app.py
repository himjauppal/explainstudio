"""ExplainStudio sales dashboard."""

import altair as alt
import streamlit as st

from analytics import summarize
from sales import DATA, DataError, load_stuttgart, load_upload

alt.data_transformers.disable_max_rows()

st.set_page_config(page_title="ExplainStudio", page_icon="🍽️", layout="wide")
st.markdown("""
<style>
    .block-container { max-width: 1350px; padding-top: 3.6rem; }
    [data-testid="stMetric"] {
        background: white; padding: .8rem 1rem; border: 1px solid #dbe6dd;
        border-radius: 14px; min-height: 104px;
    }
    [data-testid="stMetricValue"] { font-weight: 680; }
    h1 { letter-spacing: -0.045em; }
    [data-testid="stSidebar"] h2 { font-size: 1.35rem; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.subheader("ExplainStudio")
    german = st.radio("Language / Sprache", ["English", "Deutsch"], horizontal=True) == "Deutsch"


def tr(english, deutsch):
    return deutsch if german else english


def number(value, places=0):
    formatted = f"{value:,.{places}f}"
    return formatted.translate(str.maketrans(",.", ".,")) if german else formatted


def date_label(value):
    return value.strftime("%d.%m.%Y" if german else "%Y-%m-%d")


@st.cache_data
def demo(source):
    if source == "stuttgart":
        return load_stuttgart()
    return load_upload((DATA / "synthetic_pos.csv").read_bytes())[0]


sources = {
    "stuttgart": tr("Stuttgart · real sales", "Stuttgart · echte Verkaufsdaten"),
    "synthetic": tr("Synthetic POS demo", "Synthetische Kassendaten"),
    "upload": tr("Upload a CSV", "CSV hochladen"),
}

with st.sidebar:
    source = st.radio(tr("Data source", "Datenquelle"), list(sources),
                      format_func=sources.get)
    with st.expander(tr("CSV format", "CSV-Format")):
        st.markdown(tr(
            "Required: `date` (YYYY-MM-DD), `dish`, `quantity`. Optional: "
            "`hour` (0–23), `unit_price` (EUR), `line_id`. Use UTF-8.",
            "Pflichtfelder: `date` (JJJJ-MM-TT), `dish`, `quantity`. Optional: "
            "`hour` (0–23), `unit_price` (EUR), `line_id`. UTF-8 verwenden.",
        ))
        st.download_button(
            tr("Download example CSV", "Beispiel-CSV herunterladen"),
            (DATA / "synthetic_pos.csv").read_bytes(), "synthetic_pos.csv", "text/csv",
        )

st.title(tr("Restaurant sales dashboard", "Restaurant-Verkaufsübersicht"))

if source == "upload":
    uploaded = st.file_uploader(tr("Upload your POS export", "Kassenexport hochladen"), type=["csv"])
    if uploaded is None:
        st.info(tr("Choose a CSV or download an example from the sidebar.",
                   "CSV auswählen oder Beispieldatei in der Seitenleiste herunterladen."))
        st.stop()
    try:
        sales, removed = load_upload(uploaded.getvalue())
    except DataError as error:
        st.error(tr(error.english, error.german))
        st.stop()
    if removed:
        st.info(tr(f"Removed {removed} repeated sales lines with identical IDs and values.",
                   f"{removed} doppelte Verkaufszeilen mit identischen IDs und Werten entfernt."))
    caption = tr("Uploaded POS data", "Hochgeladene Kassendaten")
    filter_key = f"{source}-{uploaded.file_id}"
else:
    sales = demo(source)
    caption = tr(
        "Stuttgart research dataset · Seven products · Daily servings sold",
        "Stuttgarter Forschungsdatensatz · Sieben Produkte · Täglich verkaufte Portionen",
    ) if source == "stuttgart" else tr(
        "Synthetic POS demo · Fictional orders and prices",
        "Synthetische Kassendaten · Fiktive Bestellungen und Preise",
    )
    filter_key = source

st.caption(caption)

first, last = sales["date"].min().date(), sales["date"].max().date()
with st.sidebar:
    st.divider()
    interval = st.date_input(tr("Date range", "Zeitraum"), (first, last),
                             min_value=first, max_value=last, key=f"dates-{filter_key}",
                             format="DD.MM.YYYY" if german else "YYYY-MM-DD")
    available = sorted(sales["dish"].unique())
    dishes = st.multiselect(tr("Menu items", "Gerichte"), available, key=f"dishes-{filter_key}",
                            placeholder=tr("All items", "Alle Gerichte")) or available

if len(interval) != 2:
    st.info(tr("Select the start and end date.", "Start- und Enddatum auswählen."))
    st.stop()

daily, weekdays, menu, hours, revenue = summarize(sales, *interval, dishes)
if menu.empty:
    st.info(tr("No records match your filters.", "Keine Einträge für diese Filter."))
    st.stop()

servings = tr("Servings", "Portionen")
day_name = tr("Date", "Datum")
dish_name = tr("Menu item", "Gericht")
cards = st.columns(5 if revenue is not None else 4)
cards[0].metric(tr("Total servings", "Portionen gesamt"), number(daily["servings"].sum()))
cards[1].metric(tr("Recorded days", "Erfasste Tage"), number(len(daily)))
cards[2].metric(tr("Top seller", "Meistverkauft"), menu.iloc[0]["dish"])
cards[3].metric(tr("Lowest seller", "Am wenigsten verkauft"), menu.iloc[-1]["dish"])
if revenue is not None:
    cards[4].metric(tr("Sales value", "Verkaufswert"), f"€ {number(revenue, 2)}")

st.subheader(tr("Daily sales", "Tagesabsatz"))
st.caption(f"{date_label(interval[0])} – {date_label(interval[1])}")
trend = daily.copy()
trend["segment"] = trend["date"].diff().dt.days.fillna(1).gt(1).cumsum()
trend[day_name] = trend["date"].map(date_label)
chart = alt.Chart(trend).mark_area(
    line={"color": "#167460", "strokeWidth": 1.8},
    color=alt.Gradient(gradient="linear", x1=0, x2=0, y1=0, y2=1,
                       stops=[alt.GradientStop(color="#57ab94", offset=0),
                              alt.GradientStop(color="#eef6ef", offset=1)]),
    point=len(trend) < 10,
).encode(
    x=alt.X("date:T", title=None, scale=alt.Scale(type="utc")),
    detail="segment:N",
    y=alt.Y("servings:Q", title=servings),
    tooltip=[alt.Tooltip(f"{day_name}:N"), alt.Tooltip("servings:Q", title=servings, format=",d")],
).properties(height=230).interactive()
st.altair_chart(chart, width="stretch", theme=None)

left, right = st.columns(2)
weekday_names = tr(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                   ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"])
weekdays["label"] = weekdays["weekday"].map(dict(enumerate(weekday_names, 1)))
average = tr("Average servings", "Ø Portionen")
with left:
    st.subheader(tr("Sales by weekday", "Absatz nach Wochentag"))
    st.caption(tr("Average per recorded day", "Durchschnitt pro erfasstem Tag"))
    st.altair_chart(alt.Chart(weekdays).mark_bar(color="#167460", cornerRadiusEnd=4).encode(
        x=alt.X("label:N", sort=weekday_names, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("servings:Q", title=average),
        tooltip=[alt.Tooltip("label:N", title=tr("Weekday", "Wochentag")),
                 alt.Tooltip("servings:Q", title=average, format=".1f")],
    ).properties(height=220), width="stretch", theme=None)

with right:
    st.subheader(tr("Sales by menu item", "Absatz nach Gericht"))
    st.caption(tr("Total servings in the selected period", "Portionen im gewählten Zeitraum"))
    st.altair_chart(alt.Chart(menu.head(15)).mark_bar(color="#668f81", cornerRadiusEnd=4).encode(
        y=alt.Y("dish:N", sort=menu["dish"].head(15).tolist(), title=None),
        x=alt.X("servings:Q", title=servings),
        tooltip=[alt.Tooltip("dish:N", title=dish_name), alt.Tooltip("servings:Q", title=servings, format=",d")],
    ).properties(height=220), width="stretch", theme=None)

if hours is not None and not hours.empty:
    st.subheader(tr("Sales by hour", "Absatz nach Stunde"))
    st.caption(tr("Uses sales rows with a recorded hour.", "Berücksichtigt Verkaufszeilen mit Stundenangabe."))
    st.altair_chart(alt.Chart(hours).mark_bar(color="#167460", cornerRadiusEnd=4).encode(
        x=alt.X("hour:O", title=tr("Hour", "Stunde"), axis=alt.Axis(labelAngle=0)),
        y=alt.Y("servings:Q", title=servings),
        tooltip=[alt.Tooltip("hour:O", title=tr("Hour", "Stunde")),
                 alt.Tooltip("servings:Q", title=servings, format=",d")],
    ).properties(height=210), width="stretch", theme=None)

with st.expander(tr("Full menu ranking", "Vollständige Rangliste")):
    st.dataframe(menu.rename(columns={"dish": dish_name, "servings": servings}), hide_index=True)

missing_days = (interval[1] - interval[0]).days + 1 - len(daily)
if missing_days:
    st.caption(tr(f"{missing_days:,} calendar days in this range have no records.",
                  f"{number(missing_days)} Kalendertage in diesem Zeitraum ohne Datensätze."))
if source == "stuttgart":
    st.caption("[Taigel & Meller (2020) · Mendeley Data · CC BY 4.0](https://doi.org/10.17632/7s3ys9ntnz.1)")
