#!/usr/bin/env python3
"""
公众号 AI 内容创作 - 项目管理脚本
用于创建、读取、更新、列出、删除、归档、复制文章项目状态。
所有项目数据存储在 <PROJECTS_DIR>/<article_id>/article.json
PROJECTS_DIR 优先读取环境变量 WECHAT_WRITER_PROJECTS_DIR，默认 /workspace/projects
"""

import json
import os
import shutil
import sys
import uuid
from datetime import datetime

# C1: 文件锁防止并发写入冲突（fcntl 为 Linux 专有模块，非 Linux 平台降级为无锁）
try:
    import fcntl
except ImportError:
    fcntl = None

# O5: 路径用环境变量，优先读取环境变量，缺省回退到默认目录
PROJECTS_DIR = os.environ.get("WECHAT_WRITER_PROJECTS_DIR", "/workspace/projects")

# O4: 操作上下文，记录当前触发的操作类型，供 operations.log 使用
_op_context = {"operation": "保存项目"}


def set_operation(op):
    """设置当前操作类型（供 operations.log 记录）"""
    _op_context["operation"] = op


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def get_project_dir(article_id):
    return os.path.join(PROJECTS_DIR, article_id)


def get_project_file(article_id):
    return os.path.join(get_project_dir(article_id), "article.json")


def validate_article_id(article_id):
    """校验 article_id 安全性，防止路径遍历攻击"""
    import re
    # 只允许字母、数字、连字符
    if not re.match(r'^[a-zA-Z0-9\-]+$', article_id):
        print(json.dumps({
            "error": f"无效的项目ID: {article_id}",
            "suggestion": "项目ID只能包含字母、数字和连字符"
        }, ensure_ascii=False))
        sys.exit(2)


def check_disk_space():
    """O9: 检查 PROJECTS_DIR 所在磁盘剩余空间，小于 100MB 时输出警告但不中断操作"""
    # 若目录不存在，向上查找已存在的父目录用于 statvfs
    check_path = PROJECTS_DIR
    while check_path and not os.path.exists(check_path):
        parent = os.path.dirname(check_path)
        if parent == check_path:
            break
        check_path = parent
    try:
        stat = os.statvfs(check_path)
        free_bytes = stat.f_bavail * stat.f_frsize
        free_mb = free_bytes / (1024 * 1024)
        if free_mb < 100:
            print(json.dumps({
                "warning": f"磁盘剩余空间不足: {free_mb:.2f} MB",
                "free_mb": round(free_mb, 2),
                "threshold_mb": 100,
                "message": "磁盘空间不足 100MB，建议清理空间后再操作（本操作仍会继续执行）"
            }, ensure_ascii=False))
            return False
        return True
    except OSError:
        # 无法获取磁盘信息时不阻塞操作
        return True


def init_project(topic_title=""):
    """创建新文章项目"""
    # O9: 创建前检查磁盘空间（仅警告，不中断）
    check_disk_space()
    article_id = f"article-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
    # O10: 目录冲突防护，极低概率下 uuid 碰撞则重新生成
    while os.path.exists(get_project_dir(article_id)):
        article_id = f"article-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
    project_dir = get_project_dir(article_id)
    ensure_dir(project_dir)
    ensure_dir(os.path.join(project_dir, "images"))

    project = {
        "id": article_id,
        "status": "planning",
        "topic": {},
        "research": {},
        "outline": {},
        "draft": {},
        "images": {},
        "formatted": {},
        "review": {},
        "publish": {},
        "retrospective": {},
        "history": [],
    }

    if topic_title:
        project["topic"]["title"] = topic_title

    set_operation("创建项目")
    save_project(article_id, project)
    print(json.dumps({"action": "init", "id": article_id, "status": "planning"}, ensure_ascii=False))
    return article_id


