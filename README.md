# Indian Stock SIP Return Calculator

A Streamlit application that simulates a monthly SIP in an Indian NSE/BSE listed stock using historical market prices and an effective-date charge/tax rule engine.

## Features

- NSE/BSE ticker input
- Monthly SIP amount
- Custom start/end date
- Custom SIP day
- Historical daily prices through Yahoo Finance
- Next available trading day execution when the requested SIP date is a holiday/weekend
- Equity-delivery brokerage model
- STT
- Exchange transaction charges
- SEBI turnover fee
- Stamp duty
- GST
- Historical effective-date rule structure
- FIFO capital-gains estimate
- STCG/LTCG split
- XIRR
- Transaction ledger
- CSV export
- Portfolio-value chart

## Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Important accuracy notes

This is an analytical simulator, not a tax filing engine.

The most important part is `load_default_rules()` in `sip_engine.py`. It contains effective-date rules so that charges are selected according to the trade date rather than blindly using today's rate.

Before relying on historical results, extend the rule table using official exchange/government/broker circulars for every rate-change period relevant to the dates you test.

### Why this matters

- STT rates can change.
- Exchange transaction charges can change.
- Stamp duty changed to a centrally collected regime from 1 July 2020.
- Brokerage depends on broker/account/order type.
- BSE charges can differ from NSE.
- DP charges may apply when selling.
- Capital-gains tax depends on the sale date and the holding period of each lot.
- Surcharge and health & education cess can depend on the taxpayer's circumstances.
- Corporate actions such as splits, bonuses, mergers and demergers need proper cost-basis treatment.

### Current statutory reference

NSE publishes current SEBI turnover fees, stamp duty, GST and STT information. Zerodha publishes its current equity-delivery charge schedule and historical change notices.

Use those official sources when updating the rule table.

## Data limitations

Yahoo Finance is used only as the historical-price provider in this starter implementation. For production-grade financial analysis, use a licensed NSE/BSE data source or a broker/API data source with corporate-action-adjusted historical data.

The app currently does not automatically process every corporate action. For long historical periods, this can materially affect SIP calculations.

## Recommended production upgrades

1. Replace Yahoo Finance with a licensed historical data source.
2. Add a corporate-actions table:
   - split
   - bonus
   - rights
   - merger
   - demerger
3. Store all rates in CSV/SQLite/PostgreSQL instead of hard-coding them.
4. Add broker profiles for Zerodha, Groww, Upstox, Angel One, etc.
5. Add exact historical DP charges.
6. Add surcharge + 4% cess.
7. Add grandfathering for eligible LTCG shares acquired before 31 Jan 2018.
8. Add dividends and dividend-tax handling.
9. Add tax-lot report and FIFO/LIFO options where legally appropriate.
10. Add NSE/BSE holiday calendars so execution dates are exchange-accurate.
11. Add a test suite with known contract-note examples.

## Disclaimer

This software is for educational and analytical use. It does not constitute investment, accounting, or tax advice. Verify statutory rates, broker charges, corporate actions and tax treatment against the applicable official documents before using results for financial decisions or tax reporting.
