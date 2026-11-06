import Link from "next/link";
import { Logo } from "@/components/Logo";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center px-5 text-center">
      <Logo />
      <h1 className="mt-8 text-5xl font-bold">404</h1>
      <p className="mt-2 text-muted">We looked everywhere and found no clue. That page does not exist.</p>
      <Link href="/" className="btn btn-primary mt-6">Back to home</Link>
    </main>
  );
}
