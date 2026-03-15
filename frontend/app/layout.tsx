import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NEURON — Brain-Computer Interface",
  description: "EEG brainwave data to creative artifacts via Claude",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#0a0a0f] text-slate-200 antialiased">
        {children}
      </body>
    </html>
  );
}
