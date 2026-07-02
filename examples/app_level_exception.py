from __future__ import annotations

import streamlit as st

st.title("App-level exception sample")
st.write("Click the button to raise during top-level Streamlit script execution.")

if st.button("Raise exception", type="primary"):
    raise RuntimeError(
        "Intentional app-level exception for testing streamlit-remote traceback width."
    )
