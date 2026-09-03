import math
import numpy as np
import pandas as pd
from datetime import date

# IMPORTANT:
# This project intentionally keeps charges in an effective-date rule table.
# Rates change over time and can differ by broker/exchange/account.
# The current Zerodha equity-delivery profile uses:
# brokerage 0, STT 0.1% buy + 0.1% sell, NSE ETC 0.00307%,
# SEBI 0.0001%, GST 18% on broker/exchange/SEBI charges,
# and delivery stamp duty 0.015% on buy.
#
# Historical statutory rules should be verified from official notifications.
# Add a row with its exact effective_from date whenever a rate changes.

def load_default_rules():
    return {
        "charges": [
            # Effective from 2024-10-01: NSE equity delivery transaction charge
            # (Zerodha published rate). Earlier periods should be filled from
            # official exchange circulars for maximum historical accuracy.
            {
                "effective_from": "2024-10-01",
                "brokerage_delivery": 0.0,
                "stt_buy": 0.001,
                "stt_sell": 0.001,
                "nse_transaction": 0.0000307,
                "bse_transaction": 0.0000375,
                "sebi": 0.000001,
                "stamp_buy": 0.00015,
                "gst": 0.18,
                "dp_charge": 0.0,
            },
            {
                "effective_from": "2020-07-01",
                "brokerage_delivery": 0.0,
                "stt_buy": 0.001,
                "stt_sell": 0.001,
                "nse_transaction": 0.0000345,
                "bse_transaction": 0.0000375,
                "sebi": 0.000001,
                "stamp_buy": 0.00015,
                "gst": 0.18,
                "dp_charge": 0.0,
            },
            # Pre-2020 stamp duty was state-dependent. A national uniform
            # delivery rate is therefore NOT assumed here.
            {
                "effective_from": "2018-04-01",
                "brokerage_delivery": 0.0,
                "stt_buy": 0.001,
                "stt_sell": 0.001,
                "nse_transaction": 0.0000345,
                "bse_transaction": 0.0000375,
                "sebi": 0.000001,
                "stamp_buy": 0.0,
                "gst": 0.18,
                "dp_charge": 0.0,
            },
        ],
        "capital_gains": [
            # Listed equity, STT-paid. Rates below are basic tax rates;
            # surcharge and cess are added separately.
            {"effective_from": "2024-07-23", "stcg": 0.20, "ltcg": 0.125, "ltcg_exemption": 125000},
            {"effective_from": "2018-04-01", "stcg": 0.15, "ltcg": 0.10, "ltcg_exemption": 100000},
            # Before 1 Apr 2018, LTCG on listed equity was generally exempt
            # under section 10(38), subject to conditions.
            {"effective_from": "2005-10-01", "stcg": 0.15, "ltcg": 0.00, "ltcg_exemption": 0},
        ]
    }

def _rule_for(rules, key, d):
    rows = sorted(rules[key], key=lambda x: pd.Timestamp(x["effective_from"]))
    chosen = rows[0]
    for row in rows:
        if pd.Timestamp(row["effective_from"]).date() <= d:
            chosen = row
        else:
            break
    return chosen

def _nearest_price(history, target):
    h = history[history["Date"].dt.date >= target].sort_values("Date")
    if h.empty:
        return None, None
    row = h.iloc[0]
    return row["Close"], row["Date"].date()

def monthly_dates(start_date, end_date, day):
    p = pd.Timestamp(start_date).to_period("M")
    end_p = pd.Timestamp(end_date).to_period("M")
    out = []
    while p <= end_p:
        d = min(day, p.days_in_month)
        candidate = p.to_timestamp().date().replace(day=d)
        if start_date <= candidate <= end_date:
            out.append(candidate)
        p += 1
    return out

def calculate_buy_charges(trade_value, d, exchange, rules):
    r = _rule_for(rules, "charges", d)
    brokerage = min(r["brokerage_delivery"] * trade_value, 0.0)  # zero for retail profile

    stt = trade_value * r["stt_buy"]
    txn_rate = r["nse_transaction"] if exchange == "NSE" else r["bse_transaction"]
    exchange_charge = trade_value * txn_rate
    sebi_charge = trade_value * r["sebi"]
    stamp = trade_value * r["stamp_buy"]

    # GST is charged on brokerage + exchange transaction charges + SEBI charges.
    gst = (brokerage + exchange_charge + sebi_charge) * r["gst"]

    return {
        "brokerage": brokerage,
        "stt": stt,
        "exchange_charge": exchange_charge,
        "sebi_charge": sebi_charge,
        "stamp_duty": stamp,
        "gst": gst,
        "buy_total_charges": brokerage + stt + exchange_charge + sebi_charge + stamp + gst,
    }

