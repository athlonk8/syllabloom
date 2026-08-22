import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { translate, type Locale } from "../lib/i18n";
import type { BilibiliPlayback, BilibiliQrCode, BilibiliQrPollResult, BilibiliSession, Lecture } from "../types/api";

const QR_POLL_INTERVAL_MS = 2_000;

type QrStatus = "loading" | "waiting" | "scanned" | "expired" | "error";

export function BilibiliPlayer({
  lecture,
  locale,
  onProgress,
}: {
  lecture: Lecture;
  locale: Locale;
  onProgress: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const sessionIdRef = useRef<number | null>(null);
  const lastPositionRef = useRef(0);
  const playingRef = useRef(false);
  const reportingRef = useRef(false);
  const pendingSeekRef = useRef(0);
  const resumeAfterSwapRef = useRef<{ time: number; playing: boolean } | null>(null);
  const localeRef = useRef(locale);
  const onProgressRef = useRef(onProgress);

  const [playback, setPlayback] = useState<BilibiliPlayback | null>(null);
  const [session, setSession] = useState<BilibiliSession | null>(null);
  const [statusKey, setStatusKey] = useState("player.preparing");
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const [loginOpen, setLoginOpen] = useState(false);
  const [qr, setQr] = useState<BilibiliQrCode | null>(null);
  const [qrStatus, setQrStatus] = useState<QrStatus>("loading");
  const [qrAttempt, setQrAttempt] = useState(0);

  // Imported multi-P lectures encode the part as "BVxxx?p=N"; P1 is the bare BV.
  const [bvid, pageSuffix] = (lecture.video?.external_id ?? "").split("?p=");
  const page = Number(pageSuffix) > 0 ? Number(pageSuffix) : 1;

  useEffect(() => {
    localeRef.current = locale;
  }, [locale]);

  useEffect(() => {
    onProgressRef.current = onProgress;
  }, [onProgress]);

  // ------------------------------------------------------------- reporting

  const reportInterval = useCallback(
    async (force = false) => {
      const video = videoRef.current;
      if (!video || (!playingRef.current && !force) || reportingRef.current) return;
      const current = Number(video.currentTime);
      const previous = lastPositionRef.current;
      const delta = current - previous;
      lastPositionRef.current = current;
      // A seek creates a discontinuity. Do not count skipped time as watched.
      if (delta <= 0 || delta > 14) return;

      reportingRef.current = true;
      try {
        const result = await api<{ session_id: number; completed: boolean }>("/watch/segments", {
          method: "POST",
          body: JSON.stringify({
            video_id: lecture.video?.id,
            start_seconds: previous,
            end_seconds: current,
            playback_rate: Number(video.playbackRate) || 1,
            session_id: sessionIdRef.current,
            duration_seconds: Number(video.duration) || undefined,
          }),
          keepalive: force,
        });
        sessionIdRef.current = result.session_id;
        setStatusKey(result.completed ? "player.complete" : "player.tracking");
        onProgressRef.current();
      } catch {
        setStatusKey("player.saveError");
      } finally {
        reportingRef.current = false;
      }
    },
    [lecture.video?.id],
  );

  // ------------------------------------------------------------ load flow

  useEffect(() => {
    if (!bvid) return;
    let cancelled = false;
    setError(null);
    setMenuOpen(false);
    setStatusKey("player.preparing");

    const setup = async () => {
      try {
        const sessionState = await api<BilibiliSession>("/bilibili/session");
        if (!cancelled) setSession(sessionState);
      } catch {
        if (!cancelled) setSession({ logged_in: false, mid: null, uname: null, vip_status: null });
      }
      try {
        const resume = await api<{ resume_position_seconds: number }>("/lectures/" + lecture.id + "/resume");
        pendingSeekRef.current = resume.resume_position_seconds > 2 ? resume.resume_position_seconds : 0;
      } catch {
        pendingSeekRef.current = 0;
      }
      const query = new URLSearchParams({ bvid, page: String(page) });
      try {
        const data = await api<BilibiliPlayback>("/bilibili/playurl?" + query.toString());
        if (!cancelled) {
          setPlayback(data);
          lastPositionRef.current = pendingSeekRef.current;
          setStatusKey(pendingSeekRef.current > 0 ? "player.resumed" : "player.ready");
        }
      } catch (cause) {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : translate(localeRef.current, "player.bilibiliLoadError"));
          setStatusKey("player.embedUnavailable");
        }
      }
    };

    void setup();
    return () => {
      cancelled = true;
    };
  }, [bvid, page, lecture.id, reloadKey]);

  // Swap the media source whenever a new playback descriptor arrives while
  // keeping the same <video> element so the watch session survives switches.
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !playback) return;

    const restore = resumeAfterSwapRef.current ?? { time: pendingSeekRef.current, playing: false };
    resumeAfterSwapRef.current = null;
    video.src = playback.stream_url;
    video.load();

    const onLoadedMetadata = () => {
      if (restore.time > 1) video.currentTime = restore.time;
      if (restore.playing) void video.play().catch(() => undefined);
    };
    video.addEventListener("loadedmetadata", onLoadedMetadata);
    return () => video.removeEventListener("loadedmetadata", onLoadedMetadata);
  }, [playback]);

  // ------------------------------------------------------- watch tracking

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const onPlay = () => {
      playingRef.current = true;
      lastPositionRef.current = Number(video.currentTime);
    };
    const onPause = () => {
      playingRef.current = false;
      void reportInterval(true);
    };
    const onEnded = () => {
      playingRef.current = false;
      void reportInterval(true);
    };
    video.addEventListener("play", onPlay);
    video.addEventListener("pause", onPause);
    video.addEventListener("ended", onEnded);

    const interval = window.setInterval(() => void reportInterval(), 7_000);
    const unload = () => void reportInterval(true);
    window.addEventListener("beforeunload", unload);

    return () => {
      window.clearInterval(interval);
      window.removeEventListener("beforeunload", unload);
      video.removeEventListener("play", onPlay);
      video.removeEventListener("pause", onPause);
      video.removeEventListener("ended", onEnded);
      void reportInterval(true);
      if (sessionIdRef.current) void api("/watch/sessions/" + sessionIdRef.current + "/finish", { method: "POST" });
      sessionIdRef.current = null;
      playingRef.current = false;
    };
  }, [reportInterval]);

  // ------------------------------------------------------------ quality ui

  const currentQuality = playback?.qualities.find((item) => item.id === playback.quality_id);

  const changeQuality = async (qn: number) => {
    setMenuOpen(false);
    const video = videoRef.current;
    if (!bvid || !playback || !video || qn === playback.quality_id) return;
    resumeAfterSwapRef.current = { time: video.currentTime, playing: !video.paused };
    try {
      const query = new URLSearchParams({ bvid, page: String(page), qn: String(qn) });
      setStatusKey("player.preparing");
      const next = await api<BilibiliPlayback>("/bilibili/playurl?" + query.toString());
      setPlayback(next);
      setStatusKey("player.ready");
    } catch (cause) {
      resumeAfterSwapRef.current = null;
      setError(cause instanceof Error ? cause.message : translate(localeRef.current, "player.bilibiliLoadError"));
    }
  };

  // -------------------------------------------------------------- qr login

  useEffect(() => {
    if (!loginOpen) return;
    let cancelled = false;
    let timer: number | undefined;

    const poll = async (qrcodeKey: string) => {
      try {
        const result = await api<BilibiliQrPollResult>("/bilibili/login/poll", {
          method: "POST",
          body: JSON.stringify({ qrcode_key: qrcodeKey }),
        });
        if (cancelled) return;
        if (result.status === "confirmed") {
          setLoginOpen(false);
          if (result.session) setSession(result.session);
          setReloadKey((key) => key + 1);
          return;
        }
        if (result.status === "scanned") setQrStatus("scanned");
        else if (result.status === "expired") {
          setQrStatus("expired");
          return; // stop polling until the learner requests a fresh code
        }
      } catch {
        if (!cancelled) setQrStatus("error");
        return;
      }
      timer = window.setTimeout(() => void poll(qrcodeKey), QR_POLL_INTERVAL_MS);
    };

    const start = async () => {
      setQr(null);
      setQrStatus("loading");
      try {
        const code = await api<BilibiliQrCode>("/bilibili/login/qrcode");
        if (cancelled) return;
        setQr(code);
        setQrStatus("waiting");
        timer = window.setTimeout(() => void poll(code.qrcode_key), QR_POLL_INTERVAL_MS);
      } catch {
        if (!cancelled) setQrStatus("error");
      }
    };

    void start();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [loginOpen, qrAttempt]);

  const logout = async () => {
    try {
      await api("/bilibili/session", { method: "DELETE" });
    } catch {
      // Clearing local state regardless keeps the UI consistent.
    }
    setSession({ logged_in: false, mid: null, uname: null, vip_status: null });
    setReloadKey((key) => key + 1);
  };

  const qrImage = qr ? "data:image/svg+xml;utf8," + encodeURIComponent(qr.qr_svg) : null;
  const anonymousHintNeeded = Boolean(playback && !session?.logged_in);

  return (
    <section className="player-shell bilibili-shell" aria-label={translate(locale, "player.bilibiliLabel", { title: lecture.title })}>
      <div className="player-frame">
        <video ref={videoRef} className="bilibili-video" controls preload="metadata" playsInline />
        {!playback && !error ? <div className="player-loading">{translate(locale, statusKey)}</div> : null}
      </div>
      <div className="player-meta">
        <span className="live-dot" />
        {translate(locale, error ? "player.embedUnavailable" : statusKey)}
        {error ? <span className="inline-error">{error}</span> : null}
        <span className="player-source-note">{translate(locale, "player.bilibiliNotice")}</span>
      </div>
      <div className="bilibili-controls">
        <div>
          <strong>{currentQuality ? `${translate(locale, "player.bilibiliQuality")} · ${currentQuality.label}` : translate(locale, "player.bilibiliQuality")}</strong>
          <span aria-live="polite">
            {anonymousHintNeeded
              ? translate(locale, "player.bilibiliQualityHint")
              : translate(locale, "player.bilibiliSignedInHint")}
          </span>
        </div>
        <div className="bilibili-control-actions quality-actions">
          <div className="quality-menu-anchor">
            <button type="button" onClick={() => setMenuOpen((open) => !open)} disabled={!playback}>
              {currentQuality ? `${translate(locale, "player.bilibiliQuality")} ▾` : translate(locale, "player.bilibiliQualityLoading")}
            </button>
            {menuOpen && playback ? (
              <ul className="quality-menu" role="listbox" aria-label={translate(locale, "player.bilibiliQuality")}>
                {playback.qualities.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={item.id === playback.quality_id}
                      className={item.id === playback.quality_id ? "quality-option active" : "quality-option"}
                      onClick={() => void changeQuality(item.id)}
                    >
                      {item.label}
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
          {session?.logged_in ? (
            <>
              <span className="bilibili-session-chip">{translate(locale, "player.bilibiliLoggedInAs", { name: session.uname ?? "" })}</span>
              <button type="button" onClick={() => void logout()}>{translate(locale, "player.bilibiliLogout")}</button>
            </>
          ) : (
            <button type="button" onClick={() => setLoginOpen(true)}>{translate(locale, "player.bilibiliLogin")}</button>
          )}
        </div>
      </div>

      {loginOpen ? (
        <div className="modal-backdrop" role="presentation" onClick={() => setLoginOpen(false)}>
          <div className="modal bilibili-login-modal" role="dialog" aria-modal="true" aria-label={translate(locale, "player.bilibiliLoginTitle")} onClick={(event) => event.stopPropagation()}>
            <button type="button" className="close" onClick={() => setLoginOpen(false)} aria-label={translate(locale, "player.bilibiliClose")}>×</button>
            <h2>{translate(locale, "player.bilibiliLoginTitle")}</h2>
            <p className="hint">{translate(locale, "player.bilibiliLoginHint")}</p>
            <div className="qr-code-box">
              {qrImage ? (
                <img src={qrImage} alt={translate(locale, "player.bilibiliLoginTitle")} width={196} height={196} />
              ) : (
                <span className="qr-placeholder">…</span>
              )}
            </div>
            <p className="qr-status" aria-live="polite">
              {qrStatus === "loading"
                ? translate(locale, "player.bilibiliQrLoading")
                : qrStatus === "waiting"
                  ? translate(locale, "player.bilibiliQrWaiting")
                  : qrStatus === "scanned"
                    ? translate(locale, "player.bilibiliQrScanned")
                    : qrStatus === "expired"
                      ? translate(locale, "player.bilibiliQrExpired")
                      : translate(locale, "player.bilibiliQrError")}
            </p>
            {qrStatus === "expired" || qrStatus === "error" ? (
              <div className="button-row">
                <button type="button" onClick={() => setQrAttempt((attempt) => attempt + 1)}>
                  {translate(locale, "player.bilibiliQrRefresh")}
                </button>
                <button type="button" onClick={() => setLoginOpen(false)}>{translate(locale, "player.bilibiliClose")}</button>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}
