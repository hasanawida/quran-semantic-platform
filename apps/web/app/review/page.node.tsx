"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, request } from "../lib/api";
import { useAuth } from "../lib/auth";

type Assignment = {
  id: string;
  target_type: string;
  target_id: string;
  status: string;
  decline_reason: string | null;
};

type Dispute = {
  id: string;
  target_type: string;
  target_id: string;
  reason: string;
  status: string;
  resolution: string | null;
};

const TARGET_LABELS: Record<string, string> = {
  claim: "ادعاء",
  source_work: "مصدر",
  root_decision: "قرار جذر",
  report_version: "نسخة تقرير",
};

const ASSIGNMENT_LABELS: Record<string, string> = {
  pending: "بانتظار ردك",
  accepted: "مقبول — قيد المراجعة",
  declined: "معتذَر عنه",
  completed: "مكتمل",
};

export default function ReviewPage() {
  const { user, loading } = useAuth();
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!user) return;
    try {
      const [queue, open] = await Promise.all([
        request<Assignment[]>("/review/assignments/mine", { auth: true }),
        request<Dispute[]>("/review/disputes", { auth: true }),
      ]);
      setAssignments(queue);
      setDisputes(open);
      setError("");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "تعذّر جلب صندوق المراجعة."
      );
    }
  }, [user]);

  useEffect(() => {
    load();
  }, [load]);

  async function respond(id: string, accept: boolean) {
    setBusy(id);
    try {
      const body: { accept: boolean; reason?: string } = { accept };
      if (!accept) {
        const reason = window.prompt("سبب الاعتذار عن هذا التكليف:");
        if (!reason) {
          setBusy(null);
          return;
        }
        body.reason = reason;
      }
      await request(`/review/assignments/${id}/respond`, {
        method: "POST",
        body,
        auth: true,
      });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر تنفيذ الإجراء.");
    } finally {
      setBusy(null);
    }
  }

  async function complete(id: string) {
    setBusy(id);
    try {
      await request(`/review/assignments/${id}/complete`, {
        method: "POST",
        auth: true,
      });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر إتمام التكليف.");
    } finally {
      setBusy(null);
    }
  }

  if (loading) return <main id="main" className="container" />;

  if (!user) {
    return (
      <main id="main" className="container">
        <div className="status-box notice">
          <p>صندوق المراجعة يحتاج تسجيل الدخول.</p>
        </div>
      </main>
    );
  }

  return (
    <main id="main" className="container">
      <header className="analysis-header">
        <h1>صندوق المراجعة</h1>
      </header>
      <p className="page-lead">
        تكليفاتك ثم الخلافات المفتوحة على المنصة. الخلاف يبقى معروضًا حتى
        تحسمه جهة مخوَّلة بتعليل موثق.
      </p>

      {error && (
        <div className="status-box error" role="alert">
          <p>{error}</p>
        </div>
      )}

      <section className="provenance-block">
        <h2>تكليفاتي ({assignments.length})</h2>
        {assignments.length === 0 ? (
          <p className="unlinked-note">لا توجد تكليفات مفتوحة عليك.</p>
        ) : (
          <ul className="word-list">
            {assignments.map((assignment) => (
              <li key={assignment.id} className="word-card">
                <div className="word-card-head">
                  <span className="claim-subject">
                    {TARGET_LABELS[assignment.target_type] ??
                      assignment.target_type}
                  </span>
                  <span className="agreement-tag">
                    {ASSIGNMENT_LABELS[assignment.status] ?? assignment.status}
                  </span>
                </div>
                <p className="claim-meta">
                  <code dir="ltr">{assignment.target_id}</code>
                </p>
                <div className="row-actions">
                  {assignment.status === "pending" && (
                    <>
                      <button
                        type="button"
                        className="primary"
                        disabled={busy === assignment.id}
                        onClick={() => respond(assignment.id, true)}
                      >
                        قبول
                      </button>
                      <button
                        type="button"
                        className="ghost"
                        disabled={busy === assignment.id}
                        onClick={() => respond(assignment.id, false)}
                      >
                        اعتذار
                      </button>
                    </>
                  )}
                  {assignment.status === "accepted" && (
                    <button
                      type="button"
                      className="primary"
                      disabled={busy === assignment.id}
                      onClick={() => complete(assignment.id)}
                    >
                      إتمام المراجعة
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="provenance-block">
        <h2>الخلافات المفتوحة ({disputes.length})</h2>
        {disputes.length === 0 ? (
          <p className="unlinked-note">لا توجد خلافات مفتوحة.</p>
        ) : (
          <ul className="word-list">
            {disputes.map((dispute) => (
              <li key={dispute.id} className="word-card">
                <div className="word-card-head">
                  <span className="claim-subject">
                    {TARGET_LABELS[dispute.target_type] ?? dispute.target_type}
                  </span>
                  <span className="agreement-tag agreement-conflict">
                    {dispute.status === "open" ? "مفتوح" : dispute.status}
                  </span>
                </div>
                <p className="claim-statement">{dispute.reason}</p>
                <p className="claim-meta">
                  <code dir="ltr">{dispute.target_id}</code>
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
