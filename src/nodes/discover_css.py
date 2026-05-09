import os
import json
import re
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_openai import ChatOpenAI as LangchainChatOpenAI
from langchain_core.messages import HumanMessage
from browser_use import Agent, Browser
from browser_use.agent.views import MessageCompactionSettings
from browser_use.llm import ChatDeepSeek
from src.state import GraphState
from src.nodes.check_recipe import save_recipe


def _extract_url(text: str) -> str | None:
    """Extracts the first URL from a text string."""
    for line in text.strip().split("\n"):
        line = line.strip()
        if line.startswith("http"):
            return line.rstrip("/")
    return None


async def get_official_url(company_name: str, llm: LangchainChatOpenAI) -> str | None:
    """Gets the company's official website URL, preferring LLM knowledge over search."""
    prompt = f"""What is the official website URL of the company "{company_name}"?
Return ONLY the URL string, nothing else. For example: "https://www.apple.com"
If you do NOT know or are unsure, return exactly "UNKNOWN" (do NOT guess or make up URLs)."""

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    url = _extract_url(response.content)
    if url and "UNKNOWN" not in response.content.upper():
        print(f"LLM returned official URL: {url}")
        return url

    # Fallback: DuckDuckGo search
    print(f"LLM could not determine URL for {company_name}, falling back to search...")
    try:
        search = DuckDuckGoSearchResults(output_format="list")
        results = search.invoke(f"{company_name} 官网")
        print(f"Search results: {results[:5] if results else 'none'}")
        if results:
            select_prompt = f"""从以下关于"{company_name}官网"的搜索结果中，找出最可能是该公司官方网站的URL。
只返回URL字符串。如果搜索结果中没有任何一个是该公司官网，返回第一个以 http 开头的 URL。

搜索结果：
{json.dumps(results[:5], ensure_ascii=False, indent=2)}"""
            response = await llm.ainvoke([HumanMessage(content=select_prompt)])
            url = _extract_url(response.content)
            if url:
                print(f"LLM selected from search: {url}")
                return url
    except Exception as e:
        print(f"Search fallback failed: {e}")
    return None


def build_agent_task_prompt(company_name: str, url: str) -> str:
    """Builds task prompt for browser-use Agent: navigate + extract HTML snippets only."""
    return f"""### 任务目标
从公司官网"寻找社会招聘"页面，提取职位列表页和职位详情页的 HTML 片段。你不需要分析 CSS 选择器，只需要提取 HTML。

### 初始入口
URL: {url}

### ⚠️ 第一步：语言检查
打开页面后检查是否为英文。如果是英文，找语言切换按钮切到中文。

### 寻路规则
1. 优先找导航栏中的"加入我们"、"人才招聘"、"Careers"、"Jobs"等入口
2. 筛选"社会招聘"/"经验人士"/"Experienced"，避开"校园招聘"/"实习生"
3. 遇到弹窗直接关掉

### 阶段 1 — 提取职位列表 HTML
到达职位列表页后，用 JavaScript evaluate 提取 HTML 片段：
```js
(function() {{
  // 找到职位列表的容器元素（如 table、ul、div.list 等）
  // 提取容器本身 + 前 3 个职位 item 的完整 HTML（包含所有 class/id 属性）
  const items = document.querySelectorAll('...');  // 根据实际页面调整选择器
  let html = '';
  for (let i = 0; i < Math.min(3, items.length); i++) {{
    html += items[i].outerHTML + '\\n';
  }}
  return html;
}})()
```
注意：outerHTML 必须包含所有 class、id、href 等属性，不要截断。

### 阶段 2 — 提取职位详情 HTML
点击第一个职位进入详情页，用 JavaScript evaluate 提取详情内容区域的 HTML：
```js
(function() {{
  // 找到详情内容容器（包含职位描述和岗位要求的父元素）
  const container = document.querySelector('...');  // 根据实际页面调整
  return container ? container.outerHTML.substring(0, 5000) : 'no container';
}})()
```

### 效率规则
1. 用 evaluate 直接提取 HTML，不要反复用 find_elements
2. 每到一个新页面先确认 URL，不要在已在目标页面上时重复点击导航链接
3. 页面上等待最多 2 次，仍不加载就尝试其他入口

### 输出格式
严格按照以下格式输出，每个标记独占一行：

===LIST_URL===
职位列表页完整URL

===LIST_HTML===
职位容器的HTML片段（含前2-3个完整item的outerHTML）

===DETAIL_URL===
职位详情页URL（包含参数如 ?jobAdId=xxx）

===DETAIL_HTML===
详情内容区域的HTML片段
"""


