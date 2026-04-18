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
        self.chart_font = fmt['font']
        self.base_font_size = fmt['base_font_size']
        self.html_max_width = fmt['html_max_width']

        # Validation threshold derived from config
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
        self.validity_category_key = val_cat['key'] if val_cat else 'validity'

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

        # Add validity narrative if present (key comes from config, e.g. 'validity_scales')
        validity_narrative_html = ""
        if narratives and self.validity_category_key in narratives:
            validity_narrative_html = self._generate_narrative_html(narratives[self.validity_category_key])
        elif not narratives:
            validity_narrative_html = '<p class="no-narrative"><em>Interpretive analysis was not requested for this report. Validity scale scores should be reviewed by a qualified clinician before interpreting substantive scales.</em></p>'

        # Generate ECharts configurations via shared chart renderer
        scale_scores = calculation_results['scale_scores']
        combined_chart_config = json.dumps(
            self._chart_renderer.generate_combined_chart_config(scale_scores), indent=2
        )
        domain_chart_configs = {
            name: json.dumps(config, indent=2)
            for name, config in self._chart_renderer.generate_domain_chart_configs(scale_scores).items()
        }
        # Only include validity subcategory charts that have elevated scales
        elevated_validity_subcats = {
            name: scales for name, scales in self.validity_subcategories.items()
            if any(
                is_elevated(self.config, scale_scores[s]['interpretive_range'])
                for s in scales if s in scale_scores
            )
        }
        validity_chart_configs = {
            name: json.dumps(config, indent=2)
            for name, config in self._chart_renderer.generate_validity_chart_configs(scale_scores).items()
            if name in elevated_validity_subcats
        }

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
                           appendix_a_html: str = "") -> str:
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

        {validity_narrative_html}
        {validity_html}
        
        <section id="validity-graphs">
            {self._generate_chart_divs(validity_chart_configs.keys(), 'Validity Scales')}
        </section>

        <section id="graphs">
            <h2>Clinician Profile</h2>
            {narrative_summary_html}
            <p class="graph-description">
                Interactive visualization of score elevations across all scales.
                Hover over data points for details. Click legend items to show/hide categories.
                Use mouse wheel to zoom, drag to pan.
            </p>
            <p class="figure-label"><strong>Figure {self._next_figure()}.</strong> <em>{self.instrument_name} Combined Profile Graph</em></p>
            <div id="chart-combined" class="chart-container"></div>

            <h3>Detailed Domain Graphs</h3>
            <p class="graph-description">
                The following graphs show scales organized by clinical dysfunction domains.
                Each domain displays relevant scale hierarchy levels
                with hierarchical styling (larger markers = higher-order scales).
            </p>
            {self._generate_chart_divs(self.domain_definitions.keys(), 'Domain')}
        </section>

        {scales_html}

        {integration_html}
        {treatment_html}

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

        // Handle window resize
        window.addEventListener('resize', function() {{
            {self._generate_resize_code(validity_chart_configs.keys())}
            chartCombined.resize();
            {self._generate_resize_code(self.domain_definitions.keys())}
        }});
    </script>
</body>
</html>"""
        return html

    def _get_css_styles(self) -> str:
        """Load CSS styles from templates/apaformat.css and substitute dynamic values."""
        css_path = Path(__file__).resolve().parent.parent / 'templates' / 'apaformat.css'
        css = css_path.read_text()
        css = css.replace('__FONT__', self.chart_font)
        css = css.replace('__FSIZE__', str(self.base_font_size))
        css = css.replace('__CHART_HEIGHT__', self.chart_config['height'])
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

        bullets = []
        if self.instrument_reference:
            bullets.append(f'<li>{self.instrument_reference}</li>')
        if self.num_items and self.response_format:
            bullets.append(f'<li>{self.num_items} items, {self.response_format} format</li>')
        if self.administration_format:
            bullets.append(f'<li>Administered via {self.administration_format}</li>')

        bullets_html = '\n                '.join(bullets)

        description_html = ''
        if self.instrument_description:
            description_html = f'\n            <p>{self.instrument_description}</p>'

        return f"""
        <section id="test-info">
            <h2>Test Information</h2>
            <p class="subsection-heading"><strong>Test Administered</strong></p>
            <p>The {self.instrument_full_name} ({self.instrument_name}) was administered to evaluate the personality and psychopathology correlates of the client. {self.instrument_description}</p>
            <p class="table-label"><strong>Test Information</strong></p>
            <table>
                <tbody>
{rows_html}
                </tbody>
            </table>
        </section>
        """

    def _generate_test_administered_html(self) -> str:
        """No longer generates a separate section — content merged into test info."""
        return ""

    def _generate_validity_html(self, val_report: Dict[str, Any], calc_results: Dict[str, Any]) -> str:
        """Generate validity assessment section HTML with scale table."""
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
            <p class="subsection-heading"><strong>Validity Scale Scores</strong></p>
            <p class="table-label"><strong>Table {table_num}.</strong> Validity Scale Scores</p>
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

        return f"""
        <section id="validity">
            <h2>Protocol Validity</h2>
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
            <p class="subsection-heading"><strong>Client Information</strong></p>
            <table>
                <tbody>
{rows_html}
                </tbody>
            </table>"""

        referral_html = ""
        if client_info.referral_question:
            referral_html = f"""
            <p class="subsection-heading"><strong>Reason for Referral</strong></p>
            <p>{client_info.referral_question}</p>"""

        background_html = ""
        if client_info.background:
            background_html = f"""
            <p class="subsection-heading"><strong>Background Information</strong></p>
            <p>{client_info.background}</p>"""

        return f"""
        <section class="report-section">
            <h2>Client Information</h2>
            {table_html}
            {referral_html}
            {background_html}
        </section>
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
