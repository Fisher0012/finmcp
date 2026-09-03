# fin-knowledge

文档知识库（RAG）——数据层 2.0 批次一。

- 存储: SQLite（env `FIN_KNOWLEDGE_DB` 必须显式设置），chunks.emb 为 float32 BLOB
- Embedding: 百炼 text-embedding-v4（env `DASHSCOPE_API_KEY`），1024 维
- 检索: numpy 余弦，支持 doc_type / stock_code 过滤，结果带文档锚（标题/来源/章节）
- 采集器: `collectors.annual_report.ingest_annual_report(stock_code)` 巨潮年报 PDF 全文入库

```python
from fin_knowledge import ingest_document, search_knowledge, knowledge_stats
```

测试: `PYTHONPATH=src python3 -m pytest tests/ -q`
