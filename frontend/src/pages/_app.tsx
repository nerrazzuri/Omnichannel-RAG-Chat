import type { AppProps } from "next/app";
import Head from "next/head";
import { useEffect, useMemo, useState } from "react";
import "../styles/globals.css";
import "../styles/beautify.css";

export default function MyApp({ Component, pageProps }: AppProps) {
  const [branding, setBranding] = useState<{
    brand_assets_uri?: string;
    csp_exceptions?: string[];
  }>({});
  const [colors, setColors] = useState<Record<string, string>>({});
  const cspContent = useMemo(() => {
    const base =
      "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline' https:; script-src 'self' https:; connect-src 'self' https:; font-src 'self' https: data:";
    const extras = (branding.csp_exceptions || []).join(" ");
    return extras ? `${base} ${extras}` : base;
  }, [branding]);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch("/api/tenant/branding");
        if (!r.ok) return;
        const b = await r.json();
        setBranding(b || {});
        if (b?.brand_assets_uri) {
          try {
            const cr = await fetch(
              `${b.brand_assets_uri.replace(/\/$/, "")}/colors.json`,
            );
            if (cr.ok) {
              const cj = await cr.json();
              setColors(cj || {});
              Object.entries(cj || {}).forEach(([k, v]) => {
                try {
                  document.documentElement.style.setProperty(
                    `--brand-${k}`,
                    String(v),
                  );
                } catch {}
              });
            }
          } catch {}
        }
        // Update favicon if provided
        if (b?.brand_assets_uri) {
          const iconHref = `${b.brand_assets_uri.replace(/\/$/, "")}/favicon.ico`;
          const link: HTMLLinkElement =
            document.querySelector("link[rel='icon']") ||
            document.createElement("link");
          link.rel = "icon";
          link.href = iconHref;
          if (!link.parentNode) document.head.appendChild(link);
        }
      } catch {}
    })();
  }, []);

  return (
    <>
      <Head>
        <meta httpEquiv="Content-Security-Policy" content={cspContent} />
        {branding?.brand_assets_uri && (
          <link
            rel="icon"
            href={`${branding.brand_assets_uri.replace(/\/$/, "")}/favicon.ico`}
          />
        )}
      </Head>
      <Component {...pageProps} />
    </>
  );
}
