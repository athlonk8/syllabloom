import { useState } from "react";
import { translate, type Locale } from "../lib/i18n";
import type { Lecture } from "../types/api";

export function BilibiliPlayer({ lecture, locale }: { lecture: Lecture; locale: Locale }) {
  const [failed, setFailed] = useState(false);
  const embedUrl = lecture.video?.embed_url;

  return (
    <section className="player-shell" aria-label={translate(locale, "player.bilibiliLabel", { title: lecture.title })}>
      {embedUrl ? (
        <div className="player-frame">
          <iframe
            className="bilibili-player"
            src={embedUrl}
            title={lecture.title}
            allow="autoplay; fullscreen"
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
    </section>
  );
}
