"""TS-UI-02.11: player header metadata and lower attributes refinement."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'frontend/public/squad'
JS = (UI / 'squad_ui02.js').read_text(encoding='utf-8')
CSS = (UI / 'squad_ui029.css').read_text(encoding='utf-8')


def test_header_uses_real_fields_only_and_renders_compact_measurements():
    assert "bodyMetric('Height',p.height_cm??p.height,'cm')" in JS
    assert "bodyMetric('Weight',p.weight_kg??p.weight,'kg')" in JS
    assert "String(p.foot||'').toLowerCase()" in JS
    assert 'Preferred foot:' in JS
    assert 'Foot unrecorded' not in JS


def test_hero_metadata_and_foot_controls_are_styled_in_existing_stylesheet():
    assert 'TS-UI-02.11' in CSS
    for token in ('.s29-body-metric', '.s29-foot-meta', '.s29-foot-switch', '.s29-foot.is-active'):
        assert token in CSS
    assert '.s29-kit-holder .s2-shirt-image' in CSS
    assert '.s28-crest-watermark.has-crest' in CSS


def test_lower_attribute_groups_are_reframed_not_rebuilt():
    assert '.s24-attributes-card .s24-card-heading' in CSS
    assert '.s24-attributes-card .s24-attribute-group' in CSS
    assert '.s24-attributes-card .s24-attribute-row' in CSS
    assert '.s24-attributes-card .s24-attribute-meter' in CSS
