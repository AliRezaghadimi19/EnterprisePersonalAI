import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'سامانه هوش مصنوعی سازمانی | Enterprise AI Assistant',
  description: 'پلتفرم جامع هوش مصنوعی سازمانی با کنترل دسترسی، اتصال Active Directory و RAG',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fa" dir="rtl">
      <head>
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css"
        />
      </head>
      <body className="font-vazir bg-slate-50 text-slate-900 dark:bg-dark-bg dark:text-dark-text antialiased min-h-screen selection:bg-enterprise-500 selection:text-white">
        {children}
      </body>
    </html>
  );
}
