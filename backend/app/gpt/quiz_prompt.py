"""自测题提示词（P2，通用无学科）。

沿用笔记管线的三条底线：忠实笔记内容不编造、时间戳来自笔记、严格 JSON 输出。
题型只有四种：single（单选）/ judge（判断）/ fill（填空）/ calc（计算与简答）。
"""

QUIZ_SYSTEM_PROMPT = (
    "你是 BiliNote 的出题助教，负责基于视频笔记出自测题。\n"
    "1. 忠实笔记：题目只能考笔记中真实存在的内容，禁止编造知识点、数据与答案；\n"
    "2. 时间戳：time_stamp 必须取笔记小节里真实存在的 HH:MM:SS，找不到就输出空字符串，禁止编造；\n"
    "3. 只输出严格合法的 JSON 对象，禁止输出任何解释、注释或 Markdown 代码块。\n"
    "4. 题干、选项、解析用中文；专有名词保留原文；数学公式用 LaTeX（行内 $...$）。"
)


def quiz_prompt(note_json: str, per_tier: int = 3):
    user = (
        "以下是一份视频笔记的 JSON：\n" + note_json + "\n\n"
        "请基于笔记内容生成阶梯式自测题，只输出 JSON：\n"
        '{"questions":[{"difficulty":"basic","type":"fill","stem":"题目中用 ____ 标记空位",'
        '"options":[],"answer":"第一空答案 / 第一空等价说法 | 第二空答案",'
        '"explanation":"解题思路与常见错误","knowledge_point":"对应知识点","time_stamp":"HH:MM:SS"}]}\n'
        "要求：\n"
        "1. difficulty 只能取 basic / medium / advanced，三档各 " + str(per_tier) + " 道，必须覆盖全部三档；\n"
        "2. type 只能取 single（单选）/ judge（判断）/ fill（填空）/ calc（计算与简答）；\n"
        "   基础档以 judge/fill/single 为主，中档以 single/fill/calc 为主，拔高以 calc/fill 为主；\n"
        "3. 单选题 options 给 4 个不带 A./B./C./D. 前缀的纯选项文本，answer 只输出正确选项字母（A/B/C/D）；\n"
        "   判断题 options 输出 []，answer 只能输出「正确」或「错误」；\n"
        "4. 填空题：题干 stem 中每个空位用连续 4 个下划线 ____ 标记（每题 1-3 个空，空位落在关键术语、"
        "公式结果或结论上）；answer 按空位顺序给出，同一空位的多个等价答案用「 / 」分隔（如「牛顿 / Newton」），"
        "不同空位用「 | 」分隔；公式空直接给 LaTeX；options 输出 []；\n"
        "5. calc 题 answer 给出最终结果或标准答案要点，options 输出 []；\n"
        "6. 每题 time_stamp 取笔记中真实存在的小节时间（HH:MM:SS），找不到输出空字符串；\n"
        "7. explanation 说明解题思路并指出常见错误；knowledge_point 给对应知识点短语。"
    )
    return [
        {"role": "system", "content": QUIZ_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def quiz_judge_prompt(stem: str, qtype: str, options, reference_answer: str,
                      user_answer: str, knowledge_point: str = ""):
    user = (
        "请批改一道自测题并讲解，只输出 JSON：\n"
        '{"correct":true,"feedback":"判断理由 + 解题思路讲解：对在哪里/错在哪里、如何得到正确答案、易错点提醒"}\n\n'
        f"题目：{stem}\n"
        f"题型：{qtype}\n"
    )
    if options:
        user += "选项：" + "；".join(str(o) for o in options) + "\n"
    user += (
        f"参考答案：{reference_answer}\n"
        f"学生答案：{user_answer}\n"
        f"知识点：{knowledge_point or ''}"
    )
    return [
        {"role": "system", "content": QUIZ_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def variant_prompt(note_json: str, question_json: str):
    user = (
        "以下是视频笔记（JSON）与一道已做过的题目（JSON）：\n"
        f"笔记：{note_json}\n题目：{question_json}\n\n"
        "请出一道**变式题**：考同一个知识点，但换情境、换问法或换数据，不要与原题重复，只输出 JSON：\n"
        '{"question":{"difficulty":"basic","type":"single","stem":"...","options":["...","...","...","..."],'
        '"answer":"A","explanation":"...","knowledge_point":"...","time_stamp":"HH:MM:SS"}}\n'
        "题型与答案格式规则与出题时一致：单选 answer 为字母；判断 answer 为「正确/错误」；"
        "填空用 ____ 标空、answer 用「 / 」分隔等价答案、「 | 」分隔多空；calc 给结果。"
        "time_stamp 取笔记中真实存在的小节时间，找不到输出空字符串。"
    )
    return [
        {"role": "system", "content": QUIZ_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]
