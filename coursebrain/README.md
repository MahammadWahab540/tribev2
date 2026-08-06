# CourseBrain QA

A pre-publish quality-assurance tool for edtech course videos. It helps course creators, test-prep teams, and edtech platforms detect moments where learners may get confused, disengaged, overloaded, or passive.

## ⚠️ Important Disclaimers

- **Research Prototype / Non-Commercial Use**: This product uses TribeV2, which is licensed under CC-BY-NC-4.0 (Creative Commons Attribution-NonCommercial 4.0). This MVP is for research and non-commercial use only.
- **Not a Medical Tool**: CourseBrain QA does not diagnose learners, measure individual attention, comprehension, emotions, intelligence, or learning outcomes. It provides instructional-design risk signals based on heuristics and predicted neuro-signal proxies.
- **TribeV2 Optional**: By default, the MVP runs in heuristic/mock-friendly mode. TribeV2 is optional and disabled unless `ENABLE_TRIBE=true`. If enabled but unavailable, the system falls back to transcript/audio/video heuristics.

## Quick Start

### Using Docker Compose (Recommended)

```bash
cd coursebrain/infra
docker compose up -d
```

This starts:
- PostgreSQL on port 5432
- Redis on port 6379
- FastAPI backend on port 8000
- Celery worker (processing jobs with mock analysis)

The API will be available at `http://localhost:8000`.

### Frontend Setup

```bash
cd coursebrain/apps/web
npm install
npm run dev
```

The frontend will be available at `http://localhost:3000`.

## Features

- **Video Upload & Analysis**: Upload course videos for automated QA analysis
- **Mock Analysis Mode**: Fast demos without heavy models (enabled by default in Docker)
- **Transcript Analysis**: Speech rate, pauses, jargon density, concept introduction rate
- **Visual Analysis**: Scene changes, OCR text density (optional), slide density
- **Issue Detection**: Cognitive-load risk, passive stretch, visual/audio overload, pacing issues
- **Timestamped Reports**: Clickable issue cards that jump to video timestamps
- **Quiz Alignment**: Check if quiz questions are covered in the video
- **Export**: Download reports as JSON

## Tech Stack

### Frontend
- Next.js 14+
- TypeScript
- Tailwind CSS
- Recharts

### Backend
- Python 3.11+
- FastAPI
- Celery (background jobs)
- Redis (job queue)
- PostgreSQL (metadata)
- FFmpeg (video/audio processing)
- Whisper/faster-whisper (transcription, optional)
- EasyOCR (optional OCR)
- TribeV2 (optional neuro-signal backend)

## Configuration

### Environment Variables

Create `.env` files as needed:

```bash
# Backend (.env)
DATABASE_URL=postgresql://user:password@localhost:5432/coursebrain
REDIS_URL=redis://localhost:6379/0
STORAGE_PATH=./storage
TRIBE_CACHE_FOLDER=./cache

# Feature flags (default: all false for lightweight demo)
ENABLE_TRIBE=false          # Enable TribeV2 neuro-signal analysis
ENABLE_LLM=false            # Enable LLM-based report refinement
ENABLE_OCR=false            # Enable OCR for visual analysis
MOCK_ANALYSIS=true          # Use mock analysis for fast demos

# Analysis settings
TASK_TIME_LIMIT_SECONDS=3600
MAX_VIDEO_DURATION_SECONDS=1800
VIDEO_SAMPLE_INTERVAL=5.0   # Sample frames every 5 seconds
TRANSCRIPT_WINDOW_SIZE=30   # Analyze in 30-second windows

# Optional: LLM configuration
OPENAI_API_KEY=sk-...       # For LLM reporter
LLM_MODEL=gpt-4o-mini

# Frontend (apps/web/.env.local)
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Installation (Local Development)

### Prerequisites

- Python 3.11+
- Node.js 18+
- FFmpeg (`apt install ffmpeg` or `brew install ffmpeg`)
- Redis (`apt install redis-server` or `brew install redis`)
- PostgreSQL 14+

### 1. Setup Backend

```bash
cd coursebrain/services/api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Setup Database

