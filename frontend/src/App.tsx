import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { YouTubePlayer } from "./components/YouTubePlayer";
import { api, ApiError } from "./lib/api";
import { detectLocale, localeLink, translate, type Locale, type Translator } from "./lib/i18n";
import { formatPercent, formatSeconds } from "./lib/format";
import { getInitialThemePreference, persistThemePreference, resolveTheme, systemPrefersDark, type ThemePreference } from "./lib/theme";
import type { Assignment, Course, Dashboard } from "./types/api";

const PRESETS = [
  { label: "Karpathy - Zero to Hero", type: "youtube", url: "https://www.youtube.com/@AndrejKarpathy/playlists" },
  { label: "Stanford CS229", type: "stanford", url: "https://cs229.stanford.edu/" },
  { label: "Stanford CS224N", type: "stanford", url: "https://web.stanford.edu/class/cs224n/" },
  { label: "Stanford CS336", type: "stanford", url: "https://cs336.stanford.edu/" },
];

type AIProviderName = "codex_cli" | "openai_compatible" | "disabled";

type AIProviderStatus = {
  provider: AIProviderName | "invalid";
  base_url: string | null;
  model: string | null;
  api_key_configured: boolean;
  uses_network: boolean;
  error?: string;
  codex: { installed: boolean; version?: string; error?: string };
};

function messageFrom(error: unknown, t: Translator): string {
  return error instanceof Error ? error.message : t("error.generic");
}

function ProgressRing({ value }: { value: number }) {
  return (
    <span
      className="progress-ring"
      style={{ "--progress": String(Math.max(0, Math.min(100, value * 100))) + "%" } as CSSProperties}
    >
      {formatPercent(value)}
    </span>
  );
}

function assignmentStatus(status: string, t: Translator): string {
  const key = "assignment.status." + status;
  const localized = t(key);
  return localized === key ? status.replaceAll("_", " ") : localized;
}

function ImportDialog({
  onClose,
  onImported,
  t,
}: {
  onClose: () => void;
  onImported: (course: Course) => void;
  t: Translator;
}) {
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
    setBusy(true);
    setError(null);
    try {
      let response: { course: Course };
      if (mode === "youtube") {
        response = await api("/imports/youtube", { method: "POST", body: JSON.stringify({ url }) });
      } else if (mode === "stanford") {
        response = await api("/imports/stanford", {
          method: "POST",
          body: JSON.stringify({ url, max_pages: 18, max_depth: 1 }),
        });
      } else {
        response = await api("/imports/manual-youtube", {
          method: "POST",
          body: JSON.stringify({ name, videos: [{ url, title: videoTitle || name }] }),
        });
      }
      onImported(response.course);
      onClose();
    } catch (cause) {
      setError(messageFrom(cause, t));
      if (cause instanceof ApiError && mode === "youtube" && cause.message.includes("API key")) setMode("manual");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label={t("import.dialogLabel")}>
      <form className="modal" onSubmit={submit}>
        <button className="icon-button close" type="button" onClick={onClose} aria-label={t("common.close")}>×</button>
        <p className="eyebrow">{t("import.library")}</p>
        <h2>{t("import.title")}</h2>
        <p className="muted">{t("import.policy")}</p>
        <div className="segmented">
          <button type="button" className={mode === "youtube" ? "selected" : ""} onClick={() => setMode("youtube")}>{t("import.youtubeApi")}</button>
          <button type="button" className={mode === "stanford" ? "selected" : ""} onClick={() => setMode("stanford")}>{t("import.stanfordUrl")}</button>
          <button type="button" className={mode === "manual" ? "selected" : ""} onClick={() => setMode("manual")}>{t("import.manualFallback")}</button>
        </div>
        {mode === "manual" && (
          <>
            <label>{t("import.courseName")}<input value={name} onChange={(event) => setName(event.target.value)} required placeholder={t("import.courseNamePlaceholder")} /></label>
            <label>{t("import.videoTitle")}<input value={videoTitle} onChange={(event) => setVideoTitle(event.target.value)} placeholder={t("import.videoTitlePlaceholder")} /></label>
          </>
        )}
        <label>
          {mode === "stanford" ? t("import.stanfordCourseUrl") : t("import.youtubeUrl")}
          <input value={url} onChange={(event) => setUrl(event.target.value)} required type="url" placeholder="https://…" />
        </label>
        {mode === "youtube" && <p className="hint">{t("import.youtubeHint")}</p>}
        {error && <p className="inline-error">{error}</p>}
        <button className="primary-button" disabled={busy}>{busy ? t("import.importing") : t("import.submit")}</button>
        <div className="preset-list">
          <span className="muted">{t("import.presets")}</span>
          {PRESETS.map((preset) => <button type="button" key={preset.label} onClick={() => usePreset(preset)}>{preset.label}</button>)}
        </div>
      </form>
    </div>
  );
}

