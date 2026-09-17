export type Condition = 'used' | 'new';
export interface Phone {
  brand: string;
  model: string;
  condition: Condition;
  storage_gb?: number | null;
  ram_gb?: number | null;
  photo_count?: number | null;
  city?: string | null;
  seller_type?: 'shop' | 'private' | null;
}
export interface Prediction {
  predicted_price_azn: number;
  currency: 'AZN';
  condition: Condition;
  actual_price_azn: number | null;
  difference_pct: number | null;
  verdict: string | null;
  model_version: string;
  features?: Phone;
  listing_id?: string;
  url?: string;
}
export interface Result {
  prediction: Prediction;
  phone: Phone;
  url?: string;
}
const base = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');

export function normalizeListingUrl(input: string): string {
  let parsed: URL;
  try {
    parsed = new URL(input.trim());
  } catch {
    throw new Error(
      'Paste the full Tap.az listing link, starting with https://tap.az/.',
    );
  }
  if (
    parsed.protocol !== 'https:' ||
    parsed.hostname !== 'tap.az' ||
    parsed.port ||
    parsed.username ||
    parsed.password ||
    !/^\/elanlar\/elektronika\/telefonlar\/[0-9]{1,20}\/?$/.test(
      parsed.pathname,
    )
  ) {
    throw new Error(
      'Use a phone listing from tap.az, not a search page or another website.',
    );
  }
  // Shared links may include tracking parameters. Only the canonical listing is sent.
  return `https://tap.az${parsed.pathname.replace(/\/$/, '')}`;
}

export async function predict(
  endpoint: '/predict' | '/predict-from-url',
  body: object,
  signal: AbortSignal,
): Promise<Prediction> {
  const timeout = new AbortController();
  const timer = window.setTimeout(() => timeout.abort(), 90000);
  try {
    const response = await fetch(base + endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.any([signal, timeout.signal]),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const errors: Record<number, string> = {
        404: 'This listing is no longer available. You can still enter the phone details manually.',
        429: 'Another listing is being checked. Wait a few seconds, then try again.',
        502: 'We couldn’t read Tap.az right now. Try again later or enter the phone details manually.',
        503: 'Price checks are temporarily unavailable. Please try again shortly.',
        504: 'Tap.az took too long to respond. Try again or enter the phone details manually.',
      };
      if (response.status === 422) {
        throw new Error(
          endpoint === '/predict-from-url'
            ? 'This listing has missing or conflicting details, or isn’t a supported phone. Check its condition before entering details manually.'
            : 'Check the phone details. Brand, model, and condition are required; prices and memory must be positive numbers.',
        );
      }
      throw new Error(
        errors[response.status] ||
          'We couldn’t complete this price check. Please try again.',
      );
    }
    if (
      !data ||
      !Number.isFinite(data.predicted_price_azn) ||
      data.predicted_price_azn <= 0 ||
      !['used', 'new'].includes(data.condition) ||
      (endpoint === '/predict-from-url' && !data.features)
    ) {
      throw new Error(
        'The price check returned an incomplete result. Please try again.',
      );
    }
    return data as Prediction;
  } catch (error) {
    if (signal.aborted) throw error;
    if (timeout.signal.aborted)
      throw new Error(
        'This check is taking too long. Please try again or enter the phone details manually.',
      );
    if (error instanceof TypeError)
      throw new Error(
        'We couldn’t connect to the price checker. Please try again shortly.',
      );
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}
