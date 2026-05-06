import os
import json
import asyncio
from typing import Optional, List, Dict, Any
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from crawl4ai import CrawlerRunConfig, CacheMode, JsonCssExtractionStrategy
from src.state import GraphState, JobRequirement
from src.nodes.check_recipe import save_recipe

async def search_recruitment_url(company_name: str) -> List[Dict[str, str]]:
    """
    Searches for the company's recruitment page URL using LangChain's DuckDuckGo tool.
    Returns a list of results with 'snippet', 'title', and 'link'.
    """
    search = DuckDuckGoSearchResults(output_format="list")
    results = search.invoke(f"!g {company_name} 社会招聘")
    print(f"{company_name} 社会招聘: {results}")
    return results

async def discover_css_node(state: GraphState) -> GraphState:
    """
    Discovers the recruitment URL, navigates to the job list, and analyzes CSS.
    """
    print(f"--- Discovering Recruitment URL and CSS for {state['company_name']} ---")
    
    # 1. Search for potential URLs
    search_results = await search_recruitment_url(state["company_name"])
    if not search_results:
        state["error"] = f"Could not find any search results for {state['company_name']}"
        return state

    # We'll try the top results
    urls_to_try = [r.get("link") for r in search_results[:3] if r.get("link")]
    
    llm = ChatOpenAI(
        api_key=os.getenv("DOUBAO_API_KEY"),
        base_url=os.getenv("DOUBAO_BASE_URL"),
        model=os.getenv("DOUBAO_MODEL"),
        temperature=0
    )

    crawler = state["crawler"]
    
    for url in urls_to_try:
        print(f"Checking URL: {url}")
        
        # Navigate and Handle Dynamic Content
        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            js_code="window.scrollTo(0, document.body.scrollHeight); await new Promise(r => setTimeout(r, 3000));",
            delay_before_return_html=2.0
        )
        
        try:
            result = await crawler.arun(url=url, config=run_config)
            if not result.success:
                continue
            
            markdown = result.markdown[:20000] # Limit context size
            
            # 2. LLM: Is this a job list page?
            LIST_CHECK_PROMPT = """
            Analyze the following markdown of a web page. 
            Is this a page that directly lists multiple job openings (a job list/search results page)?
            Respond with 'YES' or 'NO'. If 'NO', explain briefly why.
            
            Markdown:
            {markdown}
            """
            prompt = ChatPromptTemplate.from_template(LIST_CHECK_PROMPT)
            chain = prompt | llm
            response = await chain.ainvoke({"markdown": markdown})
            is_list = "YES" in response.content.upper()
            
            if is_list:
                print("Confirmed: This is a job list page.")
                state["url"] = url
                # 3. Analyze CSS Structure
                CSS_ANALYSIS_PROMPT = """
                Identify the CSS selectors for a JsonCssExtractionStrategy based on this markdown.
                We need to extract: job_id, title, location, link, and job_desc for each job item.
                
                URL: {url}
                Markdown:
                {markdown}
                
                Output ONLY a JSON object:
                {{
                  "baseSelector": "the CSS selector for each job item container",
                  "fields": [
                    {{"name": "title", "selector": "...", "type": "text"}},
                    {{"name": "location", "selector": "...", "type": "text"}},
                    {{"name": "link", "selector": "...", "type": "attribute", "attribute": "href"}},
                    {{"name": "job_id", "selector": "...", "type": "text"}},
                    {{"name": "job_desc", "selector": "...", "type": "text"}}
                  ]
                }}
                """
                css_prompt = ChatPromptTemplate.from_template(CSS_ANALYSIS_PROMPT)
                css_chain = css_prompt | llm
                css_response = await css_chain.ainvoke({"url": url, "markdown": markdown})
                
                content = css_response.content
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                css_schema = json.loads(content.strip())
                recipe_data = {
                    "company": state["company_name"],
                    "url": url,
                    "schema": css_schema
                }
                state["recipe_config"] = recipe_data
                save_recipe(state["company_name"], recipe_data)
                state["success"] = True
                return state
            
            else:
                # 4. LLM: Find the actual recruitment list link
                print(f"Not a list page. Reason: {response.content}")
                NAV_PROMPT = """
                The current page is not a direct job list. 
                Identify the most likely link that leads to the "Social Recruitment" or "Job Openings" list page.
                Return ONLY the absolute URL or the relative path. If none found, return 'NONE'.
                
                Current URL: {url}
                Markdown:
                {markdown}
                """
                nav_prompt = ChatPromptTemplate.from_template(NAV_PROMPT)
                nav_chain = nav_prompt | llm
                nav_response = await nav_chain.ainvoke({"url": url, "markdown": markdown})
                
                nav_url = nav_response.content.strip()
                if nav_url != "NONE" and len(nav_url) > 5:
                    # Handle relative URLs if necessary (basic joining)
                    if nav_url.startswith("/"):
                        from urllib.parse import urljoin
                        nav_url = urljoin(url, nav_url)
                    
                    print(f"Navigating to: {nav_url}")
                    # Try navigating to this new URL once
                    result = await crawler.arun(url=nav_url, config=run_config)
                    if result.success:
                        markdown = result.markdown[:20000]
                        # Re-run CSS analysis on this new page
                        css_response = await css_chain.ainvoke({"url": nav_url, "markdown": markdown})
                        content = css_response.content
                        if "```json" in content:
                            content = content.split("```json")[1].split("```")[0].strip()
                        elif "```" in content:
                            content = content.split("```")[1].split("```")[0].strip()
                        
                        css_schema = json.loads(content.strip())
                        recipe_data = {
                            "company": state["company_name"],
                            "url": nav_url,
                            "schema": css_schema
                        }
                        state["url"] = nav_url
                        state["recipe_config"] = recipe_data
                        save_recipe(state["company_name"], recipe_data)
                        state["success"] = True
                        return state

        except Exception as e:
            print(f"Error discovering on {url}: {e}")
            continue

    state["error"] = "Failed to discover job list page and CSS structure"
    state["success"] = False
    return state
