"""All /api/v1 routes. Handlers stay thin: parse input -> call a service -> return a schema."""

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Response,
    UploadFile,
    status,
)

from app import __version__
from app.api.deps import Ctx, get_ai_ctx, get_ctx
from app.core.config import Settings, get_settings
from app.schemas import api as s
from app.services.account import AccountService
from app.services.chat import ChatService
from app.services.dashboard import DashboardService
from app.services.documents import DocumentService, IngestionService
from app.services.flashcards import FlashcardService
from app.services.quiz import QuizService
from app.services.summary import SummaryService
from app.services.usage import UsageService
from app.services.workspaces import WorkspaceService

ERRORS = {401: {"model": s.ErrorOut}, 404: {"model": s.ErrorOut}, 422: {"model": s.ErrorOut}}
AI_ERRORS = {**ERRORS, 429: {"model": s.ErrorOut}, 502: {"model": s.ErrorOut}}

router = APIRouter(prefix="/api/v1")


# ------------------------------------------------------------------- health
@router.get("/health", response_model=s.HealthOut, tags=["system"])
def health(settings: Settings = Depends(get_settings)):
    """Unauthenticated, no DB access: used by Render health checks and to wake a sleeping instance."""
    return {"status": "ok", "version": __version__, "environment": settings.app_env, "ai_provider": settings.ai_provider}


# ------------------------------------------------------------------- me
@router.get("/me", response_model=s.ProfileOut, responses=ERRORS, tags=["account"])
def get_me(ctx: Ctx = Depends(get_ctx)):
    return AccountService(ctx).me()


@router.patch("/me", response_model=s.ProfileOut, responses=ERRORS, tags=["account"])
def update_me(body: s.ProfileUpdate, ctx: Ctx = Depends(get_ctx)):
    return AccountService(ctx).update(body.display_name)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS, tags=["account"])
def delete_me(ctx: Ctx = Depends(get_ctx)):
    AccountService(ctx).delete_account()
    return Response(status_code=204)


# ------------------------------------------------------------------- workspaces
@router.get("/workspaces", response_model=list[s.WorkspaceOut], responses=ERRORS, tags=["workspaces"])
def list_workspaces(ctx: Ctx = Depends(get_ctx)):
    return WorkspaceService(ctx).list()


@router.post("/workspaces", response_model=s.WorkspaceOut, status_code=201, responses=ERRORS, tags=["workspaces"])
def create_workspace(body: s.WorkspaceCreate, ctx: Ctx = Depends(get_ctx)):
    return WorkspaceService(ctx).create(body.name.strip(), body.description.strip())


@router.get("/workspaces/{workspace_id}", response_model=s.WorkspaceOut, responses=ERRORS, tags=["workspaces"])
def get_workspace(workspace_id: str, ctx: Ctx = Depends(get_ctx)):
    return WorkspaceService(ctx).get(workspace_id)


@router.patch("/workspaces/{workspace_id}", response_model=s.WorkspaceOut, responses=ERRORS, tags=["workspaces"])
def update_workspace(workspace_id: str, body: s.WorkspaceUpdate, ctx: Ctx = Depends(get_ctx)):
    return WorkspaceService(ctx).update(workspace_id, body.model_dump(exclude_none=True))


@router.delete("/workspaces/{workspace_id}", status_code=204, responses=ERRORS, tags=["workspaces"])
def delete_workspace(workspace_id: str, ctx: Ctx = Depends(get_ctx)):
    WorkspaceService(ctx).delete(workspace_id)
    return Response(status_code=204)


# ------------------------------------------------------------------- documents
@router.get("/workspaces/{workspace_id}/documents", response_model=list[s.DocumentOut], responses=ERRORS, tags=["documents"])
def list_documents(workspace_id: str, ctx: Ctx = Depends(get_ctx)):
    return DocumentService(ctx).list(workspace_id)


@router.post(
    "/workspaces/{workspace_id}/documents",
    response_model=s.DocumentOut,
    status_code=201,
    responses={**ERRORS, 409: {"model": s.ErrorOut}},
    tags=["documents"],
)
def upload_document(workspace_id: str, background: BackgroundTasks, file: UploadFile = File(...), ctx: Ctx = Depends(get_ctx)):
    """Validates and stores the file, then extracts/chunks/embeds it in the background (status -> READY/FAILED)."""
    data = file.file.read(ctx.settings.max_upload_bytes + 1)  # never read more than limit + 1 byte
    doc = DocumentService(ctx).upload(workspace_id, file.filename or "document", file.content_type, data)
    background.add_task(IngestionService(ctx.admin, ctx.storage, ctx.ai, ctx.settings).process, ctx.user_id, doc["id"])
    return doc


