# 模块 5：配图制作（Image Designer）

> 三通道混合配图：AI 生成 + 截图 + 数据图表。为初稿匹配视觉资产，输出可直接嵌入排版的图片文件清单。

## 模块职责

- 根据大纲配图标注，逐张判断最合适的配图通道（AI 生成 / 截图 / 数据图表）
- 生成封面图与文中插图，确保图片与段落内容契合
- 统一命名、存储图片文件，符合公众号尺寸规格
- 产出配图清单，写入 `ArticleProject.images` 字段

配图制作是全流程中「失败不阻塞」的典型环节：任何一张图缺失都不应卡住整体流程，应降级处理并明确标注。

## 输入

| 输入项 | 来源 | 说明 |
|--------|------|------|
| 大纲配图标注 | `ArticleProject.outline.sections[].image_type` | 每节的配图类型标注（ai_generated / screenshot / data_chart / none） |
| 配图描述 | `ArticleProject.outline.sections[].image_description` | 每节配图的内容描述与意图 |
| 初稿正文 | `ArticleProject.draft` | 用于图文匹配校验，确认图片与段落内容契合 |
| 调研数据点 | `ArticleProject.research.data_points` | 数据图表通道的数据来源（基准测试、能力对比、市场数据） |
| 文章类型 | `ArticleProject.topic.content_type` | 产品 / 技术 / 科普 / 行业解读，影响配图风格取向 |
| 项目 ID | `ArticleProject.id` | 决定图片存储路径 `/workspace/projects/<article_id>/images/` |

## 输出

写入 `ArticleProject.images` 字段，结构如下：

```json
{
  "cover": {
    "path": "/workspace/projects/<article_id>/images/cover.png",
    "channel": "ai_generated",
    "prompt": "封面图生成 prompt",
    "status": "success"
  },
  "inline": [
    {
      "id": "img-1",
      "section_index": 2,
      "channel": "ai_generated | screenshot | data_chart",
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

遍历大纲 `sections[]` 的配图标注，逐张判断使用哪个通道：

| 标注类型 | 推荐通道 | 说明 |
|---------|---------|------|
| `ai_generated`（封面图） | AI 生成 | 封面图，强调视觉冲击力 |
| `ai_generated`（概念图） | AI 生成 | 抽象概念可视化、示意图 |
| `ai_generated`（氛围图） | AI 生成 | 氛围图、科技感插画 |
| `screenshot`（产品展示类） | 截图通道 | 生成截图指引，需用户提供 |
| `screenshot`（技术演示类） | 截图通道 | 生成截图规范 |
| `data_chart` | 数据图表通道 | 从 `research.data_points` 提取数据生成 |
| `none` | 不配图 | 该节无需配图 |

规划完成后形成配图清单草案（每张图的通道、位置、描述），再进入对应通道执行。

### 步骤 2：AI 生成通道

适用于封面图、概念图/示意图、氛围图。使用 `GenerateImage` 工具。

- **封面图**：突出主题、视觉冲击力强，避免文字堆砌。prompt 需明确主体、风格、构图、色调
- **概念图/示意图**：将抽象概念（如「注意力机制」「知识蒸馏」）转为可视化意象
- **氛围图**：科技感插画，烘托段落基调，不喧宾夺主

prompt 构造要求：
1. 写明用途与场景（如「公众号文章封面图：XX 主题」）
2. 指定风格（写实 / 插画 / 极简 / 3D 渲染）
3. 描述主体、构图、色调、氛围
4. 指定尺寸（封面建议 `landscape_16_9`，文中插图按内容定）

生成后保存到 `images/` 目录，统一命名：`cover.png`、`img-<序号>.png`。

### 步骤 3：截图通道

适用于产品展示类和技术演示类。本模块不直接截图，而是生成截图指引供用户/操作执行。

- **产品展示类截图指引**：截什么界面、重点突出什么功能、建议标注哪些区域
- **技术演示类截图规范**：所需环境/版本、操作步骤、截图范围、敏感信息脱敏要求

将指引写入该图的 `screenshot_guide` 字段，`status` 标记为 `skipped`（待用户提供），不阻塞流程。

### 步骤 4：数据图表通道

适用于基准测试对比图、能力雷达图、市场数据图。从 `research.data_points` 提取数据生成。

- **基准测试对比图**：多模型/多方案横向对比，柱状图或折线图
- **能力雷达图**：多维度能力对比（如推理、代码、多模态、长文本）
- **市场数据图**：趋势线、占比饼图、增长率柱状图

数据来源必须可追溯到 `research.data_points` 中的具体条目，不得编造数据。图表需含标题、图例、数据来源标注。

### 步骤 5：图文匹配校验

逐张检查图片与对应段落内容是否契合：

- 图片内容是否准确反映段落主题
- 图片说明（caption）是否准确、简洁
- 图片位置是否在段落语义最贴合处
- 是否存在图文重复（图已说明的内容正文又长篇重复）

不契合的图片：AI 通道的重新生成；其他通道的调整说明或标注待修。

### 步骤 6：图片管理

- 统一命名：`cover.png`、`img-1.png`、`img-2.png`……按出现顺序编号
- 统一存储到 `/workspace/projects/<article_id>/images/`
- 公众号尺寸规格：
  - 封面图：建议 16:9 或 2.35:1，宽度 ≥ 900px
  - 文中插图：宽度适配移动端，单图高度不过长
- 更新 `ArticleProject.images` 字段并持久化到 `article.json`

## 降级方案

| 失败点 | 自动降级 | 用户感知（三段式） |
|--------|---------|------------------|
| AI 生成失败 | 文字占位 + 截图指引 | 「封面图生成失败，已留占位符，可手动上传」 |
| 用户未提供截图 | 跳过该标注位置，不阻塞 | 「产品截图需要你提供，已标注位置，不阻塞流程」 |
| 数据图表失败 | 降级为文字表格 | 「图表生成失败，已用文字表格替代」 |
| 数据点缺失 | 跳过该图表，标注待补 | 「XX 数据缺失，已跳过该图，发布前可补」 |

降级后的图片 `status` 必须标记为 `placeholder` 或 `skipped`，并在 `placeholder_reason` 写明原因，便于后续模块（排版、发布前清单）识别处理。

## 注意事项

1. **三通道混合优先级**：能精准呈现的优先截图/数据图表（真实可信），抽象或氛围类才用 AI 生成，避免用 AI 图伪装真实截图误导读者
2. **AI 生成图需明确标注**：文中如使用 AI 生成的示意图/概念图，应在 caption 注明「示意图」性质，不冒充真实产品界面或数据
3. **数据图表不可编造**：所有数据必须来自 `research.data_points`，缺失则降级或跳过，绝不凭印象补数
4. **截图涉敏脱敏**：截图指引需提示脱敏 API key、账号、内部系统名等信息
5. **版权与风格一致**：全篇配图风格尽量统一，AI 生成图避免出现明显版权 logo 或特定品牌标识
6. **失败不阻塞**：任一图片失败都走降级，不允许因配图问题中断整体流程
7. **图片说明不可省**：每张文中插图都应有 caption，既是图文匹配校验产物，也提升可读性
8. **排版前校验 images 字段**：若 `ArticleProject.images` 为空对象或不存在，排版模块应走全降级路径（纯文字排版），不因配图缺失中断
