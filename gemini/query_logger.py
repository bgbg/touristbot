"""
Query logging utilities for Gemini RAG system
Logs all queries and answers with metadata to a unified log file
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class QueryLogger:
    """Logs queries and answers to a unified JSONL file"""

    def __init__(self, log_path: str, area: str = "", site: str = ""):
        """
        Initialize query logger

        Args:
            log_path: Path to the log file (JSONL format)
            area: Tourism area name (e.g., "sharon")
            site: Site name (e.g., "bridge")
        """
        self.log_path = log_path
        self.area = area
        self.site = site

        # Ensure parent directory exists
        log_dir = Path(log_path).parent
        if log_dir and not log_dir.exists():
            log_dir.mkdir(parents=True, exist_ok=True)

    def log_query(
        self,
        query: str,
        answer: str,
        model: str,
        context_chars: int,
        response_time_seconds: float,
        chunks_used: Optional[List[str]] = None,
    ):
        """
        Log a query and its answer

        Args:
            query: The user's query
            answer: The generated answer
            model: Model name used
            context_chars: Number of characters in context
            response_time_seconds: Time taken to generate the answer (in seconds)
            chunks_used: List of chunk filenames used in context (optional)
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "area": self.area,
            "site": self.site,
            "query": query,
            "answer": answer,
            "model": model,
            "context_chars": context_chars,
            "response_time_seconds": round(response_time_seconds, 2),
        }

        # Add chunk references if provided
        if chunks_used:
            log_entry["chunks_used"] = chunks_used

        # Append to log file (JSON Lines format)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    def get_recent_queries(self, n: int = 10) -> List[Dict]:
        """
        Get the N most recent queries

        Args:
            n: Number of recent queries to retrieve

        Returns:
            List of query log entries (most recent first)
        """
        if not os.path.exists(self.log_path):
            return []

        with open(self.log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Parse last N lines
        recent_entries = []
        for line in lines[-n:]:
            try:
                entry = json.loads(line.strip())
                recent_entries.append(entry)
            except json.JSONDecodeError:
                continue

        # Return in reverse order (most recent first)
        return list(reversed(recent_entries))

    def get_stats(self) -> Dict:
        """
        Get statistics about logged queries

        Returns:
            Dictionary with statistics
        """
        if not os.path.exists(self.log_path):
            return {
                "total_queries": 0,
                "avg_response_time_seconds": 0,
                "areas": [],
                "sites": [],
            }

        total_queries = 0
        total_response_time = 0
        areas = set()
        sites = set()

        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    total_queries += 1
                    total_response_time += entry.get("response_time_seconds", 0)
                    areas.add(entry.get("area", ""))
                    sites.add(entry.get("site", ""))
                except json.JSONDecodeError:
                    continue

        return {
            "total_queries": total_queries,
            "avg_response_time_seconds": (
                round(total_response_time / total_queries, 2)
                if total_queries > 0
                else 0
            ),
            "areas": sorted(list(areas)),
            "sites": sorted(list(sites)),
        }
