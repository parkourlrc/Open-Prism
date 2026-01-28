from datetime import datetime

from ..aient.aient.plugins import (
    # read_file,
    # read_image,
    register_tool,
    # write_to_file,
    excute_command,
    # list_directory,
    # get_url_content,
    # run_python_script,
    # set_readonly_path,
    # get_search_results,
    # download_read_arxiv_pdf,
)

from ..aient.aient.architext.architext import Messages, SystemMessage, UserMessage, AssistantMessage, ToolCalls, ToolResults, Texts, RoleMessage, Images, Files

from .write_file import write_to_file

from beswarm.tools import (
    # worker,
    # get_code_repo_map,
    # search_arxiv,
    # edit_file,
    # request_admin_input,
    search_web,
    create_task,
    get_task_result,
    get_all_tasks_status,
    resume_task,
    create_tasks_from_csv,
    get_node_details,
    add_knowledge_node,
    delete_knowledge_node,
    rename_knowledge_node,
    move_knowledge_node,
    get_knowledge_graph_tree,
    add_tags_to_knowledge_node,
    remove_tags_from_knowledge_node,
)

from ..core import mcp_manager, broker, kgm, get_task_manager, current_task_manager, current_work_dir
from ..agents.planact import BrokerWorker


@register_tool()
def get_task1_goal(query: str):
    """
    根据用户查询获取任务1的目标。

    返回的字符串将用作初始任务的“目标”。
    它包含了指导AI代理（扮演“首席情报官”）从网络搜索结果构建知识图谱的说明。

    参数:
        query: 用户的搜索查询。

    返回:
        一个格式化的字符串，包含任务的详细目标提示。
    """
    return (
        f"用户查询：{query}"
        """
调用 search_web 工具搜索，该工具会把搜索结果保存到 csv 文件中。

**禁止**使用任何方式读取任何 csv 文件。搜索结果的csv文件是给create_tasks_from_csv工具用的，**禁止**直接读取。

然后使用 create_tasks_from_csv 工具，从 csv 文件中创建多个子任务。

csv 的 title 是 query, url和content，content是url对应的网页内容。query 是查询内容。

下面是通过 create_tasks_from_csv 创建子任务需要传入的 goal 模版，请将```内字符串原样传入，不要修改：

```
### **Deep Search & Synthesis Prompt (深度搜索与综合 Prompt)**

**核心任务:** 你是一位**首席情报官、信息整合大师与战略分析师**。你的唯一目标是，围绕核心查询 (`{query}`), 通过深度分析指定URL (`{url}`) 的内容 (在 `<content>` 标签内), 动态地构建并填充一个**充满洞察、结构清晰、并具备决策价值**的知识图谱。

**【决策者画像】**
你的用户是一位**聪明的领域分析师、研究员或战略决策者**。他们需要一个关于 `{query}` 的、超越了简单链接列表的、结构化的深度理解。你的输出必须兼顾信息的精确性和整体格局的洞察力。

**【第一原则 / The Prime Directive: 将信息转化为可行动的战略洞察】**
1.  **【价值创造】** 你的目标远不止于信息的摘要，而是**提炼全新的理解、识别关键联系、并揭示潜在的洞察**。这要求你必须做到：**识别核心论点与反方观点**、**提取关键数据与证据**、**映射关键实体（人物、组织）及其关系**、**指明新兴趋势与待解问题**。
2.  **【结构即大纲与查询根节点】** 整个知识图谱**必须且只能有一个根节点**，它代表核心查询 `{query}`。所有信息都必须是此根节点的子孙节点。当分析新内容时，应将其**核心观点**填充到**根节点下已有的主题节点**中（例如“核心论点”或“关键数据”），而非创建重复的结构。
3.  **【来源可溯源】** 图谱中的**每一个信息点**都必须明确标注其来源 `#source:{url}`。
4.  **【整合优先，审慎创建】** 尽一切努力将新信息归入现有的大纲结构中。只有当一个观点在逻辑上完全无法融入当前结构时，才考虑调整大纲（例如，新增一个“争议焦点”的三级标题）。
5.  **【拥抱涌现】** 对 `{query}` 的理解是在持续分析中动态生长和重构的有机体，要为未来的可能性保留空间。
6.  **【类别与实例分离】** **二级、三级节点必须是抽象的标题** (如 “关键人物”, “支持性证据”)。**具体的人物、组织、数据点等实例，只能作为叶子节点存在于各级标题之下。**
7.  **【层级为骨，标签为魂】** 使用**层级结构**来表示信息的**主题归属关系**。对于所有**次要的、跨领域的、多维度的属性** (如观点倾向、证据类型)，**必须**使用**标签**来表示。

**【命名风格规范】**
所有节点的名称**必须**采用 **“中文名称 (英文全称或常用缩写)”** 的格式。

**输入信息:**
- **查询 (Query):** {query}
- **URL:** {url}
- **网页内容 (Content):** 在 `<content>` 标签内
<content>
{content}
</content>

**核心工作流:**

你必须严格遵循以下**五个步骤**的思维与行动模型来完成任务：

1.  **【第1步：审视全局与校准意图 (Review Landscape & Calibrate Intent)】**
    *   调用 `get_knowledge_graph_tree` 工具，深入理解当前围绕 `{query}` 已构建的**知识图谱结构、核心主题、以及已有的标签体系**。明确当前分析的主要目的是为了填补哪些信息空白。

2.  **【第2步：快速甄别与多维深潜 (Triage & Multi-dimensional Deep Dive)】**
    *   **快速甄别:** 首先，判断该 `{url}` 的 `content` 是否与 `{query}` **直接相关**。如果完全无关，则**立即调用 `task_complete` 并注明“内容不相关”**，终止任务。
    *   **多维深潜:** 如果相关，则必须从以下**多个维度**对内容进行强制性的深度分析：
        *   **核心论点评估 (Central Thesis Assessment):** 此内容针对 `{query}` 提出了什么**核心观点、主张或关键信息**？
        *   **证据与数据提取 (Evidence & Data Extraction):** 内容中是否包含可量化的**数据、统计、关键性能指标或强力证据**？必须将其作为独立节点提取。(标签: `#数据点`, `#统计数据`, `#案例研究`)
        *   **立场与偏见识别 (Stance & Bias Identification):** 作者或来源对 `{query}` 持什么立场？是**支持、反对，还是中立**？是否存在明显的**商业或意识形态偏见**？ (标签: `#支持观点`, `#反对观点`, `#中立分析`, `#商业推广`)
        *   **关键实体识别 (Key Entity Recognition):** 内容中是否提到了与 `{query}` 相关的**关键人物、组织、产品或技术**？这些应被识别并可能成为独立的节点。
        *   **观点链接 (Argument Interconnectivity):** 此内容的观点是否**印证、反驳或补充**了知识图谱中已有的某个观点？
        *   **信源强度评估 (Source Strength Assessment):** 该来源的**权威性**如何？是**官方报告、专家分析、新闻报道，还是用户生成内容**？ (标签: `#权威信源`, `#专家意见`, `#媒体报道`, `#用户评论`)
        *   **洞察提炼 (Actionable Insight Distillation):** 该信息是否揭示了某个**新兴趋势、潜在风险、商业机会或有待进一步研究的问题**？ (标签: `#新兴趋势`, `#潜在风险`, `#未来方向`)

3.  **【第3步：精确整合 (Precise Integration)】**
    *   根据你的多维分析，调用工具 (`add_knowledge_node`, `add_tags_to_knowledge_node` 等) 将内容的知识点精确地整合进图谱。
    *   **必须立即**为所有新节点打上**来源标签 (`#source:{url}`)** 和在第2步中规划好的所有**分析标签**。

4.  **【第4步：自我审查与价值综合 (Self-Correction & Value Synthesis)】**
    *   **在你调用`task_complete`之前，必须执行这一最终的、强制性的审查与综合步骤。**
    *   再次调用 `get_knowledge_graph_tree()`，审视整个知识图谱，并对照以下的**【高价值情报简报清单】**进行重构：
        *   **检查项1 (来源可溯源性):** 图谱中的**每一个信息点**是否都已正确、无遗漏地标注了其 `#source:{url}`？
        *   **检查项2 (结构一致性):** 整个知识图谱是否严格维持在**单一查询根节点**之下？我是否将新信息正确**填充**到了已有的主题中，而不是创建了重复的类别？
        *   **检查项3 (观点综合呈现):** 我是否已将**对立或互补的观点**组织在专门的标题下（如“争议焦点”）进行**对比呈现**？
        *   **检查项4 (数据集中化):** 我能否创建一个对比性的列表或小节，来**并列呈现不同来源的关键数据**？
        *   **检查项5 (关键实体网络):** 我是否清晰地展示了**核心实体（人物、组织）及其之间的关系**？
        *   **检查项6 (洞察凸显):** **最具价值的洞察** (例如，被标记为 `#新兴趋势` 或 `#潜在风险` 的节点) 是否被组织在了专门的“**核心摘要**”或“**战略展望**”章节下，使其一目了然？
    *   **如果检查发现任何可以提升情报价值的机会，你必须立即调用相应工具进行重构。**

5.  **【第5步：完成任务 (Finalize)】**
    *   只有当你确认知识图谱（情报简报）在**结构、逻辑、深度和洞察力**上都达到了你作为**首席情报官**的最高标准时，才能调用 `task_complete` 结束你的任务。
```
观察知识图谱，如果当前信息不足以回答用户的查询，则继续从不同角度搜索，直到信息足够为止。继续循环上一个子任务，直到信息足够为止。
        """
    )

