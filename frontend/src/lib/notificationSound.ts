import type { SoundId } from "./notificationPrefs";

let unlocked = false;
let ctx: AudioContext | null = null;

export function isAudioUnlocked(): boolean {
  return unlocked;
}

export function unlockNotificationAudio(): void {
  if (unlocked) return;
  try {
    const AC = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AC) return;
    ctx = ctx ?? new AC();
    if (ctx.state === "suspended") void ctx.resume();
    unlocked = true;
  } catch {
    unlocked = false;
  }
}

function tone(now: number, freq: number, start: number, dur: number, volume: number, type: OscillatorType) {
  if (!ctx) return;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, now + start);
  gain.gain.setValueAtTime(0.0001, now + start);
  gain.gain.exponentialRampToValueAtTime(Math.max(0.001, volume), now + start + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.0001, now + start + dur);
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start(now + start);
  osc.stop(now + start + dur + 0.02);
}

export function playNotificationSound(soundId: SoundId, volume: number): void {
  if (!unlocked || volume <= 0) return;
  try {
    const AC = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AC) return;
    ctx = ctx ?? new AC();
    if (ctx.state === "suspended") void ctx.resume();
    const now = ctx.currentTime;
    const v = Math.min(1, Math.max(0, volume)) * 0.18;
    if (soundId === "soft") {
      tone(now, 520, 0, 0.18, v * 0.7, "sine");
      tone(now, 660, 0.12, 0.22, v * 0.5, "sine");
    } else if (soundId === "alert") {
      tone(now, 880, 0, 0.12, v, "square");
      tone(now, 660, 0.14, 0.12, v, "square");
      tone(now, 880, 0.28, 0.16, v, "square");
    } else {
      tone(now, 784, 0, 0.12, v, "triangle");
      tone(now, 988, 0.13, 0.16, v, "triangle");
      tone(now, 1175, 0.28, 0.22, v * 0.8, "sine");
    }
  } catch {
    /* Autoplay یا عدم پشتیبانی */
  }
}
