import { Link } from "@tanstack/react-router"
import { Terminal } from "lucide-react"
import { cn } from "@/lib/utils"
interface LogoProps { variant?: "full" | "icon" | "responsive"; className?: string; asLink?: boolean }
export function Logo({ variant = "full", className, asLink = true }: LogoProps) {
  const content = <span className={cn("flex items-center gap-3 font-mono font-semibold", className)}><Terminal size={24} />{variant !== "icon" ? "AI Code Audit" : null}</span>
  return asLink ? <Link to="/">{content}</Link> : content
}
