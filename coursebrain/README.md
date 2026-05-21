# CourseBrain QA

A pre-publish quality-assurance tool for edtech course videos. It helps course creators, test-prep teams, and edtech platforms detect moments where learners may get confused, disengaged, overloaded, or passive.

## ⚠️ Important Disclaimers

- **Research Prototype / Non-Commercial Use**: This product uses TribeV2, which is licensed under CC-BY-NC-4.0 (Creative Commons Attribution-NonCommercial 4.0). This MVP is for research and non-commercial use only.
- **Not a Medical Tool**: CourseBrain QA does not diagnose learners, measure individual attention, comprehension, emotions, intelligence, or learning outcomes. It provides instructional-design risk signals based on heuristics and predicted neuro-signal proxies.
- **TribeV2 Fallback**: If TribeV2 inference fails or no GPU is available, the system falls back to transcript/audio/video heuristics and marks the neuro-signal as unavailable.

## Features

- **Video Upload & Analysis**: Upload course videos for automated QA analysis
- **Transcript Analysis**: Speech rate, pauses, jargon density, concept introduction rate
- **Visual Analysis**: Scene changes, OCR text density, slide density
- **Neuro-Signal Analysis**: TribeV2 predicted brain-response signals (when available)
- **Issue Detection**: Cognitive-load risk, passive stretch, visual/audio overload, pacing issues, and more
- **Timestamped Reports**: Clickable issue cards that jump to video timestamps
- **Quiz Alignment**: Check if quiz questions are covered in the video
- **Export**: Download reports as JSON or PDF

## Tech Stack

### Frontend
- Next.js 14+
- TypeScript
- Tailwind CSS
- shadcn/ui
- Recharts

### Backend
- Python 3.11+
- FastAPI
- Celery (background jobs)
- Redis (job queue)
- PostgreSQL (metadata)
- FFmpeg (video/audio processing)
- Whisper/faster-whisper (transcription)
- EasyOCR (optional OCR)
- TribeV2 (neuro-signal backend)

## Prerequisites

### System Requirements
- Python 3.11+
- Node.js 18+
- FFmpeg (`apt install ffmpeg` or `brew install ffmpeg`)
- Redis (`apt install redis-server` or `brew install redis`)
- PostgreSQL 14+
- GPU recommended for TribeV2 (CUDA 11.8+)

### Environment Variables

Create `.env` files as needed:

```bash
# Backend (.env)
DATABASE_URL=postgresql://user:password@localhost:5432/coursebrain
REDIS_URL=redis://localhost:6379/0
STORAGE_PATH=./storage
TRIBE_CACHE_FOLDER=./cache
OPENAI_API_KEY=sk-...  # Optional, for LLM reporter
LLM_MODEL=gpt-4o-mini  # or any OpenAI-compatible model

# Frontend (apps/web/.env.local)
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Installation

### 1. Clone and Setup Backend

```bash
cd coursebrain/services/api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install TribeV2 (non-commercial use only)
pip install git+https://github.com/facebookresearch/tribev2.git
```

### 2. Install TribeV2 Dependencies

TribeV2 requires additional setup:

```bash
# Install system dependencies for TribeV2
apt install -y libavcodec-dev libavformat-dev libavutil-dev libswresample-dev

# Download TribeV2 model (first run will auto-download)
# The model is ~2GB, ensure you have sufficient disk space
```

### 3. Setup Database

```bash
# Start PostgreSQL
sudo systemctl start postgresql  # or brew services start postgresql

# Create database
createdb coursebrain

# Run migrations (if using Alembic)
# alembic upgrade head
```

### 4. Start Redis

```bash
redis-server
```

### 5. Start Backend Services

```bash
# Terminal 1: Start FastAPI
cd coursebrain/services/api
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start Celery Worker
cd coursebrain/services/api
source venv/bin/activate
celery -A app.main.celery_app worker --loglevel=info --concurrency=1
```

### 6. Setup Frontend

```bash
cd coursebrain/apps/web

# Install dependencies
npm install

# Start development server
npm run dev
```

The app will be available at `http://localhost:3000`.

## API Endpoints

### Upload Video

```bash
curl -X POST http://localhost:8000/api/uploads \
  -F "file=@path/to/video.mp4"
```

Response:
```json
{
  "upload_id": "uuid-string",
  "filename": "video.mp4",
  "size_bytes": 12345678
}
```

### Create Analysis Job

