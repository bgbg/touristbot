# Sapir Academic College Web Scraper

Scrapy-based web scraper for downloading content from [sapir.ac.il](https://www.sapir.ac.il/).

## Features

- **Polite crawling**: Respects robots.txt, implements delays and conservative concurrency
- **Domain restricted**: Only downloads from sapir.ac.il domain
- **File type filtering**: Downloads HTML pages, PDFs, and images (skips CSS, JS, etc.)
- **Exponential backoff**: Automatic retry with randomized exponential delays (0-3s max)
- **HTTP caching**: Avoids re-downloading previously scraped content
- **Hebrew support**: Full UTF-8 encoding support for Hebrew content
- **Resumable**: Can stop and restart without losing progress

## Installation

From the project root:

```bash
pip install -r requirements.txt
```

This installs Scrapy and all dependencies.

## Usage

### Basic Usage

Run the scraper from the project root:

```bash
python scraper/run_sapir_scraper.py
```

### Command Line Options

```bash
# Resume from last run (uses HTTP cache)
python scraper/run_sapir_scraper.py --resume

# Clear cache and start fresh
python scraper/run_sapir_scraper.py --clear-cache

# Enable debug logging
python scraper/run_sapir_scraper.py --debug
```

### Stopping and Resuming

- Press `Ctrl+C` to stop the scraper at any time
- Run again to resume - HTTP cache ensures no duplicate downloads
- To start completely fresh, use `--clear-cache`

## Output Structure

Downloaded files are organized under `data/sapir/`:

```
data/sapir/
├── html/           # HTML pages
├── pdf/            # PDF documents
├── images/         # Images (JPG, PNG, GIF, WebP)
└── .httpcache/     # Scrapy HTTP cache (internal)
```

### Filename Convention

Files are named using the pattern: `{hash}_{sanitized-name}.{ext}`

- `hash`: 12-character MD5 hash of the URL (ensures uniqueness)
- `sanitized-name`: Cleaned original filename (alphanumeric + hyphens)
- `ext`: Original file extension

Example: `a3f2b8c1d4e5_academic-programs.html`

## Configuration

### Crawl Settings

Configured in [sapir_scraper/settings.py](sapir_scraper/settings.py):

- **Concurrent requests**: 4 (conservative)
- **Download delay**: 0.1s base delay between requests
- **Max retries**: 4 attempts with exponential backoff
- **Retry delays**: 0-0.2s → 0-0.4s → 0-0.8s → 0-1.6s (max 3s)
- **Download timeout**: 30 seconds
- **Max file size**: 50MB

### File Types

**Downloaded**:
- HTML/HTM pages
- PDF documents
- Images: JPG, JPEG, PNG, GIF, WebP

**Skipped**:
- CSS stylesheets
- JavaScript files
- Fonts (WOFF, TTF, etc.)
- Videos (MP4, AVI, etc.)
- Archives (ZIP, TAR, etc.)

## Monitoring Progress

The scraper logs provide real-time progress information:

```
INFO: Saved html: a3f2b8c1d4e5_index.html (45231 bytes)
INFO: Saved pdf: b4c3d2e1f0a9_syllabus.pdf (234567 bytes)
INFO: Saved images: c5d4e3f2a1b0_campus.jpg (123456 bytes)
```

At the end, Scrapy statistics show:

- Total requests made
- Items scraped
- Retry counts
- Download speeds
- Memory usage

## Testing

Run the test suite:

```bash
pytest scraper/tests/
```

Tests verify:
- Domain restrictions work correctly
- File type filtering accepts/rejects correct types
- Exponential backoff calculations
- UTF-8 Hebrew text handling

## Architecture

### Components

1. **SapirSpider** ([spiders/sapir_spider.py](sapir_scraper/spiders/sapir_spider.py))
   - CrawlSpider with link extraction rules
   - Domain and file type filtering
   - Direct file saving with organized output

2. **ExponentialBackoffRetryMiddleware** ([middlewares.py](sapir_scraper/middlewares.py))
   - Custom retry logic with exponential delays
   - Randomization to avoid thundering herd
   - Maximum delay cap at 3 seconds

3. **Settings** ([settings.py](sapir_scraper/settings.py))
   - HTTP cache configuration
   - Concurrency and delay settings
   - UTF-8 encoding for Hebrew

4. **CLI Runner** ([run_sapir_scraper.py](run_sapir_scraper.py))
   - Command-line interface
   - Cache management
   - User-friendly output

### Why Scrapy?

Scrapy provides out-of-the-box:
- Asynchronous request handling (Twisted-based)
- Robust middleware system
- HTTP caching
- robots.txt compliance
- Link extraction and crawling
- Comprehensive statistics

Much more suitable for site-wide scraping than requests/BeautifulSoup.

## Troubleshooting

### Scraper stops with connection errors

The exponential backoff middleware will automatically retry failed requests. If you see persistent errors:

1. Check your internet connection
2. Verify sapir.ac.il is accessible
3. Review robots.txt compliance: https://www.sapir.ac.il/robots.txt

### Memory usage is high

Adjust settings in `settings.py`:

```python
MEMUSAGE_LIMIT_MB = 256  # Lower limit
CONCURRENT_REQUESTS = 2   # Reduce concurrency
```

### Want to scrape faster

Increase concurrency (but be respectful):

```python
CONCURRENT_REQUESTS = 8
DOWNLOAD_DELAY = 0.05
```

### Hebrew text appears garbled

Check that `FEED_EXPORT_ENCODING = 'utf-8'` is set in settings.py (it should be by default).

## Ethical Considerations

This scraper is configured for **polite, respectful crawling**:

- ✓ Obeys robots.txt directives
- ✓ Implements delays between requests
- ✓ Uses conservative concurrency
- ✓ Identifies itself via User-Agent
- ✓ Implements exponential backoff on errors

**Always ensure you have permission to scrape a website and comply with their terms of service.**

## License

Part of the TARASA Tourism RAG project.
