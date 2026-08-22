import { FormEvent, useEffect, useMemo, useState } from "react";
import { YouTubePlayer } from "./components/YouTubePlayer";
import { api, apiBase, ApiError } from "./lib/api";
import { formatPercent, formatSeconds } from "./lib/format";
import type { Assignment, Course, Dashboard, Lecture } from "./types/api";

const PRESETS = [
  { label: "Karpathy - Zero to Hero", type: "youtube", url: "https://www.youtube.com/@AndrejKarpathy/playlists" },
  { label: "Stanford CS229", type: "stanford", url: "https://cs229.stanford.edu/" },
  { label: "Stanford CS224N", type: "stanford", url: "https://web.stanford.edu/class/cs224n/" },
  { label: "Stanford CS336", type: "stanford", url: "https://cs336.stanford.edu/" },
];

function messageFrom(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

function ProgressRing({ value }: { value: number }) {
  return <span className="progress-ring" style={{ "--progress": `${Math.max(0, Math.min(100, value * 100))}%` } as React.CSSProperties}>{formatPercent(value)}</span>;
}

function ImportDialog({ onClose, onImported }: { onClose: () => void; onImported: (course: Course) => void }) {
  const [mode, setMode] = useState<"youtube" | "stanford" | "manual">("youtube");
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [videoTitle, setVideoTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const usePreset = (preset: (typeof PRESETS)[number]) => {
    setMode(preset.type as "youtube" | "stanford");
    setUrl(preset.url);
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true); setError(null);
    try {
      let response: { course: Course };
      if (mode === "youtube") response = await api("/imports/youtube", { method: "POST", body: JSON.stringify({ url }) });
      else if (mode === "stanford") response = await api("/imports/stanford", { method: "POST", body: JSON.stringify({ url, max_pages: 18, max_depth: 1 }) });
      else response = await api("/imports/manual-youtube", { method: "POST", body: JSON.stringify({ name, videos: [{ url, title: videoTitle || name }] }) });
      onImported(response.course);
      onClose();
    } catch (cause) {
      setError(messageFrom(cause));
      if (cause instanceof ApiError && mode === "youtube" && cause.message.includes("API key")) setMode("manual");
    } finally {
      setBusy(false);
    }
  };
  return <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Add course">
    <form className="modal" onSubmit={submit}>
      <button className="icon-button close" type="button" onClick={onClose} aria-label="Close">×</button>
      <p className="eyebrow">COURSE LIBRARY</p><h2>Add a course</h2>
      <p className="muted">Import only public materials. Stanford pages are bounded, robots-aware, and never bypass login.</p>
      <div className="segmented"><button type="button" className={mode === "youtube" ? "selected" : ""} onClick={() => setMode("youtube")}>YouTube API</button><button type="button" className={mode === "stanford" ? "selected" : ""} onClick={() => setMode("stanford")}>Stanford URL</button><button type="button" className={mode === "manual" ? "selected" : ""} onClick={() => setMode("manual")}>Manual fallback</button></div>
      {mode === "manual" && <><label>Course name<input value={name} onChange={(event) => setName(event.target.value)} required placeholder="e.g. Neural Networks" /></label><label>Video title<input value={videoTitle} onChange={(event) => setVideoTitle(event.target.value)} placeholder="Lecture 1" /></label></>}
      <label>{mode === "stanford" ? "Stanford course URL" : "YouTube video or playlist URL"}<input value={url} onChange={(event) => setUrl(event.target.value)} required type="url" placeholder="https://..." /></label>
      {mode === "youtube" && <p className="hint">Uses the official YouTube Data API. Add a local API key in Settings; no HTML scraping fallback is used.</p>}
      {error && <p className="inline-error">{error}</p>}
      <button className="primary-button" disabled={busy}>{busy ? "Importing…" : "Import course"}</button>
      <div className="preset-list"><span className="muted">Import presets</span>{PRESETS.map((preset) => <button type="button" key={preset.label} onClick={() => usePreset(preset)}>{preset.label}</button>)}</div>
    </form>
  </div>;
}

function SettingsDialog({ onClose }: { onClose: () => void }) {
  const [youtubeKey, setYoutubeKey] = useState("");
  const [vaultPath, setVaultPath] = useState("");
  const [threshold, setThreshold] = useState("0.85");
  const [codex, setCodex] = useState<{ installed: boolean; version?: string; error?: string } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => { void (async () => {
    const [settings, codexStatus] = await Promise.all([api<{ obsidian_vault_path: string | null; watch_completion_threshold: number }>("/settings"), api<{ installed: boolean; version?: string; error?: string }>("/settings/codex")]);
    setVaultPath(settings.obsidian_vault_path || ""); setThreshold(String(settings.watch_completion_threshold)); setCodex(codexStatus);
  })().catch((cause) => setNotice(messageFrom(cause))); }, []);
  const save = async (event: FormEvent) => {
    event.preventDefault(); setNotice(null);
    try {
      if (youtubeKey.trim()) await api("/settings/value/YOUTUBE_API_KEY", { method: "PUT", body: JSON.stringify({ value: youtubeKey, is_secret: true }) });
      await api("/settings/value/watch_completion_threshold", { method: "PUT", body: JSON.stringify({ value: threshold }) });
      if (vaultPath.trim()) await api("/settings/obsidian", { method: "PUT", body: JSON.stringify({ vault_path: vaultPath, create_if_missing: false }) });
      setNotice("Local settings saved.");
    } catch (cause) { setNotice(messageFrom(cause)); }
  };
  return <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Settings"><form className="modal settings-modal" onSubmit={save}>
    <button className="icon-button close" type="button" onClick={onClose} aria-label="Close">×</button><p className="eyebrow">LOCAL CONFIGURATION</p><h2>Settings</h2>
    <label>YouTube Data API key<input value={youtubeKey} onChange={(event) => setYoutubeKey(event.target.value)} type="password" placeholder="Stored only in local SQLite" autoComplete="off" /></label>
    <label>Obsidian Vault Path<input value={vaultPath} onChange={(event) => setVaultPath(event.target.value)} placeholder="D:\Obsidian\AI-Learning" /></label>
    <label>Watch completion threshold<input value={threshold} onChange={(event) => setThreshold(event.target.value)} type="number" min="0.01" max="1" step="0.01" /></label>
    <p className="hint">The configured vault must already exist. The app writes only under its `AI-Learning` subfolder and never overwrites Answer.md.</p>
    <div className="codex-status"><strong>Codex CLI</strong><span className={codex?.installed ? "status-good" : "status-warn"}>{codex ? (codex.installed ? codex.version : codex.error) : "Checking…"}</span></div>
    {notice && <p className={notice === "Local settings saved." ? "notice" : "inline-error"}>{notice}</p>}<button className="primary-button">Save local settings</button>
  </form></div>;
}