function SettingsDialog({ onClose, t }: { onClose: () => void; t: Translator }) {
  const [youtubeKey, setYoutubeKey] = useState("");
  const [vaultPath, setVaultPath] = useState("");
  const [threshold, setThreshold] = useState("0.85");
  const [provider, setProvider] = useState<AIProviderName>("codex_cli");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiKeyConfigured, setApiKeyConfigured] = useState(false);
  const [clearApiKey, setClearApiKey] = useState(false);
  const [codex, setCodex] = useState<{ installed: boolean; version?: string; error?: string } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    void (async () => {
      const [settings, aiStatus] = await Promise.all([
        api<{ obsidian_vault_path: string | null; watch_completion_threshold: number }>("/settings"),
        api<AIProviderStatus>("/settings/ai-provider"),
      ]);
      const nextProvider: AIProviderName = aiStatus.provider === "codex_cli" || aiStatus.provider === "openai_compatible" || aiStatus.provider === "disabled"
        ? aiStatus.provider
        : "disabled";
      setVaultPath(settings.obsidian_vault_path || "");
      setThreshold(String(settings.watch_completion_threshold));
      setProvider(nextProvider);
      setBaseUrl(aiStatus.base_url || "");
      setModel(aiStatus.model || "");
      setApiKeyConfigured(aiStatus.api_key_configured);
      setCodex(aiStatus.codex);
      if (aiStatus.error) setNotice(aiStatus.error);
    })().catch((cause) => {
      setSaved(false);
      setNotice(messageFrom(cause, t));
    });
  }, [t]);

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setNotice(null);
    setSaved(false);
    try {
      if (youtubeKey.trim()) {
        await api("/settings/value/YOUTUBE_API_KEY", {
          method: "PUT",
          body: JSON.stringify({ value: youtubeKey, is_secret: true }),
        });
      }
      await api("/settings/value/watch_completion_threshold", {
        method: "PUT",
        body: JSON.stringify({ value: threshold }),
      });
      if (vaultPath.trim()) {
        await api("/settings/obsidian", {
          method: "PUT",
          body: JSON.stringify({ vault_path: vaultPath, create_if_missing: false }),
        });
      }
      const providerPayload: {
        provider: AIProviderName;
        base_url?: string;
        model?: string;
        api_key?: string;
        clear_api_key?: boolean;
      } = { provider };
      if (provider === "openai_compatible") {
        providerPayload.base_url = baseUrl;
        providerPayload.model = model;
        if (apiKey.trim()) providerPayload.api_key = apiKey;
        if (clearApiKey) providerPayload.clear_api_key = true;
      }
      const aiStatus = await api<AIProviderStatus>("/settings/ai-provider", {
        method: "PUT",
        body: JSON.stringify(providerPayload),
      });
      setApiKey("");
      setClearApiKey(false);
      setApiKeyConfigured(aiStatus.api_key_configured);
      setCodex(aiStatus.codex);
      setSaved(true);
      setNotice(t("settings.saved"));
    } catch (cause) {
      setSaved(false);
      setNotice(messageFrom(cause, t));
    }
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label={t("settings.dialogLabel")}>
      <form className="modal settings-modal" onSubmit={save}>
        <button className="icon-button close" type="button" onClick={onClose} aria-label={t("common.close")}>×</button>
        <p className="eyebrow">{t("settings.eyebrow")}</p>
        <h2>{t("settings.title")}</h2>
        <label>{t("settings.youtubeKey")}<input value={youtubeKey} onChange={(event) => setYoutubeKey(event.target.value)} type="password" placeholder={t("settings.youtubePlaceholder")} autoComplete="off" /></label>
        <label>{t("settings.vaultPath")}<input value={vaultPath} onChange={(event) => setVaultPath(event.target.value)} placeholder={t("settings.vaultPlaceholder")} /></label>
        <label>{t("settings.threshold")}<input value={threshold} onChange={(event) => setThreshold(event.target.value)} type="number" min="0.01" max="1" step="0.01" /></label>
        <label>
          {t("settings.provider")}
          <select value={provider} onChange={(event) => setProvider(event.target.value as AIProviderName)}>
            <option value="codex_cli">{t("settings.provider.codex")}</option>
            <option value="openai_compatible">{t("settings.provider.compatible")}</option>
            <option value="disabled">{t("settings.provider.disabled")}</option>
          </select>
        </label>
        {provider === "openai_compatible" && (
          <div className="provider-fields">
            <label>{t("settings.baseUrl")}<input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} required placeholder="http://localhost:11434/v1" /></label>
            <label>{t("settings.model")}<input value={model} onChange={(event) => setModel(event.target.value)} required placeholder={t("settings.modelPlaceholder")} /></label>
            <label>{t("settings.apiKey")}<input value={apiKey} onChange={(event) => setApiKey(event.target.value)} type="password" placeholder={apiKeyConfigured ? t("settings.apiKeySaved") : t("settings.apiKeyEmpty")} autoComplete="off" /></label>
            {apiKeyConfigured && <label className="checkbox-row"><input type="checkbox" checked={clearApiKey} onChange={(event) => setClearApiKey(event.target.checked)} /> {t("settings.removeKey")}</label>}
            <p className="hint">{t("settings.compatibleHint")}</p>
          </div>
        )}
        {provider === "disabled" && <p className="hint">{t("settings.disabledHint")}</p>}
        <p className="hint">{t("settings.vaultHint")}</p>
        <div className="codex-status">
          <strong>{t("settings.codex")}</strong>
          <span className={codex?.installed ? "status-good" : "status-warn"}>{codex ? (codex.installed ? codex.version : codex.error) : t("settings.checking")}</span>
        </div>
        {notice && <p className={saved ? "notice" : "inline-error"}>{notice}</p>}
        <button className="primary-button">{t("settings.save")}</button>
      </form>
    </div>
  );
}