@router.get("/documents/{document_id}", response_model=s.DocumentOut, responses=ERRORS, tags=["documents"])
def get_document(document_id: str, ctx: Ctx = Depends(get_ctx)):
    return DocumentService(ctx).get(document_id)


@router.delete("/documents/{document_id}", status_code=204, responses=ERRORS, tags=["documents"])
def delete_document(document_id: str, ctx: Ctx = Depends(get_ctx)):
    DocumentService(ctx).delete(document_id)
    return Response(status_code=204)


@router.post(
    "/documents/{document_id}/process",
    response_model=s.DocumentOut,
    status_code=202,
    responses={**ERRORS, 409: {"model": s.ErrorOut}},
    tags=["documents"],
)
def reprocess_document(document_id: str, background: BackgroundTasks, ctx: Ctx = Depends(get_ctx)):
    """Re-runs ingestion (e.g. after a FAILED status or a server restart left it stuck in PROCESSING)."""
    svc = DocumentService(ctx)
    svc.ensure_can_process(document_id)
    background.add_task(IngestionService(ctx.admin, ctx.storage, ctx.ai, ctx.settings).process, ctx.user_id, document_id)
    return svc.get(document_id)


@router.get("/documents/{document_id}/summary", response_model=s.SummaryOut | None, responses=ERRORS, tags=["documents"])
def get_summary(document_id: str, ctx: Ctx = Depends(get_ctx)):
    return SummaryService(ctx).get_cached(document_id)


@router.post("/documents/{document_id}/summary", response_model=s.SummaryOut, responses=AI_ERRORS, tags=["documents"])
def create_summary(document_id: str, body: s.SummaryRequest | None = None, ctx: Ctx = Depends(get_ai_ctx)):
    return SummaryService(ctx).generate(document_id, force=bool(body and body.force))


# ------------------------------------------------------------------- chat
@router.post("/workspaces/{workspace_id}/chat", response_model=s.ChatResponse, responses=AI_ERRORS, tags=["chat"])
def chat(workspace_id: str, body: s.ChatRequest, ctx: Ctx = Depends(get_ai_ctx)):
    return ChatService(ctx).ask(workspace_id, body.question, body.conversation_id, body.document_ids)


@router.get(
    "/workspaces/{workspace_id}/conversations", response_model=list[s.ConversationSummaryOut], responses=ERRORS, tags=["chat"]
)
def list_conversations(workspace_id: str, ctx: Ctx = Depends(get_ctx)):
    return ChatService(ctx).list_conversations(workspace_id)


@router.get("/conversations/{conversation_id}", response_model=s.ConversationOut, responses=ERRORS, tags=["chat"])
def get_conversation(conversation_id: str, ctx: Ctx = Depends(get_ctx)):
    return ChatService(ctx).get_conversation(conversation_id)


@router.delete("/conversations/{conversation_id}", status_code=204, responses=ERRORS, tags=["chat"])
def delete_conversation(conversation_id: str, ctx: Ctx = Depends(get_ctx)):
    ChatService(ctx).delete_conversation(conversation_id)
    return Response(status_code=204)


# ------------------------------------------------------------------- quizzes
@router.post(
    "/workspaces/{workspace_id}/quizzes/generate",
    response_model=s.QuizOut,
    status_code=201,
    responses=AI_ERRORS,
    tags=["quizzes"],
)
def generate_quiz(workspace_id: str, body: s.QuizGenerateRequest, ctx: Ctx = Depends(get_ai_ctx)):
    return QuizService(ctx).generate(
        workspace_id,
        title=body.title,
        num_questions=body.num_questions,
        difficulty=body.difficulty,
        types=list(dict.fromkeys(body.types)),
        document_ids=body.document_ids,
    )


@router.get("/workspaces/{workspace_id}/quizzes", response_model=list[s.QuizListItem], responses=ERRORS, tags=["quizzes"])
def list_quizzes(workspace_id: str, ctx: Ctx = Depends(get_ctx)):
    return QuizService(ctx).list(workspace_id)


