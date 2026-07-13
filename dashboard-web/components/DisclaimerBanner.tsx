export default function DisclaimerBanner({ text }: { text: string }) {
  return (
    <div className="rounded-md border border-status-warning/40 bg-status-warning/10 px-4 py-3 text-sm text-text-secondary">
      <span className="font-semibold text-foreground">Not financial advice.</span>{" "}
      {text}
    </div>
  );
}
