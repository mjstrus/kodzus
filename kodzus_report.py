"""
KODZUS — Generator raportu PDF (profesjonalny).

Buduje raport HTML z wykresami SVG i renderuje do PDF przez Chromium (playwright).
Sekcje: nagłówek z brandingiem biura, aktualny kod, harmonogram 5 lat,
wykresy (składki w czasie + podział), scenariusze, wskazówki/terminy,
CTA przy błędnym kodzie (link do konsultacji).

Renderowanie: HTML → Chromium → PDF (pełna kontrola nad wyglądem).
"""

from __future__ import annotations
import os
import tempfile
from datetime import date
from dataclasses import dataclass

# Kolory marki
NAVY = "#0a2540"
NAVY2 = "#14315c"
ACCENT = "#2563eb"
SUCCESS = "#0f9d58"
WARNING = "#e8a317"
DANGER = "#d93939"
INK = "#1a2233"
MUTED = "#64748b"
LINE = "#e2e8f0"

POLISH_MONTHS_SHORT = ["sty", "lut", "mar", "kwi", "maj", "cze",
                       "lip", "sie", "wrz", "paź", "lis", "gru"]


@dataclass
class BrandConfig:
    """Konfiguracja brandingu biura rachunkowego."""
    office_name: str = ""
    office_subtitle: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    consultation_url: str = ""
    client_name: str = ""


# =============================================================================
# WYKRESY SVG (bez JS — deterministyczne renderowanie)
# =============================================================================

def _svg_stacked_timeline(timeline: list[dict], width: int = 680, height: int = 240) -> str:
    """Wykres słupkowy: składki społeczne + zdrowotna w czasie (po etapach)."""
    if not timeline:
        return ""

    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 50
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    max_total = max((r["monthly_total"] for r in timeline), default=1) or 1
    # Zaokrąglij górę skali do ładnej liczby
    scale_max = (int(max_total / 500) + 1) * 500

    n = len(timeline)
    gap = 14
    bar_w = (plot_w - gap * (n - 1)) / n if n > 0 else plot_w

    bars = []
    labels = []
    for i, row in enumerate(timeline):
        x = pad_l + i * (bar_w + gap)
        social = row["monthly_social"]
        health = row["monthly_healthcare"]

        h_social = (social / scale_max) * plot_h
        h_health = (health / scale_max) * plot_h

        y_social = pad_t + plot_h - h_social
        y_health = y_social - h_health

        if h_social > 0.5:
            bars.append(f'<rect x="{x:.1f}" y="{y_social:.1f}" width="{bar_w:.1f}" '
                        f'height="{h_social:.1f}" fill="{ACCENT}" rx="3"/>')
        if h_health > 0.5:
            bars.append(f'<rect x="{x:.1f}" y="{y_health:.1f}" width="{bar_w:.1f}" '
                        f'height="{h_health:.1f}" fill="{NAVY}" rx="3"/>')

        # Etykieta kwoty nad słupkiem
        total = row["monthly_total"]
        bars.append(f'<text x="{x + bar_w/2:.1f}" y="{y_health - 6:.1f}" '
                    f'text-anchor="middle" font-size="10" font-weight="700" '
                    f'fill="{INK}">{total:.0f}</text>')

        # Etykieta okresu pod słupkiem
        d = row["date_from"]
        lbl = f"{POLISH_MONTHS_SHORT[d.month-1]} {str(d.year)[2:]}"
        labels.append(f'<text x="{x + bar_w/2:.1f}" y="{height - pad_b + 16:.1f}" '
                      f'text-anchor="middle" font-size="9" fill="{MUTED}">{lbl}</text>')
        # Kod etapu
        labels.append(f'<text x="{x + bar_w/2:.1f}" y="{height - pad_b + 30:.1f}" '
                      f'text-anchor="middle" font-size="8" font-weight="600" '
                      f'fill="{NAVY}">{row["code"]}</text>')

    # Oś Y — linie pomocnicze
    grid = []
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        y = pad_t + plot_h - frac * plot_h
        val = scale_max * frac
        grid.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" '
                    f'stroke="{LINE}" stroke-width="1"/>')
        grid.append(f'<text x="{pad_l - 8}" y="{y + 3:.1f}" text-anchor="end" '
                    f'font-size="9" fill="{MUTED}">{val:.0f}</text>')

    return f'''<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" width="100%">
        {"".join(grid)}
        {"".join(bars)}
        {"".join(labels)}
    </svg>'''


