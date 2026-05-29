from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any
from urllib import error, request

OBJECTIVE_TERM_PATTERN = r"[\u4e00-\u9fff]{2,}|[A-Za-z]{4,}"
DEFAULT_ACTION_TEMPLATE = "{name}依据{goal}，在{location}主动试探新的信息。"
DEFAULT_DIALOGUE_TEMPLATE = "{name}：我会结合当前线索继续推进，确保这条分支仍然可回溯。"
MAX_LONG_TERM_MEMORIES = 3
MAX_SHORT_TERM_MEMORIES = 2
MAX_RECENT_SCENES = 2

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMConfig:
    model: str = "gpt-4o-mini"
    base_url: str = ""
    api_key: str = ""

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.api_key)


class LLMClient:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    @classmethod
    def from_env(cls) -> "LLMClient":
        return cls(
            LLMConfig(
                model=os.getenv("PLOT_SYSTEM_LLM_MODEL", "gpt-4o-mini"),
                base_url=os.getenv("PLOT_SYSTEM_LLM_BASE_URL", "").rstrip("/"),
                api_key=os.getenv("PLOT_SYSTEM_LLM_API_KEY", ""),
            )
        )

    def complete(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.7, max_tokens: int = 220) -> str | None:
        if not self.config.enabled:
            return None
        safe_temperature = min(2.0, max(0.0, temperature))
        safe_max_tokens = max(1, int(max_tokens))
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": safe_temperature,
            "max_tokens": safe_max_tokens,
        }
        endpoint = f"{self.config.base_url}/chat/completions"
        req = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self.config.api_key,
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=20) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
            cleaned = content.strip()
            return cleaned or None
        except (error.URLError, TimeoutError, OSError, ValueError, KeyError, IndexError) as exc:
            LOGGER.debug("LLM completion failed: %s", exc)
            return None


class GraphRAGContextManager:
    """A lightweight GraphRAG-style context retriever for local project state."""

    @staticmethod
    def retrieve(project: dict[str, Any], objective: str, character: dict[str, Any] | None = None, top_k: int = 3) -> dict[str, Any]:
        objective_terms = set(re.findall(OBJECTIVE_TERM_PATTERN, objective.lower()))
        graph_nodes = project.get("knowledge_graph", {}).get("nodes", [])
        graph_chunks = project.get("knowledge_graph", {}).get("chunks", [])
        scored_nodes = []
        for node in graph_nodes:
            label = str(node.get("label", ""))
            score = sum(1 for term in objective_terms if term and term in label.lower())
            score += int(node.get("mentions", 0))
            scored_nodes.append((score, label))
        scored_nodes.sort(key=lambda item: (-item[0], item[1]))

        memories: list[str] = []
        if character:
            memories.extend(character.get("long_term_memory", [])[-MAX_LONG_TERM_MEMORIES:])
            memories.extend(character.get("short_term_memory", [])[-MAX_SHORT_TERM_MEMORIES:])

        chunk_ranked = []
        for chunk in graph_chunks:
            text = str(chunk)
            score = sum(1 for term in objective_terms if term and term in text.lower())
            chunk_ranked.append((score, text))
        chunk_ranked.sort(key=lambda item: (-item[0], len(item[1])))

        latest_scene_summaries = [
            scene.get("summary", "") for scene in project.get("scenes", [])[-MAX_RECENT_SCENES:] if scene.get("summary")
        ]
        return {
            "graph_terms": [label for _, label in scored_nodes[:top_k] if label],
            "graph_chunks": [text for _, text in chunk_ranked[:top_k] if text],
            "memory": memories[:top_k],
            "scene_summaries": latest_scene_summaries,
        }


