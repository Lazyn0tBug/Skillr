# Skillr

---

### 🔄  6 步需求 → MVP 实现映射

| 步骤 | Skillr 实现方式 | 交付物 |
|:---|:---|:---|
| 1. 形态为 Skill，含 `/SkillrScan` 和 `/Skillr` | 作为宿主 Agent 的插件/Skill 注册，暴露两个 Slash 命令 | `skill.yaml` + 命令路由入口 |
| 2. `/SkillrScan` 扫描生成本地 Skills 概览 | 遍历 `./skills/`，解析元数据，输出 `SKILR_INDEX.md`（人类可读）+ `skillr_index.json`（机器可读） | 静态索引文件 |
| 3. `/Skillr <任务>` 分析用户意图 | 调用一次轻量 LLM，输出结构化 `task_spec.json`（意图/约束/关键词） | 意图压缩结果 |
| 4. 根据意图匹配可用 Skills | 关键词匹配 + LLM 排序（Top 3~5），输出候选列表与匹配理由 | 候选清单 |
| 5. 交给用户选择 | Markdown 列表 + 编号选择，支持单/多选与顺序调整 | `selected_plan.json` |
| 6. 帮用户调用 Skill | 按选中顺序组装最终 Prompt/Context，触发宿主 Agent 原生工具调用机制 | 执行指令/计划 |

---

### 📦 极简数据契约（MVP 版，预留升级口）

#### 1. `skill.yaml`（每个 Skill 自带）
```yaml
id: code_gen
name: Python 代码生成器
description: 根据需求生成可运行脚本，含类型提示和单测
triggers: ["写代码", "生成脚本", "python", "自动化", "fastapi"]
input_contract: "自然语言需求，可指定语言/框架"
output_contract: "代码文件 + 可选测试文件"
prompt_template: "你是资深工程师。请根据以下需求生成代码：\n需求：{{task_intent}}\n约束：{{constraints}}"
```

#### 2. `skillr_index.json`（`/SkillrScan` 输出）
```json
[
  {
    "id": "code_gen",
    "name": "Python 代码生成器",
    "description": "根据需求生成可运行脚本，含类型提示和单测",
    "triggers": ["写代码", "生成脚本", "python", "自动化", "fastapi"],
    "file_path": "./skills/code_gen"
  }
]
```

#### 3. `task_spec.json`（`/Skillr` 意图分析输出）
```json
{
  "intent": "生成带 JWT 鉴权的 FastAPI 接口",
  "constraints": ["Python 3.10+", "Pydantic v2", "需含单元测试"],
  "keywords": ["fastapi", "jwt", "pydantic", "unittest", "python"]
}
```

---

### 🛠 两个命令的具体逻辑

#### 🔹 `/SkillrScan`
```python
# 伪代码逻辑
def scan_skills(skills_dir: str = "./skills"):
    index = []
    for folder in os.listdir(skills_dir):
        yaml_path = os.path.join(skills_dir, folder, "skill.yaml")
        if os.path.exists(yaml_path):
            meta = load_yaml(yaml_path)
            index.append({
                "id": meta["id"],
                "name": meta["name"],
                "description": meta["description"],
                "triggers": meta["triggers"],
                "file_path": f"./skills/{folder}"
            })
    save_json(index, "skillr_index.json")
    save_markdown(index, "SKILR_INDEX.md")  # 生成人类可读概览
    return f"✅ 扫描完成，共发现 {len(index)} 个 Skills。索引已更新至 skillr_index.json"
```
**迭代预留**：后续可替换为异步扫描、向量嵌入生成、或拉取远程 Skill Registry。

#### 🔹 `/Skillr <用户任务>`
```python
def route_and_select(user_prompt: str):
    # 1. 意图分析
    task_spec = llm_extract(f"从以下任务中提取意图、约束和关键词：{user_prompt}")
    
    # 2. 匹配 Skills
    index = load_json("skillr_index.json")
    candidates = hybrid_match(task_spec["keywords"], index, top_k=3)
    
    # 3. 展示并等待用户选择
    print(format_candidates_markdown(candidates))
    selection = input("请输入编号（如 1,2 或 1）：")
    selected_skills = parse_selection(selection, candidates)
    
    # 4. 组装执行计划
    plan = build_execution_plan(selected_skills, task_spec)
    
    # 5. 触发宿主调用（返回结构化指令）
    return {
        "action": "execute_skills",
        "plan": plan,
        "prompt_slices": assemble_prompts(plan, task_spec)
    }
```
**迭代预留**：匹配可升级为 BM25+向量混合；选择可升级为 TUI/GUI；执行可升级为 DAG 状态机。

---

### 🌱 预留的迭代扩展点（不破坏 MVP）

| 当前 MVP | 未来可平滑升级 | 升级方式 |
|:---|:---|:---|
| 关键词+LLM排序匹配 | 语义向量检索 + 查询重写 | 替换 `hybrid_match()`，加 `sentence-transformers` |
| Markdown 文本选择 | TUI 交互界面 | 引入 `prompt_toolkit`，不改数据流 |
| 线性顺序执行 | 依赖图/并行执行 | `plan` 结构增加 `depends_on` 字段，宿主解析 |
| 本地 JSON 索引 | 远程 Skill 市场 | `scan_skills()` 增加 `--remote` 参数拉取 |
| 直接返回 Prompt 切片 | 结构化 ExecutionManifest | 增加 `manifest_version` 字段，宿主适配 |

---

### 📁 MVP 目录结构（极简可运行）

```
skillr/
├── skill.yaml              # Skillr 自身元数据
├── commands/
│   ├── skillrscan.py        # /SkillrScan 实现
│   └── skillr.py            # /Skillr 实现
├── core/
│   ├── matcher.py          # 关键词+LLM 匹配逻辑
│   ├── assembler.py        # Prompt 切片与计划组装
│   └── utils.py            # YAML/JSON/Markdown 读写
├── skills/                 # 用户 Skills 存放目录
│   ├── code_gen/
│   │   └── skill.yaml
│   └── test_runner/
│       └── skill.yaml
├── skillr_index.json        # /SkillrScan 生成
├── SKILR_INDEX.md          # /SkillrScan 生成
└── README.md
```

---

### ✅ 下一步建议

这套设计完全贴合 6 步需求，**无过度抽象，所有复杂能力均预留了平滑升级路径**。建议按以下顺序启动：

1. **先写 `skill.yaml` 规范**（我可提供完整字段说明与校验逻辑）
2. **实现 `/SkillrScan`**（遍历目录 → 生成索引文件）
3. **实现 `/Skillr` 核心流**（意图提取 → 匹配 → 选择 → 组装）
4. **接入宿主 Agent**（将输出转为宿主可执行的 Tool Call / Prompt）

**你希望我先输出哪一部分的可运行代码？**
- 🔹 `skill.yaml` 规范 + 校验脚本
- 🔹 `/SkillrScan` 完整实现
- 🔹 `/Skillr` 意图分析+匹配+选择交互
- 🔹 宿主 Agent 适配示例（Claude Code / OpenClaw 等）

告诉我优先级，我们直接进代码阶段。
