import streamlit as st

st.title("±8.70 Close Calculator")

# Input for close price
close_price = st.number_input("Enter Close Price:", value=6527.3, format="%.2f")

# Calculate
upside = close_price + 8.70
downside = close_price - 8.70

# Display results
st.write(f"📈 Close + 8.70 = **{upside:.2f}**")
st.write(f"📉 Close - 8.70 = **{downside:.2f}**")