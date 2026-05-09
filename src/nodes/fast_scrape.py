import json
from urllib.parse import urljoin, urlparse, parse_qs
from crawl4ai import CrawlerRunConfig, CacheMode, JsonCssExtractionStrategy
from src.state import GraphState, JobRequirement


def _parse_job_id_from_url(url: str) -> str:
    """Extracts job_id from a detail page URL query parameter."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    for key in ("jobAdId", "jobId", "job_id", "id", "positionId"):
        if key in params and params[key]:
            return params[key][0]
    return ""


async def fast_scrape_node(state: GraphState) -> GraphState:
    """Performs scraping using the new recipe format (job_list_schema + job_detail_schema)."""
    if not state["recipe_config"]:
        state["error"] = "No recipe config found"
        state["success"] = False
        return state

    recipe = state["recipe_config"]

    # Validate job_list_schema
    list_schema = recipe.get("job_list_schema", {})
    list_base = list_schema.get("baseSelector")
    if not list_schema or not list_base:
        state["error"] = "Recipe is invalid or missing job_list_schema.baseSelector"
        state["success"] = False
        return state

    list_url = recipe.get("job_list_url") or state.get("url")
    if not list_url:
        state["error"] = "No job_list_url in recipe"
        state["success"] = False
        return state

    print(f"--- Fast Scraping for {state['company_name']} ---")

    crawler = state["crawler"]
    detail_schema = recipe.get("job_detail_schema", {})
    detail_template = recipe.get("job_detail_url_template")

    try:
        # Step 1: Scrape job list page
        list_strategy = JsonCssExtractionStrategy(list_schema)
        list_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            extraction_strategy=list_strategy,
            delay_before_return_html=3.0,
            wait_for_timeout=10000,
        )
        list_result = await crawler.arun(url=list_url, config=list_config)

        if not list_result.success:
            state["error"] = f"List scrape failed: {list_result.error_message}"
            state["success"] = False
            return state

        try:
            list_data = json.loads(list_result.extracted_content)
        except json.JSONDecodeError:
            state["error"] = "Failed to parse list page extracted JSON"
            state["success"] = False
            return state

        if not list_data:
            state["error"] = "List page extracted data is empty"
            state["success"] = False
            return state

        # Step 2: Scrape each job detail page
        jobs = []
        for item in list_data:
            # Determine detail URL
            link_url = item.get("link", "")
            if detail_template:
                raw_job_id = item.get("job_id", "")
                detail_url = detail_template.replace("{job_id}", str(raw_job_id))
            else:
                detail_url = link_url
                if detail_url:
                    detail_url = urljoin(list_url, detail_url)

            # Parse job_id from detail URL if not already set
            job_id = str(item.get("job_id", ""))
            if not job_id and detail_url:
                job_id = _parse_job_id_from_url(detail_url)

            if not detail_url:
                jobs.append(JobRequirement(
                    job_id=job_id, title=str(item.get("title", "")),
                    location=str(item.get("location", "")), link=link_url,
                ))
                continue

            # Scrape detail page if schema is available
            if detail_schema and detail_schema.get("baseSelector"):
                detail_strategy = JsonCssExtractionStrategy(detail_schema)
                detail_config = CrawlerRunConfig(
                    cache_mode=CacheMode.BYPASS,
                    extraction_strategy=detail_strategy,
                    delay_before_return_html=2.0,
                    wait_for_timeout=10000,
                )
                detail_result = await crawler.arun(url=detail_url, config=detail_config)

                job_desc = ""
                job_requirements = ""
                if detail_result.success:
                    try:
                        detail_data = json.loads(detail_result.extracted_content)
                        if isinstance(detail_data, list) and detail_data:
                            detail_data = detail_data[0]
                        if isinstance(detail_data, dict):
                            job_desc = str(detail_data.get("job_desc", ""))
                            job_requirements = str(detail_data.get("job_requirements", ""))
                    except json.JSONDecodeError:
                        pass
            else:
                job_desc = ""
                job_requirements = ""

            jobs.append(JobRequirement(
                job_id=job_id, title=str(item.get("title", "")),
                location=str(item.get("location", "")), link=link_url,
                job_desc=job_desc, job_requirements=job_requirements,
            ))

        state["scraped_data"] = jobs
        state["success"] = True
        state["error"] = None
        print(f"Scraped {len(jobs)} jobs for {state['company_name']}")

    except Exception as e:
        state["error"] = f"Fast scrape exception: {str(e)}"
        state["success"] = False

    return state
