
from pathlib import Path
import sys
import streamlit as st

#APP_TITLE = "Bot Performance Analysis"

# To install required modules: python -m pip install -r requirements-streamlit.txt
# Run command: streamlit run streamlit-app.py




def main() -> None:
   # st.set_page_config(page_title=APP_TITLE, layout="wide")
   # st.title(APP_TITLE)

   bot_analysis_page = st.Page(
      "ui/bot_analysis/analysis_page.py",
      title="Bot Analysis",
      icon="📊",
   )

   comparison_page = st.Page(
      "ui/bot_analysis/comparison_page.py",
      title="Run Comparison",
      icon="⚖️",
   )

   predictor_analysis_page = st.Page(
      "ui/predictor_analysis/predictor_analysis_page.py",
      title="Predictor Analysis",
      icon="📈",
   )


   page = st.navigation({
      "Bot Analysis": [
         bot_analysis_page,
         comparison_page,
      ],
      "Predictor Analysis": [
         predictor_analysis_page,
      ],
      # "Data": [
      #    data_page,
      # ],
   })

   page.run()

if __name__ == "__main__":
   main()


