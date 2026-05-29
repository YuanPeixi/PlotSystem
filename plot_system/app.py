from __future__ import annotations

from pathlib import Path
from typing import Any

from .domain import build_snapshot, create_branch_from_snapshot, create_project_payload, export_summary, simulate_scene
from .storage import JsonStorage


class ProjectService:
    def __init__(self, storage: JsonStorage) -> None:
        self.storage = storage

    def list_projects(self) -> list[dict[str, Any]]:
        data = self.storage.load()
        return sorted(data["projects"].values(), key=lambda item: item["created_at"], reverse=True)

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        return self.storage.load()["projects"].get(project_id)

    def create_project(self, title: str, seed_text: str) -> dict[str, Any]:
        data = self.storage.load()
        project = create_project_payload(title=title.strip() or "未命名项目", seed_text=seed_text.strip())
        project["snapshots"].append(build_snapshot(project, "初始快照"))
        data["projects"][project["id"]] = project
        self.storage.save(data)
        return project

    def simulate(self, project_id: str, rounds: int) -> dict[str, Any]:
        data = self.storage.load()
        project = self._require_project(data, project_id)
        scene = simulate_scene(project, rounds)
        self.storage.save(data)
        return scene

    def summarize(self, project_id: str, style: str) -> dict[str, Any]:
        data = self.storage.load()
        project = self._require_project(data, project_id)
        export = export_summary(project, style)
        self.storage.save(data)
        return export

    def branch(self, project_id: str, snapshot_id: str, branch_name: str) -> dict[str, Any]:
        data = self.storage.load()
        project = self._require_project(data, project_id)
        snapshot = next((item for item in project["snapshots"] if item["id"] == snapshot_id), None)
        if snapshot is None:
            raise KeyError(f"Snapshot not found: {snapshot_id}")
        branch = create_branch_from_snapshot(project, snapshot, branch_name.strip() or "新分支")
        project["branches"].append({"project_id": branch["id"], "name": branch_name, "source_snapshot_id": snapshot_id})
        data["projects"][branch["id"]] = branch
        self.storage.save(data)
        return branch

    @staticmethod
    def _require_project(data: dict[str, Any], project_id: str) -> dict[str, Any]:
        project = data["projects"].get(project_id)
        if project is None:
            raise KeyError(f"Project not found: {project_id}")
        return project


def create_project_service(data_dir: str | Path | None = None) -> ProjectService:
    base_dir = Path(data_dir or Path(__file__).resolve().parent.parent / "data")
    return ProjectService(JsonStorage(base_dir / "plot_system.json"))