def save_project(article_id, project):
    """保存项目状态（带文件锁）"""
    project_file = get_project_file(article_id)
    ensure_dir(get_project_dir(article_id))

    # C1: 文件锁防止并发写入冲突
    lock_file = project_file + ".lock"
    with open(lock_file, "w") as lf:
        if fcntl is not None:
            try:
                fcntl.flock(lf, fcntl.LOCK_EX)
            except (IOError, OSError):
                pass  # 锁获取失败不阻塞，继续写入

        # T4: 限制 history 保留最近 10 条
        if "history" in project and isinstance(project["history"], list):
            if len(project["history"]) > 10:
                project["history"] = project["history"][-10:]

        with open(project_file, "w", encoding="utf-8") as f:
            json.dump(project, f, ensure_ascii=False, indent=2)

        # O4: 追加操作日志到项目目录下的 operations.log
        log_path = os.path.join(get_project_dir(article_id), "operations.log")
        # O8: 日志轮转，超过 1MB 时将当前日志重命名为 .old，只保留一个旧日志文件
        try:
            if os.path.exists(log_path) and os.path.getsize(log_path) > 1024 * 1024:
                old_log_path = log_path + ".old"
                if os.path.exists(old_log_path):
                    os.remove(old_log_path)
                os.rename(log_path, old_log_path)
        except OSError:
            # 轮转失败不影响主流程
            pass
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = project.get("status", "unknown")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] 操作: {_op_context['operation']}, 状态: {status}\n")

        if fcntl is not None:
            try:
                fcntl.flock(lf, fcntl.LOCK_UN)
            except (IOError, OSError):
                pass


def load_project(article_id):
    """加载项目状态"""
    validate_article_id(article_id)
    project_file = get_project_file(article_id)
    # D4: 文件不存在时输出 JSON 格式错误
    if not os.path.exists(project_file):
        print(json.dumps({
            "error": f"项目不存在: {article_id}",
            "id": article_id,
            "suggestion": "请检查项目 ID 是否正确，或使用 list 命令查看所有可用项目"
        }, ensure_ascii=False))
        sys.exit(2)
    # T2/D4: JSON 解析失败时不崩溃，输出三段式 JSON 错误
    try:
        with open(project_file, "r", encoding="utf-8") as f:
            project = json.load(f)
    except json.JSONDecodeError:
        print(json.dumps({
            "error": "项目文件损坏，无法读取",
            "id": article_id,
            "suggestion": "请检查 article.json 是否被手动编辑导致格式错误，或删除该项目目录重新创建"
        }, ensure_ascii=False))
        sys.exit(2)

    # C2: 大文件加载优化，超过 500KB 时增加 _warning 字段提示
    file_size = os.path.getsize(project_file)
    if file_size > 500 * 1024:
        project["_warning"] = f"项目文件较大（{file_size // 1024}KB），加载可能较慢"

    return project


def backup_project(article_id):
    """O6: 关键节点自动备份，将 article.json 复制为 article.json.bak"""
    project_file = get_project_file(article_id)
    if os.path.exists(project_file):
        shutil.copy2(project_file, project_file + ".bak")


def update_status(article_id, status):
    """更新项目状态"""
    validate_article_id(article_id)
    project = load_project(article_id)
    # O6: 保存前先备份
    backup_project(article_id)
    project["status"] = status
    project["history"].append({
        "stage": status,
        "timestamp": datetime.now().isoformat(),
        "output_summary": f"状态更新为: {status}",
    })
    set_operation(f"更新状态: {status}")
    save_project(article_id, project)
    print(json.dumps({"action": "update_status", "id": article_id, "status": status}, ensure_ascii=False))


def update_field(article_id, field, data):
    """更新项目指定字段"""
    validate_article_id(article_id)
    project = load_project(article_id)
    # O6: 保存前先备份
    backup_project(article_id)
    project[field] = data
    project["history"].append({
        "stage": field,
        "timestamp": datetime.now().isoformat(),
        "output_summary": f"更新字段: {field}",
    })
    set_operation(f"更新字段: {field}")
    save_project(article_id, project)
    print(json.dumps({"action": "update_field", "id": article_id, "field": field}, ensure_ascii=False))


def list_projects():
    """列出所有项目"""
    if not os.path.exists(PROJECTS_DIR):
        print(json.dumps({"projects": [], "errors": []}, ensure_ascii=False))
        return

    projects = []
    errors = []
    for name in sorted(os.listdir(PROJECTS_DIR)):
        # D9/O7: 跳过 archive 目录
        if name == "archive":
            continue
        project_file = get_project_file(name)
        if os.path.exists(project_file):
            # D8: 直接读取并捕获异常，避免 load_project 触发 sys.exit 导致列表崩溃
            try:
                with open(project_file, "r", encoding="utf-8") as f:
                    project = json.load(f)
            except (json.JSONDecodeError, OSError):
                errors.append({"id": name, "reason": "article.json 损坏或不可读"})
                continue
            title = project.get("topic", {}).get("title", "未命名")
            status = project.get("status", "unknown")
            projects.append({"id": name, "title": title, "status": status})

    print(json.dumps({"projects": projects, "errors": errors}, ensure_ascii=False, indent=2))


