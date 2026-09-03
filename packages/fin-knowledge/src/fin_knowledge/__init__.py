"""fin-knowledge: 文档知识库（RAG）——数据层 2.0 批次一。"""

from .ingest import ingest_document
from .query import knowledge_stats, search_knowledge

__all__ = ["ingest_document", "search_knowledge", "knowledge_stats"]
