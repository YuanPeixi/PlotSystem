from __future__ import annotations

import tempfile
import unittest

from plot_system.app import create_project_service


class PlotSystemTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.service = create_project_service(self.temp_dir.name)
        self.seed_text = (
            "旧王城的地下遗迹重新开启，三名互不信任的探索者为了不同目的进入其中。"
            "遗迹中残留着会改变环境的机关与未完成的誓约，任何选择都会带来新的分支结局。"
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_create_project_generates_graph_and_agents(self) -> None:
        project = self.service.create_project("测试项目", self.seed_text)
        self.assertEqual(project["title"], "测试项目")
        self.assertGreaterEqual(len(project["knowledge_graph"]["nodes"]), 1)
        self.assertEqual(len(project["characters"]), 3)
        self.assertEqual(project["snapshots"][0]["label"], "初始快照")

    def test_simulate_summary_and_branch_flow(self) -> None:
        project = self.service.create_project("测试项目", self.seed_text)
        scene = self.service.simulate(project["id"], 2)
        self.assertEqual(len(scene["rounds"]), 2)

        refreshed = self.service.get_project(project["id"])
        self.assertIsNotNone(refreshed)
        self.assertEqual(len(refreshed["scenes"]), 1)
        self.assertGreaterEqual(len(refreshed["snapshots"]), 3)

        export = self.service.summarize(project["id"], "剧本")
        self.assertIn("作品标题", export["content"])

        latest_snapshot = refreshed["snapshots"][-1]
        branch = self.service.branch(project["id"], latest_snapshot["id"], "支线")
        self.assertEqual(branch["parent_project_id"], project["id"])
        self.assertTrue(branch["title"].endswith("支线"))


if __name__ == "__main__":
    unittest.main()
