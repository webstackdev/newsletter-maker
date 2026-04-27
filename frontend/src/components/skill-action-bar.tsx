"use client"

import { useMutation, useQuery } from "@tanstack/react-query"
import { useRouter } from "next/navigation"
import { useEffect, useRef, useState } from "react"

import type { ContentSkillName, SkillResult } from "@/lib/types"

type AsyncSkillName = Extract<
  ContentSkillName,
  "relevance_scoring" | "summarization"
>

type SkillActionBarProps = {
  projectId: number
  contentId: number
  canSummarize: boolean
  initialPendingSkills: AsyncSkillName[]
}

type SkillActionResponse = {
  message: string
  skillResult: SkillResult
}

const ghostButtonClass =
  "inline-flex min-h-11 items-center justify-center rounded-full border border-[#1f2b27]/12 bg-transparent px-4 py-3 text-sm font-medium text-[#1f2b27] transition hover:bg-white/50 disabled:cursor-not-allowed disabled:opacity-50"
const statusMessageClass =
  "basis-full rounded-[18px] bg-[#1f2b27]/6 px-4 py-3 text-sm leading-6 text-[#5d6d67]"
const errorMessageClass =
  "basis-full rounded-[18px] bg-[#c55f4d]/14 px-4 py-3 text-sm leading-6 text-[#7c3023]"

function isPendingStatus(status: SkillResult["status"]) {
  return status === "pending" || status === "running"
}

function getSkillLabel(skillName: AsyncSkillName, isBusy: boolean) {
  if (skillName === "summarization") {
    return isBusy ? "Summarizing..." : "Summarize"
  }

  return isBusy ? "Scoring relevance..." : "Explain relevance"
}

export function SkillActionBar({
  projectId,
  contentId,
  canSummarize,
  initialPendingSkills,
}: SkillActionBarProps) {
  const router = useRouter()
  const refreshRequestedRef = useRef(false)
  const [queuedSkills, setQueuedSkills] = useState<AsyncSkillName[]>([])
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const watchedSkills = [...new Set([...initialPendingSkills, ...queuedSkills])]

  const contentSkillResultsQuery = useQuery({
    queryKey: ["content-skill-results", projectId, contentId],
    enabled: watchedSkills.length > 0,
    queryFn: async (): Promise<SkillResult[]> => {
      const response = await fetch(
        `/api/content-skills?projectId=${projectId}&contentId=${contentId}`,
        {
          cache: "no-store",
        },
      )

      if (!response.ok) {
        throw new Error("Unable to refresh skill status.")
      }

      return (await response.json()) as SkillResult[]
    },
    refetchInterval: 2000,
  })

  const hasPendingWatchedSkill = watchedSkills.some((skillName) => {
    const latestSkillResult = contentSkillResultsQuery.data?.find(
      (skillResult) =>
        skillResult.skill_name === skillName && skillResult.superseded_by === null,
    )

    return latestSkillResult ? isPendingStatus(latestSkillResult.status) : false
  })

  useEffect(() => {
    if (
      !contentSkillResultsQuery.data ||
      watchedSkills.length === 0 ||
      hasPendingWatchedSkill ||
      refreshRequestedRef.current
    ) {
      return
    }

    refreshRequestedRef.current = true
    router.refresh()
  }, [contentSkillResultsQuery.data, hasPendingWatchedSkill, router, watchedSkills.length])

  const queueSkillMutation = useMutation({
    mutationFn: async (skillName: AsyncSkillName) => {
      const formData = new FormData()
      formData.set("projectId", String(projectId))
      formData.set("contentId", String(contentId))
      formData.set("redirectTo", `/content/${contentId}?project=${projectId}`)

      const response = await fetch(`/api/skills/${skillName}?mode=json`, {
        method: "POST",
        body: formData,
      })
      const payload = (await response.json()) as Partial<SkillActionResponse>

      if (!response.ok || !payload.skillResult || !payload.message) {
        throw new Error(payload.message || `Unable to run ${skillName}.`)
      }

      return payload as SkillActionResponse
    },
    onSuccess: ({ message, skillResult }) => {
      refreshRequestedRef.current = false
      setErrorMessage(null)
      setStatusMessage(message)

      if (isPendingStatus(skillResult.status)) {
        const queuedSkill = skillResult.skill_name as AsyncSkillName
        setQueuedSkills((currentSkills) =>
          currentSkills.includes(queuedSkill)
            ? currentSkills
            : [...currentSkills, queuedSkill],
        )
        router.refresh()
        return
      }

      router.refresh()
    },
    onError: (error) => {
      setErrorMessage(
        error instanceof Error ? error.message : "Unable to queue skill.",
      )
    },
  })

  const isBusy = (skillName: AsyncSkillName) =>
    watchedSkills.includes(skillName) ||
    (queueSkillMutation.isPending && queueSkillMutation.variables === skillName)

  return (
    <>
      <button
        className={ghostButtonClass}
        type="button"
        disabled={!canSummarize || isBusy("summarization")}
        onClick={() => {
          setStatusMessage(null)
          queueSkillMutation.mutate("summarization")
        }}
      >
        {getSkillLabel("summarization", isBusy("summarization"))}
      </button>
      <button
        className={ghostButtonClass}
        type="button"
        disabled={isBusy("relevance_scoring")}
        onClick={() => {
          setStatusMessage(null)
          queueSkillMutation.mutate("relevance_scoring")
        }}
      >
        {getSkillLabel("relevance_scoring", isBusy("relevance_scoring"))}
      </button>
      {statusMessage ? (
        <p className={statusMessageClass} role="status">
          {statusMessage}
        </p>
      ) : null}
      {errorMessage ? (
        <p className={errorMessageClass} role="alert">
          {errorMessage}
        </p>
      ) : null}
    </>
  )
}
