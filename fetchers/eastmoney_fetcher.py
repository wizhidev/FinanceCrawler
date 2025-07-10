import requests
import json
import pandas as pd
from datetime import datetime

# -- 市场配置 --
MARKET_OPTIONS = {
    "沪深京A股": {
        "fs": "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23",
        "columns": {
            'f12': '代码', 'f14': '名称', 'f2': '最新价', 'f3': '涨跌幅', 'f4': '涨跌额',
            'f5': '成交量(手)', 'f6': '成交额', 'f7': '振幅', 'f8': '换手率', 'f15': '最高',
            'f16': '最低', 'f17': '今开', 'f18': '昨收', 'f10': '量比', 'f9': '市盈率(动态)', 'f23': '市净率'
        },
        "type": "A-Share"
    },
    "知名港股": {
        "fs": "b:DLMK0106",  # Corrected board ID for well-known HK stocks
        "columns": {
            'f12': '代码', 'f14': '名称', 'f2': '最新价', 'f3': '涨跌幅', 'f4': '涨跌额',
            'f5': '成交量(股)', 'f6': '成交额(港元)', 'f15': '最高', 'f16': '最低',
            'f17': '今开', 'f18': '昨收'
        },
        "type": "HK-Share"
    }
}

def crawl_stock_ranking_data(market_name):
    """
    从东方财富网获取股票排名数据
    """
    if market_name not in MARKET_OPTIONS:
        return None

    market_config = MARKET_OPTIONS[market_name]
    is_ashare = market_config["type"] == "A-Share"

    if is_ashare:
        # --- Parameters for A-Share ---
        url = "http://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "cb": "jQuery112405034891155096131_1589169999999",
            "pn": "1", "pz": "500", "np": "1",
            "ut": "bd1d9ddb040897001ac3b38159e2164a",
            "fltt": "2", "invt": "2",
            "wbp2u": "||0|0|0|web", "fid": "f3", "po": "0",
            "fs": market_config["fs"],
            "fields": ",".join(market_config["columns"].keys())
        }
    else:
        # --- Parameters for HK-Share (based on user-provided script) ---
        url = "https://69.push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": "1", "pz": "50000", "po": "1", "np": "2",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2", "invt": "2", "dect": "1",
            "wbp2u": "|0|0|0|web", "fid": "f3",
            "fs": market_config["fs"],
            "fields": ",".join(market_config["columns"].keys())
        }
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36",
        "Referer": "https://quote.eastmoney.com/"
    }

    # --- Debugging Block for ALL markets ---
    import urllib.parse
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    print(f"\n--- [DEBUG] {market_name} Request ---")
    print(f"Market Type: {market_config['type']}")
    print(f"Requesting URL: {full_url}")
    print(f"Request Headers: {headers}")
    print("------------------------------\n")

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        print(f"\n--- [DEBUG] {market_name} Response ---")
        print(f"Response Status Code: {response.status_code}")
        print(f"Response Text (first 1000 chars): {response.text[:1000]}")
        print("-------------------------------\n")
        
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"\n--- [DEBUG] {market_name} Request ERROR ---\n{e}\n------------------------------------\n")
        return None

    # --- Data Parsing ---
    try:
        if is_ashare:
            # A-Share uses JSONP, requires stripping the callback
            jsonp_data = response.text
            start = jsonp_data.find('(')
            end = jsonp_data.rfind(')')
            if start != -1 and end != -1:
                json_str = jsonp_data[start+1:end]
                data = json.loads(json_str)
            else:
                raise json.JSONDecodeError("Invalid JSONP format", jsonp_data, 0)
        else:
            # HK-Share returns pure JSON
            data = response.json()
    except json.JSONDecodeError as e:
        print(f"JSON parsing failed with error: {e}")
        return None

    # --- Data Extraction ---
    stock_list = []
    diff_data = data.get("data", {}).get("diff")

    if not diff_data:
        print("No stock data found in response")
        return pd.DataFrame()

    if is_ashare:
        # A-share data is a list of dictionaries
        stock_list = diff_data
    else:
        # HK-share data is a dictionary of dictionaries, needs to be transposed
        df_temp = pd.DataFrame.from_dict(diff_data, orient='index')
        stock_list = df_temp.to_dict('records')

    print(f"Parsed data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
    print(f"Stock list length: {len(stock_list)}")
    if stock_list:
        print(f"First stock sample: {stock_list[0]}")
    print("-------------------------------\n")

    df = pd.DataFrame(stock_list)
    df = df.rename(columns=market_config["columns"])

    # Refactored Data Formatting Block
    # 1. Convert all potential numeric columns to numeric type first, coercing errors
    for col_name in df.columns:
        if col_name not in ['代码', '名称']:
            df[col_name] = pd.to_numeric(df[col_name], errors='coerce')

    # 2. Apply special formatting for volume and turnover and rename columns
    if "成交量(手)" in df.columns:
        df["成交量(万手)"] = (df["成交量(手)"] / 10000).round(2)
        df.drop(columns=["成交量(手)"], inplace=True)
    if "成交额" in df.columns:
        df["成交额(亿)"] = (df["成交额"] / 100_000_000).round(2)
        df.drop(columns=["成交额"], inplace=True)
    # Handle HK stocks for completeness
    if "成交量(股)" in df.columns:
        df["成交量(万股)"] = (df["成交量(股)"] / 10000).round(2)
        df.drop(columns=["成交量(股)"], inplace=True)
    if "成交额(港元)" in df.columns:
        df["成交额(亿港元)"] = (df["成交额(港元)"] / 100_000_000).round(2)
        df.drop(columns=["成交额(港元)"], inplace=True)

    # 3. Reorder columns for better readability
    if market_name == "沪深京A股":
        desired_order = [
            '代码', '名称', '最新价', '涨跌幅', '涨跌额',
            '市盈率(动态)', '市净率', '量比',
            '成交量(万手)', '成交额(亿)', '换手率', '振幅',
            '最高', '最低', '今开', '昨收'
        ]
        existing_columns = [col for col in desired_order if col in df.columns]
        df = df[existing_columns]
    elif market_name == "知名港股":
        desired_order = [
            '代码', '名称', '最新价', '涨跌额', '涨跌幅',
            '今开', '最高', '最低', '昨收',
            '成交量(万股)', '成交额(亿港元)'
        ]
        existing_columns = [col for col in desired_order if col in df.columns]
        df = df[existing_columns]

    # 4. Finally, convert all non-identifier columns to string for safe display
    for col_name in df.columns:
        if col_name not in ['代码', '名称']:
            df[col_name] = df[col_name].astype(str).replace('nan', '-')

    return df


def get_market_options():
    """
    返回可用的市场选项
    """
    return MARKET_OPTIONS 