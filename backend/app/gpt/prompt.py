"""结构化笔记提示词（pipeline: structured-v1）。

设计依据（AI 视频笔记提示词调研，2026-10）：
 1. 忠实转写红线：只写转写里出现的内容，禁止编造事实/数据/引用/时间戳，宁可省略不可臆测
 2. 答案先行：先给核心结论，再展开；不写机械的「论点/论据/意义」套格
 3. 时间戳第一公民：每个章节/小节绑转写中真实存在的 HH:MM:SS，禁止编造
 4. 长内容分段（map）→ 合并去重 → 全局重组（reduce），消重复、去流水账
 5. 输出严格 JSON，由调用方做解析校验与失败重试
 6. 语言跟随转写；专有名词、术语、品牌名、人名保留原文
 7. 去口语化、保信息密度：术语/公式/结论/代码完整保留，铺垫闲话删除；
    严禁把口播改写成零碎短句要点，宁可少而精不要灌水
 8. 标签 3-8 个主题词，合并同义，排除「视频/总结/字幕」等工作流词
"""

# ---------- 通用红线（map / merge / finalize 共用） ----------

SYSTEM_PROMPT = (
    "你是 BiliNote 的视频笔记助手，负责把带时间戳的视频转写内容整理成结构化笔记。\n"
    "1. 忠实转写：只记录转写中出现的内容，禁止编造事实、数据、引用与时间戳；"
    "转写不清或缺失的部分宁可省略，不要臆测补全。\n"
    "2. 语言：笔记正文用中文撰写；专有名词、术语、品牌名、人名保留原文。\n"
    "3. 时间戳：每个章节、小节必须携带转写中真实存在的开始时间（HH:MM:SS，如 00:12:34），禁止编造。\n"
    "4. 只输出严格合法的 JSON 对象，禁止输出任何解释性文字、注释或 Markdown 代码块。\n"
    "5. 数学公式用 LaTeX 表示（行内 $...$，独立公式直接给源码）；代码保留缩进与准确性。"
)

# ---------- 结构约束（map / merge / finalize 共用） ----------

SECTION_TYPE_GUIDE = (
    "小节 type 按内容自行选择，只可取：\n"
    "- overview：一段话要点概述；\n"
    "- detail：概念、原理、观点的详细讲解；\n"
    "- steps：流程、步骤、操作、方法（blocks 里用 steps 块给完整过程）；\n"
    "- example：案例、演示、示例（给情境与完整解答/结果）；\n"
    "- comparison：对比、取舍、异同（blocks 里用 table 块）；\n"
    "- code：代码讲解（blocks 里用 code 块）；\n"
    "- formula：公式推导或运算（blocks 里用 formula/steps 块）；\n"
    "- conclusion：结论、建议、注意事项。"
)

BLOCK_GUIDE = (
    "blocks 中每个元素 type 只可取：\n"
    "- text：成段讲解（content 为段落文字，可含行内公式 $...$ 与 **加粗**，不要只写一句话）；\n"
    "- formula：独立成行的公式（content 为 LaTeX 源码，不要包裹 $$）；\n"
    "- steps：分步过程（items 为有序步骤数组，流程/推导/操作必须用它）；\n"
    "- list：并列要点（ordered 为 true 有序/false 无序，items 为数组）；\n"
    "- code：代码（language 给语言名，content 为完整代码，保留缩进）；\n"
    "- table：对比或结构化信息（headers 为表头数组，rows 为二维数组）；\n"
    "- quote：结论、金句、原话引用或提醒（content 为一句话）；\n"
    "- screenshot：截图占位（content 为该画面说明，time_stamp 为 HH:MM:SS，仅在开启截图时使用）。"
)

QUALITY_GUIDE = (
    "质量红线：\n"
    "1. 必须是成体系的讲解：概念讲清楚、步骤给完整过程、案例给情境和结果；"
    "严禁把口播内容改写成一堆零碎短句要点；\n"
    "2. 术语、公式、数据、结论、代码必须完整保留，口语化铺垫与寒暄可以删；\n"
    "3. 内容按内在逻辑组织（是什么→为什么→怎么做→注意什么），不要写成时间流水账；\n"
    "4. 宁可少而精，不要灌水；转写里没有的内容一个字也不要加。"
)

