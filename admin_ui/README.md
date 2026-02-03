# Tourism RAG - Admin Backoffice UI

Web-based administrative interface for managing the Tourism RAG system. Built with Streamlit for rapid development and ease of use.

## Overview

The admin backoffice provides a user-friendly interface for:

- **Content Management**: Upload DOCX/PDF/TXT/MD files to locations
- **Content Browsing**: View uploaded files with metadata (images, topics, last updated)
- **Conversation Monitoring**: List, view, and manage chat conversations
- **Bulk Operations**: Delete multiple conversations at once

### Key Features

- Direct GCS access (no additional API layer)
- Multi-page Streamlit app with navigation
- Progress tracking for file uploads
- Conversation filtering (area, site, limit)
- Single-selection conversation detail view
- Bulk delete with confirmation
- Comprehensive error handling

## Setup

### Prerequisites

- Python 3.11+
- Conda environment: `tarasa`
- GCS service account credentials with "Storage Object Admin" role
- Access to GCS bucket: `tarasa_tourist_bot_content`

### Installation

1. **Activate conda environment:**
   ```bash
   conda activate tarasa
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

   Note: Streamlit should already be in requirements.txt. If not, add it:
   ```bash
   pip install streamlit
   ```

3. **Configure GCS credentials:**

   Copy the example secrets file:
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```

   Edit `.streamlit/secrets.toml` and add your GCS service account credentials under `[gcs_credentials]`. See the example file for the required format.

4. **Verify configuration:**

   Ensure `config.yaml` has the correct GCS bucket name:
   ```yaml
   gcs_bucket_name: tarasa_tourist_bot_content
   ```

## Running Locally

Start the admin UI:

```bash
streamlit run admin_ui/app.py --server.port 8502
```

Open your browser to: http://localhost:8502

**Note:** The main Q&A app runs on port 8501, so the admin UI uses 8502 to avoid conflicts.

## Usage Guide

### Home Page

Displays quick stats:
- **Locations**: Number of area/site combinations with uploaded content
- **Conversations**: Total conversations in the system
- **Images**: Total images extracted from documents

Use the sidebar to navigate between pages.

### Upload Content Page

1. **Select Location:**
   - Enter `area` (e.g., `hefer_valley`)
   - Enter `site` (e.g., `agamon_hefer`)

2. **Choose Files:**
   - Drag and drop or browse for files
   - Supported formats: DOCX, PDF, TXT, MD
   - Multiple files can be uploaded at once

3. **Options:**
   - Check "Force re-upload" to re-process already uploaded files

4. **Upload:**
   - Click "Upload" button
   - Monitor progress bar
   - View results: uploaded count, images extracted, topics generated

**Existing Locations** section shows all area/site combinations currently in the system.

### View Content Page

Browse uploaded content organized by area and site.

For each site, view:
- **Files**: Number of uploaded documents
- **Images**: Number of extracted images
- **Topics**: Number of generated topics
- **Last Updated**: Timestamp of last upload

Expand the images section to see:
- Document name
- Image captions
- Context snippets (text before/after image)

### Conversations Page

1. **Filters:**
   - Area: Filter by location area
   - Site: Filter by location site
   - Limit: Maximum conversations to load (default: 100)

2. **Conversation List:**
   - Shows conversation ID, location, message count, updated timestamp
   - Check boxes to select conversations for bulk operations
   - Click "View" to see conversation details below

3. **Conversation Details:**
   - Full message history (user and assistant messages)
   - Citations displayed in expandable sections
   - Images displayed in expandable sections
   - Close button to hide details
   - Delete button to remove conversation

4. **Bulk Operations:**
   - Select multiple conversations using checkboxes
   - Click "Delete X conversations" button
   - Click again to confirm (two-click pattern prevents accidents)

## Architecture

### Direct GCS Access

The admin UI uses direct GCS access instead of API endpoints:

- **Advantages:**
  - No additional backend deployment needed
  - Simpler architecture
  - Faster development
  - Direct access to all GCS features

- **Requirements:**
  - GCS service account credentials
  - Runs on authenticated machines only
  - Not suitable for public access

### Components

```
admin_ui/
├── app.py                           # Main entry point, home page
├── upload_helper.py                 # Upload manager (wraps CLI uploader)
└── pages/
    ├── 1_📤_Upload_Content.py      # File upload interface
    ├── 2_📁_View_Content.py        # Content browser
    └── 3_💬_Conversations.py       # Conversation management
```

