"""gpt 层通用小工具：Markdown 转义还原。"""
import codecs


def fix_markdown(markdown: str) -> str:
    return codecs.decode(markdown, 'unicode_escape')
