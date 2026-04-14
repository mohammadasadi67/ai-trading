import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, date

st.set_page_config(layout="wide", page_title="Professional Trading Panel")

# ======================
# دریافت داده‌های زنده
# ======================
def get_live_data():
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 200} # تعداد دیتا را بیشتر کردیم برای فیلتر تاریخ
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        df = pd.DataFrame(data, columns=[
            "time","open","high","low","close","volume",
            "close_time","qav","trades","tbbav","tbqav","ignore"
        ])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df = df[["time","open","high","low","close"]]
        df.columns = ["Time","Open","High","Low","Close"]
        df.set_index("Time", inplace=True)
        df = df.astype(float)
        return df
    except Exception as e:
        st.error(f"خطا در اتصال به بایننس: {e}")
        return pd.DataFrame()

# ======================
# سایدبار (تنظیمات و فیلترها)
# ======================
st.sidebar.title("⚙️ تنظیمات و فیلتر")

initial_capital = st.sidebar.number_input("سرمایه اولیه ($)", value=1000.0, step=100.0)

# فیلتر تاریخ
st.sidebar.subheader("📅 بازه زمانی")
start_date = st.sidebar.date_input("تاریخ شروع", value=date(2024, 1, 1))
end_date = st.sidebar.date_input("تاریخ پایان", value=date.today())

# ======================
# محاسبات سیگنال و PnL
# ======================
df = get_live_data()

if not df.empty:
    # اعمال فیلتر تاریخ روی کل دیتافریم
    # تبدیل تاریخ‌های انتخابی به فرمت مناسب پانداز
    mask = (df.index.date >= start_date) & (df.index.date <= end_date)
    df_filtered = df.loc[mask].copy()

    if df_filtered.empty:
        st.warning("⚠️ در این بازه زمانی دیتایی وجود ندارد. لطفاً تاریخ را تغییر دهید.")
    else:
        df_filtered["Signal"] = "⚪ WAIT"
        df_filtered["Entry"] = np.nan
        df_filtered["Target"] = np.nan
        df_filtered["StopLoss"] = np.nan
        df_filtered["PnL_Percent"] = 0.0

        total_pnl_multiplier = 1.0 

        # محاسبه سیگنال‌ها در دیتای فیلتر شده
        for i in range(2, len(df_filtered)):
            p1 = df_filtered.iloc[i-1]
            p2 = df_filtered.iloc[i-2]
            
            if p1["Close"] > p2["Close"]:
                entry = df_filtered["Open"].iloc[i]
                diff = p1["Close"] - p2["Close"]
                target = entry + diff
                sl = p1["Low"]
                
                curr_high = df_filtered["High"].iloc[i] if "High" in df_filtered.columns else df_filtered["Close"].iloc[i]
                curr_low = df_filtered["Low"].iloc[i] if "Low" in df_filtered.columns else df_filtered["Close"].iloc[i]
                curr_close = df_filtered["Close"].iloc[i]

                if curr_high >= target:
                    exit_price = target
                elif curr_low <= sl:
                    exit_price = sl
                else:
                    exit_price = curr_close

                pnl_perc = (exit_price - entry) / entry
                
                df_filtered.iloc[i, df_filtered.columns.get_loc("Signal")] = "🟢 BUY"
                df_filtered.iloc[i, df_filtered.columns.get_loc("Entry")] = entry
                df_filtered.iloc[i, df_filtered.columns.get_loc("Target")] = target
                df_filtered.iloc[i, df_filtered.columns.get_loc("StopLoss")] = sl
                df_filtered.iloc[i, df_filtered.columns.get_loc("PnL_Percent")] = pnl_perc * 100
                
                total_pnl_multiplier *= (1 + pnl_perc)

        final_balance = initial_capital * total_pnl_multiplier

        # ======================
        # نمایش خروجی
        # ======================
        current_p = df["Close"].iloc[-1]
        st.markdown(f"""
            <div style="text-align: center; background-color: #1e1e1e; padding: 15px; border-radius: 10px; border: 1px solid #4CAF50;">
                <h2 style="margin: 0; color: white;">BTC Current Price: <span style="color: #4CAF50;">${current_p:,.2f}</span></h2>
            </div>
        """, unsafe_allow_html=True)

        st.write("")
        c1, c2, c3 = st.columns(3)
        c1.metric("سرمایه در شروع بازه", f"${initial_capital:,.0f}")
        c2.metric("موجودی نهایی", f"${final_balance:,.2f}", delta=f"{((final_balance/initial_capital)-1)*100:.2f}%")
        c3.metric("سود خالص در این بازه", f"${final_balance - initial_capital:,.2f}")

        st.divider()
        
        st.subheader(f"📋 معاملات از {start_date} تا {end_date}")
        
        view_df = df_filtered.sort_index(ascending=False).copy()
        
        st.dataframe(
            view_df,
            use_container_width=True,
            height=400,
            column_config={
                "Signal": st.column_config.TextColumn("وضعیت"),
                "Entry": st.column_config.NumberColumn("ورود", format="$%.1f"),
                "Target": st.column_config.NumberColumn("هدف", format="$%.1f"),
                "StopLoss": st.column_config.NumberColumn("استاپ", format="$%.1f"),
                "PnL_Percent": st.column_config.NumberColumn("سود/ضرر %", format="%.2f%%"),
                "Close": st.column_config.NumberColumn("قیمت نهایی", format="$%.1f"),
                "Open": None, "High": None, "Low": None
            }
        )

# رفرش خودکار
st.markdown("<script>setTimeout(function(){window.location.reload();}, 60000);</script>", unsafe_allow_html=True)
