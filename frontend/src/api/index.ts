import type { Api } from "./contract";
import { demoApi } from "./demo";
import { httpApi } from "./http";
import { resolveDemoMode } from "./mode";

/** داده نمایشی فقط در توسعه فعال است؛ build عملیاتی همیشه باید به API متصل شود. */
export const DEMO_MODE = resolveDemoMode(import.meta.env.DEV, import.meta.env.VITE_DEMO_MODE);

export const api: Api = DEMO_MODE ? demoApi : httpApi;
