// UC-6.0 Dish Recommendation, with the rules shown openly (traceability, NFR-6)
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import BookmarkButton from '../components/BookmarkButton';
import { VerdictBadge } from '../components/badges';
import { ErrorBox, Loading, PageHeader } from '../components/common';
import { DishPhotoCredit, DishThumb } from '../components/DishPhoto';
import Icon from '../components/Icon';
import { api, type DishAssessment, type Verdict } from '../lib/api';
import { useAuth } from '../lib/auth';
import { CONDITIONS, NUTRIENT_LABEL, RESTRICTIONS, VERDICT } from '../lib/labels';
import { useApi } from '../lib/useApi';

const GROUPS: Verdict[] = ['SUITABLE', 'MODERATE', 'INSUFFICIENT_DATA', 'AVOID'];

function Toggle({ on, label, onClick }: { on: boolean; label: string; onClick: () => void }) {
  return (
    <button onClick={onClick} aria-pressed={on} className={`chip border py-1 text-sm ${on ? 'border-brand-700 bg-brand-700 text-white' : 'border-stone-300 dark:border-stone-700'}`}>
      {on && <Icon name="check" className="size-3.5" />} {label}
    </button>
  );
}

function DishCard({ d, open, onToggle }: { d: DishAssessment; open: boolean; onToggle: () => void }) {
  const n = d.nutrients;
  return (
    <div className="card p-3" id={`dish-${d.id}`}>
      <div className="flex items-center gap-2">
        <button className="flex min-w-0 flex-1 items-center gap-3 text-left" onClick={onToggle} aria-expanded={open}>
          <DishThumb name={d.dish_name} className="size-14" />
          <span className="min-w-0 flex-1">
            <span className="block truncate font-medium">{d.dish_name}</span>
            <span className="text-xs text-stone-500">
              {d.category}
              {n.sodium_mg != null && ` · ${n.sodium_mg.toLocaleString()} mg sodium`}
              {d.serving_g != null && ` · ${d.serving_g} g serving`}
            </span>
          </span>
          <VerdictBadge verdict={d.verdict} />
          <Icon name="chevron" className={`size-4 shrink-0 text-stone-400 transition ${open ? 'rotate-90' : ''}`} />
        </button>
        <BookmarkButton type="DISH" id={d.id} compact />
      </div>
      {open && (
        <div className="mt-3 border-t border-stone-100 pt-3 text-sm dark:border-stone-800">
          <DishPhotoCredit name={d.dish_name} />
          <dl className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-5">
            {Object.entries(n).map(([k, v]) => (
              <div key={k}>
                <dt className="text-xs text-stone-500">{NUTRIENT_LABEL[k]}</dt>
                <dd className={v == null ? 'text-stone-400' : 'font-medium'}>{v == null ? 'no data' : v.toLocaleString()}</dd>
              </div>
            ))}
          </dl>
          <h4 className="mb-1 mt-3 font-semibold">Why</h4>
          <ul className="space-y-1.5">
            {d.findings.map((f, i) => (
              <li key={i} className="flex gap-2">
                <span className="mt-0.5 shrink-0">{f.verdict ? <VerdictBadge verdict={f.verdict} /> : <span className="chip bg-stone-100 dark:bg-stone-800">Gap</span>}</span>
                <span>
                  {f.message}
                  {f.rule_id !== '-' && <span className="text-stone-400"> · {f.rule_id}</span>}
                  {f.citation && <span className="block text-xs text-stone-500">{f.citation}</span>}
                </span>
              </li>
            ))}
          </ul>
          {d.unchecked_conditions.length > 0 && (
            <p className="mt-2 text-xs text-amber-700 dark:text-amber-400">Couldn’t check for: {d.unchecked_conditions.join(', ').toLowerCase().replace('_', ' ')} (missing nutrient data).</p>
          )}
          <p className="mt-2 text-xs text-stone-500">Source: {d.source}</p>
        </div>
      )}
    </div>
  );
}

