import re

from app.api.deps import Ctx
from app.core.errors import AIProviderError, ValidationFailedError
from app.db.gateway import in_
from app.repositories import (
    CitationRepo,
    ConversationRepo,
    DocumentRepo,
    MessageRepo,
    WorkspaceRepo,
)
from app.schemas.ai import ChatAnswerDraft
from app.services.prompts import GROUNDING_RULES, chat_prompt, format_sources
from app.services.retrieval import RetrievalService
from app.services.usage import ActivityService, UsageService

INSUFFICIENT_MESSAGE = (
    "I couldn't find information about this in the materials uploaded to this workspace, so I won't guess. "
    "Try rephrasing the question, or upload a document that covers this topic."
)
LABEL_RE = re.compile(r"\[(S\d+)\]")


def validate_citations(draft: ChatAnswerDraft, label_map: dict[str, dict]) -> tuple[str, list[str]]:
    """Keeps only citations that point at chunks retrieved for THIS request.

    Labels the model invented are removed from both the citation list and the answer text,
    so the UI can never display a source that does not exist.
    """
    used = [lbl for lbl in dict.fromkeys(draft.cited_sources + LABEL_RE.findall(draft.answer)) if lbl in label_map]
    answer = LABEL_RE.sub(lambda m: m.group(0) if m.group(1) in label_map else "", draft.answer)
    return re.sub(r"[ \t]{2,}", " ", answer).strip(), used


