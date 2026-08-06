"use client"

import { useState, useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { Brain, Loader2, CheckCircle, AlertCircle } from "lucide-react"

const STEPS = [
  "Upload received",
  "Extracting audio",
  "Transcribing speech",
  "Sampling video frames",
  "Analyzing visual content",
  "Running neuro-signal analysis",
  "Detecting instructional risks",
  "Generating report",
  "Analysis complete",
]

export default function JobStatusPage() {
  const params = useParams()
  const router = useRouter()
  const jobId = params.jobId as string

  const [status, setStatus] = useState<{
    status: string
    progress: number
    current_step: string
    error_message?: string
  } | null>(null)

  const [polling, setPolling] = useState(true)

  useEffect(() => {
    if (!polling) return

    const pollStatus = async () => {
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/analysis-jobs/${jobId}`
        )
        if (!res.ok) throw new Error("Failed to fetch status")

        const data = await res.json()
        setStatus(data)

        if (data.status === "completed") {
          setPolling(false)
          // Redirect to report after a short delay
          setTimeout(() => {
            router.push(`/reports/${jobId}`)
          }, 1500)
        } else if (data.status === "failed") {
          setPolling(false)
        }
      } catch (err) {
        console.error(err)
      }
    }

    pollStatus()
    const interval = setInterval(pollStatus, 2000)
    return () => clearInterval(interval)
  }, [jobId, polling, router])

  const getCurrentStepIndex = () => {
    if (!status?.current_step) return 0
    return STEPS.findIndex((step) => step.toLowerCase().includes(status.current_step?.toLowerCase() || ""))
  }

  const currentStepIndex = getCurrentStepIndex()

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white">
        <div className="container mx-auto px-4 py-4 flex items-center gap-2">
          <Brain className="w-6 h-6 text-blue-600" />
          <h1 className="text-lg font-semibold">CourseBrain QA</h1>
        </div>
      </header>

      <main className="container mx-auto px-4 py-12">
        <div className="max-w-2xl mx-auto">
          <div className="bg-white rounded-lg shadow-lg p-8">
            <h2 className="text-2xl font-bold mb-6">Analysis Progress</h2>

            {status?.status === "failed" ? (
              <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
                <AlertCircle className="w-12 h-12 mx-auto mb-4 text-red-600" />
                <h3 className="text-lg font-semibold text-red-800 mb-2">Analysis Failed</h3>
                <p className="text-red-700 mb-4">{status.error_message || "An unknown error occurred"}</p>
                <Link
                  href="/"
                  className="inline-block bg-red-600 text-white px-6 py-2 rounded-lg hover:bg-red-700"
                >
                  Try Again
                </Link>
              </div>
            ) : status?.status === "completed" ? (
              <div className="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
                <CheckCircle className="w-12 h-12 mx-auto mb-4 text-green-600" />
                <h3 className="text-lg font-semibold text-green-800 mb-2">Analysis Complete!</h3>
                <p className="text-green-700">Redirecting to report...</p>
              </div>
            ) : (
              <>
                <div className="mb-8">
                  <div className="flex justify-between text-sm text-gray-600 mb-2">
                    <span>Progress</span>
                    <span>{status?.progress || 0}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-3">
                    <div
                      className="bg-blue-600 h-3 rounded-full transition-all duration-500"
                      style={{ width: `${status?.progress || 0}%` }}
                    />
                  </div>
                </div>

                <div className="space-y-4">
                  {STEPS.map((step, index) => {
                    const isCompleted = index < currentStepIndex
                    const isCurrent = index === currentStepIndex

                    return (
                      <div
                        key={step}
                        className={`flex items-center gap-3 p-3 rounded-lg ${
                          isCurrent ? "bg-blue-50" : ""
                        }`}
                      >
                        {isCompleted ? (
                          <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0" />
                        ) : isCurrent ? (
                          <Loader2 className="w-5 h-5 text-blue-600 animate-spin flex-shrink-0" />
                        ) : (
                          <div className="w-5 h-5 rounded-full border-2 border-gray-300 flex-shrink-0" />
                        )}
                        <span
                          className={`${
                            isCurrent ? "text-blue-700 font-medium" : "text-gray-600"
                          }`}
                        >
                          {step}
                        </span>
                      </div>
                    )
                  })}
                </div>

                <p className="mt-8 text-center text-sm text-gray-500">
                  This process may take several minutes depending on video length.
                </p>
              </>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
