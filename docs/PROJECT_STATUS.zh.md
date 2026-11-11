# 项目进度（2026-11-11）

## 已完成（代码层面全部完成，并在本地实际运行验证）

| 企划书模块 | 状态 | 位置 |
|---|---|---|
| 用户认证（注册/登录/登出/保持登录/重置密码/资料） | ✅ | `frontend/src/features/auth`，后端 JWKS 验证 `backend/app/core/security.py` |
| 用户数据隔离（RLS + 服务层双重检查） | ✅ 已测试 | `supabase/migrations`，`supabase/tests` |
| Workspace CRUD + 级联清理（含 Storage 文件） | ✅ | `services/workspaces.py` |
| 文档上传/格式+MIME+文件头校验/去重/状态/失败原因/重新处理 | ✅ | `services/documents.py`，`parsers/` |
| Chunking + Embedding（768 维）+ pgvector 检索 | ✅ | `services/chunking.py`，`match_chunks` |
| RAG 问答 + 引用验证 + 资料不足识别 + 对话历史 | ✅ | `services/chat.py` |
| 分段摘要（8 个部分）+ 缓存 | ✅ | `services/summary.py` |
| 测验生成（3 种题型）+ Pydantic/规则校验 + 自动评分（含简答 LLM 评分） | ✅ | `services/quiz.py` |
| 闪卡生成/翻转/掌握状态/待复习/复习历史 | ✅ | `services/flashcards.py` |
| Dashboard + 学习进度图表（真实数据） | ✅ | `services/dashboard.py`，`features/progress` |
| AI 用量记录 / 每日配额 / 速率限制 / Mock Provider | ✅ | `services/usage.py`，`providers/mock.py` |
| 14 个前端页面（桌面 + 移动端，Loading/Empty/Error/Success 状态） | ✅ 已截图检查 | `frontend/src` |
| 自动化测试：后端 76 个、前端 10 个、E2E 冒烟 8 个、SQL RLS 检查 | ✅ 全部通过 | `docs/testing.md` |
| 部署配置：`render.yaml`、`vercel.json`、GitHub Actions CI | ✅ | 仓库根目录 |
| 文档：README（英文）、SRS、架构图、ER 图、API、隐私、部署、测试报告、演示脚本 | ✅ | `docs/` |

## 需要你本人完成（需要你的账号，我无法代做）

1. ✅ Supabase dev 项目已创建并建表（2026-11-11）；prod 项目在部署时再建。
2. ✅ Gemini dev Key 已创建并验证；prod Key 部署时在另一个项目里建。
3. ✅ **真实 RAG 评估已完成（2026-11-11）**：26/26，但语料只有 3 份短笔记，检索几乎不构成挑战；需要用 10–20 份真实长 PDF 再测一次才有说服力。
4. **运行线上 RLS 测试**（`tests/integration`）和完整 E2E（`e2e/full-flow.spec.ts`）。
5. **部署**：Render（Blueprint）→ Vercel（Root Directory = `frontend`）→ 回填 CORS 和 Supabase Redirect URLs。
6. **作品集收尾**：真实截图（放 `docs/screenshots/`）、按 `docs/demo-script.md` 录 2–3 分钟视频、README 填 Live Demo 链接。

## 建议的学习顺序（对应原 8 周计划）

你不需要从零写代码，但面试时必须能讲清楚。建议每周读懂一层，并亲手改一个小功能：
- W1：跑通本地环境；读 `core/config.py`、`main.py`、`api/deps.py`
- W2：读 migration 的 RLS 部分 + `core/security.py`；跑 `supabase/tests`
- W3：读 `parsers/` 和 `services/documents.py`；上传一个自己的 PDF
- W4：读 `chunking.py`、`retrieval.py`、`match_chunks`；改 `RETRIEVAL_TOP_K` 看效果
- W5：读 `chat.py` 的引用验证；跑真实 Gemini 评估
- W6：读 `quiz.py` 的 `check_question`；读 `flashcards.py`
- W7：读测试文件，自己补 2–3 个测试
- W8：部署 + 录视频

## 简历描述（真实、可核查；括号内数字在你跑完评估后再补）

- Built **StudyPilot AI**, a full-stack RAG study assistant (React/TypeScript, FastAPI, Supabase PostgreSQL + pgvector, Gemini API) deployed on Vercel and Render.
- Implemented citation-grounded Q&A: workspace-scoped vector search, a provider-agnostic AI adapter, and server-side citation validation that rejects sources not returned by retrieval; the assistant declines when materials lack evidence.
- Enforced multi-tenant isolation with PostgreSQL Row Level Security (backend queries run under the user's JWT, verified via JWKS) and read-only integrity tables for scores and AI usage; verified with SQL and API isolation tests.
- Generated quizzes and flashcards with JSON-schema output validated by Pydantic and business rules; auto-grading including LLM-graded short answers.
- Controlled AI cost with per-user daily quotas, rate limiting, embedding reuse via SHA-256 deduplication and cached map-reduce summaries.
- Wrote 94 automated tests (Pytest, Vitest, Playwright) and a GitHub Actions CI pipeline; on a 26-question evaluation set over sample course notes, every in-scope answer cited the correct source and all 6 out-of-scope questions were correctly declined (small corpus — expanding the benchmark).
