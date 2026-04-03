import type { Metadata } from "next";
import type { ReactNode } from "react";

import { Providers } from "@/components/providers";

import "./globals.css";
import "./design-system.css";

export const metadata: Metadata = {
  title: "CannabIA Frontend",
  description: "Bootstrap do novo frontend em Next.js para a CannabIA.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body>
        {/* Skip navigation — acessibilidade para navegação por teclado */}
        <a className="skip-nav" href="#main-content">
          Pular para o conteúdo principal
        </a>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
