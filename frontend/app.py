import requests
import streamlit as st

import os
API_URL = os.environ.get("API_URL", "https://rag-agent-1rua.onrender.com")

st.set_page_config(page_title="FilingsIQ", page_icon="📊")

st.title("FilingsIQ")
st.caption("Ask questions about SEC 10-K filings — numeric facts, business risks, or comparisons.")

question = st.text_input(
    "Your question",
    placeholder="e.g. What was Apple's net income in 2024?",
)

if st.button("Ask", type="primary"):
    if not question.strip():
        st.warning("Please type a question first.")
    else:
        with st.spinner("Thinking..."):
            try:
                resp = requests.post(
                    f"{API_URL}/query",
                    json={"question": question},
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
            except requests.exceptions.ConnectionError:
                st.error("Can't reach the API. Is the backend running on port 8000?")
                st.stop()
            except Exception as e:
                st.error(f"Something went wrong: {e}")
                st.stop()

        if data.get("declined"):
            st.info(f"I can't answer that. Reason: {data.get('reason')}")
        else:
            st.markdown("### Answer")
            st.markdown(data.get("synthesis", "(no answer)").replace("$", "\\$"))

        with st.expander("How it answered (details)"):
            st.json(data)
