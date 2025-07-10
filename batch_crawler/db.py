import sqlite3
import pandas as pd
import os
import sys

# 使用相对导入，从同一个包中导入config模块
from .config import DB_FILE, DB_DIR

def get_db_connection():
    """
    创建并返回一个到SQLite数据库的连接。
    如果数据库目录不存在，则会先创建该目录。
    """
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    return conn

def create_tables():
    """
    在数据库中创建所有需要的表 (如果它们还不存在的话)。
    - stocks: 存储基础的股票信息。
    - financial_data: 存储详细的财务指标。
    - news: 存储公司相关的新闻资讯。
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # SQL语句，用于创建stocks表
    # stock_code 作为主键，确保唯一性
    # market_type 用于区分 'A-Share' 或 'HK-Share'
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS stocks (
        stock_code TEXT PRIMARY KEY,
        stock_name TEXT NOT NULL,
        market_type TEXT NOT NULL,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # SQL语句，用于创建financial_data表
    # 使用复合主键 (stock_code, last_updated) 来存储历史数据
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS financial_data (
        stock_code TEXT,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        raw_data TEXT,
        FOREIGN KEY (stock_code) REFERENCES stocks (stock_code),
        PRIMARY KEY (stock_code, last_updated)
    )
    ''')

    # SQL语句，用于创建news表
    # 使用 url 作为主键，防止重复存储同一条新闻
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS news (
        url TEXT PRIMARY KEY,
        stock_code TEXT,
        title TEXT NOT NULL,
        publish_time TIMESTAMP,
        crawled_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (stock_code) REFERENCES stocks (stock_code)
    )
    ''')

    conn.commit()
    conn.close()
    print("数据库表创建成功或已存在。")

if __name__ == '__main__':
    """
    当直接运行此脚本时，会自动创建数据库和所有表。
    """
    print("正在初始化数据库...")
    create_tables()
    print("数据库初始化完成。") 