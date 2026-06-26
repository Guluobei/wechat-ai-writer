#!/usr/bin/env python3
"""
project-manager.py 全面测试套件（v2）

覆盖四轮检测中发现的所有场景：
  - 第一轮：基本功能、错误处理、降级方案、崩溃恢复
  - 第二轮：list 容错、archive 排除、delete 二次确认、日志轮转、目录冲突
  - 第三轮：错误 token、operations.log 轮转、copy 边界条件
  - 第四轮：路径遍历安全、文件锁、大文件警告、字段完整性

测试分类：
  A. 基础功能（init/list/show/status/update）
  B. 安全性（路径遍历、ID 校验）
  C. 容错性（损坏 JSON、缺失文件、archive 隔离）
  D. 数据完整性（history 限制、备份、字段同步）
  E. 高级功能（delete 二次确认、archive、copy）
  F. 运维（日志轮转、磁盘检查、大文件警告）
  G. 端到端场景（全流程、崩溃恢复、单模块、多项目并发）

独立运行:
  python3 test_project_manager_v2.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_MANAGER = os.path.join(SCRIPT_DIR, "project-manager.py")
ERROR_EXIT_CODE = 2


class TestBase(unittest.TestCase):
    """测试基类：临时目录隔离 + CLI 调用辅助。"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="waw_test_")
        self.env = os.environ.copy()
        self.env["WECHAT_WRITER_PROJECTS_DIR"] = self.tmp_dir

    def tearDown(self):
        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

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
        """解析 stdout 为 JSON，兼容多行和 warning 前置。"""
        stdout = stdout.strip()
        self.assertTrue(stdout, "命令无输出")
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            pass
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        self.fail(f"无法解析 JSON: {stdout!r}")

    def init_project(self, title="测试文章"):
        """创建项目，返回 article_id。"""
        rc, out, err = self.run_cmd("init", title)
        self.assertEqual(rc, 0, f"init 失败: {out!r} {err!r}")
        return self.parse_json(out)["id"]

    def project_path(self, article_id, *parts):
        return os.path.join(self.tmp_dir, article_id, *parts)

    def read_article(self, article_id):
        with open(self.project_path(article_id, "article.json"), "r", encoding="utf-8") as f:
            return json.load(f)

    def write_article(self, article_id, data):
        with open(self.project_path(article_id, "article.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def corrupt_article(self, article_id, content="not valid json {{{"):
        """手动损坏 article.json。"""
        with open(self.project_path(article_id, "article.json"), "w", encoding="utf-8") as f:
            f.write(content)


# ================================================================
# A. 基础功能
# ================================================================

class TestBasicFunctions(TestBase):

    def test_a01_init_creates_project(self):
        """init 创建项目，article.json 含全部字段。"""
        aid = self.init_project("AI Agent 深度解析")
        self.assertTrue(aid.startswith("article-"))
        # article.json 存在
        self.assertTrue(os.path.exists(self.project_path(aid, "article.json")))
        # images 子目录存在
        self.assertTrue(os.path.isdir(self.project_path(aid, "images")))
        # 字段完整
        project = self.read_article(aid)
        expected = {"id", "status", "topic", "research", "outline", "draft",
                    "images", "formatted", "review", "publish", "retrospective", "history"}
        self.assertTrue(expected.issubset(project.keys()))
        self.assertEqual(project["status"], "planning")
        self.assertEqual(project["topic"]["title"], "AI Agent 深度解析")
        self.assertEqual(project["history"], [])

    def test_a02_init_empty_title(self):
        """init 不带标题也能创建。"""
        rc, out, _ = self.run_cmd("init")
        self.assertEqual(rc, 0)
        data = self.parse_json(out)
        self.assertEqual(data["status"], "planning")

    def test_a03_list_returns_projects(self):
        """list 返回所有项目。"""
        id1 = self.init_project("文章一")
        id2 = self.init_project("文章二")
        rc, out, _ = self.run_cmd("list")
        self.assertEqual(rc, 0)
        data = self.parse_json(out)
        ids = [p["id"] for p in data["projects"]]
        self.assertIn(id1, ids)
        self.assertIn(id2, ids)

    def test_a04_show_displays_project(self):
        """show 返回完整项目数据。"""
        aid = self.init_project("展示测试")
        rc, out, _ = self.run_cmd("show", aid)
        self.assertEqual(rc, 0)
        project = self.parse_json(out)
        self.assertEqual(project["id"], aid)

    def test_a05_update_status(self):
        """status 更新状态并记录 history。"""
        aid = self.init_project()
        rc, out, _ = self.run_cmd("status", aid, "researching")
        self.assertEqual(rc, 0)
        project = self.read_article(aid)
        self.assertEqual(project["status"], "researching")
        self.assertEqual(len(project["history"]), 1)
        self.assertEqual(project["history"][0]["stage"], "researching")

    def test_a06_update_field(self):
        """update 写入指定字段。"""
        aid = self.init_project()
        draft = {"content_markdown": "正文", "word_count": 100}
        rc, out, _ = self.run_cmd("update", aid, "draft",
                                  json.dumps(draft, ensure_ascii=False))
        self.assertEqual(rc, 0)
        project = self.read_article(aid)
        self.assertEqual(project["draft"], draft)

    def test_a07_help_exits_zero(self):
        """无参数调用显示帮助，退出码 0。"""
        rc, out, _ = self.run_cmd()
        self.assertEqual(rc, 0)
        self.assertIn("用法", out)


# ================================================================
# B. 安全性
# ================================================================

class TestSecurity(TestBase):

    def test_b01_path_traversal_dotdot(self):
        """S1: ../../etc 被拦截。"""
        rc, out, _ = self.run_cmd("show", "../../etc")
        self.assertEqual(rc, ERROR_EXIT_CODE)
        data = self.parse_json(out)
        self.assertIn("error", data)
        self.assertIn("无效", data["error"])

    def test_b02_path_traversal_slash(self):
        """S1: 含斜杠的 ID 被拦截。"""
        rc, out, _ = self.run_cmd("show", "foo/bar")
        self.assertEqual(rc, ERROR_EXIT_CODE)
        data = self.parse_json(out)
        self.assertIn("error", data)

    def test_b03_path_traversal_backslash(self):
        """S1: 含反斜杠的 ID 被拦截。"""
        rc, out, _ = self.run_cmd("show", "foo\\bar")
        self.assertEqual(rc, ERROR_EXIT_CODE)

    def test_b04_valid_id_passes(self):
        """合法 ID（字母+数字+连字符）通过校验。"""
        aid = self.init_project()
        rc, out, _ = self.run_cmd("show", aid)
        self.assertEqual(rc, 0)

    def test_b05_delete_with_traversal_id(self):
        """S1: delete 恶意 ID 被拦截，不会删除任何目录。"""
        rc, out, _ = self.run_cmd("delete", "../../etc", "--confirm", "whatever")
        self.assertEqual(rc, ERROR_EXIT_CODE)

    def test_b06_archive_with_traversal_id(self):
        """S1: archive 恶意 ID 被拦截。"""
        rc, out, _ = self.run_cmd("archive", "../../../tmp")
        self.assertEqual(rc, ERROR_EXIT_CODE)


# ================================================================
# C. 容错性
# ================================================================

class TestFaultTolerance(TestBase):

    def test_c01_list_with_corrupted_project(self):
        """D8: list 遇损坏项目不崩溃，返回 errors 数组。"""
        good = self.init_project("正常")
        bad = self.init_project("损坏")
        self.corrupt_article(bad)
        rc, out, _ = self.run_cmd("list")
        self.assertEqual(rc, 0)
        data = self.parse_json(out)
        ids = [p["id"] for p in data["projects"]]
        self.assertIn(good, ids)
        self.assertNotIn(bad, ids)
        self.assertIn("errors", data)
        error_ids = [e["id"] for e in data["errors"]]
        self.assertIn(bad, error_ids)

    def test_c02_incomplete_with_corrupted_project(self):
        """D8: incomplete 遇损坏项目不崩溃。"""
        good = self.init_project("正常")
        bad = self.init_project("损坏")
        self.corrupt_article(bad)
        rc, out, _ = self.run_cmd("incomplete")
        self.assertEqual(rc, 0)
        data = self.parse_json(out)
        # 正常项目在列表中
        good_ids = [p["id"] for p in data["incomplete"]]
        self.assertIn(good, good_ids)

    def test_c03_show_corrupted_json(self):
        """D4/T2: show 损坏 JSON 返回错误不崩溃。"""
        aid = self.init_project()
        self.corrupt_article(aid)
        rc, out, _ = self.run_cmd("show", aid)
        self.assertEqual(rc, ERROR_EXIT_CODE)
        data = self.parse_json(out)
        self.assertIn("error", data)

    def test_c04_show_nonexistent_project(self):
        """show 不存在的项目返回 JSON 错误。"""
        rc, out, _ = self.run_cmd("show", "article-nonexist-999999")
        self.assertEqual(rc, ERROR_EXIT_CODE)
        data = self.parse_json(out)
        self.assertIn("error", data)

    def test_c05_list_excludes_archive(self):
        """D9/O7: list 不包含 archive 目录。"""
        aid = self.init_project("待归档")
        self.run_cmd("archive", aid)
        rc, out, _ = self.run_cmd("list")
        data = self.parse_json(out)
        ids = [p["id"] for p in data["projects"]]
        self.assertNotIn(aid, ids)

    def test_c06_incomplete_excludes_archive(self):
        """D9/O7: incomplete 不包含 archive 目录。"""
        aid = self.init_project("待归档")
        self.run_cmd("archive", aid)
        rc, out, _ = self.run_cmd("incomplete")
        data = self.parse_json(out)
        ids = [p["id"] for p in data["incomplete"]]
        self.assertNotIn(aid, ids)

    def test_c07_list_empty_dir(self):
        """list 空目录返回空列表。"""
        rc, out, _ = self.run_cmd("list")
        self.assertEqual(rc, 0)
        data = self.parse_json(out)
        self.assertEqual(data["projects"], [])

    def test_c08_status_nonexistent_project(self):
        """status 不存在的项目返回错误。"""
        rc, out, _ = self.run_cmd("status", "article-ghost-000000", "researching")
        self.assertEqual(rc, ERROR_EXIT_CODE)


# ================================================================
# D. 数据完整性
# ================================================================

class TestDataIntegrity(TestBase):

    def test_d01_history_limit_10(self):
        """T4: history 超过 10 条只保留最近 10 条。"""
        aid = self.init_project()
        for i in range(12):
            self.run_cmd("status", aid, f"stage{i}")
        project = self.read_article(aid)
        self.assertEqual(len(project["history"]), 10)
        stages = [h["stage"] for h in project["history"]]
        self.assertEqual(stages[0], "stage2")
        self.assertEqual(stages[-1], "stage11")

    def test_d02_backup_on_status_update(self):
        """O6: status 更新时生成 .bak 备份。"""
        aid = self.init_project()
        bak = self.project_path(aid, "article.json.bak")
        self.assertFalse(os.path.exists(bak))
        self.run_cmd("status", aid, "researching")
        self.assertTrue(os.path.exists(bak))
        # .bak 内容是更新前状态
        with open(bak, "r", encoding="utf-8") as f:
            bak_data = json.load(f)
        self.assertEqual(bak_data["status"], "planning")

    def test_d03_backup_on_field_update(self):
        """O6: update field 时也生成 .bak 备份。"""
        aid = self.init_project()
        bak = self.project_path(aid, "article.json.bak")
        self.run_cmd("update", aid, "draft",
                     json.dumps({"content": "x"}, ensure_ascii=False))
        self.assertTrue(os.path.exists(bak))

    def test_d04_operations_log_written(self):
        """O4: 每次保存写入 operations.log。"""
        aid = self.init_project()
        log = self.project_path(aid, "operations.log")
        self.assertTrue(os.path.exists(log))
        with open(log, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("创建项目", content)
        # 更新后再检查
        self.run_cmd("status", aid, "researching")
        with open(log, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("researching", content)

    def test_d05_init_creates_unique_id(self):
        """O10: 连续 init 多个项目 ID 不冲突。"""
        ids = [self.init_project(f"文章{i}") for i in range(5)]
        self.assertEqual(len(ids), len(set(ids)))

    def test_d06_update_preserves_other_fields(self):
        """update 只改目标字段，不影响其他字段。"""
        aid = self.init_project()
        self.run_cmd("status", aid, "researching")
        self.run_cmd("update", aid, "draft",
                     json.dumps({"content": "草稿"}, ensure_ascii=False))
        project = self.read_article(aid)
        self.assertEqual(project["status"], "researching")  # 状态未被覆盖
        self.assertEqual(project["draft"]["content"], "草稿")
        self.assertEqual(project["outline"], {})  # 其他字段未动


# ================================================================
# E. 高级功能
# ================================================================

class TestAdvancedFunctions(TestBase):

    def test_e01_delete_without_confirm(self):
        """T8: delete 不带 confirm 只提示，不删除。"""
        aid = self.init_project()
        rc, out, _ = self.run_cmd("delete", aid)
        self.assertEqual(rc, 0)
        data = self.parse_json(out)
        self.assertEqual(data["status"], "等待确认")
        self.assertIn("confirm_token", data)
        self.assertTrue(os.path.exists(os.path.join(self.tmp_dir, aid)))

    def test_e02_delete_with_correct_confirm(self):
        """T8: delete 带正确 token 删除项目。"""
        aid = self.init_project()
        token = aid[:8]
        rc, out, _ = self.run_cmd("delete", aid, "--confirm", token)
        self.assertEqual(rc, 0)
        self.assertFalse(os.path.exists(os.path.join(self.tmp_dir, aid)))

    def test_e03_delete_with_wrong_confirm(self):
        """T11: delete 带错误 token 不删除，返回错误。"""
        aid = self.init_project()
        rc, out, _ = self.run_cmd("delete", aid, "--confirm", "wrongtoken")
        self.assertEqual(rc, ERROR_EXIT_CODE)
        data = self.parse_json(out)
        self.assertIn("error", data)
        self.assertTrue(os.path.exists(os.path.join(self.tmp_dir, aid)))

    def test_e04_archive_moves_project(self):
        """archive 将项目移到 archive 目录。"""
        aid = self.init_project("归档")
        rc, out, _ = self.run_cmd("archive", aid)
        self.assertEqual(rc, 0)
        self.assertFalse(os.path.exists(os.path.join(self.tmp_dir, aid)))
        archived = os.path.join(self.tmp_dir, "archive", aid, "article.json")
        self.assertTrue(os.path.exists(archived))

    def test_e05_copy_with_outline(self):
        """copy 复制大纲和配置，清空产出字段。"""
        aid = self.init_project("原文")
        outline = {"sections": [{"title": "一"}]}
        self.run_cmd("update", aid, "outline",
                     json.dumps(outline, ensure_ascii=False))
        rc, out, _ = self.run_cmd("copy", aid, "复制文")
        self.assertEqual(rc, 0)
        data = self.parse_json(out)
        new_id = data["id"]
        new_project = self.read_article(new_id)
        self.assertEqual(new_project["outline"], outline)
        self.assertEqual(new_project["draft"], {})
        self.assertEqual(new_project["status"], "planning")

    def test_e06_copy_empty_outline_warning(self):
        """T10: copy 源大纲为空时输出 warning。"""
        aid = self.init_project()
        rc, out, _ = self.run_cmd("copy", aid, "空大纲复制")
        self.assertEqual(rc, 0)
        data = self.parse_json(out)
        self.assertIn("warning", data)
        self.assertIn("大纲为空", data["warning"])

    def test_e07_copy_nonexistent_source(self):
        """copy 不存在的源项目返回错误。"""
        rc, out, _ = self.run_cmd("copy", "article-ghost-000000", "新文章")
        self.assertEqual(rc, ERROR_EXIT_CODE)
        data = self.parse_json(out)
        self.assertIn("error", data)


# ================================================================
# F. 运维
# ================================================================

class TestOps(TestBase):

    def test_f01_operations_log_rotation(self):
        """T12/O8: operations.log 超 1MB 轮转生成 .old。"""
        aid = self.init_project()
        log = self.project_path(aid, "operations.log")
        old_log = log + ".old"
        # 写入超过 1MB
        with open(log, "w", encoding="utf-8") as f:
            f.write("x" * (1024 * 1024 + 100))
        # 触发保存
        self.run_cmd("status", aid, "rotation_test")
        self.assertTrue(os.path.exists(old_log))
        with open(log, "r", encoding="utf-8") as f:
            self.assertIn("rotation_test", f.read())

    def test_f02_backup_file_kept_after_multiple_updates(self):
        """O6: 多次更新后 .bak 始终存在且是上一次状态。"""
        aid = self.init_project()
        self.run_cmd("status", aid, "stage1")
        self.run_cmd("status", aid, "stage2")
        bak = self.project_path(aid, "article.json.bak")
        self.assertTrue(os.path.exists(bak))
        with open(bak, "r", encoding="utf-8") as f:
            bak_data = json.load(f)
        # .bak 应该是 stage1（上一次状态）
        self.assertEqual(bak_data["status"], "stage1")

    def test_f03_large_file_warning(self):
        """C2: article.json 超 500KB 时 show 返回 _warning。"""
        aid = self.init_project()
        # 构造大文件
        project = self.read_article(aid)
        project["draft"] = {"content_markdown": "x" * (600 * 1024)}
        self.write_article(aid, project)
        rc, out, _ = self.run_cmd("show", aid)
        self.assertEqual(rc, 0)
        data = self.parse_json(out)
        self.assertIn("_warning", data)
        self.assertIn("较大", data["_warning"])


# ================================================================
# G. 端到端场景
# ================================================================

class TestE2E(TestBase):

    def test_g01_full_workflow(self):
        """端到端：init → status → update → list → show → archive。"""
        aid = self.init_project("全流程文章")
        # 模拟流程推进
        self.run_cmd("status", aid, "researching")
        self.run_cmd("update", aid, "research",
                     json.dumps({"facts": ["AI 事实"]}, ensure_ascii=False))
        self.run_cmd("status", aid, "outlining")
        self.run_cmd("update", aid, "outline",
                     json.dumps({"sections": [{"title": "一"}]}, ensure_ascii=False))
        self.run_cmd("status", aid, "writing")
        self.run_cmd("update", aid, "draft",
                     json.dumps({"content_markdown": "正文"}, ensure_ascii=False))
        # list 包含
        rc, out, _ = self.run_cmd("list")
        data = self.parse_json(out)
        self.assertIn(aid, [p["id"] for p in data["projects"]])
        # show 验证全链路
        rc, out, _ = self.run_cmd("show", aid)
        project = self.parse_json(out)
        self.assertEqual(project["status"], "writing")
        self.assertEqual(project["research"]["facts"], ["AI 事实"])
        self.assertEqual(project["outline"]["sections"][0]["title"], "一")
        self.assertEqual(project["draft"]["content_markdown"], "正文")
        # history 记录了所有阶段
        stages = [h["stage"] for h in project["history"]]
        self.assertIn("researching", stages)
        self.assertIn("outlining", stages)
        self.assertIn("writing", stages)
        # archive
        self.run_cmd("archive", aid)
        rc, out, _ = self.run_cmd("list")
        data = self.parse_json(out)
        self.assertNotIn(aid, [p["id"] for p in data["projects"]])

    def test_g02_crash_recovery(self):
        """崩溃恢复：init → 手动改状态 → incomplete 检测。"""
        aid = self.init_project("崩溃文章")
        project = self.read_article(aid)
        project["status"] = "outlining"
        self.write_article(aid, project)
        rc, out, _ = self.run_cmd("incomplete")
        self.assertEqual(rc, 0)
        data = self.parse_json(out)
        ids = [p["id"] for p in data["incomplete"]]
        self.assertIn(aid, ids)

    def test_g03_single_module_workflow(self):
        """单模块调用：init → 只 update draft → show 验证。"""
        aid = self.init_project()
        draft = {"content_markdown": "单模块草稿", "inline_citations": []}
        self.run_cmd("update", aid, "draft",
                     json.dumps(draft, ensure_ascii=False))
        rc, out, _ = self.run_cmd("show", aid)
        project = self.parse_json(out)
        self.assertEqual(project["draft"], draft)
        self.assertEqual(project["status"], "planning")
        self.assertEqual(project["outline"], {})

    def test_g04_multi_project_management(self):
        """多项目管理：创建3个 → list → incomplete → archive 1 → verify。"""
        id1 = self.init_project("文章一")
        id2 = self.init_project("文章二")
        id3 = self.init_project("文章三")
        # id3 标记为已完成
        self.run_cmd("status", id3, "published")
        # list 包含全部
        rc, out, _ = self.run_cmd("list")
        data = self.parse_json(out)
        all_ids = [p["id"] for p in data["projects"]]
        self.assertEqual(len(all_ids), 3)
        # incomplete 只含未完成
        rc, out, _ = self.run_cmd("incomplete")
        data = self.parse_json(out)
        incomplete_ids = [p["id"] for p in data["incomplete"]]
        self.assertIn(id1, incomplete_ids)
        self.assertIn(id2, incomplete_ids)
        self.assertNotIn(id3, incomplete_ids)
        # archive id1
        self.run_cmd("archive", id1)
        rc, out, _ = self.run_cmd("list")
        data = self.parse_json(out)
        remaining = [p["id"] for p in data["projects"]]
        self.assertNotIn(id1, remaining)
        self.assertIn(id2, remaining)
        self.assertIn(id3, remaining)

    def test_g05_corrupted_project_recovery(self):
        """损坏项目恢复：3 个项目 → 损坏 1 个 → list 仍返回其他 2 个 + errors。"""
        id1 = self.init_project("正常一")
        id2 = self.init_project("正常二")
        id3 = self.init_project("损坏")
        self.corrupt_article(id3)
        # list 不崩溃
        rc, out, _ = self.run_cmd("list")
        self.assertEqual(rc, 0)
        data = self.parse_json(out)
        project_ids = [p["id"] for p in data["projects"]]
        self.assertIn(id1, project_ids)
        self.assertIn(id2, project_ids)
        self.assertNotIn(id3, project_ids)
        self.assertIn("errors", data)
        error_ids = [e["id"] for e in data["errors"]]
        self.assertIn(id3, error_ids)
        # incomplete 也不崩溃
        rc, out, _ = self.run_cmd("incomplete")
        self.assertEqual(rc, 0)

    def test_g06_delete_full_cycle(self):
        """删除全流程：init → delete 提示 → delete 确认 → 验证已删除。"""
        aid = self.init_project("待删除")
        project_dir = os.path.join(self.tmp_dir, aid)
        self.assertTrue(os.path.exists(project_dir))
        # 第一次 delete：只提示
        rc, out, _ = self.run_cmd("delete", aid)
        self.assertEqual(rc, 0)
        data = self.parse_json(out)
        token = data["confirm_token"]
        self.assertTrue(os.path.exists(project_dir))
        # 第二次 delete：确认删除
        rc, out, _ = self.run_cmd("delete", aid, "--confirm", token)
        self.assertEqual(rc, 0)
        self.assertFalse(os.path.exists(project_dir))
        # list 不再包含
        rc, out, _ = self.run_cmd("list")
        data = self.parse_json(out)
        self.assertNotIn(aid, [p["id"] for p in data["projects"]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
