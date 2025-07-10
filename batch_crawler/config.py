import os

# --- 数据库配置 ---
# 定义数据库文件存放的目录
DB_DIR = os.path.join(os.path.dirname(__file__), 'database')
# 定义数据库文件的完整路径
DB_FILE = os.path.join(DB_DIR, 'financial_data.db')

# --- 日志配置 ---
LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'crawler.log')

# --- 爬虫相关配置 ---
# 全局超时设置 (秒)
CRAWL_TIMEOUT = 60
# 并发执行的进程数
MAX_WORKERS = 3

# 确保日志和数据库目录存在
os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True) 