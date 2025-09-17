import './globals.css'
import { Inter } from 'next/font/google'
import TopNav from './(components)/TopNav'

const inter = Inter({ subsets: ['latin'] })

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <head>
        <link rel="icon" href="/favicon.ico" />
      </head>
      <body className={`${inter.className} min-h-screen bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100`}>
        <TopNav />
        {children}
      </body>
    </html>
  )
}
