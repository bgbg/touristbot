"""
Scrapy spider for sapir.ac.il website.

Downloads HTML pages, PDFs, and images from Sapir Academic College website
while respecting robots.txt and implementing polite crawling practices.
"""
import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
import os
from urllib.parse import urlparse, unquote
import hashlib


class SapirSpider(CrawlSpider):
    name = 'sapir'
    allowed_domains = ['sapir.ac.il']
    start_urls = [
        'https://www.sapir.ac.il/',
        'https://brc.sapir.ac.il/',  # BRC subdomain (research center)
        'https://it.sapir.ac.il/',   # IT subdomain
    ]

    # File types we want to download
    ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.html', '.htm'}

    # Skip these file types in link extraction (but NOT pdf/images)
    DENIED_EXTENSIONS = [
        r'\.css$', r'\.js$', r'\.json$', r'\.xml$', r'\.svg$',
        r'\.woff$', r'\.woff2$', r'\.ttf$', r'\.eot$', r'\.otf$',
        r'\.ico$', r'\.mp4$', r'\.mp3$', r'\.avi$', r'\.mov$',
        r'\.zip$', r'\.tar$', r'\.gz$', r'\.rar$'
    ]

    rules = (
        # Rule 1: Download PDFs (highest priority - don't use deny_extensions)
        Rule(
            LinkExtractor(
                allow_domains=['sapir.ac.il'],
                allow=(r'\.pdf$',),  # Explicitly allow PDFs
                deny_extensions=[],  # Don't deny anything for this rule
                canonicalize=True,
                unique=True
            ),
            callback='parse_item',
            follow=False  # Don't follow from PDFs
        ),
        # Rule 2: Download images
        Rule(
            LinkExtractor(
                allow_domains=['sapir.ac.il'],
                allow=(r'\.(jpg|jpeg|png|gif|webp)$',),
                deny_extensions=[],  # Don't deny anything for this rule
                canonicalize=True,
                unique=True
            ),
            callback='parse_item',
            follow=False
        ),
        # Rule 3: Follow HTML links (excluding already handled files)
        Rule(
            LinkExtractor(
                allow_domains=['sapir.ac.il'],
                deny=(r'\.(pdf|jpg|jpeg|png|gif|webp|css|js|json|xml|svg|woff|woff2|ttf|eot|otf|ico|mp4|mp3|avi|mov|zip|tar|gz|rar)$',),
                canonicalize=True,
                unique=True
            ),
            callback='parse_item',
            follow=True  # Continue following HTML pages
        ),
    )

    custom_settings = {
        # UTF-8 encoding for Hebrew content
        'FEED_EXPORT_ENCODING': 'utf-8',
    }

    def __init__(self, *args, **kwargs):
        super(SapirSpider, self).__init__(*args, **kwargs)
        # Create output directories
        self.output_base = os.path.join('data', 'sapir')
        os.makedirs(os.path.join(self.output_base, 'html'), exist_ok=True)
        os.makedirs(os.path.join(self.output_base, 'pdf'), exist_ok=True)
        os.makedirs(os.path.join(self.output_base, 'images'), exist_ok=True)

    def parse_start_url(self, response):
        """Parse the start URL."""
        return self.parse_item(response)

    def parse_item(self, response):
        """Parse and save downloaded content."""
        url = response.url
        content_type = response.headers.get('Content-Type', b'').decode('utf-8', errors='ignore').lower()

        # Determine file type and save location
        parsed_url = urlparse(url)
        path = unquote(parsed_url.path)

        # Generate safe filename using URL hash + original extension
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()[:12]

        # Determine file extension and category
        if path.lower().endswith('.pdf') or 'application/pdf' in content_type:
            category = 'pdf'
            extension = '.pdf'
        elif any(path.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
            category = 'images'
            extension = os.path.splitext(path)[1].lower()
        elif 'image/' in content_type:
            category = 'images'
            # Try to get extension from content type
            if 'jpeg' in content_type:
                extension = '.jpg'
            elif 'png' in content_type:
                extension = '.png'
            elif 'gif' in content_type:
                extension = '.gif'
            elif 'webp' in content_type:
                extension = '.webp'
            else:
                extension = '.jpg'  # default
        else:
            # HTML or other text content
            category = 'html'
            extension = '.html'

        # Create safe filename: hash_original-name.ext
        original_name = os.path.basename(path) or 'index'
        # Remove extension from original name if present
        original_name = os.path.splitext(original_name)[0]
        # Sanitize filename
        safe_name = "".join(c for c in original_name if c.isalnum() or c in ('-', '_'))[:50]
        filename = f"{url_hash}_{safe_name}{extension}"

        filepath = os.path.join(self.output_base, category, filename)

        # Save the file
        with open(filepath, 'wb') as f:
            f.write(response.body)

        self.logger.info(f'Saved {category}: {filename} ({len(response.body)} bytes)')

        # Return item for stats
        yield {
            'url': url,
            'category': category,
            'filename': filename,
            'size': len(response.body),
            'status': response.status
        }
