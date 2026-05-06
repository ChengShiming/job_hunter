import asyncio
from crawl4ai import AsyncWebCrawler, AdaptiveCrawler

async def main():
    async with AsyncWebCrawler() as crawler:
        # Create an adaptive crawler (config is optional)
        adaptive = AdaptiveCrawler(crawler)

        # Start crawling with a query
        result = await adaptive.digest(
            start_url="https://www.cicc.com/",
            query="社会招聘"
        )

        # View statistics
        adaptive.print_stats()

        # Get the most relevant content
        relevant_pages = adaptive.get_relevant_content(top_k=5)
        for page in relevant_pages:
            print(f"- {page['url']} (score: {page['score']:.2f})")
            
        # Get the most relevant excerpts
        for doc in adaptive.get_relevant_content(top_k=3):
            print(f"\nFrom: {doc['url']}")
            print(f"Relevance: {doc['score']:.2%}")
            print(doc['content'][:500] + "...")

if __name__ == "__main__":
    asyncio.run(main())