function AssignmentCard({ assignment, refresh, notify }: { assignment: Assignment; refresh: () => Promise<void>; notify: (message: string) => void }) {
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<Array<{ version: number; grades: Array<{ score: number | null; status: string; score_type: string }> }> | null>(null);
  const invoke = async (path: string, payload?: object) => {
    setBusy(true);
    try { const result = await api<Record<string, unknown>>(path, { method: "POST", body: payload ? JSON.stringify(payload) : undefined }); notify(typeof result.root === "string" ? `Saved locally: ${result.root}` : "Action completed."); await refresh(); }
    catch (cause) { notify(messageFrom(cause)); }
    finally { setBusy(false); }
  };
  const loadHistory = async () => { try { const result = await api<{ submissions: typeof history }>(`/assignments/${assignment.id}/history`); setHistory(result.submissions); } catch (cause) { notify(messageFrom(cause)); } };
  return <article className="assignment-card">
    <div className="assignment-heading"><div><span className="tag">{assignment.key}</span><h4>{assignment.title}</h4></div><span className={`assignment-status ${assignment.status}`}>{assignment.status.replaceAll("_", " ")}</span></div>
    <p>{assignment.description || "Official assignment resource detected from the course source."}</p>
    {assignment.protected_resource ? <p className="protected">Requires Stanford authentication - recorded, not accessed.</p> : <div className="button-row"><button disabled={busy} onClick={() => void invoke(`/assignments/${assignment.id}/download`)}>Download original</button><button disabled={busy} onClick={() => void invoke(`/assignments/${assignment.id}/prepare-workspace`)}>Create notes</button>{assignment.local_root && <button disabled={busy} onClick={() => void invoke(`/assignments/${assignment.id}/open-workspace`)}>Open workspace</button>}</div>}
    <label className="acknowledgement"><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} /> I explicitly approve sending this staged snapshot to my configured Codex provider for feedback.</label>
    <button className="primary-button compact" disabled={busy || !acknowledged || assignment.protected_resource} onClick={() => void invoke(`/assignments/${assignment.id}/submit`, { run_official_tests: true, run_codex_review: true, acknowledge_cloud_submission: true })}>Submit to Codex</button>
    <button className="text-button" onClick={() => void loadHistory()}>Show grading history</button>
    {history && <div className="grading-history">{history.length ? history.map((item) => <p key={item.version}>v{item.version}: {item.grades.map((grade) => `${grade.score ?? "-"} (${grade.score_type}, ${grade.status})`).join(" · ") || "No grade yet"}</p>) : <p>No submissions yet.</p>}</div>}
  </article>;
}

