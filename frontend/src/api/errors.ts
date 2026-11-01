import type { ApiErrorBody } from "./types";

/** رویدادی که هنگام دریافت 401 از سرور (انقضای نشست) روی window ارسال می‌شود. */
export const UNAUTHORIZED_EVENT = "zsh:unauthorized";

export class ApiError extends Error {
  code: string;
  fields: Record<string, string>;
  status: number;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message_fa);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.fields = body.fields ?? {};
  }
}

export function asApiError(err: unknown): ApiError {
  if (err instanceof ApiError) return err;
  return new ApiError(0, { code: "client", message_fa: err instanceof Error ? err.message : "خطای ناشناخته" });
}

/** پیام قابل‌نمایش برای هر خطا (فارسی). */
export function errorMessage(err: unknown): string {
  return asApiError(err).message;
}
