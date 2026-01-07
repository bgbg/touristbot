# Tourism RAG System with Google Gemini

A Retrieval-Augmented Generation (RAG) system for tourism Q&A using Google Gemini's File Search API. The system organizes content by geographic area and site, enabling location-specific question answering.

## Features

- **Streamlit Web Interface**: Modern web UI for Q&A and content management
- **Location-Based RAG**: Organize content by area/site hierarchy (e.g., Tel Aviv District → Jaffa Port)
- **Flexible Content Upload**: Upload from structured directories or flat folders with custom location mapping
- **Content Management**: View, delete, and manage uploaded content through the web interface
- **Token-Based Chunking**: Smart content chunking with configurable overlap
- **Bilingual Support**: Handle content in multiple languages (English, Hebrew, etc.)
- **Upload Tracking**: Avoid duplicate uploads with hash-based file tracking

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

5. Configure the system by editing `config.yaml`:
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

## Project Structure

```
roy_chat/
├── gemini/
│   ├── main_qa.py              # Streamlit web interface (Q&A + Management)
│   ├── main_upload.py          # CLI upload tool
│   ├── config.py               # Configuration management
│   ├── config.yaml             # Configuration file
│   ├── chunker.py              # Content chunking logic
│   ├── directory_parser.py     # Parse content directory structure
│   ├── store_manager.py        # Gemini File Search API wrapper
│   ├── store_registry.py       # Map locations to Gemini stores
│   ├── upload_tracker.py       # Track uploaded files with hashes
│   ├── upload_manager.py       # Upload operations and content management
│   └── query_processor.py      # Query processing and RAG logic
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

## Configuration Options

Key settings in `config.yaml`:

- `content_root`: Directory containing source content
- `chunks_dir`: Directory for generated chunks
- `chunk_tokens`: Tokens per chunk (default: 7000)
- `chunk_overlap_percent`: Overlap between chunks (default: 0.20)
- `model_name`: Gemini model to use (e.g., "gemini-2.0-flash-exp")
- `temperature`: Model temperature for responses (0.0-2.0)
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
