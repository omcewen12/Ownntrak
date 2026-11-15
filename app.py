"""OwnnTrak by OSH Ventures: Streamlit front end for the ownership mapper."""
from __future__ import annotations

import os
import re

import pandas as pd
import streamlit as st

from ubo_mapper import theme
from ubo_mapper.analysis import build_ownership
from ubo_mapper.client import CompaniesHouseClient, CompaniesHouseError, normalise_company_number
from ubo_mapper.demo import DEMO_LABELS, DemoProvider
from ubo_mapper.graph import to_dot
from ubo_mapper.rag import DIMENSIONS
from ubo_mapper.report import CLASS_LABELS, LIMITATIONS, company_rows, to_json, to_markdown

st.set_page_config(page_title="OwnnTrak by OSH Ventures", layout="wide")
st.markdown(theme.css_block(), unsafe_allow_html=True)

RAG_ICONS = {"GREEN": "\U0001F7E2", "AMBER": "\U0001F7E0", "RED": "\U0001F534"}
DEMO_MODE = "Demo data (fictional)"
LIVE_MODE = "Live Companies House data"


def stored_api_key() -> str:
    """Key from Streamlit secrets or the environment, never from the repo."""
    try:
        key = st.secrets.get("COMPANIES_HOUSE_API_KEY")
    except Exception:  # no secrets file present
        key = None
    return key or os.environ.get("COMPANIES_HOUSE_API_KEY", "")


# ---------------------------------------------------------------- sidebar
st.sidebar.markdown(theme.sidebar_brand(), unsafe_allow_html=True)
mode = st.sidebar.radio("Data source", [DEMO_MODE, LIVE_MODE])

if mode == DEMO_MODE:
    choice = st.sidebar.selectbox("Scenario", list(DEMO_LABELS), format_func=lambda k: DEMO_LABELS[k])
    company_input = choice
    api_key = ""
else:
    company_input = st.sidebar.text_input("Company number", placeholder="e.g. 00445790")
    api_key = stored_api_key()
    if api_key:
        st.sidebar.caption("Using the API key stored in this app's secrets.")
    else:
        api_key = st.sidebar.text_input(
            "Companies House REST API key", type="password",
            help="Used for this session only. It is not saved anywhere.",
        )

max_depth = st.sidebar.slider("Ownership levels to follow", 1, 6, 4)
include_ceased = st.sidebar.checkbox("Show ceased PSCs (history only)")
run = st.sidebar.button("Trace ownership", type="primary")

# ------------------------------------------------------------------- main
st.markdown(theme.hero(), unsafe_allow_html=True)

if run:
    number = normalise_company_number(company_input)
    if not re.fullmatch(r"[A-Z0-9]{6,8}", number):
        st.error("Enter a Companies House number of six to eight letters and digits.")
    elif mode == LIVE_MODE and not api_key:
        st.error("Add a Companies House REST API key in the sidebar, or switch to the demo data.")
    else:
        provider = DemoProvider() if mode == DEMO_MODE else CompaniesHouseClient(api_key)
        source = "Fictional demo data" if mode == DEMO_MODE else "Companies House API"
        try:
            with st.spinner("Tracing ownership..."):
                st.session_state["result"] = build_ownership(
                    provider, number, max_depth=max_depth, include_ceased=include_ceased, source=source,
                )
        except CompaniesHouseError as error:
            st.session_state.pop("result", None)
            st.error(str(error))

result = st.session_state.get("result")

if result is None:
    st.info("Choose a scenario or enter a company number in the sidebar, then select **Trace ownership**.")
    st.stop()

root = result.root
st.markdown(
    theme.company_header(root.name, root.company_number, root.status, result.source, result.generated_at),
    unsafe_allow_html=True,
)

rag_columns = st.columns([1.3, 1, 1, 1, 1])
rag_columns[0].markdown(
    theme.rag_card("Overall", result.overall_rag, result.overall_reasons, overall=True), unsafe_allow_html=True,
)
for column, (key, _label) in zip(rag_columns[1:], DIMENSIONS):
    item = result.rag[key]
    column.markdown(theme.rag_card(item["label"], item["rag"], item["reasons"]), unsafe_allow_html=True)
st.write("")

high = len(result.flags_by_severity("HIGH"))
medium = len(result.flags_by_severity("MEDIUM"))
columns = st.columns(4)
cards = [
    ("Natural persons found", len(result.people), theme.SAGE_LIGHT),
    ("Unresolved owners", len(result.unresolved), theme.PINK),
    ("High flags", high, theme.CORAL),
    ("Medium flags", medium, theme.CLAY),
]
for column, (label, value, colour) in zip(columns, cards):
    column.markdown(theme.stat_card(label, value, colour), unsafe_allow_html=True)

st.write("")
tab_map, tab_people, tab_companies, tab_unresolved, tab_flags, tab_export = st.tabs(
    ["Ownership map", "People", "Companies and filings", "Unresolved owners", "Red flags", "Export and method"]
)

with tab_map:
    st.graphviz_chart(to_dot(result), use_container_width=True)
    st.caption(
        "Arrows run from owner to owned company, labelled with the published percentage band. "
        "Terracotta is the target and ovals are people. A person's outline shows their Companies House identity "
        "verification (green verified, amber not yet, coral overdue). A dashed pink box is an owner the register "
        "cannot look through, and a coral outline marks a high severity flag."
    )

with tab_people:
    if not result.people:
        st.warning("No natural persons could be identified from public data.")
    else:
        rows = [{
            "Person": p.name,
            "Low %": p.low,
            "High %": p.high,
            "Assessment": CLASS_LABELS[p.classification],
            "Identity verification (Companies House)": f"{RAG_ICONS.get(p.idv_rag, '')} {p.idv_label or 'Not assessed'}".strip(),
            "Levels up": p.layers,
            "Residence": p.residence or "",
            "Born": p.birth or "",
        } for p in result.people]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        for p in result.people:
            with st.expander(f"How {p.name} connects to {root.name}"):
                for route in p.routes + p.control_routes:
                    st.write(route)
        st.caption(
            "Ranges multiply the published bands along each chain and add up separate chains. "
            "A person is a likely UBO only when even the low end reaches 25%."
        )

with tab_companies:
    rows = company_rows(result)
    if not rows:
        st.info("No filing information was returned for the companies in this structure.")
    else:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption(
            "Accounts and confirmation statement dates come from each company's profile. "
            "An overdue filing is a high flag, and one due within 30 days is a medium flag."
        )

with tab_unresolved:
    if not result.unresolved:
        st.success("Every owner was traced to a natural person.")
    else:
        rows = [{
            "Entity": u.name,
            "Country": u.country or "",
            "Up to %": u.high,
            "Why unresolved": u.reason,
        } for u in result.unresolved]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption("These owners need to be followed up outside the public register, for example through their own filings or the customer.")

with tab_flags:
    if not result.flags:
        st.success("No red flags raised.")
    for flag in result.flags:
        st.markdown(theme.flag_card(flag.severity, flag.title, flag.detail), unsafe_allow_html=True)

with tab_export:
    st.download_button("Download working paper (Markdown)", to_markdown(result),
                       file_name=f"ownntrak_{root.company_number}.md", mime="text/markdown")
    st.download_button("Download full data (JSON)", to_json(result),
                       file_name=f"ownntrak_{root.company_number}.json", mime="application/json")
    with st.expander("Method and limitations", expanded=True):
        for item in LIMITATIONS:
            st.write(f"- {item}")
