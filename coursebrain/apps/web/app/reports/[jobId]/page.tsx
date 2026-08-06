"use client"

import { useState, useEffect, useRef } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { Brain, AlertTriangle, CheckCircle, ArrowLeft, Download, Play } from "lucide-react"

type Issue = {
  id: string
  type: string
  severity: string
  start_sec: number
  end_sec: number
  title: string
  diagnosis: string
  evidence: string[]
  recommended_fix: string
  rewrite_example: string
  confidence: number
}

type Report = {
  coursebrain_score: number
  summary: string
  disclaimer: string
  video_duration_seconds: number
  metrics: any
  timeline: any[]
  issues: Issue[]
  quiz_alignment: any
}

export default function ReportPage() {
  const params = useParams()
  const jobId = params.jobId as string
  const [report, setReport] = useState<Report | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState("issues")
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    const fetchReport = async () => {
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/reports/${jobId}`
        )
        if (!res.ok) throw new Error("Failed to fetch report")
        const data = await res.json()
        setReport(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : "An error occurred")
      } finally {
        setLoading(false)
      }
    }
    fetchReport()
  }, [jobId])

  const handleJumpToTime = (seconds: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = seconds
      videoRef.current.play()
    }
  }

  const handleExport = () => {
    if (!report) return
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `coursebrain-report-${jobId}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "high":
        return "bg-red-100 text-red-800 border-red-300"
      case "medium":
        return "bg-amber-100 text-amber-800 border-amber-300"
      case "low":
        return "bg-blue-100 text-blue-800 border-blue-300"
      default:
        return "bg-gray-100 text-gray-800 border-gray-300"
    }
  }

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, "0")}`
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600">Loading report...</p>
        </div>
      </div>
    )
  }

  if (error || !report) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-red-600" />
          <p className="text-red-700 mb-4">{error || "Report not found"}</p>
          <Link href="/" className="text-blue-600 hover:underline">
            Return to Home
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white sticky top-0 z-10">
        <div className="container mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/" className="text-gray-600 hover:text-blue-600">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div className="flex items-center gap-2">
              <Brain className="w-6 h-6 text-blue-600" />
              <h1 className="text-lg font-semibold">CourseBrain QA</h1>
            </div>
          </div>
          <button
            onClick={handleExport}
            className="flex items-center gap-2 px-4 py-2 bg-gray-100 rounded-lg hover:bg-gray-200"
          >
            <Download className="w-4 h-4" />
            Export JSON
          </button>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6">
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Left: Video & Score */}
          <div className="lg:col-span-2 space-y-6">
            {/* Score Card */}
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold">CourseBrain Score</h2>
                <div
                  className={`w-20 h-20 rounded-full flex items-center justify-center text-2xl font-bold ${
                    report.coursebrain_score >= 80
                      ? "bg-green-100 text-green-700"
                      : report.coursebrain_score >= 60
                      ? "bg-amber-100 text-amber-700"
                      : "bg-red-100 text-red-700"
                  }`}
                >
                  {Math.round(report.coursebrain_score)}
                </div>
              </div>
              <p className="text-gray-700">{report.summary}</p>
            </div>

            {/* Issues */}
            <div className="bg-white rounded-lg shadow">
              <div className="border-b px-6 py-4">
                <h2 className="text-xl font-bold">Issues ({report.issues.length})</h2>
              </div>
              <div className="p-6 space-y-4 max-h-[600px] overflow-y-auto">
                {report.issues.length === 0 ? (
                  <div className="text-center py-8">
                    <CheckCircle className="w-12 h-12 mx-auto mb-4 text-green-600" />
                    <p className="text-gray-600">No significant issues detected!</p>
                  </div>
                ) : (
                  report.issues.map((issue) => (
                    <div
                      key={issue.id}
                      className={`border rounded-lg p-4 ${getSeverityColor(issue.severity)}`}
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <h3 className="font-semibold">{issue.title}</h3>
                          <p className="text-sm opacity-80">{issue.diagnosis}</p>
                        </div>
                        <button
                          onClick={() => handleJumpToTime(issue.start_sec)}
                          className="flex items-center gap-1 px-3 py-1 bg-white/50 rounded hover:bg-white/80"
                        >
                          <Play className="w-4 h-4" />
                          {formatTime(issue.start_sec)}
                        </button>
                      </div>
                      <div className="flex flex-wrap gap-2 mb-3">
                        {issue.evidence.slice(0, 3).map((ev, i) => (
                          <span key={i} className="text-xs px-2 py-1 bg-white/50 rounded">
                            {ev}
                          </span>
                        ))}
                      </div>
                      <div className="space-y-2 text-sm">
                        <p>
                          <strong>Fix:</strong> {issue.recommended_fix}
                        </p>
                        <p className="italic opacity-80">
                          <strong>Example:</strong> {issue.rewrite_example}
                        </p>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Right: Metrics & Disclaimer */}
          <div className="space-y-6">
            {/* Metrics */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="font-semibold mb-4">Metrics</h3>
              <dl className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <dt className="text-gray-600">Speech Rate</dt>
                  <dd className="font-medium">{report.metrics.avg_speech_rate_wpm?.toFixed(0)} WPM</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-600">Pause Frequency</dt>
                  <dd className="font-medium">{report.metrics.pause_frequency_per_min?.toFixed(1)}/min</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-600">Slide Text Density</dt>
                  <dd className="font-medium">
                    {(report.metrics.avg_slide_text_density * 100).toFixed(1)}%
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-600">Visual Changes</dt>
                  <dd className="font-medium">
                    {report.metrics.visual_change_rate_per_min?.toFixed(1)}/min
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-600">TribeV2 Signal</dt>
                  <dd className="font-medium">
                    {report.metrics.tribe_signal_available ? "Available" : "Unavailable"}
                  </dd>
                </div>
              </dl>
            </div>

            {/* Disclaimer */}
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
              <h3 className="font-semibold text-amber-800 mb-2 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4" />
                Important Notice
              </h3>
              <p className="text-sm text-amber-700">{report.disclaimer}</p>
            </div>

            {/* Quiz Alignment */}
            {report.quiz_alignment?.matched_questions && (
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="font-semibold mb-4">Quiz Alignment</h3>
                <div className="mb-4">
                  <div className="flex justify-between text-sm mb-1">
                    <span>Coverage</span>
                    <span className="font-medium">{report.quiz_alignment.score.toFixed(0)}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-blue-600 h-2 rounded-full"
                      style={{ width: `${report.quiz_alignment.score}%` }}
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  {report.quiz_alignment.matched_questions.map((q: any, i: number) => (
                    <div key={i} className="text-sm">
                      <div className="flex items-center gap-2">
                        {q.covered_in_video ? (
                          <CheckCircle className="w-4 h-4 text-green-600" />
                        ) : (
                          <AlertTriangle className="w-4 h-4 text-amber-600" />
                        )}
                        <span className="truncate">{q.question}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
