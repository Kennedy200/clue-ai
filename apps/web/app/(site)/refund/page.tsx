import type { Metadata } from "next";
import { Legal } from "@/components/Legal";

export const metadata: Metadata = { title: "Refund Policy", alternates: { canonical: "/refund" } };

export default function Refund() {
  return (
    <Legal title="Refund Policy" updated="6 November 2026" sections={[
      ["Subscriptions", ["You can cancel any time; the plan then ends at the close of the current billing period. If you were charged by mistake or the service did not work as described, contact us within 7 days of the charge and we will review a refund."]],
      ["Credits and top-ups", ["Credits that were used on completed actions are not refundable. Credits reserved for a job that fails are returned automatically. Unused top-up credits may be refunded within 7 days of purchase."]],
      ["Annual plans", ["If you cancel an annual plan within 7 days of the first payment and have used few credits, we will refund the payment. After that, the plan runs to the end of the year."]],
      ["How to ask", ["Use the contact page with your account email and the date of the payment."]],
      ["Self-hosted installs", ["Self-hosted installs are free, so there is nothing to refund."]],
    ]} />
  );
}
