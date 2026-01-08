# Tourism RAG System with Google Gemini

A Retrieval-Augmented Generation (RAG) system for tourism Q&A using Google Gemini's File Search API. The system organizes content by geographic area and site, enabling location-specific question answering.

## Features

- **Streamlit Web Interface**: Modern web UI for Q&A and content management
- **Location-Based RAG**: Organize content by area/site hierarchy (e.g., Tel Aviv District → Jaffa Port)
- **YAML-Based Prompt Configuration**: Separate prompt engineering from code with version-controlled YAML files
- **Flexible Content Upload**: Upload from structured directories or flat folders with custom location mapping
- **Content Management**: View, delete, and manage uploaded content through the web interface
- **Token-Based Chunking**: Smart content chunking with configurable overlap
- **Bilingual Support**: Handle content in multiple languages (English, Hebrew, etc.)
- **Auto-Registry Rebuild**: Registry automatically rebuilds from Gemini Files API on startup (solves Streamlit Cloud restart issue)
- **48-Hour File Persistence**: Uploaded files persist in Gemini API for 48 hours, enabling registry recovery after restarts

## Installation

1. Create and activate virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Linux/Mac
# or: .venv\Scripts\activate  # On Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Get your Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey)

4. Set up secrets:
```bash
# Copy the example secrets file
cp .streamlit/secrets.toml.example .streamlit/secrets.toml

# Edit .streamlit/secrets.toml and add your API key
# GOOGLE_API_KEY = "your-api-key-here"
# TAVILY_API_KEY = "your-tavily-key-here"  # Optional
```

**Important**: Never commit `.streamlit/secrets.toml` to git - it's already in `.gitignore`

5. Configure Google Cloud Storage (required for chunk storage):

**Why GCS?** The system stores processed chunks in Google Cloud Storage, ensuring they're available both locally and when deployed to Streamlit Cloud. All developers use the same GCS bucket as the single source of truth.

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

6. Configure the system by editing `config.yaml`:
```yaml
content_root: "data/locations"
chunks_dir: "data/chunks"
chunk_tokens: 7000
chunk_overlap_percent: 0.20
model_name: "gemini-2.0-flash-exp"
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

### Running Streamlit App

**Development mode:**
```bash
streamlit run gemini/main_qa.py
```

**Production mode with custom port:**
```bash
streamlit run gemini/main_qa.py --server.port 8501 --server.address 0.0.0.0
```

**Run in background:**
```bash
nohup streamlit run gemini/main_qa.py --server.port 8501 > streamlit.log 2>&1 &
```

### Deployment Options

#### 1. Streamlit Community Cloud (Free)

1. Push your code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click "New app"
4. Select your repository and branch
5. Set main file path: `gemini/main_qa.py`
6. Add secrets in App Settings → Secrets:
   ```toml
   GOOGLE_API_KEY = "your-api-key-here"
   TAVILY_API_KEY = "your-tavily-key-here"
   ```
7. Deploy

**Note**: The app uses the same secret format for local development (`.streamlit/secrets.toml`) and cloud deployment (Streamlit Cloud secrets dashboard).

#### 2. Docker Deployment

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "gemini/main_qa.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

Build and run:
```bash
docker build -t tourism-rag .
docker run -p 8501:8501 -e GEMINI_API_KEY='your-key' tourism-rag
```

#### 3. VPS/Cloud Server (AWS, GCP, Azure, DigitalOcean)

1. SSH into your server
2. Clone the repository
3. Install Python and dependencies
4. Set environment variable for API key
5. Run with systemd service:

Create `/etc/systemd/system/streamlit-rag.service`:
```ini
[Unit]
Description=Tourism RAG Streamlit App
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/roy_chat
Environment="GEMINI_API_KEY=your-api-key"
ExecStart=/path/to/.venv/bin/streamlit run gemini/main_qa.py --server.port 8501 --server.address 0.0.0.0
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable streamlit-rag
sudo systemctl start streamlit-rag
```

#### 4. Behind Nginx (Production)

Configure Nginx as reverse proxy:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Registry Rebuild Feature

### Overview

The system includes an **automatic registry rebuild** feature that solves the Streamlit Cloud restart problem. When the app restarts (e.g., on Streamlit Cloud), the registry automatically rebuilds from files still available in the Gemini Files API (48-hour persistence window).

### How It Works

1. **Metadata Encoding**: When files are uploaded, area/site information is encoded in the display name:
   ```
   Format: {area}__{site}__{filename}
   Example: tel_aviv__jaffa_port__historical_tour_chunk_001.txt
   ```

2. **API Persistence**: Files remain in Gemini Files API for 48 hours after upload

3. **Startup Rebuild**: On app startup, the registry:
   - Queries `client.files.list()` to get all uploaded files
   - Parses display names to extract area/site metadata
   - Rebuilds registry entries by grouping files by location
   - Merges with existing local registry (preserves manually added entries)

4. **Graceful Fallback**: If rebuild fails (API error, network issue), app falls back to local registry

### Configuration

Control registry rebuild behavior in `config.yaml`:

```yaml
gemini_rag:
  # Enable/disable automatic registry rebuild on startup
  auto_rebuild_registry: true  # Default: true
