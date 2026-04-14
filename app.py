# ======================
# REAL-TIME SIGNAL
# ======================

# آخرین کندل (در حال تشکیل)
live = yf.download("BTC-USD", period="1d", interval="1m")

if isinstance(live.columns, pd.MultiIndex):
    live.columns = live.columns.get_level_values(0)

live_price = live["Close"].dropna().iloc[-1]

# آخرین کندل 4 ساعته
last_row = df.iloc[-1].copy()

# جایگزین قیمت با لایو
last_row["Close"] = live_price

# محاسبه اندیکاتور روی همین کندل زنده
ema200 = df["EMA200"].iloc[-1]
rsi = df["RSI"].iloc[-1]

# سیگنال قبل از بسته شدن کندل
live_signal = (live_price > ema200) and (rsi < 45)

# نمایش
st.subheader("🔥 REAL-TIME SIGNAL")

if live_signal:
    st.success(f"BUY NOW @ {live_price:.2f}")
else:
    st.warning("WAIT")

st.metric("💰 Live Price", f"{live_price:.2f}")
