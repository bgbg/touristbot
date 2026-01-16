"""
Scrapy settings for sapir_scraper project.

Configured for polite, respectful crawling of sapir.ac.il with:
- Conservative concurrency (4 concurrent requests)
- HTTP caching to avoid re-downloads
- Exponential backoff retry logic
- Hebrew UTF-8 support
"""

BOT_NAME = 'sapir_scraper'

SPIDER_MODULES = ['sapir_scraper.spiders']
NEWSPIDER_MODULE = 'sapir_scraper.spiders'

# Crawl responsibly by identifying yourself (and your website) on the user-agent
USER_AGENT = 'SapirBot/1.0 (+https://github.com/yourorg/sapir-scraper; Academic Research)'

# Obey robots.txt rules
ROBOTSTXT_OBEY = True

# Configure maximum concurrent requests (conservative for polite crawling)
CONCURRENT_REQUESTS = 4

# Configure a delay for requests for the same website (default: 0)
DOWNLOAD_DELAY = 0.1  # 100ms base delay between requests

# The download delay setting will honor only one of:
CONCURRENT_REQUESTS_PER_DOMAIN = 4
# CONCURRENT_REQUESTS_PER_IP = 4

# Disable cookies (not needed for public academic content)
COOKIES_ENABLED = False

# Disable Telnet Console (enabled by default)
TELNETCONSOLE_ENABLED = False

# Override the default request headers:
DEFAULT_REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'he,en-US,en;q=0.9',  # Hebrew + English
    'Accept-Encoding': 'gzip, deflate',
}

# Enable or disable spider middlewares
SPIDER_MIDDLEWARES = {
    'sapir_scraper.middlewares.SapirScraperSpiderMiddleware': 543,
}

# Enable or disable downloader middlewares
DOWNLOADER_MIDDLEWARES = {
    'sapir_scraper.middlewares.SapirScraperDownloaderMiddleware': 543,
    # Replace default RetryMiddleware with our exponential backoff version
    'scrapy.downloadermiddlewares.retry.RetryMiddleware': None,
    'sapir_scraper.middlewares.ExponentialBackoffRetryMiddleware': 550,
}

# Enable or disable extensions
EXTENSIONS = {
    'scrapy.extensions.telnet.TelnetConsole': None,
}

# Configure item pipelines
ITEM_PIPELINES = {
    'sapir_scraper.pipelines.SapirScraperPipeline': 300,
}

# Enable and configure HTTP caching
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 0  # Never expire (persistent cache)
HTTPCACHE_DIR = 'data/sapir/.httpcache'
HTTPCACHE_IGNORE_HTTP_CODES = []
HTTPCACHE_STORAGE = 'scrapy.extensions.httpcache.FilesystemCacheStorage'

# Retry settings
RETRY_ENABLED = True
RETRY_TIMES = 4  # Maximum 4 retry attempts
RETRY_HTTP_CODES = [500, 502, 503, 504, 429, 408]  # Status codes to retry

# AutoThrottle settings (adaptive throttling)
# AUTOTHROTTLE_ENABLED = True
# AUTOTHROTTLE_START_DELAY = 0.1
# AUTOTHROTTLE_MAX_DELAY = 3.0
# AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0

# UTF-8 encoding for Hebrew content
FEED_EXPORT_ENCODING = 'utf-8'

# Logging
LOG_LEVEL = 'INFO'  # Can be DEBUG for more verbose output
LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
LOG_DATEFORMAT = '%Y-%m-%d %H:%M:%S'

# Depth limit (optional, remove to crawl entire site)
# DEPTH_LIMIT = 3

# Download timeout
DOWNLOAD_TIMEOUT = 30  # 30 seconds

# Disable redirects for some status codes
# REDIRECT_ENABLED = True
# REDIRECT_MAX_TIMES = 10

# Configure maximum file size (50MB)
DOWNLOAD_MAXSIZE = 50 * 1024 * 1024  # 50MB
DOWNLOAD_WARNSIZE = 10 * 1024 * 1024  # Warn at 10MB

# Memory usage
MEMUSAGE_ENABLED = True
MEMUSAGE_LIMIT_MB = 512  # Stop if memory exceeds 512MB
MEMUSAGE_WARNING_MB = 256  # Warn at 256MB

# Scrapy statistics
STATS_DUMP = True
