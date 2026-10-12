import re
from typing import List, Tuple


def extract_screenshot_timestamps(markdown: str) -> List[Tuple[str, int]]:
    # 支持 mm:ss（含 3 位分钟）与 hh:mm:ss 两种写法
    pattern = r"(\*?Screenshot-(?:\[(?:(\d{1,3}):)?(\d{1,3}):(\d{2})\]|(?:(\d{1,3}):)?(\d{1,3}):(\d{2})))"
    results: List[Tuple[str, int]] = []
    for match in re.finditer(pattern, markdown):
        hh = match.group(2) or match.group(5)
        mm = match.group(3) or match.group(6)
        ss = match.group(4) or match.group(7)
        total_seconds = (int(hh) if hh else 0) * 3600 + int(mm) * 60 + int(ss)
        results.append((match.group(1), total_seconds))
    return results