class ChatService:
    def __init__(self, ctx: Ctx):
        self.ctx = ctx
        self.conversations = ConversationRepo(ctx.db)
        self.messages = MessageRepo(ctx.db)
        self.citations = CitationRepo(ctx.db)
        self.usage = UsageService(ctx.admin, ctx.settings)

    # ------------------------------------------------------------------ reads
    def list_conversations(self, workspace_id: str) -> list[dict]:
        WorkspaceRepo(self.ctx.db).get(self.ctx.user_id, workspace_id)
        return self.conversations.list(self.ctx.user_id, {"workspace_id": workspace_id}, limit=50)

    def get_conversation(self, conversation_id: str) -> dict:
        conv = self.conversations.get(self.ctx.user_id, conversation_id)
        msgs = self.messages.list(self.ctx.user_id, {"conversation_id": conversation_id})
        return {**conv, "messages": [self._with_citations(m) for m in msgs]}

    def delete_conversation(self, conversation_id: str) -> None:
        self.conversations.delete(self.ctx.user_id, conversation_id)

    def _with_citations(self, msg: dict) -> dict:
        cites = self.citations.list(self.ctx.user_id, {"message_id": msg["id"]}) if msg["role"] == "assistant" else []
        if cites:
            chunk_rows = self.ctx.db.select(
                "document_chunks",
                {"user_id": self.ctx.user_id, "id": in_([c["chunk_id"] for c in cites])},
                columns="id,document_id,page_number,section_title",
            )
            chunks = {c["id"]: c for c in chunk_rows}
            doc_ids = list({c["document_id"] for c in chunk_rows})
            docs = (
                {
                    d["id"]: d
                    for d in DocumentRepo(self.ctx.db).list(self.ctx.user_id, {"id": in_(doc_ids)}, columns="id,filename")
                }
                if doc_ids
                else {}
            )
            out = []
            for c in cites:
                ch = chunks.get(c["chunk_id"], {})
                out.append(
                    {
                        "label": f"S{c['rank']}",
                        "chunk_id": c["chunk_id"],
                        "document_id": ch.get("document_id"),
                        "filename": docs.get(ch.get("document_id"), {}).get("filename", "Deleted document"),
                        "page_number": ch.get("page_number"),
                        "section_title": ch.get("section_title"),
                        "quote_text": c["quote_text"],
                        "score": c["score"],
                    }
                )
            cites = out
        return {**msg, "citations": cites}

    # ------------------------------------------------------------------ ask
    def ask(self, workspace_id: str, question: str, conversation_id: str | None, document_ids: list[str] | None) -> dict:
        s, uid = self.ctx.settings, self.ctx.user_id
        question = question.strip()
        if not question:
            raise ValidationFailedError("Question cannot be empty.")
        if len(question) > s.max_question_chars:
            raise ValidationFailedError(f"Question is longer than {s.max_question_chars} characters.")
        WorkspaceRepo(self.ctx.db).get(uid, workspace_id)
        self.usage.check_quota(uid)

        if conversation_id:
            conv = self.conversations.get(uid, conversation_id)
            if conv["workspace_id"] != workspace_id:
                raise ValidationFailedError("Conversation does not belong to this workspace.")
        else:
            conv = self.conversations.create(uid, {"workspace_id": workspace_id, "title": question[:80]})
        history = self.messages.list(uid, {"conversation_id": conv["id"]})[-6:]

        chunks = RetrievalService(self.ctx).search(workspace_id, question, document_ids=document_ids)
        answer, used_labels, label_map, insufficient = INSUFFICIENT_MESSAGE, [], {}, True
        model_name, in_tok, out_tok = None, 0, 0

        if chunks:  # no relevant chunks => no LLM call at all (saves quota, cannot hallucinate)
            sources_block, label_map = format_sources(chunks)
            prompt = chat_prompt(question, sources_block, history)
            for attempt in range(2):  # at most one regeneration if citations were invalid
                result = self.ctx.ai.generate_structured_output(
                    prompt, ChatAnswerDraft, system=GROUNDING_RULES, max_output_tokens=s.max_answer_tokens
                )
                self.usage.record(uid, self.ctx.ai.name, "chat", result.usage)
                model_name = result.usage.model
                in_tok += result.usage.input_tokens
                out_tok += result.usage.output_tokens
                answer, used_labels = validate_citations(result.data, label_map)
                insufficient = not result.data.sufficient_evidence
                if insufficient or used_labels:
                    break
                if attempt == 0:
                    prompt += "\n\nYour previous answer cited no valid source labels. Cite only labels from <sources>."
            if not insufficient and not used_labels:
                # Model insisted on an answer it could not ground: refuse rather than show unsupported claims.
                answer, insufficient = INSUFFICIENT_MESSAGE, True
            if not answer:
                raise AIProviderError("The AI returned an empty answer.")

        user_msg = self.messages.create(uid, {"conversation_id": conv["id"], "role": "user", "content": question})
        asst = self.messages.create(
            uid,
            {
                "conversation_id": conv["id"],
                "role": "assistant",
                "content": answer,
                "insufficient_evidence": insufficient,
                "model_name": model_name,
                "input_tokens": in_tok or None,
                "output_tokens": out_tok or None,
            },
        )
        citation_rows = []
        for lbl in used_labels:
            ch = label_map[lbl]
            citation_rows.append(
                {
                    "message_id": asst["id"],
                    "chunk_id": ch["id"],
                    "rank": int(lbl[1:]),
                    "score": round(float(ch.get("similarity") or 0), 4),
                    "quote_text": ch["content"][:400],
                }
            )
        self.citations.create_many(uid, citation_rows)
        self.conversations.update(uid, conv["id"], {"title": conv["title"]})  # bumps updated_at
        ActivityService(self.ctx.admin).log(uid, workspace_id, "chat", f"Asked: {question[:120]}")

        citations = [
            {
                "label": lbl,
                "chunk_id": label_map[lbl]["id"],
                "document_id": label_map[lbl]["document_id"],
                "filename": label_map[lbl]["filename"],
                "page_number": label_map[lbl].get("page_number"),
                "section_title": label_map[lbl].get("section_title"),
                "quote_text": label_map[lbl]["content"][:400],
                "score": round(float(label_map[lbl].get("similarity") or 0), 4),
            }
            for lbl in used_labels
        ]
        return {
            "conversation_id": conv["id"],
            "user_message": {**user_msg, "citations": []},
            "message": {**asst, "citations": citations},
            "insufficient_evidence": insufficient,
        }
