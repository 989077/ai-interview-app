"use client";

import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  getReport,
  startSession,
  submitAnswer,
  type AnswerResult,
  type Question,
  type Report,
  type Session,
} from "../lib/api";

const TOPICS = [
  { value: "", label: "Rotate through all topics" },
  { value: "sql", label: "SQL" },
  { value: "excel", label: "Excel" },
  { value: "power_bi", label: "Power BI / DAX" },
  { value: "statistics", label: "Statistics" },
  { value: "case_study", label: "Case study" },
  { value: "behavioral", label: "Behavioral" },
];

const topicLabel = (value: string) => TOPICS.find((t) => t.value === value)?.label ?? value;

function verdict(score: number) {
  if (score >= 7) return "Strong";
  if (score >= 4) return "Getting there";
  return "Needs work";
}

function ErrorBanner({ error }: { error: ApiError | null }) {
  if (!error) return null;
  const hint =
    error.status === 503
      ? "This is a setup problem. Start the Ollama app, then try again."
      : error.status === 502
        ? "The model failed this time. Try again."
        : null;
  return (
    <div className="error" role="alert">
      <strong>{error.message}</strong>
      {hint && <div>{hint}</div>}
    </div>
  );
}

export default function Home() {
  const [stage, setStage] = useState<"setup" | "interview" | "report">("setup");
  const [busy, setBusy] = useState<null | "starting" | "scoring" | "report">(null);
  const [error, setError] = useState<ApiError | null>(null);

  // setup form
  const [level, setLevel] = useState("fresher");
  const [count, setCount] = useState(6);
  const [topic, setTopic] = useState("");
  const [resume, setResume] = useState("");
  const [jd, setJd] = useState("");

  // interview state
  const [session, setSession] = useState<Session | null>(null);
  const [question, setQuestion] = useState<Question | null>(null);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [report, setReport] = useState<Report | null>(null);

  const answerRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (stage === "interview" && !result) answerRef.current?.focus();
  }, [stage, question, result]);

  function fail(e: unknown) {
    setError(e instanceof ApiError ? e : new ApiError(0, "Something went wrong."));
  }

  async function onStart(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy("starting");
    try {
      const s = await startSession({
        level,
        n_questions: count,
        topic: topic || null,
        resume_text: resume,
        job_description: jd,
      });
      setSession(s);
      setQuestion(s.question);
      setAnswer("");
      setResult(null);
      setReport(null);
      setStage("interview");
    } catch (err) {
      fail(err);
    } finally {
      setBusy(null);
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!session || !answer.trim()) return;
    setError(null);
    setBusy("scoring");
    try {
      setResult(await submitAnswer(session.session_id, answer.trim()));
    } catch (err) {
      fail(err); // the interview is unchanged on the server, so the answer stays in the box
    } finally {
      setBusy(null);
    }
  }

  function onNext() {
    if (!result?.next_question) return;
    setQuestion(result.next_question);
    setAnswer("");
    setResult(null);
  }

  async function onReport() {
    if (!session) return;
    setError(null);
    setBusy("report");
    try {
      setReport(await getReport(session.session_id));
      setStage("report");
    } catch (err) {
      fail(err);
    } finally {
      setBusy(null);
    }
  }

  function restart() {
    setStage("setup");
    setSession(null);
    setQuestion(null);
    setResult(null);
    setReport(null);
    setAnswer("");
    setError(null);
  }

  return (
    <main className="shell">
      <header className="top">
        <h1>AI Interview Practice</h1>
        <p>Data Analyst interviews with honest, specific feedback.</p>
      </header>

      <ErrorBanner error={error} />

      {stage === "setup" && (
        <form className="card" onSubmit={onStart}>
          <h2>Set up your interview</h2>
          <div className="grid">
            <label>
              Level
              <select value={level} onChange={(e) => setLevel(e.target.value)}>
                <option value="fresher">Fresher</option>
                <option value="junior">Junior</option>
                <option value="mid">Mid</option>
              </select>
            </label>
            <label>
              Questions
              <select value={count} onChange={(e) => setCount(Number(e.target.value))}>
                {[5, 6, 7, 8, 9, 10].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <label className="wide">
              Starting topic
              <select value={topic} onChange={(e) => setTopic(e.target.value)}>
                {TOPICS.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <details>
            <summary>Add your resume or a job description (optional)</summary>
            <label>
              Resume
              <textarea rows={5} value={resume} onChange={(e) => setResume(e.target.value)} />
            </label>
            <label>
              Job description
              <textarea rows={5} value={jd} onChange={(e) => setJd(e.target.value)} />
            </label>
          </details>
          <button className="primary" type="submit" disabled={busy !== null}>
            {busy === "starting" ? "Preparing your first question..." : "Start interview"}
          </button>
          {busy === "starting" && (
            <p className="hint" aria-live="polite">
              The first question can take up to a minute while the model loads.
            </p>
          )}
        </form>
      )}

      {stage === "interview" && session && question && (
        <>
          <div className="progress" aria-label="Progress">
            <div className="bar">
              <div
                className="fill"
                style={{ width: `${(session.n_questions ? (result ? result.answered : question.number - 1) / session.n_questions : 0) * 100}%` }}
              />
            </div>
            <span>
              Question {question.number} of {session.n_questions}
            </span>
          </div>

          <section className="card">
            <div className="chips">
              <span className="chip">{topicLabel(question.topic)}</span>
              <span className="chip">{question.difficulty}</span>
              {question.is_follow_up && <span className="chip accent">Follow-up</span>}
            </div>
            <h2 className="question">{question.question}</h2>

            {!result && (
              <form onSubmit={onSubmit}>
                <label>
                  Your answer
                  <textarea
                    ref={answerRef}
                    rows={7}
                    maxLength={4000}
                    value={answer}
                    onChange={(e) => setAnswer(e.target.value)}
                    disabled={busy === "scoring"}
                    placeholder="Explain your thinking. Examples and edge cases score higher."
                  />
                </label>
                <div className="row">
                  <span className="hint">{answer.length} / 4000</span>
                  <button className="primary" type="submit" disabled={busy !== null || !answer.trim()}>
                    {busy === "scoring" ? "Scoring..." : "Submit answer"}
                  </button>
                </div>
                {busy === "scoring" && (
                  <p className="hint" aria-live="polite">
                    Scoring your answer. This can take up to a minute.
                  </p>
                )}
              </form>
            )}
          </section>

          {result && (
            <section className="card" aria-live="polite">
              <div className="scoreRow">
                <div className="bigScore">
                  {result.feedback.score}
                  <span>/10</span>
                </div>
                <div>
                  <strong>{verdict(result.feedback.score)}</strong>
                  <div className="metrics">
                    <span>Correctness {result.feedback.correctness}</span>
                    <span>Clarity {result.feedback.clarity}</span>
                    <span>Depth {result.feedback.depth}</span>
                  </div>
                </div>
              </div>
              <h3>What worked</h3>
              <p>{result.feedback.strengths}</p>
              <h3>What to improve</h3>
              <p>{result.feedback.improve}</p>
              <details>
                <summary>See a model answer</summary>
                <p>{result.feedback.better_answer}</p>
              </details>
              {result.finished ? (
                <button className="primary" onClick={onReport} disabled={busy !== null}>
                  {busy === "report" ? "Writing your report..." : "See your report"}
                </button>
              ) : (
                <button className="primary" onClick={onNext}>
                  Next question
                </button>
              )}
              {busy === "report" && <p className="hint">Writing your report can take up to a minute.</p>}
            </section>
          )}
        </>
      )}

      {stage === "report" && report && (
        <>
          <section className="card">
            <div className="scoreRow">
              <div className="bigScore">
                {report.overall_score}
                <span>/10</span>
              </div>
              <div>
                <strong>Overall: {verdict(report.overall_score)}</strong>
                <p className="hint">Average of your {report.turns.length} answer scores.</p>
              </div>
            </div>
            <p>{report.summary}</p>
            <div className="three">
              <div>
                <h3>Strengths</h3>
                <ul>{report.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
              </div>
              <div>
                <h3>Weak topics</h3>
                <ul>{report.weak_topics.map((s, i) => <li key={i}>{s}</li>)}</ul>
              </div>
              <div>
                <h3>Practice next</h3>
                <ul>{report.next_practice.map((s, i) => <li key={i}>{s}</li>)}</ul>
              </div>
            </div>
          </section>

          <section className="card">
            <h2>Question by question</h2>
            {report.turns.map((t, i) => (
              <details key={i} className="turn">
                <summary>
                  <span className="turnScore">{t.score}/10</span> {t.is_follow_up ? "Follow-up: " : ""}
                  {t.question}
                </summary>
                <h3>Your answer</h3>
                <p>{t.answer}</p>
                <h3>What worked</h3>
                <p>{t.strengths}</p>
                <h3>What to improve</h3>
                <p>{t.improve}</p>
                <h3>Model answer</h3>
                <p>{t.better_answer}</p>
              </details>
            ))}
          </section>

          <button className="primary" onClick={restart}>
            Practice again
          </button>
        </>
      )}
    </main>
  );
}
