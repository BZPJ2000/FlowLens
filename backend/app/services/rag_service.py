"""RAG 服务 — 智能上下文检索和对话管理

核心策略:
1. 关键词提取: 从用户问题中提取关键概念
2. 相关性排序: 根据关键词匹配度、角色重要性、连接数量对文件排序
3. 上下文构建: 取最相关的文件，组装结构化的 prompt 上下文
4. 窗口优化: 控制 token 预算，优先放最重要的信息
"""

import json
import re
from collections import defaultdict
from typing import Optional


class RAGService:
    """基于项目分析数据的智能检索增强生成服务"""

    # 角色重要性权重（越重要的角色优先出现在上下文中）
    ROLE_WEIGHTS = {
        "controller": 10,
        "route": 9,
        "service": 8,
        "model": 7,
        "store": 6,
        "middleware": 6,
        "hook": 5,
        "view": 5,
        "type": 4,
        "util": 3,
        "config": 3,
        "test": 2,
        "other": 1,
    }

    # 中文关键词 → 架构角色映射
    KEYWORD_ROLE_MAP = {
        "路由|router|route|handler|controller|控制器|请求|http|api|endpoint": "controller",
        "服务|service|业务|逻辑|biz|logic|domain": "service",
        "模型|model|schema|entity|数据模型|数据库|database|orm|dto": "model",
        "组件|component|view|页面|page|ui|渲染|render|jsx|tsx|模板": "view",
        "工具|util|helper|工具函数|辅助|lib|common": "util",
        "配置|config|setting|环境|env|环境变量": "config",
        "中间件|middleware|拦截|interceptor|auth|认证|鉴权|权限": "middleware",
        "状态|store|state|redux|zustand|pinia|vuex|管理": "store",
        "类型|type|interface|接口|泛型|generic|enum": "type",
        "测试|test|spec|单元测试|e2e|集成测试": "test",
        "钩子|hook|effect|use[A-Z]|composable": "hook",
    }

    def extract_keywords(self, query: str) -> list[str]:
        """从查询中提取关键词"""
        keywords: list[str] = []

        # 1. 提取引号中的精确短语
        quoted = re.findall(r'["\'`]([^"\'`]+)["\'`]', query)
        keywords.extend(quoted)

        # 2. 提取文件路径模式 (如 src/xxx, @/xxx, ./xxx)
        paths = re.findall(r'[\w@./-]+\.\w{2,5}', query)
        keywords.extend(paths)

        # 3. 提取 CamelCase/PascalCase/snake_case 标识符
        identifiers = re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b', query)
        keywords.extend(identifiers)
        snake_cases = re.findall(r'\b[a-z]+(?:_[a-z]+)+\b', query)
        keywords.extend(snake_cases)

        # 4. 提取中文关键词（2-4 字）
        chinese_words = re.findall(r'[\u4e00-\u9fff]{2,4}', query)
        keywords.extend(chinese_words)

        # 5. 提取英文单词（≥3 字母，排除常见停用词）
        stops = {
            "the", "and", "for", "are", "but", "not", "you", "all",
            "can", "had", "her", "was", "one", "our", "out", "has",
            "have", "how", "its", "may", "new", "old", "see", "she",
            "that", "this", "with", "what", "when", "where", "which",
            "who", "will", "from", "does", "did", "been", "being",
            "they", "them", "then", "than", "some", "such", "just",
            "like", "make", "made", "more", "much", "must", "only",
            "over", "said", "same", "into", "also", "very", "well",
        }
        words = re.findall(r'\b[a-zA-Z]{3,}\b', query.lower())
        keywords.extend(w for w in words if w not in stops)

        # 去重保序
        seen = set()
        result = []
        for k in keywords:
            kl = k.lower()
            if kl not in seen and len(k) >= 2:
                seen.add(kl)
                result.append(k)
        return result

    def score_files(
        self,
        query: str,
        nodes_data: list[dict],
        edge_data: list[dict],
        keywords: list[str] | None = None,
    ) -> list[dict]:
        """对文件按相关性打分排序

        每个 node_dict 应包含:
        - id, file_path, file_name, summary, detail
        - imports_json, exports_json (optional)
        - architecture_role (optional)
        """
        if keywords is None:
            keywords = self.extract_keywords(query)

        # 建立邻居索引（用于传播相关性）
        neighbors: dict[str, set[str]] = defaultdict(set)
        for e in edge_data:
            src = e.get("source_node_id") or e.get("from_file_id")
            tgt = e.get("target_node_id") or e.get("to_file_id")
            if src and tgt:
                src_str = str(src)
                tgt_str = str(tgt)
                neighbors[src_str].add(tgt_str)
                neighbors[tgt_str].add(src_str)

        scored = []
        for node in nodes_data:
            score = 0.0
            nid = str(node.get("id", ""))
            file_path = node.get("file_path", "")
            file_name = node.get("file_name", "")
            summary = node.get("summary", "")
            detail = node.get("detail", "")
            role = node.get("architecture_role", "other")

            # 合并文本
            text = f"{file_path} {file_name} {summary} {detail}".lower()

            # 关键词匹配
            for kw in keywords:
                kwl = kw.lower()
                # 精确匹配
                count = text.count(kwl)
                if count > 0:
                    score += 3.0 * count
                # 部分匹配（关键词包含在文本中）
                elif kwl in text:
                    score += 1.5

            # 角色权重
            score += self.ROLE_WEIGHTS.get(role, 1)

            # 连接度权重（被依赖多的文件更值得展示）
            conn_count = len(neighbors.get(nid, set()))
            score += min(conn_count * 0.5, 5.0)

            # 角色匹配加权（问题中提到了特定角色类型）
            for pattern, target_role in self.KEYWORD_ROLE_MAP.items():
                if re.search(pattern, query, re.IGNORECASE) and role == target_role:
                    score += 5.0

            # 检查 imports/exports 中是否有匹配
            imports_json = node.get("imports_json") or node.get("inputs") or []
            exports_json = node.get("exports_json") or node.get("outputs") or []
            for imp in imports_json:
                name = imp.get("name", "") if isinstance(imp, dict) else getattr(imp, "name", "")
                for kw in keywords:
                    if kw.lower() in str(name).lower():
                        score += 2.0
            for exp in exports_json:
                name = exp.get("name", "") if isinstance(exp, dict) else getattr(exp, "name", "")
                for kw in keywords:
                    if kw.lower() in str(name).lower():
                        score += 2.0

            scored.append({**node, "_score": score})

        scored.sort(key=lambda x: x["_score"], reverse=True)
        return scored

    def build_context(
        self,
        query: str,
        nodes_data: list[dict],
        edge_data: list[dict],
        max_files: int = 30,
        max_chars: int = 8000,
    ) -> str:
        """构建结构化的 RAG 上下文

        返回针对用户问题的精炼上下文文本，控制在 token 预算内。
        """
        keywords = self.extract_keywords(query)
        scored = self.score_files(query, nodes_data, edge_data, keywords)

        # 建立邻居索引
        neighbors: dict[str, set[str]] = defaultdict(set)
        for e in edge_data:
            src = str(e.get("source_node_id") or e.get("from_file_id") or "")
            tgt = str(e.get("target_node_id") or e.get("to_file_id") or "")
            if src and tgt:
                neighbors[src].add(tgt)
                neighbors[tgt].add(src)

        parts: list[str] = []
        used_ids: set[str] = set()
        total_chars = 0

        # 先放最相关文件
        for node in scored:
            if len(used_ids) >= max_files or total_chars >= max_chars:
                break

            nid = str(node.get("id", ""))
            if nid in used_ids:
                continue
            used_ids.add(nid)

            file_path = node.get("file_path", "")
            summary = node.get("summary", "")
            detail = node.get("detail", "")
            role = node.get("architecture_role", "")

            # 构建单文件摘要
            block = f"**{file_path}**"
            if role:
                block += f" [{role}]"
            block += f"\n  {summary}"
            if detail:
                # 截断 detail
                short_detail = detail[:200] + "..." if len(detail) > 200 else detail
                block += f"\n  {short_detail}"

            # 输入输出摘要
            imports_json = node.get("imports_json") or node.get("inputs") or []
            exports_json = node.get("exports_json") or node.get("outputs") or []

            key_imports = []
            for imp in imports_json[:5]:
                name = imp.get("name", "") if isinstance(imp, dict) else getattr(imp, "name", "")
                dtype = imp.get("type", "") if isinstance(imp, dict) else getattr(imp, "type", "")
                if name:
                    key_imports.append(f"{name}:{dtype}" if dtype else name)

            key_exports = []
            for exp in exports_json[:5]:
                name = exp.get("name", "") if isinstance(exp, dict) else getattr(exp, "name", "")
                dtype = exp.get("type", "") if isinstance(exp, dict) else getattr(exp, "type", "")
                if name:
                    key_exports.append(f"{name}:{dtype}" if dtype else name)

            if key_imports:
                block += f"\n  输入: {', '.join(key_imports)}"
            if key_exports:
                block += f"\n  输出: {', '.join(key_exports)}"

            # 相关文件
            nbrs = neighbors.get(nid, set())
            if nbrs:
                nbr_names = []
                for n in scored:
                    if str(n.get("id", "")) in nbrs and len(nbr_names) < 3:
                        nbr_names.append(n.get("file_name", ""))
                if nbr_names:
                    block += f"\n  关联: {', '.join(nbr_names)}"

            if total_chars + len(block) > max_chars:
                # 如果加上会超限，做截断
                remaining = max_chars - total_chars - 3
                if remaining > 50:
                    block = block[:remaining] + "..."
                else:
                    break

            parts.append(block)
            total_chars += len(block) + 2

        # 如果没有找到相关文件
        if not parts:
            # 放前几个文件作为默认上下文
            for node in nodes_data[:10]:
                file_path = node.get("file_path", "")
                summary = node.get("summary", "")
                parts.append(f"**{file_path}**\n  {summary}")
            total_chars = sum(len(p) for p in parts)

        # 组装最终上下文
        entry_info = ""
        exit_info = ""

        # 提取全局入口出口信息
        all_entry_ids = set()
        all_exit_ids = set()
        for e in edge_data:
            src = str(e.get("source_node_id") or e.get("from_file_id") or "")
            tgt = str(e.get("target_node_id") or e.get("to_file_id") or "")
            if src:
                all_entry_ids.add(src)
            if tgt:
                all_exit_ids.add(tgt)

        if all_entry_ids or all_exit_ids:
            entry_files = [
                n.get("file_name", "") for n in nodes_data
                if str(n.get("id", "")) in all_entry_ids
            ][:5]
            exit_files = [
                n.get("file_name", "") for n in nodes_data
                if str(n.get("id", "")) in all_exit_ids
            ][:5]
            if entry_files:
                entry_info = f"入口文件: {', '.join(entry_files)}"
            if exit_files:
                exit_info = f"出口文件: {', '.join(exit_files)}"

        header = (
            f"项目共 {len(nodes_data)} 个文件，{len(edge_data)} 条数据流连接。\n"
        )
        if entry_info:
            header += f"{entry_info}\n"
        if exit_info:
            header += f"{exit_info}\n"

        context = header + "\n---\n" + "\n\n".join(parts)

        # 添加查询相关提示
        context += (
            f"\n\n---\n"
            f"用户问题关键词: {', '.join(keywords[:10])}\n"
            f"以上是该项目中最相关的 {len(parts)} 个文件的信息，"
            f"请基于这些信息回答用户问题。"
        )

        return context


# 单例
rag_service = RAGService()
