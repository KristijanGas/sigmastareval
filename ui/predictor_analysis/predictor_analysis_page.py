
import streamlit as st



TITLE = "Predictor Performance Analysis"


def render_page():
    st.set_page_config(page_title=TITLE, layout="wide")
    st.title(TITLE)



render_page()