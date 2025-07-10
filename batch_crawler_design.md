# 批量定时抓取A股/港股数据与资讯系统设计方案（兼容现有代码）

## 1. 设计目标

- **不修改现有抓取脚本**（如 eastmoney_fetcher.py、stock_details_fetcher.py、hk_details_fetcher.py、news_fetcher.py 等），在其基础上实现批量、定时、自动化抓取与入库。
- 支持A股、港股股票列表的定时批量获取。
- 支持每只股票的详细信息和新闻资讯的批量抓取。
- 支持数据自动保存到数据库。
- 具备良好的容错、日志和可扩展性。

---

## 2. 总体流程

1. **定时任务调度**
   - 使用 APScheduler/schedule/crontab 等定时调度工具，定时触发批量抓取任务。

2. **批量获取股票列表**
   - 通过调用现有 eastmoney_fetcher.py，分别获取A股、港股列表。

3. **遍历股票列表，抓取详情和资讯**
   - 对每只股票，调用 stock_details_fetcher.py（A股）、hk_details_fetcher.py（港股）获取详情。
   - 对每只股票，调用 news_fetcher.py 获取新闻资讯。

4. **数据入库**
   - 统一数据结构，保存到数据库（如sqlite3/MySQL/PostgreSQL）。
   - 支持批量插入、去重、断点续抓。

5. **日志与异常处理**
   - 全流程日志记录，异常自动跳过并记录。

---

## 3. 主要模块设计

### 3.1 调度与主控模块
- 新增 batch_crawler.py 作为主控入口。
- 负责定时调度、批量流程控制、日志管理。

### 3.2 列表抓取适配
- 通过 subprocess 或 import 方式调用 eastmoney_fetcher.py，获取A股、港股列表。
- 支持参数配置（如热门、全市场、板块等）。

### 3.3 详情与资讯批量抓取
- 通过 subprocess 调用 stock_details_fetcher.py、hk_details_fetcher.py、news_fetcher.py。
- 支持多线程/多进程/协程并发抓取，提升效率。
- 每只股票抓取失败自动重试或跳过。

### 3.4 数据库与数据结构
- 新增 db.py，封装数据库操作。
- 推荐表结构：

#### 表1：stock_list
| 字段       | 类型     | 说明         |
|------------|----------|--------------|
| id         | int      | 主键         |
| code       | varchar  | 股票代码     |
| name       | varchar  | 股票名称     |
| market     | varchar  | 市场（A/HK） |
| ...        | ...      | 其他信息     |

#### 表2：stock_details
| 字段        | 类型     | 说明         |
|-------------|----------|--------------|
| id          | int      | 主键         |
| code        | varchar  | 股票代码     |
| market      | varchar  | 市场         |
| detail_json | text     | 详情原始数据 |
| update_time | datetime | 更新时间     |

#### 表3：stock_news
| 字段         | 类型     | 说明         |
|--------------|----------|--------------|
| id           | int      | 主键         |
| code         | varchar  | 股票代码     |
| market       | varchar  | 市场         |
| title        | varchar  | 新闻标题     |
| url          | varchar  | 新闻链接     |
| publish_time | datetime | 发布时间     |
| insert_time  | datetime | 入库时间     |

---

## 4. 并发与性能优化
- 使用 ThreadPoolExecutor/ProcessPoolExecutor/asyncio 控制并发抓取。
- 合理设置并发数，防止被目标网站封禁。
- 支持失败重试、断点续抓。

---

## 5. 代码结构建议

```
/batch_crawler/
    ├── batch_crawler.py      # 主控入口，调度与流程控制
    ├── db.py                # 数据库操作
    ├── config.py            # 配置文件（定时、并发、数据库等）
    ├── utils.py             # 工具函数
    └── logs/                # 日志目录
```

---

## 6. 方案亮点与扩展性
- **最大化复用现有脚本**，无需大改原有抓取逻辑。
- 支持灵活扩展（如后续增加美股、基金等）。
- 支持多种数据库，便于后续数据分析与可视化。
- 具备良好的容错和日志能力。

---

如需具体某一部分的代码实现、表结构DDL或调度脚本样例，请随时告知！ 