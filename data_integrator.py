import pandas as pd
import subprocess
import sys
import json
from eastmoney_fetcher import (
    crawl_stock_ranking_data, 
    get_market_options
)
# The direct import is no longer needed as we call it via subprocess
# from stock_details_fetcher import get_stock_details 
from news_fetcher import get_company_news

def get_integrated_market_data(market_name):
    """
    获取整合后的市场数据
    :param market_name: 市场名称
    :return: pandas DataFrame
    """
    return crawl_stock_ranking_data(market_name)

def get_integrated_stock_details(stock_code):
    """
    通过独立的子进程执行stock_details_fetcher.py脚本，以隔离Playwright环境。
    :param stock_code: 股票代码
    :return: dict 包含财务数据和新闻资讯
    """
    try:
        # Construct the command to run the fetcher script
        command = [sys.executable, "stock_details_fetcher.py", stock_code]
        
        # Execute the command
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,  # Raise an exception for non-zero exit codes
            encoding='utf-8',
            timeout=90  # 90-second timeout for the whole process
        )
        
        # Parse the JSON output from the script
        result = json.loads(process.stdout)
        financial_df = pd.read_json(result['dataframe'], orient='split')
        financial_raw_data = result['raw_data']
        error_msg = result['error']

    except subprocess.TimeoutExpired:
        error_msg = "获取财务数据超时"
        financial_df, financial_raw_data = _get_fallback_financial_data()
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
        error_msg = f"处理财务数据子进程时出错: {e}"
        if isinstance(e, subprocess.CalledProcessError):
            error_msg += f" - Stderr: {e.stderr}"
        financial_df, financial_raw_data = _get_fallback_financial_data()

    # 从独立的新闻模块获取新闻资讯
    news_data = get_company_news(stock_code)
    
    return {
        'financial_data': financial_df,
        'financial_raw_data': financial_raw_data,
        'error_msg': error_msg,
        'news_data': news_data
    }

def _get_fallback_financial_data():
    """Returns a default empty/NA structure for financial data on error."""
    na_df = pd.DataFrame([['N/A'] * 8], columns=['指标', '总市值', '净资产', '净利润', '市盈率(动)', '市净率', '毛利率', 'ROE'])
    empty_raw_data = {'stock_name': 'N/A', 'industry_name': 'N/A', 'comparison_data': {}}
    return na_df, empty_raw_data

def get_available_markets():
    """
    获取可用的市场选项
    """
    return get_market_options()

def format_news_for_display(news_list):
    """
    格式化新闻数据用于显示
    """
    if not news_list:
        return "暂无相关新闻"
    
    formatted_news = []
    for news in news_list[:5]:  # 只显示前5条
        # 东方财富网新闻数据字段: publishTime, title, url
        if 'publishTime' in news:
            # publishTime 是时间戳，需要转换
            from datetime import datetime
            date = datetime.fromtimestamp(news['publishTime']).strftime('%Y-%m-%d') if news.get('publishTime') else ''
        else:
            date = news.get('datetime', '').split(' ')[0] if news.get('datetime') else ''
        
        title = news.get('title', '无标题')
        formatted_news.append(f"📰 {date} {title}")
    
    return '\n'.join(formatted_news)

def format_financial_data_for_display(financial_df):
    """
    格式化财务数据用于显示
    """
    if financial_df is None or financial_df.empty:
        return "无法获取财务数据"
    
    try:
        # 将DataFrame转换为HTML表格，用于Streamlit显示
        return financial_df.to_html(escape=False, table_id="financial_table")
    except Exception as e:
        return f"数据格式化错误: {str(e)}" 