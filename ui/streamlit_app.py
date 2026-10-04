"""Streamlit demo UI.  Run:  streamlit run ui/streamlit_app.py"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from triage.models import TriageRequest  # noqa: E402
from triage.service import get_service  # noqa: E402

st.set_page_config(page_title="AI Fault Triage Assistant", page_icon="🛠️", layout="wide")


@st.cache_resource
def service():
    return get_service()


svc = service()

st.title("AI Network Fault Triage Assistant")
st.caption(
    f"Mode: **{'LLM agent' if svc.use_llm else 'offline (retrieval only)'}** · "
    f"Embedder: `{svc.kb.embedder.name}` · {svc.kb.count()} past faults indexed"
)

EXAMPLES = [
    "BGP session with our ISP keeps dropping every few minutes",
    "Whole 3rd floor lost network and MAC addresses are flapping",
    "Users can ping IPs but websites don't open by name",
    "Rx light level on the uplink SFP is around -25 dBm",
]

from triage.offline import category_label as label  # noqa: E402


example = st.selectbox("Try an example", ["(type your own)"] + EXAMPLES)

with st.form("triage"):
    description = st.text_area(
        "Describe the fault", value="" if example == "(type your own)" else example, height=110)
    col1, col2 = st.columns(2)
    device = col1.text_input("Device (optional)", placeholder="router-blr-01")
    create_ticket = col2.checkbox("Allow the assistant to open a ticket")
    submitted = st.form_submit_button("Triage", type="primary")

if submitted:
    if len(description.strip()) < 5:
        st.warning("Please describe the fault in a few words.")
        st.stop()
    with st.spinner("Searching past faults and analysing..."):
        result = svc.triage(TriageRequest(
            description=description, device_name=device or None, create_ticket=create_ticket))

    m1, m2, m3 = st.columns(3)
    m1.metric("Likely category", label(result.likely_category))
    m2.metric("Suggested severity", result.suggested_severity)
    m3.metric("Confidence", f"{result.confidence:.0%}")

    if result.summary:
        st.info(result.summary)
    st.subheader("Likely root cause")
    st.write(result.likely_root_cause)
    st.subheader("Fixes that resolved similar faults")
    for i, step in enumerate(result.recommended_steps, 1):
        st.write(f"{i}. {step}")

    if result.actions_taken:
        st.subheader("Actions taken")
        st.json(result.actions_taken)

    st.subheader("Similar past faults (evidence)")
    st.dataframe(
        [{"id": f["id"], "similarity": f["similarity"], "title": f["title"],
          "category": label(f["category"]), "root cause": f["root_cause"], "resolution": f["resolution"],
          "cited": "✓" if f["id"] in result.cited_fault_ids else ""}
         for f in result.similar_faults],
        width="stretch", hide_index=True,
    )