@router.get("/quizzes/{quiz_set_id}", response_model=s.QuizOut, responses=ERRORS, tags=["quizzes"])
def get_quiz(quiz_set_id: str, ctx: Ctx = Depends(get_ctx)):
    return QuizService(ctx).get(quiz_set_id)


@router.delete("/quizzes/{quiz_set_id}", status_code=204, responses=ERRORS, tags=["quizzes"])
def delete_quiz(quiz_set_id: str, ctx: Ctx = Depends(get_ctx)):
    QuizService(ctx).delete(quiz_set_id)
    return Response(status_code=204)


@router.post("/quiz-attempts", response_model=s.AttemptOut, status_code=201, responses=ERRORS, tags=["quizzes"])
def start_attempt(body: s.AttemptCreate, ctx: Ctx = Depends(get_ctx)):
    return QuizService(ctx).start_attempt(body.quiz_set_id)


@router.post(
    "/quiz-attempts/{attempt_id}/submit",
    response_model=s.AttemptResultOut,
    responses={**AI_ERRORS, 409: {"model": s.ErrorOut}},
    tags=["quizzes"],
)
def submit_attempt(attempt_id: str, body: s.AttemptSubmit, ctx: Ctx = Depends(get_ctx)):
    return QuizService(ctx).submit(attempt_id, body.answers)


@router.get("/quiz-attempts/{attempt_id}", response_model=s.AttemptResultOut, responses=ERRORS, tags=["quizzes"])
def get_attempt(attempt_id: str, ctx: Ctx = Depends(get_ctx)):
    return QuizService(ctx).result(attempt_id)


# ------------------------------------------------------------------- flashcards
@router.post(
    "/workspaces/{workspace_id}/flashcards/generate",
    response_model=s.FlashcardSetOut,
    status_code=201,
    responses=AI_ERRORS,
    tags=["flashcards"],
)
def generate_flashcards(workspace_id: str, body: s.FlashcardGenerateRequest, ctx: Ctx = Depends(get_ai_ctx)):
    return FlashcardService(ctx).generate(workspace_id, title=body.title, count=body.count, document_ids=body.document_ids)


@router.get(
    "/workspaces/{workspace_id}/flashcard-sets",
    response_model=list[s.FlashcardSetListItem],
    responses=ERRORS,
    tags=["flashcards"],
)
def list_flashcard_sets(workspace_id: str, ctx: Ctx = Depends(get_ctx)):
    return FlashcardService(ctx).list_sets(workspace_id)


@router.get("/flashcard-sets/{set_id}", response_model=s.FlashcardSetOut, responses=ERRORS, tags=["flashcards"])
def get_flashcard_set(set_id: str, ctx: Ctx = Depends(get_ctx)):
    return FlashcardService(ctx).get_set(set_id)


@router.delete("/flashcard-sets/{set_id}", status_code=204, responses=ERRORS, tags=["flashcards"])
def delete_flashcard_set(set_id: str, ctx: Ctx = Depends(get_ctx)):
    FlashcardService(ctx).delete_set(set_id)
    return Response(status_code=204)


@router.get("/flashcards/due", response_model=list[s.FlashcardOut], responses=ERRORS, tags=["flashcards"])
def due_flashcards(workspace_id: str | None = None, ctx: Ctx = Depends(get_ctx)):
    return FlashcardService(ctx).due(workspace_id)


@router.patch("/flashcards/{card_id}", response_model=s.FlashcardOut, responses=ERRORS, tags=["flashcards"])
def update_flashcard(card_id: str, body: s.FlashcardUpdate, ctx: Ctx = Depends(get_ctx)):
    return FlashcardService(ctx).update_status(card_id, body.mastery_status)


@router.get("/flashcards/{card_id}/reviews", response_model=list[s.ReviewOut], responses=ERRORS, tags=["flashcards"])
def flashcard_history(card_id: str, ctx: Ctx = Depends(get_ctx)):
    return FlashcardService(ctx).history(card_id)


# ------------------------------------------------------------------- dashboard / usage
@router.get("/dashboard/summary", response_model=s.DashboardOut, responses=ERRORS, tags=["dashboard"])
def dashboard(ctx: Ctx = Depends(get_ctx)):
    return DashboardService(ctx).summary()


@router.get("/usage", response_model=s.UsageOut, responses=ERRORS, tags=["dashboard"])
def usage(ctx: Ctx = Depends(get_ctx)):
    return UsageService(ctx.admin, ctx.settings).summary(ctx.user_id)
