#!/usr/bin/env python3
"""
Flask server for skeleton_assess — lightweight web front end
for score processing. Run with: python server.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory

# Ensure project root is on sys.path so imports work
PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from main import process_score_file
from psychometric_scoring.instrument_config import load_instrument_config
from psychometric_scoring.client_info import load_client_info_json

app = Flask(__name__)


@app.route("/")
def index():
    return send_from_directory(str(PROJECT_ROOT), "frontend.html")


@app.route("/api/generate", methods=["POST"])
def generate():
    tmp_dir = tempfile.mkdtemp()
    try:
        # --- Score CSV (required) ---
        score_file = request.files.get("score_file")
        if not score_file or score_file.filename == "":
            return jsonify(success=False, error="Score CSV file is required."), 400
        csv_path = os.path.join(tmp_dir, score_file.filename)
        score_file.save(csv_path)

        # --- Instrument config ---
        config_path = request.form.get("instrument_config", "").strip()
        if not config_path:
            config_path = "instrument_config.json"
        instrument_config = load_instrument_config(config_path)

        # --- Output options ---
        fmt = request.form.get("format", "html")
        if fmt not in ("docx", "html", "both"):
            fmt = "html"

        output_dir = request.form.get("output_dir", "").strip()
        if not output_dir:
            output_dir = "output/reports"
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        interpretive = request.form.get("interpretive") == "true"

        # --- Client info JSON (optional) ---
        client_info = None
        client_file = request.files.get("client_info_file")
        if client_file and client_file.filename != "":
            ci_path = os.path.join(tmp_dir, client_file.filename)
            client_file.save(ci_path)
            client_info = load_client_info_json(ci_path)

        # --- Run the pipeline ---
        success = process_score_file(
            csv_path,
            output_dir=output_dir,
            format=fmt,
            client_info=client_info,
            interpretive=interpretive,
            instrument_config=instrument_config,
        )

        if not success:
            return jsonify(success=False, error="Processing failed. Check server console for details.")

        # Collect generated files
        out = Path(output_dir)
        stem = Path(csv_path).stem  # e.g. "TEST_001"
        # The test_id comes from inside the CSV; list any recently created files
        generated = sorted(out.glob("*_report.*"), key=lambda p: p.stat().st_mtime, reverse=True)
        # Return the most recent files matching this run (created in last 10 seconds)
        import time
        now = time.time()
        files = [str(p) for p in generated if now - p.stat().st_mtime < 10]

        return jsonify(success=True, files=files)

    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@app.route("/api/create-instrument", methods=["POST"])
def create_instrument():
    try:
        data = request.get_json()
        if not data:
            return jsonify(success=False, error="No JSON body provided."), 400

        config_name = data.get("config_name", "").strip()
        if not config_name:
            return jsonify(success=False, error="Config name is required."), 400

        # Load the template as a base
        with open(PROJECT_ROOT / "instrument_config.json", "r") as f:
            config = json.load(f)

        # Overlay user-provided values
        config["instrument_name"] = data.get("instrument_name", "")
        config["instrument_full_name"] = data.get("instrument_full_name", "")
        config["num_items"] = int(data.get("num_items", 0))
        config["response_type"] = data.get("response_type", "boolean")
        config["max_missing_threshold"] = float(data.get("max_missing_threshold", 0.10))
        config["instrument_reference"] = data.get("instrument_reference", "")
        config["instrument_description"] = data.get("instrument_description", "")
        config["norms"] = data.get("norms", "")

        if data.get("disclaimer_text"):
            config["disclaimer_text"] = data["disclaimer_text"]

        # Response options
        if config["response_type"] == "boolean":
            true_vals = [v.strip() for v in data.get("true_values", "True,1,Yes,T").split(",") if v.strip()]
            false_vals = [v.strip() for v in data.get("false_values", "False,0,No,F").split(",") if v.strip()]
            config["response_options"] = {"true_values": true_vals, "false_values": false_vals}
        else:
            config["response_options"] = {
                "min_value": int(data.get("likert_min", 0)),
                "max_value": int(data.get("likert_max", 3)),
            }

        # Save to configs/ directory
        configs_dir = PROJECT_ROOT / "configs"
        configs_dir.mkdir(exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in config_name)
        out_path = configs_dir / f"{safe_name}_config.json"
        with open(out_path, "w") as f:
            json.dump(config, f, indent=2)

        rel_path = str(out_path.relative_to(PROJECT_ROOT))
        return jsonify(success=True, path=rel_path)

    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@app.route("/reports/<path:filename>")
def serve_report(filename):
    """Serve generated reports so the user can click links to open them."""
    reports_dir = PROJECT_ROOT / "output" / "reports"
    return send_from_directory(str(reports_dir), filename)


if __name__ == "__main__":
    print("Starting skeleton_assess server at http://localhost:5000")
    app.run(debug=True, port=5000)
