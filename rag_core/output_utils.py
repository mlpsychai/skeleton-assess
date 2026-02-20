"""
Utility functions for RAG output handling
Convenience wrappers for common output operations
"""

from pathlib import Path
from typing import Optional, Dict
from .output_formatter import OutputFormatter
from .config import DEFAULT_OUTPUT_FORMAT, INCLUDE_AI_SCORE, OUTPUT_DIRECTORY


def save_rag_output(
    content: str,
    filename: str,
    output_dir: Optional[Path] = None,
    format: Optional[str] = None,
    title: Optional[str] = None,
    metadata: Optional[Dict] = None,
    include_ai_score: Optional[bool] = None,
) -> Path:
    """
    Convenience function to save RAG output with default settings

    Args:
        content: Text content to save
        filename: Base filename (extension will be added automatically)
        output_dir: Output directory (defaults to ./output)
        format: Output format (defaults to DEFAULT_OUTPUT_FORMAT)
        title: Document title
        metadata: Additional metadata
        include_ai_score: Whether to include AI score (defaults to INCLUDE_AI_SCORE)

    Returns:
        Path to saved file
    """
    # Set defaults
    if output_dir is None:
        output_dir = Path.cwd() / OUTPUT_DIRECTORY
    else:
        output_dir = Path(output_dir)

    if format is None:
        format = DEFAULT_OUTPUT_FORMAT

    if include_ai_score is None:
        include_ai_score = INCLUDE_AI_SCORE

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create output path
    output_path = output_dir / filename

    # Create formatter and save
    formatter = OutputFormatter(default_format=format)
    return formatter.save_output(
        content=content,
        output_path=output_path,
        format=format,
        title=title,
        metadata=metadata,
        include_ai_score=include_ai_score
    )


def analyze_text_for_ai(text: str) -> Dict:
    """
    Analyze text for AI-generation likelihood

    Args:
        text: Text to analyze

    Returns:
        Dict with AI analysis results
    """
    formatter = OutputFormatter()
    return formatter.calculate_ai_score(text)


def get_ai_score_only(text: str) -> float:
    """
    Get just the AI score number

    Args:
        text: Text to analyze

    Returns:
        AI likelihood score (0-100)
    """
    analysis = analyze_text_for_ai(text)
    return analysis.get('ai_score', 0)
