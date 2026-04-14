import streamlit as st
import pandas as pd
import requests

st.set_page_config(layout="wide", page_title="Fast Trade Panel")

# ======================
# تابع دریافت دیتا (با کش برای سرعت)
# ======================
@st.cache_data(ttl=60)
def fetch_data():
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 100}
    try:
        data = requests.get(url, params=params).json()
        df = pd.DataFrame(data).iloc[:, :5]
        df.columns = ["Time", "Open", "High", "Low", "Close"]
        df["Time"] = pd.to_datetime(df["Time"], unit="ms")
        df[["Open", "High", "Low", "Close"]] = df[["Open", "High", "Low", "Close"]].astype(float)
        return df
    except:
        return pd.DataFrame()

# ======================
# بدنه اصلی برنامه
# ======================
st.title("🚀 پنل سریع BTC")

# دکمه آپدیت دستی برای جلوگیری از لود بی وقفه
if st.button("🔄 آپدیت قیمت‌ها"):
    st.cache_data.clear()
    st.rerun()

df = fetch_data()

if not df.empty:
    # محاسبات سریع بدون حلقه For سنگین
    df['Prev_Close'] = df['Close'].shift(1)
    df['Prev2_Close'] = df['Close'].shift(2)
    
    # تعیین سیگنال
    df['Signal'] = "WAIT"
    mask = df['Prev_Close'] > df['Prev2_Close']
    df.loc[mask, 'Signal'] = "TRADE"
    
    # محاسبه سود و هدف
    df['Target'] = df['Open'] + (df['Prev_Close'] - df['Prev2_Close'])
    df['PnL%'] = ((df['Close'] - df['Open']) / df['Open']) * 100
    
    # تمیزکاری برای نمایش
    view_df = df[['Time', 'Open', 'Close', 'Signal', 'Target', 'PnL%']].copy()
    view_df['Time'] = view_df['Time'].dt.strftime('%m-%d %H:%M')
    
    # نمایش در یک جدول شیک و سریع
    st.dataframe(
        view_df.sort_index(ascending=False),
        use_container_width=True,
        height=500,
        column_config={
            "PnL%": st.column_config.NumberColumn(format="%.2f%%"),
            "Signal": st.column_config.TextColumn("وضعیت")
        }
    )

    # نمایش موجودی در پایین
    st.divider()
    st.metric("BTC Price", f"${df['Close'].iloc[-1]:,.2f}")
