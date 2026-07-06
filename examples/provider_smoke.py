from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

st.set_page_config(page_title="Provider smoke test")

if "click_count" not in st.session_state:
    st.session_state.click_count = 0

st.title("Provider smoke test")
st.write("Use this app to verify a tunnel provider with Streamlit's live connection.")

rendered_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
st.metric("Button clicks", st.session_state.click_count)
st.caption(f"Rendered at {rendered_at}")

message = st.text_input("Echo text", value="hello")
st.write(f"Echo: {message}")

left, right = st.columns(2)
with left:
    if st.button("Increment", type="primary"):
        st.session_state.click_count += 1
        st.rerun()

with right:
    if st.button("Rerun"):
        st.rerun()

enabled = st.toggle("Show success message")
if enabled:
    st.success("Widget state updated through the remote connection.")

with st.expander("Pass criteria"):
    st.markdown(
        """
        - The remote HTTPS URL opens this page.
        - Typing in the text input updates the echo text.
        - The increment button updates the counter and keeps session state.
        - The rerun button refreshes the rendered timestamp.
        - No disconnected/reconnecting banner remains visible.
        """
    )
