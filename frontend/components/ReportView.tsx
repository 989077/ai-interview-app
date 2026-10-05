import type { Report } from "../lib/api";

export function verdict(score: number) {
  if (score >= 7) return "Strong";
  if (score >= 4) return "Getting there";
  return "Needs work";
}

export function ReportView({ report }: { report: Report }) {
  return (
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
    </>
  );
}
