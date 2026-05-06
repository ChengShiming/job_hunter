import json
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode, JsonCssExtractionStrategy
from src.state import GraphState, JobRequirement

async def fast_scrape_node(state: GraphState) -> GraphState:
    """Performs scraping using JsonCssExtractionStrategy and the saved schema."""
    if not state["recipe_config"]:
        state["error"] = "No recipe config found"
        return state

    schema = state["recipe_config"].get("schema", {})
    # Support both camelCase (crawl4ai standard) and snake_case (legacy)
    base_selector = schema.get("baseSelector") or schema.get("base_selector")
    if not schema or not base_selector:
        state["error"] = "Recipe schema is invalid or missing baseSelector"
        return state

    # Ensure the schema used by crawl4ai has the correct key
    if "baseSelector" not in schema and "base_selector" in schema:
        schema["baseSelector"] = schema["base_selector"]

    print(f"--- Fast Scraping for {state['company_name']} using JsonCssExtractionStrategy ---")
    
    # Use JsonCssExtractionStrategy with the saved schema
    extraction_strategy = JsonCssExtractionStrategy(schema)
    
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        extraction_strategy=extraction_strategy,
        delay_before_return_html=3.0,
        wait_for_timeout=10000 
    )

    try:
        crawler = state["crawler"]
        result = await crawler.arun(url=state["url"], config=run_config)
        
        if not result.success:
             state["error"] = f"Scrape failed: {result.error_message}"
             state["success"] = False
        else:
            try:
                data = json.loads(result.extracted_content)
                if not data:
                    state["error"] = "Extracted data is empty"
                    state["success"] = False
                else:
                    state["scraped_data"] = [JobRequirement(**item) for item in data]
                    state["success"] = True
                    state["error"] = None
            except json.JSONDecodeError:
                state["error"] = "Failed to parse extracted JSON"
                state["success"] = False
                
    except Exception as e:
        state["error"] = f"Fast scrape exception: {str(e)}"
        state["success"] = False

    return state
