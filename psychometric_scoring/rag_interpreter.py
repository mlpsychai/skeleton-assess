"""
RAG Interpreter

Ingests interpretation worksheets into ChromaDB and generates
per-category clinical narratives using RAG-retrieved context
sent to the Anthropic Claude API.

All instrument-specific values are read from instrument_config.json.
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import tiktoken

from rag_core import VectorStore, QueryEngine
from rag_core.config import DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP
from .instrument_config import load_instrument_config, get_elevated_labels, get_baseline_label


class RAGInterpreter:
    """Generates interpretive narratives using RAG."""

    def __init__(self, chroma_dir: str = "./chroma_db", templates_dir: str = "./templates",
                 instrument_config: Optional[Dict[str, Any]] = None,
                 rag_settings: Optional[Dict[str, Any]] = None):
        if instrument_config is None:
            instrument_config = load_instrument_config()

        self.config = instrument_config
        self.chroma_dir = chroma_dir
        self.templates_dir = templates_dir
        self.encoding = tiktoken.get_encoding("cl100k_base")

        # Derive from config
        self.instrument_name = self.config['instrument_name']
        self.safety_scales = self.config.get('safety_scales', [])
        self.collection_name = f"{self.instrument_name.lower().replace('-', '')}_interpretations"

        # Config-driven elevation labels
        self.elevated_labels = get_elevated_labels(self.config)
        self.baseline_label = get_baseline_label(self.config)

        # Non-elevated, non-baseline labels (e.g. "Slightly Elevated")
        all_labels = {c['label'] for c in self.config.get('interpretive_cutoffs', [])}
        self.low_range_labels = all_labels - self.elevated_labels - {self.baseline_label}

        # Special worksheets from config
        self.special_worksheets = self.config.get('special_worksheets', {})

        # RAG query settings (from config.yaml rag_settings)
        rag = rag_settings or {}
        self.top_k_category = rag.get('top_k_category', 15)
        self.top_k_integration = rag.get('top_k_integration', 20)
        self.top_k_treatment = rag.get('top_k_treatment', 20)
        self.top_k_summary = rag.get('top_k_summary', 10)

        # Build categories from config
        self.categories = {}
        for cat in self.config.get('categories', []):
            self.categories[cat['key']] = {
                'worksheet': cat.get('worksheet', ''),
                'scales': cat['scales'],
                'title': cat['title'],
            }

    def ingest_worksheets(self, worksheets_dir: str) -> int:
        """
        Ingest interpretation worksheets into ChromaDB.

        Reads .md files, chunks them with tiktoken, and stores
        in the instrument interpretations collection.

        Args:
            worksheets_dir: Path to directory containing worksheet .md files

        Returns:
            Number of chunks ingested
        """
        worksheets_path = Path(worksheets_dir)
        if not worksheets_path.exists():
            raise ValueError(f"Worksheets directory not found: {worksheets_dir}")

        # Initialize vector store for interpretations
        vector_store = VectorStore(
            collection_name=self.collection_name,
            persist_directory=self.chroma_dir,
        )

        # Clear existing interpretation chunks
        if vector_store.count() > 0:
            print(f"Clearing {vector_store.count()} existing interpretation chunks...")
            vector_store.clear()
            # Re-create after clear
            vector_store = VectorStore(
                collection_name=self.collection_name,
                persist_directory=self.chroma_dir,
            )

        total_chunks = 0

        # Find which category each file belongs to
        file_to_category = {}
        for cat_key, cat_info in self.categories.items():
            file_to_category[cat_info["worksheet"]] = cat_key

        # Also include special worksheets from config
        for key, filename in self.special_worksheets.items():
            file_to_category[filename] = key

        for md_file in sorted(worksheets_path.glob("*.md")):
            filename = md_file.name
            category = file_to_category.get(filename, "general")

            print(f"  Processing {filename} (category: {category})...")

            # Read file
            text = md_file.read_text(encoding="utf-8")

            # Chunk with tiktoken
            chunks = self._chunk_text(text)

            # Detect which scale abbreviations appear in each chunk
            all_scale_abbrs = set()
            for cat_info in self.categories.values():
                all_scale_abbrs.update(cat_info["scales"])

            # Build documents
            documents = []
            for i, chunk in enumerate(chunks):
                # Find scale abbreviations mentioned in this chunk
                chunk_scales = [s for s in all_scale_abbrs if s in chunk]

                metadata = {
                    "source": str(md_file),
                    "filename": filename,
                    "category": category,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "document_type": "interpretation_worksheet",
                    "scales": ",".join(sorted(chunk_scales)) if chunk_scales else "general",
                }
                documents.append({"content": chunk, "metadata": metadata})

            if documents:
                vector_store.add_documents(documents)
                total_chunks += len(documents)
                print(f"    Added {len(documents)} chunks")

        print(f"\nTotal: {total_chunks} interpretation chunks ingested")
        return total_chunks

    def _chunk_text(self, text: str) -> List[str]:
        """Chunk text using tiktoken, matching rag_core's DocumentLoader approach."""
        tokens = self.encoding.encode(text)
        chunks = []
        start = 0

        while start < len(tokens):
            end = start + DEFAULT_CHUNK_SIZE
            chunk_tokens = tokens[start:end]
            chunk_text = self.encoding.decode(chunk_tokens).strip()
            if chunk_text:
                chunks.append(chunk_text)
            start = end - DEFAULT_CHUNK_OVERLAP

        return chunks

    def is_ready(self) -> bool:
        """Check if interpretation worksheets have been ingested."""
        try:
            vector_store = VectorStore(
                collection_name=self.collection_name,
                persist_directory=self.chroma_dir,
            )
            return vector_store.count() > 0
        except Exception:
            return False

    def generate_all_narratives(
        self,
        calc_results: Dict[str, Any],
        client_info=None,
    ) -> Dict[str, str]:
        """
        Generate interpretive narratives for all scale categories.

        Args:
            calc_results: Output from ScoreCalculator.calculate()
            client_info: Optional ClientInfo instance

        Returns:
            Dict mapping category keys to narrative text strings
        """
        # Set up RAG components
        vector_store = VectorStore(
            collection_name=self.collection_name,
            persist_directory=self.chroma_dir,
        )

        if vector_store.count() == 0:
            raise RuntimeError(
                "No interpretation worksheets found. "
                "Run --ingest-worksheets first."
            )

        query_engine = QueryEngine(
            vector_store=vector_store,
            templates_dir=self.templates_dir,
        )

        scale_scores = calc_results["scale_scores"]

        # Build client context string
        client_context = ""
        if client_info:
            client_context = client_info.to_context_string()

        narratives = {}

        # Generate per-category narratives
        for cat_key, cat_info in self.categories.items():
            print(f"  Generating {cat_info['title']} narrative...")
            query = self._build_category_query(
                cat_key, cat_info, scale_scores, client_context
            )

            result = query_engine.query(
                query_text=query,
                action="interpret",
                template="interpretation",
                top_k=self.top_k_category,
            )
            narratives[cat_key] = result["answer"]

        # Generate integration narrative
        print("  Generating Profile Integration narrative...")
        integration_query = self._build_integration_query(
            scale_scores, client_context
        )
        result = query_engine.query(
            query_text=integration_query,
            action="integrate",
            template="integration",
            top_k=self.top_k_integration,
        )
        narratives["integration"] = result["answer"]

        # Generate treatment recommendations
        print("  Generating Treatment Recommendations...")
        treatment_query = self._build_treatment_query(
            scale_scores, client_context
        )
        result = query_engine.query(
            query_text=treatment_query,
            action="treat",
            template="treatment",
            top_k=self.top_k_treatment,
        )
        narratives["treatment"] = result["answer"]

        # Generate summary
        print("  Generating Summary...")
        summary_query = self._build_summary_query(
            scale_scores, client_context, narratives
        )
        result = query_engine.query(
            query_text=summary_query,
            action="interpret",
            template="interpretation",
            top_k=self.top_k_summary,
        )
        narratives["summary"] = result["answer"]

        return narratives

    def _build_category_query(
        self,
        cat_key: str,
        cat_info: Dict,
        scale_scores: Dict[str, Any],
        client_context: str,
    ) -> str:
        """Build query string for a specific scale category."""
        lines = [f"CATEGORY: {cat_info['title']}\n"]

        if client_context:
            lines.append(f"CLIENT CONTEXT:\n{client_context}\n")

        lines.append("SCALE SCORES:")
        for scale_abbr in cat_info["scales"]:
            if scale_abbr in scale_scores:
                s = scale_scores[scale_abbr]
                t = s.get("t_score_display", s.get("t_score", "N/A"))
                lines.append(
                    f"  {scale_abbr} ({s['scale_name']}): "
                    f"Raw={s['raw_score']}/{s['total_items']}, "
                    f"T={t}, "
                    f"Range={s['interpretive_range']}"
                )
            else:
                lines.append(f"  {scale_abbr}: Not scored")

        # Add elevation summary
        elevated = [
            abbr for abbr in cat_info["scales"]
            if abbr in scale_scores
            and scale_scores[abbr]["interpretive_range"] in self.elevated_labels
        ]
        low_range = [
            abbr for abbr in cat_info["scales"]
            if abbr in scale_scores
            and scale_scores[abbr]["interpretive_range"] in self.low_range_labels
        ]

        lines.append(f"\nClinically Elevated: {', '.join(elevated) if elevated else 'None'}")
        lines.append(f"Low-Range Elevated: {', '.join(low_range) if low_range else 'None'}")

        return "\n".join(lines)

    def _build_integration_query(
        self,
        scale_scores: Dict[str, Any],
        client_context: str,
    ) -> str:
        """Build query for profile integration."""
        lines = ["PROFILE INTEGRATION — ALL SCALES\n"]

        if client_context:
            lines.append(f"CLIENT CONTEXT:\n{client_context}\n")

        # Group all scales by elevation
        clinically_elevated = []
        low_range = []
        within_normal = []

        for abbr, s in scale_scores.items():
            t = s.get("t_score_display", s.get("t_score", "N/A"))
            entry = f"{abbr} (T={t}, {s['interpretive_range']})"
            if s["interpretive_range"] in self.elevated_labels:
                clinically_elevated.append(entry)
            elif s["interpretive_range"] in self.low_range_labels:
                low_range.append(entry)
            else:
                within_normal.append(entry)

        lines.append("CLINICALLY ELEVATED SCALES:")
        for e in clinically_elevated:
            lines.append(f"  {e}")

        lines.append("\nLOW-RANGE ELEVATIONS:")
        for e in low_range:
            lines.append(f"  {e}")

        lines.append(f"\nSCALES WITHIN NORMAL LIMITS: {len(within_normal)}")

        # Key cross-domain patterns
        lines.append("\nKEY SCALE SCORES BY DOMAIN:")
        for cat_key, cat_info in self.categories.items():
            cat_elevated = [
                abbr for abbr in cat_info["scales"]
                if abbr in scale_scores
                and scale_scores[abbr]["interpretive_range"] != self.baseline_label
            ]
            if cat_elevated:
                scores_str = ", ".join(
                    f"{a}=T{scale_scores[a].get('t_score_display', scale_scores[a].get('t_score', '?'))}"
                    for a in cat_elevated
                )
                lines.append(f"  {cat_info['title']}: {scores_str}")

        return "\n".join(lines)

    def _build_treatment_query(
        self,
        scale_scores: Dict[str, Any],
        client_context: str,
    ) -> str:
        """Build query for treatment recommendations."""
        lines = ["TREATMENT RECOMMENDATIONS QUERY\n"]

        if client_context:
            lines.append(f"CLIENT CONTEXT:\n{client_context}\n")

        lines.append("ELEVATED SCALES REQUIRING TREATMENT CONSIDERATION:")

        for abbr, s in scale_scores.items():
            if s["interpretive_range"] in self.elevated_labels:
                t = s.get("t_score_display", s.get("t_score", "N/A"))
                lines.append(
                    f"  {abbr} ({s['scale_name']}): T={t}, {s['interpretive_range']}"
                )

        # Flag safety concerns from config-driven safety scales
        for safety_abbr in self.safety_scales:
            safety_data = scale_scores.get(safety_abbr, {})
            if safety_data and safety_data.get("interpretive_range") != self.baseline_label:
                t = safety_data.get('t_score_display', safety_data.get('t_score', '?'))
                lines.append(
                    f"\n** SAFETY NOTE: {safety_abbr} is elevated (T={t}). "
                    f"Prioritize safety assessment for {safety_data.get('scale_name', safety_abbr)}. **"
                )

        return "\n".join(lines)

    def _build_summary_query(
        self,
        scale_scores: Dict[str, Any],
        client_context: str,
        narratives: Dict[str, str],
    ) -> str:
        """Build query for overall summary paragraph."""
        lines = [
            "Write a concise SUMMARY paragraph (4-6 sentences) for the end of this "
            f"{self.instrument_name} interpretive report. This should capture the essence of the entire "
            "profile in a way that a referring clinician can quickly understand.\n"
        ]

        if client_context:
            lines.append(f"CLIENT CONTEXT:\n{client_context}\n")

        # Include brief notes from each narrative
        lines.append("KEY FINDINGS FROM THE REPORT:")
        for cat_key in list(self.categories.keys()) + ["integration"]:
            if cat_key in narratives:
                # Take first 300 chars as a brief summary
                brief = narratives[cat_key][:300].replace("\n", " ")
                lines.append(f"\n{cat_key.upper()}: {brief}...")

        # Elevated count
        elevated_count = sum(
            1 for s in scale_scores.values()
            if s["interpretive_range"] in self.elevated_labels
        )
        lines.append(f"\nTotal elevated scales: {elevated_count}")

        return "\n".join(lines)