function CourseWorkspace({ course, onRefresh, notify }: { course: Course; onRefresh: () => Promise<void>; notify: (message: string) => void }) {
  const lectures = course.lectures || [];
  const [lectureId, setLectureId] = useState<number | null>(lectures[0]?.id ?? null);
  const [creatingCertificate, setCreatingCertificate] = useState(false);
  useEffect(() => setLectureId(lectures[0]?.id ?? null), [course.id]);
  const lecture = lectures.find((item) => item.id === lectureId) || lectures[0];
  const lectureProgress = useMemo(() => new Map(course.progress.lectures.map((item) => [item.lecture_id, item])), [course.progress.lectures]);
  const exportNotes = async () => { try { const result = await api<{ root: string }>(`/courses/${course.id}/obsidian`, { method: "POST" }); notify(`Notes created in ${result.root}`); } catch (cause) { notify(messageFrom(cause)); } };
  const certificate = async () => {
    const name = window.prompt("Learner name for the independent learning certificate:"); if (!name) return;
    setCreatingCertificate(true);
    try { const result = await api<{ download_url: string; certificate_id: string }>(`/courses/${course.id}/certificates`, { method: "POST", body: JSON.stringify({ certificate_type: "completion", learner_name: name }) }); window.open(`${apiBase}${result.download_url}`, "_blank", "noopener"); notify(`Certificate ${result.certificate_id} generated locally.`); await onRefresh(); }
    catch (cause) { notify(messageFrom(cause)); } finally { setCreatingCertificate(false); }
  };
  return <main className="workspace">
    <header className="course-header"><div><p className="eyebrow">{course.code || course.source_type.toUpperCase()} {course.version || ""}</p><h1>{course.name}</h1><p className="muted">{course.description || "Database-driven course workspace with source provenance."}</p></div><div className="header-actions"><button onClick={() => void exportNotes()}>Export Obsidian notes</button><button className="primary-button" disabled={creatingCertificate} onClick={() => void certificate()}>Issue completion certificate</button></div></header>
    <div className="course-layout"><aside className="lecture-list"><div className="section-title"><span>LECTURES</span><b>{course.progress.completed_lecture_count}/{course.progress.required_lecture_count}</b></div>{lectures.length ? lectures.map((item) => { const itemProgress = lectureProgress.get(item.id); return <button key={item.id} className={item.id === lecture?.id ? "lecture-item active" : "lecture-item"} onClick={() => setLectureId(item.id)}><span className={itemProgress?.completed ? "check done" : "check"}>{itemProgress?.completed ? "✓" : String(item.order_index).padStart(2, "0")}</span><span>{item.title}<small>{formatPercent(itemProgress?.fraction || 0)} watched</small></span></button>; }) : <p className="empty-note">No embeddable lectures were found. Source resources are still preserved below.</p>}</aside>
      <section className="learning-stage">{lecture?.video ? <YouTubePlayer lecture={lecture} onProgress={() => void onRefresh()} /> : <div className="empty-player"><h3>No embeddable video selected</h3><p>Course resources and public links remain available without redirecting you by default.</p></div>}{lecture && <div className="lecture-context"><div><p className="eyebrow">LECTURE {lecture.order_index}</p><h2>{lecture.title}</h2><p>{lecture.description || "Watch coverage is calculated from unique intervals, not button clicks."}</p></div>{lecture.source_url && <a href={lecture.source_url} target="_blank" rel="noreferrer">Official source ↗</a>}</div>}</section>
      <aside className="course-inspector"><div className="progress-card"><ProgressRing value={course.progress.course_completion} /><div><span>COURSE PROGRESS</span><strong>{formatPercent(course.progress.course_completion)}</strong><small>{course.progress.passed_assignment_count}/{course.progress.required_assignment_count} required public assignments passed</small></div></div><div className="inspector-block"><h3>Source policy</h3><p>{course.course_ai_policy || "No public course AI policy was found during import."}</p>{course.official_course_url && <a href={course.official_course_url} target="_blank" rel="noreferrer">View official course page ↗</a>}</div><div className="inspector-block"><h3>Learning record</h3><p>Average score: {course.progress.average_assignment_score ?? "Not graded"}</p><p>Completion requires {formatPercent(0.85)} unique video coverage and passed public required assignments.</p></div></aside>
    </div>
    <section className="resource-section"><div><p className="eyebrow">OFFICIAL WORK</p><h2>Assignments</h2></div><div className="assignment-grid">{(course.assignments || []).length ? course.assignments?.map((item) => <AssignmentCard key={item.id} assignment={item} refresh={onRefresh} notify={notify} />) : <div className="empty-card"><h3>No public official assignment available</h3><p>This importer will not invent AI-generated assignments or label them as official work.</p></div>}</div></section>
    <section className="resource-section provenance"><div><p className="eyebrow">TRACEABILITY</p><h2>Source provenance</h2></div><div className="resource-table">{(course.resources || []).map((resource) => <div key={resource.id}><span className={resource.access_status === "protected" ? "status-warn" : "status-good"}>{resource.resource_type}</span><a href={resource.resource_url} target="_blank" rel="noreferrer">{resource.title}</a><small>{resource.access_status === "protected" ? "Requires Stanford authentication - not downloaded" : `Discovered from ${resource.source_page_url || "course source"}`}</small></div>)}{!(course.resources || []).length && <p className="empty-note">No linked resources recorded yet.</p>}</div></section>
  </main>;
}

