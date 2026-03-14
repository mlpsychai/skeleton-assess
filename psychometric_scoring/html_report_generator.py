"""
HTML Report Generator

Generates standalone HTML reports with interactive ECharts graphs.
All instrument-specific values are read from instrument_config.json.
Chart configuration logic is shared with chart_renderer.py.
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

from .instrument_config import (
    load_instrument_config, get_validity_category, get_substantive_categories,
    is_elevated, get_all_cutoff_labels, get_elevated_labels, slugify_label
)
from .chart_renderer import ChartRenderer


class HTMLReportGenerator:
    """Generates interactive HTML score reports with ECharts."""

    def __init__(self, instrument_config: Optional[Dict[str, Any]] = None):
        """Initialize the HTML report generator.

        Args:
            instrument_config: Instrument configuration dict.
                               Loaded from instrument_config.json if not provided.
        """
        if instrument_config is None:
            instrument_config = load_instrument_config()

        self.config = instrument_config
        self._table_counter = 0
        self._figure_counter = 0
        self._section_counter = 0

        # All values from config
        fmt = self.config['formatting']
        self.instrument_name = self.config['instrument_name']
        self.instrument_full_name = self.config.get('instrument_full_name', self.instrument_name)
        self.instrument_reference = self.config.get('instrument_reference', '')
        self.instrument_description = self.config.get('instrument_description', '')
        self.response_format = self.config.get('response_format', '')
        self.administration_format = self.config.get('administration_format', '')
        self.norms = self.config.get('norms', '')
        self.num_items = self.config['num_items']
        self.disclaimer_text = self.config.get('disclaimer_text', '')
        self.chart_font = fmt.get('font', 'Times New Roman')
        self.base_font_size = fmt.get('base_font_size', 12)
        self.html_max_width = fmt.get('html_max_width', '1280px')

        # Validation threshold derived from config
        self.valid_completion_threshold = 1.0 - self.config['max_missing_threshold']

        # Config-driven elevation labels
        self.elevated_labels = get_elevated_labels(self.config)
        self.cutoff_labels = get_all_cutoff_labels(self.config)
        self.category_colors = fmt['chart_colors']
        self.domain_definitions = fmt['domain_definitions']
        self.chart_config = fmt['chart']
        self.validity_chart_colors = fmt['validity_chart_colors']
        self.validity_subcategories = self.config['validity_subcategories']

        # Shared chart renderer for config generation
        self._chart_renderer = ChartRenderer(instrument_config=self.config)

        # Derive scale order from categories
        self.scale_order = {}
        for cat in get_substantive_categories(self.config):
            self.scale_order[cat['title']] = cat['scales']

        # Get validity category
        val_cat = get_validity_category(self.config)
        self.validity_scales = val_cat['scales'] if val_cat else []

        # Substantive categories for generating scale tables
        self.substantive_categories = get_substantive_categories(self.config)

    def generate_html_report(self, calculation_results: Dict[str, Any],
                           validation_report: Dict[str, Any],
                           output_path: str,
                           client_info=None,
                           narratives=None) -> str:
        """
        Generate a standalone HTML report with interactive ECharts.

        Args:
            calculation_results: Results from ScoreCalculator
            validation_report: Results from ScoreValidator
            output_path: Path for output .html file
            client_info: Optional ClientInfo instance for interpretive reports
            narratives: Optional dict of narrative strings keyed by category

        Returns:
            Path to generated report
        """
        # Reset counters for each report
        self._table_counter = 0
        self._figure_counter = 0
        self._section_counter = 0

        # Generate all HTML sections
        client_info_section_html = ""
        if client_info:
            client_info_section_html = self._generate_client_info_section_html(client_info)

        test_info_html = self._generate_test_info_html(calculation_results, validation_report, client_info)
        test_administered_html = self._generate_test_administered_html()
        validity_html = self._generate_validity_html(validation_report, calculation_results)
        scales_html = self._generate_scales_html(calculation_results, narratives)
        summary_html = self._generate_summary_html(calculation_results)
        appendix_a_html = self._generate_appendix_a_html(calculation_results)

        # Narrative-specific sections
        integration_html = ""
        treatment_html = ""
        narrative_summary_html = ""
        signature_html = ""
        if narratives:
            if 'integration' in narratives:
                integration_html = self._generate_narrative_section_html(
                    narratives.get('integration', ''), 'Profile Integration', 'profile-integration'
                )
            if 'treatment' in narratives:
                treatment_html = self._generate_narrative_section_html(
                    narratives.get('treatment', ''), 'Treatment Recommendations', 'treatment-recommendations'
                )
            if 'summary' in narratives:
                narrative_summary_html = self._generate_narrative_html(
                    narratives['summary']
                )
        if client_info:
            signature_html = self._generate_signature_block_html(client_info)

        # Add validity narrative if present
        validity_narrative_html = ""
        if narratives and 'validity' in narratives:
            validity_narrative_html = self._generate_narrative_html(narratives['validity'])

        # Generate ECharts configurations via shared chart renderer
        scale_scores = calculation_results['scale_scores']
        combined_chart_config = json.dumps(
            self._chart_renderer.generate_combined_chart_config(scale_scores), indent=2
        )
        domain_chart_configs = {
            name: json.dumps(config, indent=2)
            for name, config in self._chart_renderer.generate_domain_chart_configs(scale_scores).items()
        }
        validity_chart_configs = {
            name: json.dumps(config, indent=2)
            for name, config in self._chart_renderer.generate_validity_chart_configs(scale_scores).items()
        }

        # PAI-specific profile charts
        pai_full_scale_html = ""
        pai_subscale_html = ""
        pai_full_scale_config = "null"
        pai_subscale_config = "null"
        if self.instrument_name == 'PAI':
            pai_fs_raw = self._chart_renderer.generate_pai_full_scale_config(scale_scores)
            pai_sub_raw = self._chart_renderer.generate_pai_subscale_config(scale_scores)

            # Extract table metadata before JSON serialization
            pai_fs_table = pai_fs_raw.pop('_pai_table', {})
            pai_sub_table = pai_sub_raw.pop('_pai_subscale_table', {})

            pai_full_scale_config = json.dumps(pai_fs_raw, indent=2)
            pai_subscale_config = json.dumps(pai_sub_raw, indent=2)

            pai_full_scale_html = self._generate_pai_full_scale_html(pai_fs_table)
            pai_subscale_html = self._generate_pai_subscale_html(pai_sub_table)

        # Embed score data as JSON
        score_data_json = json.dumps({
            'test_id': calculation_results['test_id'],
            'test_date': calculation_results['test_date'],
            'examinee_id': calculation_results['examinee_id'],
            'scale_scores': calculation_results['scale_scores']
        }, indent=2)

        # Build complete HTML
        html_content = self._build_html_template(
            calculation_results=calculation_results,
            test_info_html=test_info_html,
            test_administered_html=test_administered_html,
            validity_html=validity_html,
            scales_html=scales_html,
            summary_html=summary_html,
            combined_chart_config=combined_chart_config,
            domain_chart_configs=domain_chart_configs,
            validity_chart_configs=validity_chart_configs,
            score_data_json=score_data_json,
            client_info_section_html=client_info_section_html,
            validity_narrative_html=validity_narrative_html,
            integration_html=integration_html,
            treatment_html=treatment_html,
            narrative_summary_html=narrative_summary_html,
            signature_html=signature_html,
            appendix_a_html=appendix_a_html,
            pai_full_scale_html=pai_full_scale_html,
            pai_subscale_html=pai_subscale_html,
            pai_full_scale_config=pai_full_scale_config,
            pai_subscale_config=pai_subscale_config,
        )

        # Save to file
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_content, encoding='utf-8')

        return str(output_path)

    def _build_html_template(self, calculation_results: Dict[str, Any],
                           test_info_html: str, test_administered_html: str,
                           validity_html: str,
                           scales_html: str, summary_html: str,
                           combined_chart_config: str,
                           domain_chart_configs: Dict[str, str],
                           validity_chart_configs: Dict[str, str],
                           score_data_json: str,
                           client_info_section_html: str = "",
                           validity_narrative_html: str = "",
                           integration_html: str = "",
                           treatment_html: str = "",
                           narrative_summary_html: str = "",
                           signature_html: str = "",
                           appendix_a_html: str = "",
                           pai_full_scale_html: str = "",
                           pai_subscale_html: str = "",
                           pai_full_scale_config: str = "null",
                           pai_subscale_config: str = "null") -> str:
        """Build the complete HTML document."""

        test_id = calculation_results['test_id']
        is_interpretive = bool(integration_html or treatment_html)
        report_title = f"{self.instrument_name} Interpretive Report" if is_interpretive else f"{self.instrument_name} Score Report"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report_title} - {test_id}</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
    <style>
        {self._get_css_styles()}
    </style>
</head>
<body>
    <div id="report-content">
        <h1>{report_title}</h1>

        {client_info_section_html}

        {test_info_html}

        {test_administered_html}

        {validity_html}
        {validity_narrative_html}

        {pai_full_scale_html}
        {pai_subscale_html}

        <section id="validity-graphs">
            <h2>Validity Scale Visualization</h2>
            <p class="graph-description">
                Interactive visualization of validity scales organized by category.
                Hover over data points for details.
            </p>

            {self._generate_chart_divs(self.validity_subcategories.keys(), 'Validity Scales')}
        </section>

        {scales_html}

        <section id="graphs">
            <h2>Profile Visualization</h2>
            <p class="graph-description">
                Interactive visualization of score elevations across all scales.
                Hover over data points for details. Click legend items to show/hide categories.
                Use mouse wheel to zoom, drag to pan.
            </p>
            <p class="figure-label"><strong>Figure {self._next_figure()}.</strong> <em>{self.instrument_name} Combined Profile Graph</em></p>
            <div id="chart-combined" class="chart-container"></div>

            <h2>Detailed Domain Graphs</h2>
            <p class="graph-description">
                The following graphs show scales organized by clinical dysfunction domains.
                Each domain displays relevant scale hierarchy levels
                with hierarchical styling (larger markers = higher-order scales).
            </p>

            {self._generate_chart_divs(self.domain_definitions.keys(), 'Domain')}
        </section>

        {integration_html}
        {treatment_html}
        {narrative_summary_html}

        {summary_html}

        {signature_html}

        <div class="print-button-container">
            <button onclick="window.print()" class="print-button">
                Download as PDF
            </button>
            <p class="print-note">
                Tip: Use your browser's Print function (Ctrl+P or Cmd+P) and select "Save as PDF"
            </p>
        </div>

        <section id="disclaimer">
            <h2>Disclaimer</h2>
            <p class="disclaimer-text">{self.disclaimer_text}</p>
        </section>

        {appendix_a_html}

        <footer>
            <p>Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </footer>
    </div>

    <script>
        // Embedded score data
        const scoreData = {score_data_json};

        // Initialize validity charts
        {self._generate_chart_initializers(validity_chart_configs)}

        // Initialize combined profile chart
        const chartCombined = echarts.init(document.getElementById('chart-combined'));
        const combinedConfig = {combined_chart_config};

        // Add tooltip formatter
        combinedConfig.tooltip.formatter = function(params) {{
            return '<strong>' + params.seriesName + '</strong><br/>' +
                   'Scale: ' + params.data.name + ' - ' + params.data.scale_name + '<br/>' +
                   'Raw Score: ' + params.data.raw_score + '<br/>' +
                   'Range: ' + params.data.interpretive_range;
        }};

        chartCombined.setOption(combinedConfig);

        // Initialize domain charts
        {self._generate_chart_initializers(domain_chart_configs)}

        // Initialize PAI profile charts (if present)
        var paiFullScale = null;
        var paiSubscale = null;
        (function() {{
            var fsConfig = {pai_full_scale_config};
            if (fsConfig && fsConfig !== null) {{
                var el = document.getElementById('chart-pai-full-scale');
                if (el) {{
                    paiFullScale = echarts.init(el);
                    fsConfig.tooltip.formatter = function(params) {{
                        return '<strong>' + params.data.name + '</strong> - ' + params.data.scale_name + '<br/>' +
                               'Raw: ' + params.data.raw_score + '<br/>' +
                               'T: ' + params.value + '<br/>' +
                               params.data.interpretive_range;
                    }};
                    paiFullScale.setOption(fsConfig);
                }}
            }}
            var subConfig = {pai_subscale_config};
            if (subConfig && subConfig !== null) {{
                var el2 = document.getElementById('chart-pai-subscale');
                if (el2) {{
                    paiSubscale = echarts.init(el2);
                    subConfig.tooltip.formatter = function(params) {{
                        return '<strong>' + params.data.name + '</strong> - ' + params.data.scale_name + '<br/>' +
                               'Raw: ' + params.data.raw_score + '<br/>' +
                               'T: ' + params.value[0] + '<br/>' +
                               params.data.interpretive_range;
                    }};
                    paiSubscale.setOption(subConfig);
                }}
            }}
        }})();

        // Handle window resize
        window.addEventListener('resize', function() {{
            {self._generate_resize_code(self.validity_subcategories.keys())}
            chartCombined.resize();
            if (paiFullScale) paiFullScale.resize();
            if (paiSubscale) paiSubscale.resize();
            {self._generate_resize_code(self.domain_definitions.keys())}
        }});
    </script>
</body>
</html>"""
        return html

    def _get_css_styles(self) -> str:
        """Get embedded CSS styles for the report (APA 7th Edition format)."""
        font = self.chart_font
        fsize = self.base_font_size
        chart_height = self.chart_config.get('height', '500px')
        css = """
        * {
            box-sizing: border-box;
        }

        body {
            font-family: '__FONT__', serif;
            font-size: __FSIZE__pt;
            line-height: 1.15;
            max-width: __MAXWIDTH__;
            margin: 0 auto;
            padding: 1in;
            background-color: #fff;
            color: #000;
        }

        #report-content {
            background-color: white;
            padding: 0;
        }

        /* APA Level 1: Centered, Bold, Title Case */
        h1 {
            text-align: center;
            font-weight: bold;
            font-size: __FSIZE__pt;
            color: #000;
            margin-top: 0;
            margin-bottom: 12pt;
        }

        /* APA Level 2: Flush Left, Bold, Title Case */
        h2 {
            text-align: left;
            font-weight: bold;
            font-size: __FSIZE__pt;
            color: #000;
            margin-top: 24pt;
            margin-bottom: 12pt;
        }

        /* APA Level 3: Flush Left, Bold Italic, Title Case */
        h3 {
            text-align: left;
            font-weight: bold;
            font-style: italic;
            font-size: __FSIZE__pt;
            color: #000;
            margin-top: 18pt;
            margin-bottom: 12pt;
        }

        p {
            margin: 0 0 12pt 0;
        }

        section {
            margin-bottom: 24pt;
        }

        /* APA Tables */
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 6pt 0 12pt 0;
            border-top: 2px solid #000;
            border-bottom: 2px solid #000;
            font-size: 10pt;
        }

        th, td {
            padding: 4pt 10pt;
            text-align: left;
            border: none;
            font-weight: normal;
        }

        thead {
            border-bottom: 1px solid #000;
        }

        th {
            font-weight: normal;
            font-size: 11pt;
            color: #000;
            background-color: transparent;
        }

        .section-summary {
            margin: 6pt 0 12pt 0;
            font-size: __FSIZE__pt;
            line-height: 1.5;
        }

        .table-label {
            margin-bottom: 2pt;
            font-size: __FSIZE__pt;
        }

        .figure-label {
            margin-bottom: 4pt;
            font-size: __FSIZE__pt;
        }

        .elevated { }

        .status-valid {
            font-weight: bold;
        }

        .status-warning {
            font-weight: bold;
            font-style: italic;
        }

        .status-invalid {
            font-weight: bold;
            text-decoration: underline;
        }

        .chart-container {
            width: 100%;
            height: __CHART_HEIGHT__;
            margin: 18pt 0;
        }

        .graph-description {
            font-style: italic;
            margin-bottom: 12pt;
        }

        .print-button-container {
            text-align: center;
            margin: 24pt 0;
        }

        .print-button {
            padding: 10pt 30pt;
            font-family: '__FONT__', serif;
            font-size: __FSIZE__pt;
            background-color: #000;
            color: #fff;
            border: none;
            cursor: pointer;
        }

        .print-button:hover {
            background-color: #333;
        }

        .print-note {
            font-size: 10pt;
            margin-top: 6pt;
        }

        .disclaimer-text {
            white-space: pre-line;
            font-size: 10pt;
            padding: 12pt;
            border: 1px solid #000;
            margin: 12pt 0;
        }

        .appendix-tables {
            display: flex;
            gap: 24pt;
        }
        .appendix-tables table {
            flex: 1;
        }

        footer {
            text-align: center;
            font-size: 10pt;
            margin-top: 24pt;
            padding-top: 12pt;
            border-top: 1px solid #000;
        }

        ul {
            margin: 6pt 0;
            padding-left: 0.5in;
        }

        li {
            margin: 3pt 0;
        }

        hr.section-divider {
            border: none;
            border-top: 2px solid #000;
            margin: 24pt 0;
        }

        tr.row-divider td {
            border-bottom: 1px solid #000;
        }

        .report-section {
            margin-bottom: 12pt;
        }

        .interpretation-narrative {
            padding: 0;
            margin: 12pt 0 18pt 0;
        }

        .interpretation-narrative p {
            text-indent: 0;
            margin: 0 0 12pt 0;
        }

        .profile-integration {
            padding: 0;
            margin: 18pt 0;
        }

        .treatment-recommendations {
            padding: 0;
            margin: 18pt 0;
        }

        .treatment-recommendations ol {
            padding-left: 0.5in;
        }

        .treatment-recommendations li {
            margin: 6pt 0;
        }

        .signature-block {
            margin-top: 48pt;
            padding-top: 12pt;
            border-top: 1px solid #000;
        }

        .signature-block .signature-line {
            display: flex;
            justify-content: space-between;
            margin-top: 36pt;
        }

        .signature-block .signature-entry {
            text-align: center;
            width: 45%;
        }

        .signature-block .signature-entry .line {
            border-top: 1px solid #000;
            margin-bottom: 4pt;
            padding-top: 4pt;
        }

        .signature-block .signature-entry .name {
            font-weight: bold;
        }

        .signature-block .signature-entry .credentials {
            font-size: 10pt;
        }

        .elevation-badge {
            display: inline;
            font-size: 10pt;
            font-weight: normal;
        }

        @media print {
            body {
                padding: 1in;
            }

            .print-button-container {
                display: none;
            }

            .chart-container {
                page-break-inside: avoid;
                height: 450px;
            }

            h2 {
                page-break-after: avoid;
            }

            section {
                page-break-inside: avoid;
            }

            .interpretation-narrative {
                page-break-inside: avoid;
            }

            .profile-integration,
            .treatment-recommendations {
                page-break-before: always;
            }

            .signature-block {
                page-break-before: always;
            }
        }

        @media (max-width: 768px) {
            body {
                padding: 12pt;
            }

            .chart-container {
                height: 350px;
            }

            table {
                font-size: 10pt;
            }

            th, td {
                padding: 4pt 6pt;
            }
        }
        """
        css = css.replace('__FONT__', font)
        css = css.replace('__FSIZE__', str(fsize))
        css = css.replace('__CHART_HEIGHT__', chart_height)
        css = css.replace('__MAXWIDTH__', self.html_max_width)
        return css

    def _generate_test_info_html(self, calc_results: Dict[str, Any],
                                 val_report: Dict[str, Any],
                                 client_info=None) -> str:
        """Generate test information section HTML."""
        completion = val_report['completion_rate']
        items_completed = self.num_items - val_report['missing_count']

        rows = []
        rows.append(f'                <tr><td>Assessment</td><td>{self.instrument_name}</td></tr>')
        rows.append(f'                <tr><td>Test Date</td><td>{calc_results["test_date"]}</td></tr>')
        rows.append(f'                <tr><td>Examinee ID</td><td>{calc_results["examinee_id"]}</td></tr>')
        rows.append(f'                <tr><td>Completion Rate</td><td>{completion:.1%} ({items_completed}/{self.num_items} items)</td></tr>')

        if client_info:
            if client_info.referral_source:
                rows.append(f'                <tr><td>Referral Source</td><td>{client_info.referral_source}</td></tr>')
            examiner_val = client_info.examiner_name
            if examiner_val and client_info.examiner_credentials:
                examiner_val = f"{examiner_val}, {client_info.examiner_credentials}"
            if examiner_val:
                rows.append(f'                <tr><td>Test Examiner</td><td>{examiner_val}</td></tr>')
            if client_info.setting:
                rows.append(f'                <tr><td>Setting</td><td>{client_info.setting}</td></tr>')

        rows_html = '\n'.join(rows)

        return f"""
        <section id="test-info">
            <h2>Test Information</h2>
            <table>
                <tbody>
{rows_html}
                </tbody>
            </table>
        </section>
        """

    def _generate_test_administered_html(self) -> str:
        """Generate Test Administered section HTML."""
        bullets = []
        if self.instrument_reference:
            bullets.append(f'<li>{self.instrument_reference}</li>')
        if self.num_items and self.response_format:
            bullets.append(f'<li>{self.num_items} items, {self.response_format} format</li>')
        if self.administration_format:
            bullets.append(f'<li>Administered via {self.administration_format}</li>')
        if self.norms:
            bullets.append(f'<li>Scoring referenced to {self.norms}</li>')

        bullets_html = '\n                '.join(bullets)

        description_html = ''
        if self.instrument_description:
            description_html = f'\n            <p>{self.instrument_description}</p>'

        return f"""
        <section id="test-administered">
            <h3>Test Administered</h3>
            <p><strong>{self.instrument_full_name}</strong></p>
            <ul>
                {bullets_html}
            </ul>{description_html}
        </section>
        """

    def _generate_validity_html(self, val_report: Dict[str, Any], calc_results: Dict[str, Any]) -> str:
        """Generate validity assessment section HTML with scale table."""
        status = val_report['is_valid']
        completion = val_report['completion_rate']

        if status and completion >= self.valid_completion_threshold:
            status_text = 'VALID'
            status_class = 'status-valid'
        elif status:
            status_text = 'VALID with concerns'
            status_class = 'status-warning'
        else:
            status_text = 'INVALID'
            status_class = 'status-invalid'

        warnings_html = ''
        if val_report['warnings']:
            warnings_list = ''.join([f'<li>{warning}</li>' for warning in val_report['warnings']])
            warnings_html = f"""
            <h3>Warnings:</h3>
            <ul>
                {warnings_list}
            </ul>
            """

        # Generate validity scales table
        scale_scores = calc_results['scale_scores']
        available_validity = [s for s in self.validity_scales if s in scale_scores]

        validity_table_html = ''
        if available_validity:
            rows_html = ''
            for scale_abbr in available_validity:
                scale_info = scale_scores[scale_abbr]
                row_class = 'elevated' if scale_info['interpretive_range'] in self.elevated_labels else ''
                t_display = scale_info.get('t_score_display', '')
                if not t_display:
                    t_display = "N/A"
                badge_class = self._get_badge_class(scale_info['interpretive_range'])
                interp_html = f'<span class="elevation-badge {badge_class}">{scale_info["interpretive_range"]}</span>'

                rows_html += f"""
                <tr class="{row_class}">
                    <td>{scale_abbr} - {scale_info['scale_name']}</td>
                    <td>{scale_info['raw_score']}</td>
                    <td>{t_display}</td>
                    <td>{scale_info['items_scored']}/{scale_info['total_items']}</td>
                    <td>{interp_html}</td>
                </tr>
                """

            self._table_counter += 1
            table_num = self._table_counter
            validity_table_html = f"""
            <h3>Validity Scale Scores</h3>
            <p class="table-label"><strong>Table {table_num}.</strong> <em>Validity Scale Scores</em></p>
            <table>
                <thead>
                    <tr>
                        <th>Scale</th>
                        <th>Raw Score</th>
                        <th>T-Score</th>
                        <th>Items Scored</th>
                        <th>Interpretation</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
            """

        # Generate summary for validity scales
        validity_summary_html = self._generate_section_summary(
            available_validity, scale_scores
        )

        return f"""
        <section id="validity">
            <h2>Protocol Validity</h2>
            {validity_summary_html}
            <p><strong>Status:</strong> <span class="{status_class}">{status_text}</span></p>
            {warnings_html}
            {validity_table_html}
        </section>
        """

    def _generate_scales_html(self, calc_results: Dict[str, Any],
                              narratives=None) -> str:
        """Generate scale scores tables HTML with optional narrative sections."""
        scale_scores = calc_results['scale_scores']
        sections = []

        # Data-driven loop over substantive categories from config
        for category in self.substantive_categories:
            sections.append(self._generate_scale_table_html(
                category['title'], category['scales'], scale_scores
            ))
            if narratives and category['key'] in narratives:
                sections.append(self._generate_narrative_html(narratives[category['key']]))

        return '\n'.join(sections)

    def _generate_section_summary(self, scale_list: List[str],
                                  scale_scores: Dict[str, Any]) -> str:
        """Generate a brief summary paragraph for a scale section."""
        available = [s for s in scale_list if s in scale_scores]
        if not available:
            return ""

        # Bucket scales by their interpretive range label (config-driven)
        buckets = {}
        for label in self.cutoff_labels:
            buckets[label] = []

        for abbr in available:
            info = scale_scores[abbr]
            r = info['interpretive_range']
            t = info.get('t_score_display', '')
            display = f"{abbr} (T={t})" if t else abbr
            if r in buckets:
                buckets[r].append(display)
            else:
                buckets.setdefault(r, []).append(display)

        parts = []
        baseline_label = self.cutoff_labels[0] if self.cutoff_labels else None
        has_elevated = False

        # Report elevated labels from highest to lowest (reverse order)
        for label in reversed(self.cutoff_labels):
            if label == baseline_label:
                continue
            scales_in_bucket = buckets.get(label, [])
            if scales_in_bucket:
                has_elevated = True
                parts.append(f"{label} elevations were observed on "
                             f"{self._join_list(scales_in_bucket)}.")

        # Report normal/baseline
        normal = buckets.get(baseline_label, []) if baseline_label else []
        if normal and not has_elevated:
            parts.append(f"All scales in this section fell within normal limits.")
        elif normal:
            count = len(normal)
            if count <= 3:
                parts.append(f"{self._join_list(normal)} fell within normal limits.")
            else:
                parts.append(f"The remaining {count} scales fell within normal limits.")

        if not parts:
            return ""

        return f'<p class="section-summary">{" ".join(parts)}</p>'

    def _join_list(self, items: List[str]) -> str:
        """Join a list of items with commas and 'and'."""
        if len(items) == 1:
            return items[0]
        elif len(items) == 2:
            return f"{items[0]} and {items[1]}"
        else:
            return ", ".join(items[:-1]) + f", and {items[-1]}"

    def _generate_scale_table_html(self, category_name: str,
                                   scale_list: List[str],
                                   scale_scores: Dict[str, Any]) -> str:
        """Generate HTML table for a category of scales with T-score column."""
        available_scales = [s for s in scale_list if s in scale_scores]

        if not available_scales:
            return f"""
            <section>
                <h2>{category_name}</h2>
                <p>No scales available in this category.</p>
            </section>
            """

        summary_html = self._generate_section_summary(scale_list, scale_scores)

        self._table_counter += 1
        table_num = self._table_counter

        rows_html = ''
        for scale_abbr in available_scales:
            scale_info = scale_scores[scale_abbr]
            interp_range = scale_info['interpretive_range']
            t_display = scale_info.get('t_score_display', '')
            if not t_display:
                t_display = "N/A"
            interp_html = f'<span class="elevation-badge">{interp_range}</span>'

            rows_html += f"""
                <tr>
                    <td>{scale_abbr} - {scale_info['scale_name']}</td>
                    <td>{scale_info['raw_score']}</td>
                    <td>{t_display}</td>
                    <td>{scale_info['items_scored']}/{scale_info['total_items']}</td>
                    <td>{interp_html}</td>
                </tr>
            """

        return f"""
        <section>
            <h2>{category_name}</h2>
            {summary_html}
            <p class="table-label"><strong>Table {table_num}.</strong> <em>{category_name}</em></p>
            <table>
                <thead>
                    <tr>
                        <th>Scale</th>
                        <th>Raw Score</th>
                        <th>T-Score</th>
                        <th>Items Scored</th>
                        <th>Interpretation</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </section>
        """

    def _get_badge_class(self, interpretive_range: str) -> str:
        """Get CSS badge class for an interpretive range (auto-derived from label)."""
        return f'badge-{slugify_label(interpretive_range)}'

    def _generate_client_info_section_html(self, client_info) -> str:
        """Generate client information section."""
        section_num = self._next_section()

        fields = [
            ('Client Name', client_info.client_name),
            ('Date of Birth', client_info.dob),
            ('Age', str(client_info.age) if client_info.age else ''),
            ('Sex', client_info.sex),
            ('Education', client_info.education),
            ('Marital Status', client_info.marital_status),
        ]

        rows = []
        visible = [(l, v) for l, v in fields if v]
        for i, (label, value) in enumerate(visible):
            cls = ' class="row-divider"' if i == len(visible) - 1 else ''
            rows.append(f'                    <tr{cls}><td>{label}</td><td>{value}</td></tr>')

        rows_html = '\n'.join(rows)

        table_html = f"""
            <h3>Identifying Information</h3>
            <table>
                <tbody>
{rows_html}
                </tbody>
            </table>"""

        referral_html = ""
        if client_info.referral_question:
            referral_html = f"""
            <h3>Reason for Referral</h3>
            <p>{client_info.referral_question}</p>"""

        background_html = ""
        if client_info.background:
            background_html = f"""
            <h3>Background Information</h3>
            <p>{client_info.background}</p>"""

        return f"""
        <hr class="section-divider">
        <section class="report-section">
            <h2>Section {section_num}: Client Information</h2>
            {table_html}
            {referral_html}
            {background_html}
        </section>
        <hr class="section-divider">
        """

    def _clean_narrative_text(self, text: str) -> str:
        """Clean markdown artifacts from LLM-generated narrative text."""
        lines = text.strip().split('\n')
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if re.match(r'^#{1,3}\s', stripped):
                continue
            cleaned.append(line)
        text = '\n'.join(cleaned)

        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'^\s*-\s+', '&nbsp;&nbsp;&nbsp;', text, flags=re.MULTILINE)

        return text

    def _paragraph_to_html(self, text: str) -> str:
        """Convert a single paragraph/block to HTML."""
        stripped = text.strip()
        if not stripped:
            return ''
        return f'<p>{stripped}</p>'

    def _generate_narrative_html(self, narrative_text: str, title: str = "") -> str:
        """Wrap narrative text in a styled div."""
        cleaned = self._clean_narrative_text(narrative_text)
        paragraphs = cleaned.strip().split('\n\n')
        p_html = '\n'.join(self._paragraph_to_html(p) for p in paragraphs if p.strip())

        title_html = f'<h2>{title}</h2>' if title else ''

        return f"""
        <div class="interpretation-narrative">
            {title_html}
            {p_html}
        </div>
        """

    def _generate_narrative_section_html(self, narrative_text: str,
                                         title: str, css_class: str) -> str:
        """Generate a narrative section (integration, treatment, etc.)."""
        cleaned = self._clean_narrative_text(narrative_text)
        paragraphs = cleaned.strip().split('\n\n')
        p_html = '\n'.join(self._paragraph_to_html(p) for p in paragraphs if p.strip())

        return f"""
        <section class="{css_class}">
            <h2>{title}</h2>
            {p_html}
        </section>
        """

    def _generate_signature_block_html(self, client_info) -> str:
        """Generate examiner/supervisor signature block."""
        examiner_name = client_info.examiner_name or "____________________"
        examiner_creds = client_info.examiner_credentials or ""
        supervisor_name = client_info.supervisor_name or "____________________"
        supervisor_creds = client_info.supervisor_credentials or ""

        return f"""
        <div class="signature-block">
            <div class="signature-line">
                <div class="signature-entry">
                    <div class="line">&nbsp;</div>
                    <div class="name">{examiner_name}</div>
                    <div class="credentials">{examiner_creds}</div>
                    <div>Examiner</div>
                </div>
                <div class="signature-entry">
                    <div class="line">&nbsp;</div>
                    <div class="name">{supervisor_name}</div>
                    <div class="credentials">{supervisor_creds}</div>
                    <div>Supervisor</div>
                </div>
            </div>
        </div>
        """

    def _generate_summary_html(self, calc_results: Dict[str, Any]) -> str:
        """Generate summary section HTML."""
        summary = calc_results['summary']

        return f"""
        <section id="summary">
            <h2>Summary</h2>
            <p><strong>Total scales:</strong> {summary['total_scales']}</p>
            <p><strong>Elevated scales:</strong> {summary['elevated_scales_count']}</p>
        </section>
        """

    def _generate_pai_full_scale_html(self, table_data: Dict) -> str:
        """Generate HTML section for PAI Full Scale Profile chart with data table."""
        if not table_data:
            return ""

        scale_order = table_data['scale_order']
        raw_row = table_data['raw_row']
        t_row = table_data['t_row']
        pct_row = table_data['pct_row']

        # Build table header and rows
        scale_cells = ''.join(f'<th>{s}</th>' for s in scale_order)
        raw_cells = ''.join(f'<td>{v}</td>' for v in raw_row)
        t_cells = ''.join(f'<td>{v}</td>' for v in t_row)
        pct_cells = ''.join(f'<td>{v}</td>' for v in pct_row)

        fig_num = self._next_figure()

        return f"""
        <section id="pai-full-scale-profile" style="page-break-before:always;">
            <h2>PAI Full Scale Profile</h2>
            <p class="figure-label"><strong>Figure {fig_num}.</strong> <em>PAI Full Scale Profile</em></p>
            <div id="chart-pai-full-scale" style="width:100%; height:800px;"></div>
            <table class="pai-profile-table" style="font-size:9pt; text-align:center; margin-top:12pt;">
                <thead>
                    <tr><th style="text-align:left;">Scale</th>{scale_cells}</tr>
                </thead>
                <tbody>
                    <tr><td style="text-align:left; font-weight:bold;">Raw</td>{raw_cells}</tr>
                    <tr><td style="text-align:left; font-weight:bold;">T</td>{t_cells}</tr>
                    <tr><td style="text-align:left; font-weight:bold;">% complete</td>{pct_cells}</tr>
                </tbody>
            </table>
            <p style="font-size:9pt; margin-top:6pt;">
                <em>Note.</em> Plotted T scores are based on a U.S. Census-matched standardization sample of 1,000 normal adults.
                Dashed red line indicates T = 70 (clinical significance threshold).
            </p>
        </section>
        """

    def _generate_pai_subscale_html(self, table_data: Dict) -> str:
        """Generate HTML section for PAI Subscale Profile — chart only, table in y-axis labels."""
        if not table_data:
            return ""

        fig_num = self._next_figure()

        return f"""
        <section id="pai-subscale-profile" style="page-break-before:always;">
            <h2>PAI Subscale Profile</h2>
            <p class="figure-label"><strong>Figure {fig_num}.</strong> <em>PAI Subscale Profile</em></p>
            <div id="chart-pai-subscale" style="width:100%; height:800px;"></div>
            <p style="font-size:9pt; margin-top:6pt;">
                <em>Note.</em> Plotted T scores are based on a U.S. Census-matched standardization sample of 1,000 normal adults.
            </p>
        </section>
        """

    def _generate_appendix_a_html(self, calc_results: Dict[str, Any]) -> str:
        """Generate Appendix A — Scale Name Abbreviations as two side-by-side tables."""
        scale_scores = calc_results['scale_scores']
        items = list(scale_scores.items())
        mid = (len(items) + 1) // 2
        left_items = items[:mid]
        right_items = items[mid:]

        def build_rows(item_list):
            return ''.join(
                f'<tr><td>{abbr}</td><td>{info["scale_name"]}</td></tr>'
                for abbr, info in item_list
            )

        return f"""
        <section id="appendix-a">
            <h2>Appendix A</h2>
            <p><em>Scale Name Abbreviations</em></p>
            <div class="appendix-tables">
                <table>
                    <thead><tr><th>Abbreviation</th><th>Scale</th></tr></thead>
                    <tbody>{build_rows(left_items)}</tbody>
                </table>
                <table>
                    <thead><tr><th>Abbreviation</th><th>Scale</th></tr></thead>
                    <tbody>{build_rows(right_items)}</tbody>
                </table>
            </div>
        </section>
        """

    def _next_figure(self) -> int:
        """Increment and return the next figure number."""
        self._figure_counter += 1
        return self._figure_counter

    def _next_section(self) -> str:
        """Increment and return the next section Roman numeral."""
        self._section_counter += 1
        numerals = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X']
        idx = self._section_counter - 1
        return numerals[idx] if idx < len(numerals) else str(self._section_counter)

    def _generate_chart_divs(self, names, suffix: str) -> str:
        """Generate HTML divs for a set of charts."""
        parts = []
        for name in names:
            self._figure_counter += 1
            chart_id = self._chart_renderer.name_to_chart_id(name)
            parts.append(
                f'<p class="figure-label"><strong>Figure {self._figure_counter}.</strong> '
                f'<em>{name} {suffix}</em></p>\n'
                f'            <div id="{chart_id}" class="chart-container"></div>'
            )
        return '\n            '.join(parts)

    def _generate_chart_initializers(self, chart_configs: Dict[str, str]) -> str:
        """Generate JavaScript code to initialize a set of ECharts instances."""
        js_code = []
        for name, config_json in chart_configs.items():
            chart_id = self._chart_renderer.name_to_chart_id(name)
            var_name = chart_id.replace('-', '_')
            config_var = f'{var_name}_config'
            js_code.append(f"""
        const {var_name} = echarts.init(document.getElementById('{chart_id}'));
        const {config_var} = {config_json};
        {config_var}.tooltip.formatter = function(params) {{
            return '<strong>' + params.seriesName + '</strong><br/>' +
                   'Scale: ' + params.data.name + ' - ' + params.data.scale_name + '<br/>' +
                   'Raw Score: ' + params.data.raw_score + '<br/>' +
                   'Range: ' + params.data.interpretive_range;
        }};
        {var_name}.setOption({config_var});""")

        return '\n'.join(js_code)

    def _generate_resize_code(self, names) -> str:
        """Generate JavaScript code to resize a set of charts."""
        chart_vars = [self._chart_renderer.name_to_chart_id(name).replace('-', '_')
                      for name in names]
        resize_calls = '\n            '.join([f'if (typeof {var} !== "undefined") {var}.resize();' for var in chart_vars])
        return resize_calls
