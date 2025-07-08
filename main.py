import streamlit as st
import pandas as pd
from data_integrator import (
    get_integrated_market_data, 
    get_integrated_stock_details, 
    get_available_markets,
    format_news_for_display,
    format_financial_data_for_display
)

# 页面配置
st.set_page_config(
    page_title="股票数据分析系统", 
    page_icon="📈", 
    layout="wide"
)

# --- Session State Initialization ---
if 'selected_stock_code' not in st.session_state:
    st.session_state.selected_stock_code = None
if 'selected_stock_name' not in st.session_state:
    st.session_state.selected_stock_name = None

# --- Sidebar ---
MARKET_OPTIONS = get_available_markets()
st.sidebar.header("控制面板")
selected_market = st.sidebar.selectbox(
    "选择市场",
    list(MARKET_OPTIONS.keys()),
    help="选择要查看的股票市场",
    key="market_selector" # Add a key to prevent state issues
)

# --- Main Page ---
st.title("📈 股票数据分析系统")
st.markdown("### 💰 东方财富网数据")

# --- Market Data Display ---
st.subheader(f"📋 {selected_market} 股票排名")
if st.button("🔄 刷新数据", type="primary"):
    # Clear cache and reset selection
    st.cache_data.clear()
    st.session_state.selected_stock_code = None
    st.session_state.selected_stock_name = None
    st.experimental_rerun() # Rerun to reflect changes immediately

with st.spinner("正在获取股票数据..."):
    df = get_integrated_market_data(selected_market)

if df is not None and not df.empty:
    st.dataframe(
        df,
        use_container_width=True,
        height=400,
        hide_index=True
    )
    
    # --- Stock Selector ---
    stock_codes = df['代码'].tolist() if '代码' in df.columns else []
    stock_names = df['名称'].tolist() if '名称' in df.columns else []
    
    if stock_codes and stock_names:
        stock_options = {f"{code} - {name}": code for code, name in zip(stock_codes, stock_names)}
        
        selected_stock_display = st.selectbox(
            "选择股票查看详细信息：",
            ["请选择..."] + list(stock_options.keys()),
            key="stock_selector"
        )
        
        if selected_stock_display != "请选择...":
            st.session_state.selected_stock_code = stock_options[selected_stock_display]
            st.session_state.selected_stock_name = selected_stock_display
        else:
            # Reset if "请选择..." is chosen
            st.session_state.selected_stock_code = None
            st.session_state.selected_stock_name = None
    
else:
    st.error("无法获取股票数据，请检查网络连接或稍后重试")

# --- Stock Details Display Section ---
if st.session_state.selected_stock_code:
    st.divider()
    st.subheader(f"📊 {st.session_state.selected_stock_name} 详细信息")
    
    with st.spinner("正在获取详细数据..."):
        details = get_integrated_stock_details(st.session_state.selected_stock_code)
        error_msg = details.get('error_msg')
    
    # --- Financial Data Section (now arranged vertically) ---
    st.markdown("#### 💰 核心财务指标")
    if error_msg:
        st.error(f"获取财务数据失败: {error_msg}")
    
    financial_data = details.get('financial_data')
    if financial_data is not None and not financial_data.empty:
        st.table(financial_data.set_index('指标')) # Set index for better alignment
    else:
        st.warning("暂无财务数据")

    # --- News Section (now arranged vertically) ---
    st.markdown("#### 📰 最新资讯")
    news_data = details.get('news_data', [])
    if news_data:
        for news in news_data:
            # Format date and title for each news item
            from datetime import datetime
            if 'publishTime' in news and news['publishTime']:
                date_str = datetime.fromtimestamp(news['publishTime']).strftime('%Y-%m-%d')
            else:
                date_str = "未知日期"
            title = news.get('title', '无标题新闻')
            # Assuming 'url' is a field in the news data
            url = news.get('url') 
            if url:
                st.markdown(f"[{title}]({url}) - *{date_str}*")
            else:
                st.markdown(f"{title} - *{date_str}*")
            st.divider()
    else:
        st.info("暂无最新公司新闻")

# --- Footer ---
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666;'>
        <p>🎯 数据来源：东方财富网</p>
        <p>⚡ 实时数据 | 🔄 自动刷新 | 📱 响应式设计</p>
    </div>
    """,
    unsafe_allow_html=True
) 