@register_tool()
def get_task2_goal(query: str):
    """
    根据用户查询生成任务2的目标。

    这个函数为第二个子任务创建一个详细的提示。该子任务的目标是
    扮演一个“首席分析师”的角色，基于第一个任务构建的知识图谱，
    生成一份最终的情报分析报告。

    返回的字符串是一个模版，将用作第二个主要任务的“目标”。
    它包含了指导AI代理如何审视知识图谱、构建报告大纲、
    通过创建更多子任务来并行撰写报告的各个章节、
    最终将所有章节整合成一份完整报告的详细说明。

    参数:
        query: 用户的搜索查询。

    返回:
        一个格式化的字符串，包含任务的详细目标提示。
    """
    return (
        f"用户查询：{query}"
        """
### **Deep Synthesis & Report Generation Prompt (深度综合与报告生成 Prompt)**

**任务:** 你是一位顶尖的**首席分析师**和资深的**情报报告总编辑**。你和你的情报官团队已经围绕核心查询 (`{query}`)，成功构建了一个高度结构化、信息丰富的知识图谱。现在，你的最终任务是基于这个完美的知识图谱，撰写一篇全面、深入、且具备决策价值的**最终情报分析报告**。

**【最高指导原则：结构即洞察，深度源于综合】**
1.  **以图谱为唯一蓝本:** 你撰写的报告，其**章节、段落、乃至论述的逻辑顺序，都必须严格遵循我们已经构建好的知识图谱树状结构**。图谱的层级就是你报告的层级。
2.  **融合细节，提炼洞察:** 不要简单地罗列图谱中的叶子节点信息（如单个数据或观点）。你的任务是**综合**一个类别下的所有实例（叶子节点），并**提炼**出该类别的**核心趋势、关键发现、主要争论点或战略启示**。
3.  **引用来源，彰显可信:** 在论述中提及任何具体信息、数据或观点时，你**必须**利用记录在节点`tags`中的`#source`信息，以清晰的方式（如 `(Source: {url})`）来标注来源。

**你的工作流程:**

你将采用一种**“总编规划 -> 分析师并行撰写 -> 总编整合终审”**的专业报告生成工作流。

1.  **【第1步：全局情报审视 (Global Intelligence Review)】**
    *   调用 `get_knowledge_graph_tree`，获取最终的、完整的知识图谱。这是你撰写报告的唯一事实来源，也是你分发给手下分析师们的“共享数据库”。

2.  **【第2步：构建报告大纲并分派任务 (Report Outline & Task Delegation)】**
    *   **a. 构思报告框架**: 基于你对整个知识图谱的理解，创造一个符合专业情报报告范式、具有逻辑递进关系的**报告大纲（即报告目录）**。例如，可以包含“执行摘要”、“核心发现”、“关键实体分析”、“数据与证据”、“新兴趋势与风险”、“战略展望”等章节。
    *   **b. 精准定位素材**: 对于大纲中的**每一个章节**，明确指出它对应知识图谱中的**哪一个或哪几个主要分支**。这是你接下来要分派给每个分析师的“撰写范围”。
    *   **c. 分派撰写子任务**: 基于你的大纲，调用`create_task`工具，为**每一个章节**创建一个并行的子任务。你**必须**将以下信息清晰地传递给每个子任务的`goal`中：
        *   **`section_title`**: 你为该章节设定的标题。
        *   **`list_of_relevant_kg_paths`**: 你在(b)步中为该章节划定的、在知识图谱中对应的源路径列表。
        *   **`full_report_outline`**: 完整的报告大纲，让每个分析师都了解自己的工作在整个报告中的位置，以便更好地把握上下文和撰写口吻。
        *   **`chief_analyst_notes`**: （可选但推荐）你作为总编辑对本章撰写的特别指示，例如“本章重点要突出不同来源观点的冲突与矛盾”或“请将本章数据进行可视化呈现的建议”。

3.  **【第3步：监控与等待 (Monitor & Wait)】**
    *   所有章节的撰写任务已并行派出。你的任务是监控它们的进度，并使用`get_task_result`工具，以等待所有撰写任务全部完成。

4.  **【第4步：整合与终审 (Integration & Final Review)】**
    *   调用`get_task_result`返回了所有子任务的结果，现在你的手上有多份独立的Markdown章节草稿。
    *   你的任务是：
        a. **整合**: 将所有章节草稿按照你最初设计的大纲顺序，合并成一篇完整的分析报告。
        b. **审校**: 通读全文，检查章节间的过渡是否流畅，术语使用是否一致，整体风格是否统一。进行必要的编辑和润色。
        c. **撰写执行摘要与战略展望**: 基于所有章节的深度内容，亲自撰写全文的**“执行摘要”**（提炼核心洞察给决策者）和**“战略展望”**（指明未来方向和建议）部分，为整篇报告注入灵魂。

5.  **【第5步：完成任务 (Finalize)】**
    *   当你对这篇由团队协作完成、并由你亲自统稿的报告感到满意时，编写执行摘要和战略展望章节，编写脚本通过 excute_command 使用 cat 和输出重定向进行文件内容拼接将所有章节合并到同一个md文件保存到本地，最后调用 `task_complete`，并将**最终的、完整的Markdown报告全文的文件路径**作为`message`参数返回。

---
### **【分析师专用】子任务`goal`** (注意：这是子任务的`goal`，填入必要信息后，将下面的goal原样完整传给子-任务执行，不要修改)

**任务:** 你是一位专业的领域分析师。你的总编辑已经为你规划好了整篇报告的结构，并为你分配了具体的章节撰写任务。

**你的撰写任务:**

- **章节标题:** `{section_title}` (例如: "3. 关键实体分析")
- **撰写范围 (知识图谱路径):** `{list_of_relevant_kg_paths}` (例如: `["{query}/关键人物", "{query}/相关组织"]`)

**核心指令:**

1.  **获取全局图谱**: 首先，调用 `get_knowledge_graph_tree` 获取完整的、最新的知识图谱，作为你的参考背景。

2.  **聚焦与深挖**: 将你的注意力**严格限制**在你被分配的撰写范围（`{list_of_relevant_kg_paths}`）内。
    *   遍历这些分支下的所有叶子节点。
    *   对于每一个重要的叶子节点，调用 `get_node_details` 来获取其完整的`description`（其中包含了核心信息）和`#source`标签。

3.  **提炼与叙述**: 基于你收集到的详细信息，撰写一段**只关于本章节内容**的、逻辑连贯、语言流畅的Markdown文本保存到本地。
    *   你需要综合信息，提炼观点（例如，总结某一类实体的共同特征或相互关系），而不是简单地罗列事实。
    *   在论述中提及任何具体信息或数据时，**必须**以 `(Source: {url})` 的格式清晰地标注其来源。
    *   如果需要，可以使用Markdown的表格来对比不同来源的数据。

4.  **串行写作:** 你将以串行的方式，逐一完成每一个二级标题的撰写，分阶段写入本地文件。对于每个需要撰写的二级标题的内容，查看知识图谱分析是否存在可以补充的背景信息，调用 get_node_details 获取信息来补充。

5.  **对于每一个二级标题，你必须遵循以下写作规范:**
    *   a. **规划段落:** 在动笔前，先构思好要写2-3个段落来阐述观点。**禁止**使用不必要的无序列表。
    *   b. **详细阐述:** 确保内容详实、有据可依、逻辑清晰，确保篇幅适中，每个二级标题只有一段是不合适的。
    *   c. **承上启下:** 在开始撰写一个新的二级标题时，你的第一句话应该巧妙地与上一个标题的内容进行关联或对比，以确保章节的流畅性。

6.  **完成本章**: 当你完成了本章节的撰写后，调用 `task_complete`，并将**你撰写的本章节Markdown文本的文件路径**作为`message`参数返回。**不要包含任何额外的内容，只返回你负责的这一章。**
        """
    )

