#!/usr/bin/env python3
"""
project-manager.py 单元测试与端到端测试。

使用 Python 标准库 unittest 框架，通过 subprocess 调用 project-manager.py CLI。
每个测试用例在独立的临时项目目录中运行，互不干扰，测试前后自动创建和清理。

覆盖:
  T6 单元测试 (test_01 ~ test_14, test_18)
  T7 端到端测试 (test_15 ~ test_17)

独立运行:
  python3 test_project_manager.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

# 被测脚本绝对路径（与本测试脚本同目录）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_MANAGER = os.path.join(SCRIPT_DIR, "project-manager.py")

# project-manager.py 的错误退出码
ERROR_EXIT_CODE = 2


class ProjectManagerTestCase(unittest.TestCase):
    """project-manager.py 的测试基类，提供临时目录与 CLI 调用辅助方法。"""

    def setUp(self):
        # 每个测试用独立的临时目录作为 PROJECTS_DIR，避免污染真实 /workspace/projects
        self.tmp_dir = tempfile.mkdtemp(prefix="wechat_writer_test_")
        self.env = os.environ.copy()
        self.env["WECHAT_WRITER_PROJECTS_DIR"] = self.tmp_dir

    def tearDown(self):
        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # ---------- 辅助方法 ----------

    def run_cmd(self, *args):
        """调用 project-manager.py，返回 (returncode, stdout, stderr)。"""
        result = subprocess.run(
            [sys.executable, PROJECT_MANAGER, *map(str, args)],
            env=self.env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return result.returncode, result.stdout, result.stderr

    def parse_json(self, stdout):
        """解析命令 stdout 为 JSON。

        兼容两种情况:
        1. 整体多行 indent JSON (list/show/incomplete) —— 直接整体解析。
        2. 单行 JSON 前置可能存在 warning 输出 (init/copy 会做磁盘空间检查)
           —— 取最后一个可解析的 JSON 行。
        """
        stdout = stdout.strip()
        self.assertTrue(stdout, f"命令无输出")
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            pass
        for line in reversed([ln for ln in stdout.splitlines() if ln.strip()]):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        self.fail(f"无法解析 JSON 输出: {stdout!r}")

    def init_project(self, title="测试文章"):
        """辅助: 创建项目，返回 article_id。"""
        rc, out, err = self.run_cmd("init", title)
        self.assertEqual(rc, 0, f"init 失败: stdout={out!r} stderr={err!r}")
        data = self.parse_json(out)
        self.assertEqual(data["action"], "init")
        return data["id"]

    def project_path(self, article_id, *parts):
        """辅助: 拼接项目目录下的路径。"""
        return os.path.join(self.tmp_dir, article_id, *parts)

    def read_article_json(self, article_id):
        """辅助: 直接读取项目的 article.json。"""
        with open(self.project_path(article_id, "article.json"), "r", encoding="utf-8") as f:
            return json.load(f)

    def write_article_json(self, article_id, project):
        """辅助: 直接写入 article.json (用于模拟崩溃/手动修改)。"""
        with open(self.project_path(article_id, "article.json"), "w", encoding="utf-8") as f:
            json.dump(project, f, ensure_ascii=False, indent=2)


# ====================================================================
# T6: 单元测试
# ====================================================================

class TestProjectManagerUnit(ProjectManagerTestCase):

    def test_01_init_project(self):
        """init 命令正常创建项目，验证 article.json 存在且包含正确字段。"""
        rc, out, _ = self.run_cmd("init", "AI行业洞察")
        self.assertEqual(rc, 0)
        data = self.parse_json(out)
        self.assertEqual(data["action"], "init")
        self.assertEqual(data["status"], "planning")
        article_id = data["id"]
        self.assertTrue(article_id.startswith("article-"))

        # article.json 存在
        article_path = self.project_path(article_id, "article.json")
        self.assertTrue(os.path.exists(article_path))
        # images 子目录存在
        self.assertTrue(os.path.isdir(self.project_path(article_id, "images")))

        # 包含正确字段
        project = self.read_article_json(article_id)
        expected_fields = {
            "id", "status", "topic", "research", "outline", "draft",
            "images", "formatted", "review", "publish", "retrospective", "history",
        }
        self.assertTrue(expected_fields.issubset(project.keys()))
        self.assertEqual(project["id"], article_id)
        self.assertEqual(project["status"], "planning")
        self.assertEqual(project["topic"]["title"], "AI行业洞察")
        self.assertEqual(project["history"], [])

    def test_02_list_projects(self):
        """list 命令正常返回项目列表。"""
        id1 = self.init_project("文章一")
        id2 = self.init_project("文章二")
        rc, out, _ = self.run_cmd("list")
        self.assertEqual(rc, 0)
        data = self.parse_json(out)
        self.assertIn("projects", data)
        ids = [p["id"] for p in data["projects"]]
        self.assertIn(id1, ids)
        self.assertIn(id2, ids)
        titles = {p["id"]: p["title"] for p in data["projects"]}
        self.assertEqual(titles[id1], "文章一")
        self.assertEqual(titles[id2], "文章二")

    def test_03_list_with_corrupted_project(self):
        """list 遇到损坏的 article.json 不崩溃，结果包含 errors 数组。"""
        good_id = self.init_project("正常文章")
        bad_id = self.init_project("损坏文章")
        # 手动写一个损坏的 article.json
        with open(self.project_path(bad_id, "article.json"), "w", encoding="utf-8") as f:
            f.write("{这是损坏的 JSON,,,}")
        rc, out, _ = self.run_cmd("list")
        self.assertEqual(rc, 0)  # 不崩溃
        data = self.parse_json(out)
        self.assertIn("projects", data)
        self.assertIn("errors", data)
        # 正常项目仍在列表
        ids = [p["id"] for p in data["projects"]]
        self.assertIn(good_id, ids)
        self.assertNotIn(bad_id, ids)
        # 损坏项目被收集到 errors
        error_ids = [e["id"] for e in data["errors"]]
        self.assertIn(bad_id, error_ids)

    def test_04_list_excludes_archive(self):
        """list 不包含 archive 目录中的项目。"""
        aid = self.init_project("待归档文章")
        self.run_cmd("archive", aid)
        rc, out, _ = self.run_cmd("list")
        self.assertEqual(rc, 0)
        data = self.parse_json(out)
        ids = [p["id"] for p in data["projects"]]
        self.assertNotIn(aid, ids)
        # archive 目录中确实存在该项目
        archived_path = os.path.join(self.tmp_dir, "archive", aid, "article.json")
        self.assertTrue(os.path.exists(archived_path))

    def test_05_load_corrupted_json(self):
        """加载损坏 JSON 时返回错误而非崩溃。"""
        aid = self.init_project("损坏测试")
        with open(self.project_path(aid, "article.json"), "w", encoding="utf-8") as f:
            f.write("not a json {{{")
        # show 命令加载损坏 JSON 应返回错误且非零退出
        rc, out, _ = self.run_cmd("show", aid)
        self.assertEqual(rc, ERROR_EXIT_CODE)
        data = self.parse_json(out)
        self.assertIn("error", data)
        self.assertEqual(data["id"], aid)

    def test_06_update_status(self):
        """status 命令更新项目状态正常工作。"""
        aid = self.init_project("状态测试")
        rc, out, _ = self.run_cmd("status", aid, "researching")
        self.assertEqual(rc, 0)
        data = self.parse_json(out)
        self.assertEqual(data["action"], "update_status")
        self.assertEqual(data["status"], "researching")
        # 验证已写入文件
        project = self.read_article_json(aid)
        self.assertEqual(project["status"], "researching")
        # history 新增一条
        self.assertEqual(len(project["history"]), 1)
        self.assertEqual(project["history"][0]["stage"], "researching")

    def test_07_update_field(self):
        """update 命令更新项目字段正常工作。"""
        aid = self.init_project("字段测试")
        draft_data = {"title": "草稿标题", "content": "这是草稿正文"}
        rc, out, _ = self.run_cmd("update", aid, "draft",
                                  json.dumps(draft_data, ensure_ascii=False))
        self.assertEqual(rc, 0)
        data = self.parse_json(out)
        self.assertEqual(data["action"], "update_field")
        self.assertEqual(data["field"], "draft")
        project = self.read_article_json(aid)
        self.assertEqual(project["draft"], draft_data)

    def test_08_history_limit(self):
        """history 超过 10 条时只保留最近 10 条。"""
        aid = self.init_project("历史测试")
        # 触发 12 次状态更新
        for i in range(12):
            rc, out, _ = self.run_cmd("status", aid, f"stage{i}")
            self.assertEqual(rc, 0, f"第 {i} 次 status 失败: {out}")
        project = self.read_article_json(aid)
        self.assertEqual(len(project["history"]), 10)
        # 保留最近 10 条 (stage2 ~ stage11)
        stages = [h["stage"] for h in project["history"]]
        self.assertEqual(stages[0], "stage2")
        self.assertEqual(stages[-1], "stage11")

    def test_09_backup_on_update(self):
        """更新时自动生成 .bak 文件。"""
        aid = self.init_project("备份测试")
        bak_path = self.project_path(aid, "article.json.bak")
        self.assertFalse(os.path.exists(bak_path))
        self.run_cmd("status", aid, "researching")
        self.assertTrue(os.path.exists(bak_path))
        # .bak 内容是更新前的状态 (planning)
        with open(bak_path, "r", encoding="utf-8") as f:
            bak = json.load(f)
        self.assertEqual(bak["status"], "planning")

    def test_10_delete_requires_confirm(self):
        """delete 命令不带 confirm 时不删除。"""
        aid = self.init_project("删除测试")
        project_dir = os.path.join(self.tmp_dir, aid)
        # 不带 confirm: 仅输出确认提示，不删除
        rc, out, _ = self.run_cmd("delete", aid)
        self.assertEqual(rc, 0)
        data = self.parse_json(out)
        self.assertEqual(data["status"], "等待确认")
        self.assertIn("confirm_token", data)
        self.assertTrue(os.path.exists(project_dir))  # 项目仍存在

        # 带正确 confirm token 才删除 (token = article_id 前 8 字符)
        token = aid[:8]
        rc, out, _ = self.run_cmd("delete", aid, "--confirm", token)
        self.assertEqual(rc, 0)
        self.assertFalse(os.path.exists(project_dir))

    def test_11_archive_project(self):
        """archive 命令正常移动项目到 archive 目录。"""
        aid = self.init_project("归档测试")
        rc, out, _ = self.run_cmd("archive", aid)
        self.assertEqual(rc, 0)
        data = self.parse_json(out)
        self.assertEqual(data["action"], "archive")
        self.assertEqual(data["status"], "已归档")
        # 原目录已移走
        self.assertFalse(os.path.exists(os.path.join(self.tmp_dir, aid)))
        # archive 目录下存在该项目
        archived_path = os.path.join(self.tmp_dir, "archive", aid, "article.json")
        self.assertTrue(os.path.exists(archived_path))

    def test_12_copy_project(self):
        """copy 命令正常复制项目（大纲与配置复制，产出字段清空）。"""
        aid = self.init_project("原文章")
        outline = {"sections": [{"title": "第一节"}, {"title": "第二节"}]}
        self.run_cmd("update", aid, "outline",
                     json.dumps(outline, ensure_ascii=False))
        rc, out, _ = self.run_cmd("copy", aid, "复制文章")
        self.assertEqual(rc, 0)
        data = self.parse_json(out)
        self.assertEqual(data["action"], "copy")
        self.assertEqual(data["source_id"], aid)
        self.assertNotIn("warning", data)  # 大纲非空，无 warning
        new_id = data["id"]
        self.assertNotEqual(new_id, aid)
        self.assertEqual(data["title"], "复制文章")
        # 新项目大纲已复制，产出字段为空
        new_project = self.read_article_json(new_id)
        self.assertEqual(new_project["outline"], outline)
        self.assertEqual(new_project["status"], "planning")
        self.assertEqual(new_project["draft"], {})

    def test_13_copy_empty_outline(self):
        """copy 源项目大纲为空时给出提示。"""
        aid = self.init_project("空大纲文章")
        # init 后 outline 为空
        self.assertEqual(self.read_article_json(aid)["outline"], {})
        rc, out, _ = self.run_cmd("copy", aid, "空大纲复制")
        self.assertEqual(rc, 0)
        data = self.parse_json(out)
        self.assertEqual(data["action"], "copy")
        self.assertIn("warning", data)
        self.assertIn("大纲为空", data["warning"])
        # 新项目大纲也为空
        new_project = self.read_article_json(data["id"])
        self.assertEqual(new_project["outline"], {})

    def test_14_delete_wrong_confirm_token(self):
        """delete 传错误 token 时不删除，返回错误且非零退出。"""
        aid = self.init_project("错误token测试")
        project_dir = os.path.join(self.tmp_dir, aid)
        # 传错误的 confirm token
        rc, out, _ = self.run_cmd("delete", aid, "--confirm", "wrongtoken")
        self.assertEqual(rc, ERROR_EXIT_CODE)
        data = self.parse_json(out)
        self.assertIn("error", data)
        self.assertIn("token", data["error"])
        # 项目仍存在
        self.assertTrue(os.path.exists(project_dir))

    def test_18_operations_log_rotation(self):
        """operations.log 超过 1MB 时自动轮转生成 .old 文件。"""
        aid = self.init_project("日志轮转测试")
        log_path = self.project_path(aid, "operations.log")
        old_log_path = log_path + ".old"
        # 手动写入超过 1MB 的日志内容
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("x" * (1024 * 1024 + 100))
        # 触发一次保存，应触发轮转
        self.run_cmd("status", aid, "testing_rotation")
        # .old 文件应存在
        self.assertTrue(os.path.exists(old_log_path))
        # 新日志应已重置并包含新条目
        with open(log_path, "r", encoding="utf-8") as f:
            new_log = f.read()
        self.assertIn("testing_rotation", new_log)


# ====================================================================
# T7: 端到端测试场景
# ====================================================================

class TestProjectManagerE2E(ProjectManagerTestCase):

    def test_15_e2e_full_flow(self):
        """端到端: init -> update_status -> update_field -> list -> show -> archive。"""
        # init
        aid = self.init_project("端到端文章")
        # update_status
        rc, out, _ = self.run_cmd("status", aid, "drafting")
        self.assertEqual(rc, 0)
        # update_field
        draft = {"content": "正文内容"}
        rc, out, _ = self.run_cmd("update", aid, "draft",
                                  json.dumps(draft, ensure_ascii=False))
        self.assertEqual(rc, 0)
        # list 能看到该项目
        rc, out, _ = self.run_cmd("list")
        self.assertEqual(rc, 0)
        data = self.parse_json(out)
        self.assertIn(aid, [p["id"] for p in data["projects"]])
        # show 验证状态与字段
        rc, out, _ = self.run_cmd("show", aid)
        self.assertEqual(rc, 0)
        project = self.parse_json(out)
        self.assertEqual(project["status"], "drafting")
        self.assertEqual(project["draft"], draft)
        # archive
        rc, out, _ = self.run_cmd("archive", aid)
        self.assertEqual(rc, 0)
        # archive 后 list 不再包含
        rc, out, _ = self.run_cmd("list")
        data = self.parse_json(out)
        self.assertNotIn(aid, [p["id"] for p in data["projects"]])

    def test_16_e2e_crash_recovery(self):
        """崩溃恢复: init -> 模拟崩溃(手动改状态) -> incomplete 检测。"""
        aid = self.init_project("崩溃恢复文章")
        # 模拟崩溃: 手动把状态改为中断状态 (drafting)
        project = self.read_article_json(aid)
        project["status"] = "drafting"
        self.write_article_json(aid, project)
        # incomplete 应能检测到该未完成项目
        rc, out, _ = self.run_cmd("incomplete")
        self.assertEqual(rc, 0)
        data = self.parse_json(out)
        self.assertIn(aid, [p["id"] for p in data["incomplete"]])

        # 已完成项目不在 incomplete 列表中
        done_id = self.init_project("已完成文章")
        self.run_cmd("status", done_id, "published")
        rc, out, _ = self.run_cmd("incomplete")
        self.assertEqual(rc, 0)
        data = self.parse_json(out)
        ids = [p["id"] for p in data["incomplete"]]
        self.assertNotIn(done_id, ids)
        self.assertIn(aid, ids)  # 崩溃项目仍被检测到

    def test_17_e2e_single_module(self):
        """单模块调用: init -> 只 update draft 字段 -> show 验证。"""
        aid = self.init_project("单模块文章")
        # 仅更新 draft 字段 (模拟单模块独立调用)
        draft = {"title": "单模块草稿", "content": "单模块正文"}
        rc, out, _ = self.run_cmd("update", aid, "draft",
                                  json.dumps(draft, ensure_ascii=False))
        self.assertEqual(rc, 0)
        # show 验证 draft 已写入，其他字段保持初始
        rc, out, _ = self.run_cmd("show", aid)
        self.assertEqual(rc, 0)
        project = self.parse_json(out)
        self.assertEqual(project["draft"], draft)
        self.assertEqual(project["status"], "planning")  # 状态未变
        self.assertEqual(project["outline"], {})  # 其他字段未动
        # history 记录了 draft 更新
        self.assertEqual(len(project["history"]), 1)
        self.assertEqual(project["history"][0]["stage"], "draft")


if __name__ == "__main__":
    unittest.main(verbosity=2)