```bash
# Start PostgreSQL
sudo systemctl start postgresql  # or brew services start postgresql

# Create database
createdb coursebrain
```

### 3. Start Services

```bash
# Terminal 1: Start FastAPI
cd coursebrain/services/api
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start Celery Worker
cd coursebrain/services/api
source venv/bin/activate
celery -A app.celery_app.celery_app worker --loglevel=info --concurrency=1
```

### 4. Setup Frontend

```bash
cd coursebrain/apps/web

# Install dependencies
npm install

# Start development server
npm run dev
```

## Mock Analysis Mode

For quick demos without GPU or heavy model downloads, enable mock analysis:

```bash
# In .env
MOCK_ANALYSIS=true
```

When enabled:
- Skips Whisper transcription
- Skips frame sampling and OCR
- Skips TribeV2 inference
- Generates deterministic mock issues scaled to video duration
- Returns a realistic report in seconds

Default mock issues:
1. High cognitive-load risk (15%-25% of video)
2. Passive stretch detected (40%-55% of video)
3. Visual/audio overload risk (70%-80% of video)

## TribeV2 Integration (Optional)

TribeV2 is disabled by default. To enable:

```bash
# In .env
ENABLE_TRIBE=true
```

Then install TribeV2:

```bash
pip install git+https://github.com/facebookresearch/tribev2.git

# System dependencies
apt install -y libavcodec-dev libavformat-dev libavutil-dev libswresample-dev
```

**Note**: TribeV2 requires ~2GB disk space for the model and benefits significantly from GPU acceleration (CUDA 11.8+).

If TribeV2 fails or is unavailable, the job continues with heuristic analysis and marks `tribe_signal_available: false` in the report.

## API Endpoints

### Health Check

```bash
curl http://localhost:8000/health
```

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

### Get Upload Info

```bash
curl http://localhost:8000/api/uploads/{upload_id}
```

### Stream Video

```bash
curl http://localhost:8000/api/uploads/{upload_id}/stream
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

### Get Job Status

```bash
curl http://localhost:8000/api/analysis-jobs/{job_id}
```

### Get Report

```bash
curl http://localhost:8000/api/reports/{job_id}
```

## User Flow

1. Open `http://localhost:3000/upload`
2. Fill in course metadata:
   - Course title
   - Target learner
   - Lesson objective
   - Difficulty level
   - Quiz questions (one per line)
3. Upload video file (MP4, MOV, AVI, WebM, MKV)
4. Click "Start Analysis"
5. View progress on job status page
6. When complete, view report with:
   - Video player with clickable timestamps
   - CourseBrain score
   - Issue cards with recommended fixes
   - Timeline visualization
   - Quiz alignment metrics
   - JSON export option

## Known Limitations

- Mock analysis generates placeholder issues, not real analysis
- Without ENABLE_LLM, issue descriptions are heuristic-based
- Without ENABLE_OCR, visual analysis uses edge detection only
- PDF export not yet implemented
- No authentication or user management
- Single-user local deployment only

## License

- CourseBrain QA code: MIT License
- TribeV2: CC-BY-NC-4.0 (non-commercial use only)

## Project Structure

```
coursebrain/
├── apps/
│   └── web/                    # Next.js frontend
│       ├── app/                # App router pages
│       │   ├── upload/         # Upload form page
│       │   ├── jobs/           # Job progress page
│       │   └── reports/        # Report viewer page
│       ├── components/         # React components
│       └── lib/                # Utility functions
├── services/
│   └── api/                    # FastAPI backend
│       ├── app/
│       │   ├── celery_app.py   # Celery configuration
│       │   ├── config.py       # Settings
│       │   ├── db.py           # Database connection
│       │   ├── schemas.py      # Pydantic schemas
│       │   ├── routes/         # API endpoints
│       │   ├── workers/        # Celery tasks
│       │   ├── analyzers/      # Analysis modules
│       │   └── utils/          # Utilities
│       └── requirements.txt
└── infra/
    └── docker-compose.yml      # Docker services
```
