-- StudyPilot AI — initial schema
-- Embedding dimension is fixed at 768 (gemini-embedding-001 with output_dimensionality=768).
-- If you change EMBEDDING_DIM in the backend, you must write a new migration AND re-embed every chunk.

create extension if not exists vector with schema extensions;

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- profiles (1:1 with auth.users)
-- ---------------------------------------------------------------------------
create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  display_name text not null default '' check (char_length(display_name) <= 80),
  created_at timestamptz not null default now()
);

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (id, display_name)
  values (new.id, coalesce(new.raw_user_meta_data ->> 'display_name', split_part(new.email, '@', 1)));
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------
-- workspaces
-- ---------------------------------------------------------------------------
create table public.workspaces (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  name text not null check (char_length(name) between 1 and 120),
  description text not null default '' check (char_length(description) <= 2000),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index workspaces_user_id_created_idx on public.workspaces (user_id, created_at desc);
create trigger workspaces_updated_at before update on public.workspaces
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- documents
-- ---------------------------------------------------------------------------
create table public.documents (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  filename text not null,
  storage_path text not null,
  mime_type text not null,
  size_bytes bigint not null check (size_bytes > 0),
  sha256 text not null,
  status text not null default 'UPLOADED' check (status in ('UPLOADED', 'PROCESSING', 'READY', 'FAILED')),
  page_count int,
  chunk_count int not null default 0,
  error_message text,
  processing_started_at timestamptz,
  created_at timestamptz not null default now(),
  unique (workspace_id, sha256)
);
create index documents_workspace_idx on public.documents (workspace_id, created_at desc);
create index documents_user_sha_idx on public.documents (user_id, sha256);

-- ---------------------------------------------------------------------------
-- document_chunks (pgvector)
-- ---------------------------------------------------------------------------
create table public.document_chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.documents (id) on delete cascade,
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  chunk_index int not null,
  content text not null,
  page_number int,
  section_title text,
  embedding extensions.vector(768) not null,
  created_at timestamptz not null default now(),
  unique (document_id, chunk_index)
);
-- V1 uses exact (filtered) search: workspace filter first, then distance sort.
-- This avoids HNSW post-filter recall loss. Add an HNSW index later if chunk count grows large.
create index document_chunks_workspace_idx on public.document_chunks (workspace_id);
create index document_chunks_document_idx on public.document_chunks (document_id, chunk_index);

