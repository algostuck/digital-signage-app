/**
 * IANA time zones for `Select` controls, with the estate's common zones
 * first. Uses the browser's list when available (Intl.supportedValuesOf),
 * with a short fallback for older engines.
 */
const COMMON = ["Asia/Kolkata", "Asia/Dubai", "Asia/Singapore", "Asia/Riyadh", "Europe/London", "America/New_York", "UTC"];
const FALLBACK = [...COMMON, "Asia/Karachi", "Asia/Dhaka", "Asia/Colombo", "Asia/Kathmandu", "Australia/Sydney", "Europe/Berlin"];

export function timeZoneNames(): string[] {
  const intl = Intl as unknown as { supportedValuesOf?: (key: string) => string[] };
  const zones = intl.supportedValuesOf?.("timeZone") ?? FALLBACK;
  return [...COMMON, ...zones.filter((z) => !COMMON.includes(z))];
}

export function timeZoneOptions(): { value: string; label: string }[] {
  return timeZoneNames().map((z) => ({ value: z, label: z.replace(/_/g, " ") }));
}

/** Locales the product ships copy for; extend when translations land. */
export const LOCALE_OPTIONS = [
  { value: "en-IN", label: "English (India)" },
  { value: "en-GB", label: "English (UK)" },
  { value: "en-US", label: "English (US)" },
  { value: "hi-IN", label: "Hindi (India)" },
];
