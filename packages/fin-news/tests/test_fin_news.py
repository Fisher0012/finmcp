"""fin-news 包单元测试（SPEC F4）: db/查询/staleness/env 契约。全部临时库, 零网络。"""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


def _tmp_db():
    fd, name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(name)  # 让包自己建
    return name


class EnvContractTests(unittest.TestCase):
    def test_missing_env_raises_explicit(self):
        from fin_news import db

        env = {k: v for k, v in os.environ.items() if k != "FIN_NEWS_DB"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                db.db_path()
            self.assertIn("FIN_NEWS_DB", str(ctx.exception))


class DbAndQueryTests(unittest.TestCase):
    def setUp(self):
        self.path = _tmp_db()
        self._patch = patch.dict(os.environ, {"FIN_NEWS_DB": self.path})
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        Path(self.path).unlink(missing_ok=True)

    def _seed(self, n=3, source="新浪财经", title_prefix="宁德时代动态"):
        from fin_news.db import save

        return save(
            [
                {
                    "source": source,
                    "title": f"{title_prefix}{i}",
                    "content": f"正文{i}",
                    "url": f"http://x/{source}/{title_prefix}/{i}",
                    "published_at": "",
                }
                for i in range(n)
            ]
        )

    def test_save_dedup_by_id(self):
        from fin_news.db import save

        item = {"source": "新浪财经", "title": "同一条", "url": "http://x/1"}
        self.assertEqual(1, save([item]))
        self.assertEqual(0, save([item]))  # 重复入库被 IGNORE

    def test_get_recent_and_diverse(self):
        from fin_news import count, get_recent, get_recent_diverse

        self._seed(3, "新浪财经")
        self._seed(3, "巨潮资讯", "公司：公告")
        self.assertEqual(6, count())
        self.assertEqual(6, len(get_recent(limit=50, hours=1)))
        diverse = get_recent_diverse(per_source=2, hours=1)
        self.assertEqual(4, len(diverse))  # 每源限 2
        self.assertEqual({"新浪财经", "巨潮资讯"}, {r["source"] for r in diverse})

    def test_search_news_filters(self):
        from fin_news import search_news

        self._seed(2, "新浪财经", "宁德时代快讯")
        self._seed(2, "同花顺", "白酒行情")
        r = search_news("宁德时代", days=1)
        self.assertTrue(r["ok"])
        self.assertEqual(2, len(r["data"]["items"]))
        r = search_news("不存在的词xyz", days=1)
        self.assertTrue(r["ok"])
        self.assertEqual([], r["data"]["items"])
        self.assertEqual("confirmed_absent", r["meta"]["empty_reason"])

    def test_search_announcements_cninfo_only(self):
        from fin_news import search_announcements

        self._seed(2, "新浪财经", "宁德时代快讯")
        self._seed(2, "巨潮资讯", "宁德时代：公告")
        r = search_announcements("宁德时代", days=1)
        self.assertTrue(r["ok"])
        self.assertEqual(2, len(r["data"]["items"]))
        self.assertTrue(all(i["source"] == "巨潮资讯" for i in r["data"]["items"]))

    def test_staleness_warning_after_60min(self):
        from fin_news import search_news
        from fin_news.db import connect

        self._seed(1)
        # 把 fetched_at 拨回 90 分钟前
        conn = connect()
        conn.execute("UPDATE news SET fetched_at = ?", (int(time.time()) - 90 * 60,))
        conn.commit()
        conn.close()
        r = search_news("", days=1)
        warn = r["meta"].get("staleness_warning")
        self.assertIsNotNone(warn, "停采 90 分钟必须携带 staleness_warning")
        self.assertGreaterEqual(warn["minutes_ago"], 89)

    def test_no_staleness_when_fresh(self):
        from fin_news import search_news

        self._seed(1)
        r = search_news("", days=1)
        self.assertNotIn("staleness_warning", r["meta"])

    def test_empty_db_search_carries_staleness(self):
        from fin_news import search_news

        r = search_news("x", days=1)
        self.assertTrue(r["ok"])
        self.assertIsNotNone(r["meta"].get("staleness_warning"))
        self.assertIsNone(r["meta"]["staleness_warning"]["last_collected_at"])


if __name__ == "__main__":
    unittest.main()
