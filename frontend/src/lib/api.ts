// Typed client for our FastAPI backend. Types come from the generated OpenAPI schema
// (npm run gen:api), so a renamed backend field breaks `npm run typecheck`.
import type { components } from '../api/schema';

export type S = components['schemas'];
export type CentreSummary = S['CentreSummary'];
export type CentreDetail = S['CentreDetail'];
export type StallSummary = S['StallSummary'];
export type StallDetail = S['StallDetail'];
export type DishAssessment = S['DishAssessment'];
export type DishList = S['DishListOut'];
export type Recommendation = S['RecommendationOut'];
export type Profile = S['ProfileOut'];
export type ProfileIn = S['ProfileIn'];
export type Favourite = S['FavouriteOut'];
export type Visit = S['VisitOut'];
export type Alert = S['AlertOut'];
export type Freshness = S['FreshnessOut'];
export type SearchResult = S['SearchOut'];
export type Geocode = S['GeocodeResult'];
export type Rule = S['RuleOut'];
export type Me = S['MeOut'];
export type SafeGrade = S['SafeGradeValue'];
export type Verdict = S['Verdict'];
export type CentreStatus = S['CentreStatus'];
export type Closure = S['ClosureOut'];

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '';

let tokenGetter: () => Promise<string | null> = async () => null;
export function setTokenGetter(fn: () => Promise<string | null>) {
  tokenGetter = fn;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

type Query = Record<string, string | number | boolean | string[] | null | undefined>;

function qs(params?: Query): string {
  if (!params) return '';
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === null || v === undefined || v === '') continue;
    if (Array.isArray(v)) v.forEach((x) => u.append(k, x));
    else u.set(k, String(v));
  }
  const s = u.toString();
  return s ? `?${s}` : '';
}

async function request<T>(method: string, path: string, opts: { query?: Query; body?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = { accept: 'application/json' };
  const token = await tokenGetter();
  if (token) headers.authorization = `Bearer ${token}`;
  if (opts.body !== undefined) headers['content-type'] = 'application/json';
  let res: Response;
  try {
    res = await fetch(`${BASE}/api${path}${qs(opts.query)}`, {
      method,
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check your connection and try again.");
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = (data as { detail?: unknown }).detail;
    const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? 'Some fields are invalid' : `Request failed (${res.status})`;
    throw new ApiError(res.status, msg);
  }
  return data as T;
}

export const api = {
  freshness: () => request<Freshness>('GET', '/meta/freshness'),
  regions: () => request<string[]>('GET', '/regions'),
  centres: (q: Query = {}) => request<CentreSummary[]>('GET', '/centres', { query: q }),
  // An <img> src, not a request: the backend fetches NEA's photo so the browser never calls NEA (NFR-5)
  centrePhotoUrl: (id: number) => `${BASE}/api/centres/${id}/photo`,
  // halalOnly null/undefined: the backend follows the signed-in user's HALAL restriction
  centre: (id: number, minGrade?: SafeGrade | null, halalOnly?: boolean | null) =>
    request<CentreDetail>('GET', `/centres/${id}`, { query: { min_grade: minGrade, halal_only: halalOnly } }),
  stall: (id: number) => request<StallDetail>('GET', `/stalls/${id}`),
  search: (q: string) => request<SearchResult>('GET', '/search', { query: { q } }),
  dishes: (conditions?: string[], restrictions?: string[]) =>
    request<DishList>('GET', '/dishes', { query: { conditions, restrictions } }),
  rules: () => request<Rule[]>('GET', '/rules'),
  hdpNote: () => request<string>('GET', '/hdp-note'),
  recommendations: (lat?: number, lng?: number) =>
    request<Recommendation>('GET', '/recommendations', { query: { lat, lng } }),
  geocode: (q: string) => request<Geocode[]>('GET', '/geocode', { query: { q } }),

  me: () => request<Me>('GET', '/me'),
  profile: () => request<Profile | null>('GET', '/me/profile'),
  saveProfile: (p: ProfileIn) => request<Profile>('PUT', '/me/profile', { body: p }),
  favourites: () => request<Favourite[]>('GET', '/me/favourites'),
  addFavourite: (target_type: S['FavouriteTarget'], target_id: number) =>
    request<Favourite>('POST', '/me/favourites', { body: { target_type, target_id } }),
  removeFavourite: (id: number) => request<void>('DELETE', `/me/favourites/${id}`),
  visits: () => request<Visit[]>('GET', '/me/visits'),
  addVisit: (v: S['VisitIn']) => request<Visit>('POST', '/me/visits', { body: v }),
  alerts: () => request<Alert[]>('GET', '/me/alerts'),
  readAlert: (id: number) => request<void>('POST', `/me/alerts/${id}/read`),
};
