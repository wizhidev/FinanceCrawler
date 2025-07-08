import requests
import json

def get_company_news(stock_code):
    """
    从东方财富网获取最新的公司资讯
    :param stock_code: 股票代码
    :return: list of news articles or an empty list
    """
    url = "https://np-list.eastmoney.com/comm/web/getNewsByCode"
    params = {"code": str(stock_code), "type": 1, "page": 1, "pagesize": 5}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36",
    }
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        news_data = resp.json()
        return news_data.get('Result', {}).get('data', [])
    except (requests.RequestException, json.JSONDecodeError):
        # Return empty list if there is any network or parsing error
        return [] 