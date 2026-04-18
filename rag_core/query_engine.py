"""
Query engine for RAG using Anthropic Claude API
"""
import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from anthropic import Anthropic
from .vector_store import VectorStore
from .config import DEFAULT_CLAUDE_MODEL, DEFAULT_TOP_K, DEFAULT_TEMPERATURE


class QueryEngine:
    """RAG query engine using Anthropic Claude"""

    def __init__(
        self,
        vector_store: VectorStore,
        api_key: Optional[str] = None,
        model: str = DEFAULT_CLAUDE_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        templates_dir: str = "./templates",
    ):
        self.vector_store = vector_store
        self.model = model
        self.temperature = temperature
        self.templates_dir = Path(templates_dir)

        # Initialize Anthropic client
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")

        self.client = Anthropic(api_key=api_key)

    def query(
        self,
        query_text: str,
        action: str = "query",
        template: str = "default",
        top_k: int = DEFAULT_TOP_K,
        filter_dict: Optional[Dict[str, Any]] = None,
        rubric_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a RAG query

        Args:
            query_text: The user's query
            action: Action type - "query", "summarize", "synthesize", or "assignment_completion"
            template: Template name (e.g., "insight_paper", "default")
            top_k: Number of relevant chunks to retrieve
            filter_dict: Optional metadata filter
            rubric_path: Optional path to rubric JSON file

        Returns:
            Dict with 'answer', 'sources', 'context', and optionally 'rubric_score' keys
        """
        # Retrieve relevant documents
        results = self.vector_store.query(
            query_text=query_text,
            top_k=top_k,
            filter_dict=filter_dict,
        )

        if not results:
            return {
                "answer": "No relevant documents found in the knowledge base.",
                "sources": [],
                "context": [],
            }

        # Build context from retrieved documents
        context_parts = []
        sources = []
        for i, result in enumerate(results):
            context_parts.append(f"[Document {i+1}]\n{result['content']}\n")
            source_info = {
                "filename": result["metadata"].get("filename", "Unknown"),
                "source": result["metadata"].get("source", "Unknown"),
                "chunk_index": result["metadata"].get("chunk_index", 0),
                "distance": result["distance"],
            }
            sources.append(source_info)

        context = "\n".join(context_parts)

        # Load rubric if provided
        rubric_content = None
        rubric_data = None
        if rubric_path:
            rubric_data = self._load_rubric(rubric_path)
            rubric_content = self._format_rubric_for_prompt(rubric_data)

        # Generate prompt
        prompt = self._build_prompt(query_text, context, action, template, rubric_content)

        # Call Claude API
        response = self.client.messages.create(
            model=self.model,
            max_tokens=512,
            temperature=self.temperature,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        answer = response.content[0].text

        result = {
            "answer": answer,
            "sources": sources,
            "context": results,
        }

        # Score against rubric if provided
        if rubric_data:
            rubric_score = self._score_against_rubric(answer, rubric_data)
            result["rubric_score"] = rubric_score

        return result

    def _build_prompt(
        self,
        query: str,
        context: str,
        action: str,
        template: str,
        rubric_content: Optional[str] = None,
    ) -> str:
        """Build prompt by loading template file"""

        # Determine template folder based on action
        if action == "assignment_completion":
            folder = "assignments"
        else:
            folder = "actions"
            # Map action names to template files
            action_map = {
                "query": "query",
                "summarize": "summarize",
                "synthesize": "synthesize",
            }
            template = action_map.get(action, template)

        # Build template path
        if template == "raw_context_dump":
            return f"Context:\n{context}\n\nQuery: {query}"

        template_path = self.templates_dir / folder / f"{template}.txt"

        try:
            with open(template_path, "r", encoding="utf-8") as f:
                prompt_template = f.read()

            # Replace placeholders
            prompt = prompt_template.replace("{context}", context)
            prompt = prompt.replace("{query}", query)

            # Add rubric if provided
            if rubric_content:
                prompt = prompt.replace("{rubric}", f"\n{rubric_content}\n")
            else:
                prompt = prompt.replace("{rubric}", "")

            return prompt

        except FileNotFoundError:
            available = self._list_templates(folder)
            raise ValueError(
                f"Template not found: {template_path}\n"
                f"Available templates in {folder}/: {', '.join(available)}"
            )

    def _load_rubric(self, rubric_path: str) -> Dict[str, Any]:
        """Load rubric JSON file"""
        full_path = self.templates_dir / "rubrics" / rubric_path
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            raise ValueError(f"Rubric not found: {full_path}")
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in rubric: {full_path}")

    def _format_rubric_for_prompt(self, rubric: Dict[str, Any]) -> str:
        """Format rubric for inclusion in prompt"""
        lines = [
            f"\nASSIGNMENT RUBRIC ({rubric['total_points']} points total):",
            "=" * 60,
        ]

        for criterion in rubric["criteria"]:
            lines.append(
                f"\n{criterion['name']} ({criterion['points']} points):"
            )
            lines.append(f"  {criterion['description']}")

        lines.append("\n" + "=" * 60)
        lines.append(
            "Please ensure your response addresses all rubric criteria."
        )

        return "\n".join(lines)

    def _score_against_rubric(
        self, output: str, rubric: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Score output against rubric using LLM"""

        scoring_prompt = f"""You are evaluating a student assignment against a rubric.

ASSIGNMENT OUTPUT:
{output}

RUBRIC:
{json.dumps(rubric, indent=2)}

For each criterion, provide:
1. Points earned (0 to maximum for that criterion)
2. Brief feedback explaining the score

Respond in JSON format:
{{
  "scores": [
    {{"criterion": "name", "earned": points, "max": points, "feedback": "text"}},
    ...
  ],
  "total_earned": sum,
  "total_possible": {rubric['total_points']},
  "percentage": percentage
}}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            temperature=0.3,
            messages=[{"role": "user", "content": scoring_prompt}],
        )

        # Parse JSON response
        try:
            score_data = json.loads(response.content[0].text)
            return score_data
        except json.JSONDecodeError:
            # Fallback if LLM doesn't return valid JSON
            return {
                "error": "Failed to parse rubric score",
                "raw_response": response.content[0].text,
            }

    def _list_templates(self, folder: str) -> List[str]:
        """List available templates in a folder"""
        folder_path = self.templates_dir / folder
        if not folder_path.exists():
            return []

        templates = []
        for file in folder_path.glob("*.txt"):
            templates.append(file.stem)
        return templates
