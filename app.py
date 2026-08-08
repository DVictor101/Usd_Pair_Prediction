import streamlit as st
import pandas as pd
import joblib

model = joblib.load("./Models/best_catboost.pkl")
preprocessor = joblib.load("./Models/preprocessor.pkl")

st.title("USD/JPY News Impact Prediction System")

st.write(

"""
Predict the expected impact of macroeconomic news releases
on the USD/JPY exchange rate using Machine Learning.

"""

)

# user inputs
Year = st.text_input(
    "Year",
    "2024"
)
# user inputs
Month = st.text_input(
    "Month",
    "jan"
)

# user inputs
Day = st.text_input(
    "Day",
    "Mon"
)


# user inputs
Time = st.text_input(
    "Time",
    "13:30"
)

currency = st.selectbox(
    "currency",
    ["USD", "JPY"]
)

event = st.text_input(
    "News Event",
    "Non-Farm Payrolls"
)

actual = st.text_input(
    "Actual Value"
)

previous = st.text_input(
    "Previous Value"
)

Close_5min_before = st.number_input(
    "Price 5 Minutes Before",
    format="%.5f"
)

Close_at_release = st.number_input(
    "Price At Release",
    format="%.5f"
)


## input data form

input_data = pd.DataFrame({

    "Year":[Year],

    "Month":[Month],

    "Day":[Day],

    "Time":[Time],

    "currency":[currency],

    "event":[event],

    "actual":[actual],

    "previous":[previous],

    "Close_5min_before":[Close_5min_before],

    "Close_at_release":[Close_at_release]

})

#applying preprocessing
processed = preprocessor.transform(input_data)
print(processed.shape)
#make prediction
prediction = model.predict(processed)

##display prediction

st.subheader("Prediction")

st.success(f"Predicted 48-Hour Price Change: {prediction[0]:.5f}")

