"""
Item pipelines for Sapir scraper.

Currently, file saving is handled directly in the spider for simplicity.
This file is kept for potential future pipeline additions.
"""


class SapirScraperPipeline:
    """Base pipeline for sapir_scraper."""

    def process_item(self, item, spider):
        """Process scraped items."""
        return item
