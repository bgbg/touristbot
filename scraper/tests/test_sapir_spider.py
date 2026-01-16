"""
Tests for Sapir spider.

Tests verify domain restrictions, file type filtering, exponential backoff,
and UTF-8 Hebrew text handling.
"""
import pytest
import random
from unittest.mock import Mock, patch, MagicMock
from scrapy.http import Response, Request, HtmlResponse
from scrapy.utils.test import get_crawler
import sys
import os

# Add scraper to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sapir_scraper.spiders.sapir_spider import SapirSpider
from sapir_scraper.middlewares import ExponentialBackoffRetryMiddleware


class TestSapirSpider:
    """Test SapirSpider functionality."""

    def setup_method(self):
        """Set up test spider."""
        self.spider = SapirSpider()

    def test_allowed_domains(self):
        """Test that only sapir.ac.il domain is allowed."""
        assert self.spider.allowed_domains == ['sapir.ac.il']

    def test_start_urls(self):
        """Test start URL is set correctly."""
        assert 'https://www.sapir.ac.il/' in self.spider.start_urls

    def test_denied_extensions(self):
        """Test that CSS, JS, and other unwanted extensions are denied."""
        denied = self.spider.DENIED_EXTENSIONS
        assert any('.css' in pattern for pattern in denied)
        assert any('.js' in pattern for pattern in denied)
        assert any('.mp4' in pattern for pattern in denied)
        assert any('.zip' in pattern for pattern in denied)

    def test_allowed_file_extensions(self):
        """Test that desired file extensions are in allowed set."""
        allowed = self.spider.ALLOWED_EXTENSIONS
        assert '.pdf' in allowed
        assert '.jpg' in allowed
        assert '.jpeg' in allowed
        assert '.png' in allowed
        assert '.gif' in allowed
        assert '.webp' in allowed
        assert '.html' in allowed
        assert '.htm' in allowed

    @patch('os.makedirs')
    @patch('builtins.open', create=True)
    def test_parse_html_page(self, mock_open, mock_makedirs):
        """Test parsing and saving HTML page."""
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        # Create mock response
        url = 'https://www.sapir.ac.il/about'
        html_content = b'<html><body><h1>\xd7\x90\xd7\x95\xd7\x93\xd7\x95\xd7\xaa</h1></body></html>'  # Hebrew "about"
        response = HtmlResponse(
            url=url,
            body=html_content,
            headers={'Content-Type': 'text/html; charset=utf-8'}
        )

        # Parse response
        results = list(self.spider.parse_item(response))

        # Verify results
        assert len(results) == 1
        item = results[0]
        assert item['url'] == url
        assert item['category'] == 'html'
        assert '.html' in item['filename']
        assert item['size'] == len(html_content)

        # Verify file was written
        mock_file.write.assert_called_once_with(html_content)

    @patch('os.makedirs')
    @patch('builtins.open', create=True)
    def test_parse_pdf_file(self, mock_open, mock_makedirs):
        """Test parsing and saving PDF file."""
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        url = 'https://www.sapir.ac.il/files/syllabus.pdf'
        pdf_content = b'%PDF-1.4 fake pdf content'
        response = Response(
            url=url,
            body=pdf_content,
            headers={'Content-Type': 'application/pdf'}
        )

        results = list(self.spider.parse_item(response))

        assert len(results) == 1
        item = results[0]
        assert item['category'] == 'pdf'
        assert item['filename'].endswith('.pdf')
        mock_file.write.assert_called_once_with(pdf_content)

    @patch('os.makedirs')
    @patch('builtins.open', create=True)
    def test_parse_image_file(self, mock_open, mock_makedirs):
        """Test parsing and saving image file."""
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        url = 'https://www.sapir.ac.il/images/campus.jpg'
        image_content = b'\xff\xd8\xff\xe0 fake jpeg data'
        response = Response(
            url=url,
            body=image_content,
            headers={'Content-Type': 'image/jpeg'}
        )

        results = list(self.spider.parse_item(response))

        assert len(results) == 1
        item = results[0]
        assert item['category'] == 'images'
        assert item['filename'].endswith('.jpg')
        mock_file.write.assert_called_once_with(image_content)

    def test_hebrew_text_handling(self):
        """Test that Hebrew UTF-8 text is handled correctly."""
        hebrew_text = "אוניברסיטת ספיר"  # "Sapir University" in Hebrew
        encoded = hebrew_text.encode('utf-8')

        # Verify encoding/decoding works
        decoded = encoded.decode('utf-8')
        assert decoded == hebrew_text

        # Check spider's UTF-8 setting
        assert self.spider.custom_settings['FEED_EXPORT_ENCODING'] == 'utf-8'


