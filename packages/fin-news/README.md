# fin-news

财经新闻自采集与检索包（SPEC F4, 自 workbench `lib/fin_news` 迁入）。

- **采集**: 5 源（新浪 7x24 / 华尔街见闻 / 东财快讯 / 巨潮公告 / 同花顺要闻），30 分钟循环。
  独立进程运行: `FIN_NEWS_DB=/path/to/fin_news.db python -m fin_news`（PM2 常驻）。
- **查询**: `get_recent` / `get_recent_diverse` / `count`（兼容 API, 裸返回）；
  `search_news` / `search_announcements`（三态封套 + `staleness_warning`）。
- **数据库**: 路径只认 env `FIN_NEWS_DB`，未设置显式报错（迁代码不迁数据）。
