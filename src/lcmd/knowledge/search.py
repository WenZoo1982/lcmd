import re
from pathlib import PurePosixPath

from lcmd.knowledge.models import KnowledgeBase, KnowledgeDocument, SearchResult

_CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")
_ENGLISH_PATTERN = re.compile(r"[a-z0-9]+")
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def _extract_usage(body: str) -> str:
    """提取 Markdown 正文中的用途章节。"""
    lines = body.splitlines()
    usage_lines = []
    collecting = False

    for line in lines:
        match = _HEADING_PATTERN.match(line.strip())

        if match:
            heading = match.group(2).strip()

            if collecting:
                break

            if heading == "用途":
                collecting = True
                continue

        if collecting:
            usage_lines.append(line)

    return "\n".join(usage_lines)


def _query_units(keyword: str) -> tuple[str, ...]:
    """将查询内容转换为中文片段和英文单词。"""
    units = []

    for segment in keyword.casefold().split():
        position = 0

        for match in _CJK_PATTERN.finditer(segment):
            if match.start() > position:
                units.extend(_ENGLISH_PATTERN.findall(segment[position : match.start()]))

            chinese = match.group()

            if len(chinese) == 1:
                units.append(chinese)
            else:
                units.extend(chinese[index : index + 2] for index in range(len(chinese) - 1))
                units.extend(chinese)

            position = match.end()

        if position < len(segment):
            units.extend(_ENGLISH_PATTERN.findall(segment[position:]))

    return tuple(dict.fromkeys(units))


def _contains_unit(text: str, unit: str) -> bool:
    """判断文本是否包含查询片段，英文采用单词边界。"""
    if _CJK_PATTERN.fullmatch(unit):
        return unit in text

    pattern = rf"(?<![a-z0-9]){re.escape(unit)}(?![a-z0-9])"
    return re.search(pattern, text.casefold()) is not None


def _contains_phrase(text: str, keyword: str) -> bool:
    """判断完整关键词是否命中，英文遵守单词边界。"""
    keyword = keyword.strip().casefold()
    text = text.casefold()

    if not keyword:
        return False

    if _CJK_PATTERN.search(keyword):
        return keyword in text

    pattern = rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])"
    return re.search(pattern, text) is not None


def _document_names(document: KnowledgeDocument) -> str:
    """提取文档名称、工具名称和完整子命令路径。"""
    parts = PurePosixPath(document.id).parts

    if document.category == "platforms":
        return PurePosixPath(parts[-1]).stem

    if document.category == "tools":
        tool = document.tool or ""
        relative_parts = parts[3:]

        command_parts = list(relative_parts)

        if command_parts:
            command_parts[-1] = PurePosixPath(command_parts[-1]).stem

        return " ".join((tool, *command_parts))

    return ""


def _score_field(
    text: str,
    units: tuple[str, ...],
    weight: float,
) -> tuple[float, int]:
    """计算字段匹配得分和命中关键词数量。"""
    if not text:
        return 0.0, 0

    matched = sum(_contains_unit(text, unit) for unit in units)

    if not matched:
        return 0.0, 0

    coverage = matched / len(units)
    return weight * (1.0 + coverage), matched


def _score_document(
    document: KnowledgeDocument,
    units: tuple[str, ...],
    keyword: str,
    full: bool,
) -> float:
    """计算单篇文档的综合搜索得分。"""
    names = _document_names(document)
    summary = document.summary
    usage = _extract_usage(document.body)

    fields = (
        (names, 10.0),
        (summary, 6.0),
        (usage, 3.0),
    )

    score = 0.0
    matched_units = set()

    for text, weight in fields:
        field_score, _ = _score_field(text, units, weight)
        score += field_score

        matched_units.update(unit for unit in units if _contains_unit(text, unit))

        if text and _contains_phrase(text, keyword):
            score += weight * 0.5

    if full:
        body_score, _ = _score_field(document.body, units, 1.0)
        score += body_score

        matched_units.update(unit for unit in units if _contains_unit(document.body, unit))

        if _contains_phrase(document.body, keyword):
            score += 0.5

    # 多关键词覆盖度奖励，避免只命中一个关键词的文档排在前面。
    score += len(matched_units) / len(units)

    return score


def search_knowledge(
    knowledge: KnowledgeBase,
    keyword: str,
    full: bool = False,
) -> tuple[SearchResult, ...]:
    """搜索当前知识库，返回按相关度排序的结果。"""
    keyword = keyword.strip()

    if not keyword:
        return ()

    units = _query_units(keyword)

    if not units:
        return ()

    results = []

    for document in knowledge.documents:
        score = _score_document(
            document,
            units,
            keyword,
            full,
        )

        if score > 0:
            results.append(
                SearchResult(
                    document=document,
                    score=score,
                )
            )

    results.sort(
        key=lambda item: (-item.score, item.document.id),
    )

    return tuple(results)
