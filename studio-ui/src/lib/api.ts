// Typed API client. All requests are same-origin (served by the parent Python server
// at http://localhost:4318). Mutations carry the X-CSRF-Token from GET /api/state.
// No fake data: every method hits a real endpoint described in the API contract.

import type { Plan } from './timeline';
import {fromWirePlan,toWirePlan} from './wire';
import type {WirePlan} from './wire';

export interface ProjectSummary {
  id: string;
  name: string;
  revision: number;
  updated_at: string;
}

export interface Asset {
  id: string;
  name: string;
  path: string;
  duration: number;
  width: number;
  height: number;
  has_audio: boolean;
  url: string;
}

export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed';
export type JobKind = 'draft' | 'final';

export interface Job {
  id: string;
  status: JobStatus;
  project_id: string;
  revision: number;
  kind: JobKind;
  result_url: string | null;
  error: string | null;
  created_at: string;
}

export interface AppState {
  csrf: string;
  projects: ProjectSummary[];
  assets: Asset[];
  jobs: Job[];
}

export interface HistoryEntry {
  revision: number;
  label: string;
  created_at: string;
}

export interface Project {
  id: string;
  name: string;
  revision: number;
  plan: Plan;
  history: HistoryEntry[];
  can_undo: boolean;
  can_redo: boolean;
}

/** Raised on any non-2xx. `stale` is true for HTTP 409 (revision conflict). */
export class ApiError extends Error {
  status: number;
  stale: boolean;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.stale = status === 409;
  }
}

async function parse<T>(res: Response): Promise<T> {
  const text = await res.text();
  let body: any = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = null;
    }
  }
  if (!res.ok) {
    const msg = (body && typeof body.error === 'string' && body.error) || res.statusText || `HTTP ${res.status}`;
    throw new ApiError(msg, res.status);
  }
  return body as T;
}

export class StudioApi {
  private csrf = '';
  private assets: Asset[] = [];

  private async projectResponse(res: Response): Promise<Project> {
    const raw = await parse<Omit<Project,'plan'> & {plan: WirePlan}>(res);
    return {...raw,plan:fromWirePlan(raw.plan,this.assets)};
  }

  setCsrf(token: string): void {
    this.csrf = token;
  }

  private headers(json = true): HeadersInit {
    const h: Record<string, string> = {};
    if (json) h['Content-Type'] = 'application/json';
    if (this.csrf) h['X-CSRF-Token'] = this.csrf;
    return h;
  }

  async getState(): Promise<AppState> {
    const state = await parse<AppState>(await fetch('/api/state', { headers: { Accept: 'application/json' } }));
    this.csrf = state.csrf;
    this.assets = state.assets;
    return state;
  }

  async getProject(id: string): Promise<Project> {
    return this.projectResponse(await fetch(`/api/projects/${encodeURIComponent(id)}`, { headers: { Accept: 'application/json' } }));
  }

  async createProject(name: string): Promise<Project> {
    return this.projectResponse(
      await fetch('/api/projects', {
        method: 'POST',
        headers: this.headers(),
        body: JSON.stringify({ name }),
      }),
    );
  }

  async saveProject(
    id: string,
    body: { name: string; plan: Plan; expected_revision: number; label: string },
  ): Promise<Project> {
    return this.projectResponse(
      await fetch(`/api/projects/${encodeURIComponent(id)}`, {
        method: 'PUT',
        headers: this.headers(),
        body: JSON.stringify({...body,plan:toWirePlan(body.plan,this.assets)}),
      }),
    );
  }

  async undo(id: string, expected_revision: number): Promise<Project> {
    return this.projectResponse(
      await fetch(`/api/projects/${encodeURIComponent(id)}/undo`, {
        method: 'POST',
        headers: this.headers(),
        body: JSON.stringify({ expected_revision }),
      }),
    );
  }

  async redo(id: string, expected_revision: number): Promise<Project> {
    return this.projectResponse(
      await fetch(`/api/projects/${encodeURIComponent(id)}/redo`, {
        method: 'POST',
        headers: this.headers(),
        body: JSON.stringify({ expected_revision }),
      }),
    );
  }

  async render(id: string, kind: JobKind, expected_revision: number): Promise<Job> {
    return parse<Job>(
      await fetch(`/api/projects/${encodeURIComponent(id)}/render`, {
        method: 'POST',
        headers: this.headers(),
        body: JSON.stringify({ kind, expected_revision }),
      }),
    );
  }

  /** Upload a video as raw binary. Filename travels in the X-Filename header,
   *  URI-encoded so arbitrary names never break the header. Returns the new Asset. */
  async uploadAsset(file: File): Promise<Asset> {
    const h: Record<string, string> = {
      'Content-Type': 'application/octet-stream',
      'X-Filename': encodeURIComponent(file.name),
    };
    if (this.csrf) h['X-CSRF-Token'] = this.csrf;
    return parse<Asset>(await fetch('/api/assets', { method: 'POST', headers: h, body: file }));
  }
}

export const api = new StudioApi();
