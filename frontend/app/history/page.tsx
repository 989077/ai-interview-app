"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { verdict } from "../../components/ReportView";
import { ApiError, deleteSession, getHistory, type HistoryItem } from "../../lib/api";

function when(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export default function History() {
  const [items, setItems] = useState<HistoryItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHistory()
      .then(setItems)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Something went wrong."));
  }, []);

  async function remove(id: string) {
    if (!window.confirm("Delete this interview? This cannot be undone.")) return;
    try {
      await deleteSession(id);
      setItems((cur) => (cur ? cur.filter((i) => i.id !== id) : cur));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not delete.");
    }
  }

  const done = items?.filter((i) => i.status === "finished" && i.overall_score !== null) ?? [];
  const avg = done.length ? Math.round(done.reduce((a, i) => a + (i.overall_score ?? 0), 0) / done.length) : null;

  return (
    <main className="shell">
      <header className="top">
        <h1>Past interviews</h1>
        <p>
          <Link href="/">Start a new interview</Link>
        </p>
      </header>

      {error && (
        <div className="error" role="alert">
          <strong>{error}</strong>
        </div>
      )}

      {items === null && !error && <p className="hint">Loading...</p>}

      {items && items.length === 0 && (
        <section className="card">
          <p>No interviews yet. Finish one and it will show up here.</p>
        </section>
      )}

      {items && items.length > 0 && (
        <>
          <p className="hint">
            {items.length} interview{items.length === 1 ? "" : "s"}
            {avg !== null && ` · average score ${avg}/10 across ${done.length} finished`}
          </p>
          <ul className="history">
            {items.map((i) => (
              <li key={i.id} className="card historyItem">
                <div>
                  <strong>{when(i.created_at)}</strong>
                  <div className="chips">
                    <span className="chip">{i.level}</span>
                    <span className="chip">
                      {i.answered} / {i.n_questions} answered
                    </span>
                    {i.status === "in_progress" && <span className="chip accent">Unfinished</span>}
                  </div>
                </div>
                <div className="historyRight">
                  {i.status === "finished" && i.overall_score !== null ? (
                    <>
                      <div className="bigScore small">
                        {i.overall_score}
                        <span>/10</span>
                      </div>
                      <div className="hint">{verdict(i.overall_score)}</div>
                      <Link href={`/history/${i.id}`}>View report</Link>
                    </>
                  ) : (
                    <div className="hint">No report</div>
                  )}
                  <button className="linkBtn" onClick={() => remove(i.id)}>
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </main>
  );
}