export default function Dishes() {
  const { me } = useAuth();
  const [params] = useSearchParams();
  const focus = params.get('focus');
  const [conditions, setConditions] = useState<string[] | null>(null); // null = use saved profile
  const [restrictions, setRestrictions] = useState<string[] | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [showRules, setShowRules] = useState(false);

  const list = useApi(() => api.dishes(conditions ?? undefined, restrictions ?? undefined), [conditions?.join(), restrictions?.join(), me?.id]);
  const rules = useApi(() => (showRules ? api.rules() : Promise.resolve([])), [showRules]);

  const activeC = conditions ?? list.data?.conditions ?? [];
  const activeR = restrictions ?? list.data?.restrictions ?? [];
  const flip = (arr: string[], v: string) => (arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);

  useEffect(() => {
    if (!focus || !list.data) return;
    const d = list.data.dishes.find((x) => x.dish_name === focus);
    if (d) {
      setOpenId(d.id);
      setTimeout(() => document.getElementById(`dish-${d.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50);
    }
  }, [focus, list.data]);

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Dishes for you" subtitle="Common hawker dishes rated against HPB guidance and your health profile." />

      <div className="card mb-4 space-y-3 p-4">
        <div>
          <p className="mb-2 text-sm font-medium">Health conditions {me && conditions === null && <span className="font-normal text-stone-500">(from your profile)</span>}</p>
          <div className="flex flex-wrap gap-2">
            {CONDITIONS.map((c) => (
              <Toggle key={c.value} label={c.label} on={activeC.includes(c.value)} onClick={() => setConditions(flip(activeC, c.value))} />
            ))}
          </div>
        </div>
        <div>
          <p className="mb-2 text-sm font-medium">Dietary restrictions</p>
          <div className="flex flex-wrap gap-2">
            {RESTRICTIONS.filter((r) => !r.stallsOnly).map((r) => (
              <Toggle key={r.value} label={r.label} on={activeR.includes(r.value)} onClick={() => setRestrictions(flip(activeR, r.value))} />
            ))}
          </div>
          <p className="mt-2 text-xs text-stone-500">Based on typical recipes. Halal is a stall-level filter (in your profile), using HPB’s listing where a stall has one.</p>
        </div>
      </div>

      {list.error && <ErrorBox message={list.error} onRetry={list.reload} />}
      {!list.data && <Loading />}
      {list.data && list.data.dishes.length === 0 && (
        <div className="card p-6 text-center">
          No dishes match all selected constraints.
          <button className="btn-ghost mt-3" onClick={() => setRestrictions([])}>
            Expand search
          </button>
        </div>
      )}

      {list.data &&
        GROUPS.map((v) => {
          const items = list.data!.dishes.filter((d) => d.verdict === v);
          if (!items.length) return null;
          return (
            <section key={v} className="mb-5">
              <h2 className="mb-2 flex items-center gap-2 font-semibold">
                <VerdictBadge verdict={v} /> <span className="text-sm font-normal text-stone-500">{items.length} dishes · {VERDICT[v].hint.toLowerCase()}</span>
              </h2>
              <div className="space-y-2">
                {items.map((d) => (
                  <DishCard key={d.id} d={d} open={openId === d.id} onToggle={() => setOpenId(openId === d.id ? null : d.id)} />
                ))}
              </div>
            </section>
          );
        })}

      {list.data && (
        <p className="text-xs text-stone-500">
          {list.data.excluded_by_restriction > 0 && `${list.data.excluded_by_restriction} dishes hidden by your restrictions. `}
          {list.data.disclaimer}
        </p>
      )}

      <div className="mt-6">
        <button className="btn-ghost text-sm" onClick={() => setShowRules(!showRules)} aria-expanded={showRules}>
          <Icon name="info" className="size-4" /> How we rate dishes
        </button>
        {showRules && rules.data && (
          <div className="card mt-3 overflow-x-auto p-0">
            <table className="w-full text-left text-sm">
              <thead className="bg-stone-100 text-xs uppercase text-stone-500 dark:bg-stone-800">
                <tr>
                  <th className="px-3 py-2">Rule</th>
                  <th className="px-3 py-2">Applies to</th>
                  <th className="px-3 py-2">If</th>
                  <th className="px-3 py-2">Then</th>
                  <th className="px-3 py-2">Basis</th>
                </tr>
              </thead>
              <tbody>
                {rules.data.map((r) => (
                  <tr key={r.rule_id} className="border-t border-stone-100 align-top dark:border-stone-800">
                    <td className="px-3 py-2 font-mono text-xs">{r.rule_id}</td>
                    <td className="px-3 py-2">{r.condition.toLowerCase().replace('_', ' ')}</td>
                    <td className="whitespace-nowrap px-3 py-2">
                      {NUTRIENT_LABEL[r.nutrient]} {r.operator} {r.threshold} {r.unit}
                    </td>
                    <td className="px-3 py-2">
                      <VerdictBadge verdict={r.verdict} />
                    </td>
                    <td className="px-3 py-2 text-xs text-stone-500">
                      {r.status === 'draft' && <span className="chip mr-1 bg-amber-100 text-amber-900">draft</span>}
                      {r.citation}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