def _svg_donut(social: float, health: float, size: int = 160) -> str:
    """Wykres kołowy (donut): podział społeczne vs zdrowotna."""
    total = social + health
    if total <= 0:
        return ""

    cx = cy = size / 2
    r = size / 2 - 16
    circ = 2 * 3.14159265 * r
    stroke_w = 26

    social_frac = social / total
    social_len = circ * social_frac
    health_len = circ * (1 - social_frac)

    # Społeczne (accent) zaczyna od góry
    social_arc = (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
                  f'stroke="{ACCENT}" stroke-width="{stroke_w}" '
                  f'stroke-dasharray="{social_len:.2f} {circ:.2f}" '
                  f'transform="rotate(-90 {cx} {cy})"/>')
    # Zdrowotna (navy) po społecznych
    health_arc = (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
                  f'stroke="{NAVY}" stroke-width="{stroke_w}" '
                  f'stroke-dasharray="{health_len:.2f} {circ:.2f}" '
                  f'stroke-dashoffset="{-social_len:.2f}" '
                  f'transform="rotate(-90 {cx} {cy})"/>')

    return f'''<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg" width="{size}">
        {social_arc}
        {health_arc}
        <text x="{cx}" y="{cy - 4}" text-anchor="middle" font-size="13" font-weight="800" fill="{INK}">{total:.0f}</text>
        <text x="{cx}" y="{cy + 12}" text-anchor="middle" font-size="9" fill="{MUTED}">zł/msc</text>
    </svg>'''


# =============================================================================
# SKŁADANIE HTML
# =============================================================================

def _money(v: float) -> str:
    return f"{v:,.2f}".replace(",", " ").replace(".", ",") + " zł"


def _date_pl(d: date | None) -> str:
    if d is None:
        return "bezterminowo"
    return d.strftime("%d.%m.%Y")


