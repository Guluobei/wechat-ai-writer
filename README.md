# wechat-ai-writer

公众号 AI 行业内容创作全流程 Skill。

## 概述

聚焦 AI 行业（产品、技术、科普、行业解读），覆盖从选题到复盘的完整闭环：

```
选题 → 调研 → 大纲 → 撰写 → 配图 → 排版 → 校对 → 发布 → 复盘
```

## 特性

- **全流程覆盖**：10 个模块 + 1 个配置层，从选题到发布后复盘
- **开箱即用**：内置 24 个 AI 行业信源、通用风格档案、公众号排版模板
- **关键节点可控**：大纲、初稿、发布前三个确认点暂停等用户确认
- **错误自解释**：三段式错误呈现（发生了什么 / 为什么 / 你该做什么）
- **失败不阻塞**：每个失败点都有降级方案
- **崩溃可恢复**：每步自动存盘，重启后从断点继续
- **安全防护**：路径遍历校验、文件锁、自动备份

## 文件结构

```
wechat-ai-writer/
├── SKILL.md                          # 主编排器
├── .preheat                          # 预热文件
├── .gitignore
├── assets/                           # 配置层（开箱即用）
│   ├── default-sources.json          # 24 个 AI 行业信源
│   ├── default-style-profile.md      # 通用写作风格档案
│   └── default-template.html         # 公众号 HTML 排版模板
├── references/                       # 9 个子模块详细指令
│   ├── module-1-topic-planner.md     # 选题策划
│   ├── module-2-researcher.md        # 调研收集
│   ├── module-3-outliner.md          # 大纲构建 ★确认点1
│   ├── module-4-writer.md            # 正文撰写 ★确认点2
│   ├── module-5-image-designer.md    # 配图制作
│   ├── module-6-formatter.md         # 排版美化
│   ├── module-7-reviewer.md          # 校对优化
│   ├── module-8-publisher.md         # 发布分发 ★确认点3
│   └── module-9-retrospective.md     # 复盘反馈（可选）
├── scripts/
│   ├── project-manager.py            # 项目管理脚本
│   ├── test_project_manager.py       # 测试套件 v1（18 个用例）
│   └── test_project_manager_v2.py    # 测试套件 v2（43 个用例）
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-06-26-wechat-ai-content-skill-design.md  # 设计文档
```

## 测试

```bash
# 运行 v1 测试套件（18 个用例）
python3 scripts/test_project_manager.py

# 运行 v2 测试套件（43 个用例，覆盖安全/容错/端到端）
python3 scripts/test_project_manager_v2.py
```

## 质量保证

经过五角色（开发、测试、产品、用户、运维）四轮检测，共发现并修复 64 个问题，61 个测试用例全部通过。
