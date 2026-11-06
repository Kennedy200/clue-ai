import Link from "next/link";
import { Logo } from "./Logo";

export function AuthShell({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center px-5 py-10">
      <Link href="/" className="mb-8 self-start" aria-label="Clue AI home">
        <Logo />
      </Link>
      <div className="card p-6">
        <h1 className="text-2xl font-bold">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
        <div className="mt-5">{children}</div>
      </div>
    </main>
  );
}

export function Field({ label, ...p }: { label: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="mb-3 block text-sm font-medium">
      {label}
      <input className="input mt-1" {...p} />
    </label>
  );
}

export function FormError({ msg }: { msg: string }) {
  return msg ? (
    <p role="alert" className="mb-3 rounded-xl bg-coral/10 px-3 py-2 text-sm text-coral">
      {msg}
    </p>
  ) : null;
}
