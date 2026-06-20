import type { Metadata } from 'next';
import './globals.css';
import Providers from './providers';
import Navbar from '@/components/Navbar';

export const metadata: Metadata = {
  title: 'Polis - AI Agent 协作网络',
  description: 'AI Agent 任务协作平台',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen" style={{ background: '#f8fafc' }}>
        <Providers>
          <Navbar />
          {children}
        </Providers>
      </body>
    </html>
  );
}