```

Or disable programmatically:
```python
config = GeminiConfig.from_yaml()
config.auto_rebuild_registry = False
```

### Limitations

- **48-Hour Window**: Files expire after 48 hours in Gemini API. Registry can only rebuild from files uploaded within this window.
- **Encoding Required**: Legacy files uploaded before this feature won't have area/site encoding and will be skipped during rebuild.
- **Upload Tracking Reset**: Upload tracking is session-based and resets on restart. Use "Force Re-upload" if files were modified.

### Troubleshooting

**Problem**: Registry is empty after restart, but files exist in Gemini API

**Solutions**:
1. Check if files have area/site encoding in display names (recent uploads should have this)
2. Verify `auto_rebuild_registry: true` in config.yaml
3. Check Streamlit logs for rebuild errors
4. Files older than 48 hours won't appear in rebuild

**Problem**: Some locations missing after rebuild

**Possible Causes**:
- Files for that location expired (>48 hours old)
- Files uploaded before encoding feature (legacy files)
- Display names don't match expected format

**Solution**: Re-upload content for missing locations

## Project Structure

```
roy_chat/
├── gemini/
│   ├── main_qa.py              # Streamlit web interface (Q&A + Management)
│   ├── main_upload.py          # CLI upload tool
│   ├── config.py               # Configuration management
│   ├── config.yaml             # Configuration file
│   ├── prompt_loader.py        # YAML-based prompt configuration loader
│   ├── chunker.py              # Content chunking logic
│   ├── directory_parser.py     # Parse content directory structure
│   ├── store_manager.py        # Gemini File Search API wrapper
│   ├── store_registry.py       # Map locations to Gemini stores (with rebuild_from_api)
│   ├── display_name_utils.py   # Encode/decode area/site metadata in display names
│   ├── upload_tracker.py       # Track uploaded files with hashes
│   ├── upload_manager.py       # Upload operations and content management
│   └── query_processor.py      # Query processing and RAG logic
├── prompts/
│   ├── tourism_qa.yaml         # Tourism Q&A prompt configuration
│   └── README.md               # Prompt configuration documentation
├── data/
│   ├── locations/              # Source content (area/site hierarchy)
│   └── chunks/                 # Generated chunks (auto-created)
├── config.yaml                 # Main configuration file
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

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

1. **Upload**: Content files are chunked using token-based or character-based chunking
2. **Store**: Chunks are uploaded to Gemini File Search stores (one per location)
3. **Registry**: Mapping between locations and store IDs is maintained in `store_registry.json`
4. **Tracking**: File hashes prevent duplicate uploads (`upload_tracking.json`)
5. **Query**: Questions are processed with relevant chunks loaded based on selected location
6. **Response**: Gemini generates answers using RAG with the uploaded content

## YAML-Based Prompt Configuration

The system uses YAML files to configure LLM prompts, separating prompt engineering from code. This enables version control for prompts, easy A/B testing, and prompt reuse.

### Prompt File Structure

Prompt configurations are stored in the `prompts/` directory. Each YAML file contains:

```yaml
model_name: gemini-2.0-flash
temperature: 0.7

system_prompt: |
  You are a helpful tourism guide assistant for the {area} region,
  specifically for the {site} area.

  Use ONLY the following source material to answer questions.

  SOURCE MATERIAL:
  {context}

user_prompt: |
  {question}
```

### Variable Interpolation

Use Python format string placeholders in prompts:
- `{area}` - Geographic area/region
- `{site}` - Specific site within the area
- `{context}` - Source material/context for RAG
- `{question}` - User's question
- `{conversation_history}` - Previous conversation messages
- `{bot_name}` - Bot name/persona
- `{bot_personality}` - Bot personality description

### Creating Custom Prompts

1. Create a new YAML file in `prompts/` directory (e.g., `prompts/museum_qa.yaml`)
2. Define `model_name`, `temperature`, `system_prompt`, and `user_prompt`
3. Use `{variable_name}` placeholders where dynamic content should be inserted
4. Update your code to load the new prompt configuration:

```python
from gemini.prompt_loader import PromptLoader

# Load prompt configuration
prompt_config = PromptLoader.load('prompts/museum_qa.yaml')

# Format prompts with variables
system_prompt, user_prompt = prompt_config.format(
    area="Jerusalem",
    site="Old City",
    context="Historical information...",
    question="What is the significance of this site?"
)
```

See [prompts/README.md](prompts/README.md) for detailed documentation.

## Configuration Options

Key settings in `config.yaml`:

- `content_root`: Directory containing source content
- `chunks_dir`: Directory for generated chunks
- `chunk_tokens`: Tokens per chunk (default: 7000)
- `chunk_overlap_percent`: Overlap between chunks (default: 0.20)
- `model_name`: Gemini model to use (e.g., "gemini-2.0-flash-exp")
- `temperature`: Model temperature for responses (0.0-2.0)
- `prompts_dir`: Directory containing YAML prompt configurations (default: "prompts/")
- `supported_formats`: File extensions to process (.txt, .md, etc.)

## Generated Files

These files are auto-generated and git-ignored:

- `gemini/store_registry.json`: Maps locations to Gemini store IDs
- `gemini/upload_tracking.json`: Tracks uploaded files with hashes
- `gemini/query_log.jsonl`: Query and response logs (if enabled)
- `data/chunks/`: Generated chunk files

## Dependencies

- `google-genai`: Google Gemini API client
- `streamlit`: Web interface framework
- `pandas`: Data manipulation for UI tables
- `tiktoken`: Token counting for chunking
- `PyYAML`: Configuration file parsing

## Notes

- Deleting content from the web interface removes local tracking and chunks but does not delete from Gemini API
- The system maintains separate stores for each area/site combination
- Upload tracking uses SHA-256 hashes to detect file changes
- Chunks are stored locally for transparency and debugging
