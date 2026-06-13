/* TypeScript types mirroring backend Pydantic schemas */

export interface User {
  id: string;
  name: string;
  email: string | null;
  goal: string | null;
  created_at: string;
}

export interface UserCreate {
  name: string;
  email?: string;
  goal?: string;
}

export interface SkillProfile {
  id: string;
  user_id: string;
  raw_skills: string[];
  embedding_updated_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface MissingSkill {
  skill: string;
  priority: 'high' | 'medium' | 'low';
  reason: string;
}

export interface RoadmapStep {
  week: number;
  title: string;
  tasks: string[];
  resources: string[];
}

export interface GapAnalysis {
  missing_skills: MissingSkill[];
  match_score: number;
  strengths: string[];
}

export interface Opportunity {
  id: string;
  title: string;
  company: string;
  location: string;
  type: string;
  skills_required: string[];
  description: string | null;
  url: string | null;
  stipend: string | null;
  deadline: string | null;
  created_at: string;
  match_score?: number;
}

export interface OpportunityCreate {
  title: string;
  company: string;
  location: string;
  type: string;
  skills_required: string[];
  description?: string;
  url?: string;
  stipend?: string;
  deadline?: string;
}

export type AppStatus = 'wishlist' | 'applied' | 'interviewing' | 'offer' | 'rejected';

export interface Application {
  id: string;
  user_id: string;
  opportunity_id: string | null;
  company: string;
  role: string;
  status: AppStatus;
  notes: string | null;
  applied_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApplicationCreate {
  user_id: string;
  company: string;
  role: string;
  status?: AppStatus;
  notes?: string;
  opportunity_id?: string;
}

export interface ApplicationUpdate {
  status?: AppStatus;
  notes?: string;
}

export interface ChatRequest {
  user_id: string;
  message: string;
}

export interface ChatResponse {
  response: string;
  intent: string;
  memory_used: number;
}

export interface SSEEvent {
  type: 'progress' | 'token' | 'done' | 'error';
  node?: string;
  chunk?: string;
  message?: string;
}

export interface SearchRequest {
  query: string;
  user_id?: string;
  limit?: number;
}