def parse_agent_html_output(raw_output: str) -> dict | None:
    """Parses the Agent's HTML extraction output into URL and HTML dict."""
    sections = {}

    for marker in ["LIST_URL", "LIST_HTML", "DETAIL_URL", "DETAIL_HTML"]:
        pattern = f"==={marker}===\\s*\\n?(.*?)(?=\\n===|$)"
        match = re.search(pattern, raw_output, re.DOTALL)
        if match:
            sections[marker.lower()] = match.group(1).strip()

    required = ["list_url", "list_html", "detail_url", "detail_html"]
    for key in required:
        if key not in sections or not sections[key]:
            print(f"Missing section in Agent output: {key}")
            return None

    return sections


async def generate_recipe_from_html(
    extracted: dict, company_name: str, llm: LangchainChatOpenAI
) -> dict | None:
    """Doubao analyzes HTML snippets to infer CSS selectors and generate recipe JSON."""
    prompt = f"""分析以下"{company_name}"招聘网站的 HTML 片段，推断出用于 Crawl4AI JsonCssExtractionStrategy 的 CSS 选择器。

### 职位列表页
URL: {extracted["list_url"]}
HTML 片段（前几个职位 item）:
```html
{extracted["list_html"][:6000]}
```

### 职位详情页
URL: {extracted["detail_url"]}
HTML 片段（详情内容区域）:
```html
{extracted["detail_html"][:4000]}
```

### 要求
1. 从列表 HTML 中找到每个职位 item 的共同容器选择器（baseSelector）
2. 确定各字段相对于 baseSelector 的选择器：title、location、link（href 属性）、job_id
3. 从详情 HTML 中确定 job_desc 和 job_requirements 的选择器
4. 注意：job_detail_url_template 通常为 null，因为列表页的 link 字段已经包含完整的详情页 URL（含 jobAdId 等参数）。只有当详情页 URL 需要拼装时才设置模板。
5. job_id 字段的选择器应指向列表项中能唯一标识职位的元素（如 title 文本中的括号编号，或 link URL 中的 ID 参数）。如果从 HTML 中无法直接提取，可设为与 title 相同的选择器，后续会从 link URL 中自动解析。

仅输出 JSON：
{{
  "company": "{company_name}",
  "job_list_url": "列表页URL",
  "job_list_schema": {{
    "baseSelector": "...",
    "fields": [
      {{"name": "title", "selector": "...", "type": "text"}},
      {{"name": "location", "selector": "...", "type": "text"}},
      {{"name": "link", "selector": "...", "type": "attribute", "attribute": "href"}},
      {{"name": "job_id", "selector": "...", "type": "text"}}
    ]
  }},
  "job_detail_url_template": null,
  "job_detail_schema": {{
    "baseSelector": "...",
    "fields": [
      {{"name": "job_desc", "selector": "...", "type": "text"}},
      {{"name": "job_requirements", "selector": "...", "type": "text"}}
    ]
  }}
}}"""

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    content = response.content.strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        print(f"Doubao failed to generate valid JSON. Output:\n{content[:2000]}")
        return None


def _is_placeholder(value: str) -> bool:
    if not value or not isinstance(value, str):
        return True
    value = value.strip()
    if not value or value in ("...", "…"):
        return True
    if value.startswith("选择器") or value == "selector":
        return True
    return False


