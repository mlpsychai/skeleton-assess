"""
Chart Renderer

ECharts-only rendering engine for psychometric profile graphs.
Generates ECharts JSON configs and renders to PNG via Playwright
for DOCX embedding. Replaces matplotlib-based profile_graph.py.

All chart logic is centralized here — both html_report_generator.py
and report_generator.py consume this module.
"""

import json
import math
import re
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional

from .instrument_config import (
    load_instrument_config, get_validity_category, get_substantive_categories,
    get_elevated_labels, get_all_cutoff_labels, get_hierarchy_levels, get_fallback_category
)

# Playwright is optional — PNG export degrades gracefully
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class ChartRenderer:
    """Generates ECharts configs and renders to PNG for DOCX embedding."""

    def __init__(self, instrument_config: Optional[Dict[str, Any]] = None):
        """
        Initialize the chart renderer.

        Args:
            instrument_config: Instrument configuration dict.
                               Loaded from instrument_config.json if not provided.
        """
        if instrument_config is None:
            instrument_config = load_instrument_config()

        self.config = instrument_config
        fmt = self.config['formatting']

        self.instrument_name = self.config['instrument_name']
        self.chart_font = fmt['font']
        self.category_colors = fmt['chart_colors']
        self.domain_definitions = fmt['domain_definitions']
        self.chart_config = fmt['chart']
        self.validity_chart_colors = fmt['validity_chart_colors']
        self.validity_subcategories = self.config.get('validity_subcategories', {})

        # Config-driven elevation detection
        self.elevated_labels = get_elevated_labels(self.config)
        self.cutoff_labels = get_all_cutoff_labels(self.config)

        # Config-driven hierarchy and fallback
        self.hierarchy_levels = get_hierarchy_levels(self.config)
        self.fallback_category = get_fallback_category(self.config)

        # Chart font sizing
        self.chart_font_size = self.chart_config.get('chart_font_size', 16)
        self.png_font_scale = self.chart_config.get('chart_png_font_scale', 1.3)
        self._font_scale = 1.0  # active multiplier; set >1 for PNG rendering

        # Chart formatting from config
        self.symbol_size_normal = self.chart_config['symbol_size_normal']
        self.symbol_size_elevated = self.chart_config['symbol_size_elevated']
        self.line_width = self.chart_config['line_width']
        self.validity_line_width = self.chart_config['validity_line_width']
        self.grid_configs = self.chart_config['grid']
        raw_bands = self.chart_config['plot_bands']
        # Support both formats: list of floats (boundaries) or list of dicts
        if raw_bands and isinstance(raw_bands[0], (int, float)):
            # Convert boundary list [0.0, 0.33, 0.66, 1.0] to band dicts
            self.plot_bands = []
            for i in range(len(raw_bands) - 1):
                self.plot_bands.append({
                    'base': raw_bands[i],
                    'range': raw_bands[i + 1] - raw_bands[i]
                })
        else:
            self.plot_bands = raw_bands

        # Derive scale order from categories
        self.scale_order = {}
        for cat in get_substantive_categories(self.config):
            self.scale_order[cat['title']] = cat['scales']

        # Get validity scales
        val_cat = get_validity_category(self.config)
        self.validity_scales = val_cat['scales'] if val_cat else []

        # Substantive categories
        self.substantive_categories = get_substantive_categories(self.config)

    # ─── Public API ───────────────────────────────────────────────────

    def generate_combined_chart_config(self, scale_scores: Dict[str, Any]) -> Dict:
        """Generate ECharts config dict for combined profile graph."""
        categories = {}
        assigned_scales = set(self.validity_scales)

        for cat in self.substantive_categories:
            title = cat['title']
            if title in self.category_colors:
                categories[title] = cat['scales']
                assigned_scales.update(cat['scales'])

        # Remaining scales go into fallback category
        if self.fallback_category not in categories:
            categories[self.fallback_category] = []
        for scale_abbr in scale_scores:
            if scale_abbr not in assigned_scales:
                categories[self.fallback_category].append(scale_abbr)
        categories[self.fallback_category].sort()

        # Collect all scales in order
        all_x_labels = []
        for category_name, scale_list in categories.items():
            if not scale_list:
                continue
            available = [s for s in scale_list if s in scale_scores]
            if not available:
                continue
            if category_name in self.scale_order:
                ordered = [s for s in self.scale_order[category_name] if s in available]
            else:
                ordered = sorted(available)
            for scale_abbr in ordered:
                all_x_labels.append(scale_abbr)

        # Build series
        series_list = []
        for category_name, scale_list in categories.items():
            if not scale_list:
                continue
            available = [s for s in scale_list if s in scale_scores]
            if not available:
                continue

            series_data = []
            for scale_abbr in all_x_labels:
                if scale_abbr in scale_list and scale_abbr in scale_scores:
                    scale_info = scale_scores[scale_abbr]
                    plot_value = self._raw_score_to_plot_value(
                        scale_info['raw_score'], scale_info['total_items'],
                        scale_info['interpretive_range'],
                        t_score=scale_info.get('t_score')
                    )
                    elevated = scale_info['interpretive_range'] in self.elevated_labels
                    series_data.append({
                        'value': plot_value,
                        'name': scale_abbr,
                        'raw_score': scale_info['raw_score'],
                        'scale_name': scale_info['scale_name'],
                        'interpretive_range': scale_info['interpretive_range'],
                        'is_elevated': elevated,
                        'symbolSize': self.symbol_size_elevated
                    })
                else:
                    series_data.append(None)

            series_list.append({
                'name': category_name,
                'type': 'line',
                'data': series_data,
                'itemStyle': {'color': self.category_colors.get(category_name, '#000000')},
                'lineStyle': {'width': self.line_width},
                'symbol': 'circle',
                'connectNulls': False,
                'emphasis': {'focus': 'series'}
            })

        return {
            'title': {
                'text': f'{self.instrument_name} Profile Graph',
                'left': 'center',
                'textStyle': self._apa_text_style(bold=True)
            },
            'tooltip': {'trigger': 'item', 'textStyle': self._apa_text_style(self.chart_font_size - 2)},
            'legend': {
                'data': [cat for cat in categories.keys() if categories[cat]],
                'top': 30, 'type': 'scroll',
                'textStyle': self._apa_text_style(self.chart_font_size - 2)
            },
            'grid': {**self.grid_configs['combined'], 'top': '12%'},
            'xAxis': {
                'type': 'category', 'data': all_x_labels,
                'axisLabel': {**self._apa_text_style(self.chart_font_size - 2), 'rotate': 45},
                'axisLine': {'lineStyle': {'color': '#000'}},
                'axisTick': {'lineStyle': {'color': '#000'}},
                'name': f'{self.instrument_name} Scales',
                'nameLocation': 'middle', 'nameGap': 50,
                'nameTextStyle': self._apa_text_style(self.chart_font_size - 2, bold=True)
            },
            'yAxis': self._chart_y_axis(name_gap=50, data_max=self._max_series_value(series_list)),
            'series': series_list,
            'markLine': self._chart_mark_lines(),
            'toolbox': {
                'feature': {
                    'dataZoom': {'yAxisIndex': 'none'},
                    'restore': {},
                    'saveAsImage': {}
                }
            }
        }

    def generate_domain_chart_configs(self, scale_scores: Dict[str, Any]) -> Dict[str, Dict]:
        """Generate ECharts configs for domain-specific graphs."""
        domain_configs = {}
        for domain_name, domain_def in self.domain_definitions.items():
            config = self._generate_single_domain_config(domain_name, domain_def, scale_scores)
            if config:
                domain_configs[domain_name] = config
        return domain_configs

    def generate_validity_chart_configs(self, scale_scores: Dict[str, Any]) -> Dict[str, Dict]:
        """Generate ECharts configs for validity scale graphs."""
        validity_configs = {}
        for category_name, scale_list in self.validity_subcategories.items():
            color = self.validity_chart_colors.get(category_name, '#000000')
            category_def = {'scales': scale_list, 'color': color}
            config = self._generate_single_validity_config(category_name, category_def, scale_scores)
            if config:
                validity_configs[category_name] = config
        return validity_configs

    def generate_pai_full_scale_config(self, scale_scores: Dict[str, Any]) -> Dict:
        """Generate ECharts config for PAI Full Scale Profile chart.

        Vertical line chart showing all 22 full/standalone scales with T-scores,
        matching the PAR report layout: validity | clinical | treatment | interpersonal.
        """
        # PAI full scale order matching PAR report
        scale_order = [
            'ICN', 'INF', 'NIM', 'PIM',
            'SOM', 'ANX', 'ARD', 'DEP', 'MAN', 'PAR', 'SCZ', 'BOR', 'ANT', 'ALC', 'DRG',
            'AGG', 'SUI', 'STR', 'NON', 'RXR',
            'DOM', 'WRM'
        ]

        # Group boundaries for vertical dividers
        group_boundaries = [4, 15, 20]  # after PIM, after DRG, after RXR

        x_labels = []
        data_points = []
        for abbr in scale_order:
            x_labels.append(abbr)
            if abbr in scale_scores:
                s = scale_scores[abbr]
                t = s.get('t_score')
                data_points.append({
                    'value': t if t is not None else None,
                    'name': abbr,
                    'scale_name': s.get('scale_name', ''),
                    'raw_score': s.get('raw_score', ''),
                    'interpretive_range': s.get('interpretive_range', ''),
                    'symbol': 'circle',
                    'symbolSize': 10,
                    'label': {
                        'show': True,
                        'position': 'top',
                        'formatter': '{b}',
                        **self._apa_text_style(10),
                        'fontStyle': 'italic',
                    }
                })
            else:
                data_points.append(None)

        # Build raw/T/% complete rows for the data table (rendered in HTML, not ECharts)
        raw_row = []
        t_row = []
        pct_row = []
        for abbr in scale_order:
            if abbr in scale_scores:
                s = scale_scores[abbr]
                raw_row.append(str(s.get('raw_score', '')))
                t_val = s.get('t_score')
                t_row.append(str(t_val) if t_val is not None else 'N/A')
                prop = s.get('proportion_scored', 1.0)
                pct_row.append(str(round(prop * 100)))
            else:
                raw_row.append('—')
                t_row.append('—')
                pct_row.append('—')

        # Find max T for axis scaling
        max_t = max((p['value'] for p in data_points if p and p.get('value')), default=110)

        y_min = 30
        y_max = 110
        interval = 10
        if max_t > y_max:
            y_max = math.ceil((max_t + 5) / interval) * interval

        # Mark lines for reference
        mark_lines = {
            'data': [
                {'yAxis': 70, 'label': {'formatter': '70T', **self._apa_text_style(10)},
                 'lineStyle': {'type': 'dashed', 'color': '#FF0000', 'width': 1.5}}
            ],
            'silent': True,
            'symbol': 'none',
        }

        config = {
            'animation': False,
            'tooltip': {
                'trigger': 'item',
                'formatter': '',  # set by JS
            },
            'grid': {
                'left': '6%', 'right': '6%', 'bottom': '18%', 'top': '8%',
                'containLabel': True,
            },
            'xAxis': {
                'type': 'category',
                'data': x_labels,
                'axisLabel': {**self._apa_text_style(11), 'fontStyle': 'italic', 'interval': 0},
                'axisLine': {'lineStyle': {'color': '#000'}},
                'axisTick': {'alignWithLabel': True},
            },
            'yAxis': {
                'type': 'value',
                'name': 'T score',
                'nameLocation': 'end',
                'nameTextStyle': {**self._apa_text_style(11), 'fontStyle': 'italic'},
                'min': y_min,
                'max': y_max,
                'interval': interval,
                'axisLabel': self._apa_text_style(11),
                'axisLine': {'show': True, 'lineStyle': {'color': '#000'}},
                'splitLine': {'show': True, 'lineStyle': {'type': 'solid', 'color': '#ddd'}},
            },
            'series': [{
                'type': 'line',
                'data': data_points,
                'lineStyle': {'color': '#000', 'width': 2},
                'itemStyle': {'color': '#000'},
                'symbol': 'circle',
                'symbolSize': 10,
                'label': {'show': False},
                'markLine': mark_lines,
                'connectNulls': False,
            }],
        }

        # Store table data as metadata for HTML rendering
        config['_pai_table'] = {
            'scale_order': scale_order,
            'raw_row': raw_row,
            't_row': t_row,
            'pct_row': pct_row,
            'group_boundaries': group_boundaries,
        }

        return config

    def generate_pai_subscale_config(self, scale_scores: Dict[str, Any]) -> Dict:
        """Generate ECharts config for PAI Subscale Profile chart.

        Horizontal dot chart with subscales grouped by parent scale,
        matching the PAR report layout.
        """
        # Subscale groups in PAR report order
        subscale_groups = [
            ('SOM', ['SOM-C', 'SOM-S', 'SOM-H']),
            ('ANX', ['ANX-C', 'ANX-A', 'ANX-P']),
            ('ARD', ['ARD-O', 'ARD-P', 'ARD-T']),
            ('DEP', ['DEP-C', 'DEP-A', 'DEP-P']),
            ('MAN', ['MAN-A', 'MAN-G', 'MAN-I']),
            ('PAR', ['PAR-H', 'PAR-P', 'PAR-R']),
            ('SCZ', ['SCZ-P', 'SCZ-S', 'SCZ-T']),
            ('BOR', ['BOR-A', 'BOR-I', 'BOR-N', 'BOR-S']),
            ('ANT', ['ANT-A', 'ANT-E', 'ANT-S']),
            ('AGG', ['AGG-A', 'AGG-V', 'AGG-P']),
        ]

        # Build y-axis labels with integrated table info: "ABR   Name   Raw   T"
        # Blank spacer entries between groups for separator lines
        y_labels = []
        series_data = []
        spacer_indices = []

        for gi, (parent, subs) in enumerate(subscale_groups):
            group_points = []
            for abbr in subs:
                if abbr in scale_scores:
                    s = scale_scores[abbr]
                    t = s.get('t_score')
                    raw = s.get('raw_score', '')
                    name = s.get('scale_name', '')
                    t_disp = t if t is not None else 'N/A'
                    label = f"{abbr}   {name}   {raw}   {t_disp}"
                    y_labels.append(label)
                    group_points.append({
                        'value': [t if t is not None else None, label],
                        'name': abbr,
                        'scale_name': name,
                        'raw_score': raw,
                        'interpretive_range': s.get('interpretive_range', ''),
                    })
                else:
                    label = f"{abbr}   —   —"
                    y_labels.append(label)
                    group_points.append({'value': [None, label]})

            # Add blank spacer after each group except the last
            if gi < len(subscale_groups) - 1:
                spacer_indices.append(len(y_labels))
                y_labels.append('')

            series_data.append({
                'type': 'line',
                'data': group_points,
                'lineStyle': {'color': '#000', 'width': 1.5},
                'itemStyle': {'color': '#000'},
                'symbol': 'circle',
                'symbolSize': 8,
                'label': {'show': False},
                'connectNulls': False,
            })

        # Find max T for axis
        all_t = []
        for parent, subs in subscale_groups:
            for abbr in subs:
                if abbr in scale_scores:
                    t = scale_scores[abbr].get('t_score')
                    if t is not None:
                        all_t.append(t)
        max_t = max(all_t) if all_t else 110

        x_min = 30
        x_max = 110
        interval = 10
        if max_t > x_max:
            x_max = math.ceil((max_t + 5) / interval) * interval

        # Draw horizontal separator lines on the spacer rows
        separator_marks = []
        for idx in spacer_indices:
            separator_marks.append({
                'yAxis': idx,
                'lineStyle': {'type': 'solid', 'color': '#999', 'width': 1},
                'label': {'show': False},
            })

        if series_data and separator_marks:
            series_data[0]['markLine'] = {
                'data': separator_marks,
                'silent': True,
                'symbol': 'none',
            }

        config = {
            'animation': False,
            'tooltip': {
                'trigger': 'item',
                'formatter': '',  # set by JS
            },
            'grid': {
                'left': '3%', 'right': '5%', 'bottom': '5%', 'top': '3%',
                'containLabel': True,
            },
            'xAxis': {
                'type': 'value',
                'name': '',
                'min': x_min,
                'max': x_max,
                'interval': interval,
                'axisLabel': self._apa_text_style(11),
                'axisLine': {'show': True, 'lineStyle': {'color': '#000'}},
                'splitLine': {'show': True, 'lineStyle': {'type': 'solid', 'color': '#ddd'}},
                'position': 'bottom',
            },
            'yAxis': {
                'type': 'category',
                'data': y_labels,
                'axisLabel': {**self._apa_text_style(10), 'fontFamily': 'monospace'},
                'axisLine': {'show': True, 'lineStyle': {'color': '#000'}},
                'axisTick': {'show': False},
                'inverse': True,
            },
            'series': series_data,
        }

        # Store table data for HTML rendering (in correct top-to-bottom order)
        table_rows_ordered = []
        for parent, subs in subscale_groups:
            for abbr in subs:
                if abbr in scale_scores:
                    s = scale_scores[abbr]
                    t = s.get('t_score')
                    table_rows_ordered.append({
                        'abbr': abbr,
                        'name': s.get('scale_name', ''),
                        'raw': s.get('raw_score', ''),
                        't': t if t is not None else 'N/A',
                        'parent': parent,
                    })
                else:
                    table_rows_ordered.append({
                        'abbr': abbr, 'name': '', 'raw': '—', 't': '—', 'parent': parent,
                    })

        config['_pai_subscale_table'] = {
            'rows': table_rows_ordered,
            'subscale_groups': [(p, s) for p, s in subscale_groups],
        }

        return config

    def render_to_png(self, chart_config: Dict, output_path: str,
                      width: int = 900, height: int = 500) -> Optional[str]:
        """
        Render an ECharts config to a static PNG file via Playwright.

        Args:
            chart_config: ECharts option dict
            output_path: Path to save the PNG file
            width: Image width in pixels
            height: Image height in pixels

        Returns:
            Path to PNG file, or None if Playwright unavailable
        """
        if not PLAYWRIGHT_AVAILABLE:
            return None

        config_json = json.dumps(chart_config)

        html_content = f"""<!DOCTYPE html>
<html><head>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
</head><body>
<div id="chart" style="width:{width}px;height:{height}px;"></div>
<script>
var chart = echarts.init(document.getElementById('chart'));
chart.setOption({config_json});
</script>
</body></html>"""

        # Write temp HTML, render with Playwright
        with tempfile.NamedTemporaryFile(suffix='.html', mode='w', delete=False, encoding='utf-8') as f:
            f.write(html_content)
            temp_html = f.name

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={'width': width, 'height': height},
                                       device_scale_factor=2)
                page.goto(f'file://{temp_html}')
                page.wait_for_timeout(1000)  # Wait for ECharts to render
                page.locator('#chart').screenshot(path=output_path)
                browser.close()
            return output_path
        except Exception as e:
            print(f"Warning: Playwright rendering failed: {e}")
            return None
        finally:
            Path(temp_html).unlink(missing_ok=True)

    def render_all_to_png(self, scale_scores: Dict[str, Any],
                          output_dir: str) -> Dict[str, str]:
        """
        Render all charts (combined, domain, validity) to PNG files.

        Args:
            scale_scores: Scale scores dict from calculator
            output_dir: Directory to save PNG files

        Returns:
            Dict mapping chart name to PNG file path
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Scale up chart fonts for PNG rendering so text remains legible
        # after the image is scaled down to Inches(6.5) in the DOCX.
        self._font_scale = self.png_font_scale

        results = {}

        try:
            # Combined profile
            combined_config = self.generate_combined_chart_config(scale_scores)
            png_path = self.render_to_png(combined_config, str(output_dir / 'combined_profile.png'))
            if png_path:
                results['combined'] = png_path

            # Domain charts
            for domain_name, config in self.generate_domain_chart_configs(scale_scores).items():
                slug = self._name_to_slug(domain_name)
                png_path = self.render_to_png(config, str(output_dir / f'domain_{slug}.png'))
                if png_path:
                    results[f'domain_{slug}'] = png_path

            # Validity charts
            for cat_name, config in self.generate_validity_chart_configs(scale_scores).items():
                slug = self._name_to_slug(cat_name)
                png_path = self.render_to_png(config, str(output_dir / f'validity_{slug}.png'))
                if png_path:
                    results[f'validity_{slug}'] = png_path
        finally:
            self._font_scale = 1.0

        return results

    # ─── Helpers ──────────────────────────────────────────────────────

    def name_to_chart_id(self, name: str) -> str:
        """Convert a human-readable name to a valid HTML/JS chart ID."""
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        return f'chart-{slug}'

    def _name_to_slug(self, name: str) -> str:
        """Convert a name to a filesystem-safe slug."""
        return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')

    def _apa_text_style(self, size: int = None, bold: bool = False) -> Dict:
        """Return APA-compliant ECharts text style dict.

        Args:
            size: Font size in CSS pixels. Defaults to self.chart_font_size.
                  Multiplied by self._font_scale (>1 for PNG rendering).
            bold: Whether to apply bold weight.
        """
        if size is None:
            size = self.chart_font_size
        scaled = round(size * self._font_scale)
        style = {
            'fontFamily': self.chart_font,
            'fontSize': scaled,
            'color': '#000'
        }
        if bold:
            style['fontWeight'] = 'bold'
        return style

    def _max_series_value(self, series_list: List) -> Optional[float]:
        """Return the maximum plotted value across all series."""
        max_val = None
        for series in series_list:
            for point in series.get('data', []):
                if point is None:
                    continue
                val = point['value'] if isinstance(point, dict) else point
                if val is not None and (max_val is None or val > max_val):
                    max_val = val
        return max_val

    def _chart_mark_lines(self) -> Dict:
        """Build ECharts markLine config from chart reference lines."""
        ref_lines = self.chart_config.get('reference_lines', [])
        data = []
        for ref in ref_lines:
            data.append({
                'yAxis': ref['value'],
                'label': {**self._apa_text_style(self.chart_font_size - 4), 'formatter': ref['label']}
            })
        return {
            'data': data,
            'lineStyle': {'type': 'dashed', 'color': '#999'}
        }

    def _chart_y_axis(self, name_gap: int = 50, data_max: Optional[float] = None) -> Dict:
        """Build ECharts yAxis config from chart settings.

        If any plotted value exceeds the configured y_max, the axis maximum is
        extended (rounded up to the next interval boundary) so that all data
        points remain visible on the chart.
        """
        y_min = self.chart_config['y_min']
        y_max = self.chart_config['y_max']
        interval = self.chart_config['y_interval']

        if data_max is not None and data_max > y_max:
            # Round up to next value ending in 5 that exceeds data_max,
            # keeping consistent 10-unit tick spacing (25, 35, 45 ... 95, 105, 115 ...)
            y_max = math.ceil((data_max - 5) / interval) * interval + 5

        return {
            'type': 'value',
            'name': 'Estimated Score Position',
            'nameLocation': 'middle',
            'nameGap': name_gap,
            'nameTextStyle': self._apa_text_style(self.chart_font_size - 2, bold=True),
            'axisLabel': self._apa_text_style(self.chart_font_size - 2),
            'axisLine': {'lineStyle': {'color': '#000'}},
            'axisTick': {'lineStyle': {'color': '#000'}},
            'min': y_min,
            'max': y_max,
            'interval': interval
        }

    def _raw_score_to_plot_value(self, raw_score: int, total_items: int,
                                  interpretive_range: str,
                                  t_score: int = None) -> float:
        """Convert raw score to plot value in T-score visual range (25-95).

        Uses the actual T-score when available; falls back to an approximation
        based on interpretive range and raw-score proportion.
        """
        if t_score is not None:
            return t_score

        if total_items == 0:
            return 35

        proportion = raw_score / total_items

        # Approximate T-score position from interpretive range
        idx = self.cutoff_labels.index(interpretive_range) if interpretive_range in self.cutoff_labels else 0
        idx = min(idx, len(self.plot_bands) - 1)
        band = self.plot_bands[idx]
        return band['base'] + (proportion * band['range'])

    def _generate_single_domain_config(self, domain_name: str,
                                       domain_def: Dict,
                                       scale_scores: Dict[str, Any]) -> Optional[Dict]:
        """Generate ECharts config for a single domain graph."""
        domain_scales = {}
        for level in self.hierarchy_levels:
            if level in domain_def:
                for scale_abbr in domain_def[level]:
                    if scale_abbr in scale_scores:
                        domain_scales[scale_abbr] = {
                            'level': level,
                            'data': scale_scores[scale_abbr]
                        }

        if not domain_scales:
            return None

        domain_color = domain_def['color']
        config_line_styles = self.chart_config.get('line_styles', {})
        line_styles = {}
        for level_key, style_def in config_line_styles.items():
            line_styles[level_key] = {
                'width': style_def.get('width', 2.0),
                'type': style_def.get('style', 'solid'),
                'symbol': style_def.get('symbol', 'circle'),
                'size': style_def.get('size', 8)
            }

        all_x_labels = []
        for level in self.hierarchy_levels:
            if level not in domain_def:
                continue
            level_scales = [s for s in domain_def[level] if s in scale_scores]
            for scale_abbr in level_scales:
                all_x_labels.append(scale_abbr)

        series_list = []
        for level in self.hierarchy_levels:
            if level not in domain_def:
                continue
            level_scales = [s for s in domain_def[level] if s in scale_scores]
            if not level_scales:
                continue

            series_data = []
            for scale_abbr in all_x_labels:
                if scale_abbr in level_scales and scale_abbr in scale_scores:
                    scale_info = scale_scores[scale_abbr]
                    plot_value = self._raw_score_to_plot_value(
                        scale_info['raw_score'], scale_info['total_items'],
                        scale_info['interpretive_range'],
                        t_score=scale_info.get('t_score')
                    )
                    elevated = scale_info['interpretive_range'] in self.elevated_labels
                    style = line_styles.get(level, {'size': self.symbol_size_normal})
                    series_data.append({
                        'value': plot_value,
                        'name': scale_abbr,
                        'raw_score': scale_info['raw_score'],
                        'scale_name': scale_info['scale_name'],
                        'interpretive_range': scale_info['interpretive_range'],
                        'is_elevated': elevated,
                        'symbolSize': self.symbol_size_elevated
                    })
                else:
                    series_data.append(None)

            style = line_styles.get(level, {'width': 2.0, 'type': 'solid', 'symbol': 'circle'})
            series_list.append({
                'name': level.replace('_', ' '),
                'type': 'line',
                'data': series_data,
                'itemStyle': {'color': domain_color},
                'lineStyle': {'width': style['width'], 'type': style['type']},
                'symbol': style['symbol'],
                'connectNulls': False,
                'emphasis': {'focus': 'series'}
            })

        return {
            'title': {
                'text': domain_name,
                'left': 'center',
                'textStyle': self._apa_text_style(bold=True)
            },
            'tooltip': {'trigger': 'item', 'textStyle': self._apa_text_style(self.chart_font_size - 2)},
            'legend': {
                'data': [level.replace('_', ' ') for level in self.hierarchy_levels if level in domain_def],
                'top': 30,
                'textStyle': self._apa_text_style(self.chart_font_size - 2)
            },
            'grid': {**self.grid_configs['domain'], 'top': '12%'},
            'xAxis': {
                'type': 'category', 'data': all_x_labels,
                'axisLabel': {**self._apa_text_style(self.chart_font_size - 2), 'rotate': 45},
                'axisLine': {'lineStyle': {'color': '#000'}},
                'axisTick': {'lineStyle': {'color': '#000'}}
            },
            'yAxis': self._chart_y_axis(name_gap=45, data_max=self._max_series_value(series_list)),
            'series': series_list,
            'markLine': self._chart_mark_lines(),
            'toolbox': {
                'feature': {
                    'dataZoom': {'yAxisIndex': 'none'},
                    'restore': {},
                    'saveAsImage': {}
                }
            }
        }

    def _generate_single_validity_config(self, category_name: str,
                                          category_def: Dict,
                                          scale_scores: Dict[str, Any]) -> Optional[Dict]:
        """Generate ECharts config for a single validity category graph."""
        available_scales = [s for s in category_def['scales'] if s in scale_scores]
        if not available_scales:
            return None

        category_color = category_def['color']
        x_labels = []
        series_data = []

        for scale_abbr in available_scales:
            scale_info = scale_scores[scale_abbr]
            plot_value = self._raw_score_to_plot_value(
                scale_info['raw_score'], scale_info['total_items'],
                scale_info['interpretive_range'],
                t_score=scale_info.get('t_score')
            )
            elevated = scale_info['interpretive_range'] in self.elevated_labels
            x_labels.append(scale_abbr)
            series_data.append({
                'value': plot_value,
                'name': scale_abbr,
                'raw_score': scale_info['raw_score'],
                'scale_name': scale_info['scale_name'],
                'interpretive_range': scale_info['interpretive_range'],
                'is_elevated': elevated,
                'symbolSize': self.symbol_size_elevated
            })

        return {
            'title': {
                'text': category_name,
                'left': 'center',
                'textStyle': self._apa_text_style(bold=True)
            },
            'tooltip': {'trigger': 'item', 'textStyle': self._apa_text_style(self.chart_font_size - 2)},
            'grid': self.grid_configs['validity'],
            'xAxis': {
                'type': 'category', 'data': x_labels,
                'axisLabel': self._apa_text_style(self.chart_font_size - 2),
                'axisLine': {'lineStyle': {'color': '#000'}},
                'axisTick': {'lineStyle': {'color': '#000'}}
            },
            'yAxis': self._chart_y_axis(name_gap=45, data_max=self._max_series_value([{'data': series_data}])),
            'series': [{
                'name': category_name,
                'type': 'line',
                'data': series_data,
                'itemStyle': {'color': category_color},
                'lineStyle': {'width': self.validity_line_width},
                'symbol': 'circle',
                'smooth': False,
                'emphasis': {'focus': 'series'}
            }],
            'markLine': self._chart_mark_lines()
        }
