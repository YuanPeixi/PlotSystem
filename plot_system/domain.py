from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any
from uuid import uuid4

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "then", "when", "will",
    "have", "about", "through", "scene", "agent", "system", "plot", "story", "role",
    "一个", "可以", "通过", "进行", "以及", "需要", "开始", "最后", "按照", "生成", "整个",
    "智能体", "场景", "剧情", "角色", "环境", "系统", "文本", "用户", "之后", "允许",
}

MAX_EDGE_REASON_LENGTH = 60
CHARACTER_SPLIT_PATTERN = r"(?:进入|开启|改变|带来|重新|其中|并且|并|为了|会|使得|导致|推动|相关)"

ATMOSPHERE_KEYWORDS = {
    "紧张": ("危险", "追逐", "危机", "冲突", "秘密", "阴谋", "战争"),
    "温情": ("家", "守护", "友情", "亲情", "治愈"),
    "浪漫": ("爱", "心动", "约定", "告白"),
    "探索": ("遗迹", "旅途", "地图", "线索", "调查"),
    "奇幻": ("魔法", "龙", "神明", "秘术", "异界"),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


def split_sentences(text: str) -> list[str]:
    chunks = [part.strip() for part in re.split(r"[。！？!?.\n]+", text) if part.strip()]
    return chunks or [text.strip() or "未提供种子文本"]


def extract_terms(text: str) -> list[str]:
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z\-']{3,}", text)
    freq: dict[str, int] = {}
    for token in tokens:
        normalized = token.lower()
        if normalized in STOPWORDS:
            continue
        key = token if re.search(r"[\u4e00-\u9fff]", token) else normalized.title()
        freq[key] = freq.get(key, 0) + 1
    ordered = sorted(freq.items(), key=lambda item: (-item[1], item[0]))
    return [token for token, _ in ordered[:8]]


def build_knowledge_graph(seed_text: str) -> dict[str, Any]:
    sentences = split_sentences(seed_text)
    terms = extract_terms(seed_text)
    if not terms:
        terms = ["主角", "目标", "危机"]

    nodes = []
    for term in terms:
        mentions = sum(1 for sentence in sentences if term.lower() in sentence.lower())
        nodes.append({"id": make_id("node"), "label": term, "mentions": mentions or 1})

    edges = []
    for sentence in sentences:
        present = [term for term in terms if term.lower() in sentence.lower()]
        for index, source in enumerate(present):
            for target in present[index + 1 :]:
                if source != target:
                    edges.append({
                        "id": make_id("edge"),
                        "source": source,
                        "target": target,
                        "reason": sentence[:MAX_EDGE_REASON_LENGTH],
                    })

    if not edges and len(terms) >= 2:
        edges.append({
            "id": make_id("edge"),
            "source": terms[0],
            "target": terms[1],
            "reason": "种子文本中推断出的核心关联",
        })

    return {"nodes": nodes, "edges": edges, "chunks": sentences}


def infer_atmosphere(seed_text: str, objective: str) -> list[str]:
    combined = f"{seed_text} {objective}"
    result = [tag for tag, keywords in ATMOSPHERE_KEYWORDS.items() if any(keyword in combined for keyword in keywords)]
    return result or ["探索", "叙事"]


def build_characters(seed_text: str, graph: dict[str, Any]) -> list[dict[str, Any]]:
    used_names: set[str] = set()
    seeds = [derive_character_name(node["label"], used_names) for node in graph["nodes"][:3]]
    if len(seeds) < 3:
        seeds.extend(["主角", "同伴", "观察者"][len(seeds) : 3])

    templates = [
        ("主导者", "推动局势并逼近真相"),
        ("执行者", "采取行动并测试环境规则"),
        ("记录者", "观察变化并保留关键线索"),
    ]
    characters = []
    for index, (seed, template) in enumerate(zip(seeds, templates), start=1):
        role, goal = template
        characters.append(
            {
                "id": make_id("char"),
                "name": seed,
                "role": role,
                "persona": f"{seed}是剧情中的{role}，擅长围绕种子文本中的关键关系做出反应。",
                "goal": goal,
                "traits": [role, "沉浸式扮演", "关注上下文"],
                "long_term_memory": [f"初始设定来自种子文本关键词：{seed}"],
                "short_term_memory": [],
            }
        )
    return characters


def derive_character_name(term: str, used_names: set[str]) -> str:
    parts = [part.strip("，、；：,. ") for part in re.split(CHARACTER_SPLIT_PATTERN, term) if part.strip("，、；：,. ")]
    candidates = sorted(parts or [term], key=lambda item: (abs(len(item) - 3), len(item)))
    for candidate in candidates:
        if 2 <= len(candidate) <= 6 and candidate not in used_names:
            used_names.add(candidate)
            return candidate

    fallback = (parts[0] if parts else term)[:4] or "角色"
    if fallback in used_names:
        fallback = f"{fallback[:3]}{len(used_names) + 1}"
    used_names.add(fallback)
    return fallback


def create_project_payload(title: str, seed_text: str) -> dict[str, Any]:
    graph = build_knowledge_graph(seed_text)
    characters = build_characters(seed_text, graph)
    goal_seed = graph["chunks"][0]
    environment_focus = graph["nodes"][0]["label"] if graph["nodes"] else "未知地点"
    project_id = make_id("project")
    return {
        "id": project_id,
        "title": title,
        "seed_text": seed_text,
        "status": "draft",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "knowledge_graph": graph,
        "director": {
            "name": "导演智能体",
            "goal": f"围绕“{goal_seed[:40]}”推进剧情，并保留后续可分支的关键决策点。",
        },
        "atmosphere_agent": {"name": "氛围智能体", "mode": "keyword"},
        "summary_agent": {"name": "总结智能体", "style": "流畅叙事"},
        "environment_agent": {
            "name": "环境智能体",
            "rules": ["环境变化必须回应角色动作", "每轮记录可回溯状态", "在冲突时提高紧张度"],
        },
        "environment": {
            "location": environment_focus,
            "time_of_day": "黄昏",
            "tension": 1,
            "state_tags": infer_atmosphere(seed_text, goal_seed),
            "facts": [f"初始焦点：{environment_focus}"],
        },
        "characters": characters,
        "scenes": [],
        "snapshots": [],
        "branches": [],
        "exports": [],
    }


def build_snapshot(project: dict[str, Any], label: str) -> dict[str, Any]:
    return {
        "id": make_id("snapshot"),
        "project_id": project["id"],
        "label": label,
        "created_at": utc_now(),
        "state": deepcopy(
            {
                "environment": project["environment"],
                "characters": project["characters"],
                "scenes": project["scenes"],
            }
        ),
    }


def simulate_scene(project: dict[str, Any], rounds: int = 1) -> dict[str, Any]:
    rounds = max(1, min(rounds, 5))
    scene_id = make_id("scene")
    objective = f"推进与{project['environment']['location']}相关的核心矛盾"
    scene = {
        "id": scene_id,
        "name": f"场景 {len(project['scenes']) + 1}",
        "objective": objective,
        "atmosphere": infer_atmosphere(project["seed_text"], objective),
        "director_notes": [],
        "rounds": [],
        "summary": "",
    }

    for round_index in range(1, rounds + 1):
        snapshot = build_snapshot(project, f"{scene['name']} - 回合 {round_index} 前")
        project["snapshots"].append(snapshot)
        turns = []
        for character in project["characters"]:
            action = f"{character['name']}依据{character['goal']}，在{project['environment']['location']}主动试探新的信息。"
            dialogue = f"{character['name']}：我会结合当前线索继续推进，确保这条分支仍然可回溯。"
            character["short_term_memory"].append(action)
            turns.append(
                {
                    "character_id": character["id"],
                    "character_name": character["name"],
                    "action": action,
                    "dialogue": dialogue,
                }
            )

        project["environment"]["tension"] += 1
        env_update = {
            "tension": project["environment"]["tension"],
            "state_tags": infer_atmosphere(project["seed_text"], objective),
            "fact": f"环境对本轮互动做出反馈，紧张度提升到 {project['environment']['tension']}。",
        }
        project["environment"]["facts"].append(env_update["fact"])
        director_decision = {
            "result": "continue" if round_index < rounds else "advance",
            "reason": "导演智能体认为当前信息足以保留分支点并继续推进主线。",
        }
        scene["director_notes"].append(director_decision["reason"])
        scene["rounds"].append(
            {
                "index": round_index,
                "snapshot_id": snapshot["id"],
                "turns": turns,
                "environment_update": env_update,
                "director_decision": director_decision,
            }
        )

    for character in project["characters"]:
        if character["short_term_memory"]:
            digest = f"在{scene['name']}中，{character['name']}完成了{len(character['short_term_memory'])}次关键互动。"
            character["long_term_memory"].append(digest)
            character["short_term_memory"] = []

    scene["summary"] = summarize_scene(scene)
    project["scenes"].append(scene)
    project["status"] = "running"
    project["updated_at"] = utc_now()
    return scene


def summarize_scene(scene: dict[str, Any]) -> str:
    highlights = []
    for round_data in scene["rounds"]:
        actor_names = "、".join(turn["character_name"] for turn in round_data["turns"])
        highlights.append(f"第{round_data['index']}轮中，{actor_names}共同推动了剧情。")
    return f"{scene['name']}围绕“{scene['objective']}”展开。" + " ".join(highlights)


def export_summary(project: dict[str, Any], style: str = "网文") -> dict[str, Any]:
    if not project["scenes"]:
        simulate_scene(project, 1)
    scene_text = "\n".join(scene["summary"] for scene in project["scenes"])
    memory_text = "\n".join(
        f"- {character['name']}：{character['long_term_memory'][-1]}"
        for character in project["characters"]
        if character["long_term_memory"]
    )
    content = (
        f"【{style}导出】\n"
        f"作品标题：{project['title']}\n"
        f"导演目标：{project['director']['goal']}\n\n"
        f"场景梗概：\n{scene_text}\n\n"
        f"角色长期记忆：\n{memory_text}\n\n"
        f"环境状态：地点={project['environment']['location']}，紧张度={project['environment']['tension']}。"
    )
    export = {"id": make_id("export"), "style": style, "content": content, "created_at": utc_now()}
    project["exports"].append(export)
    project["updated_at"] = utc_now()
    return export


def create_branch_from_snapshot(project: dict[str, Any], snapshot: dict[str, Any], branch_name: str) -> dict[str, Any]:
    new_project = deepcopy(project)
    new_project["id"] = make_id("project")
    new_project["title"] = f"{project['title']} / {branch_name}"
    new_project["created_at"] = utc_now()
    new_project["updated_at"] = utc_now()
    new_project["status"] = "branch"
    new_project["parent_project_id"] = project["id"]
    new_project["branch_source_snapshot_id"] = snapshot["id"]
    new_project["environment"] = deepcopy(snapshot["state"]["environment"])
    new_project["characters"] = deepcopy(snapshot["state"]["characters"])
    new_project["scenes"] = deepcopy(snapshot["state"]["scenes"])
    new_project["snapshots"] = []
    new_project["branches"] = []
    new_project["exports"] = []
    return new_project
