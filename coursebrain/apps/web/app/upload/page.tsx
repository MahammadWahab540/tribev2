"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Upload, FileVideo, Brain, AlertTriangle } from "lucide-react"

export default function UploadPage() {
  const router = useRouter()
  const [file, setFile] = useState<File | null>(null)
  const [courseTitle, setCourseTitle] = useState("")
  const [targetLearner, setTargetLearner] = useState("")
  const [lessonObjective, setLessonObjective] = useState("")
  const [difficulty, setDifficulty] = useState<"beginner" | "intermediate" | "advanced">("beginner")
  const [quizQuestions, setQuizQuestions] = useState("")
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) {
      setError("Please select a video file")
      return
    }

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
        const errorData = await uploadRes.json().catch(() => ({}))
        throw new Error(errorData.detail || "Upload failed")
      }

      const uploadData = await uploadRes.json()

      // Parse quiz questions (one per line)
      const questions = quizQuestions
        .split("\n")
        .map((q) => q.trim())
        .filter((q) => q.length > 0)

      // Create analysis job with real metadata
      const jobRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/analysis-jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          upload_id: uploadData.upload_id,
          course_title: courseTitle || "Untitled Course",
          target_learner: targetLearner || "General audience",
          lesson_objective: lessonObjective || "Learn the basics",
          difficulty: difficulty,
          quiz_questions: questions,
        }),
      })

      if (!jobRes.ok) {
        const errorData = await jobRes.json().catch(() => ({}))
        throw new Error(errorData.detail || "Failed to create analysis job")
      }

      const jobData = await jobRes.json()
      
      // Redirect to job progress page
      router.push(`/jobs/${jobData.job_id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred")
    } finally {
      setUploading(false)
    }
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
            <a href="/" className="text-gray-600 hover:text-blue-600">
              Home
            </a>
          </nav>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-8">
            <h2 className="text-3xl font-bold mb-2">
              Start Video Analysis
            </h2>
            <p className="text-gray-600">
              Upload your course video and provide lesson details for comprehensive QA analysis.
            </p>
          </div>

          <div className="bg-white rounded-lg shadow-lg p-8">
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Video Upload */}
              <div>
                <label className="block text-sm font-medium mb-2">
                  Course Video *
                </label>
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-blue-400 transition">
                  <input
                    type="file"
                    accept="video/*,.mp4,.mov,.avi,.webm,.mkv"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                    className="hidden"
                    id="video-upload"
                  />
                  <label htmlFor="video-upload" className="cursor-pointer block">
                    <FileVideo className="w-12 h-12 mx-auto mb-4 text-gray-400" />
                    <p className="text-lg font-medium">
                      {file ? file.name : "Click to upload video"}
                    </p>
                    <p className="text-sm text-gray-500">
                      MP4, MOV, AVI, WebM, or MKV (max 2GB)
                    </p>
                  </label>
                </div>
              </div>

              {/* Course Title */}
              <div>
                <label htmlFor="courseTitle" className="block text-sm font-medium mb-2">
                  Course Title
                </label>
                <input
                  type="text"
                  id="courseTitle"
                  value={courseTitle}
                  onChange={(e) => setCourseTitle(e.target.value)}
                  placeholder="e.g., Introduction to Python Programming"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              {/* Target Learner */}
              <div>
                <label htmlFor="targetLearner" className="block text-sm font-medium mb-2">
                  Target Learner
                </label>
                <input
                  type="text"
                  id="targetLearner"
                  value={targetLearner}
                  onChange={(e) => setTargetLearner(e.target.value)}
                  placeholder="e.g., High school students, College freshmen, Working professionals"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              {/* Lesson Objective */}
              <div>
                <label htmlFor="lessonObjective" className="block text-sm font-medium mb-2">
                  Lesson Objective *
                </label>
                <textarea
                  id="lessonObjective"
                  value={lessonObjective}
                  onChange={(e) => setLessonObjective(e.target.value)}
                  placeholder="e.g., Students will be able to understand and apply the concept of variables in programming"
                  rows={3}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              {/* Difficulty */}
              <div>
                <label htmlFor="difficulty" className="block text-sm font-medium mb-2">
                  Difficulty Level
                </label>
                <select
                  id="difficulty"
                  value={difficulty}
                  onChange={(e) => setDifficulty(e.target.value as typeof difficulty)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="beginner">Beginner</option>
                  <option value="intermediate">Intermediate</option>
                  <option value="advanced">Advanced</option>
                </select>
              </div>

              {/* Quiz Questions */}
              <div>
                <label htmlFor="quizQuestions" className="block text-sm font-medium mb-2">
                  Quiz Questions (Optional)
                </label>
                <textarea
                  id="quizQuestions"
                  value={quizQuestions}
                  onChange={(e) => setQuizQuestions(e.target.value)}
                  placeholder="Enter one question per line&#10;e.g.&#10;What is a variable?&#10;How do you declare a constant?&#10;What is the difference between let and const?"
                  rows={4}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm"
                />
                <p className="text-xs text-gray-500 mt-1">
                  One question per line. Leave empty if no quiz questions.
                </p>
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
        </div>
      </main>
    </div>
  )
}