-- ---------------------------------------------------------------------------
-- document_summaries (cache)
-- ---------------------------------------------------------------------------
create table public.document_summaries (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null unique references public.documents (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  content_json jsonb not null,
  model_name text,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- conversations / messages / citations
-- ---------------------------------------------------------------------------
create table public.conversations (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  title text not null default 'New conversation',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index conversations_workspace_idx on public.conversations (workspace_id, updated_at desc);
create trigger conversations_updated_at before update on public.conversations
  for each row execute function public.set_updated_at();

create table public.messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.conversations (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  insufficient_evidence boolean not null default false,
  model_name text,
  input_tokens int,
  output_tokens int,
  created_at timestamptz not null default now()
);
create index messages_conversation_idx on public.messages (conversation_id, created_at);

create table public.message_citations (
  id uuid primary key default gen_random_uuid(),
  message_id uuid not null references public.messages (id) on delete cascade,
  chunk_id uuid not null references public.document_chunks (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  rank int not null,
  score double precision,
  quote_text text not null
);
create index message_citations_message_idx on public.message_citations (message_id, rank);

-- ---------------------------------------------------------------------------
-- quizzes
-- ---------------------------------------------------------------------------
create table public.quiz_sets (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  title text not null,
  settings_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index quiz_sets_workspace_idx on public.quiz_sets (workspace_id, created_at desc);

create table public.quiz_questions (
  id uuid primary key default gen_random_uuid(),
  quiz_set_id uuid not null references public.quiz_sets (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  position int not null,
  type text not null check (type in ('multiple_choice', 'true_false', 'short_answer')),
  question text not null,
  options_json jsonb not null default '[]'::jsonb,
  correct_answer text not null,
  explanation text not null,
  source_chunk_ids uuid[] not null default '{}',
  difficulty text not null check (difficulty in ('easy', 'medium', 'hard'))
);
create index quiz_questions_set_idx on public.quiz_questions (quiz_set_id, position);

create table public.quiz_attempts (
  id uuid primary key default gen_random_uuid(),
  quiz_set_id uuid not null references public.quiz_sets (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  score double precision,
  started_at timestamptz not null default now(),
  submitted_at timestamptz
);
create index quiz_attempts_user_idx on public.quiz_attempts (user_id, started_at desc);
create index quiz_attempts_set_idx on public.quiz_attempts (quiz_set_id);

create table public.quiz_answers (
  id uuid primary key default gen_random_uuid(),
  attempt_id uuid not null references public.quiz_attempts (id) on delete cascade,
  question_id uuid not null references public.quiz_questions (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  answer_json jsonb not null,
  is_correct boolean not null,
  feedback text not null default '',
  unique (attempt_id, question_id)
);

-- ---------------------------------------------------------------------------
-- flashcards
-- ---------------------------------------------------------------------------
create table public.flashcard_sets (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  title text not null,
  created_at timestamptz not null default now()
);
create index flashcard_sets_workspace_idx on public.flashcard_sets (workspace_id, created_at desc);

create table public.flashcards (
  id uuid primary key default gen_random_uuid(),
  set_id uuid not null references public.flashcard_sets (id) on delete cascade,
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  position int not null default 0,
  front text not null,
  back text not null,
  source_chunk_id uuid references public.document_chunks (id) on delete set null,
  mastery_status text not null default 'NEW' check (mastery_status in ('NEW', 'LEARNING', 'MASTERED')),
  reviewed_at timestamptz
);
create index flashcards_set_idx on public.flashcards (set_id, position);
create index flashcards_user_status_idx on public.flashcards (user_id, mastery_status);

create table public.flashcard_reviews (
  id uuid primary key default gen_random_uuid(),
  flashcard_id uuid not null references public.flashcards (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  previous_status text not null,
  new_status text not null,
  reviewed_at timestamptz not null default now()
);
create index flashcard_reviews_card_idx on public.flashcard_reviews (flashcard_id, reviewed_at desc);

-- ---------------------------------------------------------------------------
-- study_activities (feeds Dashboard "Study Sessions" + "Recent Activity")
-- ---------------------------------------------------------------------------
create table public.study_activities (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  workspace_id uuid references public.workspaces (id) on delete cascade,
  activity_type text not null check (activity_type in
    ('chat', 'summary', 'quiz_generated', 'quiz_submitted', 'flashcards_generated', 'flashcard_review', 'document_uploaded')),
  description text not null,
  created_at timestamptz not null default now()
);
create index study_activities_user_idx on public.study_activities (user_id, created_at desc);

-- ---------------------------------------------------------------------------
-- ai_usage_events
-- ---------------------------------------------------------------------------
create table public.ai_usage_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  provider text not null,
  model text not null,
  operation text not null,
  input_tokens int not null default 0,
  output_tokens int not null default 0,
  estimated_cost numeric(12, 6) not null default 0,
  created_at timestamptz not null default now()
);
create index ai_usage_events_user_created_idx on public.ai_usage_events (user_id, created_at desc);

-- ---------------------------------------------------------------------------
-- Row Level Security
-- Content tables: the owner may read and write their own rows.
-- Integrity tables (scores, usage, activity log): the owner may only READ;
-- writes happen in the backend with the secret key and explicit user_id checks,
-- so a user cannot forge a quiz score or reset their AI quota through the public API.
-- ---------------------------------------------------------------------------
alter table public.profiles enable row level security;
create policy "profiles_select_own" on public.profiles for select to authenticated using (id = (select auth.uid()));
create policy "profiles_update_own" on public.profiles for update to authenticated
  using (id = (select auth.uid())) with check (id = (select auth.uid()));

do $$
declare t text;
begin
  foreach t in array array[
    'workspaces', 'documents', 'document_chunks', 'document_summaries', 'conversations', 'messages',
    'message_citations', 'quiz_sets', 'quiz_questions', 'flashcard_sets', 'flashcards', 'flashcard_reviews'
  ] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('create policy "%1$s_select_own" on public.%1$I for select to authenticated using (user_id = (select auth.uid()))', t);
    execute format('create policy "%1$s_insert_own" on public.%1$I for insert to authenticated with check (user_id = (select auth.uid()))', t);
    execute format('create policy "%1$s_update_own" on public.%1$I for update to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()))', t);
    execute format('create policy "%1$s_delete_own" on public.%1$I for delete to authenticated using (user_id = (select auth.uid()))', t);
  end loop;

  foreach t in array array['quiz_attempts', 'quiz_answers', 'study_activities', 'ai_usage_events'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('create policy "%1$s_select_own" on public.%1$I for select to authenticated using (user_id = (select auth.uid()))', t);
  end loop;
end $$;

-- Cross-table ownership: a child row must point at a parent the same user owns.
-- (RLS on the parent already hides foreign rows; these checks stop "attach my row to your workspace".)
create or replace function public.owns_workspace(ws uuid)
returns boolean language sql stable security invoker set search_path = '' as $$
  select exists (select 1 from public.workspaces w where w.id = ws and w.user_id = (select auth.uid()));
$$;

create policy "documents_parent_owned" on public.documents as restrictive for insert to authenticated
  with check (public.owns_workspace(workspace_id));
create policy "conversations_parent_owned" on public.conversations as restrictive for insert to authenticated
  with check (public.owns_workspace(workspace_id));
create policy "quiz_sets_parent_owned" on public.quiz_sets as restrictive for insert to authenticated
  with check (public.owns_workspace(workspace_id));
create policy "flashcard_sets_parent_owned" on public.flashcard_sets as restrictive for insert to authenticated
  with check (public.owns_workspace(workspace_id));

-- ---------------------------------------------------------------------------
-- Vector search. SECURITY INVOKER => RLS applies to the caller, and the
-- workspace filter is applied BEFORE ordering by distance (exact search).
-- ---------------------------------------------------------------------------
create or replace function public.match_chunks(
  query_embedding extensions.vector(768),
  p_workspace_id uuid,
  p_user_id uuid,
  match_count int default 5,
  p_document_ids uuid[] default null
)
returns table (
  id uuid,
  document_id uuid,
  chunk_index int,
  content text,
  page_number int,
  section_title text,
  filename text,
  similarity double precision
)
language sql stable security invoker set search_path = public, extensions as $$
  select c.id, c.document_id, c.chunk_index, c.content, c.page_number, c.section_title, d.filename,
         1 - (c.embedding <=> query_embedding) as similarity
  from public.document_chunks c
  join public.documents d on d.id = c.document_id
  where c.workspace_id = p_workspace_id
    and c.user_id = p_user_id
    and d.status = 'READY'
    and (p_document_ids is null or c.document_id = any (p_document_ids))
  order by c.embedding <=> query_embedding
  limit least(greatest(match_count, 1), 20);
$$;

-- ---------------------------------------------------------------------------
-- Storage: private bucket, path = {user_id}/{workspace_id}/{document_id}/{filename}
-- ---------------------------------------------------------------------------
insert into storage.buckets (id, name, public, file_size_limit)
values ('documents', 'documents', false, 20971520)
on conflict (id) do update set public = false, file_size_limit = excluded.file_size_limit;

create policy "documents_bucket_select_own" on storage.objects for select to authenticated
  using (bucket_id = 'documents' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy "documents_bucket_insert_own" on storage.objects for insert to authenticated
  with check (bucket_id = 'documents' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy "documents_bucket_delete_own" on storage.objects for delete to authenticated
  using (bucket_id = 'documents' and (storage.foldername(name))[1] = (select auth.uid())::text);
