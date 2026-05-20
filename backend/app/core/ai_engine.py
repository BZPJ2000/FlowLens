"""AI 分析引擎 — LLM 驱动的代码理解，三层压缩策略"""

import json
import re
import asyncio
from typing import Optional

from app.config import settings
from app.models.schemas import AIFileAnalysis, AIInputOutput, ParseResult
from app.core.prompts import (
    SYSTEM_PROMPT,
    ARCHITECTURE_SYSTEM,
    ARCHITECTURE_USER,
    CHAT_SYSTEM,
    build_file_prompt,
)


class AIAnalysisEngine:

    def __init__(self, api_key: str = "", model: str = "", base_url: str = ""):
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model
        self.base_url = base_url or settings.llm_base_url

    # ── 文件分析 ───────────────────────────────

    async def analyze_file(
        self,
        parse_result: ParseResult,
        file_content: str,
        max_retries: int = 2,
    ) -> AIFileAnalysis:
        prompt = build_file_prompt(parse_result, file_content)
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                raw = await self._call_llm(
                    system=SYSTEM_PROMPT,
                    user=prompt,
                    temperature=0.15,
                    max_tokens=2000,
                )
                return self._parse_response(raw, parse_result.file_path)
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    await asyncio.sleep(1 * (attempt + 1))

        print(f"[AIEngine] 分析 {parse_result.file_path} 失败: {last_error}，使用降级分析")
        return self._fallback_analysis(parse_result)

    # ── 批量分析 ───────────────────────────────

    async def analyze_batch(
        self,
        file_data: list[tuple[ParseResult, str]],
        concurrency: int = 3,
        progress_callback=None,
    ) -> list[AIFileAnalysis]:
        sem = asyncio.Semaphore(concurrency)
        results: list[Optional[AIFileAnalysis]] = [None] * len(file_data)
        completed = 0
        total = len(file_data)
        lock = asyncio.Lock()

        async def _do(i: int, pr: ParseResult, content: str):
            nonlocal completed
            async with sem:
                result = await self.analyze_file(pr, content)
            async with lock:
                results[i] = result
                completed += 1
                if progress_callback:
                    await progress_callback(completed, total, pr.file_path)

        async def _do_safe(i: int, pr: ParseResult, content: str):
            nonlocal completed
            async with sem:
                try:
                    result = await self.analyze_file(pr, content)
                except Exception:
                    result = self._fallback_analysis(pr)
            async with lock:
                results[i] = result
                completed += 1
                if progress_callback:
                    await progress_callback(completed, total, pr.file_path)

        tasks = [_do_safe(i, pr, c) for i, (pr, c) in enumerate(file_data)]
        await asyncio.gather(*tasks, return_exceptions=True)

        return [r for r in results if r is not None and not isinstance(r, Exception)]

    # ── 架构总结 ───────────────────────────────

    async def generate_architecture_summary(
        self,
        role_distribution: dict,
        core_deps: list[dict],
        entry_points: list[str],
        exit_points: list[str],
    ) -> str:
        prompt = ARCHITECTURE_USER.format(
            role_distribution=json.dumps(role_distribution, ensure_ascii=False),
            core_deps=json.dumps(core_deps[:20], ensure_ascii=False),
            entry_points=json.dumps(entry_points[:10], ensure_ascii=False),
            exit_points=json.dumps(exit_points[:10], ensure_ascii=False),
        )
        try:
            return await self._call_llm(
                system=ARCHITECTURE_SYSTEM,
                user=prompt,
                temperature=0.3,
                max_tokens=500,
            )
        except Exception:
            return "该项目采用分层架构，数据从入口文件流入，经过业务逻辑层处理后输出。"

    # ── 对话 ───────────────────────────────────

    async def chat(
        self, user_message: str, context: str, chat_history: list[dict]
    ) -> str:
        messages = [{"role": "system", "content": CHAT_SYSTEM}]
        messages.extend(chat_history[-10:])
        messages.append({
            "role": "user",
            "content": (
                f"## 项目结构分析数据\n\n{context}\n\n"
                f"## 用户问题\n{user_message}\n\n请基于项目数据回答。"
            ),
        })
        try:
            return await self._call_llm_raw(messages, temperature=0.4, max_tokens=1500)
        except Exception:
            return "AI 服务暂时不可用。请检查 API Key 配置，或在 backend/.env 中设置 LLM_API_KEY。"

    # ── LLM 调用 ───────────────────────────────

    async def _call_llm(
        self,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        return await self._call_llm_raw(messages, temperature, max_tokens)

    async def _call_llm_raw(
        self, messages: list[dict], temperature: float, max_tokens: int
    ) -> str:
        import litellm

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": 120,  # per-call timeout (seconds)
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.base_url:
            kwargs["api_base"] = self.base_url

        response = await litellm.acompletion(**kwargs)
        content = response.choices[0].message.content or ""
        return content

    async def _call_llm_stream(
        self, messages: list[dict], temperature: float = 0.4, max_tokens: int = 1500
    ):
        """流式调用 LLM，返回 async generator，逐 token yield SSE 数据行"""
        import litellm

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": 120,
            "stream": True,
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.base_url:
            kwargs["api_base"] = self.base_url

        try:
            response = await litellm.acompletion(**kwargs)
            async for chunk in response:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield f"data: {json.dumps({'type': 'chunk', 'delta': delta.content})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    async def stream_chat(
        self, user_message: str, context: str, chat_history: list[dict]
    ):
        """流式对话接口 — 返回 async generator，逐 token 产生 SSE 事件"""
        messages = [{"role": "system", "content": CHAT_SYSTEM}]
        messages.extend(chat_history[-10:])
        messages.append({
            "role": "user",
            "content": (
                f"## 项目结构分析数据\n\n{context}\n\n"
                f"## 用户问题\n{user_message}\n\n请基于项目数据回答。"
            ),
        })
        async for sse_data in self._call_llm_stream(messages, temperature=0.4, max_tokens=1500):
            yield sse_data

    # ── 响应解析 ───────────────────────────────

    def _parse_response(self, raw: str, file_path: str) -> AIFileAnalysis:
        json_str = raw
        # 提取 markdown 代码块
        if "```json" in raw:
            m = re.search(r"```json\s*([\s\S]*?)\s*```", raw)
            if m:
                json_str = m.group(1)
        elif "```" in raw:
            m = re.search(r"```\s*([\s\S]*?)\s*```", raw)
            if m:
                json_str = m.group(1)

        # 找到第一个完整 JSON 对象
        json_match = re.search(r"\{[\s\S]*\}", json_str)
        if not json_match:
            return AIFileAnalysis(file_path=file_path, summary="AI 响应格式错误")

        try:
            data = json.loads(json_match.group(0))
        except json.JSONDecodeError:
            try:
                cleaned = re.sub(r",\s*}", "}", json_match.group(0))
                cleaned = re.sub(r",\s*]", "]", cleaned)
                data = json.loads(cleaned)
            except json.JSONDecodeError:
                return AIFileAnalysis(file_path=file_path, summary="JSON 解析失败")

        # 防御性提取：LLM 可能返回 "inputs": null 而不是 "inputs": []
        # dict.get(k, default) 只在 key 缺失时使用 default，key 存在但值为 None 时返回 None
        raw_inputs = data.get("inputs") or []
        raw_outputs = data.get("outputs") or []
        raw_structures = data.get("internal_structures") or []

        return AIFileAnalysis(
            file_path=file_path,
            summary=str(data.get("summary") or ""),
            detail=str(data.get("detail") or ""),
            inputs=[AIInputOutput(**i) for i in raw_inputs],
            outputs=[AIInputOutput(**o) for o in raw_outputs],
            internal_structures=raw_structures,
            architecture_role=str(data.get("architecture_role") or "other"),
            dependencies_summary=str(data.get("dependencies_summary") or ""),
        )

    # ── 降级分析 ───────────────────────────────

    def _fallback_analysis(self, parse_result: ParseResult) -> AIFileAnalysis:
        inputs = [
            AIInputOutput(
                name=imp.variable_name,
                type=imp.data_type,
                source=imp.source_module,
            )
            for imp in parse_result.imports
        ]
        outputs = [
            AIInputOutput(
                name=exp.variable_name,
                type=exp.data_type,
                is_function=exp.is_function,
            )
            for exp in parse_result.exports
        ]

        func_names = [f.name for f in parse_result.functions[:5]]
        class_names = [c.name for c in parse_result.classes[:3]]

        summary_parts = []
        if func_names:
            summary_parts.append(
                f"{len(parse_result.functions)}个函数({', '.join(func_names[:3])})"
            )
        if class_names:
            summary_parts.append(
                f"{len(parse_result.classes)}个类({', '.join(class_names[:3])})"
            )

        return AIFileAnalysis(
            file_path=parse_result.file_path,
            summary=", ".join(summary_parts) if summary_parts
            else f"{parse_result.language} 源码文件",
            detail=(
                f"该文件导入了 {len(parse_result.imports)} 个外部依赖，"
                f"导出了 {len(parse_result.exports)} 个符号，"
                f"包含 {len(parse_result.functions)} 个函数和 "
                f"{len(parse_result.classes)} 个类。"
            ),
            inputs=inputs,
            outputs=outputs,
            architecture_role="other",
        )


# 单例
ai_engine = AIAnalysisEngine()
