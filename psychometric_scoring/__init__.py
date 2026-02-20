"""
Psychometric Score Processing Package

This package provides functionality for processing psychometric test scores:
- Loading scores from CSV files
- Validating responses
- Calculating raw scores using item-to-scale mappings
- Generating formatted .docx reports with interpretive ranges
- Generating interactive HTML reports with ECharts

For educational and research purposes only. Not a substitute for
official scoring through licensed assessment platforms.
"""

from .score_loader import ScoreLoader
from .score_validator import ScoreValidator
from .score_calculator import ScoreCalculator
from .html_report_generator import HTMLReportGenerator
from .client_info import ClientInfo
# RAG interpreter — optional (requires tiktoken, chromadb, anthropic)
try:
    from .rag_interpreter import RAGInterpreter
except ImportError:
    RAGInterpreter = None

# Legacy DOCX pipeline — optional imports
try:
    from .report_generator import ReportGenerator
except ImportError:
    ReportGenerator = None

# ECharts rendering — optional imports
try:
    from .chart_renderer import ChartRenderer
except ImportError:
    ChartRenderer = None

__version__ = "1.0.0"
__all__ = [
    "ScoreLoader", "ScoreValidator", "ScoreCalculator",
    "ReportGenerator", "HTMLReportGenerator", "ChartRenderer",
    "ClientInfo", "RAGInterpreter",
]