class AutoGenCoordinator:
    """A lightweight AutoGen-like coordinator with deterministic fallback."""

    def __init__(self, client: LLMClient | None = None) -> None:
        self.client = client or LLMClient.from_env()
        self.graphrag = GraphRAGContextManager()

    @staticmethod
    def _format_dialogue(name: str, content: str) -> str:
        return content if content.startswith(f"{name}：") else f"{name}：{content}"

    def character_turn(self, *, project: dict[str, Any], character: dict[str, Any], objective: str, location: str) -> tuple[str, str]:
        context = self.graphrag.retrieve(project, objective, character=character)
        fallback_action = DEFAULT_ACTION_TEMPLATE.format(name=character["name"], goal=character["goal"], location=location)
        fallback_dialogue = DEFAULT_DIALOGUE_TEMPLATE.format(name=character["name"])

        prompt = (
            f"角色名：{character['name']}\n"
            f"角色定位：{character['role']}\n"
            f"角色目标：{character['goal']}\n"
            f"场景目标：{objective}\n"
            f"地点：{location}\n"
            f"GraphRAG关键词：{', '.join(context['graph_terms']) or '无'}\n"
            f"GraphRAG片段：{'; '.join(context['graph_chunks']) or '无'}\n"
            f"记忆：{'; '.join(context['memory']) or '无'}\n"
            "请仅输出两行：\n"
            "ACTION: ...\n"
            "DIALOGUE: ...\n"
        )
        completion = self.client.complete(
            system_prompt="你是剧情多智能体系统中的角色智能体，请给出具体且简洁的行动与对白。",
            user_prompt=prompt,
            temperature=0.75,
            max_tokens=180,
        )
        if not completion:
            return fallback_action, fallback_dialogue

        action = fallback_action
        dialogue = fallback_dialogue
        for line in completion.splitlines():
            stripped = line.strip()
            if stripped.upper().startswith("ACTION:"):
                candidate = stripped.split(":", 1)[1].strip()
                if candidate:
                    action = candidate
            elif stripped.upper().startswith("DIALOGUE:"):
                candidate = stripped.split(":", 1)[1].strip()
                if candidate:
                    dialogue = self._format_dialogue(character["name"], candidate)
        return action, dialogue

    def director_decision(self, *, project: dict[str, Any], objective: str, round_index: int, rounds: int) -> dict[str, str]:
        default_result = "continue" if round_index < rounds else "advance"
        default_reason = "导演智能体认为当前信息足以保留分支点并继续推进主线。"
        context = self.graphrag.retrieve(project, objective, character=None)
        prompt = (
            f"回合：{round_index}/{rounds}\n"
            f"场景目标：{objective}\n"
            f"关键图谱词：{', '.join(context['graph_terms']) or '无'}\n"
            f"近期场景总结：{'；'.join(context['scene_summaries']) or '无'}\n"
            "请仅输出两行：\n"
            "RESULT: continue 或 advance\n"
            "REASON: 一句简洁理由\n"
        )
        completion = self.client.complete(
            system_prompt="你是导演智能体，负责控制剧情推进节奏并保留可分支决策点。",
            user_prompt=prompt,
            temperature=0.4,
            max_tokens=120,
        )
        if not completion:
            return {"result": default_result, "reason": default_reason}

        result = default_result
        reason = default_reason
        for line in completion.splitlines():
            stripped = line.strip()
            if stripped.upper().startswith("RESULT:"):
                candidate = stripped.split(":", 1)[1].strip().lower()
                if candidate in {"continue", "advance"}:
                    result = candidate
            elif stripped.upper().startswith("REASON:"):
                candidate = stripped.split(":", 1)[1].strip()
                if candidate:
                    reason = candidate
        return {"result": result, "reason": reason}

    def summary(self, *, project: dict[str, Any], style: str, fallback_content: str) -> str:
        context = self.graphrag.retrieve(project, project.get("director", {}).get("goal", ""))
        prompt = (
            f"风格：{style}\n"
            f"标题：{project.get('title', '')}\n"
            f"导演目标：{project.get('director', {}).get('goal', '')}\n"
            f"图谱关键词：{', '.join(context['graph_terms']) or '无'}\n"
            f"近期总结：{'；'.join(context['scene_summaries']) or '无'}\n"
            "请输出一段剧情总结，包含导演目标、场景推进、角色记忆和环境状态。"
        )
        completion = self.client.complete(
            system_prompt="你是总结智能体，负责产出结构清晰的剧情导出文本。",
            user_prompt=prompt,
            temperature=0.65,
            max_tokens=320,
        )
        if not completion:
            return fallback_content
        return completion