def build_sip_transactions(history, monthly_amount, start_date, end_date, sip_day,
                            exchange, broker, rules):
    history = history.copy()
    history["Date"] = pd.to_datetime(history["Date"]).dt.tz_localize(None)

    rows = []
    for requested_date in monthly_dates(start_date, end_date, sip_day):
        price, execution_date = _nearest_price(history, requested_date)
        if price is None or float(price) <= 0:
            continue

        # The SIP amount is treated as total cash budget including buy-side
        # transaction costs. Shares = net cash available / price.
        price = float(price)
        base = monthly_amount
        approx_charges = calculate_buy_charges(base, execution_date, exchange, rules)
        net_for_stock = max(base - approx_charges["buy_total_charges"], 0)
        shares = net_for_stock / price
        actual_trade_value = shares * price
        charges = calculate_buy_charges(actual_trade_value, execution_date, exchange, rules)
        # Recompute once with actual trade value; for proportional charges this
        # is already consistent. Fixed brokerage/DP charges can be added here.
        cash_outflow = actual_trade_value + charges["buy_total_charges"]

        rows.append({
            "requested_date": requested_date,
            "trade_date": execution_date,
            "price": price,
            "gross_sip": monthly_amount,
            **charges,
            "cash_outflow": cash_outflow,
            "shares": shares,
        })

    tx = pd.DataFrame(rows)
    if tx.empty:
        return tx
    tx["cumulative_shares"] = tx["shares"].cumsum()
    return tx

def calculate_portfolio(tx, history, end_date):
    last = history[history["Date"].dt.date <= end_date].sort_values("Date").iloc[-1]
    last_price = float(last["Close"])
    dates = pd.date_range(tx["trade_date"].min(), end_date, freq="D")
    series = pd.DataFrame({"Date": dates})
    series["market_value"] = tx["shares"].sum() * last_price
    return {
        "last_price": last_price,
        "market_value": float(tx["shares"].sum() * last_price),
        "series": series,
    }

def xirr(cashflows, dates, terminal_value):
    cf = [-float(x) for x in cashflows] + [float(terminal_value)]
    ds = [pd.Timestamp(d).date() for d in dates] + [pd.Timestamp(dates.iloc[-1]).date()]
    t0 = ds[0]
    years = np.array([(d - t0).days / 365.0 for d in ds], dtype=float)

    def npv(rate):
        return np.sum(np.array(cf) / np.power(1.0 + rate, years))

    low, high = -0.9999, 10.0
    f_low, f_high = npv(low), npv(high)
    if f_low * f_high > 0:
        return float("nan")

    for _ in range(200):
        mid = (low + high) / 2
        f_mid = npv(mid)
        if abs(f_mid) < 1e-9:
            return mid * 100
        if f_low * f_mid <= 0:
            high, f_high = mid, f_mid
        else:
            low, f_low = mid, f_mid
    return ((low + high) / 2) * 100

def calculate_exit_tax(tx, sell_price, sell_date, rules):
    # FIFO tax-lot calculation.
    lots = []
    for _, row in tx.sort_values("trade_date").iterrows():
        lots.append({
            "date": pd.Timestamp(row["trade_date"]).date(),
            "qty": float(row["shares"]),
            "cost": float(row["cash_outflow"]) / max(float(row["shares"]), 1e-12)
        })

    gross_sale = sum(x["qty"] for x in lots) * sell_price
    sell_rule = _rule_for(rules, "charges", sell_date)
    sell_stt = gross_sale * sell_rule["stt_sell"]
    txn_rate = sell_rule["nse_transaction"]
    sell_exchange = gross_sale * txn_rate
    sell_sebi = gross_sale * sell_rule["sebi"]
    sell_gst = (sell_exchange + sell_sebi) * sell_rule["gst"]
    # DP charge varies by broker/account and is intentionally 0 in the default
    # profile; add it to the rule table if applicable.
    sell_charges = sell_stt + sell_exchange + sell_sebi + sell_gst

    # Simplified lot-wise Indian listed-equity tax.
    # Tax rate is selected based on the sale date for the current law.
    cg_rule = _rule_for(rules, "capital_gains", sell_date)
    stcg = 0.0
    ltcg = 0.0

    for lot in lots:
        proceeds = lot["qty"] * sell_price
        cost = lot["qty"] * lot["cost"]
        gain = max(proceeds - cost, 0.0)
        holding_days = (sell_date - lot["date"]).days
        if holding_days > 365:
            ltcg += gain
        else:
            stcg += gain

    taxable_ltcg = max(0.0, ltcg - cg_rule["ltcg_exemption"])
    capital_gains_tax = stcg * cg_rule["stcg"] + taxable_ltcg * cg_rule["ltcg"]

    net_final = gross_sale - sell_charges - capital_gains_tax
    net_xirr = xirr(tx["cash_outflow"], tx["trade_date"], net_final)

    return {
        "gross_sale": gross_sale,
        "sell_charges": sell_charges,
        "stcg_gain": stcg,
        "ltcg_gain": ltcg,
        "capital_gains_tax": capital_gains_tax,
        "net_final_value": net_final,
        "net_xirr": net_xirr,
    }