function AssignmentCard({
  assignment,
  refresh,
  notify,
  t,
}: {
  assignment: Assignment;
  refresh: () => Promise<void>;
  notify: (message: string) => void;
  t: Translator;
}) {
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<Array<{ version: number; grades: Array<{ score: number | null; status: string; score_type: string }> }> | null>(null);

  const invoke = async (path: string, payload?: object) => {
    setBusy(true);
    try {
      const result = await api<Record<string, unknown>>(path, { method: "POST", body: payload ? JSON.stringify(payload) : undefined });
      notify(typeof result.root === "string" ? t("notice.savedLocally", { root: result.root }) : t("notice.actionCompleted"));
      await refresh();
    } catch (cause) {
      notify(messageFrom(cause, t));
    } finally {
      setBusy(false);
    }
  };

  const loadHistory = async () => {
    try {
      const result = await api<{ submissions: typeof history }>("/assignments/" + assignment.id + "/history");
      setHistory(result.submissions);
    } catch (cause) {
      notify(messageFrom(cause, t));
    }
  };

  return (
    <article className="assignment-card">
      <div className="assignment-heading">
        <div><span className="tag">{assignment.key}</span><h4>{assignment.title}</h4></div>
        <span className={"assignment-status " + assignment.status}>{assignmentStatus(assignment.status, t)}</span>
      </div>
      <p>{assignment.description || t("assignment.defaultDescription")}</p>
      {assignment.protected_resource ? (
        <p className="protected">{t("assignment.protected")}</p>
      ) : (
        <div className="button-row">
          <button disabled={busy} onClick={() => void invoke("/assignments/" + assignment.id + "/download")}>{t("assignment.download")}</button>
          <button disabled={busy} onClick={() => void invoke("/assignments/" + assignment.id + "/prepare-workspace")}>{t("assignment.createNotes")}</button>
          {assignment.local_root && <button disabled={busy} onClick={() => void invoke("/assignments/" + assignment.id + "/open-workspace")}>{t("assignment.openWorkspace")}</button>}
        </div>
      )}
      <label className="acknowledgement"><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} /> {t("assignment.ack")}</label>
      <button
        className="primary-button compact"
        disabled={busy || !acknowledged || assignment.protected_resource}
        onClick={() => void invoke("/assignments/" + assignment.id + "/submit", {
          run_official_tests: true,
          run_ai_review: true,
          acknowledge_cloud_submission: true,
        })}
      >
        {t("assignment.submit")}
      </button>
      <button className="text-button" onClick={() => void loadHistory()}>{t("assignment.history")}</button>
      {history && (
        <div className="grading-history">
          {history.length
            ? history.map((item) => (
              <p key={item.version}>
                v{item.version}: {item.grades.map((grade) => (grade.score ?? "-") + " (" + grade.score_type + ", " + grade.status + ")").join(" · ") || t("assignment.noGrade")}
              </p>
            ))
            : <p>{t("assignment.noSubmissions")}</p>}
        </div>
      )}
    </article>
  );
}

