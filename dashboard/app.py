from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


# --------------------------------------------------
# Page setup
# --------------------------------------------------

st.set_page_config(
    page_title="H&M Fashion Demand Momentum",
    page_icon="📈",
    layout="wide",
)


# --------------------------------------------------
# Paths
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"


# --------------------------------------------------
# Load data
# --------------------------------------------------

@st.cache_data
def load_csv(filename):
    return pd.read_csv(OUTPUT_DIR / filename)


lifecycle_profiles = load_csv(
    "lifecycle_profile_counts.csv"
)

momentum_tiers = load_csv(
    "momentum_tier_counts.csv"
)

garment_summary = load_csv(
    "garment_group_business_summary.csv"
)

surge_comparison = load_csv(
    "nov2019_period_comparison.csv"
)


# --------------------------------------------------
# Header
# --------------------------------------------------

st.title("H&M Fashion Demand Momentum Analysis")

st.caption(
    "Exploring how fashion products gain, sustain, and lose "
    "demand using 31.8M H&M transactions from 2018–2020."
)


# --------------------------------------------------
# KPI calculations
# --------------------------------------------------

total_articles = int(
    lifecycle_profiles["articles"].sum()
)

total_units = int(
    lifecycle_profiles["total_units"].sum()
)


sustained_row = lifecycle_profiles.loc[
    lifecycle_profiles["lifecycle_profile"]
    == "Sustained Performer"
].iloc[0]


extreme_row = momentum_tiers.loc[
    momentum_tiers["momentum_tier"]
    == "Extreme Momentum"
].iloc[0]


sustained_articles = int(
    sustained_row["articles"]
)

sustained_share = float(
    sustained_row["pct_articles"]
)

extreme_articles = int(
    extreme_row["articles"]
)

extreme_share = float(
    extreme_row["pct_articles"]
)


# --------------------------------------------------
# KPI cards
# --------------------------------------------------

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Momentum-eligible articles",
    f"{total_articles:,}",
)

col2.metric(
    "Units represented",
    f"{total_units:,}",
)

col3.metric(
    "Sustained performers",
    f"{sustained_articles:,}",
    f"{sustained_share:.2f}% of articles",
)

col4.metric(
    "Extreme-momentum articles",
    f"{extreme_articles:,}",
    f"{extreme_share:.2f}% of articles",
)


st.divider()


# --------------------------------------------------
# Lifecycle profile distribution
# --------------------------------------------------

st.subheader("How H&M product demand behaves over time")

st.caption(
    "Products are classified using demand concentration, "
    "accumulation speed, post-peak behavior, and lifecycle "
    "completeness."
)


profile_order = [
    "Sustained Performer",
    "Slow Burn",
    "Balanced Lifecycle",
    "Long Tail",
    "Rapid Spike",
    "Partial Lifecycle",
]


profile_chart_data = (
    lifecycle_profiles
    .set_index("lifecycle_profile")
    .reindex(profile_order)
    .reset_index()
)


profile_fig = px.bar(
    profile_chart_data,
    x="lifecycle_profile",
    y="pct_articles",
    text="pct_articles",
    labels={
        "lifecycle_profile": "Lifecycle profile",
        "pct_articles": "Share of articles (%)",
    },
)


profile_fig.update_traces(
    texttemplate="%{text:.1f}%",
    textposition="outside",
)


profile_fig.update_layout(
    showlegend=False,
    xaxis_title="",
    yaxis_title="Share of eligible articles (%)",
)


st.plotly_chart(
    profile_fig,
    use_container_width=True,
    config={"displayModeBar": False},
)


# --------------------------------------------------
# Category comparison
# --------------------------------------------------

st.divider()

st.subheader(
    "Which garment groups produce more sustained demand?"
)

st.caption(
    "Sustained Performer share uses only products with "
    "fully observed lifecycles."
)


category_chart_data = (
    garment_summary[
        garment_summary["complete_lifecycle_articles"] >= 100
    ]
    .sort_values(
        "sustained_share_complete_pct",
        ascending=False,
    )
    .head(10)
)


category_fig = px.bar(
    category_chart_data,
    x="sustained_share_complete_pct",
    y="garment_group_name",
    orientation="h",
    text="sustained_share_complete_pct",
    labels={
        "garment_group_name": "",
        "sustained_share_complete_pct":
            "Sustained Performer share (%)",
    },
)


category_fig.update_traces(
    texttemplate="%{text:.1f}%",
    textposition="outside",
)


category_fig.update_layout(
    yaxis={
        "categoryorder": "total ascending"
    },
    showlegend=False,
)


st.plotly_chart(
    category_fig,
    use_container_width=True,
    config={"displayModeBar": False},
)


# --------------------------------------------------
# Momentum category comparison
# --------------------------------------------------

st.divider()

st.subheader(
    "Which garment groups show the sharpest momentum?"
)

momentum_chart_data = (
    garment_summary[
        garment_summary["complete_lifecycle_articles"] >= 100
    ]
    .sort_values(
        "extreme_momentum_share_pct",
        ascending=False,
    )
    .head(10)
)


momentum_fig = px.bar(
    momentum_chart_data,
    x="extreme_momentum_share_pct",
    y="garment_group_name",
    orientation="h",
    text="extreme_momentum_share_pct",
    labels={
        "garment_group_name": "",
        "extreme_momentum_share_pct":
            "Extreme Momentum share (%)",
    },
)


momentum_fig.update_traces(
    texttemplate="%{text:.1f}%",
    textposition="outside",
)


momentum_fig.update_layout(
    yaxis={
        "categoryorder": "total ascending"
    },
    showlegend=False,
)


st.plotly_chart(
    momentum_fig,
    use_container_width=True,
    config={"displayModeBar": False},
)


# --------------------------------------------------
# Late-November demand event
# --------------------------------------------------

st.divider()

st.subheader(
    "A demand surge can begin before sales reach their peak"
)


surge_fig = px.bar(
    surge_comparison,
    x="period",
    y="avg_daily_units",
    text="avg_daily_units",
    labels={
        "period": "",
        "avg_daily_units": "Average daily units",
    },
)


surge_fig.update_traces(
    texttemplate="%{text:,.0f}",
    textposition="outside",
)


surge_fig.update_layout(
    showlegend=False,
)


st.plotly_chart(
    surge_fig,
    use_container_width=True,
    config={"displayModeBar": False},
)


prior_row = surge_comparison[
    surge_comparison["period"]
    == "Prior 28 Days"
].iloc[0]


event_row = surge_comparison[
    surge_comparison["period"]
    == "Late Nov / Early Dec 2019"
].iloc[0]


daily_unit_change = (
    (
        event_row["avg_daily_units"]
        / prior_row["avg_daily_units"]
    )
    - 1
) * 100


st.info(
    f"Average daily demand increased by approximately "
    f"{daily_unit_change:.1f}% during the late-November / "
    f"early-December window compared with the prior 28 days. "
    f"Product-level momentum began strengthening before the "
    f"catalog reached its highest sales volume."
)


# --------------------------------------------------
# Methodology note
# --------------------------------------------------

st.divider()

st.subheader("How momentum is measured")

st.markdown(
    """
    **Demand velocity** measures how quickly a product's
    smoothed daily demand is changing.

    **Demand acceleration** measures whether that rate of
    change is itself strengthening or weakening.

    **Cumulative lifecycle demand** measures how sales build
    across the full observed product lifecycle.

    These concepts correspond to rate-of-change and
    accumulation ideas from calculus, implemented with
    discrete daily retail data.
    """
)