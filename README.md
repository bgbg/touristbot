# Tourism RAG System with Google Gemini

A Retrieval-Augmented Generation (RAG) system for tourism Q&A using Google Gemini's File Search API. The system organizes content by geographic area and site, enabling location-specific question answering.

## Features

### Core Functionality
- **Location-Based RAG**: Organize content by area/site hierarchy (e.g., Tel Aviv District → Jaffa Port)
- **File Search API Integration**: Semantic retrieval using Gemini's File Search with metadata filtering
- **Citation Support**: Automatic source attribution with grounding metadata
- **Server-Side Chunking**: Gemini handles all chunking automatically with configurable parameters
- **Bilingual Support**: Handle content in multiple languages (English, Hebrew, etc.)

### Content Management
- **Streamlit Web Interface**: Modern web UI for Q&A and content management
- **Flexible Content Upload**: Upload from structured directories or flat folders with custom location mapping
- **CLI Upload Tool**: Batch uploads via command-line interface
- **Content Management**: View, delete, and manage uploaded content through the web interface

### Advanced Features
- **Multimodal Image Support**: Automatically extract images from DOCX files with LLM-based relevance filtering
- **Proactive Topic Suggestions**: Pre-generated topics guide users to relevant information
- **YAML-Based Prompt Configuration**: Separate prompt engineering from code with version-controlled YAML files
- **Location-Specific Overrides**: Customize prompts and settings per area/site
- **FastAPI Backend**: Optional REST API backend deployed on Google Cloud Run
- **GCS Storage**: All registries and metadata stored in Google Cloud Storage (single source of truth)

## Installation

### Option 1: Conda Environment (Recommended)
```bash
# Create conda environment
conda create -n tarasa python=3.11
conda activate tarasa

# Install dependencies
pip install -r requirements.txt
```

### Option 2: Virtual Environment
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Linux/Mac
# or: .venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

### API Keys and Secrets

1. Get your Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey)

2. Set up secrets:
```bash
# Copy the example secrets file
cp .streamlit/secrets.toml.example .streamlit/secrets.toml

# Edit .streamlit/secrets.toml and add your API key
# GOOGLE_API_KEY = "your-api-key-here"
# TAVILY_API_KEY = "your-tavily-key-here"  # Optional
```

**Important**: Never commit `.streamlit/secrets.toml` to git - it's already in `.gitignore`

### Configure Google Cloud Storage (Required)

GCS is mandatory for all registry and metadata storage. All developers need GCS access.

**Why GCS?** The system stores all registries (store registry, image registry), topics, and metadata in Google Cloud Storage. This ensures consistency between local development, Streamlit Cloud deployment, and the backend API. GCS is the single source of truth.

a. Create a GCS bucket (if not already created):
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Create/select your project
   - Navigate to Cloud Storage > Buckets
   - Create bucket named `tarasa_tourist_bot_content` (or update `config.yaml` with your bucket name)

b. Create a service account and download credentials:
   - Navigate to "IAM & Admin" > "Service Accounts"
   - Create new service account (or use existing)
   - Grant it "Storage Object Admin" role
   - Create a JSON key and download it

c. Add GCS credentials to `.streamlit/secrets.toml`:
   - Open the downloaded JSON key file
   - Copy its contents into `.streamlit/secrets.toml` as a TOML table
   - See `.streamlit/secrets.toml.example` for the exact format

Example:
```toml
[gcs_credentials]
type = "service_account"
project_id = "your-project-id"
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "your-sa@your-project.iam.gserviceaccount.com"
# ... other fields from the JSON key
```

**For Streamlit Cloud deployment:**
- Add the same `gcs_credentials` table to your Streamlit Cloud app secrets
- The app will work identically in local and cloud environments

### Configure the System

Edit `config.yaml` at the project root:
```yaml
content_root: "data/locations"
gemini_rag:
  model: "gemini-2.0-flash"
  temperature: 0.7
  chunk_tokens: 400  # Server-side chunking parameter
  chunk_overlap_percent: 0.15  # 15% overlap
  file_search_store_name: "TARASA_Tourism_RAG_v2"
  auto_rebuild_registry: false  # Registry rebuild disabled for performance
storage:
  gcs_bucket_name: "tarasa_tourist_bot_content"
```

## Usage

### Web Interface (Recommended)

Start the Streamlit web application:

```bash
streamlit run gemini/main_qa.py
```