tools = [
    write_to_file,
    excute_command,
    search_web,
    create_task,
    get_task_result,
    get_all_tasks_status,
    resume_task,
    create_tasks_from_csv,
    get_knowledge_graph_tree,
    add_knowledge_node,
    add_tags_to_knowledge_node,
    rename_knowledge_node,
    move_knowledge_node,
    get_node_details,
    get_task1_goal,
    get_task2_goal,
]

@register_tool()
async def deepsearch(query: str, work_dir: str):
    """
    执行一个深度搜索和综合任务，分为两个主要阶段。

    deepsearch 任务通过编排两个连续的子任务来响应用户查询。
    首先，它启动一个“情报收集”阶段，然后是一个“报告生成”阶段。

    参数:
        query (str): 用户的原始搜索查询。
        work_dir (str): 工作目录的绝对路径。deepsearch 任务将在此目录上下文中执行操作。deepsearch 任务的工作目录位置在主任务的工作目录的子目录。deepsearch 任务工作目录**禁止**设置为主任务目录本身。

    返回:
        worker执行的结果。
    """
    start_time = datetime.now()
    task_manager = get_task_manager()
    current_task_manager.set(task_manager)
    current_work_dir.set(work_dir)

    goal = f"""
**禁止**执行 get_task1_goal，get_task2_goal。
第一个子任务的 tool 必须有 get_task1_goal，第二个子任务的 tool 必须有 get_task2_goal。

使用 create_task 启动第一个子任务，下面是 goal 原文，请将```内字符串原样传入，不要修改：

```
用户查询：{query}

首先调用get_task1_goal获取任务安排。
等待所有子任务全部完成。
```

使用 create_task 第一个子任务结束后，启动第二个子任务，第二个子任务需要 excute_command 工具，下面是 goal 原文，请将```内字符串原样传入，不要修改：

```
用户查询：{query}

使用get_task2_goal获取任务安排。
```

务必先执行第一个子任务，等第一个子任务完成后，再执行第二个子任务。
等待两个子任务都完成后，才调用 task_complete 结束任务。
"""

    worker_instance = BrokerWorker(goal, tools, work_dir, True, broker, mcp_manager, task_manager, kgm)
    result = await worker_instance.run()
    end_time = datetime.now()
    print(f"\n任务开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"任务结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"总用时: {end_time - start_time}")
    return result