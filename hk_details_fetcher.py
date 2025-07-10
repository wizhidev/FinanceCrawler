import pandas as pd
from playwright.sync_api import sync_playwright
import time
import sys
import re 
from bs4 import BeautifulSoup # FIX: Move import to top level

def fetch_hk_stock_details(stock_code: str):
    """
    从东方财富网抓取指定港股的详细财务数据，使用Playwright来处理动态加载的内容。

    Args:
        stock_code (str): 港股代码 (例如: '00700').

    Returns:
        dict: 包含 'financial_data' (DataFrame) 和 'error_msg' 的字典。
    """
    if len(stock_code) < 5 and stock_code.isdigit():
        stock_code = stock_code.zfill(5)
        
    url = f"https://quote.eastmoney.com/hk/{stock_code}.html"
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until='load', timeout=30000)

            # 等待关键的财务数据表格出现
            finance_div_selector = 'div.finance4'
            page.wait_for_selector(finance_div_selector, timeout=20000)
            
            # 等待表格内的数据加载完成
            page.wait_for_function(f"""
                () => document.querySelector('{finance_div_selector} table tbody tr:first-child td:nth-child(2)').innerText.trim() !== '-'
            """, timeout=15000)

            # 短暂延时，确保所有JS渲染完毕
            time.sleep(1)

            # [FIX] Get the container's HTML to pass to the correct parsing function
            finance_div = page.locator(finance_div_selector)
            html_content = finance_div.inner_html()
            browser.close()

            # [FIX] Call the correct, centralized parsing function
            parsed_data, error_message = _parse_hk_financial_table(html_content)

            if error_message:
                print(f"错误: {error_message}")
                return {'financial_data': None, 'error_msg': error_message}
                
            # [FIX] Create DataFrame from the correctly parsed data
            df = pd.DataFrame(parsed_data['all_rows'], columns=parsed_data['headers'])
            return {'financial_data': df, 'error_msg': None, 'raw_data': parsed_data}

        except Exception as e:
            error_message = f"使用 Playwright 抓取或解析港股 {stock_code} 数据时发生错误: {e}"
            print(error_message)
            return {'financial_data': None, 'error_msg': error_message}

def _parse_hk_financial_table(html_content):
    """
    解析抓取到的港股财务表格HTML。
    """
    if not html_content:
        return None, "抓取到的HTML内容为空"
        
    soup = BeautifulSoup(html_content, 'lxml')
    table = soup.find('table')
    
    if not table:
        return None, "在抓取到的内容中未能找到 <table> 标签"

    # 1. 解析表头，并修正第一列的列名
    headers = [th.get_text(strip=True) for th in table.select('thead th')]
    if headers and headers[0] == '':
        headers[0] = '指标'

    # 2. 解析所有数据行
    all_rows = []
    data_rows = table.select('tbody tr')
    if not data_rows:
        return None, "数据表格中没有找到任何数据行"

    for tr in data_rows:
        cells = tr.select('td')
        if not cells:
            continue # 跳过没有单元格的空行

        row_data = [td.get_text(strip=True) for td in cells]

        # 检查行数据和表头长度是否匹配
        if len(row_data) == len(headers):
            all_rows.append(row_data)

    # 3. 提取元数据
    company_name = "未知公司"
    industry_name = "未知行业"
    if all_rows:
        # 公司名称通常在第一行的第一列
        company_name_raw = all_rows[0][0]
        company_name = re.sub(r'\d+$', '', company_name_raw).strip()
        
        # 行业名称在第二行
        if len(all_rows) > 1:
            industry_name_raw = all_rows[1][0]
            match = re.search(r'^(.*?)\(行业平均\)', industry_name_raw)
            industry_name = match.group(1) if match else industry_name_raw

    parsed_data = {
        'headers': headers,
        'all_rows': all_rows,
        'company_name': company_name,
        'industry_name': industry_name
    }
    return parsed_data, None

if __name__ == '__main__':
    # 为了让这个脚本可以被 data_integrator 通过 subprocess 调用，
    # 我们将结果序列化为JSON并打印到标准输出。
    # 这也统一了A股和港股详情获取脚本的行为模式。
    if len(sys.argv) > 1:
        stock_code_arg = sys.argv[1]
        details = fetch_hk_stock_details(stock_code_arg)
        
        output = {
            'dataframe': None,
            'raw_data': {}, # 港股脚本目前不提供原始数据
            'error': details['error_msg']
        }
        
        if details['financial_data'] is not None:
            output['dataframe'] = details['financial_data'].to_json(orient='split', force_ascii=False)
            # [FIX] Pass the raw_data upstream
            if 'raw_data' in details:
                output['raw_data'] = details['raw_data']
            
        import json
        print(json.dumps(output, ensure_ascii=False))
    else:
        # --- 原有的直接运行测试代码 ---
        print("Running in test mode. To fetch a stock, provide its code as an argument.")
        test_codes = ['00700', '03690', '09988']
        for code in test_codes:
            details_result = fetch_hk_stock_details(code)
            if details_result and details_result.get('financial_data') is not None:
                print(f"\n--- 股票代码: {code} 的详细信息 ---")
                print(details_result['financial_data'].to_string())
            else:
                error = details_result.get('error_msg', '未知错误') if details_result else '未知错误'
                print(f"\n--- 未能获取股票代码: {code} 的信息 ---. 原因: {error}") 