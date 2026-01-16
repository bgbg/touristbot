#!/usr/bin/env python3
"""
CLI runner for Sapir scraper.

Usage:
    python scraper/run_sapir_scraper.py              # Run scraper with HTTP cache
    python scraper/run_sapir_scraper.py --clear-cache # Clear cache and start fresh
    python scraper/run_sapir_scraper.py --resume      # Alias for default (use cache)

Examples:
    # First run - downloads everything
    python scraper/run_sapir_scraper.py

    # Subsequent runs - uses cache, only downloads new content
    python scraper/run_sapir_scraper.py

    # Force re-download everything
    python scraper/run_sapir_scraper.py --clear-cache
"""
import sys
import os
import argparse
import shutil

# Add scraper directory to path before imports
scraper_dir = os.path.dirname(os.path.abspath(__file__))
if scraper_dir not in sys.path:
    sys.path.insert(0, scraper_dir)

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

# Import spider directly
from sapir_scraper.spiders.sapir_spider import SapirSpider


def clear_cache(cache_dir='data/sapir/.httpcache'):
    """Clear HTTP cache directory."""
    if os.path.exists(cache_dir):
        print(f"Clearing cache: {cache_dir}")
        shutil.rmtree(cache_dir)
        print("Cache cleared.")
    else:
        print(f"No cache found at {cache_dir}")


def main():
    """Run the Sapir scraper."""
    parser = argparse.ArgumentParser(
        description='Scrape sapir.ac.il website',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--clear-cache',
        action='store_true',
        help='Clear HTTP cache before starting (forces re-download)'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume scraping (uses cache, default behavior)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )

    args = parser.parse_args()

    # Clear cache if requested
    if args.clear_cache:
        clear_cache()

    # Set SCRAPY_SETTINGS_MODULE environment variable
    os.environ.setdefault('SCRAPY_SETTINGS_MODULE', 'sapir_scraper.settings')

    # Load Scrapy settings
    settings = get_project_settings()

    # Override log level if debug mode
    if args.debug:
        settings.set('LOG_LEVEL', 'DEBUG')

    # Create output directories
    os.makedirs('data/sapir/html', exist_ok=True)
    os.makedirs('data/sapir/pdf', exist_ok=True)
    os.makedirs('data/sapir/images', exist_ok=True)

    print("=" * 60)
    print("Sapir Academic College Web Scraper")
    print("=" * 60)
    print(f"Target: https://www.sapir.ac.il/")
    print(f"Output: data/sapir/")
    print(f"Cache: {'ENABLED (resume mode)' if not args.clear_cache else 'DISABLED (fresh start)'}")
    print("=" * 60)
    print("\nStarting scraper...")
    print("(Press Ctrl+C to stop)\n")

    # Create crawler process and run spider
    process = CrawlerProcess(settings)
    process.crawl(SapirSpider)  # Use spider class directly
    process.start()

    print("\n" + "=" * 60)
    print("Scraping completed!")
    print("=" * 60)
    print(f"\nDownloaded files saved to:")
    print(f"  - HTML pages: data/sapir/html/")
    print(f"  - PDF files:  data/sapir/pdf/")
    print(f"  - Images:     data/sapir/images/")
    print(f"\nHTTP cache: data/sapir/.httpcache/")


if __name__ == '__main__':
    main()
