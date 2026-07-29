"use client";

export default function GlobalError({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  return (
    <html lang="en">
      <body>
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center">
          <h2 className="text-lg font-semibold">Something went badly wrong</h2>
          <p className="max-w-md text-sm text-muted-foreground">
            {error.message || "The application crashed unexpectedly."}
          </p>
          <button
            onClick={() => unstable_retry()}
            className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-accent"
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
