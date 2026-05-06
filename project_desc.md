# 需求说明
爬取招聘网站的招聘信息

# 架构设计
基于 Crawl4AI + Browserless 的“按需提取与自愈”落地方案

## 核心组件设计

1. Recipe DB (规则库)：存储每家公司的抓取逻辑（即你提到的 JSON 配置）。
2. Worker Node (高速抓取节点)：完全由 Crawl4AI + Browserless 驱动，不调用昂贵的 LLM。只读取 Recipe 执行动作和数据提取。
3. Analyzer Agent (分析师智能体)：当 Worker 报告“没有规则”或“规则失效”时介入。它使用 LLM 配合页面的 Raw Markdown/HTML，重新推导并生成新的Recipe。

## 工作流设计 (LangGraph 视角)

我们可以将整个过程抽象为一个状态机（State Graph）：

1. Check_Recipe 节点：
    * 检查目标公司（如 Apple）在数据库中是否有可用的 JSON Recipe。
    * 有 -> 进入 Fast_Scrape 节点。
    * 无 -> 进入 AI_Analyze 节点。

2. Fast_Scrape 节点 (低成本, 高速度)：
    * 使用 Browserless 连接。
    * 使用 Crawl4AI，通过注入 Recipe 中的 js_code（用于点击、翻页、滚动）执行交互。
    * 使用 Recipe 中的 css_selector 进行提取（Crawl4AI 支持直接基于 CSS/XPath 提取，或者用轻量级正则提取）。
    * 校验提取结果。如果结果为空或报错（说明页面改版） -> 标记 Recipe 失效 -> 进入 AI_Analyze 节点（触发自愈）。
    * 如果成功 -> 进入 Save_Data 节点结束。

3. AI_Analyze 节点 (高成本, 高智能)：
    * 使用 Crawl4AI 完整抓取该公司的入口页面，获取极简的 Markdown (result.markdown.raw_markdown)。
    * 将 Markdown 内容及抓取目标（“提取社招岗位的标题、地点、链接”）交给 DeepSeek/GPT-4o。
    * LLM 分析后，输出标准化的 JSON Recipe：包含翻页动作指令（如果需要）和确切的提取选择器。
    * 将新生成的 Recipe 存入 Recipe DB -> 重新进入 Fast_Scrape 节点。