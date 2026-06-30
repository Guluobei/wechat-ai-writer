# 模块 5：配图制作（Image Designer）

> 四通道混合配图：社交卡片 + AI 生成 + 截图 + 数据图表。为初稿匹配视觉资产，输出可直接嵌入排版的图片文件清单。

## 模块职责

- 根据大纲配图标注，逐张判断最合适的配图通道（社交卡片 / AI 生成 / 截图 / 数据图表）
- 生成封面图与文中插图，确保图片与段落内容契合
- 统一命名、存储图片文件，符合公众号尺寸规格
- 产出配图清单，写入 `ArticleProject.images` 字段

配图制作是全流程中「失败不阻塞」的典型环节：任何一张图缺失都不应卡住整体流程，应降级处理并明确标注。

## 输入

| 输入项 | 来源 | 说明 |
|--------|------|------|
| 大纲配图标注 | `ArticleProject.outline.sections[].image_type` | 每节的配图类型标注（social_card / ai_generated / screenshot / data_chart / none） |
| 配图描述 | `ArticleProject.outline.sections[].image_description` | 每节配图的内容描述与意图 |
| 初稿正文 | `ArticleProject.draft` | 用于图文匹配校验，确认图片与段落内容契合 |
| 调研数据点 | `ArticleProject.research.data_points` | 数据图表通道的数据来源（基准测试、能力对比、市场数据） |
| 文章标题 | `ArticleProject.topic.title` | 社交卡片通道的封面标题来源 |
| 文章类型 | `ArticleProject.topic.content_type` | 产品 / 技术 / 科普 / 行业解读，影响配图风格取向 |
| 项目 ID | `ArticleProject.id` | 决定图片存储路径 `/workspace/projects/<article_id>/images/` |

## 输出

写入 `ArticleProject.images` 字段，结构如下：

```json
{
  "cover": {
    "path": "/workspace/projects/<article_id>/images/cover.png",
    "channel": "social_card | ai_generated",
    "prompt": "封面图生成 prompt 或 guizang 配置说明",
    "status": "success"
  },
  "inline": [
    {
      "id": "img-1",
      "section_index": 2,
      "channel": "social_card | ai_generated | screenshot | data_chart",
      "path": "/workspace/projects/<article_id>/images/img-1.png",
      "caption": "图片说明文字",
      "screenshot_guide": "截图指引（仅截图通道）",
      "status": "success | placeholder | skipped",
      "placeholder_reason": "降级原因（仅非 success 时）"
    }
  ]
}
```

- 图片文件统一存储到 `/workspace/projects/<article_id>/images/`
- 配图清单随 `article.json` 持久化

## 执行步骤

### 步骤 1：配图规划

遍历大纲 `sections[]` 的配图标注，逐张判断使用哪个通道。**封面图优先走社交卡片通道**。

| 标注类型 | 推荐通道 | 说明 |
|---------|---------|------|
| `social_card`（封面图） | **社交卡片通道（首选）** | 公众号 21:9 + 1:1 封面对，guizang skill 渲染 |
| `social_card`（数据卡） | **社交卡片通道** | KPI 柱塔、TOP 排名条形图、账本行、能力矩阵 |
| `ai_generated`（封面图） | AI 生成（降级） | 社交卡片通道不可用时降级 |
| `ai_generated`（概念图） | AI 生成 | 抽象概念可视化、示意图 |
| `ai_generated`（氛围图） | AI 生成 | 氛围图、科技感插画 |
| `screenshot`（产品展示类） | 截图通道 | 生成截图指引，需用户提供 |
| `screenshot`（技术演示类） | 截图通道 | 生成截图规范 |
| `data_chart`（分析型） | 数据图表通道 | 趋势折线、分布饼图、多系列对比——从 `research.data_points` 生成 |
| `data_chart`（社交型） | **社交卡片通道** | 少数关键数字 + 强排版——用 guizang Swiss KPI/排名骨架 |
| `none` | 不配图 | 该节无需配图 |

**数据图表的通道选择规则**：

| 数据特征 | 推荐通道 | 原因 |
|---------|---------|------|
| 少数关键数字（3-8 个），强调对比和排名 | 社交卡片（Swiss KPI Tower / H-Bar） | 设计感强，直接可发 |
| 趋势变化（时间序列、增长率） | 数据图表（matplotlib 折线） | guizang 无折线图能力 |
| 占比分布（饼图、环形图） | 数据图表（matplotlib） | guizang 无饼图能力 |
| 多维度对比（雷达图、热力图） | 数据图表（matplotlib） | guizang 无此类图表 |
| TOP N 排名（横向条形图） | 社交卡片（Swiss H-Bar Chart） | 比 matplotlib 更精致 |

规划完成后形成配图清单草案（每张图的通道、位置、描述），再进入对应通道执行。

