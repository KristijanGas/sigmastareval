import streamlit as st

#APP_TITLE = "Bot Performance Analysis"

# To install required modules: python -m pip install -r requirements-streamlit.txt
# Run command: streamlit run streamlit-app.py




def main() -> None:
   st.set_page_config(page_title="Bot Evaluator", layout="wide")
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

   live_passive_trading_page = st.Page(
      "ui/passive_trading/live_dashboard_page.py",
      title="Live Passive Trading",
      icon="🟢",
   )

   model_training_page = st.Page(
      "ui/predictor_analysis/model_training_page.py",
      title="Model Training",
      icon="🦾",
   )

   # model_evalutaion_page = st.Page(
   #    "ui/predictor_analysis/model_evaluation_page.py",
   #    title="Model Evaluation",
   #    icon="📈",
   # )


   page = st.navigation({
      "Bot Analysis": [
         bot_analysis_page,
         comparison_page,
      ],
      "Passive Trading": [
         live_passive_trading_page,
      ],
      "Prediction Models": [
         model_training_page,
         #model_evalutaion_page,
      ],

   })

   page.run()

if __name__ == "__main__":
   main()