### Backend Integration

Reuses existing backend modules:

- `backend/gcs_storage.py` - GCS operations
- `backend/conversation_storage/conversations.py` - Conversation management
- `backend/store_registry.py` - Content metadata
- `backend/image_registry.py` - Image metadata
- `gemini/main_upload.py` - Upload logic (via subprocess wrapper)

## Deployment (Optional)

### Cloud Run Deployment

The admin UI can be deployed to Cloud Run for remote access:

```bash
cd admin_ui

gcloud run deploy tourism-admin-ui \
  --source . \
  --region me-west1 \
  --platform managed \
  --service-account tourism-rag-backend@project.iam.gserviceaccount.com \
  --no-allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --timeout 600
```

**Important:** Use `--no-allow-unauthenticated` to restrict access to authenticated users only.

### Environment Variables (Cloud Run)

Set GCS bucket name if different from default:

```bash
gcloud run services update tourism-admin-ui \
  --region me-west1 \
  --set-env-vars GCS_BUCKET=tarasa_tourist_bot_content
```

Note: Service account credentials are provided via the attached service account, not environment variables.

## Troubleshooting

### Authentication Failed

**Error:** "Authentication failed: ..."

**Solution:**
1. Verify `.streamlit/secrets.toml` exists and has `[gcs_credentials]` section
2. Check that service account has "Storage Object Admin" role
3. Verify GCS bucket name matches `config.yaml`
4. Ensure credentials JSON is valid

### Upload Not Working

**Error:** Upload fails or shows 0 uploaded files

**Solution:**
1. Check that area/site are entered correctly (no spaces, lowercase recommended)
2. Verify file format is supported (DOCX, PDF, TXT, MD)
3. Check file size (< 50 MB)
4. Review error messages in expandable "View Errors" section

### Conversations Not Loading

**Error:** "No conversations found" or empty list

**Solution:**
1. Check filters - try clearing area/site filters
2. Increase limit (default: 100)
3. Verify GCS bucket has conversations in `conversations/` prefix
4. Check that conversations use expected JSON format

### Page Not Responding

**Issue:** Page hangs or loads slowly

**Solution:**
1. Reduce limit on Conversations page (try 50 instead of 1000)
2. Apply area/site filters to reduce dataset size
3. Check GCS bucket region (me-west1 is closest)
4. Clear browser cache and refresh

### Stats Show "Error"

**Error:** Metrics display "Error" instead of count

**Solution:**
1. Check error caption below metric (shows first 50 chars of error)
2. Verify GCS credentials have read permissions
3. Check registry files exist in GCS:
   - `metadata/store_registry.json`
   - `metadata/image_registry.json`
4. Review application logs for detailed errors

## Testing

### Unit Tests

Run backend extension tests:

```bash
pytest tests/admin_ui/test_conversation_store_extensions.py -v
```

This tests the new ConversationStore methods:
- `list_all_conversations()` with filters
- `delete_conversations_bulk()`
- `get_conversations_stats()`

### Manual Testing

1. **Upload Test:**
   - Upload a sample DOCX file to new location
   - Verify File Search Store updated
   - Check images extracted and displayed
   - Verify topics generated

2. **Content Browsing:**
   - Navigate to View Content page
   - Verify all metrics accurate
   - Check images display correctly

3. **Conversation Management:**
   - Filter conversations by area/site
   - View conversation details
   - Delete single conversation
   - Bulk delete multiple conversations

## Limitations

Current MVP does not include:

- Real-time updates (manual refresh required)
- Conversation search (full-text in messages)
- Export functionality (CSV, JSON download)
- Content deletion (upload only)
- User roles and permissions
- Advanced authentication (password, IP whitelist)
- Mobile-responsive optimizations

These features can be added in future iterations based on user needs.

## Contributing

When adding new features:

1. Update this README with usage instructions
2. Add unit tests for backend logic
3. Test manually with production-like data
4. Follow existing code patterns (session state management, error handling)
5. Update `.streamlit/secrets.toml.example` if new credentials needed

## Support

For issues or questions:

1. Check troubleshooting section above
2. Review application logs (Streamlit console output)
3. Verify GCS permissions and bucket access
4. Check GitHub issues for known problems

## License

Same as main project.
