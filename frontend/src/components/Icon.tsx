import type { ReactNode, SVGProps } from "react";

export type IconName =
  | "home" | "users" | "tactics" | "calendar" | "trophy" | "search"
  | "transfer" | "shield" | "wallet" | "inbox" | "staff" | "training"
  | "medical" | "arrow" | "chevron" | "clock" | "stadium" | "target"
  | "heart" | "smile" | "trending" | "check" | "alert" | "mail"
  | "bell" | "football" | "close" | "external" | "news" | "sparkles";

const paths: Record<IconName, ReactNode> = {
  home: <><path d="m3 10 9-7 9 7v11H3z" /><path d="M9 21v-8h6v8" /></>,
  users: <><circle cx="9" cy="8" r="3" /><path d="M3 21v-2a6 6 0 0 1 12 0v2M17 4a3 3 0 0 1 0 6M17 15a5 5 0 0 1 4 5v1" /></>,
  tactics: <><circle cx="12" cy="12" r="9" /><path d="m7 7 3 3 7-3-2 6 3 4-6-1-5 2 1-7z" /></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M7 2v6M17 2v6M3 10h18M8 14h3M8 17h3M14 14h2" /></>,
  trophy: <><path d="M7 3h10v8a5 5 0 0 1-10 0V3ZM7 5H3v3a4 4 0 0 0 4 4M17 5h4v3a4 4 0 0 1-4 4M12 16v5M8 21h8" /></>,
  search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></>,
  transfer: <><path d="M4 8h16l-4-4M20 16H4l4 4M20 8H4M4 16h16" /></>,
  shield: <path d="M12 2 3 6v6c0 5.5 3.7 8.1 9 10 5.3-1.9 9-4.5 9-10V6z" />,
  wallet: <><rect x="3" y="6" width="18" height="15" rx="2" /><path d="M3 10h18M6 6V3h12v3M16 15h2" /></>,
  inbox: <><path d="M3 4h18v16H3zM3 14h5l2 3h4l2-3h5" /></>,
  staff: <><circle cx="12" cy="7" r="4" /><path d="M4 21c0-5 3-8 8-8s8 3 8 8M19 5l2-1M3 5 5 4" /></>,
  training: <><path d="m7 21 2-8 3-3 3 3 2 8M9 13l-4 3M15 13l4 3M12 10V5M9 4h6" /></>,
  medical: <><rect x="3" y="3" width="18" height="18" rx="3" /><path d="M12 7v10M7 12h10" /></>,
  arrow: <><path d="M4 12h16m-6-6 6 6-6 6" /></>,
  chevron: <path d="m9 5 7 7-7 7" />,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v6l4 2" /></>,
  stadium: <><rect x="3" y="7" width="18" height="12" rx="3" /><path d="M3 11c5 5 13 5 18 0M6 3v4M18 3v4M7 16h10" /></>,
  target: <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1" /></>,
  heart: <path d="M20.5 9c0 5-8.5 11-8.5 11S3.5 14 3.5 9a4.5 4.5 0 0 1 8.5-2 4.5 4.5 0 0 1 8.5 2Z" />,
  smile: <><circle cx="12" cy="12" r="9" /><path d="M8 14c1 2 3 3 4 3s3-1 4-3M8 10h.01M16 10h.01" /></>,
  trending: <><path d="M3 17 10 10l4 4 7-8M15 6h6v6" /></>,
  check: <path d="m4 12 5 5L20 6" />,
  alert: <><path d="m12 3 9.5 17h-19z" /><path d="M12 9v5M12 17h.01" /></>,
  mail: <><rect x="2.5" y="5" width="19" height="14" rx="2" /><path d="m3 7 9 7 9-7" /></>,
  bell: <><path d="M6 10a6 6 0 0 1 12 0v5l2 3H4l2-3zM10 21h4" /></>,
  football: <><circle cx="12" cy="12" r="9" /><path d="m12 7 4 3-1 5h-6l-1-5zM12 7V3M16 10l4.5-1M15 15l3 5M9 15l-3 5M8 10 3.5 9" /></>,
  close: <path d="M5 5 19 19M19 5 5 19" />,
  external: <><path d="M12 4h8v8M20 4 10 14M20 14v6H4V4h6" /></>,
  news: <><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M7 7h10M7 11h10M7 15h5" /></>,
  sparkles: <><path d="M12 2 14.5 9.5 22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5z" /></>,
};

interface Props extends SVGProps<SVGSVGElement> {
  name: IconName;
  size?: number;
}

export function Icon({ name, size = 18, className = "", ...props }: Props) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      {...props}
    >
      {paths[name]}
    </svg>
  );
}
