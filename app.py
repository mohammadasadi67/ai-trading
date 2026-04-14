# ======================
    # نمایش UI
    # ======================
    current_p = df["Close"].iloc[-1]
    
    # هدر اصلی
    st.markdown(f"<h1 style='text-align: center; color: #ffca28;'>BTC Live: ${current_p:,.2f}</h1>", unsafe_allow_html=True)
    
    st.divider()

    # مرتب‌سازی برای نمایش (جدیدترین در بالا)
    view_df = df.sort_index(ascending=False).head(15)

    st.subheader("📋 لیست سیگنال‌ها و سطوح قیمتی")

    # تابع رنگ‌بندی جدید (سازگار با نسخه‌های جدید پانداز)
    def color_signal(val):
        if val == "🟢 BUY":
            return 'color: #2e7d32; font-weight: bold'
        return 'color: #757575'

    # نمایش جدول با استفاده از تنظیمات ستون خود استریم‌لیت (بسیار مرتب‌تر)
    st.dataframe(
        view_df,
        use_container_width=True,
        height=450,
        column_config={
            "Signal": st.column_config.TextColumn("سیگنال"),
            "Entry": st.column_config.NumberColumn("قیمت ورود", format="$%.1f"),
            "Target": st.column_config.NumberColumn("هدف (TP)", format="$%.1f"),
            "StopLoss": st.column_config.NumberColumn("حد ضرر (SL)", format="$%.1f"),
            "Close": st.column_config.NumberColumn("قیمت فعلی", format="$%.1f"),
            "Open": st.column_config.NumberColumn("باز شدن", format="$%.1f"),
            "High": None, # حذف ستون‌های اضافی برای خلوت شدن
            "Low": None,
            "Status": st.column_config.TextColumn("وضعیت")
        }
    )

    # نمایش کارت‌های سریع برای آخرین سیگنال فعال
    trade_signals = df[df["Signal"] == "🟢 BUY"]
    if not trade_signals.empty:
        last_signal = trade_signals.iloc[-1]
        st.info(f"📌 آخرین سیگنال صادر شده در ساعت: {last_signal.name.strftime('%H:%M')}")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Entry (ورود)", f"${last_signal['Entry']:,.1f}")
        c2.metric("Target (سود)", f"${last_signal['Target']:,.1f}", delta=f"{last_signal['Target']-last_signal['Entry']:.1f}")
        c3.metric("Stop Loss (ضرر)", f"${last_signal['StopLoss']:,.1f}", delta=f"{last_signal['StopLoss']-last_signal['Entry']:.1f}", delta_color="inverse")