def build_report_html(result: dict, timeline: list[dict], error_info: dict,
                      full_code: str, code_detail: dict,
                      scenarios: list[dict], brand: BrandConfig,
                      is_unregistered: bool = False, is_planning: bool = False,
                      wakacje: dict | None = None, advice: dict | None = None) -> str:
    """Buduje pełny HTML raportu."""

    today = date.today().strftime("%d.%m.%Y")

    # --- Branding header ---
    office_block = ""
    if brand.office_name:
        sub = f'<div class="brand-sub">{brand.office_subtitle}</div>' if brand.office_subtitle else ""
        office_block = f'<div class="brand-name">{brand.office_name}</div>{sub}'

    client_block = ""
    if brand.client_name:
        client_block = f'<div class="client">Przygotowano dla: <strong>{brand.client_name}</strong></div>'

    # --- Sekcja: działalność nierejestrowana (osobny wariant) ---
    if is_unregistered:
        return _build_unregistered_html(brand, today, result)

    # --- Główny kod ---
    stage_end_str = _date_pl(result.get("stage_end"))
    _label = "Kod tytułu ubezpieczenia na start" if is_planning else "Aktualny kod tytułu ubezpieczenia"
    _period = "Pierwszy etap: od" if is_planning else "Obowiązuje od"
    code_card = f'''
    <div class="code-card">
        <div class="code-card-label">{_label}</div>
        <div class="code-card-value">{full_code}</div>
        <div class="code-card-desc">{result["stage_label"]}</div>
        <div class="code-card-period">{_period} {_date_pl(result.get("stage_start"))} do {stage_end_str}</div>
    </div>'''

    # --- CTA ---
    cta_block = ""
    if is_planning:
        # Dla planującego: zachęta do konsultacji przy zakładaniu (nie "błędny kod")
        link = ""
        if brand.consultation_url:
            link = f'<a class="cta-btn cta-btn-blue" href="{brand.consultation_url}">Umów konsultację →</a>'
        elif brand.contact_email:
            link = f'<a class="cta-btn cta-btn-blue" href="mailto:{brand.contact_email}">Napisz do nas →</a>'
        if link:
            cta_block = f'''
            <div class="cta-box cta-box-blue">
                <div class="cta-title cta-title-blue">🚀 Zakładasz firmę? Zrób to dobrze od początku</div>
                <div class="cta-text cta-text-blue">
                    Wybór właściwej ścieżki ulg i prawidłowe zgłoszenie do ZUS na starcie pozwala
                    uniknąć kosztownych błędów. Pomożemy Ci wybrać optymalną formę i dopełnić formalności.
                </div>
                {link}
            </div>'''
    elif error_info.get("cta_visible"):
        link = ""
        if brand.consultation_url:
            link = f'<a class="cta-btn" href="{brand.consultation_url}">Umów konsultację →</a>'
        elif brand.contact_email:
            link = f'<a class="cta-btn" href="mailto:{brand.contact_email}">Napisz do nas →</a>'
        cta_block = f'''
        <div class="cta-box">
            <div class="cta-title">⚠ Zweryfikuj swój aktualny kod ZUS</div>
            <div class="cta-text">
                Według naszej analizy prawidłowy kod tytułu ubezpieczenia to <strong>{full_code}</strong>.
                Jeśli Twoje deklaracje ZUS wskazują inny kod, możesz mieć niedopłaty, zaległości
                lub utracone prawo do ulg. To częsty i kosztowny błąd.
                <br><br>
                Nasi specjaliści mogą zweryfikować Twoją sytuację i przygotować korektę.
            </div>
            {link}
        </div>'''

    # --- Tabela harmonogramu ---
    rows = ""
    for r in timeline:
        forecast = ' <span class="forecast">prognoza</span>' if r["is_forecast"] else ""
        rows += f'''<tr>
            <td><strong>{r["stage_name"]}</strong>{forecast}</td>
            <td class="code-cell">{r["code"]}</td>
            <td>{_date_pl(r["date_from"])}</td>
            <td>{_date_pl(r["date_to"])}</td>
            <td class="num">{_money(r["monthly_social"])}</td>
            <td class="num">{_money(r["monthly_healthcare"])}</td>
            <td class="num total">{_money(r["monthly_total"])}</td>
        </tr>'''

    # --- Wykresy ---
    chart_timeline = _svg_stacked_timeline(timeline)
    first = timeline[0] if timeline else {"monthly_social": 0, "monthly_healthcare": 0}
    chart_donut = _svg_donut(first["monthly_social"], first["monthly_healthcare"])

    # --- Scenariusze ---
    # Obsługa nowych scenariuszy strategii (mają cost_5y) lub starych (mają diff)
    scenario_cards = ""
    scenario_table = ""
    is_strategy = scenarios and "cost_5y" in scenarios[0]

    if is_strategy:
        def _hz(sc, hz, field):
            return sc.get("horizons", {}).get(hz, {}).get(field, 0.0)

        for sc in scenarios:
            star = "★ " if sc.get("recommended") else ""
            border = f"2px solid {ACCENT}" if sc.get("recommended") else f"1.5px solid {LINE}"
            bg = "#f5f9ff" if sc.get("recommended") else "#fff"
            dots = "●" * sc["protection_level"] + "○" * (3 - sc["protection_level"])

            def hrow(label, field, prefix=""):
                cells = "".join(
                    f'<td style="text-align:right;font-size:8px;padding:2px 4px">{prefix}{_money(_hz(sc, hz, field))}</td>'
                    for hz in (12, 36, 60))
                return f'<tr><td style="font-size:7.5px;color:{MUTED};padding:2px 4px">{label}</td>{cells}</tr>'

            scenario_cards += f'''
            <div class="scenario" style="border:{border};background:{bg}">
                <div class="scenario-name">{star}{sc["name"]}</div>
                <div class="scenario-code">{sc["subtitle"]}</div>
                <table style="width:100%;border-collapse:collapse;margin:6px 0">
                    <tr style="border-bottom:1px solid {LINE}">
                        <td style="padding:2px 4px"></td>
                        <td style="text-align:right;font-size:7px;color:#94a3b8;padding:2px 4px">1 rok</td>
                        <td style="text-align:right;font-size:7px;color:#94a3b8;padding:2px 4px">3 lata</td>
                        <td style="text-align:right;font-size:7px;color:#94a3b8;padding:2px 4px">5 lat</td>
                    </tr>
                    {hrow("Wydano", "spent")}
                    {hrow("Emerytura", "pension")}
                    {hrow("Podatek", "tax_shield", "−")}
                </table>
                <div class="scenario-metric">🛡 Ochrona: {dots} &nbsp; ▶ Start: <strong>{_money(sc["first_total"])}/msc</strong></div>
                <div class="scenario-note">{sc["for_whom"]}</div>
            </div>'''

        # Tabela zbiorcza — stan po 5 latach
        trows = ""
        for sc in scenarios:
            star = "★ " if sc.get("recommended") else ""
            hl = ' style="background:#eff6ff"' if sc.get("recommended") else ""
            trows += f'''<tr{hl}>
                <td><strong>{star}{sc["name"]}</strong></td>
                <td class="num">{_money(sc["cost_5y"])}</td>
                <td class="num">{_money(sc["pension_5y"])}</td>
                <td class="num">−{_money(sc.get("tax_5y", 0))}</td>
                <td>{sc["protection_label"]}</td>
            </tr>'''
        scenario_table = f'''
        <div style="font-size:9px;color:{MUTED};margin:10px 0 4px">Tabela zbiorcza — stan po 5 latach</div>
        <table>
            <thead><tr>
                <th>Wariant</th><th class="num">Wydano (5 lat)</th>
                <th class="num">Na emeryturę</th><th class="num">Obniżka podatku</th><th>Ochrona</th>
            </tr></thead>
            <tbody>{trows}</tbody>
        </table>'''

    # --- Wskazówki i terminy ---
    tips = ""
    for w in result.get("warnings", []):
        tips += f'<li>{w}</li>'
    if error_info.get("boundary_warning"):
        tips += f'<li><strong>{error_info["boundary_warning"]}</strong></li>'

    # Terminy administracyjne
    deadlines = '''
        <li><strong>20. dzień miesiąca</strong> — termin opłaty składek ZUS za miesiąc poprzedni.</li>
        <li><strong>31 stycznia</strong> — oświadczenie o Małym ZUS Plus (jeśli kwalifikujesz).</li>
        <li><strong>20 maja</strong> — roczne rozliczenie składki zdrowotnej (DRA za kwiecień).</li>
        <li><strong>7 dni</strong> — termin na zgłoszenie zmiany kodu / danych w ZUS.</li>'''

    # --- Wakacje składkowe (opcjonalna sekcja) ---
    wakacje_block = ""
    if wakacje:
        if wakacje["qualifies"]:
            saving = wakacje["monthly_social_saving"]
            if saving > 0:
                body = (f'Kwalifikujesz się do wakacji składkowych — raz w roku kalendarzowym możesz '
                        f'zwolnić się ze składek społecznych za jeden wybrany miesiąc. '
                        f'Oszczędność na etapie {wakacje["stage_for_saving"]}: '
                        f'<strong>{_money(saving)}</strong> za ten miesiąc (zdrowotną nadal opłacasz).')
            else:
                body = ('Kwalifikujesz się do wakacji składkowych. Obecnie jesteś na etapie bez składek '
                        'społecznych (Ulga), więc zwolnienie warto wykorzystać po wejściu w składki preferencyjne lub pełne.')
            wakacje_block = f'''
            <div class="section">
                <div class="section-title">Wakacje składkowe</div>
                <div class="explain" style="background:#ecfdf3">
                    <div style="font-size:10.5px;color:{INK};margin-bottom:8px">{body}</div>
                    <div style="font-size:10px;color:{INK}">
                        💡 <strong>Wskazówka:</strong> o wakacje składkowe najlepiej wnioskować na miesiąc
                        przed miesiącem spodziewanego wysokiego przychodu — obniżają one składki społeczne za
                        wybrany miesiąc. Wniosek RWS składasz w eZUS w miesiącu poprzedzającym
                        (np. zwolnienie za grudzień → wniosek w listopadzie).
                    </div>
                </div>
            </div>'''
        else:
            powody = "; ".join(wakacje["reasons"])
            wakacje_block = f'''
            <div class="section">
                <div class="section-title">Wakacje składkowe</div>
                <div class="explain" style="background:#fffbeb">
                    <div style="font-size:10.5px;color:{INK}">
                        Nie kwalifikujesz się do wakacji składkowych. Powód: {powody}.
                    </div>
                </div>
            </div>'''

    # --- Rekomendacja doradcza (narracja + kroki + pułapki) ---
    advice_block = ""
    if advice:
        steps_html = "".join(f'<li>{s}</li>' for s in advice.get("steps", []))
        pitfalls_html = "".join(f'<li>{p}</li>' for p in advice.get("pitfalls", []))
        reasoning = advice.get("reasoning", "")
        advice_block = f'''
        <div class="section">
            <div class="section-title">Nasza rekomendacja</div>
            <div class="reco-box">
                <div class="reco-headline">{advice.get("headline","")}</div>
                <div class="reco-reasoning">{reasoning}</div>
            </div>
            <div class="reco-cols">
                <div class="reco-col">
                    <div class="reco-col-title">Plan krok po kroku</div>
                    <ol class="reco-steps">{steps_html}</ol>
                </div>
                <div class="reco-col">
                    <div class="reco-col-title">Na co uważać</div>
                    <ul class="reco-pitfalls">{pitfalls_html}</ul>
                </div>
            </div>
        </div>'''

    # --- Stopka kontaktowa ---
    footer_contact = ""
    parts = []
    if brand.contact_email:
        parts.append(brand.contact_email)
    if brand.contact_phone:
        parts.append(brand.contact_phone)
    if parts:
        footer_contact = " · ".join(parts)

    # Legenda wykresu podziału
    donut_legend = f'''
        <div class="legend">
            <div class="legend-item"><span class="dot" style="background:{ACCENT}"></span> Składki społeczne</div>
            <div class="legend-item"><span class="dot" style="background:{NAVY}"></span> Składka zdrowotna</div>
        </div>'''

    code_explain = f'''
        <div class="explain">
            <div class="explain-row"><span class="explain-k">Rdzeń {full_code[:5]}</span> {code_detail.get("name","")}</div>
            <div class="explain-row"><span class="explain-k">5. znak ({full_code.split()[2][0]})</span> {code_detail.get("fifth_meaning","")}</div>
            <div class="explain-row"><span class="explain-k">6. znak ({full_code.split()[2][1]})</span> {code_detail.get("sixth_meaning","")}</div>
        </div>'''

    return f'''<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<style>
    @page {{ size: A4; margin: 0; }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
        color: {INK}; font-size: 11px; line-height: 1.5;
    }}
    .page {{ padding: 38px 44px; }}
    /* Header */
    .header {{
        background: linear-gradient(135deg, {NAVY} 0%, {NAVY2} 55%, {ACCENT} 150%);
        color: #fff; padding: 28px 32px; border-radius: 16px; margin-bottom: 22px;
        position: relative; overflow: hidden;
    }}
    .header::after {{
        content: ""; position: absolute; top: -50%; right: -8%;
        width: 240px; height: 240px; border-radius: 50%;
        background: radial-gradient(circle, rgba(255,255,255,0.10), transparent 70%);
    }}
    .header h1 {{ font-size: 22px; font-weight: 800; letter-spacing: -0.02em; }}
    .header .subtitle {{ opacity: 0.85; font-size: 12px; margin-top: 4px; font-weight: 400; }}
    .brand-name {{ font-size: 14px; font-weight: 700; margin-top: 14px; }}
    .brand-sub {{ font-size: 10px; opacity: 0.8; }}
    .client {{ font-size: 11px; margin-top: 10px; opacity: 0.92; }}
    .meta {{ font-size: 10px; opacity: 0.75; margin-top: 12px; }}
    /* Code card */
    .code-card {{
        background: linear-gradient(145deg, #0a1628, #0f2138);
        color: #e6edf3; border-radius: 14px; padding: 22px 26px; margin-bottom: 18px;
    }}
    .code-card-label {{ color: #7d8fa3; font-size: 9px; text-transform: uppercase; letter-spacing: 0.08em; }}
    .code-card-value {{ font-family: 'JetBrains Mono', monospace; color: #6db3ff; font-size: 32px; font-weight: 700; letter-spacing: 0.06em; margin: 4px 0; }}
    .code-card-desc {{ color: #a5d6ff; font-size: 13px; font-weight: 600; }}
    .code-card-period {{ color: #7d8fa3; font-size: 10px; margin-top: 8px; }}
    /* Sections */
    .section {{ margin-bottom: 22px; }}
    .section-title {{
        font-size: 13px; font-weight: 800; color: {NAVY};
        border-left: 4px solid {ACCENT}; padding-left: 10px; margin-bottom: 12px;
    }}
    /* CTA */
    .cta-box {{
        background: #fef2f2; border: 1.5px solid {DANGER}; border-radius: 12px;
        padding: 18px 22px; margin-bottom: 18px;
    }}
    .cta-title {{ color: {DANGER}; font-weight: 800; font-size: 13px; margin-bottom: 6px; }}
    .cta-text {{ color: #7f1d1d; font-size: 11px; }}
    .cta-btn {{
        display: inline-block; margin-top: 12px; background: {DANGER}; color: #fff;
        text-decoration: none; padding: 9px 20px; border-radius: 8px; font-weight: 700; font-size: 11px;
    }}
    .cta-box-blue {{ background: #eff6ff; border-color: {ACCENT}; }}
    .cta-title-blue {{ color: {ACCENT}; }}
    .cta-text-blue {{ color: #1e3a8a; }}
    .cta-btn-blue {{ background: {ACCENT}; }}
    /* Rekomendacja */
    .reco-box {{ background: linear-gradient(135deg,#f0f7ff,#eef2ff); border-left: 4px solid {ACCENT};
                 border-radius: 10px; padding: 14px 18px; margin-bottom: 12px; }}
    .reco-headline {{ font-size: 13px; font-weight: 800; color: {NAVY}; margin-bottom: 6px; }}
    .reco-reasoning {{ font-size: 10.5px; color: {INK}; line-height: 1.55; }}
    .reco-cols {{ display: flex; gap: 14px; }}
    .reco-col {{ flex: 1; }}
    .reco-col-title {{ font-size: 10px; font-weight: 800; color: {ACCENT};
                       text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 6px; }}
    ol.reco-steps {{ padding-left: 16px; }}
    ol.reco-steps li {{ font-size: 9.5px; color: {INK}; line-height: 1.45; padding: 3px 0; }}
    ul.reco-pitfalls {{ list-style: none; }}
    ul.reco-pitfalls li {{ font-size: 9.5px; color: #7c2d12; line-height: 1.45; padding: 4px 0 4px 16px;
                           position: relative; }}
    ul.reco-pitfalls li::before {{ content: "!"; position: absolute; left: 4px; font-weight: 800;
                                   color: {WARNING}; }}
    /* Charts */
    .chart-row {{ display: flex; gap: 20px; align-items: center; }}
    .chart-main {{ flex: 1; }}
    .chart-side {{ width: 200px; text-align: center; }}
    .legend {{ margin-top: 8px; font-size: 9px; }}
    .legend-item {{ display: inline-block; margin: 0 8px; color: {MUTED}; }}
    .dot {{ display: inline-block; width: 9px; height: 9px; border-radius: 50%; vertical-align: middle; margin-right: 3px; }}
    /* Table */
    table {{ width: 100%; border-collapse: collapse; font-size: 10px; }}
    th {{ background: {NAVY}; color: #fff; padding: 8px 8px; text-align: left; font-weight: 600; font-size: 9px; }}
    th.num, td.num {{ text-align: right; }}
    td {{ padding: 7px 8px; border-bottom: 1px solid {LINE}; }}
    tr:nth-child(even) td {{ background: #f8fafc; }}
    .code-cell {{ font-family: 'JetBrains Mono', monospace; font-weight: 700; color: {NAVY}; }}
    td.total {{ font-weight: 800; color: {NAVY}; }}
    .forecast {{ background: {WARNING}; color: #fff; font-size: 7px; padding: 1px 4px; border-radius: 3px; vertical-align: middle; }}
    /* Scenarios */
    .scenarios {{ display: flex; gap: 10px; flex-wrap: wrap; }}
    .scenario {{ flex: 1 1 30%; min-width: 30%; border: 1.5px solid {LINE}; border-radius: 12px; padding: 12px; }}
    .scenario-name {{ font-weight: 700; font-size: 10.5px; color: {NAVY}; }}
    .scenario-code {{ font-size: 8px; color: {MUTED}; margin: 2px 0 8px; line-height: 1.3; }}
    .scenario-amount {{ font-size: 17px; font-weight: 800; color: {INK}; }}
    .scenario-amount span {{ font-size: 10px; font-weight: 400; color: {MUTED}; }}
    .scenario-sub {{ font-size: 8px; color: {MUTED}; margin-bottom: 6px; }}
    .scenario-metric {{ font-size: 8.5px; color: {INK}; padding: 1px 0; }}
    .scenario-diff {{ font-size: 10px; font-weight: 700; margin: 4px 0; }}
    .scenario-diff.up {{ color: {DANGER}; }}
    .scenario-diff.down {{ color: {SUCCESS}; }}
    .scenario-diff.flat {{ color: {MUTED}; }}
    .scenario-note {{ font-size: 8px; color: {MUTED}; line-height: 1.4; margin-top: 6px; }}
    /* Lists */
    .explain {{ background: #f8fafc; border-radius: 10px; padding: 12px 16px; }}
    .explain-row {{ font-size: 10px; padding: 3px 0; }}
    .explain-k {{ display: inline-block; min-width: 110px; font-weight: 700; color: {NAVY}; }}
    ul.tips {{ list-style: none; }}
    ul.tips li {{ padding: 6px 0 6px 22px; position: relative; font-size: 10px; border-bottom: 1px solid {LINE}; }}
    ul.tips li::before {{ content: "•"; position: absolute; left: 6px; color: {ACCENT}; font-weight: 800; }}
    /* Footer */
    .footer {{
        margin-top: 26px; padding-top: 14px; border-top: 1px solid {LINE};
        font-size: 9px; color: {MUTED}; line-height: 1.6;
    }}
    .footer strong {{ color: {INK}; }}
</style>
</head>
<body>
<div class="page">
    <div class="header">
        <h1>{"Raport ZUS — plan składek na start" if is_planning else "Raport ZUS — kod tytułu ubezpieczenia"}</h1>
        <div class="subtitle">{"Składki przy zakładaniu działalności — prognoza na 5 lat" if is_planning else "Analiza składek i harmonogram na 5 lat"}</div>
        {office_block}
        {client_block}
        <div class="meta">Data sporządzenia: {today}</div>
    </div>

    {code_card}
    <div class="section">
        <div class="section-title">Co oznacza ten kod</div>
        {code_explain}
    </div>

    {cta_block}

    {advice_block}

    <div class="section">
        <div class="section-title">Składki w czasie</div>
        <div class="chart-row">
            <div class="chart-main">{chart_timeline}</div>
            <div class="chart-side">
                <div style="font-size:9px;color:{MUTED};margin-bottom:4px">Podział składki (obecny etap)</div>
                {chart_donut}
                {donut_legend}
            </div>
        </div>
    </div>

    <div class="section">
        <div class="section-title">Harmonogram składek</div>
        <table>
            <thead><tr>
                <th>Etap</th><th>Kod</th><th>Od</th><th>Do</th>
                <th class="num">Społeczne</th><th class="num">Zdrowotna</th><th class="num">Razem/msc</th>
            </tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>

    <div class="section">
        <div class="section-title">Warianty w Twojej obecnej sytuacji</div>
        <div class="scenarios">{scenario_cards}</div>
        {scenario_table}
    </div>

    {wakacje_block}

    <div class="section">
        <div class="section-title">Wskazówki i ostrzeżenia</div>
        <ul class="tips">{tips if tips else '<li>Brak szczególnych ostrzeżeń dla Twojej sytuacji.</li>'}</ul>
    </div>

    <div class="section">
        <div class="section-title">Ważne terminy</div>
        <ul class="tips">{deadlines}</ul>
    </div>

    <div class="footer">
        <strong>Zastrzeżenie:</strong> Niniejszy raport ma charakter informacyjny i nie stanowi porady
        prawnej, podatkowej ani ubezpieczeniowej. Wyliczenia opierają się na danych wprowadzonych przez
        użytkownika oraz stawkach ZUS obowiązujących w roku sporządzenia. Kwoty oznaczone jako „prognoza”
        opierają się na szacunkach i mogą ulec zmianie. W celu weryfikacji indywidualnej sytuacji
        skontaktuj się z biurem rachunkowym lub ZUS.
        {f'<br><br><strong>{brand.office_name}</strong> · {footer_contact}' if footer_contact else ''}
        <br><br>Wygenerowano przez KODZUS — kalkulator kodów ZUS.
    </div>
</div>
</body>
</html>'''


