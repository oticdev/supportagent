import { useState } from "react"
import { ArrowRight, User, Mail } from "lucide-react"

export type UserInfo = {
  name: string
  email: string
}

interface Props {
  onSubmit: (info: UserInfo) => void
}

export function UserInfoGate({ onSubmit }: Props) {
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [errors, setErrors] = useState<{ name?: string; email?: string }>({})

  function validate() {
    const next: typeof errors = {}
    if (!name.trim()) next.name = "Please enter your name."
    if (!email.trim()) {
      next.email = "Please enter your email."
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      next.email = "Please enter a valid email address."
    }
    return next
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const errs = validate()
    if (Object.keys(errs).length) {
      setErrors(errs)
      return
    }
    onSubmit({ name: name.trim(), email: email.trim() })
  }

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-sm space-y-6">
        {/* Icon */}
        <div className="flex flex-col items-center gap-2 text-center">
          <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
            <span className="text-primary text-xl font-bold">R</span>
          </div>
          <h1 className="text-lg font-semibold">Welcome to RelayPay Support</h1>
          <p className="text-sm text-muted-foreground">
            Let us know who you are so we can help you faster.
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          {/* Name */}
          <div className="space-y-1.5">
            <label htmlFor="name" className="text-sm font-medium">
              Full name
            </label>
            <div className="relative">
              <User
                size={15}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
              />
              <input
                id="name"
                type="text"
                autoComplete="name"
                placeholder="Ada Okonkwo"
                value={name}
                onChange={(e) => {
                  setName(e.target.value)
                  if (errors.name) setErrors((p) => ({ ...p, name: undefined }))
                }}
                className={`w-full rounded-lg border bg-background px-3 py-2 pl-9 text-sm outline-none transition-colors placeholder:text-muted-foreground focus:ring-2 focus:ring-primary/30 ${
                  errors.name ? "border-destructive" : "border-input"
                }`}
              />
            </div>
            {errors.name && (
              <p className="text-xs text-destructive">{errors.name}</p>
            )}
          </div>

          {/* Email */}
          <div className="space-y-1.5">
            <label htmlFor="email" className="text-sm font-medium">
              Email address
            </label>
            <div className="relative">
              <Mail
                size={15}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
              />
              <input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="ada@company.com"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value)
                  if (errors.email) setErrors((p) => ({ ...p, email: undefined }))
                }}
                className={`w-full rounded-lg border bg-background px-3 py-2 pl-9 text-sm outline-none transition-colors placeholder:text-muted-foreground focus:ring-2 focus:ring-primary/30 ${
                  errors.email ? "border-destructive" : "border-input"
                }`}
              />
            </div>
            {errors.email && (
              <p className="text-xs text-destructive">{errors.email}</p>
            )}
          </div>

          <button
            type="submit"
            className="w-full flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:ring-offset-2"
          >
            Start conversation
            <ArrowRight size={15} />
          </button>
        </form>

        <p className="text-center text-xs text-muted-foreground">
          Your details are only used to assist you during this session.
        </p>
      </div>
    </div>
  )
}
