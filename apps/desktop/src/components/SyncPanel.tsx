import { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

type AuthStatus = {
  authenticated: boolean;
  method?: string | null;
  login?: string | null;
  token_hint?: string | null;
};

type ConflictItem = {
  path: string;
  kind: string;
  base?: string | null;
  local?: string | null;
  remote?: string | null;
  unresolved_ids: string[];
  recovery_local?: string | null;
  recovery_remote?: string | null;
};

type HistoryEvent = {
  id: string;
  at: string;
  kind: string;
  detail: string;
  ok: boolean;
};

type QueuedCommit = {
  id: string;
  summary: string;
  created_at: string;
  paths: string[];
};

type PreflightWarning = {
  path: string;
  kind: string;
  detail: string;
};

type SyncStatus = {
  state: string;
  auth: AuthStatus;
  remote_url?: string | null;
  last_error?: string | null;
  last_success_at?: string | null;
  offline_queue: QueuedCommit[];
  history: HistoryEvent[];
  conflicts: ConflictItem[];
  preflight: PreflightWarning[];
  recovery_notes: string[];
  debounce_ms: number;
  backoff_ms: number;
};

type Props = {
  vaultOpen: boolean;
};

export default function SyncPanel({ vaultOpen }: Props) {
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [pat, setPat] = useState("");
  const [repoName, setRepoName] = useState("brainflow-vault");
  const [cloneUrl, setCloneUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [deviceUserCode, setDeviceUserCode] = useState<string | null>(null);
  const [deviceUri, setDeviceUri] = useState<string | null>(null);
  const [resolveChoice, setResolveChoice] = useState<Record<string, "local" | "remote">>({});

  const refresh = useCallback(async () => {
    if (!vaultOpen) {
      setStatus(null);
      return;
    }
    try {
      const s = await invoke<SyncStatus>("sync_status");
      setStatus(s);
      setError("");
    } catch (e) {
      setError(String(e));
    }
  }, [vaultOpen]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onSetPat() {
    setBusy(true);
    setError("");
    try {
      await invoke("sync_set_pat", { token: pat, login: null });
      setPat("");
      setMessage("Token stored in OS credential store (not the vault).");
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onDeviceFlow() {
    setBusy(true);
    setError("");
    try {
      const code = await invoke<{
        device_code: string;
        user_code: string;
        verification_uri: string;
        interval: number;
      }>("sync_begin_device_flow");
      setDeviceUserCode(code.user_code);
      setDeviceUri(code.verification_uri);
      setMessage(`Visit ${code.verification_uri} and enter ${code.user_code}`);
      await invoke("sync_poll_device_flow", {
        deviceCode: code.device_code,
        intervalSecs: code.interval || 5,
      });
      setMessage("Device flow complete — token in OS credential store.");
      setDeviceUserCode(null);
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onClone() {
    setBusy(true);
    setError("");
    try {
      await invoke("sync_configure_clone", { url: cloneUrl });
      setMessage("Repository linked (clone / existing).");
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onCreatePrivate() {
    setBusy(true);
    setError("");
    try {
      const res = await invoke<{ status: SyncStatus; remote?: { full_name: string; html_url: string } }>(
        "sync_configure_create",
        { name: repoName },
      );
      setStatus(res.status);
      setMessage(
        res.remote
          ? `Created private repo ${res.remote.full_name}`
          : "Private repo configured.",
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onSyncNow(offline = false) {
    setBusy(true);
    setError("");
    try {
      const s = await invoke<SyncStatus>("sync_run_now", { offline });
      setStatus(s);
      setMessage(offline ? "Offline queue updated." : `Sync finished: ${s.state}`);
    } catch (e) {
      setError(String(e));
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  async function onResolve() {
    if (!status?.conflicts.length) return;
    const missing = status.conflicts.filter((c) => !resolveChoice[c.path]);
    if (missing.length) {
      setError(
        `Choose Local or Remote for every conflict before applying (${missing.map((m) => m.path).join(", ")}).`,
      );
      return;
    }
    setBusy(true);
    setError("");
    try {
      const resolutions = status.conflicts.map((c) => {
        const side = resolveChoice[c.path] ?? "local";
        const content = side === "remote" ? c.remote ?? "" : c.local ?? "";
        return { path: c.path, content };
      });
      const s = await invoke<SyncStatus>("sync_resolve_conflicts", { resolutions });
      setStatus(s);
      setResolveChoice({});
      setMessage("Conflicts resolved — sync resumed. Recovery copies remain until you delete them.");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onLogout() {
    setBusy(true);
    try {
      await invoke("sync_logout");
      setMessage("Cleared GitHub token from OS credential store.");
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  if (!vaultOpen) {
    return (
      <section className="panel sync-panel" aria-labelledby="sync-heading">
        <h2 id="sync-heading">GitHub Sync</h2>
        <p className="muted-copy">Open a vault to configure sync. Sync is not an AI tool.</p>
      </section>
    );
  }

  const auth = status?.auth;
  const history = [...(status?.history ?? [])].reverse().slice(0, 12);

  return (
    <section className="panel sync-panel" aria-labelledby="sync-heading">
      <h2 id="sync-heading">GitHub Sync</h2>
      <p className="muted-copy">
        Non-destructive commit → fetch → integrate → validate → push. Never auto force-push. Tokens
        stay in the OS credential store.
      </p>

      <div className="sync-status-row" role="status">
        <span>
          State: <code>{status?.state ?? "…"}</code>
        </span>
        <span>
          Auth:{" "}
          <code>
            {auth?.authenticated
              ? `${auth.token_hint ?? "****"} (${auth.method ?? "token"})`
              : "not signed in"}
          </code>
        </span>
        {status?.remote_url ? (
          <span className="path">{status.remote_url}</span>
        ) : (
          <span className="muted-copy">No remote yet</span>
        )}
      </div>

      {status?.recovery_notes?.length ? (
        <div className="warn" role="status">
          <strong>Recovery</strong>
          <ul>
            {status.recovery_notes.map((n) => (
              <li key={n.slice(0, 48)}>{n}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {status?.preflight?.length ? (
        <div className="warn" role="status">
          <strong>Preflight</strong>
          <ul>
            {status.preflight.map((w) => (
              <li key={`${w.path}-${w.kind}`}>
                <code>{w.path}</code> — {w.kind}: {w.detail}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <h3>Authenticate</h3>
      <label className="field">
        <span>Personal access token (repo scope)</span>
        <input
          type="password"
          value={pat}
          onChange={(e) => setPat(e.target.value)}
          placeholder="ghp_… or fine-grained token"
          autoComplete="off"
        />
      </label>
      <div className="actions">
        <button type="button" onClick={() => void onSetPat()} disabled={busy || !pat.trim()}>
          Store PAT in OS keychain
        </button>
        <button type="button" onClick={() => void onDeviceFlow()} disabled={busy}>
          Device flow (OAuth App)
        </button>
        <button type="button" className="ghost" onClick={() => void onLogout()} disabled={busy}>
          Clear token
        </button>
      </div>
      {deviceUserCode ? (
        <p className="status">
          Enter code <code>{deviceUserCode}</code> at {deviceUri}
        </p>
      ) : null}

      <h3>Repository</h3>
      <label className="field">
        <span>Clone / link existing URL</span>
        <input
          value={cloneUrl}
          onChange={(e) => setCloneUrl(e.target.value)}
          placeholder="https://github.com/you/vault.git"
        />
      </label>
      <div className="actions">
        <button type="button" onClick={() => void onClone()} disabled={busy || !cloneUrl.trim()}>
          Link existing
        </button>
      </div>
      <label className="field">
        <span>Create private repo</span>
        <input value={repoName} onChange={(e) => setRepoName(e.target.value)} />
      </label>
      <div className="actions">
        <button type="button" onClick={() => void onCreatePrivate()} disabled={busy || !repoName.trim()}>
          Create private on GitHub
        </button>
      </div>

      <h3>Sync</h3>
      <div className="actions">
        <button type="button" className="primary" onClick={() => void onSyncNow(false)} disabled={busy}>
          Sync now
        </button>
        <button type="button" onClick={() => void onSyncNow(true)} disabled={busy}>
          Queue offline
        </button>
        <button type="button" className="ghost" onClick={() => void refresh()} disabled={busy}>
          Refresh status
        </button>
      </div>

      {status?.offline_queue?.length ? (
        <div>
          <h3>Offline queue</h3>
          <ul className="sync-list">
            {status.offline_queue.map((q) => (
              <li key={q.id}>
                <code>{q.summary}</code> · {q.paths.length} paths
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {status?.conflicts?.length ? (
        <div className="conflict-box" role="region" aria-labelledby="sync-conflicts-heading">
          <h3 id="sync-conflicts-heading">Conflicts — resolve before push</h3>
          <p className="muted-copy">
            Background sync is paused. Pick <strong>this device (Local)</strong> or{" "}
            <strong>GitHub (Remote)</strong> for each file. Recovery copies stay under{" "}
            <code>.brainflow/local/sync/recovery/</code> so neither side is silently lost.
          </p>
          {status.conflicts.map((c) => {
            const chosen = resolveChoice[c.path];
            return (
              <div key={c.path} className="conflict-item">
                <div className="conflict-meta">
                  <code>{c.path}</code>
                  <span className="muted-copy"> · {c.kind}</span>
                  {c.unresolved_ids?.length ? (
                    <span className="muted-copy">
                      {" "}
                      · unresolved ids: {c.unresolved_ids.join(", ")}
                    </span>
                  ) : null}
                </div>
                {(c.recovery_local || c.recovery_remote) && (
                  <p className="muted-copy conflict-recovery">
                    Recovery:{" "}
                    {c.recovery_local ? (
                      <>
                        local <code>{c.recovery_local}</code>
                      </>
                    ) : null}
                    {c.recovery_local && c.recovery_remote ? " · " : null}
                    {c.recovery_remote ? (
                      <>
                        remote <code>{c.recovery_remote}</code>
                      </>
                    ) : null}
                  </p>
                )}
                <fieldset className="conflict-choice">
                  <legend className="sr-only">Resolution for {c.path}</legend>
                  <label>
                    <input
                      type="radio"
                      name={`c-${c.path}`}
                      checked={chosen === "local"}
                      onChange={() => setResolveChoice((m) => ({ ...m, [c.path]: "local" }))}
                    />{" "}
                    Keep Local (this device)
                  </label>
                  <label>
                    <input
                      type="radio"
                      name={`c-${c.path}`}
                      checked={chosen === "remote"}
                      onChange={() => setResolveChoice((m) => ({ ...m, [c.path]: "remote" }))}
                    />{" "}
                    Keep Remote (GitHub)
                  </label>
                  {!chosen ? (
                    <span className="warn-inline" role="status">
                      Choose a side
                    </span>
                  ) : (
                    <span className="muted-copy">Will write {chosen} content</span>
                  )}
                </fieldset>
                <details>
                  <summary>Compare Base / Local / Remote</summary>
                  <div className="conflict-compare">
                    <div>
                      <strong>Base</strong>
                      <pre className="conflict-pre">{c.base ?? "(no base)"}</pre>
                    </div>
                    <div>
                      <strong>Local</strong>
                      <pre className="conflict-pre">{c.local ?? "(empty local)"}</pre>
                    </div>
                    <div>
                      <strong>Remote</strong>
                      <pre className="conflict-pre">{c.remote ?? "(empty remote)"}</pre>
                    </div>
                  </div>
                </details>
              </div>
            );
          })}
          <button
            type="button"
            className="primary"
            onClick={() => void onResolve()}
            disabled={
              busy ||
              !status.conflicts.every((c) => resolveChoice[c.path] === "local" || resolveChoice[c.path] === "remote")
            }
          >
            Apply resolutions &amp; resume sync
          </button>
        </div>
      ) : null}

      <h3>History</h3>
      <ul className="sync-list">
        {history.length === 0 ? <li className="muted-copy">No events yet</li> : null}
        {history.map((h) => (
          <li key={h.id} data-ok={h.ok}>
            <span className="muted-copy">{h.at}</span> · <strong>{h.kind}</strong> — {h.detail}
          </li>
        ))}
      </ul>

      {message ? (
        <p className="status" role="status">
          {message}
        </p>
      ) : null}
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      {status?.last_error ? (
        <p className="warn" role="status">
          Last error: {status.last_error}
        </p>
      ) : null}
    </section>
  );
}