def _build_unregistered_html(brand: BrandConfig, today: str, result: dict) -> str:
    """Wariant raportu dla działalności nierejestrowanej."""
    office_block = ""
    if brand.office_name:
        office_block = f'<div class="brand-name">{brand.office_name}</div>'

    warnings_html = "".join(f'<li>{w}</li>' for w in result.get("warnings", []))

    return f'''<!DOCTYPE html>
<html lang="pl"><head><meta charset="utf-8">
<style>
    @page {{ size: A4; margin: 0; }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: 'Plus Jakarta Sans', sans-serif; color: {INK}; font-size: 11px; line-height: 1.5; }}
    .page {{ padding: 38px 44px; }}
    .header {{ background: linear-gradient(135deg, {NAVY}, {ACCENT}); color: #fff; padding: 28px 32px; border-radius: 16px; margin-bottom: 22px; }}
    .header h1 {{ font-size: 22px; font-weight: 800; }}
    .brand-name {{ font-size: 14px; font-weight: 700; margin-top: 12px; }}
    .big-card {{ background: linear-gradient(145deg,#ecfdf3,#d1fae5); border:1.5px solid {SUCCESS}; border-radius:14px; padding:24px; margin-bottom:18px; }}
    .big-card .label {{ font-size:10px; text-transform:uppercase; color:{SUCCESS}; letter-spacing:0.08em; }}
    .big-card .value {{ font-size:24px; font-weight:800; color:{NAVY}; margin:6px 0; }}
    ul.tips {{ list-style:none; }}
    ul.tips li {{ padding:6px 0 6px 22px; position:relative; font-size:10px; border-bottom:1px solid {LINE}; }}
    ul.tips li::before {{ content:"•"; position:absolute; left:6px; color:{SUCCESS}; font-weight:800; }}
    .footer {{ margin-top:26px; padding-top:14px; border-top:1px solid {LINE}; font-size:9px; color:{MUTED}; line-height:1.6; }}
</style></head><body><div class="page">
    <div class="header">
        <h1>Raport ZUS — działalność nierejestrowana</h1>
        {office_block}
        <div style="font-size:10px;opacity:0.75;margin-top:12px">Data sporządzenia: {today}</div>
    </div>
    <div class="big-card">
        <div class="label">Forma działalności</div>
        <div class="value">Działalność nierejestrowana</div>
        <div style="font-size:11px;color:{MUTED}">Bez rejestracji w CEIDG · bez numeru ZUS · składki ZUS: 0 zł</div>
    </div>
    <ul class="tips">{warnings_html}</ul>
    <div class="footer"><strong>Zastrzeżenie:</strong> Raport informacyjny, nie stanowi porady prawnej.
    Po przekroczeniu progu przychodu (75% min. wynagrodzenia) masz 7 dni na rejestrację w CEIDG.
    <br><br>Wygenerowano przez KODZUS.</div>
</div></body></html>'''


