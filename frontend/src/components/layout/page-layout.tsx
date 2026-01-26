import * as React from "react"
import { Sidebar } from "./sidebar"
import { Header } from "./header"

interface PageLayoutProps {
  children: React.ReactNode
  title?: string
}

export function PageLayout({ children, title }: PageLayoutProps) {
  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <div className="lg:pl-64">
        <Header title={title} />
        <main className="p-4 lg:p-6">{children}</main>
      </div>
    </div>
  )
}
