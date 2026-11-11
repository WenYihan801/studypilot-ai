import logging

from app.api.deps import Ctx
from app.repositories import DocumentRepo, ProfileRepo, UsageRepo, WorkspaceRepo

logger = logging.getLogger("studypilot.account")


class AccountService:
    def __init__(self, ctx: Ctx):
        self.ctx = ctx

    def me(self) -> dict:
        profile = ProfileRepo(self.ctx.db).get(self.ctx.user_id) or {"display_name": "", "created_at": None}
        return {
            "id": self.ctx.user_id,
            "email": self.ctx.user.email,
            "display_name": profile.get("display_name", ""),
            "created_at": profile.get("created_at"),
        }

    def update(self, display_name: str) -> dict:
        ProfileRepo(self.ctx.db).upsert_name(self.ctx.user_id, display_name.strip())
        return self.me()

    def delete_account(self) -> None:
        """Removes files, vectors and all rows, then the auth user itself."""
        uid = self.ctx.user_id
        paths = [d["storage_path"] for d in DocumentRepo(self.ctx.admin).list(uid, columns="id,storage_path")]
        if paths:
            self.ctx.storage.remove(paths)
        for ws in WorkspaceRepo(self.ctx.admin).list(uid, columns="id"):
            WorkspaceRepo(self.ctx.admin).delete(uid, ws["id"])  # cascades everything inside
        UsageRepo(self.ctx.admin).delete_where(uid, {})
        if self.ctx.settings.data_backend == "supabase":
            # auth.users delete cascades profiles and any remaining rows via FKs.
            self.ctx.admin.client.auth.admin.delete_user(uid)  # type: ignore[attr-defined]
        logger.info("Account deleted")