### 步骤 2：社交卡片通道（guizang）

适用于公众号封面图（21:9 + 1:1 封面对）和社交型数据卡片。使用 `/workspace/skills/guizang-social-card-skill` 渲染。

**前置依赖检查**：

```bash
# 检查 Node.js
node --version

# 检查 Playwright
npx playwright --version

# 检查 guizang skill 是否存在
ls /workspace/skills/guizang-social-card-skill/SKILL.md
```

若任一依赖缺失，降级至 AI 生成通道，并告知用户「社交卡片通道依赖 Node + Playwright，当前环境不满足，已降级为 AI 生成」。

**执行流程**：

1. **读取 guizang SKILL.md**：加载 `/workspace/skills/guizang-social-card-skill/SKILL.md` 获取完整工作流指引
2. **选择风格模式**：
   - **Swiss International**：适合数据/方法论/科技类文章（IKB 蓝 / 柠檬黄 / 柠檬绿 / 安全橙）
   - **Editorial Magazine**：适合行业解读/科普类文章（墨水经典 / 靛蓝瓷 / 森林墨 / 牛皮纸 / 沙丘 / 午夜墨）
3. **封面图（21:9 + 1:1 封面对）**：
   - 在项目 `images/` 目录下创建任务文件夹 `social-card-<slug>/`
   - 拷贝对应风格的种子模板（`template-swiss-card.html` 或 `template-editorial-card.html`）作为 `index.html`
   - 21:9 封面（2100×900）：使用文章完整标题 + 副标题 + 一个强视觉元素
   - 1:1 封面（1080×1080）：从长标题派生短标题（4-10 字），大字居中，默认无图
   - 参照 `references/title-shortener.md` 的 5 步法 + 4 模式派生短标题
   - **禁止**把 21:9 裁切成 1:1，必须分别构图
4. **社交型数据卡片**：
   - 选用 Swiss 风格（数据感强）
   - KPI 柱塔（S09）：4 列数字对比，`--h:Npx` 编码数值高度
   - 横向排名条形图（S10）：5-10 行排名，`--w:NN%` 编码占比
   - 账本行（S11）：大数字 + 标签 + 图标
   - 能力矩阵（S12）：8-12 格矩阵 + 底部汇总
   - 数据必须来自 `research.data_points`，不得编造
5. **渲染**：
   - 编写 `render.cjs` 脚本，使用 Playwright 逐个 `.poster` 节点截图
   - 等待字体和图片加载（至少 500-900ms，Editorial 的 WebGL 背景需更久）
   - 保存到 `output/` 目录
   - 可选：运行 `node validate-social-deck.mjs <task-dir>` 做质量校验（溢出/碰撞/字号/密度）
6. **输出**：
   - 封面图：`cover-21x9.png`（2100×900）+ `cover-1x1.png`（1080×1080）
   - 数据卡：`img-<序号>.png`
   - 将最终图片复制到项目 `images/` 目录

**guizang 通道输出规范**：

| 图片类型 | 尺寸 | 命名 |
|---------|------|------|
| 公众号主封面 | 2100×900 | `cover-21x9.png` |
| 公众号方形封面 | 1080×1080 | `cover-1x1.png` |
| 文中数据卡片 | 按版式定 | `img-<序号>.png` |

> 排版模块（模块6）使用 `cover-21x9.png` 作为封面占位符。`cover-1x1.png` 供公众号后台设置方形封面时手动上传。

### 步骤 3：AI 生成通道

适用于概念图/示意图、氛围图，以及社交卡片通道不可用时的封面降级。使用 `GenerateImage` 工具。

- **概念图/示意图**：将抽象概念（如「注意力机制」「知识蒸馏」）转为可视化意象
- **氛围图**：科技感插画，烘托段落基调，不喧宾夺主
- **封面降级**：社交卡片通道不可用时，用 AI 生成封面图

prompt 构造要求：
1. 写明用途与场景（如「公众号文章封面图：XX 主题」）
2. 指定风格（写实 / 插画 / 极简 / 3D 渲染）
3. 描述主体、构图、色调、氛围
4. 指定尺寸（封面建议 `landscape_16_9`，文中插图按内容定）

生成后保存到 `images/` 目录，统一命名：`cover.png`、`img-<序号>.png`。

### 步骤 4：截图通道

适用于产品展示类和技术演示类。本模块不直接截图，而是生成截图指引供用户/操作执行。

- **产品展示类截图指引**：截什么界面、重点突出什么功能、建议标注哪些区域
- **技术演示类截图规范**：所需环境/版本、操作步骤、截图范围、敏感信息脱敏要求

将指引写入该图的 `screenshot_guide` 字段，`status` 标记为 `skipped`（待用户提供），不阻塞流程。

### 步骤 5：数据图表通道

