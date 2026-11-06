import type { Metadata } from "next";
import { Legal } from "@/components/Legal";

export const metadata: Metadata = { title: "Terms of Service", alternates: { canonical: "/terms" } };

export default function Terms() {
  return (
    <Legal title="Terms of Service" updated="6 November 2026" sections={[
      ["Using Clue AI", ["By creating an account you agree to these terms. You must be old enough to form a binding contract in your country, and you are responsible for activity on your account."]],
      ["Your videos", ["You own the videos you create. You promise that you have the rights to everything you upload, and that your use of music, images, voices and footage follows their licences."]],
      ["Acceptable use", ["Do not use Clue AI to break the law, infringe others' rights, harass people, or create misleading deepfakes or impersonations of real people. Do not attempt to disrupt the service or bypass limits. We may suspend accounts that break these rules."]],
      ["AI output", ["AI-generated text and media can be wrong. You are responsible for checking facts and for what you publish."]],
      ["Plans, credits and billing", ["Paid plans renew until cancelled. Cancellation takes effect at the end of the billing cycle. You keep and can download videos you already made. Credits are used for AI and render actions and may reset monthly according to your plan."]],
      ["Copyright complaints (DMCA)", ["If you believe content on the service infringes your copyright, contact us with the details of the work, where the content is, and your contact information. We will review and remove infringing content where appropriate."]],
      ["Disclaimer and liability", ["The service is provided as is, without warranties. To the extent allowed by law, we are not liable for indirect or consequential losses. The open-source software is separately licensed under the MIT licence."]],
      ["Changes", ["We may update these terms and will post the new date here. Continuing to use the service means you accept the update."]],
    ]} />
  );
}
