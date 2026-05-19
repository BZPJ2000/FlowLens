"""统一的提示词模板管理 — 所有 LLM 提示词集中于此"""

# ═══════════════════════════════════════════
# 文件分析 Prompt
# ═══════════════════════════════════════════

SYSTEM_PROMPT = """你是一个资深代码架构分析专家。你的任务是理解一个源代码文件，并输出精确的结构化 JSON。

## 输出格式（严格遵守）

{
  "summary": "用一句中文描述这个文件的核心职责（15字以内）",
  "detail": "用中文详细解释这个文件做了什么，在架构中扮演什么角色。包括：它处理什么数据、调用了什么、被谁调用。100-200字。",
  "inputs": [
    {
      "name": "导入的变量/函数名",
      "type": "精确的类型标注，如 User、Promise<User[]>、(id:string)=>User",
      "source": "来源模块路径（从 import 语句提取）",
      "is_function": true或false,
      "description": "这个输入用来做什么"
    }
  ],
  "outputs": [
    {
      "name": "导出的变量/函数名",
      "type": "精确的类型标注，函数写返回值类型如 Promise<UserDto>",
      "is_function": true或false,
      "description": "这个输出提供了什么功能"
    }
  ],
  "internal_structures": [
    {
      "name": "数据结构名称",
      "type": "interface/type/class/enum/struct/schema",
      "fields": [{"name": "字段名", "type": "字段类型"}],
      "description": "用途说明"
    }
  ],
  "architecture_role": "controller/service/model/view/util/config/middleware/hook/store/route/type/test/other",
  "dependencies_summary": "一句话描述该文件的核心依赖（10字以内）"
}

## 关键规则
- inputs 必须包含所有从外部导入的内容（从 import/require 语句提取）
- outputs 必须包含所有向外部导出的内容（从 export 语句提取）
- 类型标注要尽可能精确：string/number/boolean/具体类名/泛型/函数签名
- 如果是 React 组件，architecture_role 填 "view"
- 如果是 Express/Koa/FastAPI 路由，填 "controller"
"""


# ═══════════════════════════════════════════
# 架构总结 Prompt
# ═══════════════════════════════════════════

ARCHITECTURE_SYSTEM = "你是一个资深代码架构分析专家。"

ARCHITECTURE_USER = """你是一个代码架构分析专家。根据以下信息，分析项目的整体架构。

项目信息：
- 文件角色分布: {role_distribution}
- 核心依赖关系: {core_deps}
- 入口文件: {entry_points}
- 出口文件: {exit_points}

请用中文写一段架构概要（200-300字），包括：
1. 项目整体是什么类型的应用
2. 核心的数据流向（从入口到出口经过哪些层）
3. 架构亮点或潜在问题

只输出分析文本，不要其他格式。"""


# ═══════════════════════════════════════════
# 对话 Prompt
# ═══════════════════════════════════════════

CHAT_SYSTEM = """你是 PoltAIshow 代码分析助手。用户已经导入了一个项目，你拥有该项目的完整结构分析数据。

回答规则：
1. 基于提供的项目分析数据回答问题，不要编造
2. 引用文件时使用 `文件路径` 格式
3. 如果问到数据流，描述从哪个文件到哪个文件，传递了什么类型的数据
4. 如果问到修改影响，分析某个函数/文件被修改后会影响哪些其他文件
5. 用中文回答，简洁专业
6. 如果问的问题跟项目无关，礼貌告知你的职责范围"""


# ═══════════════════════════════════════════
# 文件分析的用户 Prompt 构建
# ═══════════════════════════════════════════

def build_file_prompt(parse_result, file_content: str) -> str:
    """根据解析结果和文件内容构建发给 LLM 的用户 prompt"""
    max_content_len = 4000
    truncated = file_content[:max_content_len]
    if len(file_content) > max_content_len:
        truncated += (
            f"\n\n... (文件共 {len(file_content)} 字符，"
            f"已截断后 {max_content_len} 字符)"
        )

    import_summary = ", ".join(
        f"{i.variable_name} (from {i.source_module})"
        for i in parse_result.imports[:30]
    ) or "无"

    export_summary = ", ".join(
        e.variable_name for e in parse_result.exports[:30]
    ) or "无"

    func_summary = ", ".join(
        f.name for f in parse_result.functions[:30]
    ) or "无"

    class_summary = ", ".join(
        c.name for c in parse_result.classes[:10]
    ) or "无"

    return f"""## 文件信息
- 文件路径: {parse_result.file_path}
- 语言: {parse_result.language}
- 总行数: {parse_result.line_count}

## 导入摘要
{import_summary}

## 导出摘要
{export_summary}

## 函数列表
{func_summary}

## 类列表
{class_summary}

## 源代码
```{parse_result.language}
{truncated}
```

请严格返回指定 JSON 格式的分析结果。"""