export default function App() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [course, setCourse] = useState<Course | null>(null);
  const [showImport, setShowImport] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const refreshDashboard = async () => { const data = await api<Dashboard>("/dashboard"); setDashboard(data); return data; };
  const refreshCourse = async () => { if (!course) return; const data = await api<Course>(`/courses/${course.id}`); setCourse(data); await refreshDashboard(); };
  useEffect(() => { void refreshDashboard().then((data) => { if (data.courses[0]) return api<Course>(`/courses/${data.courses[0].id}`).then(setCourse); }).catch((cause) => setNotice(messageFrom(cause))).finally(() => setLoading(false)); }, []);
  const selectCourse = async (courseId: number) => { try { setCourse(await api<Course>(`/courses/${courseId}`)); } catch (cause) { setNotice(messageFrom(cause)); } };
  const imported = async (newCourse: Course) => { setCourse(newCourse); await refreshDashboard(); setNotice(`Imported ${newCourse.name}.`); };
  if (loading) return <div className="loading-screen"><div className="orbit" /><p>Opening your local learning workspace…</p></div>;
  return <div className="app-shell"><aside className="sidebar"><div className="brand"><div className="brand-mark">AI</div><div><strong>Personal</strong><span>Learning OS</span></div></div><button className="primary-button add-course" onClick={() => setShowImport(true)}>＋ Add course</button><nav><button className={!course ? "nav-item active" : "nav-item"} onClick={() => setCourse(null)}>⌂ Dashboard</button><p className="nav-label">MY COURSES</p>{dashboard?.courses.map((item) => <button key={item.id} className={course?.id === item.id ? "nav-item active course-nav" : "nav-item course-nav"} onClick={() => void selectCourse(item.id)}><span>{item.name}</span><small>{formatPercent(item.progress.course_completion)}</small></button>)}</nav><div className="sidebar-footer"><button className="nav-item" onClick={() => setShowSettings(true)}>⚙ Settings</button><p>Local-first · public sources only</p></div></aside><section className="app-content">{notice && <button className="toast" onClick={() => setNotice(null)}>{notice} <span>×</span></button>}{course ? <CourseWorkspace course={course} onRefresh={refreshCourse} notify={setNotice} /> : <main className="dashboard"><header><p className="eyebrow">YOUR LEARNING LIBRARY</p><h1>Make every good course a living practice.</h1><p className="lede">Watch what matters, preserve official sources, answer in your own notes, and retain a real learning record.</p></header><section className="metrics"><div><span>TODAY</span><strong>{formatSeconds(dashboard?.today_learning_seconds || 0)}</strong><small>tracked learning time</small></div><div><span>THIS WEEK</span><strong>{formatSeconds(dashboard?.weekly_learning_seconds || 0)}</strong><small>unique watching sessions</small></div><div><span>STREAK</span><strong>{dashboard?.streak_days || 0}</strong><small>days recorded</small></div><div><span>CERTIFICATES</span><strong>{dashboard?.certificates.length || 0}</strong><small>independent credentials</small></div></section><section className="continue-section"><div className="section-heading"><div><p className="eyebrow">CONTINUE LEARNING</p><h2>Your courses</h2></div><button onClick={() => setShowImport(true)}>Import course</button></div>{dashboard?.courses.length ? <div className="course-cards">{dashboard.courses.map((item) => <button key={item.id} className="course-card" onClick={() => void selectCourse(item.id)}><div><span className="tag">{item.code || item.source_type}</span><h3>{item.name}</h3><p>{item.channel_name || item.version || "Local course"}</p></div><ProgressRing value={item.progress.course_completion} /><small>{item.progress.completed_lecture_count}/{item.progress.required_lecture_count} lectures complete</small></button>)}</div> : <div className="empty-card welcome"><h2>Start with a public course</h2><p>Paste a YouTube playlist, video, or Stanford course URL. Every course remains database-driven and locally stored.</p><button className="primary-button" onClick={() => setShowImport(true)}>Add your first course</button></div>}</section><section className="principles"><div><strong>01</strong><h3>Official work stays official</h3><p>No invented assignments are presented as course work.</p></div><div><strong>02</strong><h3>Progress reflects coverage</h3><p>Overlapping and replayed viewing intervals are merged.</p></div><div><strong>03</strong><h3>Your files stay local</h3><p>Obsidian, submissions, records, and certificates remain on your machine.</p></div></section></main>}</section>{showImport && <ImportDialog onClose={() => setShowImport(false)} onImported={(newCourse) => void imported(newCourse)} />}{showSettings && <SettingsDialog onClose={() => setShowSettings(false)} />}</div>;
}
