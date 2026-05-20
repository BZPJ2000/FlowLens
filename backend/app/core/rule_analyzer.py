"""规则分析器 — 纯启发式地将 ParseResult 转换为 AIFileAnalysis，零 LLM 调用

取代逐文件 AI 分析步骤。基于文件名、目录路径、导入导出模式分类架构角色。
"""

import re
from pathlib import Path

from app.models.schemas import AIFileAnalysis, AIInputOutput, ParseResult


# 文件名关键词 → 架构角色
_FILENAME_ROLE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(controller|handler|\broute\b)", re.I), "controller"),
    (re.compile(r"(service|biz|logic|domain)", re.I), "service"),
    (re.compile(r"(model|entity|schema|dto|vo|pojo|dao|repository)", re.I), "model"),
    (re.compile(r"(util|helper|lib|common|tool)", re.I), "util"),
    (re.compile(r"(config|setting|env|option|constant)", re.I), "config"),
    (re.compile(r"(middleware|interceptor|filter|guard)", re.I), "middleware"),
    (re.compile(r"(hook|composable)", re.I), "hook"),
    (re.compile(r"(store|atom|state|redux|zustand|pinia|vuex|recoil)", re.I), "store"),
    (re.compile(r"(test|spec|__test__|\.test\.|\.spec\.)", re.I), "test"),
    (re.compile(r"(type|interface|enum|typedef)", re.I), "type"),
    (re.compile(r"(route|router)", re.I), "route"),
    (re.compile(r"(view|component|page|layout|template)", re.I), "view"),
]

# 目录路径关键词 → 架构角色（按优先级）
_DIR_ROLE_RULES: list[tuple[str, str]] = [
    ("/controllers/", "controller"),
    ("/controller/", "controller"),
    ("/handlers/", "controller"),
    ("/handler/", "controller"),
    ("/routes/", "route"),
    ("/services/", "service"),
    ("/service/", "service"),
    ("/models/", "model"),
    ("/model/", "model"),
    ("/entities/", "model"),
    ("/entity/", "model"),
    ("/schemas/", "model"),
    ("/schema/", "model"),
    ("/dtos/", "model"),
    ("/dto/", "model"),
    ("/dao/", "model"),
    ("/repositories/", "model"),
    ("/repository/", "model"),
    ("/views/", "view"),
    ("/view/", "view"),
    ("/components/", "view"),
    ("/component/", "view"),
    ("/pages/", "view"),
    ("/page/", "view"),
    ("/layouts/", "view"),
    ("/layout/", "view"),
    ("/utils/", "util"),
    ("/util/", "util"),
    ("/helpers/", "util"),
    ("/helper/", "util"),
    ("/lib/", "util"),
    ("/common/", "util"),
    ("/config/", "config"),
    ("/configs/", "config"),
    ("/settings/", "config"),
    ("/constants/", "config"),
    ("/middleware/", "middleware"),
    ("/middlewares/", "middleware"),
    ("/interceptors/", "middleware"),
    ("/interceptor/", "middleware"),
    ("/hooks/", "hook"),
    ("/hook/", "hook"),
    ("/composables/", "hook"),
    ("/store/", "store"),
    ("/stores/", "store"),
    ("/state/", "store"),
    ("/types/", "type"),
    ("/type/", "type"),
    ("/interfaces/", "type"),
    ("/interface/", "type"),
    ("/enums/", "type"),
    ("/tests/", "test"),
    ("/test/", "test"),
    ("/__tests__/", "test"),
    ("/spec/", "test"),
    ("/__mocks__/", "test"),
]