# =============================================================================
# RENDER DO PDF (Chromium przez playwright)
# =============================================================================

def _find_chromium() -> str | None:
    """Znajduje wykonywalny plik Chromium w różnych lokalizacjach."""
    import glob
    candidates = [
        "/opt/pw-browsers/chromium-*/chrome-linux/chrome",
        os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux/chrome"),
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
    ]
    for pattern in candidates:
        matches = sorted(glob.glob(pattern))
        if matches:
            return matches[-1]
    return None


def _ensure_chromium() -> str | None:
    """Znajduje Chromium; jeśli brak, próbuje go zainstalować (Streamlit Cloud)."""
    exe = _find_chromium()
    if exe:
        return exe
    # Próba instalacji (jednorazowo, np. na Streamlit Cloud)
    try:
        import subprocess
        subprocess.run(["playwright", "install", "chromium"],
                       check=False, capture_output=True, timeout=300)
    except Exception:
        pass
    return _find_chromium()


def render_pdf(html: str) -> bytes:
    """Renderuje HTML do PDF przez Chromium. Zwraca bajty PDF."""
    from playwright.sync_api import sync_playwright

    exe = _ensure_chromium()

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f:
        f.write(html)
        html_path = f.name

    pdf_bytes = b""
    try:
        with sync_playwright() as p:
            launch_kwargs = {"args": ["--no-sandbox", "--disable-dev-shm-usage"]}
            if exe:
                launch_kwargs["executable_path"] = exe
            browser = p.chromium.launch(**launch_kwargs)
            page = browser.new_page()
            page.goto(f"file://{html_path}", wait_until="networkidle")
            pdf_bytes = page.pdf(format="A4", print_background=True,
                                 margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
            browser.close()
    finally:
        os.unlink(html_path)
    return pdf_bytes
