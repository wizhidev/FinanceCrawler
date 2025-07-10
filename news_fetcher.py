import json
from bs4 import BeautifulSoup
from datetime import datetime
from playwright.sync_api import sync_playwright

def get_company_news(stock_code, max_pages=1):
    """
    从东方财富网搜索接口抓取最新的公司资讯，通过模拟点击“下一页”实现翻页。
    :param stock_code: 股票代码
    :param max_pages: 要抓取的最大页数
    :return: list of news articles or an empty list
    """
    all_articles = []
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            # 初始导航到第一页
            url = f"https://so.eastmoney.com/news/s?keyword={stock_code}&sort=time&pageindex=1"
            page.goto(url, timeout=30000, wait_until='domcontentloaded')

            for page_num in range(1, max_pages + 1):
                print(f"--- 正在抓取第 {page_num} 页 ---")
                
                # 等待新闻列表容器加载完成
                news_list_selector = "div.news_list"
                try:
                    page.wait_for_selector(news_list_selector, timeout=20000)
                except Exception:
                    print(f"第 {page_num} 页没有找到新闻列表，抓取结束。")
                    break
                
                # 获取第一条新闻的标题，用于之后判断页面是否已更新
                first_item_selector = 'div.news_item:first-child div.news_item_t a'
                first_item_on_page = page.locator(f'{news_list_selector} {first_item_selector}')
                
                try:
                    # 等待第一个新闻项可见
                    first_item_on_page.wait_for(timeout=5000)
                except Exception:
                     print("当前页没有新闻或新闻列表不可见，抓取结束。")
                     break
                
                old_first_title = first_item_on_page.inner_text()

                html_content = page.locator(news_list_selector).inner_html()
                soup = BeautifulSoup(html_content, 'lxml')
                news_items = soup.select('div.news_item')
                
                for item in news_items:
                    title_tag = item.select_one('div.news_item_t a')
                    time_tag = item.select_one('span.news_item_time')

                    if title_tag and time_tag:
                        title = title_tag.get_text(strip=True)
                        news_url = title_tag.get('href')
                        time_str = time_tag.get_text(strip=True).replace(' -', '').strip()

                        try:
                            dt_object = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                            timestamp = int(dt_object.timestamp())
                        except ValueError:
                            continue

                        all_articles.append({
                            "title": title,
                            "url": news_url,
                            "publishTime": timestamp
                        })

                # 如果不是要抓取的最后一页，则进行翻页
                if page_num < max_pages:
                    next_page_button_selector = 'div.c_pager a[title="下一页"]'
                    next_button = page.locator(next_page_button_selector)
                    
                    if next_button.is_visible():
                        try:
                            next_button.click()
                            # 等待内容更新：判断第一条新闻的标题是否已经改变
                            page.wait_for_function("""
                                (oldTitle) => {
                                    const el = document.querySelector('div.news_list div.news_item:first-child div.news_item_t a');
                                    if (!el) return true; // 列表消失也是一种变化
                                    return el.innerText !== oldTitle;
                                }
                            """, arg=old_first_title, timeout=15000)
                        except Exception as e:
                            print(f"翻到下一页时超时或发生错误，抓取结束: {e}")
                            break
                    else:
                        print("找不到'下一页'按钮，抓取结束。")
                        break
            
            context.close()
            browser.close()
        
        return all_articles

    except Exception as e:
        print(f"[ERROR] A critical error occurred in news fetcher: {e}")
        return []

if __name__ == "__main__":
    # --- Test Function ---
    # 测试获取腾讯控股 (00700) 的新闻
    test_code = '00700'
    num_pages_to_fetch = 2
    print(f"--- 正在测试获取股票代码: {test_code} (腾讯控股) 的新闻 (前 {num_pages_to_fetch} 页) ---")
    
    news_list = get_company_news(test_code, max_pages=num_pages_to_fetch)
    
    if news_list:
        print(f"成功获取到 {len(news_list)} 条新闻：")
        # 只打印部分结果以方便查看
        for i, news in enumerate(news_list[:25], 1): # Display up to 25 results
            title = news.get('title', '无标题')
            url = news.get('url', '无链接')
            publish_time = news.get('publishTime', 0)
            
            try:
                if isinstance(publish_time, (int, float)) and publish_time > 0:
                    date_str = datetime.fromtimestamp(publish_time).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    date_str = "未知时间"
            except (ValueError, TypeError):
                date_str = "时间格式错误"

            print(f"{i}. [{date_str}] {title}")
            print(f"   链接: {url}")
    else:
        print("未能获取到新闻或发生错误。") 