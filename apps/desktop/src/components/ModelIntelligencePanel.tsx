import { useCallback, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

export type ModelPolicy =
  | "auto"
  | "balanced"
  | "maximum_quality"
  | "maximum_privacy"
  | "low_latency"
  | "pinned";

type RecommendResult = {
  ok: boolean;
  policy?: string;
  error?: string | null;
  recommendation?: {
    explanation?: string;
    winners?: Record<
      string,
      {
        display_name?: string;
        digest?: string;
        score?: number;
        license?: string;
        expected_memory_mb?: number;
        context_length?: number;
        why?: string[];
      }
    >;
    alternatives?: Array<{ display_name?: string; digest?: string; score?: number; license?: string }>;
    rejected?: Array<{ display_name?: string; reasons?: string[] }>;
    hardware_summary?: Record<string, unknown>;
    registry_digest?: string;
    pins?: Record<string, { provider: string; name: string; digest: string }>;
  };
  pin_resolution?: {
    pins?: Record<string, unknown>;
    changed?: boolean;
    reason?: string;
    notification?: string;
  };
};

const POLICIES: { id: ModelPolicy; label: string }[] = [
  { id: "auto", label: "Auto" },
  { id: "balanced", label: "Balanced" },
  { id: "maximum_quality", label: "Maximum quality" },
  { id: "maximum_privacy", label: "Maximum privacy" },
  { id: "low_latency", label: "Low latency" },
  { id: "pinned", label: "Pinned" },
];

type Props = {
  compact?: boolean;
};

export default function ModelIntelligencePanel({ compact = false }: Props) {
  const [policy, setPolicy] = useState<ModelPolicy>("auto");
  const [vision, setVision] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [card, setCard] = useState<RecommendResult | null>(null);

  const runRecommend = useCallback(async () => {
    setBusy(true);
    setErr("");
    try {
      const result = await invoke<RecommendResult>("model_recommend", {
        policy,
        requirements: {
          json_schema: true,
          vision,
          modalities: vision ? ["text", "vision"] : ["text"],
          min_context: 4096,
        },
      });
      setCard(result);
      if (!result.ok) {
        setErr(result.error || "Selection failed (fail-closed)");
      }
    } catch (e) {
      setErr(String(e));
      setCard(null);
    } finally {
      setBusy(false);
    }
  }, [policy, vision]);

  const winners = card?.recommendation?.winners || {};

  return (
    <section className={`panel model-intel${compact ? " compact" : ""}`} aria-labelledby="model-intel-h">
      <h2 id="model-intel-h">Model intelligence</h2>
      <p className="muted">
        Transparent recommendation card — digests, license, fit, and alternatives. Pins freeze for
        runs; Auto never silently swaps mid-run.
      </p>

      <div className="model-intel-controls">
        <label className="field">
          <span>Policy</span>
          <select
            value={policy}
            onChange={(e) => setPolicy(e.target.value as ModelPolicy)}
            disabled={busy}
          >
            {POLICIES.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={vision}
            onChange={(e) => setVision(e.target.checked)}
            disabled={busy}
          />
          Require vision
        </label>
        <button type="button" className="primary" onClick={runRecommend} disabled={busy}>
          {busy ? "Scoring…" : "Recommend"}
        </button>
      </div>

      {err ? (
        <p className="error" role="alert">
          {err}
        </p>
      ) : null}

      {card?.recommendation ? (
        <div className="rec-card" role="region" aria-label="Model recommendation">
          <p className="rec-expl">{card.recommendation.explanation}</p>
          {card.pin_resolution?.notification ? (
            <p className="warn" role="status">
              {card.pin_resolution.notification}
            </p>
          ) : null}
          <ul className="rec-winners">
            {Object.entries(winners).map(([role, w]) => (
              <li key={role}>
                <strong>{role}</strong>: {w.display_name}{" "}
                <code title={w.digest}>{w.digest}</code>
                {w.license ? ` · ${w.license}` : ""}
                {typeof w.score === "number" ? ` · score ${w.score.toFixed(3)}` : ""}
                {w.expected_memory_mb != null ? ` · ~${Math.round(w.expected_memory_mb)} MB` : ""}
                {w.why?.length ? (
                  <ul className="rec-why">
                    {w.why.map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                ) : null}
              </li>
            ))}
          </ul>
          {card.recommendation.alternatives?.length ? (
            <details>
              <summary>Alternatives</summary>
              <ul>
                {card.recommendation.alternatives.map((a) => (
                  <li key={a.digest || a.display_name}>
                    {a.display_name} <code>{a.digest}</code>
                    {a.license ? ` · ${a.license}` : ""}
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
          {card.recommendation.rejected?.length ? (
            <details>
              <summary>Rejected (gates)</summary>
              <ul>
                {card.recommendation.rejected.map((r) => (
                  <li key={r.display_name}>
                    {r.display_name}: {(r.reasons || []).join("; ")}
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
          {card.recommendation.registry_digest ? (
            <p className="muted">
              Registry <code>{card.recommendation.registry_digest}</code>
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