适用于分析型图表（趋势折线、分布饼图、多系列对比）。从 `research.data_points` 提取数据生成。

- **趋势折线图**：时间序列变化、增长率趋势
- **分布饼图/环形图**：占比分布
- **多系列对比柱状图**：多模型/多方案横向对比
- **能力雷达图**：多维度能力对比（如推理、代码、多模态、长文本）

使用 matplotlib 或类似库生成。数据来源必须可追溯到 `research.data_points` 中的具体条目，不得编造数据。图表需含标题、图例、数据来源标注。

> **注意**：若数据特征是"少数关键数字 + 强排名"，应优先走社交卡片通道（步骤2），而非本通道。本通道用于 guizang 无法覆盖的分析型图表。

### 步骤 6：图文匹配校验

逐张检查图片与对应段落内容是否契合：

- 图片内容是否准确反映段落主题
- 图片说明（caption）是否准确、简洁
- 图片位置是否在段落语义最贴合处
- 是否存在图文重复（图已说明的内容正文又长篇重复）

不契合的图片：AI 通道的重新生成；社交卡片通道的调整内容后重新渲染；其他通道的调整说明或标注待修。

### 步骤 7：图片管理

- 统一命名：`cover-21x9.png`、`cover-1x1.png`、`img-1.png`、`img-2.png`……按出现顺序编号
- 统一存储到 `/workspace/projects/<article_id>/images/`
- 公众号尺寸规格：
  - 封面图（社交卡片）：21:9 主封面 2100×900，1:1 方形封面 1080×1080
  - 封面图（AI 降级）：建议 16:9 或 2.35:1，宽度 ≥ 900px
  - 文中插图：宽度适配移动端，单图高度不过长
- 更新 `ArticleProject.images` 字段并持久化到 `article.json`

## 降级方案

| 失败点 | 自动降级 | 用户感知（三段式） |
|--------|---------|------------------|
| guizang 依赖缺失（Node/Playwright） | 封面降级为 AI 生成，数据卡降级为 matplotlib | 「社交卡片通道依赖 Node + Playwright，当前环境不满足，已降级处理」 |
| guizang 渲染失败 | 封面降级为 AI 生成，数据卡降级为 matplotlib | 「社交卡片渲染失败，已降级为其他通道」 |
| guizang Google Fonts 加载超时 | 重试一次，仍失败则降级为 AI 生成 | 「卡片字体加载超时，已降级为 AI 生成封面」 |
| AI 生成失败 | 文字占位 + 截图指引 | 「封面图生成失败，已留占位符，可手动上传」 |
| 用户未提供截图 | 跳过该标注位置，不阻塞 | 「产品截图需要你提供，已标注位置，不阻塞流程」 |
| 数据图表失败 | 降级为文字表格 | 「图表生成失败，已用文字表格替代」 |
| 数据点缺失 | 跳过该图表，标注待补 | 「XX 数据缺失，已跳过该图，发布前可补」 |

降级后的图片 `status` 必须标记为 `placeholder` 或 `skipped`，并在 `placeholder_reason` 写明原因，便于后续模块（排版、发布前清单）识别处理。

## 注意事项

1. **四通道混合优先级**：封面图优先社交卡片（设计感最强），分析型数据图走 matplotlib（能力最全），抽象/氛围类走 AI 生成，真实界面走截图。避免用 AI 图伪装真实截图误导读者
2. **社交卡片是封面首选**：guizang 的封面质量远超 AI 直出（文字是真实 HTML 渲染，不会乱码；内置质量校验），只要环境支持就应首选
3. **AI 生成图需明确标注**：文中如使用 AI 生成的示意图/概念图，应在 caption 注明「示意图」性质，不冒充真实产品界面或数据
4. **数据图表不可编造**：所有数据必须来自 `research.data_points`，缺失则降级或跳过，绝不凭印象补数。社交卡片通道的数据同样适用此规则
5. **截图涉敏脱敏**：截图指引需提示脱敏 API key、账号、内部系统名等信息
6. **版权与风格一致**：全篇配图风格尽量统一。社交卡片通道在一篇文章内只选一种风格模式（Swiss 或 Editorial），不混用
7. **失败不阻塞**：任一图片失败都走降级，不允许因配图问题中断整体流程
8. **图片说明不可省**：每张文中插图都应有 caption，既是图文匹配校验产物，也提升可读性
9. **排版前校验 images 字段**：若 `ArticleProject.images` 为空对象或不存在，排版模块应走全降级路径（纯文字排版），不因配图缺失中断
10. **guizang 任务文件夹清理**：社交卡片渲染产生的 `social-card-<slug>/` 任务文件夹（含 index.html、render.cjs）属于中间产物，渲染完成后应将最终 PNG 复制到 `images/` 并可清理任务文件夹，避免项目目录膨胀
