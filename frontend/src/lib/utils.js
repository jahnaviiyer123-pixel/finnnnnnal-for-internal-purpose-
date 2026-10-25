import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

/**
 * Converts any slot string (e.g. "06:00-07:00", "17:00-18:00") into 12-hour clock format ("06:00 AM - 07:00 AM", "05:00 PM - 06:00 PM").
 */
export function formatSlot12(slotStr) {
  if (!slotStr) return "";
  const s = String(slotStr).trim();
  if (s.includes("AM") || s.includes("PM")) return s;
  if (!s.includes("-") && !s.includes("–")) return s;

  const parts = s.split(/[-–]/).map((p) => p.trim());
  if (parts.length !== 2) return s;

  const to12 = (timePart) => {
    if (!timePart.includes(":")) return timePart;
    const [hStr, mStr] = timePart.split(":");
    let h = parseInt(hStr, 10);
    const m = mStr || "00";
    if (isNaN(h)) return timePart;
    const ampm = h >= 12 ? "PM" : "AM";
    h = h % 12;
    if (h === 0) h = 12;
    const hFormatted = h < 10 ? `0${h}` : `${h}`;
    return `${hFormatted}:${m} ${ampm}`;
  };

  return `${to12(parts[0])} - ${to12(parts[1])}`;
}
