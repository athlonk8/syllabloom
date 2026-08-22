import { useEffect, useMemo, useState } from "react";

import { api } from "../lib/api";
import { formatPercent } from "../lib/format";
import type { Locale, Translator } from "../lib/i18n";
import type { Assignment, AssignmentWorkspace as AssignmentWorkspaceData, Grade, GradeResult, Submission } from "../types/api";

type BusyAction = "save" | "submit" | "grade" | null;

function messageFrom(error: unknown, t: Translator): string {
  return error instanceof Error ? error.message : t("error.generic");
}

function gradeResult(grade: Grade | undefined): GradeResult | null {
  return grade?.result ?? null;
}

function FeedbackList({ title, items }: { title: string; items?: string[] }) {
  if (!items?.length) return null;
  return (
    <section className="feedback-list">
      <h4>{title}</h4>
      <ul>{items.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>
    </section>
  );
}

function SubmissionFeedback({ submission, t }: { submission: Submission | undefined; t: Translator }) {
  const grade = submission?.grades.at(-1);
  const result = gradeResult(grade);
  const failedRun = submission?.runs.at(-1);

  if (!submission) {
    return <div className="feedback-empty"><h3>{t("assignment.feedbackTitle")}</h3><p>{t("assignment.feedbackEmpty")}</p></div>;
  }
  if (!result) {
    return (
      <div className="feedback-empty">
        <h3>{t("assignment.feedbackTitle")}</h3>
        <p>{failedRun?.result?.error || failedRun?.stderr || t("assignment.feedbackPending")}</p>
      </div>
    );
  }

  const dimensions = [
    [t("assignment.conceptual"), result.conceptual_understanding],
    [t("assignment.reasoning"), result.reasoning],
    [t("assignment.accuracy"), result.technical_accuracy],
    [t("assignment.clarity"), result.clarity],
  ].filter((item): item is [string, number] => typeof item[1] === "number");

  return (
    <section className="feedback-panel">
      <div className="feedback-heading">
        <div>
          <p className="eyebrow">{t("assignment.aiEstimate")}</p>
          <h3>{t("assignment.feedbackTitle")}</h3>
          <p>{result.summary || t("assignment.feedbackNoSummary")}</p>
        </div>
        <div className="feedback-score">
          <strong>{typeof grade?.score === "number" ? Math.round(grade.score) : "—"}</strong>
          <span>/ 100</span>
          {typeof grade?.confidence === "number" && <small>{t("assignment.confidence", { percent: formatPercent(grade.confidence) })}</small>}
        </div>
      </div>
      {result.detailed_feedback && <p className="feedback-detail">{result.detailed_feedback}</p>}
      {dimensions.length > 0 && (
        <div className="feedback-dimensions">
          {dimensions.map(([label, value]) => (
            <div key={label}>
              <span>{label}</span>
              <b>{Math.round(value)}</b>
              <i><em style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /></i>
            </div>
          ))}
        </div>
      )}
      {result.rubric_breakdown?.length ? (
        <section className="rubric-breakdown">
          <h4>{t("assignment.breakdown")}</h4>
          {result.rubric_breakdown.map((criterion, index) => (
            <div key={`${criterion.title}-${index}`}>
              <b>{criterion.title}</b>
              {typeof criterion.score === "number" && <span>{Math.round(criterion.score)}{criterion.max_score ? ` / ${Math.round(criterion.max_score)}` : ""}</span>}
              <p>{criterion.feedback}</p>
            </div>
          ))}
        </section>
      ) : null}
      <div className="feedback-lists">
        <FeedbackList title={t("assignment.strengths")} items={result.strengths} />
        <FeedbackList title={t("assignment.improve")} items={result.issues} />
        <FeedbackList title={t("assignment.critical")} items={result.critical_errors} />
        <FeedbackList title={t("assignment.reviewTopics")} items={result.suggested_review_topics} />
      </div>
      <p className="feedback-disclaimer">{t("assignment.aiDisclaimer")}</p>
    </section>
  );
}

export function AssignmentWorkspace({
  assignment,
  locale,
  t,
  onClose,
  onRefresh,
  notify,
}: {
  assignment: Assignment;
  locale: Locale;
  t: Translator;
  onClose: () => void;
  onRefresh: () => Promise<void>;
  notify: (message: string) => void;
}) {
  const [workspace, setWorkspace] = useState<AssignmentWorkspaceData | null>(null);
  const [answer, setAnswer] = useState("");
  const [savedAnswer, setSavedAnswer] = useState("");
  const [selectedSubmissionId, setSelectedSubmissionId] = useState<number | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState<BusyAction>(null);
  const [error, setError] = useState<string | null>(null);

  const loadWorkspace = async () => {
    const result = await api<AssignmentWorkspaceData>(`/assignments/${assignment.id}/workspace`);
    setWorkspace(result);
    setAnswer(result.answer);
    setSavedAnswer(result.answer);
    setSelectedSubmissionId((current) => current && result.history.some((item) => item.id === current) ? current : result.history[0]?.id ?? null);
  };

  useEffect(() => {
    setWorkspace(null);
    setError(null);
    setSelectedSubmissionId(null);
    void loadWorkspace().catch((cause) => setError(messageFrom(cause, t)));
    // The assignment id defines the file and historical snapshots to load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assignment.id]);

  const selectedSubmission = useMemo(
    () => workspace?.history.find((item) => item.id === selectedSubmissionId),
    [workspace?.history, selectedSubmissionId],
  );
  const dirty = answer !== savedAnswer;

  const persist = async () => {
    const result = await api<Pick<AssignmentWorkspaceData, "assignment" | "answer" | "answer_path" | "storage">>(
      `/assignments/${assignment.id}/workspace`,
      { method: "PUT", body: JSON.stringify({ content: answer }) },
    );
    setWorkspace((current) => current ? { ...current, ...result } : current);
    setAnswer(result.answer);
    setSavedAnswer(result.answer);
  };

  const save = async () => {
    setBusy("save");
    setError(null);
    try {
      await persist();
      notify(t("assignment.saved"));
      await onRefresh();
    } catch (cause) {
      setError(messageFrom(cause, t));
    } finally {
      setBusy(null);
    }
  };

  const createSubmission = async () => {
    setBusy("submit");
    setError(null);
    try {
      if (dirty) await persist();
      const submission = await api<Submission>(`/assignments/${assignment.id}/submissions`, { method: "POST" });
      setWorkspace((current) => current ? {
        ...current,
        assignment: { ...current.assignment, status: "submitted" },
        history: [submission, ...current.history],
      } : current);
      setSelectedSubmissionId(submission.id);
      notify(t("assignment.snapshotSaved", { version: submission.version }));
      await onRefresh();
    } catch (cause) {
      setError(messageFrom(cause, t));
    } finally {
      setBusy(null);
    }
  };

  const grade = async () => {
    if (!selectedSubmissionId) return;
    setBusy("grade");
    setError(null);
    try {
      const submission = await api<Submission>(`/submissions/${selectedSubmissionId}/grade`, {
        method: "POST",
        body: JSON.stringify({
          run_official_tests: false,
          run_ai_review: true,
          acknowledge_cloud_submission: true,
        }),
      });
      setWorkspace((current) => current ? {
        ...current,
        history: current.history.map((item) => item.id === submission.id ? submission : item),
      } : current);
      notify(t("assignment.gradeReady"));
      await onRefresh();
    } catch (cause) {
      setError(messageFrom(cause, t));
    } finally {
      setBusy(null);
    }
  };

  const formatDate = (value: string) => new Intl.DateTimeFormat(locale === "zh" ? "zh-CN" : "en", {
    dateStyle: "medium", timeStyle: "short",
  }).format(new Date(value));

  if (!workspace && !error) {
    return <div className="assignment-workspace-backdrop"><div className="assignment-workspace loading-workspace"><div className="orbit" /><p>{t("assignment.loading")}</p></div></div>;
  }

  return (
    <div className="assignment-workspace-backdrop" role="dialog" aria-modal="true" aria-label={t("assignment.workspaceLabel")}>
      <main className="assignment-workspace">
        <header className="assignment-workspace-header">
          <div>
            <p className="eyebrow">{t("assignment.workspaceEyebrow")}</p>
            <div className="workspace-title"><span className="tag">{assignment.key}</span><h1>{assignment.title}</h1></div>
            <p>{t(workspace?.storage === "obsidian" ? "assignment.storageObsidian" : "assignment.storageLocal")}</p>
          </div>
          <button className="icon-button close workspace-close" type="button" onClick={onClose} aria-label={t("common.close")}>×</button>
        </header>
        {error && <p className="inline-error workspace-error">{error}</p>}
        <div className="assignment-workspace-grid">
          <section className="assignment-brief">
            <div className="brief-section">
              <p className="eyebrow">{t("assignment.prompt")}</p>
              <h2>{t("assignment.assignmentBrief")}</h2>
              <p className="assignment-description">{assignment.description || t("assignment.defaultDescription")}</p>
              {assignment.protected_resource && <p className="protected">{t("assignment.protected")}</p>}
              {assignment.official_url && <a className="source-link" href={assignment.official_url} target="_blank" rel="noreferrer">{t("assignment.openOfficial")}</a>}
              {assignment.rubric_url && <a className="source-link" href={assignment.rubric_url} target="_blank" rel="noreferrer">{t("assignment.openRubric")}</a>}
            </div>
            <div className="brief-section">
              <h3>{t("assignment.resources")}</h3>
              {assignment.resources.length ? (
                <ul className="assignment-resources">
                  {assignment.resources.map((resource) => (
                    <li key={resource.id}>
                      <a href={resource.resource_url} target="_blank" rel="noreferrer">{resource.title}</a>
                      <span>{resource.resource_type}</span>
                    </li>
                  ))}
                </ul>
              ) : <p>{t("assignment.noResources")}</p>}
            </div>
            {assignment.ai_policy && <div className="brief-section policy-copy"><h3>{t("assignment.aiPolicy")}</h3><p>{assignment.ai_policy}</p></div>}
          </section>
          <section className="answer-editor">
            <div className="answer-editor-heading">
              <div><p className="eyebrow">{t("assignment.myWork")}</p><h2>{t("assignment.answerTitle")}</h2></div>
              <span className={dirty ? "draft-state changed" : "draft-state"}>{dirty ? t("assignment.unsaved") : t("assignment.savedState")}</span>
            </div>
            <textarea
              value={answer}
              onChange={(event) => setAnswer(event.target.value)}
              placeholder={t("assignment.answerPlaceholder")}
              aria-label={t("assignment.answerTitle")}
              spellCheck
            />
            <div className="answer-actions">
              <button type="button" className="text-button" disabled={busy !== null || !dirty} onClick={() => void save()}>
                {busy === "save" ? t("assignment.saving") : t("assignment.saveDraft")}
              </button>
              <button type="button" className="primary-button compact" disabled={busy !== null} onClick={() => void createSubmission()}>
                {busy === "submit" ? t("assignment.submitting") : t("assignment.saveSnapshot")}
              </button>
            </div>
            <p className="answer-note">{t("assignment.snapshotHint")}</p>
          </section>
        </div>
        <section className="grading-workbench">
          <div className="grading-sidebar">
            <div className="grading-sidebar-heading"><div><p className="eyebrow">{t("assignment.localHistory")}</p><h2>{t("assignment.savedVersions")}</h2></div></div>
            {workspace?.history.length ? (
              <div className="submission-list">
                {workspace.history.map((submission) => (
                  <button
                    key={submission.id}
                    type="button"
                    className={submission.id === selectedSubmissionId ? "submission-item active" : "submission-item"}
                    onClick={() => setSelectedSubmissionId(submission.id)}
                  >
                    <strong>v{submission.version}</strong>
                    <span>{formatDate(submission.submitted_at)}</span>
                    <small>{submission.grades.at(-1)?.score ?? t("assignment.notGraded")}</small>
                  </button>
                ))}
              </div>
            ) : <p className="empty-note">{t("assignment.noSubmissions")}</p>}
            <label className="acknowledgement grading-acknowledgement">
              <input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} />
              {t("assignment.ack")}
            </label>
            <button
              type="button"
              className="primary-button compact grade-button"
              disabled={busy !== null || !selectedSubmissionId || !acknowledged || dirty}
              onClick={() => void grade()}
            >
              {busy === "grade" ? t("assignment.grading") : t("assignment.gradeWithCodex")}
            </button>
            {dirty && <p className="hint">{t("assignment.saveBeforeGrade")}</p>}
            {!selectedSubmissionId && <p className="hint">{t("assignment.snapshotBeforeGrade")}</p>}
          </div>
          <SubmissionFeedback submission={selectedSubmission} t={t} />
        </section>
      </main>
    </div>
  );
}