def _validate_schema(schema: dict, schema_name: str) -> bool:
    if not isinstance(schema, dict):
        print(f"{schema_name} is not a dict")
        return False
    if "baseSelector" not in schema or _is_placeholder(schema["baseSelector"]):
        print(f"{schema_name} has invalid baseSelector: {schema.get('baseSelector')}")
        return False
    if "fields" not in schema or not isinstance(schema["fields"], list):
        print(f"{schema_name} missing or invalid fields")
        return False
    for field in schema["fields"]:
        if _is_placeholder(field.get("selector", "")):
            print(f"{schema_name} field '{field.get('name')}' has placeholder selector")
            return False
    return True


def validate_recipe(recipe: dict) -> dict | None:
    """Validates a complete recipe has all required keys and valid schemas."""
    for key in ["company", "job_list_url", "job_list_schema", "job_detail_schema"]:
        if key not in recipe:
            print(f"Missing required key in recipe: {key}")
            return None
    if not recipe["job_list_url"].startswith("http"):
        print(f"Invalid job_list_url: {recipe['job_list_url']}")
        return None
    if not _validate_schema(recipe["job_list_schema"], "job_list_schema"):
        return None
    if not _validate_schema(recipe["job_detail_schema"], "job_detail_schema"):
        return None
    return recipe


async def discover_css_node(state: GraphState) -> GraphState:
    """Discovers recruitment page URL and CSS structure using browser-use Agent + Doubao analysis."""
    company_name = state["company_name"]
    print(f"--- Discovering Recruitment URL and CSS for {company_name} ---")

    url_llm = LangchainChatOpenAI(
        api_key=os.getenv("DOUBAO_API_KEY"),
        base_url=os.getenv("DOUBAO_BASE_URL"),
        model=os.getenv("DOUBAO_MODEL"),
        temperature=0,
    )

    # 1. Get company official website URL
    official_url = await get_official_url(company_name, url_llm)
    if not official_url:
        state["error"] = f"Could not determine official website URL for {company_name}"
        state["success"] = False
        return state
    print(f"Using official URL: {official_url}")

    # 2. browser-use Agent navigates and extracts HTML snippets
    try:
        browser = Browser.from_system_chrome()
        agent = Agent(
            task=build_agent_task_prompt(company_name, official_url),
            llm=ChatDeepSeek(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url=os.getenv("DEEPSEEK_BASE_URL"),
                model=os.getenv("DEEPSEEK_MODEL"),
                temperature=0,
            ),
            browser=browser,
            max_steps=25,
            message_compaction=MessageCompactionSettings(compact_every_n_steps=10),
        )

        history = await agent.run()
        raw_output = history.final_result()
        print(f"Agent HTML output:\n{raw_output[:3000]}")

        # Parse HTML snippets from Agent output
        extracted = parse_agent_html_output(raw_output)
        if not extracted:
            state["error"] = "Agent did not return valid HTML snippets"
            state["success"] = False
            return state

        # 3. llm analyzes HTML snippets to generate recipe
        print("Generating recipe from HTML snippets via Doubao...")
        recipe = await generate_recipe_from_html(extracted, company_name, url_llm)
        if not recipe:
            state["error"] = "Doubao failed to generate recipe from HTML"
            state["success"] = False
            return state

        recipe = validate_recipe(recipe)
        if not recipe:
            state["error"] = "Generated recipe failed validation"
            state["success"] = False
            return state

        state["url"] = recipe["job_list_url"]
        state["recipe_config"] = recipe
        save_recipe(company_name, recipe)
        state["success"] = True
        state["error"] = None
        print(f"Successfully discovered recipe for {company_name}")

    except Exception as e:
        print(f"Error in discover_css_node: {e}")
        state["error"] = f"Discovery failed: {str(e)}"
        state["success"] = False

    return state
