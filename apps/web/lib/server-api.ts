/** Server-side calls to the API with safe fallbacks, so marketing pages render even if the API is down. */
import type { PlanRow } from "@/components/PricingTable";

const base = () => `http://127.0.0.1:${process.env.API_PORT || "8000"}/api`;

export const FALLBACK_PLANS: PlanRow[] = [
  { id: "free", name: "Free", price_ngn_month: 0, price_usd_month: 0, monthly_credits: 15, features: {} },
  { id: "starter", name: "Starter", price_ngn_month: 9900, price_usd_month: 700, monthly_credits: 200, features: {} },
  { id: "creator", name: "Creator", price_ngn_month: 19900, price_usd_month: 1400, monthly_credits: 500, features: {} },
  { id: "business", name: "Business", price_ngn_month: 49900, price_usd_month: 3500, monthly_credits: 1200, features: {} },
];

async function get<T>(path: string, fallback: T): Promise<T> {
  try {
    const r = await fetch(base() + path, { next: { revalidate: 60 } });
    return r.ok ? ((await r.json()) as T) : fallback;
  } catch {
    return fallback;
  }
}

export const getPlans = () => get<PlanRow[]>("/plans", FALLBACK_PLANS);
export const getReviews = () => get<{ name: string; rating: number; body: string }[]>("/reviews", []);
