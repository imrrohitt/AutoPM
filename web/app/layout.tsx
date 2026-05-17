import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { Toaster } from "sonner";
import { BRAND } from "@/lib/brand";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000"),
  title: {
    default: BRAND.name,
    template: `%s | ${BRAND.name}`,
  },
  description: BRAND.tagline,
  applicationName: BRAND.name,
  authors: [{ name: BRAND.name }],
  keywords: ["AutoPM", "AI", "project management", "agent", "PM"],
  icons: {
    icon: [
      { url: BRAND.logo, type: "image/png" },
    ],
    apple: [{ url: BRAND.logo, type: "image/png" }],
    shortcut: BRAND.logo,
  },
  openGraph: {
    type: "website",
    siteName: BRAND.name,
    title: BRAND.name,
    description: BRAND.tagline,
    images: [
      {
        url: BRAND.logo,
        width: 476,
        height: 524,
        alt: `${BRAND.name} logo`,
      },
    ],
  },
  twitter: {
    card: "summary",
    title: BRAND.name,
    description: BRAND.tagline,
    images: [BRAND.logo],
  },
  manifest: "/site.webmanifest",
};

export const viewport: Viewport = {
  themeColor: BRAND.colors.teal,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="font-sans">
        {children}
        <Toaster
          theme="light"
          richColors
          position="top-right"
          closeButton
          toastOptions={{
            classNames: {
              toast:
                "rounded-lg border border-border bg-card text-card-foreground shadow-lg",
              title: "text-sm font-medium",
              description: "text-sm text-muted-foreground",
            },
          }}
        />
      </body>
    </html>
  );
}
