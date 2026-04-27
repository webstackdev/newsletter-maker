import LoginForm from "@/components/auth/login-form"

type LoginPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}

function resolveCallbackUrl(value: string | string[] | undefined) {
  if (Array.isArray(value)) {
    return value[0] || "/"
  }

  return value || "/"
}

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const resolvedSearchParams = await searchParams
  const callbackUrl = resolveCallbackUrl(resolvedSearchParams.callbackUrl)

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper px-4 py-10">
      <LoginForm callbackUrl={callbackUrl} />
    </div>
  )
}
