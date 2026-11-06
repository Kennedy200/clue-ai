import type { Metadata } from "next";
import { PricingTable } from "@/components/PricingTable";
import { Faq, JsonLd, faqLd } from "@/components/Site";
import { FAQ } from "@/lib/faq";
import { getPlans } from "@/lib/server-api";

export const metadata: Metadata = {
  title: "Pricing",
  description: "Simple plans in naira or dollars. Free to start, 50% off when billed yearly, and free forever when self-hosted.",
  alternates: { canonical: "/pricing" },
};

export default async function Pricing() {
  const plans = await getPlans();
  const faq = FAQ.filter((f) => /cancel|credits|refund|commercial|AI/i.test(f.q));
  return (
    <div className="mx-auto max-w-6xl px-5 py-14">
      <JsonLd data={faqLd(faq)} />
      <h1 className="text-center text-4xl font-bold sm:text-5xl">Pricing that stays out of your way</h1>
      <p className="mx-auto mt-4 max-w-2xl text-center text-muted">Start free. Annual billing is 50% off. Cancel any time and keep the videos you made.</p>
      <div className="mt-10"><PricingTable plans={plans} /></div>
      <div className="mx-auto mt-16 max-w-3xl"><h2 className="mb-4 text-2xl font-bold">Pricing questions</h2><Faq items={faq} /></div>
    </div>
  );
}
