// Gọi backend FastAPI. URL lấy từ EXPO_PUBLIC_API_URL (không phải bí mật — chỉ là địa chỉ API).

const DEFAULT_API_ORIGIN = 'http://localhost:8000';
export const API_BASE = `${(process.env.EXPO_PUBLIC_API_URL ?? DEFAULT_API_ORIGIN).replace(/\/$/, '')}/api/v1`;

const NETWORK_ERROR = 'Không kết nối được máy chủ — kiểm tra mạng rồi thử lại';
const TIMEOUT_ERROR = 'Máy chủ phản hồi quá lâu — thử lại sau';
const GENERIC_ERROR = 'Có lỗi xảy ra, thử lại sau';
const NO_CONTENT = 204;
// Không tới được server (mất mạng, timeout): không có response nào, nên không có mã HTTP.
export const NO_RESPONSE = 0;
const AUTH_REJECTED = [401, 403];

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// Server trả lời rõ "phiên không hợp lệ" (401/403 trong response). Mất mạng / timeout KHÔNG tính — phiên có thể vẫn tốt.
export const isAuthRejection = (error: unknown): boolean =>
  error instanceof ApiError && AUTH_REJECTED.includes(error.status);

type ValidationItem = { msg?: string };
type ErrorBody = { detail?: string | ValidationItem[] };

export type ApiOptions = {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  body?: unknown;
  token?: string | null;
  timeoutMs?: number; // hết giờ → ApiError(NO_RESPONSE), như mất mạng
};

export async function apiRequest<T>(path: string, { method = 'GET', body, token, timeoutMs }: ApiOptions = {}): Promise<T> {
  let response: Response;
  const controller = new AbortController();
  const timer = timeoutMs === undefined ? undefined : setTimeout(() => controller.abort(), timeoutMs);
  try {
    response = await fetch(API_BASE + path, {
      method,
      signal: controller.signal,
      credentials: 'include', // web: gửi/nhận cookie refresh httpOnly; native bỏ qua
      headers: {
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (error) {
    console.warn(`Gọi API ${method} ${path} thất bại`, error);
    throw new ApiError(NO_RESPONSE, controller.signal.aborted ? TIMEOUT_ERROR : NETWORK_ERROR);
  } finally {
    clearTimeout(timer);
  }
  if (response.status === NO_CONTENT) return undefined as T;
  const data = (await response.json().catch(() => null)) as T | ErrorBody | null;
  if (!response.ok) throw new ApiError(response.status, errorMessage(data as ErrorBody | null));
  return data as T;
}

// Backend đã viết sẵn câu tiếng Việt trong "detail"; lỗi validation (422) là mảng → lấy câu đầu.
function errorMessage(data: ErrorBody | null): string {
  if (typeof data?.detail === 'string') return data.detail;
  if (Array.isArray(data?.detail) && data.detail[0]?.msg) return data.detail[0].msg;
  return GENERIC_ERROR;
}
