export function formatSeconds(seconds: number, locale: "en" | "zh" = "en"): string {
  const safe = Math.max(0, Math.round(seconds));
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const secs = safe % 60;

  if (locale === "zh") {
    if (hours) return String(hours) + " 小时 " + String(minutes) + " 分钟";
    if (minutes) return String(minutes) + " 分 " + String(secs) + " 秒";
    return String(secs) + " 秒";
  }

  if (hours) return String(hours) + "h " + String(minutes) + "m";
  if (minutes) return String(minutes) + "m " + String(secs) + "s";
  return String(secs) + "s";
}

export function formatPercent(fraction: number): string {
  return String(Math.round(Math.max(0, Math.min(1, fraction)) * 100)) + "%";
}