def find_incomplete():
    """查找未完成的项目"""
    if not os.path.exists(PROJECTS_DIR):
        print(json.dumps({"incomplete": [], "errors": []}, ensure_ascii=False))
        return

    incomplete = []
    errors = []
    done_statuses = {"done", "published"}
    for name in sorted(os.listdir(PROJECTS_DIR)):
        # D9/O7: 跳过 archive 目录
        if name == "archive":
            continue
        project_file = get_project_file(name)
        if os.path.exists(project_file):
            # D8: 直接读取并捕获异常，避免 load_project 触发 sys.exit 导致列表崩溃
            try:
                with open(project_file, "r", encoding="utf-8") as f:
                    project = json.load(f)
            except (json.JSONDecodeError, OSError):
                errors.append({"id": name, "reason": "article.json 损坏或不可读"})
                continue
            if project.get("status", "") not in done_statuses:
                title = project.get("topic", {}).get("title", "未命名")
                status = project.get("status", "unknown")
                incomplete.append({"id": name, "title": title, "status": status})

    print(json.dumps({"incomplete": incomplete, "errors": errors}, ensure_ascii=False, indent=2))


def show_project(article_id):
    """显示项目详情"""
    validate_article_id(article_id)
    project = load_project(article_id)
    print(json.dumps(project, ensure_ascii=False, indent=2))


def delete_project(article_id, confirm_token=None):
    """T8: 删除指定项目目录（两步确认门控）
    第一次调用 delete <id>：只输出确认信息和 confirm_token，不删除
    第二次调用 delete <id> --confirm <token>：token 匹配后才执行 rmtree
    """
    validate_article_id(article_id)
    project_dir = get_project_dir(article_id)
    if not os.path.exists(project_dir):
        print(json.dumps({
            "error": f"项目不存在: {article_id}",
            "id": article_id,
            "suggestion": "请检查项目 ID 是否正确，或使用 list 命令查看所有可用项目"
        }, ensure_ascii=False))
        sys.exit(2)

    # 确认 token 使用项目 ID 的前 8 个字符
    expected_token = article_id[:8]

    # 未提供 --confirm：只输出确认提示，不执行删除
    if confirm_token is None:
        print(json.dumps({
            "action": "delete",
            "id": article_id,
            "status": "等待确认",
            "target": project_dir,
            "confirm_token": expected_token,
            "message": f"即将删除项目目录: {project_dir}，请使用 --confirm {expected_token} 确认删除"
        }, ensure_ascii=False))
        return

    # 提供了 --confirm 但 token 不匹配
    if confirm_token != expected_token:
        print(json.dumps({
            "error": "确认 token 不匹配，删除已取消",
            "id": article_id,
            "expected_token": expected_token,
            "suggestion": f"请使用正确的 token 重新执行: --confirm {expected_token}"
        }, ensure_ascii=False))
        sys.exit(2)

    # token 匹配，执行删除
    shutil.rmtree(project_dir)
    print(json.dumps({
        "action": "delete",
        "id": article_id,
        "status": "已删除",
        "message": "项目已成功删除"
    }, ensure_ascii=False))


def archive_project(article_id):
    """U3: 将项目移动到 archive 目录下"""
    validate_article_id(article_id)
    project_dir = get_project_dir(article_id)
    if not os.path.exists(project_dir):
        print(json.dumps({
            "error": f"项目不存在: {article_id}",
            "id": article_id,
            "suggestion": "请检查项目 ID 是否正确，或使用 list 命令查看所有可用项目"
        }, ensure_ascii=False))
        sys.exit(2)
    archive_dir = os.path.join(PROJECTS_DIR, "archive")
    ensure_dir(archive_dir)
    target_dir = os.path.join(archive_dir, article_id)
    if os.path.exists(target_dir):
        print(json.dumps({
            "error": f"归档目录已存在同名项目: {target_dir}",
            "id": article_id,
            "suggestion": "请先删除归档目录中的同名项目，或重命名后再归档"
        }, ensure_ascii=False))
        sys.exit(2)
    shutil.move(project_dir, target_dir)
    print(json.dumps({
        "action": "archive",
        "id": article_id,
        "status": "已归档",
        "archive_path": target_dir
    }, ensure_ascii=False))


