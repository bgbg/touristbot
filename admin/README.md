# Tourism RAG Admin Panel

Streamlit-based admin panel for managing and monitoring the Tourism RAG system.

## Features

### 📊 Query Logs Explorer (Implemented)
- **Direct GCS access**: Reads query logs directly from GCS (no backend API needed)
- **Date selection**: Single date or date range (up to 30 days)
- **Filtering**: Filter by area, site, error status, and text search
- **Statistics**: View metrics like average latency, error rate, citations, and images
- **Display modes**: Table view, detailed cards, or raw JSON
- **Real-time insights**: Monitor query performance, image relevance, and LLM behavior

### 💬 Conversations (Coming Soon)
- Browse active conversations
- View conversation history
- Delete old/expired conversations
- Export conversations to CSV/JSON
- Search by phone number or text

### 🔍 System Info (Coming Soon)
- GCS bucket usage statistics
- Store registry contents
- Image registry contents
- Upload tracking status
- File Search Store information

## Prerequisites

1. **GCS Bucket**: Ensure `tarasa_tourist_bot_content` bucket exists and is accessible
2. **Application Default Credentials (ADC)**: The app uses ADC for GCS authentication
   ```bash
   # Authenticate with your Google Cloud account
   gcloud auth application-default login
   ```
3. **Secrets Configuration**: Update `.streamlit/secrets.toml` with:
   ```toml
   GCS_BUCKET = "tarasa_tourist_bot_content"
   ```

## Running the Admin Panel

### Local Development

```bash
# Activate conda environment
conda activate tarasa

# Run admin panel on port 8502
streamlit run admin/app.py --server.port 8502

# Open in browser
# http://localhost:8502
```

### Alternative Ports

If port 8502 is in use, choose a different port:
```bash
streamlit run admin/app.py --server.port 8503
```

## Query Logs

### Log Format
Logs are stored in GCS as JSONL files: `query_logs/{YYYY-MM-DD}.jsonl`

Each log entry contains:
```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "conversation_id": "uuid-string",
  "area": "hefer_valley",
  "site": "agamon_hefer",
  "query": "שאלה של המשתמש",
  "response_text": "תשובת הבוט",
  "response_length": 150,
  "latency_ms": 1234.56,
  "citations_count": 3,
  "images_count": 2,
  "model_name": "gemini-2.5-flash",
  "temperature": 0.6,
  "error": null,
  "should_include_images": true,
  "image_relevance": [...],
  "citations": [...],
  "images": [...]
}
```

### Using the Logs Explorer

1. **Select Date**:
   - Use date picker to select a specific date
   - Enable "Date Range" checkbox to query multiple days
   - Quick actions: "Today" and "Yesterday" buttons

2. **Apply Filters**:
   - **Area/Site**: Filter by location
   - **Errors**: Show all, errors only, or success only
   - **Search**: Find queries containing specific text

3. **View Statistics**:
   - Total queries
   - Average latency
   - Error rate
   - Average citations
   - Images shown percentage

4. **Browse Logs**:
   - **Table**: Compact overview with key fields
   - **Detailed Cards**: Expandable entries with full query/response text, citations, and image metadata
   - **Raw JSON**: Complete log data in JSON format

### Common Use Cases

**Debug slow queries:**
```
1. Select date range
2. Sort by latency in table view
3. Expand detailed card to see full query/response
```

**Investigate errors:**
```
1. Select "Errors Only" filter
2. Review error messages in detailed view
3. Check model/temperature configuration
```

**Analyze image relevance:**
```
1. View detailed cards
2. Check "Image Relevance Scores" section
3. Compare relevance scores with actual images shown
```

**Monitor specific location:**
```
1. Filter by area and site
2. View statistics for that location
3. Review typical query patterns
```

## Architecture

### Direct GCS Access
The admin panel bypasses the backend API and reads directly from GCS:

```
Admin Panel (Streamlit)
    ↓
backend/gcs_storage.py (GCS client)
    ↓
backend/query_logging/query_logger.py (JSONL parser)
    ↓
Google Cloud Storage (tarasa_tourist_bot_content bucket)
```

**Benefits:**
- No backend API dependency
- Faster access to historical data
- Full control over data processing
- Can analyze large date ranges efficiently

### Caching
- **Resource caching**: Storage backend and query logger are singletons
- **Data caching**: Logs cached for 5 minutes to reduce GCS reads
- **Cache control**: Use "Clear Cache" button in sidebar to refresh data

## Troubleshooting

### "Missing `GCS_BUCKET` in .streamlit/secrets.toml"
**Solution**: Add `GCS_BUCKET = "tarasa_tourist_bot_content"` to `.streamlit/secrets.toml`

### "Permission denied" or "403 Forbidden"
**Solution**: Ensure you're authenticated with ADC:
```bash
gcloud auth application-default login
```

### "No logs found"
**Possible causes:**
- No queries were made on that date
- Backend is not logging to GCS (check backend configuration)
- GCS bucket path is incorrect (should be `query_logs/YYYY-MM-DD.jsonl`)

### Slow performance with large date ranges
**Solution**:
- Use smaller date ranges (7 days or less)
- Apply filters before viewing details
- Use table view instead of detailed cards
- Clear cache if data feels stale

## Development

### Adding New Tabs

To add a new admin feature:

1. Add navigation option in sidebar:
   ```python
   selected_tab = st.sidebar.radio(
       "Navigation",
       ["📊 Query Logs", "💬 Conversations", "🔍 System Info", "🆕 New Feature"],
       index=0
   )
   ```

2. Add tab implementation:
   ```python
   elif selected_tab == "🆕 New Feature":
       st.title("🆕 New Feature")
       # Implementation here
   ```

### Using Backend Modules

The admin panel can import any backend module:

```python
from backend.gcs_storage import GCSStorage
from backend.query_logging.query_logger import QueryLogger
from backend.conversation_storage.conversations import ConversationStore
from backend.store_registry import StoreRegistry
from backend.image_registry import ImageRegistry
```

## Security Notes

- **No public access**: Admin panel is local-only (localhost)
- **GCS credentials**: Uses Application Default Credentials (never committed to git)
- **Secrets management**: Secrets stored in `.streamlit/secrets.toml` (gitignored)
- **Read-only operations**: Current implementation only reads from GCS (no writes)

## Future Enhancements

- [ ] Conversation management (view, delete, export)
- [ ] System monitoring dashboard
- [ ] Store registry viewer
- [ ] Image registry browser
- [ ] Real-time log streaming
- [ ] Custom analytics queries
- [ ] Export filtered logs to CSV
- [ ] Grafana-style time series charts
- [ ] Alert configuration for errors/latency