function CourseWorkspace({
  course,
  locale,
  onRefresh,
  notify,
  t,
}: {
  course: Course;
  locale: Locale;
  onRefresh: () => Promise<void>;
  notify: (message: string) => void;
  t: Translator;
}) {
  const lectures = course.lectures || [];
  const [lectureId, setLectureId] = useState<number | null>(lectures[0]?.id ?? null);
  const [creatingCertificate, setCreatingCertificate] = useState(false);

  useEffect(() => setLectureId(lectures[0]?.id ?? null), [course.id]);

  const lecture = lectures.find((item) => item.id === lectureId) || lectures[0];
  const lectureProgress = useMemo(
    () => new Map(course.progress.lectures.map((item) => [item.lecture_id, item])),
    [course.progress.lectures],
  );

  const exportNotes = async () => {
    try {
      const result = await api<{ root: string }>("/courses/" + course.id + "/obsidian", { method: "POST" });
      notify(t("notice.notesCreated", { root: result.root }));
    } catch (cause) {
      notify(messageFrom(cause, t));
    }
  };

  const certificate = async () => {
    const name = window.prompt(t("course.certificatePrompt"));
    if (!name) return;
    setCreatingCertificate(true);
    try {
      const result = await api<{ download_url: string; certificate_id: string }>("/courses/" + course.id + "/certificates", {
        method: "POST",
        body: JSON.stringify({ certificate_type: "completion", learner_name: name }),
      });
      window.open(result.download_url, "_blank", "noopener");
      notify(t("notice.certificateGenerated", { certificateId: result.certificate_id }));
      await onRefresh();
    } catch (cause) {
      notify(messageFrom(cause, t));
    } finally {
      setCreatingCertificate(false);
    }
  };

  return (
    <main className="workspace">
      <header className="course-header">
        <div>
          <p className="eyebrow">{course.code || course.source_type.toUpperCase()} {course.version || ""}</p>
          <h1>{course.name}</h1>
          <p className="muted">{course.description || t("course.defaultDescription")}</p>
        </div>
        <div className="header-actions">
          <button onClick={() => void exportNotes()}>{t("course.exportNotes")}</button>
          <button className="primary-button" disabled={creatingCertificate} onClick={() => void certificate()}>{t("course.certificate")}</button>
        </div>
      </header>
      <div className="course-layout">
        <aside className="lecture-list">
          <div className="section-title"><span>{t("course.lectures")}</span><b>{course.progress.completed_lecture_count}/{course.progress.required_lecture_count}</b></div>
          {lectures.length ? lectures.map((item) => {
            const itemProgress = lectureProgress.get(item.id);
            return (
              <button key={item.id} className={item.id === lecture?.id ? "lecture-item active" : "lecture-item"} onClick={() => setLectureId(item.id)}>
                <span className={itemProgress?.completed ? "check done" : "check"}>{itemProgress?.completed ? "✓" : String(item.order_index).padStart(2, "0")}</span>
                <span>{item.title}<small>{t("course.watched", { percent: formatPercent(itemProgress?.fraction || 0) })}</small></span>
              </button>
            );
          }) : <p className="empty-note">{t("course.noLectures")}</p>}
        </aside>
        <section className="learning-stage">
          {lecture?.video ? (
            <YouTubePlayer lecture={lecture} locale={locale} onProgress={() => void onRefresh()} />
          ) : (
            <div className="empty-player"><h3>{t("course.noPlayer")}</h3><p>{t("course.noPlayerDescription")}</p></div>
          )}
          {lecture && (
            <div className="lecture-context">
              <div>
                <p className="eyebrow">{t("course.lecture", { number: lecture.order_index })}</p>
                <h2>{lecture.title}</h2>
                <p>{lecture.description || t("course.defaultLectureDescription")}</p>
              </div>
              {lecture.source_url && <a href={lecture.source_url} target="_blank" rel="noreferrer">{t("course.officialSource")}</a>}
            </div>
          )}
        </section>
        <aside className="course-inspector">
          <div className="progress-card">
            <ProgressRing value={course.progress.course_completion} />
            <div>
              <span>{t("course.progress")}</span>
              <strong>{formatPercent(course.progress.course_completion)}</strong>
              <small>{t("course.requiredAssignments", { passed: course.progress.passed_assignment_count, required: course.progress.required_assignment_count })}</small>
            </div>
          </div>
          <div className="inspector-block">
            <h3>{t("course.sourcePolicy")}</h3>
            {course.course_ai_policy ? (
              <details className="policy-details">
                <summary>{t("course.showImportedPolicy")}</summary>
                <p>{course.course_ai_policy}</p>
              </details>
            ) : (
              <p>{t("course.noPolicy")}</p>
            )}
            {course.official_course_url && <a href={course.official_course_url} target="_blank" rel="noreferrer">{t("course.officialPage")}</a>}
          </div>
          <div className="inspector-block">
            <h3>{t("course.learningRecord")}</h3>
            <p>{t("course.averageScore", { score: course.progress.average_assignment_score ?? t("course.notGraded") })}</p>
            <p>{t("course.completionRequires", { threshold: formatPercent(0.85) })}</p>
          </div>
        </aside>
      </div>
      <section className="resource-section">
        <div><p className="eyebrow">{t("course.officialWork")}</p><h2>{t("course.assignments")}</h2></div>
        <div className="assignment-grid">
          {(course.assignments || []).length
            ? course.assignments?.map((item) => <AssignmentCard key={item.id} assignment={item} refresh={onRefresh} notify={notify} t={t} />)
            : <div className="empty-card"><h3>{t("course.noAssignments")}</h3><p>{t("course.noAssignmentsDescription")}</p></div>}
        </div>
      </section>
      <section className="resource-section provenance">
        <div><p className="eyebrow">{t("course.traceability")}</p><h2>{t("course.provenance")}</h2></div>
        {(course.resources || []).length ? (
          <details className="provenance-details">
            <summary>{t("course.showResources", { count: course.resources?.length || 0 })}</summary>
            <div className="resource-table">
              {course.resources?.map((resource) => (
                <div key={resource.id}>
                  <span className={resource.access_status === "protected" ? "status-warn" : "status-good"}>{resource.resource_type}</span>
                  <a href={resource.resource_url} target="_blank" rel="noreferrer">{resource.title}</a>
                  <small>{resource.access_status === "protected"
                    ? t("course.protectedResource")
                    : t("course.discoveredFrom", { source: resource.source_page_url || t("course.source") })}</small>
                </div>
              ))}
            </div>
          </details>
        ) : (
          <p className="empty-note">{t("course.noResources")}</p>
        )}
      </section>
    </main>
  );
}

