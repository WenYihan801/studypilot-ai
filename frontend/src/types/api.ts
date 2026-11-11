// Mirrors backend/app/schemas/api.py

export type DocStatus = 'UPLOADED' | 'PROCESSING' | 'READY' | 'FAILED'
export type QuestionType = 'multiple_choice' | 'true_false' | 'short_answer'
export type Difficulty = 'easy' | 'medium' | 'hard' | 'mixed'
export type Mastery = 'NEW' | 'LEARNING' | 'MASTERED'

export interface Profile {
  id: string
  email: string | null
  display_name: string
  created_at: string | null
}

export interface Workspace {
  id: string
  name: string
  description: string
  document_count: number
  created_at: string
  updated_at: string
}

export interface DocumentItem {
  id: string
  workspace_id: string
  filename: string
  mime_type: string
  size_bytes: number
  sha256: string
  status: DocStatus
  page_count: number | null
  chunk_count: number
  error_message: string | null
  created_at: string
}

export interface Summary {
  overview: string
  main_topics: string[]
  key_concepts: { name: string; explanation: string }[]
  important_definitions: { term: string; definition: string }[]
  important_arguments: string[]
  key_takeaways: string[]
  revision_checklist: string[]
  source_references: { filename: string; location: string | null; chunk_ids: string[] }[]
}

export interface SummaryResponse {
  document_id: string
  summary: Summary
  model_name: string | null
  created_at: string
  cached: boolean
}

export interface Citation {
  label: string
  chunk_id: string
  document_id: string | null
  filename: string
  page_number: number | null
  section_title: string | null
  quote_text: string
  score: number | null
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  insufficient_evidence: boolean
  model_name: string | null
  created_at: string
  citations: Citation[]
}

export interface ChatResponse {
  conversation_id: string
  user_message: Message
  message: Message
  insufficient_evidence: boolean
}

export interface ConversationSummary {
  id: string
  workspace_id: string
  title: string
  created_at: string
  updated_at: string
}

export interface Conversation extends ConversationSummary {
  messages: Message[]
}

export interface QuizQuestion {
  id: string
  position: number
  type: QuestionType
  question: string
  options: string[]
  difficulty: string
}

export interface Quiz {
  id: string
  workspace_id: string
  title: string
  settings_json: Record<string, unknown>
  created_at: string
  questions: QuizQuestion[]
}

export interface QuizListItem {
  id: string
  title: string
  created_at: string
  question_count: number
  attempt_count: number
  best_score: number | null
}

export interface Attempt {
  id: string
  quiz_set_id: string
  score: number | null
  started_at: string
  submitted_at: string | null
}

export interface SourceRef {
  chunk_id: string
  filename: string | null
  page_number: number | null
  section_title?: string | null
  quote_text: string
}

export interface ResultItem {
  question_id: string
  position: number
  type: QuestionType
  question: string
  options: string[]
  difficulty: string
  your_answer: string
  is_correct: boolean
  feedback: string
  correct_answer: string
  explanation: string
  sources: SourceRef[]
}

export interface AttemptResult {
  attempt: Attempt
  quiz: { id: string; title: string; workspace_id?: string }
  items: ResultItem[]
}

export interface Flashcard {
  id: string
  set_id: string
  workspace_id: string
  position: number
  front: string
  back: string
  mastery_status: Mastery
  reviewed_at: string | null
  source: SourceRef | null
}

export interface FlashcardSetListItem {
  id: string
  title: string
  created_at: string
  card_count: number
  mastered_count: number
}

export interface FlashcardSet {
  id: string
  workspace_id: string
  title: string
  created_at: string
  cards: Flashcard[]
}

export interface Review {
  id: string
  flashcard_id: string
  previous_status: Mastery
  new_status: Mastery
  reviewed_at: string
}

export interface Activity {
  id: string
  workspace_id: string | null
  activity_type: string
  description: string
  created_at: string
}

export interface Dashboard {
  total_workspaces: number
  total_documents: number
  total_study_sessions: number
  total_quizzes: number
  average_quiz_score: number | null
  flashcards_to_review: number
  recent_activity: Activity[]
  activity_by_day: { date: string; count: number }[]
  quiz_scores: { attempt_id: string; title: string; score: number; submitted_at: string }[]
  flashcard_mastery: Record<Mastery, number>
}

export interface Usage {
  requests_today: number
  daily_limit: number
  tokens_today: number
  estimated_cost_30d: number
  by_operation: { operation: string; requests: number; input_tokens: number; output_tokens: number }[]
  by_day: { date: string; requests: number }[]
  provider: string
}
