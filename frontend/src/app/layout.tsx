import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VigilOps | Industrial Intelligence Platform",
  description: "Transform engineering documents into an evolving knowledge graph. Powered by GraphRAG.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col">
        {children}
      </body>
    </html>
  );
}
