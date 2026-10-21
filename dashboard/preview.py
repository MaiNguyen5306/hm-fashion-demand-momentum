"""Local data preview: inspect validated products without publishing a website."""

from pathlib import Path
import sys

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.product_data import ProductDataStore

st.set_page_config(page_title="H&M — Local data preview", layout="wide")
st.title("H&M demand data preview")
st.caption("Local inspection of historical sales, demand momentum, and observed lifecycles.")

REQUIRED = [ROOT / "data/processed/product_profiles.parquet",
            ROOT / "data/processed/contextual_momentum_metrics.parquet",
            ROOT / "outputs/garment_group_business_summary.csv"]
missing = [str(p.relative_to(ROOT)) for p in REQUIRED if not p.is_file()]
if missing:
    st.error("Required data are missing: " + ", ".join(missing))
    st.info("Restore the processed files or run .venv/bin/python src/run_pipeline.py from the repository root.")
    st.stop()
signature = tuple((p.stat().st_mtime_ns, p.stat().st_size) for p in REQUIRED)


@st.cache_data(show_spinner=False)
def load_products(data_signature):
    return ProductDataStore().products()


@st.cache_data(show_spinner=False, max_entries=100)
def load_history(article_id, start, end, data_signature):
    return ProductDataStore().history(article_id, start_date=start, end_date=end)


@st.cache_data(show_spinner=False)
def load_categories(data_signature):
    return pd.read_csv(REQUIRED[2])


def reset_page():
    st.session_state.product_page = 1


def choice(label, series, key):
    return st.sidebar.selectbox(label, ["All"] + sorted(series.dropna().unique().tolist()),
                                key=key, on_change=reset_page)


def draw(fig):
    fig.update_layout(margin=dict(l=15, r=15, t=35, b=15), hovermode="x unified")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


view = st.sidebar.radio("View", ["Product explorer", "Category comparison", "Data notes"])
products = load_products(signature)

