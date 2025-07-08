import pandas as pd
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# The compatibility fix for asyncio on Windows has been moved to the main application
# entry point (e.g., your Streamlit app's main .py file). It must be placed at the
# very top of that file, before streamlit is imported, to be effective.

# --- Main Function ---

def get_stock_details(stock_code):
    """
    通过Playwright，从东方财富网抓取个股的动态财务数据。
    如果抓取或解析失败，返回一个包含N/A的空DataFrame及错误信息。
    :param stock_code: 股票代码，如 '301123'
    :return: (DataFrame, dict, str or None) -> (摘要数据, 原始数据, 错误信息)
    """
    # 定义一个表示失败的、结构一致的返回值
    na_df = pd.DataFrame([['N/A'] * 8], columns=['指标', '总市值', '净资产', '净利润', '市盈率(动)', '市净率', '毛利率', 'ROE'])
    empty_raw_data = {'stock_name': 'N/A', 'industry_name': 'N/A', 'comparison_data': {}}

    full_code = get_full_stock_code(stock_code)
    
    scraped_data, error = _scrape_financial_analysis_with_playwright(full_code)

    if error:
        return na_df, empty_raw_data, error

    if not scraped_data or 'headers' not in scraped_data or 'all_rows' not in scraped_data:
        return na_df, empty_raw_data, "未能从页面解析出完整的财务数据表格"

    # 成功后，创建DataFrame和原始数据
    df = pd.DataFrame(scraped_data['all_rows'], columns=scraped_data['headers'])
    
    raw_data = {
        'stock_name': scraped_data.get('company_name', stock_code),
        'industry_name': scraped_data.get('industry_name', 'N/A'),
        'comparison_data': scraped_data
    }
    return df, raw_data, None

# --- Private Scraping and Parsing Functions ---

def _scrape_financial_analysis_with_playwright(full_code):
    """
    使用Playwright访问页面，等待JS动态加载财务数据表格后抓取。
    """
    url_code = full_code.lower()
    url = f"https://quote.eastmoney.com/{url_code}.html"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url, timeout=30000, wait_until='domcontentloaded')

            # 最终正确的选择器，基于您提供的源码
            table_container_selector = "div.finance4"
            page.wait_for_selector(table_container_selector, timeout=20000)
            
            table_html = page.locator(table_container_selector).inner_html()
            browser.close()
            
            return _parse_financial_table_html(table_html)

    except PlaywrightTimeoutError as e:
        return None, f"页面加载或元素定位超时。未能在页面上动态加载出财务数据表格 ('div.finance4')。错误: {e}"
    except Exception as e:
        return None, f"Playwright抓取过程中发生错误: {str(e)}"

def _parse_financial_table_html(html_content):
    """
    解析抓取到的财务表格HTML，智能处理特殊行，确保数据纯净。
    """
    if not html_content:
        return None, "抓取到的HTML内容为空"
        
    soup = BeautifulSoup(html_content, 'lxml')
    table = soup.find('table')
    
    if not table:
        return None, "在抓取到的内容中未能找到 <table> 标签"

    # 1. 解析表头
    headers = ['指标']
    header_tags = table.find('thead').find_all('th')
    for th in header_tags:
        header_text = th.get_text(strip=True).replace('?', '')
        if header_text:
            headers.append(header_text)

    # 2. 智能解析所有数据行
    all_rows = []
    data_rows = table.find('tbody').find_all('tr')
    if not data_rows:
        return None, "数据表格中没有找到任何数据行"

    for tr in data_rows:
        row_data = []
        cells = tr.find_all('td')
        
        # 对包含提示的特殊行（四分位属性行）进行净化处理
        if 'fw4tr' in tr.get('class', []):
            for td in cells:
                # 移除内部的提示div，避免提取到不必要的帮助文字
                tip_div = td.find('div', class_='tip')
                if tip_div:
                    tip_div.decompose()
                row_data.append(td.get_text(strip=True))
        else:
            # 普通行直接提取
            row_data = [td.get_text(strip=True) for td in cells]
            
        all_rows.append(row_data)

    # 3. 提取元数据
    company_name_raw = all_rows[0][0] if len(all_rows) > 0 else "未知公司"
    company_name = re.sub(r'\d+$', '', company_name_raw).strip()
    
    industry_name_raw = all_rows[1][0] if len(all_rows) > 1 else "未知行业"
    match = re.search(r'^(.*?)\(行业平均\)', industry_name_raw)
    industry_name = match.group(1) if match else industry_name_raw

    parsed_data = {
        'headers': headers,
        'all_rows': all_rows,
        'company_name': company_name,
        'industry_name': industry_name
    }
    return parsed_data, None

# --- Utility Functions ---
def get_full_stock_code(stock_code):
    """根据A股股票代码前缀生成完整的股票代码"""
    code_str = str(stock_code).strip().upper()
    if re.match(r'^(SH|SZ|BJ)\d{6}$', code_str):
        return code_str
    if code_str.startswith(('60', '688', '689')):
        return f"SH{code_str}"
    if code_str.startswith(('00', '30')):
        return f"SZ{code_str}"
    if code_str.startswith(('8', '4')):
        return f"BJ{code_str}"
    if len(code_str) == 6:
        if code_str.startswith(('60','68')): return f"SH{code_str}"
        return f"SZ{code_str}"
    raise ValueError(f"无法识别的股票代码格式: {stock_code}")

# --- Test Function (Removed) ---
# test_fetcher has been removed as this module is now ready for production integration.
# To test, you can call get_stock_details directly from another script or an interactive session.
# Example:
# if __name__ == '__main__':
#     df, raw, err = get_stock_details('301123')
#     if err:
#         print(err)
#     else:
#         print(df)

if __name__ == '__main__':
    """
    This block makes the script runnable from the command line.
    It takes a stock code as an argument, fetches the data,
    and prints the results as a JSON object to stdout.
    This allows it to be called from a separate process, avoiding event loop conflicts.
    """
    import sys
    import json

    if len(sys.argv) < 2:
        # Print an error as JSON to stderr
        print(json.dumps({"error": "No stock code provided."}), file=sys.stderr)
        sys.exit(1)

    stock_code_arg = sys.argv[1]
    
    df, raw_data, error = get_stock_details(stock_code_arg)
    
    if error:
        # Print error as JSON to stderr
        print(json.dumps({"error": error}), file=sys.stderr)
        sys.exit(1)

    # Serialize DataFrame to JSON and combine with other data
    result = {
        "dataframe": df.to_json(orient='split'),
        "raw_data": raw_data,
        "error": error
    }
    
    # Print the final result as a JSON string to stdout
    print(json.dumps(result)) 