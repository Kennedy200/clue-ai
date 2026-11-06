import type { Metadata } from "next";
import { Legal } from "@/components/Legal";

export const metadata: Metadata = { title: "Privacy Policy", alternates: { canonical: "/privacy" } };

export default function Privacy() {
  return (
    <Legal title="Privacy Policy" updated="6 November 2026" sections={[
      ["What we collect", ["Account details you give us (email, name), the videos, scripts and files you upload or create, and basic usage records such as credits used and job status.", "We do not sell your personal data."]],
      ["How we use it", ["To run your account, create and store your videos, bill you, prevent abuse, and improve the service. Text you ask the AI to work on (for example a script or transcript) is sent to the AI model provider you or the operator configured, only to produce the result you asked for."]],
      ["Self-hosted installs", ["If you run Clue AI yourself, your files and database stay on your own machine. The person running the installation is responsible for the data on it."]],
      ["Cookies", ["We use a session cookie to keep you signed in and a security token to protect your requests. We do not use advertising cookies."]],
      ["Your choices", ["You can export your data and delete your account from Settings. Deleting your account removes your profile and credit history. You can also contact us to ask about your data."]],
      ["Retention and security", ["We keep data while your account is active. Passwords are stored as one-way hashes and API keys are encrypted at rest. No system is perfectly secure, so please use a strong, unique password."]],
      ["Contact", ["Questions about privacy? Use the contact page."]],
    ]} />
  );
}