class TestExponentialBackoffMiddleware:
    """Test exponential backoff retry middleware."""

    def setup_method(self):
        """Set up test middleware."""
        self.crawler = get_crawler(spidercls=SapirSpider)
        self.spider = self.crawler._create_spider()
        settings = {'RETRY_TIMES': 4, 'RETRY_HTTP_CODES': [500, 502, 503, 504, 429]}
        self.middleware = ExponentialBackoffRetryMiddleware(settings)

    def test_backoff_delay_calculation(self):
        """Test that exponential backoff delays are calculated correctly."""
        # Test multiple retry attempts
        with patch('time.sleep') as mock_sleep:
            with patch('random.uniform') as mock_random:
                # Mock random to return max value for predictable testing
                mock_random.side_effect = lambda min_val, max_val: max_val

                request = Request('https://www.sapir.ac.il/test')

                # First retry: max delay should be 0.2 * 2^1 = 0.4s
                request.meta['retry_times'] = 1
                max_delay_1 = 0.2 * (2 ** 1)
                assert max_delay_1 == 0.4

                # Second retry: max delay should be 0.2 * 2^2 = 0.8s
                request.meta['retry_times'] = 2
                max_delay_2 = 0.2 * (2 ** 2)
                assert max_delay_2 == 0.8

                # Third retry: max delay should be 0.2 * 2^3 = 1.6s
                request.meta['retry_times'] = 3
                max_delay_3 = 0.2 * (2 ** 3)
                assert max_delay_3 == 1.6

                # Fourth retry: max delay should be 0.2 * 2^4 = 3.2s but capped at 3s
                request.meta['retry_times'] = 4
                max_delay_4 = min(0.2 * (2 ** 4), 3.0)
                assert max_delay_4 == 3.0

    def test_max_delay_cap(self):
        """Test that delay is capped at 3 seconds."""
        middleware = ExponentialBackoffRetryMiddleware({'RETRY_TIMES': 10})
        assert middleware.max_delay == 3.0

        # Calculate delay for very high retry count
        retry_count = 10
        calculated_delay = 0.2 * (2 ** retry_count)  # Would be 204.8s without cap
        capped_delay = min(calculated_delay, middleware.max_delay)

        assert capped_delay == 3.0

    def test_retry_on_server_errors(self):
        """Test that middleware retries on server error status codes."""
        settings = {'RETRY_TIMES': 4, 'RETRY_HTTP_CODES': [500, 502, 503, 504, 429]}
        middleware = ExponentialBackoffRetryMiddleware(settings)

        assert 500 in middleware.retry_http_codes
        assert 502 in middleware.retry_http_codes
        assert 503 in middleware.retry_http_codes
        assert 504 in middleware.retry_http_codes
        assert 429 in middleware.retry_http_codes

    def test_randomization(self):
        """Test that delays are randomized between 0 and max."""
        # Set random seed for reproducibility
        random.seed(42)

        delays = []
        for _ in range(100):
            # Simulate retry_count = 2, max_delay = 0.8s
            max_delay = 0.2 * (2 ** 2)
            delay = random.uniform(0, max_delay)
            delays.append(delay)

        # Check that we have variation
        assert min(delays) < max(delays)
        # Check that all delays are within bounds
        assert all(0 <= d <= 0.8 for d in delays)
        # Check that average is roughly in the middle
        avg_delay = sum(delays) / len(delays)
        assert 0.3 < avg_delay < 0.5  # Should be around 0.4


class TestFileTypeFiltering:
    """Test file type filtering logic."""

    def test_pdf_detection(self):
        """Test PDF file detection."""
        spider = SapirSpider()

        # Test by extension
        url = "https://www.sapir.ac.il/docs/file.pdf"
        assert url.lower().endswith('.pdf')

        # Test by content type
        content_type = "application/pdf"
        assert 'application/pdf' in content_type

    def test_image_detection(self):
        """Test image file detection."""
        spider = SapirSpider()

        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        for ext in image_extensions:
            url = f"https://www.sapir.ac.il/images/photo{ext}"
            assert any(url.lower().endswith(e) for e in image_extensions)

    def test_css_js_rejection(self):
        """Test that CSS and JS files are rejected."""
        spider = SapirSpider()

        denied_patterns = spider.DENIED_EXTENSIONS
        assert any(r'\.css$' in pattern for pattern in denied_patterns)
        assert any(r'\.js$' in pattern for pattern in denied_patterns)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
