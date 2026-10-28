import type { S, SafeGrade, Verdict } from './api';

// Display wording. Softer verdict labels from UC-4.1 so we don't overstate (NFR-6).
export const VERDICT: Record<Verdict, { label: string; cls: string; hint: string }> = {
  SUITABLE: { label: 'Good choice', cls: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-200', hint: 'Within all thresholds that apply to you' },
  MODERATE: { label: 'Have in moderation', cls: 'bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200', hint: 'Above a threshold that applies to you' },
  AVOID: { label: 'Have occasionally', cls: 'bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-200', hint: 'Well above a threshold that applies to you' },
  INSUFFICIENT_DATA: { label: 'Not enough data', cls: 'bg-stone-200 text-stone-700 dark:bg-stone-800 dark:text-stone-300', hint: 'We don’t have the nutrient values to check this for you yet' },
};

// FR-2.2: NEW must look different from C, and not like a failing grade
export const GRADE: Record<SafeGrade, { label: string; cls: string; hint: string }> = {
  A: { label: 'A', cls: 'bg-emerald-600 text-white', hint: 'No major lapse for over 3 years' },
  B: { label: 'B', cls: 'bg-teal-500 text-white', hint: 'No major lapse for 1 to 3 years' },
  C: { label: 'C', cls: 'bg-orange-600 text-white', hint: 'Had a major lapse (suspension or conviction)' },
  NEW: { label: 'NEW', cls: 'bg-sky-100 text-sky-800 ring-1 ring-sky-300 dark:bg-sky-900/50 dark:text-sky-200 dark:ring-sky-700', hint: 'Open less than a year, no track record yet. Not a failing grade.' },
};

export const CONDITIONS: { value: S['ProfileIn']['health_conditions'][number]; label: string }[] = [
  { value: 'HYPERTENSION', label: 'High blood pressure' },
  { value: 'DIABETES', label: 'Diabetes' },
  { value: 'HIGH_CHOLESTEROL', label: 'High cholesterol' },
];

// stallsOnly: filters stalls, not dishes (no dish data says whether a dish is halal)
export const RESTRICTIONS: { value: S['ProfileIn']['dietary_restrictions'][number]; label: string; stallsOnly?: boolean }[] = [
  { value: 'NO_PORK', label: 'No pork' },
  { value: 'NO_BEEF', label: 'No beef' },
  { value: 'VEGETARIAN', label: 'Vegetarian' },
  { value: 'HALAL', label: 'Halal (stalls with confirmed status only)', stallsOnly: true },
];

// Unknown halal status is the norm, so say so wherever the filter hides stalls
export const halalNote = (shown: number, confirmed = shown) =>
  `Showing ${shown === confirmed ? '' : `${shown} of `}${confirmed} ${confirmed === 1 ? 'stall' : 'stalls'} with confirmed halal status. Most stalls haven’t published this yet.`;

// HPB lists endorsement criteria as one comma-separated string, sometimes with repeats
export const hdpCriteria = (category: string | null | undefined) => [
  ...new Set((category ?? '').split(/[,;]/).map((c) => c.trim()).filter(Boolean)),
];

export const PREFERENCES: { value: S['ProfileIn']['dietary_preferences'][number]; label: string }[] = [
  { value: 'HEALTHIER_CHOICE', label: 'Prefer Healthier Dining stalls' },
  { value: 'LOWER_SODIUM', label: 'Lower sodium first' },
];

export const THRESHOLDS: { value: SafeGrade | null; label: string }[] = [
  { value: null, label: 'Any grade' },
  { value: 'NEW', label: 'A, B or NEW' },
  { value: 'B', label: 'A or B' },
  { value: 'A', label: 'A only' },
];

export const REASON_LABEL: Record<S['ClosureReasonType'], string> = {
  SPRING_CLEANING: 'Spring cleaning',
  REPAIRS_AND_REDECORATION: 'Repairs & redecoration',
  OTHER_WORKS: 'Other works',
};

export const NUTRIENT_LABEL: Record<string, string> = {
  energy_kcal: 'Energy',
  sodium_mg: 'Sodium',
  sugar_g: 'Sugar',
  saturated_fat_g: 'Saturated fat',
  protein_g: 'Protein',
};

export const fmtDate = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('en-SG', { day: 'numeric', month: 'short' });

export const fmtDateTime = (iso: string) =>
  new Date(iso).toLocaleString('en-SG', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' });