if view == "Product explorer":
    st.sidebar.subheader("Product filters")
    group = choice("Garment group", products.garment_group_name, "group")
    candidates = products if group == "All" else products.loc[products.garment_group_name.eq(group)]
    product_type = choice("Product type", candidates.product_type_name, "product_type")
    profile = choice("Lifecycle profile", products.lifecycle_profile, "profile")
    tier = choice("Momentum tier", products.momentum_tier, "tier")
    complete_only = st.sidebar.checkbox("Complete observed lifecycles only", on_change=reset_page)
    search = st.sidebar.text_input("Find article ID or product name", on_change=reset_page).strip()
    filtered = candidates
    for column, value in [("product_type_name", product_type), ("lifecycle_profile", profile), ("momentum_tier", tier)]:
        if value != "All":
            filtered = filtered.loc[filtered[column].eq(value)]
    if complete_only:
        filtered = filtered.loc[filtered.complete_lifecycle.eq(1)]
    if search:
        filtered = filtered.loc[filtered.article_id.astype(str).str.contains(search, regex=False, case=False)
                                | filtered.prod_name.str.contains(search, regex=False, case=False, na=False)]
    st.caption(f"{len(filtered):,} matching products of {len(products):,} eligible products. Product filters use whole observed histories.")
    if filtered.empty:
        st.info("No products match these filters. Clear the search or broaden a filter.")
        st.stop()
    count = 100
    pages = (len(filtered) + count - 1) // count
    if st.session_state.get("product_page", 1) > pages:
        st.session_state.product_page = 1
    page = st.sidebar.number_input("Product page", min_value=1, max_value=pages, step=1, key="product_page")
    page_rows = filtered.iloc[(page-1)*count:page*count]
    lookup = page_rows.set_index("article_id")
    article_id = st.selectbox("Article", page_rows.article_id.tolist(),
                              format_func=lambda key: f"{key} · {lookup.loc[key, 'prod_name']}")
    with st.expander("Matching product table"):
        st.caption(f"Page {page} of {pages}; up to {count} products per page. Search an exact article ID to locate it directly.")
        st.dataframe(page_rows[["article_id", "prod_name", "garment_group_name", "product_type_name", "lifecycle_profile", "momentum_tier", "total_units"]], hide_index=True, width="stretch")
    selected = lookup.loc[article_id]
    st.subheader(selected.prod_name)
    st.write(f"{article_id} · {selected.product_type_name} · {selected.garment_group_name}")
    st.write(f"**{selected.lifecycle_profile}** · {selected.momentum_tier}")
    if not selected.complete_lifecycle:
        st.info("This observed history touches a dataset boundary. Lifecycle milestones describe the available observations and may omit demand outside the dataset.")
    metrics = [("Observed units", f"{selected.total_units:,.0f}"),
               ("Observed span", f"{selected.observed_lifespan_days:,.0f} days"),
               ("Selling days", f"{selected.active_sales_days:,.0f}"),
               ("Selling-day rate", f"{selected.active_day_rate_pct:.2f}%"),
               ("Days to 50%", f"{selected.days_to_50_pct:,.0f}"),
               ("Days to 80%", f"{selected.days_to_80_pct:,.0f}"),
               ("Strongest 7-day share", f"{selected.max_7d_demand_share_pct:.2f}%"),
               ("Post-smoothed-peak share", f"{selected.post_peak_share_pct:.2f}%")]
    for offset in [0, 4]:
        for col, (label, value) in zip(st.columns(4), metrics[offset:offset+4]):
            col.metric(label, value)
    first, last = pd.Timestamp(selected.first_sale_date).date(), pd.Timestamp(selected.last_sale_date).date()
    window = st.date_input("Display dates", value=(first, last), min_value=first, max_value=last, key=f"dates_{article_id}")
    st.caption("Display dates trim chart rows only. Totals, accumulation, momentum, and same-day ranks retain their original full-history definitions. Days to milestones start at day 0.")
    if len(window) != 2:
        st.info("Select both the start and end date.")
        st.stop()
    history = load_history(article_id, window[0].isoformat(), window[1].isoformat(), signature)
    if history.empty:
        st.info("No observations in this date range.")
        st.stop()
    demand, momentum, cumulative, raw = st.tabs(["Demand", "Momentum", "Cumulative demand", "Daily data"])
    with demand:
        fig = go.Figure()
        fig.add_scatter(x=history.date, y=history.daily_units, name="Daily units", line=dict(width=1), opacity=.5)
        fig.add_scatter(x=history.date, y=history.units_ma7, name="Centered MA7", line=dict(width=2))
        for field, label, color in [("raw_peak_date", "Raw peak", "#666666"), ("smoothed_peak_date", "Smoothed peak", "#9c2f32")]:
            peak = pd.Timestamp(selected[field])
            if window[0] <= peak.date() <= window[1]:
                fig.add_vline(x=peak.isoformat(), line_dash="dot", line_color=color)
            peak_units = selected.raw_peak_daily_units if field == "raw_peak_date" else selected.peak_smoothed_demand
            st.caption(f"{label}: {peak.date()} · {peak_units:,.2f} units/day (earliest date if tied).")
        fig.update_yaxes(title_text="Units per day")
        draw(fig)
        st.caption("MA7 uses truncated windows at the observed endpoints. Peak markers outside the selected display dates are omitted.")
    with momentum:
        st.caption("Retrospective signals: centered smoothing and differences use sales up to four days ahead. These are not live forecasts. Edge NULLs remain gaps.")
        fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=.07,
                            subplot_titles=["Velocity", "Acceleration", "Velocity relative to typical active-day sales", "Same-day relative-velocity percentile"])
        for i, column in enumerate(["demand_velocity", "demand_acceleration", "velocity_pct_of_typical_day", "daily_relative_velocity_percentile"], 1):
            fig.add_scatter(x=history.date, y=history[column], name=column, row=i, col=1, connectgaps=False)
            if i < 4:
                fig.add_hline(y=0, line_width=1, line_color="#999999", row=i, col=1)
        fig.update_yaxes(range=[0, 100], row=4, col=1)
        fig.update_layout(height=800, showlegend=False)
        draw(fig)
        st.caption("Relative velocity is scaled to typical selling-day volume; it is not sales growth %. Percentiles compare valid eligible products on the same historical date.")
    with cumulative:
        fig = go.Figure()
        fig.add_scatter(x=history.date, y=history.cumulative_share_pct, name="Observed demand accumulated", fill="tozeroy")
        for field, level in [("cumulative_50_date", 50), ("cumulative_80_date", 80)]:
            milestone = pd.Timestamp(selected[field])
            fig.add_hline(y=level, line_dash="dot")
            point = history.loc[history.date.eq(milestone)]
            if not point.empty:
                fig.add_scatter(x=point.date, y=point.cumulative_share_pct, mode="markers", name=f"{level}% milestone")
            st.caption(f"First date reaching {level}%: {milestone.date()}")
        fig.update_yaxes(title_text="Full observed demand accumulated (%)", range=[0, 102])
        draw(fig)
        st.caption("Accumulation uses raw daily units. The curve can begin above zero when the displayed date range starts after the first sale.")
    with raw:
        st.dataframe(history, hide_index=True, width="stretch")
        st.download_button("Download displayed daily rows", history.to_csv(index=False),
                           file_name=f"hm_{article_id}_{window[0]}_{window[1]}.csv", mime="text/csv")

