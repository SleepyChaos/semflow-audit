import { createFileRoute } from "@tanstack/react-router"
import { Welcome } from "@/features/welcome/Welcome"

export const Route = createFileRoute("/login")({
  component: Welcome,
  head: () => ({
    meta: [{ title: "欢迎使用 · SemFlow Audit" }],
  }),
})
