/** "Save data": shrink a video to 720p in the browser before uploading (MediaRecorder; runs in real time, no extra download). */

export function canShrink(): boolean {
  return typeof window !== "undefined" && typeof MediaRecorder !== "undefined" && "captureStream" in HTMLCanvasElement.prototype && typeof AudioContext !== "undefined";
}

/** Returns the original file when it is already 720p or smaller, or when shrinking is not possible. */
export async function shrinkVideo(file: File, onProgress: (pct: number) => void): Promise<File> {
  if (!canShrink() || !file.type.startsWith("video/")) return file;
  const url = URL.createObjectURL(file);
  const v = document.createElement("video");
  v.src = url;
  v.playsInline = true;
  v.preload = "auto";
  try {
    await new Promise<void>((res, rej) => {
      v.onloadedmetadata = () => res();
      v.onerror = () => rej(new Error("This browser cannot read that video, so it will be uploaded as it is."));
    });
    const { videoWidth: w, videoHeight: h, duration } = v;
    if (!w || !h || Math.min(w, h) <= 720 || !isFinite(duration)) return file;
    const srcBitrate = (file.size * 8) / duration;
    if (srcBitrate < 1_500_000) return file; // already small: re-encoding in real time would cost minutes and save nothing
    const s = 720 / Math.min(w, h);
    const cw = Math.round((w * s) / 2) * 2, ch = Math.round((h * s) / 2) * 2;
    const canvas = document.createElement("canvas");
    canvas.width = cw;
    canvas.height = ch;
    const ctx = canvas.getContext("2d");
    if (!ctx) return file;
    const stream = canvas.captureStream(30);
    const ac = new AudioContext();
    let audioOk = false;
    try {
      const dest = ac.createMediaStreamDestination();
      ac.createMediaElementSource(v).connect(dest); // not connected to the speakers, so nothing plays aloud
      dest.stream.getAudioTracks().forEach((t) => { stream.addTrack(t); audioOk = true; });
      await ac.resume();
    } catch { /* no audio track in this file */ }
    const mime = ["video/webm;codecs=vp9,opus", "video/webm;codecs=vp8,opus", "video/webm"].find((m) => MediaRecorder.isTypeSupported(m));
    if (!mime) return file;
    const rec = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: Math.round(Math.min(2_500_000, Math.max(900_000, srcBitrate * 0.5))), audioBitsPerSecond: audioOk ? 96_000 : undefined });
    const chunks: Blob[] = [];
    rec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
    const stopped = new Promise<void>((res) => { rec.onstop = () => res(); });
    rec.start(1000);
    let raf = 0;
    const draw = () => {
      ctx.drawImage(v, 0, 0, cw, ch);
      onProgress(Math.min(99, Math.round((v.currentTime / duration) * 100)));
      raf = requestAnimationFrame(draw);
    };
    v.onended = () => rec.stop();
    await v.play();
    draw();
    await stopped;
    cancelAnimationFrame(raf);
    ac.close().catch(() => {});
    const out = new File([new Blob(chunks, { type: "video/webm" })], file.name.replace(/\.[^.]+$/, "") + "-720p.webm", { type: "video/webm" });
    onProgress(100);
    return out.size > 0 && out.size < file.size ? out : file; // never make a file bigger
  } finally {
    URL.revokeObjectURL(url);
  }
}
