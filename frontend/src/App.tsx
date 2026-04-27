import { useState } from "react"
import { BrowserRouter, Routes, Route, Link } from "react-router-dom"
import { MessageSquare, Mic, Settings, LogOut } from "lucide-react"
import { ChatAgent } from "@/components/ChatAgent"
import { VoiceAgent } from "@/components/VoiceAgent"
import { UserInfoGate, type UserInfo } from "@/components/UserInfoGate"
import { AdminPanel } from "@/components/admin/AdminPanel"
import { AdminLogin } from "@/components/admin/AdminLogin"
import { ErrorBoundary } from "@/components/ErrorBoundary"
import type { AdminCredentials } from "@/lib/api"
import { cn } from "@/lib/utils"

function CustomerApp() {
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null)
  const [tab, setTab] = useState<"chat" | "voice">("chat")

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header className="border-b px-4 py-3 flex items-center justify-between bg-background/95 backdrop-blur sticky top-0 z-10">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-primary flex items-center justify-center">
            <span className="text-primary-foreground text-xs font-bold">R</span>
          </div>
          <span className="font-semibold text-sm">RelayPay Support</span>
        </div>
        <div className="flex items-center gap-3">
          {userInfo && (
            <span className="text-xs text-muted-foreground hidden sm:block">
              {userInfo.name}
            </span>
          )}
          <Link to="/admin" className="text-xs text-muted-foreground hover:text-foreground transition-colors">
            Admin
          </Link>
        </div>
      </header>

      {!userInfo ? (
        <main className="flex-1 flex flex-col max-w-2xl mx-auto w-full">
          <UserInfoGate onSubmit={setUserInfo} />
        </main>
      ) : (
        <>
          <div className="border-b">
            <div className="flex max-w-2xl mx-auto w-full">
              <button
                onClick={() => setTab("chat")}
                className={cn(
                  "flex-1 flex items-center justify-center gap-2 py-3 text-sm font-medium border-b-2 transition-colors",
                  tab === "chat"
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                )}
              >
                <MessageSquare size={15} />
                Chat
              </button>
              <button
                onClick={() => setTab("voice")}
                className={cn(
                  "flex-1 flex items-center justify-center gap-2 py-3 text-sm font-medium border-b-2 transition-colors",
                  tab === "voice"
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                )}
              >
                <Mic size={15} />
                Voice
              </button>
            </div>
          </div>

          <main
            className="flex-1 flex flex-col max-w-2xl mx-auto w-full"
            style={{ height: "calc(100vh - 105px)" }}
          >
            <ErrorBoundary>
              {tab === "chat" ? (
                <ChatAgent userInfo={userInfo} />
              ) : (
                <VoiceAgent userInfo={userInfo} />
              )}
            </ErrorBoundary>
          </main>
        </>
      )}
    </div>
  )
}

function AdminPage() {
  const [credentials, setCredentials] = useState<AdminCredentials | null>(null)

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b px-4 py-3 flex items-center justify-between bg-background/95 backdrop-blur sticky top-0 z-10">
        <div className="flex items-center gap-2">
          <Settings size={16} className="text-muted-foreground" />
          <span className="font-semibold text-sm">RelayPay Admin</span>
        </div>
        <div className="flex items-center gap-3">
          {credentials && (
            <button
              onClick={() => setCredentials(null)}
              className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
            >
              <LogOut size={12} />
              Sign out
            </button>
          )}
          <Link
            to="/"
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            ← Back to Support
          </Link>
        </div>
      </header>

      {credentials ? (
        <AdminPanel credentials={credentials} />
      ) : (
        <AdminLogin onLogin={setCredentials} />
      )}
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<CustomerApp />} />
        <Route path="/admin" element={<AdminPage />} />
      </Routes>
    </BrowserRouter>
  )
}
