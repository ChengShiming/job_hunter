import asyncio
import sys
from src.graph import create_graph
from crawl4ai import AsyncWebCrawler, BrowserConfig
from dotenv import load_dotenv

load_dotenv()

def get_browser_config() -> BrowserConfig:
    """Configures the browser for Crawl4AI using local Chromium."""
    return BrowserConfig(
        browser_type="chromium",
        headless=True,
        enable_stealth=True,
        extra_args=["--accept-lang=zh-CN,zh;q=0.9", "--lang=zh-CN"],
    )

async def process_company(app, crawler, company_name: str):
    """Processes a single company."""
    print(f"\n{'='*20}")
    print(f"Starting job hunter for: {company_name}")
    print(f"{'='*20}\n")
    
    # Initial state
    initial_state = {
        "url": None,
        "company_name": company_name,
        "recipe_config": None,
        "scraped_data": [],
        "error": None,
        "retry_count": 0,
        "success": False,
        "crawler": crawler # Pass the crawler instance
    }
    
    try:
        final_state = await app.ainvoke(initial_state)
        if final_state["success"]:
            print(f"✅ Scraping completed for {company_name}!")
        else:
            print(f"❌ Scraping failed for {company_name}. Error: {final_state['error']}")
    except Exception as e:
        print(f"💥 Exception processing {company_name}: {e}")

async def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <company_name1> <company_name2> ...")
        sys.exit(1)
        
    # Simple parser for company names
    companies = sys.argv[1:]
    
    # Initialize the graph app once
    app = create_graph()
    
    # Use one crawler instance for all companies to reuse connections
    browser_config = get_browser_config()
    async with AsyncWebCrawler(config=browser_config) as crawler:
        for company in companies:
            await process_company(app, crawler, company)

if __name__ == "__main__":
    asyncio.run(main())
