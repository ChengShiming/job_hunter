from browser_use import Agent, Browser
from browser_use.llm import ChatDeepSeek
import asyncio, os
from dotenv import load_dotenv

load_dotenv()

async def main():
    # browserless_api_key = os.getenv("BROWSERLESS_API_KEY")
    # browser = Browser(
    #     cdp_url=f"wss://chrome.browserless.io?token={browserless_api_key}"
    #     # use_cloud=True,  # Use a stealth browser on Browser Use Cloud
    # )
    # browser = Browser(
    #     use_cloud=True,  # Use a stealth browser on Browser Use Cloud
    # )
    browser = Browser.from_system_chrome()

    agent = Agent(
        task="""
### 任务目标
从官网首页开始，寻找并进入“社会招聘”页面，并为后续的自动化采集招聘职位生成一份“抓取食谱 (Scraping Recipe)”。

### 初始入口
URL: https://www.cicc.com/

### 寻路规则
1. 优先寻找导航栏中的"加入我们" 或 "人才招聘"等招聘相关菜单。
2. 进入招聘主页后，筛选“社会招聘”或“经验人士”，避开“校园招聘”或“实习生”。
3. 如果遇到 Cookie 弹窗或国家/语言选择，请直接处理掉。

### 录制要求 (CRITICAL)
到达职位列表页后，停下来分析 DOM 结构，找出：
- **baseSelector**: 职位列表 (Job Container) 的 CSS Selector。
- **Relative Fields**: 内部字段相对于 `baseSelector` 的选择器：标题 (title)、地点 (location)、发布日期 (date)、详情页链接 (link)。
- **翻页逻辑**：是否有“下一页”按钮或“加载更多”按钮？记录其类型及选择器。

### 输出格式
任务完成后，请仅输出一个标准 JSON 对象，格式如下：
{
  "company_name": "公司名",
  "entry_url": "初始 URL",
  "final_target_url": "职位列表页真实 URL",
  "navigation_steps": [
    {"action": "click", "selector": "选择器", "description": "操作描述"}
  ],
  "extraction_recipe": {
    "name": "job_listings",
    "baseSelector": "职位列表的 CSS Selector",
    "fields": [
      {
        "name": "title",
        "selector": "相对于 baseSelector 的标题选择器",
        "type": "text"
      },
      {
        "name": "location",
        "selector": "相对于 baseSelector 的地点选择器",
        "type": "text"
      },
      {
        "name": "link",
        "selector": "相对于 baseSelector 的详情页链接选择器",
        "type": "attribute",
        "attribute": "href"
      },
      {
        "name": "date",
        "selector": "相对于 baseSelector 的发布日期选择器",
        "type": "text"
      }
    ]
  },
  "pagination": {
    "type": "scroll/click/number",
    "selector": "翻页按钮选择器"
  }
}
        """,
        llm=ChatDeepSeek(
            model="deepseek-chat", 
            temperature=0,
            api_key="sk-a59230172ae349848b9632d18155c1ae",
            base_url="https://api.deepseek.com"
        ),
        browser=browser,
        calculate_cost=True
    )


    history = await agent.run()

    # Get usage from history
    print(f"Token usage: {history.usage}")

    # Or get from usage summary
    usage_summary = await agent.token_cost_service.get_usage_summary()
    print(f"Usage summary: {usage_summary}")

if __name__ == "__main__":
    asyncio.run(main())