The app will open in your browser at `http://localhost:8501`

The web interface provides:

**Chat Tab**:
- Select area and site from sidebar
- Adjust model temperature and settings
- Ask questions about the selected location
- View response times and statistics

**Manage Content Tab**:
- View all uploaded content with chunk counts and timestamps
- Delete content by clicking inline delete buttons
- Upload new content using two methods:
  - **From Folder Path**: Upload files from any folder, assign to existing or new locations
  - **From Existing Content**: Upload from structured `data/locations/` directory

### CLI Upload Tool

For batch uploads or automation, use the command-line tool:

```bash
# Upload all content
python gemini/main_upload.py

# Upload specific area
python gemini/main_upload.py --area hefer_valley

# Upload specific site
python gemini/main_upload.py --area hefer_valley --site agamon_hefer

# Force re-upload (ignore tracking)
python gemini/main_upload.py --force
```

## Deployment

### Streamlit Community Cloud (Recommended for Frontend)

1. Push code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → "New app"
3. Set main file: `gemini/main_qa.py`
4. Add secrets in App Settings → Secrets (GOOGLE_API_KEY, gcs_credentials)
5. Deploy

### FastAPI Backend on Cloud Run (Optional)

```bash
cd backend
./deploy.sh
```

See [backend/README.md](backend/README.md) for details.

**Architecture options:**
- **Streamlit only**: Simple deployment, no API needed
- **Streamlit + Backend API**: Scalable architecture, conversation persistence in GCS

## Project Structure

```
roy_chat/
├── gemini/                     # Core RAG logic
│   ├── main_qa.py              # Streamlit web interface (Q&A + Management)
│   ├── main_upload.py          # CLI upload tool
│   ├── config.py               # Configuration management
│   ├── prompt_loader.py        # YAML-based prompt configuration loader
│   ├── file_search_store.py    # File Search Store management
│   ├── directory_parser.py     # Parse content directory structure
│   ├── store_registry.py       # Map locations to File Search Store
│   ├── image_registry.py       # Image metadata registry
│   ├── image_extractor.py      # Extract images from DOCX
│   ├── image_storage.py        # Upload images to GCS
│   ├── file_api_manager.py     # Upload images to Gemini File API
│   ├── upload_tracker.py       # Track uploaded files with hashes
│   ├── upload_manager.py       # Upload operations and content management
│   ├── topic_extractor.py      # Topic extraction logic
│   └── generate_topics.py      # CLI tool for topic generation
├── backend/                    # FastAPI backend (optional)
│   ├── main.py                 # FastAPI app
│   ├── dependencies.py         # Singleton dependency injection
│   ├── auth.py                 # API key authentication
│   ├── models.py               # Pydantic request/response schemas
│   ├── endpoints/              # API endpoint modules
│   │   ├── qa.py               # Chat endpoint with RAG
│   │   ├── topics.py           # Topics retrieval
│   │   ├── locations.py        # Location management
│   │   └── upload.py           # Upload placeholder
│   ├── conversation_storage/   # GCS conversation management
│   ├── query_logging/          # Query logging to GCS
│   ├── gcs_storage.py          # GCS storage backend
│   ├── tests/                  # Backend unit tests
│   ├── Dockerfile              # Container configuration
│   ├── deploy.sh               # Cloud Run deployment script
│   └── README.md               # Backend documentation
├── config/                     # Unified configuration directory
│   ├── prompts/                # Prompt YAMLs
│   │   ├── tourism_qa.yaml     # Tourism Q&A prompt configuration
│   │   └── topic_extraction.yaml # Topic extraction prompt
│   └── locations/              # Location-specific config overrides
│       └── <area>/
│           ├── <site>.yaml     # Site-level config override
│           └── <site>/
│               └── prompts/    # Site-level prompt overrides
├── data/
│   └── locations/              # Source content (area/site hierarchy)
├── tests/                      # Integration and unit tests
│   ├── test_*.py               # Integration tests
│   └── gemini/                 # Unit tests for gemini module
├── .cache/                     # Temporary files (gitignored)
│   └── upload_tracking.json    # Upload tracking cache
├── config.yaml                 # Main configuration file (at root)
├── requirements.txt            # Python dependencies
├── CLAUDE.md                   # Claude Code instructions
└── README.md                   # This file
```

