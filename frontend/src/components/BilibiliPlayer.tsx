import { useCallback, useEffect, useRef, useState } from "react";
import { translate, type Locale } from "../lib/i18n";
import type { Lecture } from "../types/api";

export function BilibiliPlayer({ lecture, locale, courseId }: { lecture: Lecture; locale: Locale; courseId: number }) {
  const [failed, setFailed] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [fullscreen, setFullscreen] = useState(false);
  const [fullscreenError, setFullscreenError] = useState(false);
  const [returnedFromLogin, setReturnedFromLogin] = useState(false);
  const shellRef = useRef<HTMLElement>(null);
  const embedUrl = lecture.video?.embed_url;
  const playerId = `bilibili-player-${lecture.id}`;

  const refreshPlayer = useCallback(() => {
    setFailed(false);
    setFullscreenError(false);
    setReloadKey((key) => key + 1);
  }, []);

  useEffect(() => {
    const updateFullscreen = () => setFullscreen(document.fullscreenElement === shellRef.current);
    document.addEventListener("fullscreenchange", updateFullscreen);
    return () => document.removeEventListener("fullscreenchange", updateFullscreen);
  }, []);

  useEffect(() => {
    const returnUrl = new URL(window.location.href);
    const completedHere = returnUrl.searchParams.get("bilibili_login") === "complete"
      && returnUrl.searchParams.get("bilibili_lecture") === String(lecture.id);
    if (!completedHere) {
      setReturnedFromLogin(false);
      return;
    }

    returnUrl.searchParams.delete("bilibili_login");
    returnUrl.searchParams.delete("bilibili_lecture");
    window.history.replaceState({}, "", returnUrl.pathname + returnUrl.search + returnUrl.hash);
    setReturnedFromLogin(true);
    refreshPlayer();
    window.requestAnimationFrame(() => shellRef.current?.scrollIntoView({ block: "center" }));
  }, [lecture.id, refreshPlayer]);

  const openLogin = () => {
    const returnUrl = new URL(window.location.href);
    returnUrl.searchParams.set("course", String(courseId));
    returnUrl.searchParams.set("bilibili_login", "complete");
    returnUrl.searchParams.set("bilibili_lecture", String(lecture.id));
    returnUrl.hash = playerId;
    const loginUrl = new URL("https://passport.bilibili.com/login");
    loginUrl.searchParams.set("gourl", returnUrl.toString());

    // Authentication happens in Bilibili's own first-party page.  The `gourl`
    // return target brings the same tab back to this course, where the player
    // is re-mounted without Syllabloom seeing credentials or cookies.
    window.location.assign(loginUrl.toString());
  };

  const toggleFullscreen = async () => {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
      } else {
        const shell = shellRef.current;
        if (!shell) throw new Error("Player shell is unavailable.");
        await shell.requestFullscreen();
        if (document.fullscreenElement !== shell) throw new Error("Fullscreen request was not granted.");
      }
      setFullscreenError(false);
    } catch {
      setFullscreenError(true);
    }
  };

  return (
    <section id={playerId} ref={shellRef} className="player-shell bilibili-shell" aria-label={translate(locale, "player.bilibiliLabel", { title: lecture.title })}>
      {embedUrl ? (
        <div className="player-frame">
          <iframe
            key={reloadKey}
            className="bilibili-player"
            src={embedUrl}
            title={lecture.title}
            allow="autoplay; encrypted-media; fullscreen; picture-in-picture"
            allowFullScreen
            sandbox="allow-scripts allow-same-origin allow-forms allow-presentation allow-storage-access-by-user-activation"
            referrerPolicy="strict-origin-when-cross-origin"
            onLoad={() => setFailed(false)}
            onError={() => setFailed(true)}
          />
        </div>
      ) : null}
      <div className="player-meta">
        <span className="live-dot" />
        {failed
          ? translate(locale, "player.embedUnavailable")
          : fullscreenError
            ? translate(locale, "player.fullscreenUnavailable")
            : translate(locale, "player.bilibiliReady")}
        <span className="player-source-note">{translate(locale, "player.bilibiliNotice")}</span>
      </div>
      <div className="bilibili-controls">
        <div>
          <strong>{translate(locale, "player.bilibiliHdTitle")}</strong>
          <span aria-live="polite">{translate(locale, returnedFromLogin ? "player.bilibiliReturnDetected" : "player.bilibiliHdHint")}</span>
          <span className="bilibili-in-page-status">{translate(locale, "player.bilibiliInPageOnly")}</span>
        </div>
        <div className="bilibili-control-actions">
          <button type="button" onClick={openLogin}>{translate(locale, "player.bilibiliLogin")}</button>
          <button type="button" onClick={refreshPlayer}>{translate(locale, "player.bilibiliRefresh")}</button>
          <button type="button" onClick={() => void toggleFullscreen()}>{translate(locale, fullscreen ? "player.exitFullscreen" : "player.fullscreen")}</button>
        </div>
      </div>
    </section>
  );
}