# ---------- map：分段生成小节 ----------
# 注意：BASE_PROMPT 保持「单条 user 消息模板」形态（无 system 角色），
# 因为带截图时要走多模态 content 数组，图片与正文拼在同一 user 消息里。

BASE_PROMPT = '''
{system}

视频标题：{video_title}
视频标签：{tags}

下面是本视频转写的其中一段（格式：HH:MM:SS - 内容，时间戳真实存在）：

---
{segment_text}
---

请把这一段整理成「小节笔记」，只输出 JSON：
{{"sections":[{{"type":"detail","heading":"小节标题","time_stamp":"HH:MM:SS","important":false,
"blocks":[{{"type":"text","content":"成段讲解"}}]}}]}}

小节要求：
1. {section_type_guide}
2. 每个小节必须携带该小节内容开始处转写里真实存在的时间戳（HH:MM:SS），禁止编造；
3. important 只给真正的核心结论/关键操作，这一段最多 1 个；
4. 本段内容少时小节数从少，最多 6 个小节。
内容块要求：
{block_guide}

{quality_guide}{style_guide}{format_guide}{extras}
'''

# ---------- reduce：多段小节合并去重 ----------

MERGE_PROMPT = '''你将收到同一视频分段整理后的「小节笔记」JSON 片段列表，
片段之间可能存在重复、口语化残留和顺序错位。
请把这些片段合并成一份连贯的「小节笔记」，只输出 JSON：
{"sections":[{"type":"detail","heading":"小节标题","time_stamp":"HH:MM:SS","important":false,
"blocks":[{"type":"text","content":"成段讲解"}]}]}

合并规则：
1. 同一内容只保留一次，措辞冲突时保留信息更完整的版本，不要发明新内容；
2. 按内容逻辑重排小节（是什么→为什么→怎么做→注意什么），不要按时间流水账；
3. 完整保留每个小节真实的 time_stamp（HH:MM:SS），禁止编造；
4. 小节 type 与内容块规则：
''' + SECTION_TYPE_GUIDE + "\n" + BLOCK_GUIDE + "\n" + QUALITY_GUIDE + "\n\n小节笔记 JSON 片段：\n"

# ---------- finalize：小节汇总成整篇笔记 ----------

FINALIZE_PROMPT = '''请把下面合并后的「小节笔记」整理成整篇视频笔记，只输出 JSON：
{"title":"笔记标题","summary":"3到6句核心结论概述，答案先行",
"chapters":[{"title":"章节标题","time_stamp":"HH:MM:SS","intro":"本章一句话导读",
"sections":[{"type":"detail","heading":"小节标题","time_stamp":"HH:MM:SS","important":false,
"blocks":[{"type":"text","content":"..."}]}],
"summary":"本章小结","key_points":["本章必须记住的结论"]}],
"key_takeaways":["全片核心结论，5到12条短句"],
"tags":["3到8个主题标签"]}

整理要求：
1. 按内容逻辑把小节归并为 3-8 个章节，章节顺序就是阅读顺序，每章 2-6 个小节；
2. 每章含 intro（可选一句）、sections、章末 summary 与 key_points（2-5 条）；
3. 时间戳沿用小节真实 time_stamp，章节 time_stamp 取其第一个小节的时间，禁止编造；
4. summary 先给整篇视频的核心结论（答案先行），再概述覆盖范围；
5. key_takeaways 汇总全片最值得记住的结论/方法/提醒；
6. tags 只给转写中真实出现的主题词，合并同义词，不要「视频」「总结」「笔记」这类词；
7. 小节 type 与内容块规则：
''' + SECTION_TYPE_GUIDE + "\n" + BLOCK_GUIDE + "\n" + QUALITY_GUIDE + "\n\n合并后的小节笔记：\n"

# ---------- 旧常量占位（兼容历史导入；structured-v1 起不再参与拼装） ----------

AI_SUM = ""
SCREENSHOT = ""
LINK = ""
