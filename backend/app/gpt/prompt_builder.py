"""map 阶段提示词拼装（pipeline: markdown-v2）。

对外契约保持不变：`generate_base_prompt(title, segment_text, tags, _format, style, extras)`
返回单条 user 消息文本（带截图时由 UniversalGPT 拼进多模态 content 数组）。
输出为 Markdown 正文（含 `*Content-[HH:MM:SS]` / `*Screenshot-[HH:MM:SS]` 标记），
style / format / extras 三个用户开关照旧生效：
  - style   → 表达与详略偏好（不预设学科/教学法）
  - format  → toc / link / screenshot / summary 四个能力开关
  - extras  → 用户自由补充要求
"""
from app.gpt.prompt import (
    BASE_PROMPT,
    QUALITY_GUIDE,
    SYSTEM_PROMPT,
)

note_formats = [
    {'label': '目录', 'value': 'toc'},
    {'label': '原片跳转', 'value': 'link'},
    {'label': '原片截图', 'value': 'screenshot'},
    {'label': 'AI总结', 'value': 'summary'}
]

note_styles = [
    {'label': '精简', 'value': 'minimal'},
    {'label': '详细', 'value': 'detailed'},
    {'label': '学术', 'value': 'academic'},
    {'label': '教程', 'value': 'tutorial'},
    {'label': '小红书', 'value': 'xiaohongshu'},
    {'label': '生活向', 'value': 'life_journal'},
    {'label': '任务导向', 'value': 'task_oriented'},
    {'label': '商业风格', 'value': 'business'},
    {'label': '会议纪要', 'value': 'meeting_minutes'}
]


def generate_base_prompt(title, segment_text, tags, _format=None, style=None, extras=None):
    """拼装 map（分段）阶段提示词。"""
    prompt = BASE_PROMPT.format(
        system=SYSTEM_PROMPT,
        video_title=title or "未命名视频",
        tags=tags if tags else "无",
        segment_text=segment_text,
        quality_guide=QUALITY_GUIDE,
        style_guide=get_style_format(style),
        format_guide="\n".join(filter(None, (get_format_function(f) for f in (_format or [])))),
        extras=(f"\n用户额外要求（必须满足）：\n{extras}" if extras else ""),
    )
    return prompt


def get_format_function(format_type):
    format_map = {
        'toc': get_toc_format,
        'link': get_link_format,
        'screenshot': get_screenshot_format,
        'summary': get_summary_format,
    }
    return format_map.get(format_type, lambda: '')()


def get_style_format(style):
    """风格 → 表达与详略偏好（内容结构由 schema 管，风格只管怎么说）。"""
    style_map = {
        'minimal': '风格偏好：精简。只保留核心结论、关键数据与必要步骤，能合并的小节就合并，不展开铺陈。',
        'detailed': '风格偏好：详细。完整保留讲解脉络与细节，小节充分展开，示例与步骤一个都不要省。',
        'academic': '风格偏好：学术。用词严谨，保留定义、推导与论证链条，结论注明适用条件与局限。',
        'tutorial': '风格偏好：教程。突出操作步骤、命令、参数、预期结果与坑点，流程一律用有序列表、代码用代码块。',
        'xiaohongshu': (
            '风格偏好：小红书。表达口语化有网感，多用短句与 emoji，小节标题吸引眼球但不标题党，'
            '划重点、给结论、说人话，适合「好用到哭」「小白必看」「划重点」这类种草语气。'
        ),
        'life_journal': '风格偏好：生活向。情感化表达，记录体验、感受与故事线，保留人物与情节细节。',
        'task_oriented': '风格偏好：任务导向。强调目标、行动项与待办清单，结论落成可执行条目（用列表）。',
        'business': '风格偏好：商业风格。结论先行，突出数据、对比、风险与建议，表达正式精准。',
        'meeting_minutes': (
            '风格偏好：会议纪要。按议题组织：讨论要点、各方观点、结论决议、行动项，'
            '表达客观简练，不加戏。'
        ),
    }
    return style_map.get(style, '')


def get_toc_format():
    # 目录由渲染端按章节树自动生成，无需占用模型输出
    return ''


def get_link_format():
    return (
        '原片跳转已开启：章节与小节标题后的 `*Content-[HH:MM:SS]` 标记会渲染成原片跳转链接，'
        '请务必给每个章节、小节标真实的开始时间，没有时间标记的内容无法跳转原片。'
    )


def get_screenshot_format():
    return (
        '原片截图已开启：对涉及画面演示、UI 操作、图表、板书、代码运行结果的内容，'
        '在对应小节末尾另起一行写 `*Screenshot-[HH:MM:SS]`（该画面出现的时刻），'
        '下一行用 *斜体* 一句话说明看什么。只在画面确实有助于理解时插入，每 3 分钟最多 1 个。'
    )


def get_summary_format():
    return (
        'AI 总结已开启：开头的引用概述（> 开头）与文末「## 核心要点」必须认真写足——'
        '概述先给整段核心结论（答案先行），核心要点收全最值得记住的结论与方法。'
    )
