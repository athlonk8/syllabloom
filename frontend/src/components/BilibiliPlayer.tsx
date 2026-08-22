import { useEffect, useRef, useState } from "react";
import { translate, type Locale } from "../lib/i18n";
import type { Lecture } from "../types/api";

export function BilibiliPlayer({ lecture, locale }: { lecture: Lecture; locale: Locale }) {
  const [failed, setFailed] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [fullscreen, setFullscreen] = useState(false);
  const [loginStarted, setLoginStarted] = useState(false);
  const shellRef = useRef<HTMLElement>(null);
  const embedUrl = lecture.video?.embed_url;
  const sourceUrl = lecture.source_url || `https://www.bilibili.com/video/${lecture.video?.external_id || ""}/`;

  useEffect(() => {
    const updateFullscreen = () => setFullscreen(document.fullscreenElement === shellRef.current);
    document.addEventListener("fullscreenchange", updateFullscreen);
    return () => document.removeEventListener("fullscreenchange", updateFullscreen);
  }, []);

  const openLogin = () => {
    const loginUrl = `https://passport.bilibili.com/login?gourl=${encodeURIComponent(sourceUrl)}`;
    // The account is authenticated directly on Bilibili. Syllabloom never
    // reads, stores, or proxies the login cookie.
    window.open(loginUrl, "_blank", "noopener,noreferrer");
    setLoginStarted(true);
  };

  const refreshPlayer = () => {
    setFailed(false);
    setReloadKey((key) => key + 1);
  };

  const toggleFullscreen = async () => {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
      } else {
        await shellRef.current?.requestFullscreen();
      }
    } catch {
      setFailed(true);
    }
  };

  return (
    <section ref={shellRef} className="player-shell bilibili-shell" aria-label={translate(locale, "player.bilibiliLabel", { title: lecture.title })}>
      {embedUrl ? (
        <div className="player-frame">
          <iframe
            key={reloadKey}
            className="bilibili-player"
            src={embedUrl}
            title={lecture.title}
            allow="autoplay; fullscreen; picture-in-picture"
            allowFullScreen
            referrerPolicy="strict-origin-when-cross-origin"
            onError={() => setFailed(true)}
          />
        </div>
      ) : null}
      <div className="player-meta">
        <span className="live-dot" />
        {failed ? translate(locale, "player.embedUnavailable") : translate(locale, "player.bilibiliReady")}
        <span className="player-source-note">{translate(locale, "player.bilibiliNotice")}</span>
      </div>
      <div className="bilibili-controls">
        <div>
          <strong>{translate(locale, "player.bilibiliHdTitle")}</strong>
          <span>{translate(locale, loginStarted ? "player.bilibiliLoginRefreshHint" : "player.bilibiliHdHint")}</span>
        </div>
        <div className="bilibili-control-actions">
          <button type="button" onClick={openLogin}>{translate(locale, "player.bilibiliLogin")}</button>
          <button type="button" onClick={refreshPlayer}>{translate(locale, "player.bilibiliRefresh")}</button>
          <button type="button" onClick={() => window.open(sourceUrl, "_blank", "noopener,noreferrer")}>{translate(locale, "player.bilibiliOpen")}</button>
          <button type="button" onClick={() => void toggleFullscreen()}>{translate(locale, fullscreen ? "player.exitFullscreen" : "player.fullscreen")}</button>
        </div>
      </div>
    </section>
  );
}
