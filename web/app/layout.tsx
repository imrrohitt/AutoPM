import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Toaster } from "sonner";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "AutoPM",
  description: "AI-native project management",
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
