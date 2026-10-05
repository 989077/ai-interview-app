"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { ReportView } from "../../../components/ReportView";
import { ApiError, getReport, type Report } from "../../../lib/api";

export default function SavedReport({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getReport(id)
      .then(setReport)
      .catch((e) =>
        setError(
          e instanceof ApiError && e.status === 404
            ? "This interview was not found. It may have been deleted."
            : e instanceof ApiError
              ? e.message
              : "Something went wrong.",
        ),
      );
  }, [id]);

  return (
    <main className="shell">
      <header className="top">
        <h1>Interview report</h1>
        <p>
          <Link href="/history">Back to past interviews</Link>
        </p>
      </header>
      {error && (
        <div className="error" role="alert">
          <strong>{error}</strong>
        </div>
      )}
      {!report && !error && <p className="hint">Loading...</p>}
      {report && <ReportView report={report} />}
    </main>
  );
}
