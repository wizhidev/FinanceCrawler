import pandas as pd
import subprocess
import sys
import json
import os

# 将项目根目录添加到Python路径中，以允许从 'fetchers' 目录导入模块
# 这解决了当从 'app' 目录运行脚本时出现的模块未找到问题
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fetchers.eastmoney_fetcher import (
    crawl_stock_ranking_data, 
    get_market_options
)
# All detail fetchers are now called via subprocess
# from hk_details_fetcher import fetch_hk_stock_details
# from stock_details_fetcher import get_stock_details 
# from fetchers.news_fetcher import get_company_news

def get_integrated_market_data(market_name):
    """
    获取整合后的市场数据
    :param market_name: 市场名称
    :return: pandas DataFrame
    """
    return crawl_stock_ranking_data(market_name)

def get_integrated_stock_details(stock_code, market_name):
    """
    通过独立的子进程执行相应的详情获取脚本 (A股或港股)，以隔离Playwright环境。
    :param stock_code: 股票代码
    :param market_name: 市场名称 ("沪深京A股" 或 "知名港股")
    :return: dict 包含财务数据和新闻资讯
    """
    error_msg = None
    financial_df = None
    financial_raw_data = {}
    
    market_type = get_market_options().get(market_name, {}).get("type")

    script_name = ""
    script_dir = "fetchers"  # 定义脚本所在的目录

    if market_type == "A-Share":
        script_name = "stock_details_fetcher.py"
    elif market_type == "HK-Share":
        script_name = "hk_details_fetcher.py"
    else:
        error_msg = f"未知的市场类型: {market_name}"
        financial_df, financial_raw_data = _get_fallback_financial_data()
        # Early return if market type is invalid
        return {
            'financial_data': financial_df,
            'financial_raw_data': financial_raw_data,
            'error_msg': error_msg,
            'news_data': []
        }

    try:
        # 构建脚本的完整路径
        script_path = os.path.join(script_dir, script_name)
        command = [sys.executable, script_path, stock_code]
        
        # --- 增加的调试输出 ---
        print("\n" + "="*50)
        print("--- [DEBUG] Pre-subprocess Execution Info ---")
        print(f"    Market Name Received: {market_name}")
        print(f"    Determined Market Type: {market_type}")
        print(f"    Selected Script: {script_name}")
        print(f"    Full Command: {' '.join(command)}")
        print("="*50 + "\n")
        # --- 调试输出结束 ---

        process = subprocess.run(
            command,
            capture_output=True,
            # text=True and encoding='utf-8' are removed. We will handle decoding manually.
            check=False, # We also set check=False to handle non-zero exits manually.
            timeout=90
        )
        
        stdout_str = ""
        stderr_str = ""

        # Manually decode stdout and stderr to handle potential encoding issues on Windows
        try:
            stdout_str = process.stdout.decode('utf-8')
        except UnicodeDecodeError:
            stdout_str = process.stdout.decode('gbk', errors='ignore') # Fallback to gbk

        try:
            stderr_str = process.stderr.decode('utf-8')
        except UnicodeDecodeError:
            stderr_str = process.stderr.decode('gbk', errors='ignore') # Fallback to gbk

        # 打印子进程的输出以供调试
        print(f"--- [DEBUG] 子进程输出 ({script_name} {stock_code}) ---")
        if stdout_str:
            print("--- STDOUT ---")
            print(stdout_str)
        if stderr_str:
            print("--- STDERR ---", file=sys.stderr)
            print(stderr_str, file=sys.stderr)
        print("-----------------------------------------------------\n")
        
        # Now, check for errors or empty output
        if process.returncode != 0 and not stdout_str: # check 'and'
            error_msg = f"子进程 {script_name} 执行失败或无返回。"
            if stderr_str:
                error_msg += f" 错误信息: {stderr_str}"
            financial_df, financial_raw_data = _get_fallback_financial_data()
            # Skip to the end after setting the error
            return {
                'financial_data': financial_df,
                'financial_raw_data': financial_raw_data,
                'error_msg': error_msg,
                'news_data': [], # No news data if financial data fails
                'details_url': None
            }
        
        # [FIX] Clean the subprocess output to extract only the valid JSON object.
        # This handles cases where debug prints from the subprocess are mixed with the JSON output.
        json_str = None
        brace_level = 0
        json_start = -1

        for i, char in enumerate(stdout_str):
            if char == '{':
                if brace_level == 0:
                    json_start = i
                brace_level += 1
            elif char == '}':
                if brace_level > 0:
                    brace_level -= 1
                    if brace_level == 0:
                        json_str = stdout_str[json_start : i + 1]
                        break
        
        if not json_str:
            error_msg = f"无法从子进程输出中提取有效的JSON数据。原始输出: {stdout_str[:200]}..."
            financial_df, financial_raw_data = _get_fallback_financial_data()
            return {
                'financial_data': financial_df,
                'financial_raw_data': financial_raw_data,
                'error_msg': error_msg,
                'news_data': [], # No news data if financial data fails
                'details_url': None
            }


        result = json.loads(json_str)
        # More robust handling of the returned JSON
        financial_df_json = result.get('dataframe')
        if financial_df_json:
            financial_df = pd.read_json(financial_df_json, orient='split')
        else:
            financial_df = None
            
        financial_raw_data = result.get('raw_data', {})
        error_msg = result.get('error') # Handles if key is missing or value is None

        if financial_df is None and not error_msg:
             error_msg = f"从 {script_name} 未能获取 {stock_code} 的有效数据。"
        
        # Fallback only if the dataframe is truly empty
        if financial_df is None:
             financial_df, financial_raw_data = _get_fallback_financial_data()


    except subprocess.TimeoutExpired:
        error_msg = f"获取 {market_name} 财务数据超时"
        financial_df, financial_raw_data = _get_fallback_financial_data()
    except (json.JSONDecodeError, KeyError) as e: # Removed CalledProcessError as we handle it manually
        error_msg = f"处理 {market_name} 财务数据子进程时出错: {e}"
        financial_df, financial_raw_data = _get_fallback_financial_data()


    # 通过子进程获取新闻资讯，以隔离Playwright环境
    news_data, news_error = _get_news_via_subprocess(stock_code)
    if news_error:
        # 如果财务数据部分没有错误，就用新闻部分的错误覆盖
        if not error_msg:
            error_msg = news_error

    # A股URL在raw_data['comparison_data']['url']
    # 港股URL在raw_data['url']
    details_url = financial_raw_data.get('comparison_data', {}).get('url') or financial_raw_data.get('url')

    return {
        'financial_data': financial_df,
        'financial_raw_data': financial_raw_data,
        'error_msg': error_msg,
        'news_data': news_data,
        'details_url': details_url
    }

def _get_news_via_subprocess(stock_code):
    """
    通过子进程执行 news_fetcher.py 来获取新闻，避免主进程中的Playwright冲突。
    :param stock_code: 股票代码
    :return: (list, str or None) 返回新闻列表和错误信息
    """
    script_path = os.path.join("fetchers", "news_fetcher.py")
    command = [sys.executable, script_path, stock_code]

    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding='utf-8',
            check=True,
            timeout=60
        )
        news_data = json.loads(process.stdout)
        return news_data, None
    except subprocess.CalledProcessError as e:
        error_message = f"获取新闻子进程执行失败: {e.stderr}"
        return [], error_message
    except (json.JSONDecodeError, FileNotFoundError) as e:
        error_message = f"处理新闻子进程时出错: {str(e)}"
        return [], error_message
    except subprocess.TimeoutExpired:
        error_message = "获取新闻数据超时"
        return [], error_message

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