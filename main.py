#!/usr/bin/env python3
"""
Main entry point for Psychometric Assessment System

Instrument-agnostic CLI that loads all instrument-specific values
from instrument_config.json. Supports both boolean and Likert instruments.
"""
import sys
import os
from dotenv import load_dotenv
import argparse
import yaml
import json
from pathlib import Path
from rag_core import DocumentLoader, VectorStore
from psychometric_scoring import ScoreLoader, ScoreValidator, ScoreCalculator, ReportGenerator, HTMLReportGenerator
from psychometric_scoring.client_info import ClientInfo, load_client_info_json, collect_client_info_interactive
from psychometric_scoring.rag_interpreter import RAGInterpreter
from psychometric_scoring.instrument_config import load_instrument_config

def load_config():
    """Load configuration from config.yaml"""
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

def ingest_documents(config):
    """Ingest documents from data directory"""
    print(f"Ingesting documents from {config['data_dir']}...")

    loader = DocumentLoader()
    documents = loader.load_directory(config['data_dir'])

    if not documents:
        print("No documents found to ingest!")
        return

    print(f"Loaded {len(documents)} document chunks")

    vector_store = VectorStore(
        collection_name=config['collection_name'],
        persist_directory=config['chroma_db_dir']
    )

    vector_store.add_documents(documents)
    print(f"Successfully added {len(documents)} chunks to vector store")
    print(f"Total documents in collection: {vector_store.count()}")

def clear_collection(config):
    """Clear all documents from collection"""
    vector_store = VectorStore(
        collection_name=config['collection_name'],
        persist_directory=config['chroma_db_dir']
    )

    count = vector_store.count()
    if count > 0:
        confirm = input(f"Delete {count} documents? (yes/no): ")
        if confirm.lower() == 'yes':
            vector_store.delete_collection()
            print("Collection cleared")
        else:
            print("Cancelled")
    else:
        print("Collection is already empty")

