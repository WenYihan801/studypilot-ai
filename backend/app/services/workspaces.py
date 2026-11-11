from __future__ import annotations

from collections import Counter

from app.api.deps import Ctx
from app.repositories import DocumentRepo, WorkspaceRepo


class WorkspaceService:
    def __init__(self, ctx: Ctx):
        self.ctx = ctx
        self.repo = WorkspaceRepo(ctx.db)
        self.docs = DocumentRepo(ctx.db)

    def list(self) -> list[dict]:
        workspaces = self.repo.list(self.ctx.user_id)
        counts = Counter(d["workspace_id"] for d in self.docs.list(self.ctx.user_id, columns="id,workspace_id"))
        return [{**w, "document_count": counts.get(w["id"], 0)} for w in workspaces]

    def get(self, workspace_id: str) -> dict:
        ws = self.repo.get(self.ctx.user_id, workspace_id)
        return {**ws, "document_count": self.docs.count(self.ctx.user_id, {"workspace_id": workspace_id})}

    def create(self, name: str, description: str) -> dict:
        ws = self.repo.create(self.ctx.user_id, {"name": name, "description": description})
        return {**ws, "document_count": 0}

    def update(self, workspace_id: str, values: dict) -> dict:
        self.repo.get(self.ctx.user_id, workspace_id)
        if values:
            self.repo.update(self.ctx.user_id, workspace_id, values)
        return self.get(workspace_id)

    def delete(self, workspace_id: str) -> None:
        """DB rows cascade (chunks/vectors, chats, quizzes, cards). Storage files must be removed explicitly."""
        self.repo.get(self.ctx.user_id, workspace_id)
        paths = [
            d["storage_path"] for d in self.docs.list(self.ctx.user_id, {"workspace_id": workspace_id}, columns="id,storage_path")
        ]
        if paths:
            self.ctx.storage.remove(paths)
        self.repo.delete(self.ctx.user_id, workspace_id)
