"""
Middlewares for Sapir scraper.

Includes custom retry middleware with exponential backoff and randomization.
"""
import random
import time
import scrapy
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message


class ExponentialBackoffRetryMiddleware(RetryMiddleware):
    """
    Retry middleware with exponential backoff and randomization.

    Implements delays: random(0, 0.2s) → random(0, 0.4s) → random(0, 0.8s) → random(0, 1.6s)
    Maximum delay capped at 3 seconds.
    """

    def __init__(self, settings):
        super().__init__(settings)
        self.max_delay = 3.0  # Maximum delay in seconds

    def process_response(self, request, response, spider):
        """Process response and implement retry logic with exponential backoff."""
        if request.meta.get('dont_retry', False):
            return response

        # Check if status code indicates we should retry
        if response.status in self.retry_http_codes:
            reason = response_status_message(response.status)
            return self._retry_with_backoff(request, reason, spider) or response

        return response

    def process_exception(self, request, exception, spider):
        """Process exceptions and implement retry logic with exponential backoff."""
        if (
            isinstance(exception, self.EXCEPTIONS_TO_RETRY)
            and not request.meta.get('dont_retry', False)
        ):
            return self._retry_with_backoff(request, exception, spider)

    def _retry_with_backoff(self, request, reason, spider):
        """
        Retry request with exponential backoff delay.

        Delay formula: random.uniform(0, 0.2 * (2 ** retry_count))
        Maximum delay: 3 seconds
        """
        retries = request.meta.get('retry_times', 0) + 1

        # Check if we've exceeded max retries
        retry_times = self.max_retry_times
        if 'max_retry_times' in request.meta:
            retry_times = request.meta['max_retry_times']

        stats = spider.crawler.stats
        if retries <= retry_times:
            # Calculate exponential backoff delay
            # Base delay: 0.2s, multiplied by 2^retry_count
            max_delay_for_retry = min(0.2 * (2 ** retries), self.max_delay)
            delay = random.uniform(0, max_delay_for_retry)

            spider.logger.debug(
                f"Retrying {request.url} (attempt {retries}/{retry_times}) "
                f"after {delay:.3f}s delay. Reason: {reason}"
            )

            # Sleep for the calculated delay
            time.sleep(delay)

            # Update stats
            stats.inc_value('retry/count')
            stats.inc_value(f'retry/reason_count/{reason}')

            # Create new request with updated retry count
            retryreq = request.copy()
            retryreq.meta['retry_times'] = retries
            retryreq.dont_filter = True
            retryreq.priority = request.priority + self.priority_adjust

            return retryreq
        else:
            spider.logger.warning(
                f"Gave up retrying {request.url} (failed {retries} times): {reason}"
            )
            stats.inc_value('retry/max_reached')
            stats.inc_value(f'retry/reason_count/{reason}/max_reached')


class SapirScraperSpiderMiddleware:
    """Spider middleware for sapir_scraper."""

    @classmethod
    def from_crawler(cls, crawler):
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=scrapy.signals.spider_opened)
        return s

    def process_spider_input(self, response, spider):
        return None

    def process_spider_output(self, response, result, spider):
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        pass

    def process_start_requests(self, start_requests, spider):
        for r in start_requests:
            yield r

    def spider_opened(self, spider):
        spider.logger.info(f'Spider opened: {spider.name}')


class SapirScraperDownloaderMiddleware:
    """Downloader middleware for sapir_scraper."""

    @classmethod
    def from_crawler(cls, crawler):
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=scrapy.signals.spider_opened)
        return s

    def process_request(self, request, spider):
        return None

    def process_response(self, request, response, spider):
        return response

    def process_exception(self, request, exception, spider):
        pass

    def spider_opened(self, spider):
        spider.logger.info(f'Spider opened: {spider.name}')