def process_score_file(csv_path, output_dir='output/reports', format='docx',
                       client_info=None, interpretive=False, instrument_config=None,
                       cached_narratives=None):
    """Process a single score CSV file."""
    print(f"\n{'='*60}")
    print(f"Processing: {Path(csv_path).name}")
    print(f"{'='*60}")

    try:
        num_items = instrument_config['num_items']
        instrument_name = instrument_config['instrument_name']
        response_type = instrument_config.get('response_type', 'boolean')
        response_options = instrument_config.get('response_options', {})
        max_missing = instrument_config['max_missing_threshold']

        # Load scores
        print("Loading CSV file...")
        loader = ScoreLoader(
            num_items=num_items,
            response_type=response_type,
            response_options=response_options,
        )
        score_data = loader.load_csv(csv_path)
        test_id = score_data['test_id']
        print(f"  Loaded test ID: {test_id}")

        # Validate
        print("Validating responses...")
        validator = ScoreValidator(
            num_items=num_items,
            max_missing_threshold=max_missing,
            instrument_name=instrument_name,
            response_type=response_type,
            response_options=response_options,
        )
        validation_report = validator.validate(score_data)

        completion = validation_report['completion_rate']
        missing = validation_report['missing_count']
        print(f"  Completion: {completion:.1%} ({num_items - missing}/{num_items} items)")

        if not validation_report['is_valid']:
            print(f"\n  ERROR: Protocol is invalid")
            for error in validation_report['errors']:
                print(f"  - {error}")
            return False

        if validation_report['warnings']:
            print(f"\n  Warnings:")
            for warning in validation_report['warnings']:
                print(f"  - {warning}")

        # Calculate scores
        print("Calculating scale scores...")
        calculator = ScoreCalculator(instrument_config=instrument_config)
        calc_results = calculator.calculate(score_data)
        print(f"  Calculated {len(calc_results['scale_scores'])} scales")

        # Generate interpretive narratives if requested
        narratives = None
        if interpretive:
            if cached_narratives:
                print("\nLoading cached narratives...")
                narratives = cached_narratives
                print(f"  Loaded {len(narratives)} cached narrative sections")
            else:
                print("\nGenerating interpretive narratives via RAG...")
                config = load_config()
                interpreter = RAGInterpreter(
                    chroma_dir=config.get('chroma_db_dir', './chroma_db'),
                    templates_dir='./templates',
                    instrument_config=instrument_config,
                    rag_settings=config.get('rag_settings', {}),
                )

                if not interpreter.is_ready():
                    print("  ERROR: Interpretation worksheets not ingested.")
                    print("  Run: python main.py --ingest-worksheets <worksheets_dir>")
                    return False

                narratives = interpreter.generate_all_narratives(
                    calc_results, client_info
                )
                print(f"  Generated {len(narratives)} narrative sections")

        # Generate report(s) based on format
        report_suffix = "_interpretive_report" if interpretive else "_report"
        print(f"\nGenerating {format} report(s)...")

        report_paths = []

        if format in ['docx', 'both']:
            generator = ReportGenerator(instrument_config=instrument_config)
            output_path = Path(output_dir) / f"{test_id}{report_suffix}.docx"
            report_path = generator.generate_report(
                calc_results,
                validation_report,
                str(output_path)
            )
            report_paths.append(report_path)
            print(f"  DOCX report saved: {report_path}")

        if format in ['html', 'both']:
            html_generator = HTMLReportGenerator(instrument_config=instrument_config)
            html_output_path = Path(output_dir) / f"{test_id}{report_suffix}.html"
            html_report_path = html_generator.generate_html_report(
                calc_results,
                validation_report,
                str(html_output_path),
                client_info=client_info,
                narratives=narratives,
            )
            report_paths.append(html_report_path)
            print(f"  HTML report saved: {html_report_path}")

        # Summary
        summary = calc_results['summary']
        print(f"\nSummary:")
        print(f"  Validity: {validator.get_validity_assessment(validation_report)}")
        print(f"  Elevated scales: {summary['elevated_scales_count']}")
        if summary['elevated_scales']:
            print(f"  Scale abbreviations: {', '.join(summary['elevated_scales'])}")

        print(f"\n{'='*60}\n")
        return True

    except Exception as e:
        print(f"\n  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def process_score_directory(directory, output_dir='output/reports', format='docx',
                           instrument_config=None):
    """Process all CSV files in a directory."""
    print(f"\n{'='*60}")
    print(f"Batch Processing: {directory}")
    print(f"{'='*60}\n")

    try:
        dir_path = Path(directory)
        csv_files = list(dir_path.glob("*.csv"))

        if not csv_files:
            print(f"No CSV files found in {directory}")
            return

        print(f"Found {len(csv_files)} CSV file(s)\n")

        success_count = 0
        failed_files = []

        for idx, csv_file in enumerate(csv_files, 1):
            print(f"[{idx}/{len(csv_files)}] Processing: {csv_file.name}")
            success = process_score_file(
                str(csv_file), output_dir, format,
                instrument_config=instrument_config
            )

            if success:
                success_count += 1
            else:
                failed_files.append(csv_file.name)

        print(f"{'='*60}")
        print(f"Batch Processing Complete")
        print(f"{'='*60}")
        print(f"Successful: {success_count}/{len(csv_files)}")
        print(f"Reports saved to: {output_dir}")

        if failed_files:
            print(f"\nFailed files:")
            for filename in failed_files:
                print(f"  - {filename}")

        print(f"{'='*60}\n")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description='Psychometric Assessment System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ingest interpretation worksheets
  python main.py --ingest-worksheets worksheets/

  # Process score file (HTML format)
  python main.py --score-file data/scores/test_001.csv --format html

  # Generate both DOCX and HTML reports
  python main.py --score-file data/scores/test_001.csv --format both

  # Use a different instrument config
  python main.py --instrument-config my_instrument.json --score-file test.csv

  # Generate interpretive report with RAG narratives
  python main.py --score-file test.csv --interpretive --client-info client.json --format html
        """
    )

    # Instrument config
    parser.add_argument('--instrument-config', type=str, default='instrument_config.json',
                       help='Path to instrument configuration JSON (default: instrument_config.json)')

    # RAG document operations
    parser.add_argument('--ingest', action='store_true',
                       help='Ingest documents from data directory')
    parser.add_argument('--clear', action='store_true',
                       help='Clear all documents from collection')
    parser.add_argument('--ingest-worksheets', type=str,
                       help='Ingest interpretation worksheets from directory')

    # Score Processing Arguments
    parser.add_argument('--score-file', type=str,
                       help='Process single score CSV file')
    parser.add_argument('--score-dir', type=str,
                       help='Process all CSV files in directory')
    parser.add_argument('--output-dir', type=str, default='output/reports',
                       help='Output directory for reports (default: output/reports)')
    parser.add_argument('--format', type=str, choices=['docx', 'html', 'both'],
                       default='docx',
                       help='Report format: docx (default), html (interactive), or both')

    # Interpretive Report Arguments
    parser.add_argument('--interpretive', action='store_true',
                       help='Generate full interpretive report with RAG narratives')
    parser.add_argument('--client-info', type=str,
                       help='JSON file with client demographics for interpretive report')
    parser.add_argument('--cached-narratives', type=str,
                       help='JSON file with cached narratives (skip RAG/API calls)')

    args = parser.parse_args()

    # Two-stage config: instrument_config.json for instrument, config.yaml for RAG
    instrument_config = load_instrument_config(args.instrument_config)
    config = load_config()

    if args.ingest:
        if args.clear:
            clear_collection(config)
        ingest_documents(config)
        return

    if args.clear and not args.ingest:
        clear_collection(config)
        return

    # Worksheet ingestion
    if args.ingest_worksheets:
        print(f"Ingesting interpretation worksheets from {args.ingest_worksheets}...")
        interpreter = RAGInterpreter(
            chroma_dir=config.get('chroma_db_dir', './chroma_db'),
            templates_dir='./templates',
            instrument_config=instrument_config,
            rag_settings=config.get('rag_settings', {}),
        )
        count = interpreter.ingest_worksheets(args.ingest_worksheets)
        print(f"Successfully ingested {count} interpretation chunks")
        return

    # Score Processing
    if args.score_file:
        client_info = None
        if args.client_info:
            print(f"Loading client info from {args.client_info}...")
            client_info = load_client_info_json(args.client_info)
            print(f"  Client: {client_info.client_name or 'N/A'}")

        cached_narratives = None
        if args.cached_narratives:
            with open(args.cached_narratives, 'r') as f:
                cached_narratives = json.load(f)
            print(f"  Loaded cached narratives from {args.cached_narratives}")

        process_score_file(
            args.score_file,
            args.output_dir,
            args.format,
            client_info=client_info,
            interpretive=args.interpretive,
            instrument_config=instrument_config,
            cached_narratives=cached_narratives,
        )
        return

    if args.score_dir:
        process_score_directory(
            args.score_dir, args.output_dir, args.format,
            instrument_config=instrument_config
        )
        return

    parser.print_help()

if __name__ == "__main__":
    main()