elif view == "Category comparison":
    st.subheader("Category comparison")
    categories = load_categories(signature)
    groups = st.multiselect("Garment groups", categories.garment_group_name.tolist(), default=categories.garment_group_name.tolist())
    minimum = st.number_input("Minimum complete observed lifecycles", min_value=0, value=100, step=25)
    shown = categories.loc[categories.garment_group_name.isin(groups) & categories.complete_lifecycle_articles.ge(minimum)]
    if shown.empty:
        st.info("No categories meet these selections.")
        st.stop()
    st.caption("Saved summaries for all eligible products. Product-explorer filters do not change these category populations.")
    st.write("**Lifecycle comparison — complete observed lifecycles only**")
    st.dataframe(shown[["garment_group_name", "complete_lifecycle_articles", "sustained_share_complete_pct", "rapid_spike_share_complete_pct", "long_tail_share_complete_pct", "median_max_7d_share_complete_pct", "median_days_to_80_complete"]], hide_index=True, width="stretch")
    st.write("**Volume and momentum — all eligible products**")
    st.dataframe(shown[["garment_group_name", "eligible_articles", "partial_lifecycle_articles", "total_units", "avg_units_per_article", "extreme_momentum_share_pct", "avg_peak_relative_velocity"]], hide_index=True, width="stretch")
    st.download_button("Download selected category summaries", shown.to_csv(index=False), "hm_category_summary.csv", "text/csv")
else:
    st.subheader("Data scope and definitions")
    st.markdown("""
- **Eligible products:** at least 30 selling days and 100 units across both numeric sales channels.
- **Complete observed lifecycle:** neither exact dataset boundary is touched; true launch and discontinuation remain unknown.
- **Historical data:** September 20, 2018 through September 22, 2020. Sales are observed demand, influenced by unknown availability.
- **Raw peak and smoothed peak:** distinct dates; ties choose the earliest date. Post-peak share uses the smoothed peak.
- **Relative velocity:** product-scale-adjusted change, not percentage sales growth.
- **Momentum:** retrospective, with future observations used in centered calculations.
- **Price:** anonymized index; no real revenue or profit is shown.
- **Access:** this preview reads full local histories for all eligible articles, not the 30-example export.
""")
    with st.expander("Full data contract"):
        st.markdown((ROOT / "DATA_CONTRACT.md").read_text())