```bash
curl -X POST http://localhost:8000/api/analysis-jobs \
  -H "Content-Type: application/json" \
  -d '{
    "upload_id": "uuid-string",
    "course_title": "Introduction to Algebra",
    "target_learner": "High school students",
    "lesson_objective": "Understand linear equations",
    "difficulty": "beginner",
    "quiz_questions": ["What is a linear equation?", "Solve 2x + 3 = 7"]
  }'
```

Response:
```json
{
  "job_id": "uuid-string",
  "status": "queued"
}
```

### Get Job Status

```bash
curl http://localhost:8000/api/analysis-jobs/{job_id}
```

Response:
```json
{
  "job_id": "uuid-string",
  "status": "processing",
  "progress": 45,
  "current_step": "Transcribing audio"
}
```

### Get Report

```bash
curl http://localhost:8000/api/reports/{job_id}
```

## Project Structure

```
coursebrain/
├── apps/
│   └── web/                    # Next.js frontend
│       ├── app/                # App router pages
│       ├── components/         # React components
│       ├── lib/                # Utility functions
│       └── types/              # TypeScript types
├── services/
│   └── api/                    # FastAPI backend
│       ├── app/
│       │   ├── main.py         # FastAPI app entry
│       │   ├── config.py       # Configuration
│       │   ├── db.py           # Database connection
│       │   ├── models.py       # SQLAlchemy models
│       │   ├── schemas.py      # Pydantic schemas
│       │   ├── routes/         # API route handlers
│       │   ├── workers/        # Celery tasks
│       │   ├── analyzers/      # Analysis modules
│       │   └── utils/          # Utility functions
│       └── requirements.txt
└── infra/
    └── docker-compose.yml      # Docker services
```

## Analyzer Modules

### Audio Analyzer (`audio_analyzer.py`)
- Extracts audio from video using FFmpeg
- Transcribes using Whisper/faster-whisper
- Computes speech rate, pause frequency, filler words

### Transcript Analyzer (`transcript_analyzer.py`)
- Words per minute per window
- Sentence length analysis
- Jargon density detection
- Concept introduction rate
- Learner action gap tracking
- Confusion marker detection

### Visual Analyzer (`visual_analyzer.py`)
- Scene-change detection
- OCR text density
- Slide density estimation
- Visual stability/churn metrics

### Tribe Analyzer (`tribe_analyzer.py`)
- Loads TribeV2 model lazily
- Predicts neuro-signal responses
- Computes activation energy and signal variation
- Identifies low/high variation windows
- Graceful fallback on errors

### Scoring (`scoring.py`)
- Overall CourseBrain Score (0-100)
- Weighted sub-scores: clarity, pacing, cognitive load, engagement, assessment, accessibility
- Issue-based deductions

### Issue Detector (`issue_detector.py`)
- Applies heuristics to detect risks
- Combines multiple signals for robust detection
- Generates structured issue candidates

### LLM Reporter (`llm_reporter.py`)
- Converts metrics to human-readable issues
- Strict JSON schema enforcement
- Actionable fix recommendations
- No timestamp invention

## Issue Types

1. **Cognitive Load Risk**: Too many concepts without examples
2. **Passive Stretch**: Long periods without learner action
3. **Visual/Audio Overload**: Dense slides with complex narration
4. **Unclear Explanation**: Vague or confusing segments
5. **Pacing Issue**: Too fast or too slow delivery
6. **Missing Example**: Abstract concepts without concrete examples
7. **Jargon Burst**: High density of technical terms
8. **Quiz Mismatch**: Quiz questions not covered in video
9. **Objective Mismatch**: Content drifts from lesson objective
10. **Accessibility**: Issues affecting diverse learners

## Fallback Mode

If TribeV2 is unavailable (no GPU, installation failure, timeout):
- The system continues with heuristic-based analysis
- `tribe_signal_available` is set to `false` in the report
- All other analyzers function normally
- A notice is shown in the UI explaining the fallback

## Sample Report JSON

See `sample_report.json` for a complete example.

## Development

### Running Tests

```bash
cd coursebrain/services/api
pytest
```

### Code Style

```bash
# Backend
black .
flake8 .
mypy .

# Frontend
npm run lint
npm run format
```

## License

- CourseBrain QA code: MIT License
- TribeV2: CC-BY-NC-4.0 (non-commercial use only)

## Contributing

Contributions welcome! Please read our contributing guidelines first.

## Roadmap

- [ ] Team dashboard
- [ ] LMS integrations
- [ ] Real-time analysis
- [ ] Mobile app
- [ ] Enterprise permissions
- [ ] Fine-tuned TribeV2 models
