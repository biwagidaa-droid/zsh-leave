export function resolveDemoMode(isDevelopment: boolean, configuredMode?: string): boolean {
  if (!isDevelopment && configuredMode === "true") {
    throw new Error("حالت Demo در build عملیاتی مجاز نیست");
  }
  return isDevelopment && configuredMode !== "false";
}
