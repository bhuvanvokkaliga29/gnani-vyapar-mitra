import type { Metadata } from 'next';
import Script from 'next/script';
import './globals.css';
import { MerchantProvider } from '@/lib/MerchantContext';
import { AppShell } from '@/components/layout/AppShell';

export const metadata: Metadata = {
  title: 'Vyapar Mitra Dashboard | Merchant AI Control',
  description: 'Autonomous merchant growth and real-time operations engine for Vyapar Mitra.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-white text-[#061b31]">
        <MerchantProvider>
          <AppShell>{children}</AppShell>
        </MerchantProvider>
        <Script src="https://checkout.razorpay.com/v1/checkout.js" strategy="lazyOnload" />
      </body>
    </html>
  );
}
