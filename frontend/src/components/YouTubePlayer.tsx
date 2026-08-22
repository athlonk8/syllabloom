import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { Lecture } from "../types/api";

declare global {
  interface Window {
    onYouTubeIframeAPIReady?: () => void;
    YT?: {
      Player: new (element: HTMLElement, config: unknown) => YouTubePlayerInstance;
      PlayerState?: { PLAYING: number; PAUSED: number; ENDED: number };
      loaded?: number;
    };
  }
}

interface YouTubePlayerInstance {
  getCurrentTime(): number;
  getDuration(): number;
  getPlaybackRate(): number;
  seekTo(seconds: number, allowSeekAhead: boolean): void;
  destroy(): void;
}

interface PlayerEvent {
  data: number;
  target: YouTubePlayerInstance;
}

function loadYouTubeIframeApi(): Promise<void> {
  if (window.YT?.Player) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const current = document.querySelector<HTMLScriptElement>('script[data-youtube-iframe-api="true"]');
    if (current) {
      const timer = window.setInterval(() => {
        if (window.YT?.Player) {
          window.clearInterval(timer);
          resolve();
        }
      }, 50);
      window.setTimeout(() => {
        window.clearInterval(timer);
        reject(new Error("YouTube IFrame API did not load."));
      }, 10_000);
      return;
    }
    const script = document.createElement("script");
    script.src = "https://www.youtube.com/iframe_api";
    script.async = true;
    script.dataset.youtubeIframeApi = "true";
    const previousReady = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      previousReady?.();
      resolve();
    };
    script.onerror = () => reject(new Error("Unable to load the YouTube IFrame API."));
    document.head.appendChild(script);
  });
}

export function YouTubePlayer({ lecture, onProgress }: { lecture: Lecture; onProgress: () => void }) {
  const mountRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<YouTubePlayerInstance | null>(null);
  const sessionIdRef = useRef<number | null>(null);
  const lastPositionRef = useRef(0);
  const playingRef = useRef(false);
  const reportingRef = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("Preparing player");
  const videoId = lecture.video?.id;

  const reportInterval = useCallback(
    async (force = false) => {
      const player = playerRef.current;
      if (!player || (!playingRef.current && !force) || reportingRef.current || !videoId) return;
      const current = Number(player.getCurrentTime());
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
            video_id: videoId,
            start_seconds: previous,
            end_seconds: current,
            playback_rate: Number(player.getPlaybackRate()) || 1,
            session_id: sessionIdRef.current,
            duration_seconds: Number(player.getDuration()) || undefined,
          }),
          keepalive: force,
        });
        sessionIdRef.current = result.session_id;
        setStatus(result.completed ? "Lecture complete" : "Tracking actual coverage");
        onProgress();
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Unable to save watch progress.");
      } finally {
        reportingRef.current = false;
      }
    },
    [videoId, onProgress],
  );

  useEffect(() => {
    const youtubeVideo = lecture.video;
    if (!youtubeVideo) return;
    let destroyed = false;
    let interval: number | undefined;
    const setup = async () => {
      try {
        await loadYouTubeIframeApi();
        if (destroyed || !mountRef.current || !window.YT?.Player) return;
        playerRef.current = new window.YT.Player(mountRef.current, {
          videoId: youtubeVideo.external_id,
          playerVars: { autoplay: 0, rel: 0, modestbranding: 1, origin: window.location.origin },
          events: {
            onReady: async (event: { target: YouTubePlayerInstance }) => {
              try {
                const resume = await api<{ resume_position_seconds: number }>(`/lectures/${lecture.id}/resume`);
                if (resume.resume_position_seconds > 2) event.target.seekTo(resume.resume_position_seconds, true);
                lastPositionRef.current = resume.resume_position_seconds;
                setStatus(resume.resume_position_seconds > 2 ? "Resumed from your last position" : "Ready to learn");
              } catch {
                lastPositionRef.current = Number(event.target.getCurrentTime()) || 0;
                setStatus("Ready to learn");
              }
            },
            onStateChange: (event: PlayerEvent) => {
              const playing = window.YT?.PlayerState?.PLAYING ?? 1;
              const ended = window.YT?.PlayerState?.ENDED ?? 0;
              const paused = window.YT?.PlayerState?.PAUSED ?? 2;
              if (event.data === playing) {
                playingRef.current = true;
                lastPositionRef.current = Number(event.target.getCurrentTime()) || 0;
                interval = window.setInterval(() => void reportInterval(), 7_000);
              }
              if (event.data === paused || event.data === ended) {
                void reportInterval(true);
                playingRef.current = false;
                if (interval) window.clearInterval(interval);
              }
            },
            onError: () => {
              setError("This video cannot be embedded or is currently unavailable. Its official source link is retained below.");
              setStatus("Embed unavailable");
            },
          },
        });
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Unable to start the YouTube player.");
      }
    };
    void setup();
    const unload = () => void reportInterval(true);
    window.addEventListener("beforeunload", unload);
    return () => {
      destroyed = true;
      window.removeEventListener("beforeunload", unload);
      if (interval) window.clearInterval(interval);
      void reportInterval(true);
      if (sessionIdRef.current) void api(`/watch/sessions/${sessionIdRef.current}/finish`, { method: "POST" });
      playerRef.current?.destroy();
      playerRef.current = null;
      playingRef.current = false;
      sessionIdRef.current = null;
    };
  }, [lecture.id, lecture.video, reportInterval]);

  return (
    <section className="player-shell" aria-label={`YouTube player: ${lecture.title}`}>
      <div className="player-frame" ref={mountRef} />
      <div className="player-meta">
        <span className="live-dot" /> {status}
        {error && <span className="player-error">{error}</span>}
      </div>
    </section>
  );
}
