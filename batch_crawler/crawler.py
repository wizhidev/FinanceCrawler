import sys
import os
import sqlite3
import json
import time
import random
from multiprocessing import Pool
from tqdm import tqdm

# 将项目根目录添加到Python路径中，以允许跨目录导入模块
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- Fetcher函数直接导入 ---
from fetchers.eastmoney_fetcher import get_market_options, crawl_stock_ranking_data
from fetchers.stock_details_fetcher import get_stock_details as get_a_share_details
from fetchers.hk_details_fetcher import fetch_hk_stock_details as get_hk_share_details
from fetchers.news_fetcher import get_company_news
# --- 数据库和配置导入 ---
from batch_crawler.db import get_db_connection
from batch_crawler.config import MAX_WORKERS


def update_stock_list():
    """
    获取所有市场的股票列表 (A股和港股)，并将其存入数据库的 'stocks' 表中。
    如果股票代码已存在，则忽略，不进行更新。
    """
    print("开始更新股票列表...")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    markets = get_market_options()
    total_inserted = 0
    
    for market_name, market_info in markets.items():
        print(f"正在获取 '{market_name}' 的股票列表...")
        df = crawl_stock_ranking_data(market_name)
        
        if df is None or df.empty:
            print(f"未能获取到 '{market_name}' 的数据，跳过。")
            continue
            
        market_type = market_info.get('type')
        if not market_type:
            print(f"警告: '{market_name}' 没有定义市场类型，跳过。")
            continue
        
        insert_count_for_market = 0
        for index, row in df.iterrows():
            stock_code = row.get('代码')
            stock_name = row.get('名称')
            
            if not stock_code or not stock_name:
                continue

            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO stocks (stock_code, stock_name, market_type)
                    VALUES (?, ?, ?)
                """, (stock_code, str(stock_name), market_type))
                
                if cursor.rowcount > 0:
                    insert_count_for_market += 1

            except sqlite3.Error as e:
                print(f"数据库插入错误 (代码: {stock_code}): {e}")

        total_inserted += insert_count_for_market
        print(f"'{market_name}' 处理完成。新增 {insert_count_for_market} 只股票到数据库。")

    conn.commit()
    conn.close()
    
    print(f"\n股票列表更新完成。总共新增 {total_inserted} 只股票。")


def fetch_and_save_stock_details(stock_info):
    """
    抓取单只股票的详细信息（财务、新闻）并存入数据库。
    此版本在独立的进程中运行，以保证稳定性。
    """
    
    stock_code, market_type = stock_info
    
    details_success = False
    news_success = False

    if stock_code.startswith('688'):
        return "skipped"

    # 1. 抓取财务详情
    raw_data = None
    details_error = None
    if market_type == "A-Share":
        _, raw_data, details_error = get_a_share_details(stock_code)
    else: # HK-Share
        _, raw_data, details_error = get_hk_share_details(stock_code)
    
    if details_error:
        print(f"抓取详情失败 (代码: {stock_code}): {details_error}", file=sys.stderr)

    # 2. 抓取新闻
    news_result = get_company_news(stock_code)

    # 3. 数据入库
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if raw_data and not details_error:
        try:
            raw_data_json = json.dumps(raw_data, ensure_ascii=False)
            cursor.execute("""
                INSERT OR REPLACE INTO financial_data (stock_code, raw_data) VALUES (?, ?)
            """, (stock_code, raw_data_json))
            details_success = True
        except sqlite3.Error as e:
            print(f"财务数据入库失败 (代码: {stock_code}): {e}", file=sys.stderr)

    if news_result:
        news_inserted = 0
        for news_item in news_result:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO news (url, stock_code, title, publish_time)
                    VALUES (?, ?, ?, ?)
                """, (
                    news_item.get('url'),
                    stock_code,
                    news_item.get('title'),
                    news_item.get('publishTime')
                ))
                if cursor.rowcount > 0:
                    news_inserted += 1
            except sqlite3.Error as e:
                print(f"新闻入库失败 (URL: {news_item.get('url')}): {e}", file=sys.stderr)
        
        if news_inserted > 0:
            news_success = True
    
    conn.commit()
    conn.close()
    
    if details_success or news_success:
        return "success"
    else:
        return "failed"

def crawl_all_details():
    """
    【最终版】从数据库中获取所有股票，并使用并发进程池抓取它们的详细信息。
    【新增】断点续传功能。
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    # 【核心优化】只选取尚未抓取过详情的股票，实现断点续传
    cursor.execute("""
        SELECT s.stock_code, s.market_type
        FROM stocks s
        LEFT JOIN financial_data fd ON s.stock_code = fd.stock_code
        WHERE fd.stock_code IS NULL
    """)
    all_stocks = cursor.fetchall()
    conn.close()

    if not all_stocks:
        print("数据库中没有股票，请先运行 update_stock_list()")
        return
    
    # 分批处理
    batch_size = MAX_WORKERS
    stock_batches = [all_stocks[i:i + batch_size] for i in range(0, len(all_stocks), batch_size)]

    print(f"准备开始为 {len(all_stocks)} 只股票抓取详细信息...")
    print(f"将分 {len(stock_batches)} 批处理，每批最多 {batch_size} 只股票，批次间间隔60秒。")

    total_results = []
    # 使用tqdm显示总进度
    with tqdm(total=len(all_stocks), desc="抓取总进度") as pbar:
        for i, batch in enumerate(stock_batches):
            with Pool(processes=batch_size) as pool:
                # 使用 imap_unordered，每完成一个任务就立即更新进度条
                for result in pool.imap_unordered(fetch_and_save_stock_details, batch):
                    total_results.append(result)
                    pbar.update(1) # 进度条前进一步

            # 在每批处理完成后，如果不是最后一批，则休息60秒
            if i < len(stock_batches) - 1:
                # 使用tqdm的write方法打印，避免与进度条冲突
                pbar.write(f"\n第 {i+1}/{len(stock_batches)} 批处理完成，休息60秒...")
                time.sleep(60)

    # 打印最终的统计结果
    success_count = len([r for r in total_results if r == 'success'])
    skipped_count = len([r for r in total_results if r == 'skipped'])
    failed_count = len(total_results) - success_count - skipped_count
    print(f"\n详细信息抓取完成。成功: {success_count}, 跳过: {skipped_count}, 失败: {failed_count}")


def main():
    """
    批量抓取脚本的主入口。
    """
    print("--- 开始执行批量抓取任务 ---")
    update_stock_list()
    crawl_all_details()
    print("\n--- 批量抓取任务执行完毕 ---")

if __name__ == '__main__':
    main() 