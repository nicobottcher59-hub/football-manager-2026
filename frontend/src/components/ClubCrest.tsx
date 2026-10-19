import { useId, type CSSProperties } from "react";

type Variant = "northbridge" | "redhaven";

export function ClubCrest({ variant, size = 64, className = "" }: { variant: Variant; size?: number; className?: string }) {
  const uid = useId().replace(/:/g, "");
  const red = variant === "redhaven";
  return (
    <svg
      width={size}
      height={size * 1.15}
      viewBox="0 0 90 104"
      className={className}
      role="img"
      aria-label={red ? "Fictional Redhaven FC crest" : "Fictional Northbridge FC crest"}
    >
      <defs>
        <linearGradient id={`${uid}-fill`} x1="0" y1="0" x2="1" y2="1">
          <stop stopColor={red ? "#fe536c" : "#edf7ff"} />
          <stop offset="1" stopColor={red ? "#bc1735" : "#9eaec0"} />
        </linearGradient>
      </defs>
      <path d="M45 2 82 14v37c0 26-15 40-37 51C23 91 8 77 8 51V14L45 2Z" fill="#06111f" stroke="white" strokeWidth="3" />
      <path d="M45 8 76 18v33c0 20-11 34-31 45C25 85 14 71 14 51V18L45 8Z" fill={`url(#${uid}-fill)`} />
      {red ? (
        <><path d="M45 20 51.5 36h17L55 46.5l5.5 17.5L45 54 29.5 64 35 46.5 21.5 36h17Z" fill="white" stroke="white" strokeWidth="2" /><path d="M32 74h26" stroke="#fee4ed" strokeWidth="3" strokeLinecap="round" /></>
      ) : (
        <><path d="M19 22h11v59l-11-10V22ZM36 19h18v67l-9 6-9-6V19ZM60 22h11v49L60 81V22Z" fill="#09141f" /><path d="M36 19h18v67l-9 6-9-6V19Z" fill="#fafcff" /><path d="M37 22h16v6H37z" fill="#09141f" /></>
      )}
    </svg>
  );
}

export function SmallCrest({ name, color }: { name: string; color: string }) {
  if (name === "Northbridge FC") return <ClubCrest variant="northbridge" size={22} />;
  return (
    <span className="small-crest" style={{ "--crest-color": color } as CSSProperties} aria-hidden="true">
      {name.charAt(0).toUpperCase()}
    </span>
  );
}
