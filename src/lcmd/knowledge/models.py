from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True, slots=True)
class PlatformInfo:
    """知识库中可用的平台信息。"""

    name: str
    languages: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ToolInfo:
    """知识库中可用的工具信息。"""

    name: str
    languages: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class KnowledgeCatalog:
    """知识库目录发现结果。"""

    root: Path
    version: str
    platforms: tuple[PlatformInfo, ...]
    tools: tuple[ToolInfo, ...]


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    """经过解析和验证的知识文档。"""

    id: str
    category: Literal["platforms", "tools"]
    platform: str | None
    tool: str | None
    language: str
    summary: str
    body: str

    def __post_init__(self) -> None:
        """确保文档只能属于平台命令或第三方工具中的一种。"""
        if (self.platform is None) == (self.tool is None):
            raise ValueError("KnowledgeDocument 必须且只能指定 platform 或 tool 其中之一。")

        if self.category == "platforms" and self.platform is None:
            raise ValueError("platforms 文档必须指定 platform。")

        if self.category == "tools" and self.tool is None:
            raise ValueError("tools 文档必须指定 tool。")


@dataclass(frozen=True, slots=True)
class KnowledgeBase:
    """当前选择的平台和语言对应的有效知识文档。"""

    platform: str
    language: str
    documents: tuple[KnowledgeDocument, ...]


@dataclass(frozen=True, slots=True)
class QueryResult:
    """知识查询结果，允许文档和下级子命令同时存在。"""

    documents: tuple[KnowledgeDocument, ...]
    children: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SearchResult:
    """搜索结果及其相关度分数。"""

    document: KnowledgeDocument
    score: float
