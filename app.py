import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import date
from sip_engine import (
    build_sip_transactions, calculate_portfolio, xirr,
    calculate_exit_tax, load_default_rules
)

st.set_page_config(page_title="Indian Stock SIP Calculator", page_icon="📈", layout="wide")

st.title("📈 Indian Stock SIP Return Calculator")
st.caption("Historical SIP simulator for NSE/BSE equity delivery. Charges are applied using effective-date rules.")

with st.sidebar:
    st.header("Investment")
    ticker = st.text_input("NSE ticker", "TCS").strip().upper()
    amount = st.number_input("Monthly SIP (₹)", min_value=100.0, value=5000.0, step=500.0)
    start = st.date_input("Start date", date(2018, 1, 5))
    end = st.date_input("End date", date.today())
    sip_day = st.number_input("SIP day", min_value=1, max_value=28, value=5)
    exchange = st.selectbox("Exchange", ["NSE", "BSE"])
    broker = st.selectbox("Broker profile", ["Zerodha - equity delivery"])
    tax_mode = st.selectbox("Capital gains tax", ["India individual - listed equity"])
    use_dividends = st.checkbox("Include cash dividends", value=False)

if start >= end:
    st.error("Start date must be before end date.")
    st.stop()

symbol = ticker if ticker.endswith((".NS", ".BO")) else (ticker + ".NS" if exchange == "NSE" else ticker + ".BO")

@st.cache_data(ttl=3600)
def get_history(symbol, start, end):
    df = yf.download(symbol, start=start, end=end + pd.Timedelta(days=2),
                     auto_adjust=False, progress=False)
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.reset_index()
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    return df

history = get_history(symbol, start, end)

if history.empty:
    st.error(f"No historical data found for {symbol}. Check the ticker/exchange.")
    st.stop()

st.subheader(f"{ticker} historical data")
st.line_chart(history.set_index("Date")["Close"])

rules = load_default_rules()

tx = build_sip_transactions(
    history=history,
    monthly_amount=amount,
    start_date=start,
    end_date=end,
    sip_day=int(sip_day),
    exchange=exchange,
    broker=broker,
    rules=rules,
)

if tx.empty:
    st.error("No SIP dates matched available market data.")
    st.stop()

portfolio = calculate_portfolio(tx, history, end)

gross_invested = tx["gross_sip"].sum()
charges_buy = tx["buy_total_charges"].sum()
net_cost = tx["cash_outflow"].sum()
shares = tx["shares"].sum()
market_value = portfolio["market_value"]
unrealized_gain = market_value - net_cost

c1, c2, c3, c4 = st.columns(4)
c1.metric("SIP contribution", f"₹{gross_invested:,.0f}")
c2.metric("Buy charges", f"₹{charges_buy:,.2f}")
c3.metric("Shares accumulated", f"{shares:,.4f}")
c4.metric("Current value", f"₹{market_value:,.0f}")

c5, c6, c7 = st.columns(3)
c5.metric("Net gain before exit tax", f"₹{unrealized_gain:,.0f}")
c6.metric("XIRR before exit", f"{xirr(tx['cash_outflow'], tx['trade_date'], market_value):.2f}%")
c7.metric("Last available price", f"₹{portfolio['last_price']:,.2f}")

st.subheader("Estimated sale and capital-gains tax")
tax = calculate_exit_tax(tx, portfolio["last_price"], end, rules)
e1, e2, e3, e4 = st.columns(4)
e1.metric("Estimated sell charges", f"₹{tax['sell_charges']:,.2f}")
e2.metric("Estimated capital-gains tax", f"₹{tax['capital_gains_tax']:,.2f}")
e3.metric("Net final value", f"₹{tax['net_final_value']:,.0f}")
e4.metric("Net XIRR", f"{tax['net_xirr']:.2f}%")

st.subheader("Portfolio value")
st.line_chart(portfolio["series"].set_index("Date")["market_value"])

st.subheader("SIP transaction ledger")
display_cols = [
    "trade_date", "price", "gross_sip", "brokerage", "stt",
    "exchange_charge", "sebi_charge", "stamp_duty", "gst",
    "buy_total_charges", "cash_outflow", "shares", "cumulative_shares"
]
st.dataframe(tx[display_cols], use_container_width=True, hide_index=True)

csv = tx.to_csv(index=False).encode("utf-8")
st.download_button("Download transaction CSV", csv, "sip_transactions.csv", "text/csv")

st.info(
    "Important: historical statutory rates and broker charges are maintained as effective-date rules "
    "in sip_engine.py. Review/replace the rule table with the official circular/rate applicable to your "
    "broker and account before using the result for tax or investment records."
)