export default function App() {
  const [locale, setLocale] = useState<Locale>(detectLocale);
  const [themePreference, setThemePreference] = useState<ThemePreference>(getInitialThemePreference);
  const [prefersDark, setPrefersDark] = useState(systemPrefersDark);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [course, setCourse] = useState<Course | null>(null);
  const [showImport, setShowImport] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const t = useCallback<Translator>((key, values) => translate(locale, key, values), [locale]);
  const resolvedTheme = resolveTheme(themePreference, prefersDark);

  useEffect(() => {
    document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
    document.title = translate(locale, "app.title");
    try {
      window.localStorage.setItem("syllabloom.locale", locale);
    } catch {
      // Local storage is optional; the query-string language links still work.
    }
  }, [locale]);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const update = (event: MediaQueryListEvent) => setPrefersDark(event.matches);
    setPrefersDark(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = resolvedTheme;
    document.documentElement.style.colorScheme = resolvedTheme;
    persistThemePreference(themePreference);
  }, [resolvedTheme, themePreference]);

  const refreshDashboard = async () => {
    const data = await api<Dashboard>("/dashboard");
    setDashboard(data);
    return data;
  };

  const refreshCourse = async () => {
    if (!course) return;
    const data = await api<Course>("/courses/" + course.id);
    setCourse(data);
    await refreshDashboard();
  };

  useEffect(() => {
    void refreshDashboard()
      .then((data) => {
        if (data.courses[0]) return api<Course>("/courses/" + data.courses[0].id).then(setCourse);
      })
      .catch((cause) => setNotice(messageFrom(cause, t)))
      .finally(() => setLoading(false));
  }, [t]);

  const selectCourse = async (courseId: number) => {
    try {
      setCourse(await api<Course>("/courses/" + courseId));
    } catch (cause) {
      setNotice(messageFrom(cause, t));
    }
  };

  const imported = async (newCourse: Course) => {
    setCourse(newCourse);
    await refreshDashboard();
    setNotice(t("notice.imported", { name: newCourse.name }));
  };

  const changeLocale = (nextLocale: Locale) => {
    const url = new URL(window.location.href);
    url.searchParams.set("lang", nextLocale);
    window.history.replaceState({}, "", url.pathname + url.search + url.hash);
    setLocale(nextLocale);
  };

  const toggleTheme = () => {
    setThemePreference(resolvedTheme === "dark" ? "light" : "dark");
  };

  if (loading) {
    return <div className="loading-screen"><div className="orbit" /><p>{t("app.loading")}</p></div>;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">SB</div>
          <div><strong>Syllabloom</strong><span>{locale === "zh" ? "本地学习工作台" : "Local learning workspace"}</span></div>
        </div>
        <button className="primary-button add-course" onClick={() => setShowImport(true)}>{t("nav.addCourse")}</button>
        <nav>
          <button className={!course ? "nav-item active" : "nav-item"} onClick={() => setCourse(null)}>{t("nav.dashboard")}</button>
          <p className="nav-label">{t("nav.myCourses")}</p>
          {dashboard?.courses.map((item) => (
            <button key={item.id} className={course?.id === item.id ? "nav-item active course-nav" : "nav-item course-nav"} onClick={() => void selectCourse(item.id)}>
              <span>{item.name}</span><small>{formatPercent(item.progress.course_completion)}</small>
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <button className="nav-item" onClick={() => setShowSettings(true)}>{t("nav.settings")}</button>
          <p>{t("nav.localFirst")}</p>
          <div className="theme-switcher" aria-label={t("theme.label")}>
            <span>{t("theme.label")}</span>
            <button
              className="theme-toggle"
              type="button"
              aria-label={t(resolvedTheme === "dark" ? "theme.switchToLight" : "theme.switchToDark")}
              aria-pressed={resolvedTheme === "dark"}
              onClick={toggleTheme}
            >
              <span aria-hidden="true">{resolvedTheme === "dark" ? "☾" : "☀"}</span>
              {t(resolvedTheme === "dark" ? "theme.dark" : "theme.light")}
            </button>
          </div>
          <div className="language-switcher" aria-label={t("language.label")}>
            <a href={localeLink("en")} className={locale === "en" ? "active" : ""} onClick={(event) => { event.preventDefault(); changeLocale("en"); }}>English</a>
            <span aria-hidden="true">·</span>
            <a href={localeLink("zh")} className={locale === "zh" ? "active" : ""} onClick={(event) => { event.preventDefault(); changeLocale("zh"); }}>中文</a>
          </div>
        </div>
      </aside>
      <section className="app-content">
        {notice && <button className="toast" onClick={() => setNotice(null)}>{notice} <span>×</span></button>}
        {course ? (
          <CourseWorkspace course={course} locale={locale} onRefresh={refreshCourse} notify={setNotice} t={t} />
        ) : (
          <main className="dashboard">
            <header>
              <p className="eyebrow">{t("dashboard.library")}</p>
              <h1>{t("dashboard.title")}</h1>
              <p className="lede">{t("dashboard.lede")}</p>
            </header>
            <section className="metrics">
              <div><span>{t("dashboard.today")}</span><strong>{formatSeconds(dashboard?.today_learning_seconds || 0, locale)}</strong><small>{t("dashboard.trackedTime")}</small></div>
              <div><span>{t("dashboard.week")}</span><strong>{formatSeconds(dashboard?.weekly_learning_seconds || 0, locale)}</strong><small>{t("dashboard.uniqueSessions")}</small></div>
              <div><span>{t("dashboard.streak")}</span><strong>{dashboard?.streak_days || 0}</strong><small>{t("dashboard.daysRecorded")}</small></div>
              <div><span>{t("dashboard.certificates")}</span><strong>{dashboard?.certificates.length || 0}</strong><small>{t("dashboard.independentCredentials")}</small></div>
            </section>
            <section className="continue-section">
              <div className="section-heading">
                <div><p className="eyebrow">{t("dashboard.continue")}</p><h2>{t("dashboard.yourCourses")}</h2></div>
                <button onClick={() => setShowImport(true)}>{t("dashboard.importCourse")}</button>
              </div>
              {dashboard?.courses.length ? (
                <div className="course-cards">
                  {dashboard.courses.map((item) => (
                    <button key={item.id} className="course-card" onClick={() => void selectCourse(item.id)}>
                      <div><span className="tag">{item.code || item.source_type}</span><h3>{item.name}</h3><p>{item.channel_name || item.version || t("dashboard.localCourse")}</p></div>
                      <ProgressRing value={item.progress.course_completion} />
                      <small>{t("dashboard.lecturesComplete", { completed: item.progress.completed_lecture_count, required: item.progress.required_lecture_count })}</small>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="empty-card welcome">
                  <h2>{t("dashboard.start")}</h2>
                  <p>{t("dashboard.startDescription")}</p>
                  <button className="primary-button" onClick={() => setShowImport(true)}>{t("dashboard.addFirst")}</button>
                </div>
              )}
            </section>
            <section className="principles">
              <div><strong>01</strong><h3>{t("principle.official.title")}</h3><p>{t("principle.official.description")}</p></div>
              <div><strong>02</strong><h3>{t("principle.progress.title")}</h3><p>{t("principle.progress.description")}</p></div>
              <div><strong>03</strong><h3>{t("principle.local.title")}</h3><p>{t("principle.local.description")}</p></div>
            </section>
          </main>
        )}
      </section>
      {showImport && <ImportDialog onClose={() => setShowImport(false)} onImported={(newCourse) => void imported(newCourse)} t={t} />}
      {showSettings && <SettingsDialog onClose={() => setShowSettings(false)} t={t} />}
    </div>
  );
}
