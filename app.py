"""RAG Context Tree — internal dashboard for visualizing RAG pipeline reasoning."""

import streamlit as st

st.set_page_config(
    page_title="RAG Context Tree",
    page_icon="\U0001f333",
    layout="wide",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* Metric card styling (indigo border, matching analytics-dashboard) */
    div[data-testid="stMetric"] {
        background: #1a1a2e;
        border-left: 3px solid #6366f1;
        padding: 12px 16px;
        border-radius: 4px;
    }
    div[data-testid="stMetric"] label {
        color: #94a3b8;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #fafafa;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 4px;
        padding: 8px 16px;
    }

    /* Remove default streamlit padding */
    .block-container {
        padding-top: 2rem;
    }

    /* Selectbox / input dark theme polish */
    .stSelectbox > div > div,
    .stTextInput > div > div > input {
        background: #1a1a2e;
        border-color: #334155;
    }

    /* Expander styling */
    .streamlit-expanderHeader {
        background: #1a1a2e;
        border-radius: 4px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Main App ───────────────────────────────────────────────────────────────────
st.markdown("# RAG Context Tree")

tab_tree, tab_diff, tab_flow, tab_audit, tab_prompts, tab_replay = st.tabs([
    "Context Tree",
    "Daily Diff",
    "Tweet Flow",
    "Audit",
    "Prompts",
    "Activation Replay",
])

with tab_tree:
    from tabs.tree_view import render as render_tree_view
    render_tree_view()

with tab_diff:
    from tabs.daily_diff import render as render_daily_diff
    render_daily_diff()

with tab_flow:
    from tabs.tweet_flow_tab import render as render_tweet_flow
    render_tweet_flow()

with tab_audit:
    from tabs.audit import render as render_audit
    render_audit()

with tab_prompts:
    from tabs.prompts_view import render as render_prompts
    render_prompts()

with tab_replay:
    from tabs.activation_replay import render as render_activation_replay
    render_activation_replay()