def copy_project(source_id, new_title=None):
    """U4: 复制源项目的大纲和配置到新项目，不复制 draft/formatted/images 等内容产出"""
    validate_article_id(source_id)
    # O9: 复制前检查磁盘空间（仅警告，不中断）
    check_disk_space()
    source = load_project(source_id)
    new_id = f"article-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
    project_dir = get_project_dir(new_id)
    ensure_dir(project_dir)
    ensure_dir(os.path.join(project_dir, "images"))

    # 仅复制配置(topic)和大纲(outline)，产出类字段清空，状态重置为 planning
    new_project = {
        "id": new_id,
        "status": "planning",
        "topic": source.get("topic", {}),
        "research": {},
        "outline": source.get("outline", {}),
        "draft": {},
        "images": {},
        "formatted": {},
        "review": {},
        "publish": {},
        "retrospective": {},
        "history": [],
    }

    if new_title:
        new_project["topic"]["title"] = new_title

    set_operation("复制项目")
    save_project(new_id, new_project)

    result = {
        "action": "copy",
        "source_id": source_id,
        "id": new_id,
        "status": "planning",
        "title": new_project["topic"].get("title", "未命名")
    }
    # T10: 源项目大纲为空时给出提示
    if not source.get("outline"):
        result["warning"] = "源项目大纲为空，新项目大纲也为空"

    print(json.dumps(result, ensure_ascii=False))
    return new_id


def main():
    if len(sys.argv) < 2:
        print("用法: project-manager.py <command> [args]")
        print("命令:")
        print("  init [title]                      创建新项目")
        print("  list                              列出所有项目")
        print("  incomplete                        查找未完成项目")
        print("  show <id>                         显示项目详情")
        print("  status <id> <status>              更新项目状态")
        print("  update <id> <field> <json_data>   更新项目字段")
        print("  delete <id> [--confirm <token>]   删除指定项目目录（需二次确认）")
        print("  archive <id>                      将项目移动到 archive 目录")
        print("  copy <source_id> [new_title]      复制项目大纲和配置到新项目")
        # D5: 帮助信息（无参数）退出码为 0
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "init":
        title = sys.argv[2] if len(sys.argv) > 2 else ""
        init_project(title)

    elif cmd == "list":
        list_projects()

    elif cmd == "incomplete":
        find_incomplete()

    elif cmd == "show":
        if len(sys.argv) < 3:
            print(json.dumps({
                "error": "缺少参数",
                "suggestion": "用法: show <id>"
            }, ensure_ascii=False))
            sys.exit(2)
        show_project(sys.argv[2])

    elif cmd == "status":
        if len(sys.argv) < 4:
            print(json.dumps({
                "error": "缺少参数",
                "suggestion": "用法: status <id> <status>"
            }, ensure_ascii=False))
            sys.exit(2)
        update_status(sys.argv[2], sys.argv[3])

    elif cmd == "update":
        if len(sys.argv) < 5:
            print(json.dumps({
                "error": "缺少参数",
                "suggestion": "用法: update <id> <field> <json_data>"
            }, ensure_ascii=False))
            sys.exit(2)
        article_id = sys.argv[2]
        field = sys.argv[3]
        # D5: JSON 解析失败也输出 JSON 错误
        try:
            data = json.loads(sys.argv[4])
        except json.JSONDecodeError:
            print(json.dumps({
                "error": "字段数据 JSON 解析失败",
                "suggestion": "请确保传入的 json_data 是合法的 JSON 字符串"
            }, ensure_ascii=False))
            sys.exit(2)
        update_field(article_id, field, data)

    elif cmd == "delete":
        if len(sys.argv) < 3:
            print(json.dumps({
                "error": "缺少参数",
                "suggestion": "用法: delete <id> [--confirm <token>]"
            }, ensure_ascii=False))
            sys.exit(2)
        article_id = sys.argv[2]
        # T8: 解析可选的 --confirm <token>
        confirm_token = None
        if len(sys.argv) >= 5 and sys.argv[3] == "--confirm":
            confirm_token = sys.argv[4]
        delete_project(article_id, confirm_token)

    elif cmd == "archive":
        if len(sys.argv) < 3:
            print(json.dumps({
                "error": "缺少参数",
                "suggestion": "用法: archive <id>"
            }, ensure_ascii=False))
            sys.exit(2)
        archive_project(sys.argv[2])

    elif cmd == "copy":
        if len(sys.argv) < 3:
            print(json.dumps({
                "error": "缺少参数",
                "suggestion": "用法: copy <source_id> [new_title]"
            }, ensure_ascii=False))
            sys.exit(2)
        source_id = sys.argv[2]
        new_title = sys.argv[3] if len(sys.argv) > 3 else None
        copy_project(source_id, new_title)

    else:
        print(json.dumps({
            "error": f"未知命令: {cmd}",
            "suggestion": "请使用 project-manager.py（不带参数）查看可用命令列表"
        }, ensure_ascii=False))
        sys.exit(2)


if __name__ == "__main__":
    main()
