# 📈 股票数据分析系统

这是一个使用 Python 和 Streamlit 构建的交互式股票数据分析应用。

## ✨ 功能特性

- **实时数据**：从东方财富网实时获取沪深京A股和港股的最新行情数据。
- **动态详情**：通过 Playwright 抓取动态加载的个股核心财务指标。
- **新闻资讯**：聚合与个股相关的最新新闻。
- **交互式界面**：使用 Streamlit 构建，提供市场选择、股票筛选等交互功能。
- **数据可视化**：以清晰的表格展示行情和财务数据。

## 🛠️ 技术栈

- **后端**: Python
- **Web框架**: Streamlit
- **数据抓取**: Requests, Playwright
- **数据处理**: Pandas
- **HTML解析**: BeautifulSoup, lxml

## 🚀 如何运行

1.  **安装依赖**:
    ```bash
    poetry install
    ```

2.  **安装 Playwright 浏览器驱动**:
    ```bash
    playwright install
    ```

3.  **启动应用**:
    ```bash
    streamlit run main.py
    ``` 