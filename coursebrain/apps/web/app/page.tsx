"use client"

import Link from "next/link"
import { Brain, ArrowRight } from "lucide-react"

export default function Home() {
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
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-4xl font-bold mb-4">
              Quality Assurance for Edtech Videos
            </h2>
            <p className="text-xl text-gray-600 mb-8">
              Detect moments where learners may get confused, disengaged, or overloaded.
            </p>
            <Link
              href="/upload"
              className="inline-flex items-center gap-2 bg-blue-600 text-white px-8 py-4 rounded-lg font-medium hover:bg-blue-700 transition"
            >
              Start Analysis
              <ArrowRight className="w-5 h-5" />
            </Link>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            <div className="bg-white rounded-lg p-6 shadow">
              <h3 className="font-semibold mb-2 text-lg">🧠 Cognitive Load Detection</h3>
              <p className="text-sm text-gray-600">
                Identify moments where too many concepts are introduced without examples.
              </p>
            </div>
            <div className="bg-white rounded-lg p-6 shadow">
              <h3 className="font-semibold mb-2 text-lg">😴 Passive Stretch Alerts</h3>
              <p className="text-sm text-gray-600">
                Find long periods without learner engagement or interaction.
              </p>
            </div>
            <div className="bg-white rounded-lg p-6 shadow">
              <h3 className="font-semibold mb-2 text-lg">📊 Visual/Audio Overload</h3>
              <p className="text-sm text-gray-600">
                Detect dense slides combined with complex narration.
              </p>
            </div>
          </div>

          <div className="mt-12 bg-amber-50 border border-amber-200 rounded-lg p-6">
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
      </main>
    </div>
  )
}
