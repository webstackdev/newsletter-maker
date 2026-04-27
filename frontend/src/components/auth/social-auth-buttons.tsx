"use client";

import { signIn } from "next-auth/react"

export default function SocialButtons() {
  return (
    <div className="flex flex-col space-y-3 w-full max-w-sm">
      {/* GitHub Button */}
      <button
        onClick={() => signIn("github")}
        className="flex items-center justify-center w-full px-4 py-2 space-x-3 text-white transition-colors duration-300 bg-gray-900 rounded-lg hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-900"
      >
        <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M12 1.5C6.201 1.5 1.5 6.201 1.5 12c0 4.642 3.009 8.58 7.182 9.97.525.097.718-.228.718-.507 0-.25-.009-.912-.014-1.79-2.921.635-3.538-1.408-3.538-1.408-.477-1.211-1.166-1.533-1.166-1.533-.954-.652.072-.639.072-.639 1.055.074 1.61 1.083 1.61 1.083.938 1.607 2.46 1.143 3.059.874.095-.679.367-1.143.667-1.406-2.332-.265-4.785-1.166-4.785-5.19 0-1.146.41-2.084 1.082-2.819-.108-.266-.469-1.336.103-2.785 0 0 .882-.282 2.89 1.077A10.061 10.061 0 0 1 12 6.596c.892.004 1.79.12 2.629.352 2.007-1.359 2.888-1.077 2.888-1.077.573 1.449.212 2.519.104 2.785.674.735 1.081 1.673 1.081 2.819 0 4.034-2.457 4.922-4.797 5.182.378.326.714.969.714 1.953 0 1.41-.013 2.546-.013 2.892 0 .282.19.609.724.506A10.503 10.503 0 0 0 22.5 12c0-5.799-4.701-10.5-10.5-10.5Z" />
        </svg>
        <span className="text-sm font-medium">Continue with GitHub</span>
      </button>

      {/* Google Button */}
      <button
        onClick={() => signIn("google")}
        className="flex items-center justify-center w-full px-4 py-2 space-x-3 transition-colors duration-300 bg-white border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-200"
      >
        {/* Simple Google G Icon SVG */}
        <svg className="w-5 h-5" viewBox="0 0 24 24">
          <path
            fill="#4285F4"
            d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
          />
          <path
            fill="#34A853"
            d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
          />
          <path
            fill="#FBBC05"
            d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"
          />
          <path
            fill="#EA4335"
            d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
          />
        </svg>
        <span className="text-sm font-medium">Continue with Google</span>
      </button>
    </div>
  )
}
