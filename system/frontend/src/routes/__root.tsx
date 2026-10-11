import {
  createRootRoute,
  HeadContent,
  Outlet,
  redirect,
} from "@tanstack/react-router"
import ErrorComponent from "@/components/Common/ErrorComponent"
import NotFound from "@/components/Common/NotFound"

const legacyAccountPaths = new Set([
  "/signup",
  "/recover-password",
  "/reset-password",
  "/admin",
  "/settings",
  "/items",
])

export const Route = createRootRoute({
  beforeLoad: ({ location }) => {
    if (legacyAccountPaths.has(location.pathname.replace(/\/$/, ""))) {
      throw redirect({ to: "/", replace: true })
    }
  },
  component: () => (
    <>
      <HeadContent />
      <Outlet />
    </>
  ),
  notFoundComponent: () => <NotFound />,
  errorComponent: () => <ErrorComponent />,
})
