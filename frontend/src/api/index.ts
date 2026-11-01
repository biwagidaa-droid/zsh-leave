import type { Api } from "./contract";
import { demoApi } from "./demo";
import { httpApi } from "./http";

/** پیش‌فرض: حالت نمایشی تا API واقعی پیاده‌سازی شود. با VITE_DEMO_MODE=false به Backend وصل می‌شود. */
export const DEMO_MODE = import.meta.env.VITE_DEMO_MODE !== "false";

export const api: Api = DEMO_MODE ? demoApi : httpApi;
