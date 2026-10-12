"""复习资料提示词（P3，通用无学科）。

详版三步：① 排大纲（把各篇笔记按知识逻辑而非时间顺序重排）→ ② 逐章生成
（每章单独一次调用，长合集也写得足）→ ③ 补全局信息（学习目标/易混辨析/术语索引/速记卡）。
简版一次成型，快而便宜，适合篇数少的合集。
"""

REVIEW_SYSTEM_PROMPT = (
    "你是 BiliNote 的复习资料编辑，负责把多篇视频笔记蒸馏成一份可打印的复习资料。\n"
    "1. 忠实笔记：只整理笔记中真实存在的内容，禁止编造知识点、数据与答案；\n"
    "2. 按知识逻辑组织（是什么→为什么→怎么做→注意什么），不要按视频顺序流水账；\n"
    "3. 只输出严格合法的 JSON 对象，禁止输出任何解释、注释或 Markdown 代码块；\n"
    "4. 用中文撰写；专有名词保留原文；数学公式用 LaTeX（行内 $...$）。"
)


def review_outline_prompt(course_title: str, digest_json: str):
    user = (
        f"合集《{course_title}》包含多篇视频笔记，下面是各篇的蒸馏摘要（JSON）：\n{digest_json}\n\n"
        "请按知识逻辑排出复习资料的章节大纲（不是按视频顺序），只输出 JSON：\n"
        '{"chapters":[{"title":"章节标题","goal":"本章学习目标一句话","episode_refs":[0,2]}]}\n'
        "要求：\n"
        "1. 章节数 3-12 个，章节顺序就是复习顺序；\n"
        "2. episode_refs 给出本章内容来自哪几篇笔记（摘要里的 index），允许一篇笔记的内容拆进多章；\n"
        "3. 合并跨篇重复的知识点，只讲一次；\n"
        "4. 章节标题要具体（含关键概念），不要「第一章/概述」这类空标题。"
    )
    return [
        {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def review_chapter_prompt(course_title: str, plan: dict, episodes_digest: str,
                          chapter_no: int, total: int):
    user = (
        f"合集《{course_title}》复习资料共 {total} 章，现在写第 {chapter_no} 章。\n"
        f"本章大纲：{plan}\n"
        f"相关笔记蒸馏摘要（JSON）：{episodes_digest}\n\n"
        "请写出本章完整内容，只输出 JSON：\n"
        '{"chapter":{"title":"章节标题","intro":"本章导读一句话",'
        '"sections":[{"heading":"小节标题","content":"成段讲解，可含 $公式$ 与 **加粗**"}],'
        '"exercises":[{"type":"judge","stem":"题干，填空用 ____ 标空","options":[],'
        '"answer":"正确 或 单选字母 或 空1等价 / 空1等价 | 空2","explanation":"解析"}]}}\n'
        "要求：\n"
        "1. sections 2-6 个小节，每节是成段讲解而非要点罗列，把概念、推导、步骤、案例写完整；\n"
        "2. exercises 给 2-5 道章节自测题：type 取 single/judge/fill/calc；"
        "单选 options 给 4 个纯选项文本、answer 为字母；判断 answer 为「正确/错误」；"
        "填空用 ____ 标空、answer 用「 / 」分隔等价答案、「 | 」分隔多空；calc 给最终结果；\n"
        "3. 只写本章范围内的内容，不要提前剧透后面的章节；\n"
        "4. 宁可少而精，不要灌水；笔记里没有的内容一个字也不要加。"
    )
    return [
        {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def review_wrapup_prompt(course_title: str, chapters_digest: str):
    user = (
        f"合集《{course_title}》复习资料各章已写完，下面是章节摘要（JSON）：\n{chapters_digest}\n\n"
        "请补齐全局信息，只输出 JSON：\n"
        '{"summary":"全篇核心结论概述（答案先行，3-6句）","goals":["学习目标 3-6 条"],'
        '"confusions":[{"pair":"易混概念 A vs B","difference":"一句话辨析"}],'
        '"glossary":[{"term":"术语","meaning":"一句话释义"}],'
        '"cards":[{"front":"速记卡正面（问题/概念）","back":"背面（答案/要点）"}]}\n'
        "要求：\n"
        "1. confusions 收 3-8 组最容易混的概念对，辨析要一针见血；\n"
        "2. glossary 收 8-20 个术语，按重要性排序；\n"
        "3. cards 做 8-15 张速记卡，正面提问、背面一句话答案；\n"
        "4. 全部内容必须来自章节摘要，禁止编造。"
    )
    return [
        {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def review_brief_prompt(course_title: str, digest_json: str):
    user = (
        f"合集《{course_title}》包含多篇视频笔记，下面是蒸馏摘要（JSON）：\n{digest_json}\n\n"
        "请一次性生成整份复习资料（简版），只输出 JSON：\n"
        '{"title":"复习资料标题","summary":"核心结论概述（答案先行）","goals":["学习目标"],'
        '"chapters":[{"title":"章节标题","intro":"导读",'
        '"sections":[{"heading":"小节标题","content":"成段讲解"}],'
        '"exercises":[{"type":"single","stem":"...","options":["...","...","...","..."],"answer":"A","explanation":"..."}]}],'
        '"confusions":[{"pair":"A vs B","difference":"..."}],'
        '"glossary":[{"term":"...","meaning":"..."}],"cards":[{"front":"...","back":"..."}]}\n'
        "要求：按知识逻辑组织 3-8 章；每章 2-5 个小节 + 2-5 道自测题（type 取 single/judge/fill/calc，"
        "填空用 ____ 标空、answer 用「 / 」分隔等价答案、「 | 」分隔多空）；"
        "confusions 3-8 组、glossary 8-20 词、cards 8-15 张；全部内容来自摘要，禁止编造。"
    )
    return [
        {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]