class RuleAnalyzer:
    """纯规则分析：ParseResult → AIFileAnalysis，零 token 消耗"""

    def analyze(self, parse_result: ParseResult) -> AIFileAnalysis:
        role = self._classify_role(parse_result.file_path)
        return AIFileAnalysis(
            file_path=parse_result.file_path,
            summary=self._build_summary(parse_result),
            detail=self._build_detail(parse_result),
            inputs=self._map_inputs(parse_result),
            outputs=self._map_outputs(parse_result),
            architecture_role=role,
            dependencies_summary=self._build_deps_summary(parse_result, role),
        )

    def analyze_batch(self, parse_results: list[ParseResult]) -> list[AIFileAnalysis]:
        return [self.analyze(pr) for pr in parse_results]

    # ── 架构角色分类 ───────────────────────────

    # useXxx 钩子模式必须区分大小写，单独编译（无 re.I，只匹配原始文件名）
    _HOOK_PREFIX = re.compile(r"use[A-Z]")

    def _classify_role(self, file_path: str) -> str:
        """基于文件名和目录路径的启发式角色分类"""
        normalized = file_path.replace("\\", "/").lower()
        file_name = Path(normalized).name
        raw_file_name = Path(file_path.replace("\\", "/")).name

        # 1. 先查目录路径（更可靠）
        for dir_keyword, role in _DIR_ROLE_RULES:
            if dir_keyword in f"/{normalized}":
                return role

        # 2. useXxx 钩子模式：必须保留大小写，否则 userAtom 这类文件名会被误判
        if self._HOOK_PREFIX.search(raw_file_name):
            return "hook"

        # 3. 其余文件名模式（大小写不敏感，兼容小写后的 file_name）
        for pattern, role in _FILENAME_ROLE_PATTERNS:
            if pattern.search(file_name):
                return role

        return "other"

    # ── 摘要生成 ───────────────────────────────

    def _build_summary(self, pr: ParseResult) -> str:
        parts: list[str] = []

        funcs = pr.functions
        if funcs:
            names = [f.name for f in funcs[:3]]
            suffix = f" 等" if len(funcs) > 3 else ""
            parts.append(f"{len(funcs)}个函数({', '.join(names)}{suffix})")

        classes = pr.classes
        if classes:
            names = [c.name for c in classes[:3]]
            suffix = f" 等" if len(classes) > 3 else ""
            parts.append(f"{len(classes)}个类({', '.join(names)}{suffix})")

        if parts:
            return ", ".join(parts)
        return f"{pr.language} 源码文件"

    # ── 详情生成 ───────────────────────────────

    def _build_detail(self, pr: ParseResult) -> str:
        parts = [f"该文件导入了 {len(pr.imports)} 个外部依赖"]

        if pr.exports:
            exported_names = [e.variable_name for e in pr.exports[:5]]
            suffix = " 等" if len(pr.exports) > 5 else ""
            parts.append(f"导出了 {len(pr.exports)} 个符号({', '.join(exported_names)}{suffix})")

        parts.append(f"包含 {len(pr.functions)} 个函数和 {len(pr.classes)} 个类")

        if pr.line_count > 0:
            parts.append(f"共 {pr.line_count} 行代码")

        return "，".join(parts) + "。"

    # ── 输入输出映射 ───────────────────────────

    def _map_inputs(self, pr: ParseResult) -> list[AIInputOutput]:
        return [
            AIInputOutput(
                name=imp.variable_name,
                type=imp.data_type,
                source=imp.source_module,
            )
            for imp in pr.imports
        ]

    def _map_outputs(self, pr: ParseResult) -> list[AIInputOutput]:
        return [
            AIInputOutput(
                name=exp.variable_name,
                type=exp.data_type,
                is_function=exp.is_function,
            )
            for exp in pr.exports
        ]

    # ── 依赖摘要 ───────────────────────────────

    def _build_deps_summary(self, pr: ParseResult, role: str) -> str:
        """生成一句话依赖描述"""
        if not pr.imports:
            return "无外部依赖"

        module_sources = set()
        for imp in pr.imports:
            if imp.source_module and not imp.source_module.startswith("."):
                # 提取包名（取前两级）
                parts = imp.source_module.replace("@", "").split("/")
                if parts:
                    module_sources.add(parts[0])

        count = len(pr.imports)
        if module_sources:
            sources_str = "、".join(sorted(module_sources)[:5])
            return f"依赖了 {count} 个外部模块（{sources_str} 等）"
        return f"依赖了 {count} 个模块（主要是项目内部模块）"


# 单例
rule_analyzer = RuleAnalyzer()