**Note on GCS storage**: Topics and metadata that were previously mentioned as stored locally are now in GCS:
- `topics/{area}/{site}/topics.json` - In GCS bucket
- `metadata/store_registry.json` - In GCS bucket
- `metadata/image_registry.json` - In GCS bucket

## Content Organization

Content should be organized in a hierarchical structure:

```
data/locations/
├── tel_aviv_district/
│   ├── jaffa_port/
│   │   ├── historical_tour.txt
│   │   └── historical_tour_he.txt
│   └── yarkon_park/
│       ├── park_guide.txt
│       └── park_guide_he.txt
└── hefer_valley/
    ├── agamon_hefer/
    │   ├── nature_reserve.txt
    │   └── nature_reserve_he.txt
    └── alexander_stream/
        ├── hiking_trails.txt
        └── hiking_trails_he.txt
```

Alternatively, use the web interface to upload files from any folder and assign them to locations.

## How It Works

### Upload Pipeline
1. **Content Upload**: Whole files uploaded to File Search Store with metadata (area, site, doc)
2. **Image Extraction**: DOCX files automatically processed to extract inline images
3. **Triple Storage**: Images stored in GCS bucket, uploaded to Gemini File API, tracked in image registry
4. **Server-Side Chunking**: Gemini automatically chunks text files (400 tokens/chunk with 15% overlap)
5. **Registry**: All mappings stored in GCS (`metadata/store_registry.json`, `metadata/image_registry.json`)
6. **Tracking**: File hashes in local cache prevent duplicate uploads (`.cache/upload_tracking.json`)

### Query Pipeline
1. **Metadata Filter**: Query uses area/site filter to retrieve relevant content from File Search Store
2. **Image Retrieval**: Images for the location retrieved from GCS image registry
3. **Multimodal Context**: Image URIs included in Gemini API call (up to 5 images)
4. **LLM Processing**: Gemini generates response with File Search retrieval
5. **Image Relevance**: LLM scores image relevance (0-100) and filters images (score >= 60)
6. **Citations**: Automatic source attribution from grounding metadata
7. **Response**: Text response + filtered images + citations returned to user

### Storage Architecture
- **Single File Search Store**: All locations share one store, isolated by metadata filtering
- **GCS as Source of Truth**: All registries, topics, and images stored in Google Cloud Storage
- **Session State**: Conversation history stored in GCS (backend) or session state (Streamlit)
- **No Local Persistence**: Registries and images are never stored locally (except temporary cache)

## Configuration

### System Configuration

Main configuration file: `config.yaml` (project root)

Key settings:
- `gemini_rag.model`: Gemini model (e.g., "gemini-2.0-flash")
- `gemini_rag.temperature`: Response temperature (0.0-2.0)
- `gemini_rag.chunk_tokens`: Tokens per chunk (default: 400)
- `storage.gcs_bucket_name`: GCS bucket for storage

### Prompts and Location-Specific Overrides

The system supports:
- **YAML-based prompts**: Separate prompt engineering from code
- **Hierarchical overrides**: Customize prompts and settings per area/site
- **Partial overrides**: Only specify fields to change, inherit the rest

Example override structure:
```
config/
├── prompts/                    # Global prompts
│   └── tourism_qa.yaml
└── locations/                  # Location-specific overrides
    └── hefer_valley/
        ├── agamon_hefer.yaml   # Site config override
        └── agamon_hefer/
            └── prompts/        # Site prompt overrides
```

**See [config/README.md](config/README.md) for complete documentation on prompts and overrides.**

## Backend API (Optional)

The system includes a FastAPI backend that can be deployed to Google Cloud Run:

```bash
cd backend
./deploy.sh  # Deploy to Cloud Run
```

**Features:**
- REST API for chat, topics, and location management
- Conversation history stored in GCS
- Query logging to GCS
- API key authentication
- 44+ unit tests

**Service URL:** `https://tourism-rag-backend-347968285860.me-west1.run.app`

See [backend/README.md](backend/README.md) for deployment instructions.

## Key Technical Details

- **Storage**: GCS is mandatory for all registries and metadata (no local fallback)
- **File Search**: Single store for all locations, isolated by metadata filtering (area + site)
- **Images**: Extracted from DOCX, stored in GCS, uploaded to Gemini File API
- **Chunking**: Server-side by Gemini (400 tokens/chunk, 15% overlap)
- **Topics**: Pre-generated during upload, stored in GCS
- **Tracking**: Local cache prevents duplicate uploads (SHA-256 hashing)
