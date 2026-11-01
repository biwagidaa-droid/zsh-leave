const BASE_TITLE = "سامانه مرخصی زکریا شیمی";

let pageTitle = "";
let unread = 0;
let originalHref: string | null = null;

export function appBaseTitle(): string {
  return BASE_TITLE;
}

export function setPageTitle(title: string): void {
  pageTitle = title;
  applyDocumentChrome();
}

export function setUnreadBadge(count: number): void {
  unread = Math.max(0, Math.floor(count));
  applyDocumentChrome();
}

export function currentUnreadBadge(): number {
  return unread;
}

function composeTitle(): string {
  const base = pageTitle ? `${pageTitle} · ${BASE_TITLE}` : BASE_TITLE;
  return unread > 0 ? `(${unread}) ${base}` : base;
}

function badgeFavicon(count: number): string {
  const n = count > 99 ? "99+" : String(count);
  const fontSize = n.length > 2 ? 10 : 12;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
    <rect width="32" height="32" rx="8" fill="#0f4c5c"/>
    <path d="M8 22V10h4.2c2.6 0 4.2 1.4 4.2 3.6 0 1.4-.8 2.5-2 3.1 1.4.5 2.4 1.7 2.4 3.4 0 2.4-1.8 3.9-4.6 3.9H8Zm3.1-7.3h1.2c1.1 0 1.8-.6 1.8-1.5s-.7-1.4-1.8-1.4h-1.2v2.9Zm0 5.2h1.5c1.3 0 2-.6 2-1.6s-.7-1.5-2-1.5h-1.5v3.1Z" fill="#e8b86d"/>
    <circle cx="24" cy="8" r="8" fill="#c0392b"/>
    <text x="24" y="12" text-anchor="middle" font-size="${fontSize}" font-family="Tahoma,sans-serif" font-weight="700" fill="#fff">${n}</text>
  </svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

function applyFavicon(count: number): void {
  const links = document.querySelectorAll<HTMLLinkElement>('link[rel="icon"]');
  if (!links.length) return;
  const primary = links[0];
  if (originalHref == null) originalHref = primary.getAttribute("href") ?? "/favicon.svg";
  const href = count > 0 ? badgeFavicon(count) : originalHref;
  links.forEach((el) => { el.href = href; });
}

export function applyDocumentChrome(): void {
  if (typeof document === "undefined") return;
  document.title = composeTitle();
  applyFavicon(unread);
}
