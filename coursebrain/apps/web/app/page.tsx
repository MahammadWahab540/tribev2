"use client"

import { useState } from "react"
import Link from "next/link"
import { Upload, FileVideo, Brain, AlertTriangle } from "lucide-react"

export default function Home() {
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) return

    setUploading(true)
    setError(null)

    try {
      // Upload file
      const formData = new FormData()
      formData.append("file", file)

      const uploadRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/uploads`, {
        method: "POST",
        body: formData,
      })

      if (!uploadRes.ok) {
        throw new Error("Upload failed")
      }

      const uploadData = await uploadRes.json()

      // Create analysis job
      const jobRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/analysis-jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          upload_id: uploadData.upload_id,
          course_title: "Sample Course",
          target_learner: "General audience",
          lesson_objective: "Introduction to the topic",
          difficulty: "beginner",
          quiz_questions: [],
        }),
      })

      if (!jobRes.ok) {
        throw new Error("Failed to create analysis job")
      }

      const jobData = await jobRes.json()
      setJobId(jobData.job_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred")
    } finally {
      setUploading(false)
    }
  }

  if (jobId) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-6 text-center">
          <Brain className="w-16 h-16 mx-auto mb-4 text-blue-600" />
          <h2 className="text-2xl font-bold mb-2">Analysis Started!</h2>
          <p className="text-gray-600 mb-4">
            Your video is being analyzed. This may take a few minutes.
          </p>
          <Link
            href={`/jobs/${jobId}`}
            className="inline-block bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition"
          >
            View Progress
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
      <header className="border-b bg-white">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Brain className="w-8 h-8 text-blue-600" />
            <h1 className="text-xl font-bold">CourseBrain QA</h1>
          </div>
          <nav className="flex gap-4">
            <Link href="/upload" className="text-gray-600 hover:text-blue-600">
              New Analysis
            </Link>
          </nav>
        </div>
      </header>

      <main className="container mx-auto px-4 py-12">
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-4xl font-bold mb-4">
              Quality Assurance for Edtech Videos
            </h2>
            <p className="text-xl text-gray-600">
              Detect moments where learners may get confused, disengaged, or overloaded.
            </p>
          </div>

          <div className="bg-white rounded-lg shadow-lg p-8">
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-400 transition">
                <input
                  type="file"
                  accept="video/*"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  className="hidden"
                  id="video-upload"
                />
                <label htmlFor="video-upload" className="cursor-pointer">
                  <FileVideo className="w-12 h-12 mx-auto mb-4 text-gray-400" />
                  <p className="text-lg font-medium">
                    {file ? file.name : "Click to upload video"}
                  </p>
                  <p className="text-sm text-gray-500">
                    MP4, MOV, AVI, or WebM (max 2GB)
                  </p>
                </label>
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-red-600" />
                  <p className="text-red-700">{error}</p>
                </div>
              )}

              <button
                type="submit"
                disabled={!file || uploading}
                className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {uploading ? (
                  <>
                    <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Uploading...
                  </>
                ) : (
                  <>
                    <Upload className="w-5 h-5" />
                    Start Analysis
                  </>
                )}
              </button>
            </form>

            <div className="mt-8 pt-6 border-t">
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                <h3 className="font-semibold text-amber-800 mb-2">
                  ⚠️ Research Prototype Notice
                </h3>
                <p className="text-sm text-amber-700">
                  CourseBrain provides instructional-design risk signals. It does not diagnose learners 
                  or measure individual attention, comprehension, or learning outcomes. Uses TribeV2 
                  under CC-BY-NC-4.0 license (non-commercial use only).
                </p>
              </div>
            </div>
          </div>

          <div className="mt-12 grid md:grid-cols-3 gap-6">
            <div className="bg-white rounded-lg p-6 shadow">
              <h3 className="font-semibold mb-2">🧠 Cognitive Load Detection</h3>
              <p className="text-sm text-gray-600">
                Identify moments where too many concepts are introduced without examples.
              </p>
            </div>
            <div className="bg-white rounded-lg p-6 shadow">
              <h3 className="font-semibold mb-2">😴 Passive Stretch Alerts</h3>
              <p className="text-sm text-gray-600">
                Find long periods without learner engagement or interaction.
              </p>
            </div>
            <div className="bg-white rounded-lg p-6 shadow">
              <h3 className="font-semibold mb-2">📊 Visual/Audio Overload</h3>
              <p className="text-sm text-gray-600">
                Detect dense slides combined with complex narration.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
