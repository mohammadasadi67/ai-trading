import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta, date

# تنظیمات اصلی صفحه
st.set_page_config(layout="wide", page_title="AI RL-Trading Panel")

# ======================
# دریافت داده‌های زنده از بایننس
# ======================
def get_live_data():
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 200}
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
        st.error(f"خطا در اتصال: {e}")
        return pd.DataFrame()

def get_time_remaining():
    now = datetime.utcnow()
    next_4h = (now.hour // 4 + 1) * 4
    if next_4h >= 24:
        target_t = datetime(now.year, now.month, now.day) + timedelta(days=1)
    else:
        target_t = datetime(now.year, now.month, now.day, next_4h)
    remaining = target_t - now
    return str(remaining).split(".")[0]

# ======================
# سایدبار و تنظیمات
# ======================
st.sidebar.title("🤖 AI Bot Settings")
initial_capital = st.sidebar.number_input("سرمایه اولیه ($)", value=1000.0, step=100.0)
start_date = st.sidebar.date_input("تاریخ شروع", value=date(2024, 1, 1))

# ======================
# پردازش داده‌ها با منطق RL
# ======================
df = get_live_data()

if not df.empty:
    # اعمال فیلتر تاریخ
    df_filtered = df[df.index.date >= start_date].copy()
    
    if df_filtered.empty:
        st.warning("⚠️ در این بازه زمانی دیتایی یافت نشد.")
    else:
        df_filtered["Signal"] = "⚪ WAIT"
        df_filtered["Entry"] = np.nan
        df_filtered["Target"] = np.nan
        df_filtered["StopLoss"] = np.nan
        df_filtered["Confidence"] = 0.0
        df_filtered["PnL_Percent"] = 0.0

        # پارامترهای یادگیری مدل
        best_multiplier = 1.0
        total_bal_multiplier = 1.0

        for i in range(2, len(df_filtered)):
            p1, p2 = df_filtered.iloc[i-1], df_filtered.iloc[i-2]
            
            # استراتژی پایه + چاشنی هوش مصنوعی
            if p1["Close"] > p2["Close"]:
                entry = df_filtered["Open"].iloc[i]
                
                # RL: تطبیق تارگت بر اساس موفقیت‌های قبلی
                base_diff = p1["Close"] - p2["Close"]
                target = entry + (base_diff * best_multiplier)
                sl = p1["Low"]
                
                curr_close = df_filtered["Close"].iloc[i]
                pnl_raw = (curr_close - entry) / entry
                
                # سیستم پاداش و تنبیه برای معامله بعدی
                if pnl_raw > 0:
                    best_multiplier = min(2.5, best_multiplier + 0.05) # تشویق
                    conf = min(0.98, 0.65 + (best_multiplier * 0.1))
                else:
                    best_multiplier = max(0.5, best_multiplier - 0.1) # تنبیه
                    conf = max(0.40, 0.60 - abs(best_multiplier * 0.05))

                df_filtered.iloc[i, df_filtered.columns.get_loc("Signal")] = "🤖 AI-BUY"
                df_filtered.iloc[i, df_filtered.columns.get_loc("Entry")] = entry
                df_filtered.iloc[i, df_filtered.columns.get_loc("Target")] = target
                df_filtered.iloc[i, df_filtered.columns.get_loc("StopLoss")] = sl
                df_filtered.iloc[i, df_filtered.columns.get_loc("Confidence")] = conf
                df_filtered.iloc[i, df_filtered.columns.get_loc("PnL_Percent")] = pnl_raw * 100
                
                total_bal_multiplier *= (1 + pnl_raw)

        final_balance = initial_capital * total_bal_multiplier

        # ======================
        # نمایش هدر لایو
        # ======================
        curr_p = df_filtered["Close"].iloc[-1]
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown(f"""
                <div style="background-color: #1e1e1e; padding: 15px; border-radius: 10px; border-left: 5px solid #4CAF50;">
                    <p style="color: #888; margin:0;">BTC PRICE (LIVE)</p>
                    <h1 style="margin:0; color: white;">${curr_p:,.2f}</h1>
                </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
                <div style="background-color: #1e1e1e; padding: 15px; border-radius: 10px; border-left: 5px solid #ffca28;">
                    <p style="color: #888; margin:0;">NEXT CANDLE IN</p>
                    <h1 style="margin:0; color: #ffca28;">{get_time_remaining()}</h1>
                </div>
            """, unsafe_allow_html=True)

        st.write("")
        m1, m2, m3 = st.columns(3)
        m1.metric("سرمایه شروع", f"${initial_capital:,.0f}")
        m2.metric("موجودی فعلی", f"${final_balance:,.2f}", delta=f"{(total_bal_multiplier-1)*100:.2f}%")
        m3.metric("سود خالص", f"${final_balance - initial_capital:,.2f}")

        st.divider()

        # ======================
        # جدول با نوار پیشرفت (Progress)
        # ======================
        st.subheader("📋 RL Model Predictions & History")
        
        view_df = df_filtered.sort_index(ascending=False).copy()
        
        st.dataframe(
            view_df,
            use_container_width=True,
            height=450,
            column_config={
                "Signal": st.column_config.TextColumn("سیگنال"),
                "Confidence": st.column_config.ProgressColumn(
                    "اطمینان مدل",
                    help="AI Confidence Level based on RL Memory",
                    format="%.0f%%",
                    min_value=0.0,
                    max_value=1.0
                ),
                "Entry": st.column_config.NumberColumn("ورود", format="$%.1f"),
                "Target": st.column_config.NumberColumn("تارگت بهینه", format="$%.1f"),
                "StopLoss": st.column_config.NumberColumn("حد ضرر (SL)", format="$%.1f"),
                "PnL_Percent": st.column_config.NumberColumn("PnL %", format="%.2f%%"),
                "Close": st.column_config.NumberColumn("قیمت فعلی/نهایی", format="$%.1f"),
                "Open": None, "High": None, "Low": None
            }
        )

# رفرش خودکار
st.markdown("<script>setTimeout(function(){window.location.reload();}, 15000);</script>", unsafe_allow_html=True)
