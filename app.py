"""
KODZUS — Kalkulator Kodów ZUS (Streamlit)
Wizard krok po kroku + eksport .ics + autouzupełnianie NIP + tryb biura.

Uruchomienie lokalne:  streamlit run app.py
Hosting:               Streamlit Community Cloud (share.streamlit.io)

KLUCZ GUS API (opcjonalny):
  Lokalnie: utwórz .streamlit/secrets.toml z:  gus_api_key = "TWOJ_KLUCZ"
  Cloud:    Settings → Secrets → wklej:        gus_api_key = "TWOJ_KLUCZ"
"""

import streamlit as st
from datetime import date
import pandas as pd

from kodzus_core import (
    WizardInput, calculate, generate_timeline, detect_error,
    STAGE_LABELS, MIN_WAGE_2026,
)
from kodzus_ics import generate_ics
from kodzus_gus import lookup_nip, validate_nip
from kodzus_batch import (
    make_template_df, parse_import, verify_batch, build_report_df,
    get_summary, export_excel, build_batch_ics,
)
from kodzus_codes import (
    describe_code, adjust_code_for_person, get_entrepreneur_catalog,
    FIFTH_CHAR, SIXTH_CHAR,
)
from kodzus_report import (
    build_report_html, render_pdf, compute_scenarios, BrandConfig,
)

# =============================================================================
# KONFIGURACJA STRONY
# =============================================================================

st.set_page_config(
    page_title="KODZUS — Kalkulator Kodów ZUS",
    page_icon="🧾",
    layout="centered",
)

st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
<style>
    :root {
        --navy:        #0a2540;
        --navy-2:      #14315c;
        --accent:      #2563eb;
        --accent-soft: #e8f0fe;
        --ink:         #1a2233;
        --muted:       #64748b;
        --line:        #e2e8f0;
        --bg:          #f6f8fc;
        --success:     #0f9d58;
        --warning:     #e8a317;
        --danger:      #d93939;
    }

    /* ---------- Globalne ---------- */
    html, body, [class*="css"], .stApp {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .stApp { background: var(--bg); }

    /* Główny kontener — węższy, wycentrowany, z oddechem */
    .block-container { max-width: 760px; padding-top: 2rem; padding-bottom: 4rem; }

    h1, h2, h3, h4 { color: var(--navy) !important; letter-spacing: -0.02em; font-weight: 700; }

    /* ---------- Header ---------- */
    .kodzus-header {
        background: linear-gradient(135deg, var(--navy) 0%, var(--navy-2) 55%, var(--accent) 140%);
        color: #fff; padding: 30px 34px; border-radius: 18px; margin-bottom: 22px;
        box-shadow: 0 12px 32px -12px rgba(10,37,64,0.45);
        position: relative; overflow: hidden;
    }
    .kodzus-header::after {
        content: ""; position: absolute; top: -40%; right: -10%;
        width: 280px; height: 280px; border-radius: 50%;
        background: radial-gradient(circle, rgba(255,255,255,0.10), transparent 70%);
    }
    .kodzus-header h1 { color: #fff !important; margin: 0; font-size: 1.7rem; font-weight: 800; }
    .kodzus-header p { opacity: 0.82; margin: 6px 0 0; font-size: 0.95rem; font-weight: 400; }

    /* ---------- Przyciski ---------- */
    .stButton button {
        background: var(--navy); color: #fff; border: none; border-radius: 10px;
        padding: 11px 26px; font-weight: 600; font-size: 0.95rem;
        transition: transform .12s ease, box-shadow .12s ease, background .12s ease;
        box-shadow: 0 4px 14px -6px rgba(10,37,64,0.5);
    }
    .stButton button:hover {
        background: var(--accent); transform: translateY(-1px);
        box-shadow: 0 8px 20px -6px rgba(37,99,235,0.55); color: #fff;
    }
    .stButton button:active { transform: translateY(0); }

    .stDownloadButton button {
        background: var(--success); color: #fff; border: none; border-radius: 10px;
        padding: 11px 26px; font-weight: 600;
        box-shadow: 0 4px 14px -6px rgba(15,157,88,0.5);
    }
    .stDownloadButton button:hover { background: #0c7d46; color: #fff; }

    /* ---------- Pasek postępu ---------- */
    .stProgress > div > div > div { background: var(--bg); border-radius: 99px; height: 8px; }
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, var(--accent), var(--navy));
        border-radius: 99px;
    }

    /* ---------- Pola formularza ---------- */
    .stTextInput input, .stNumberInput input, .stDateInput input {
        border-radius: 10px !important; border: 1.5px solid var(--line) !important;
        padding: 10px 14px !important; font-size: 0.95rem !important;
    }
    .stTextInput input:focus, .stNumberInput input:focus, .stDateInput input:focus {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 3px rgba(37,99,235,0.12) !important;
    }

    /* Radio jako karty */
    div[role="radiogroup"] label {
        background: #fff; border: 1.5px solid var(--line); border-radius: 12px;
        padding: 12px 16px; margin-bottom: 8px; transition: all .12s ease;
        box-shadow: 0 1px 3px rgba(10,37,64,0.04);
    }
    div[role="radiogroup"] label:hover {
        border-color: var(--accent); box-shadow: 0 4px 12px -4px rgba(37,99,235,0.25);
    }

    /* Checkbox */
    .stCheckbox { background: #fff; border: 1.5px solid var(--line); border-radius: 12px;
        padding: 12px 16px; box-shadow: 0 1px 3px rgba(10,37,64,0.04); }

    /* ---------- Blok kodu (wynik) ---------- */
    .code-block {
        font-family: 'JetBrains Mono', 'Courier New', monospace;
        background: linear-gradient(145deg, #0a1628, #0f2138);
        color: #e6edf3; border-radius: 16px; padding: 26px 30px; margin: 18px 0;
        box-shadow: 0 16px 40px -16px rgba(10,22,40,0.7);
        border: 1px solid rgba(255,255,255,0.06);
    }
    .code-label { color: #7d8fa3; font-size: 0.72rem; text-transform: uppercase;
        letter-spacing: 0.08em; font-weight: 500; }
    .code-value { color: #6db3ff; font-weight: 700; font-size: 2rem;
        letter-spacing: 0.05em; margin-top: 2px; }
    .code-desc { color: #a5d6ff; font-size: 0.95rem; margin-top: 6px; font-weight: 500; }

    /* ---------- Alerty ---------- */
    .alert-error, .alert-warning, .alert-info, .alert-success {
        border-radius: 12px; padding: 15px 18px; margin: 12px 0; font-size: 0.92rem;
        line-height: 1.55; border-left: 4px solid; box-shadow: 0 2px 8px -4px rgba(10,37,64,0.12);
    }
    .alert-error   { background: #fef2f2; border-color: var(--danger);  color: #7f1d1d; }
    .alert-warning { background: #fffbeb; border-color: var(--warning); color: #78550c; }
    .alert-info    { background: var(--accent-soft); border-color: var(--accent); color: #1e3a8a; }
    .alert-success { background: #ecfdf3; border-color: var(--success); color: #14532d; }

    /* ---------- Tabela ---------- */
    .stDataFrame { border-radius: 12px; overflow: hidden; border: 1px solid var(--line); }

    /* ---------- Metryki ---------- */
    div[data-testid="stMetric"] {
        background: #fff; border: 1px solid var(--line); border-radius: 14px;
        padding: 16px 18px; box-shadow: 0 2px 10px -4px rgba(10,37,64,0.1);
    }
    div[data-testid="stMetricValue"] { color: var(--navy); font-weight: 800; }

    /* ---------- Sidebar ---------- */
    section[data-testid="stSidebar"] { background: #fff; border-right: 1px solid var(--line); }

    /* ---------- Expander ---------- */
    .streamlit-expanderHeader, details summary {
        border-radius: 10px !important; font-weight: 600; color: var(--navy);
    }

    /* ---------- Legal / drobny tekst ---------- */
    .legal {
        font-size: 0.76rem; color: var(--muted); border-top: 1px solid var(--line);
        padding-top: 14px; margin-top: 22px; line-height: 1.6;
    }

    /* Ukryj domyślną stopkę i menu Streamlit dla czystszego wyglądu */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    div[data-testid="stDecoration"] { display: none; }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# TRYB DZIAŁANIA (sidebar)
# =============================================================================

def get_gus_key():
    try:
        return st.secrets.get("gus_api_key", "")
    except Exception:
        return ""


# Polskie nazwy miesięcy — niezależne od przeglądarki
POLISH_MONTHS = [
    "styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec",
    "lipiec", "sierpień", "wrzesień", "październik", "listopad", "grudzień",
]


def polish_date_input(label: str, key: str, default: date,
                      min_year: int = 2015, max_year: int | None = None) -> date:
    """
    Wybór daty z polskimi nazwami miesięcy (dzień / miesiąc / rok).
    Niezależny od ustawień językowych przeglądarki.
    """
    if max_year is None:
        max_year = date.today().year + 5

    st.markdown(f"**{label}**")
    c1, c2, c3 = st.columns([1, 2, 1.3])

    with c1:
        day = st.selectbox("Dzień", list(range(1, 32)),
                           index=default.day - 1, key=f"{key}_d")
    with c2:
        month = st.selectbox("Miesiąc", POLISH_MONTHS,
                            index=default.month - 1, key=f"{key}_m")
    with c3:
        years = list(range(min_year, max_year + 1))
        default_year_idx = years.index(default.year) if default.year in years else len(years) - 1
        year = st.selectbox("Rok", years, index=default_year_idx, key=f"{key}_y")

    month_num = POLISH_MONTHS.index(month) + 1
    # Korekta dnia dla krótszych miesięcy
    import calendar as _cal
    max_day = _cal.monthrange(year, month_num)[1]
    safe_day = min(day, max_day)
    if safe_day != day:
        st.caption(f"⚠️ {month} {year} ma {max_day} dni — ustawiono {safe_day}.")
    return date(year, month_num, safe_day)


with st.sidebar:
    st.markdown("### ⚙️ Tryb")
    mode = st.radio(
        "Tryb pracy",
        options=["Przedsiębiorca", "Biuro rachunkowe"],
        index=0,
        label_visibility="collapsed",
        help="Tryb biura: bez formularza kontaktowego, do liczenia w imieniu klientów.",
    )
    IS_ACCOUNTANT = (mode == "Biuro rachunkowe")

    batch_mode = False
    if IS_ACCOUNTANT:
        st.markdown('<div class="alert-info" style="font-size:0.8rem">Tryb biura: liczysz w imieniu klienta. Bez gate kontaktowego.</div>', unsafe_allow_html=True)
        work = st.radio(
            "Sposób pracy",
            options=["Pojedynczy klient", "Import zbiorczy"],
            index=0,
            help="Import zbiorczy: wgraj listę klientów, zweryfikuj wszystkich naraz.",
        )
        batch_mode = (work == "Import zbiorczy")

    st.markdown("---")
    show_catalog = st.checkbox("📖 Przeglądarka katalogu kodów", value=False,
                               help="Pełny katalog kodów ZUS dla działalności (05xx).")

    st.markdown("---")
    with st.expander("🏢 Branding raportu PDF"):
        st.caption("Dane biura na raporcie PDF (opcjonalne).")
        if "brand" not in st.session_state:
            st.session_state.brand = {}
        b = st.session_state.brand
        b["office_name"] = st.text_input("Nazwa biura", value=b.get("office_name", ""))
        b["office_subtitle"] = st.text_input("Podtytuł", value=b.get("office_subtitle", ""))
        b["contact_email"] = st.text_input("E-mail kontaktowy", value=b.get("contact_email", ""))
        b["contact_phone"] = st.text_input("Telefon", value=b.get("contact_phone", ""))
        b["consultation_url"] = st.text_input("Link do umówienia konsultacji",
                                              value=b.get("consultation_url", ""),
                                              placeholder="https://...")
        b["client_name"] = st.text_input("Imię i nazwisko klienta", value=b.get("client_name", ""),
                                         help="Pojawi się jako 'Przygotowano dla'.")

    st.markdown("---")
    if get_gus_key():
        st.markdown('<div class="alert-success" style="font-size:0.78rem">✅ GUS API podłączone</div>', unsafe_allow_html=True)
    else:
        st.caption("ℹ️ GUS API niepodłączone — autouzupełnianie NIP wyłączone. Dodaj klucz w Secrets.")


# =============================================================================
# STAN SESJI
# =============================================================================

if "step" not in st.session_state:
    st.session_state.step = 0
if "data" not in st.session_state:
    st.session_state.data = {}
if "gus_result" not in st.session_state:
    st.session_state.gus_result = None

STEPS = ["start", "history", "employer", "titles", "status", "taxation", "preferences", "result"]
STEP_TITLES = {
    "start": "Data rozpoczęcia działalności",
    "history": "Historia działalności",
    "employer": "Relacja z byłym pracodawcą",
    "titles": "Inne tytuły ubezpieczenia",
    "status": "Status szczególny",
    "taxation": "Forma opodatkowania",
    "preferences": "Twoje preferencje",
    "result": "Wynik",
}


def go_next():
    if st.session_state.step < len(STEPS) - 1:
        st.session_state.step += 1


def go_prev():
    if st.session_state.step > 0:
        st.session_state.step -= 1


def restart():
    st.session_state.step = 0
    st.session_state.data = {}
    st.session_state.gus_result = None


# =============================================================================
# HEADER + PASEK POSTĘPU
# =============================================================================

st.markdown("""
<div class="kodzus-header">
    <h1>🧾 Kalkulator Kodów ZUS</h1>
    <p>Sprawdź swój aktualny kod tytułu ubezpieczenia i harmonogram składek na 5 lat.</p>
</div>
""", unsafe_allow_html=True)

# =============================================================================
# PRZEGLĄDARKA KATALOGU KODÓW (sidebar → checkbox)
# =============================================================================

if show_catalog:
    st.subheader("📖 Katalog kodów ZUS — działalność gospodarcza")
    st.write("Pełny katalog kodów tytułu ubezpieczenia dla osób prowadzących działalność (rdzeń **05xx**). "
             "Kod ma 6 znaków: **RR RR PN** — rdzeń + 5. znak (emerytura/renta) + 6. znak (niepełnosprawność).")

    catalog = get_entrepreneur_catalog()
    search = st.text_input("🔍 Szukaj (kod, nazwa, opis)", placeholder="np. ulga, 05 70, mały zus")

    if search:
        s = search.lower().replace(" ", "")
        catalog = [c for c in catalog
                   if s in c["Kod"].lower().replace(" ", "")
                   or s in c["Nazwa"].lower()
                   or s in c["Opis"].lower()]

    st.dataframe(
        pd.DataFrame([{"Kod": c["Kod"], "Nazwa": c["Nazwa"], "Etap": c["Etap"], "Opis": c["Opis"]}
                     for c in catalog]),
        use_container_width=True, hide_index=True,
    )

    st.divider()
    st.markdown("#### Struktura 5. i 6. znaku")
    cc1, cc2 = st.columns(2)
    with cc1:
        st.markdown("**5. znak — prawo do emerytury/renty**")
        for k, v in FIFTH_CHAR.items():
            st.markdown(f"- **{k}** — {v}")
    with cc2:
        st.markdown("**6. znak — stopień niepełnosprawności**")
        for k, v in SIXTH_CHAR.items():
            st.markdown(f"- **{k}** — {v}")

    st.caption("Źródło: oficjalny katalog kodów ZUS + rozporządzenie MRiPS z 27.06.2025.")
    st.stop()


# =============================================================================
# EKRAN IMPORTU ZBIORCZEGO (tryb biura → import zbiorczy)
# =============================================================================

if IS_ACCOUNTANT and batch_mode:
    st.subheader("📦 Import zbiorczy klientów")
    st.write("Wgraj listę klientów, zweryfikuj wszystkich naraz, pobierz raport i kalendarz zmian kodów.")

    # Szablon do pobrania
    with st.expander("📋 Jak przygotować plik? (pobierz szablon)"):
        st.write("Plik CSV lub Excel z kolumnami (wymagane: **nip, nazwa, data_startu, aktualny_kod**):")
        template = make_template_df()
        st.dataframe(template, use_container_width=True, hide_index=True)
        st.download_button(
            "📥 Pobierz szablon CSV",
            data=template.to_csv(index=False, sep=";").encode("utf-8-sig"),
            file_name="kodzus-szablon-klienci.csv",
            mime="text/csv",
        )
        st.caption(
            "Kolumny opcjonalne: forma_opodatkowania (scale/linear/lump_sum/tax_card), "
            "byly_pracodawca (tak/nie), zbieg_uop (tak/nie), wynagrodzenie_uop, "
            "status (brak/emeryt/rencista), chce_chorobowe (tak/nie), przychod_roczny. "
            "Brakujące kolumny przyjmą wartości domyślne (brak wykluczeń, skala podatkowa)."
        )

    uploaded = st.file_uploader("Wgraj plik z klientami (CSV / Excel)", type=["csv", "xlsx", "xls"])

    if uploaded is not None:
        file_bytes = uploaded.read()
        df, parse_errors = parse_import(file_bytes, uploaded.name)

        if parse_errors:
            for e in parse_errors:
                st.error(e)
        else:
            st.success(f"Wczytano {len(df)} klientów.")
            with st.expander("Podgląd wczytanych danych"):
                st.dataframe(df, use_container_width=True, hide_index=True)

            if st.button("🔍 Zweryfikuj wszystkich klientów", use_container_width=True):
                with st.spinner(f"Weryfikuję {len(df)} klientów..."):
                    verified = verify_batch(df)
                    st.session_state["batch_verified"] = verified

    # Wyniki weryfikacji
    if "batch_verified" in st.session_state:
        verified = st.session_state["batch_verified"]
        summary = get_summary(verified)

        st.divider()
        st.subheader("📊 Wynik weryfikacji")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Klientów", summary["total"])
        c2.metric("Kod OK", summary["ok"])
        c3.metric("Błędny kod", summary["errors"], delta=f"{summary['error_pct']}%", delta_color="inverse")
        c4.metric("Błędy danych", summary["data_errors"])

        if summary["errors"] > 0:
            st.markdown(
                f'<div class="alert-error"><strong>⚠️ {summary["errors"]} klientów ma błędny kod ZUS</strong> '
                f'({summary["error_pct"]}% portfela). Wymagają korekty deklaracji.</div>',
                unsafe_allow_html=True)
        else:
            st.markdown('<div class="alert-success">✅ Wszyscy klienci mają prawidłowe kody ZUS.</div>',
                        unsafe_allow_html=True)

        # Tabela raportu
        report = build_report_df(verified)

        # Filtrowanie: tylko błędy
        only_errors = st.checkbox("Pokaż tylko klientów z błędnym kodem")
        display = report[report["Status"] == "BŁĄD KODU"] if only_errors else report

        def highlight_status(row):
            if row["Status"] == "BŁĄD KODU":
                return ["background-color: #fff5f5"] * len(row)
            if row["Status"] == "OK":
                return ["background-color: #f0fff4"] * len(row)
            return ["background-color: #fffbf0"] * len(row)

        st.dataframe(
            display.style.apply(highlight_status, axis=1),
            use_container_width=True, hide_index=True
        )

        # Eksporty
        st.divider()
        st.subheader("📤 Eksport zbiorczy")
        e1, e2 = st.columns(2)

        with e1:
            excel_bytes = export_excel(report, summary)
            st.download_button(
                "📊 Raport końcowy (Excel)",
                data=excel_bytes,
                file_name=f"kodzus-raport-{date.today():%Y-%m-%d}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        with e2:
            ics_bytes = build_batch_ics(verified).encode("utf-8")
            st.download_button(
                "📅 Kalendarz zmian kodów (.ics)",
                data=ics_bytes,
                file_name=f"kodzus-zmiany-kodow-{date.today():%Y-%m-%d}.ics",
                mime="text/calendar",
                use_container_width=True,
            )
        st.caption("Raport Excel zawiera podsumowanie + szczegóły. Kalendarz: daty zmian kodów wszystkich klientów.")

        if st.button("↩ Wyczyść i wgraj nową listę"):
            del st.session_state["batch_verified"]
            st.rerun()

    st.stop()  # Nie pokazuj wizarda pojedynczego klienta



current_step = st.session_state.step
result_index = STEPS.index("result")
progress = min(current_step / result_index, 1.0)
st.progress(progress)

if STEPS[current_step] != "result":
    st.caption(f"Krok {current_step + 1} z {result_index} — {STEP_TITLES[STEPS[current_step]]}")


step_name = STEPS[current_step]
d = st.session_state.data


# =============================================================================
# KROK: START (z autouzupełnianiem NIP)
# =============================================================================

if step_name == "start":
    st.subheader("📅 Kiedy zaczęłaś/zacząłeś działalność?")

    gus_key = get_gus_key()

    nip_input = st.text_input(
        "NIP firmy (opcjonalnie — autouzupełnianie z GUS)",
        value=d.get("nip", ""),
        max_chars=13,
        placeholder="0000000000",
    )
    d["nip"] = nip_input

    if nip_input:
        nip_clean = "".join(c for c in nip_input if c.isdigit())
        if len(nip_clean) == 10:
            if not validate_nip(nip_clean):
                st.warning("NIP ma nieprawidłową sumę kontrolną.")
            elif gus_key:
                if st.button("🔍 Pobierz dane z GUS"):
                    with st.spinner("Łączę z GUS..."):
                        st.session_state.gus_result = lookup_nip(nip_clean, gus_key)
                if st.session_state.gus_result:
                    r = st.session_state.gus_result
                    if r.get("error"):
                        st.warning(r["error"])
                    else:
                        st.markdown(
                            f'<div class="alert-success"><strong>{r.get("name","")}</strong><br>'
                            f'REGON: {r.get("regon","—")} | {r.get("city","—")}</div>',
                            unsafe_allow_html=True)
            else:
                st.caption("Dodaj klucz GUS API w Secrets żeby włączyć autouzupełnianie.")

    st.write("Podaj datę wpisaną do CEIDG jako dzień rozpoczęcia działalności:")
    d["start_date"] = polish_date_input(
        "Data rozpoczęcia działalności", "start_date",
        default=d.get("start_date", date.today()),
        min_year=2015, max_year=date.today().year + 5,
    )

    col1, col2 = st.columns([1, 1])
    with col2:
        st.button("Dalej →", on_click=go_next, use_container_width=True)


# =============================================================================
# KROK: HISTORIA
# =============================================================================

elif step_name == "history":
    st.subheader("📋 Historia działalności gospodarczej")
    st.write("Czy prowadziłeś/aś działalność w ciągu ostatnich 60 miesięcy (5 lat)?")

    prev = st.radio(
        "Poprzednia działalność",
        options=["Nie — pierwsza działalność lub przerwa > 5 lat",
                 "Tak — prowadziłem/am w ciągu ostatnich 5 lat"],
        index=0 if not d.get("had_previous_activity") else 1,
        label_visibility="collapsed",
    )
    d["had_previous_activity"] = prev.startswith("Tak")

    if d["had_previous_activity"]:
        d["previous_end_date"] = polish_date_input(
            "Data zamknięcia poprzedniej działalności", "prev_end",
            default=d.get("previous_end_date", date.today()),
            min_year=2010, max_year=date.today().year,
        )

    col1, col2 = st.columns([1, 1])
    with col1:
        st.button("← Wstecz", on_click=go_prev, use_container_width=True)
    with col2:
        st.button("Dalej →", on_click=go_next, use_container_width=True)


# =============================================================================
# KROK: BYŁY PRACODAWCA
# =============================================================================

elif step_name == "employer":
    st.subheader("🏢 Praca dla obecnego lub byłego pracodawcy")
    st.markdown('<div class="alert-info">ℹ️ Jeśli TAK — tracisz prawo do Ulgi na Start i Preferencyjnego ZUS, niezależnie od etatu. '
                'Wg interpretacji ZUS "były pracodawca" obejmuje też <strong>obecnego</strong> pracodawcę, dla którego świadczysz usługi w ramach działalności.</div>',
                unsafe_allow_html=True)

    emp = st.radio(
        "Pracodawca",
        options=["Nie — w działalności nie pracuję dla obecnego ani byłego pracodawcy",
                 "Tak — świadczę w działalności usługi dla obecnego lub byłego pracodawcy (ostatnie 2 lata)"],
        index=0 if not d.get("former_employer") else 1,
        label_visibility="collapsed",
    )
    d["former_employer"] = emp.startswith("Tak")
    st.caption("Dotyczy sytuacji gdy zakres działalności pokrywa się z tym, co robiłeś/robisz na etacie u tego pracodawcy.")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.button("← Wstecz", on_click=go_prev, use_container_width=True)
    with col2:
        st.button("Dalej →", on_click=go_next, use_container_width=True)


# =============================================================================
# KROK: ZBIEG TYTUŁÓW
# =============================================================================

elif step_name == "titles":
    st.subheader("💼 Inne tytuły ubezpieczenia")

    title = st.radio(
        "Zbieg tytułów",
        options=["Tylko działalność — brak innych tytułów",
                 "Umowa o pracę (UoP) — mam etat",
                 "Umowa zlecenie / inne"],
        index={"none": 0, "uop": 1, "other": 2}.get(d.get("employment_type", "none"), 0),
        label_visibility="collapsed",
    )

    if title.startswith("Tylko"):
        d["employment_type"] = "none"; d["employment_overlap"] = False; d["employment_salary"] = 0.0
    elif title.startswith("Umowa o pracę"):
        d["employment_type"] = "uop"; d["employment_overlap"] = True
        st.info(f"Próg: {MIN_WAGE_2026:.0f} zł brutto (min. płaca 2026). "
                "Jeśli zarabiasz tyle lub więcej — z działalności płacisz tylko zdrowotną.")
        d["employment_salary"] = st.number_input(
            "Wynagrodzenie brutto z UoP (PLN/msc)", min_value=0.0, step=100.0,
            value=d.get("employment_salary", 0.0))
    else:
        d["employment_type"] = "other"; d["employment_overlap"] = True; d["employment_salary"] = 0.0

    col1, col2 = st.columns([1, 1])
    with col1:
        st.button("← Wstecz", on_click=go_prev, use_container_width=True)
    with col2:
        st.button("Dalej →", on_click=go_next, use_container_width=True)


# =============================================================================
# KROK: STATUS
# =============================================================================

elif step_name == "status":
    st.subheader("🧑‍⚕️ Status szczególny")

    status = st.radio(
        "Status",
        options=["Brak — standardowa sytuacja",
                 "Emeryt — pobieram emeryturę",
                 "Rencista — pobieram rentę z tytułu niezdolności do pracy"],
        index={"none": 0, "retiree": 1, "disability_pensioner": 2}.get(d.get("special_status", "none"), 0),
        label_visibility="collapsed",
    )
    d["special_status"] = {
        "Brak — standardowa sytuacja": "none",
        "Emeryt — pobieram emeryturę": "retiree",
        "Rencista — pobieram rentę z tytułu niezdolności do pracy": "disability_pensioner",
    }[status]

    if d["special_status"] == "retiree":
        st.info("Emeryt może być zwolniony ze składki zdrowotnej z działalności, jeśli emerytura ≤ płaca minimalna "
                "(4 806 zł) oraz przychód z działalności ≤ 50% najniższej emerytury (lub karta podatkowa).")
        d["pension_amount"] = st.number_input(
            "Emerytura brutto miesięcznie (PLN)", min_value=0.0, step=100.0,
            value=d.get("pension_amount", 0.0),
            help="Do oceny zwolnienia ze składki zdrowotnej.")

    st.write("Stopień niepełnosprawności (wpływa na 6. znak kodu):")
    disab = st.radio(
        "Niepełnosprawność",
        options=["Brak orzeczenia", "Lekki stopień", "Umiarkowany stopień",
                 "Znaczny stopień", "Orzeczenie (osoba do 16. r.ż.)"],
        index=int(d.get("disability", "0")),
        label_visibility="collapsed",
    )
    d["disability"] = str(["Brak orzeczenia", "Lekki stopień", "Umiarkowany stopień",
                           "Znaczny stopień", "Orzeczenie (osoba do 16. r.ż.)"].index(disab))

    col1, col2 = st.columns([1, 1])
    with col1:
        st.button("← Wstecz", on_click=go_prev, use_container_width=True)
    with col2:
        st.button("Dalej →", on_click=go_next, use_container_width=True)


# =============================================================================
# KROK: FORMA OPODATKOWANIA
# =============================================================================

elif step_name == "taxation":
    st.subheader("💰 Forma opodatkowania")

    tax = st.radio(
        "Forma opodatkowania",
        options=["Skala podatkowa (12%/32%, zdrowotna 9% dochodu)",
                 "Podatek liniowy (19%, zdrowotna 4,9% dochodu)",
                 "Ryczałt ewidencjonowany (stała zdrowotna od przychodu)",
                 "Karta podatkowa (stała 432,54 zł/msc)"],
        index={"scale": 0, "linear": 1, "lump_sum": 2, "tax_card": 3}.get(d.get("taxation_form", "scale"), 0),
        label_visibility="collapsed",
    )
    d["taxation_form"] = {"Skala": "scale", "Podat": "linear", "Rycza": "lump_sum", "Karta": "tax_card"}[tax[:5]]

    if d["taxation_form"] == "lump_sum":
        d["lump_sum_rate"] = st.selectbox("Stawka ryczałtu (%)",
                                          options=[2.0, 3.0, 5.5, 8.5, 10.0, 12.0, 15.0, 17.0], index=3)
        d["estimated_annual_revenue"] = st.number_input(
            "Szacowany roczny przychód (PLN)", min_value=0.0, step=1000.0,
            value=d.get("estimated_annual_revenue", 0.0),
            help="Próg składki zdrowotnej: 60k / 300k PLN")
    else:
        d["estimated_monthly_income"] = st.number_input(
            "Szacowany miesięczny dochód (PLN) — opcjonalnie", min_value=0.0, step=100.0,
            value=d.get("estimated_monthly_income", 0.0),
            help="Zostaw 0 = pokażemy minimum ustawowe.")
        d["estimated_annual_revenue"] = st.number_input(
            "Szacowany roczny przychód (PLN) — opcjonalnie", min_value=0.0, step=1000.0,
            value=d.get("estimated_annual_revenue", 0.0),
            help="Do oceny kwalifikacji do Małego ZUS Plus (limit 120 000 PLN).")

    # Przychód miesięczny z działalności — potrzebny do zwolnień ze zdrowotnej
    # (emeryt o niskim świadczeniu / pracownik na ryczałcie o niskiej podstawie)
    is_retiree = d.get("special_status") == "retiree"
    is_low_uop = (d.get("employment_type") == "uop"
                  and 0 < d.get("employment_salary", 0) <= MIN_WAGE_2026)
    if is_retiree or is_low_uop:
        d["monthly_revenue_activity"] = st.number_input(
            "Przychód miesięczny z działalności (PLN)", min_value=0.0, step=100.0,
            value=d.get("monthly_revenue_activity", 0.0),
            help="Do oceny zwolnienia ze składki zdrowotnej (próg 50%).")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.button("← Wstecz", on_click=go_prev, use_container_width=True)
    with col2:
        st.button("Dalej →", on_click=go_next, use_container_width=True)


# =============================================================================
# KROK: PREFERENCJE
# =============================================================================

elif step_name == "preferences":
    st.subheader("⚙️ Twoje preferencje")

    d["wants_ulga"] = st.checkbox(
        "Chcę skorzystać z Ulgi na Start (05 40)", value=d.get("wants_ulga", True),
        help="6 pełnych miesięcy bez składek społecznych.")

    # Chorobowe niedostępne: w trakcie Ulgi LUB przy zbiegu z etatem ≥ min. płacy
    min_wage = MIN_WAGE_2026
    uop_exempt = (d.get("employment_type") == "uop"
                  and d.get("employment_salary", 0) >= min_wage)
    chorobowe_disabled = d["wants_ulga"] or uop_exempt

    d["wants_chorobowe"] = st.checkbox(
        "Chcę opłacać dobrowolne ubezpieczenie chorobowe",
        value=False if chorobowe_disabled else d.get("wants_chorobowe", False),
        disabled=chorobowe_disabled,
        help="Niedostępne w trakcie Ulgi na Start oraz przy etacie ≥ płacy minimalnej.")
    if d["wants_ulga"]:
        st.caption("ℹ️ Dobrowolne chorobowe niedostępne w trakcie Ulgi na Start.")
    elif uop_exempt:
        st.caption("ℹ️ Dobrowolne chorobowe niedostępne: masz etat ≥ płacy minimalnej, "
                   "więc składki społeczne z działalności są dobrowolne (nie możesz zgłosić chorobowego).")

    st.markdown('<div class="alert-info">Kliknij <strong>Oblicz</strong> żeby wygenerować harmonogram.</div>', unsafe_allow_html=True)

    st.divider()
    st.markdown("##### Działalność nierejestrowana")
    d["check_unregistered"] = st.checkbox(
        "Sprawdź czy kwalifikuję się do działalności nierejestrowanej",
        value=d.get("check_unregistered", False),
        help="Bez rejestracji w CEIDG, bez składek ZUS. Próg: przychód miesięczny < 75% min. wynagrodzenia (3 604,50 zł w 2026) i brak działalności w ostatnich 60 msc.",
    )
    if d["check_unregistered"]:
        d["monthly_revenue_unreg"] = st.number_input(
            "Szacowany przychód miesięczny (PLN)", min_value=0.0, step=100.0,
            value=d.get("monthly_revenue_unreg", 0.0),
            help="Próg 2026: 3 604,50 zł (75% z 4 806 zł).")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.button("← Wstecz", on_click=go_prev, use_container_width=True)
    with col2:
        st.button("🧮 Oblicz harmonogram", on_click=go_next, use_container_width=True)


# =============================================================================
# KROK: WYNIK (z eksportem .ics)
# =============================================================================

elif step_name == "result":
    inp = WizardInput(
        start_date=d.get("start_date", date.today()),
        calculation_date=date.today(),
        had_previous_activity=d.get("had_previous_activity", False),
        previous_end_date=d.get("previous_end_date"),
        former_employer=d.get("former_employer", False),
        employment_overlap=d.get("employment_overlap", False),
        employment_type=d.get("employment_type", "none"),
        employment_salary=d.get("employment_salary", 0.0),
        special_status=d.get("special_status", "none"),
        wants_ulga=d.get("wants_ulga", True),
        wants_chorobowe=d.get("wants_chorobowe", False),
        taxation_form=d.get("taxation_form", "scale"),
        lump_sum_rate=d.get("lump_sum_rate", 8.5),
        estimated_monthly_income=d.get("estimated_monthly_income", 0.0),
        estimated_annual_revenue=d.get("estimated_annual_revenue", 0.0),
        check_unregistered=d.get("check_unregistered", False),
        monthly_revenue_unreg=d.get("monthly_revenue_unreg", 0.0),
        pension_amount=d.get("pension_amount", 0.0),
        monthly_revenue_activity=d.get("monthly_revenue_activity", 0.0),
    )

    result = calculate(inp)
    timeline = generate_timeline(result, inp)
    error_info = detect_error(result)

    # --- PRZYPADEK: działalność nierejestrowana ---
    if result.get("is_unregistered"):
        st.markdown(f"""
        <div class="code-block">
            <div class="code-label">Forma działalności</div>
            <div class="code-value" style="font-size:1.3rem">Działalność nierejestrowana</div>
            <div class="code-desc">Bez rejestracji w CEIDG · bez numeru ZUS · bez składek</div>
            <br>
            <div class="code-label">Składki ZUS: 0 zł · Rozliczasz tylko podatek dochodowy</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('<div class="alert-success">✅ Kwalifikujesz się do działalności nierejestrowanej — '
                    'nie płacisz żadnych składek ZUS (ani społecznych, ani zdrowotnej).</div>',
                    unsafe_allow_html=True)
        for w in result["warnings"]:
            st.markdown(f'<div class="alert-info">ℹ️ {w}</div>', unsafe_allow_html=True)

        st.markdown(f"""
        <div class="legal">
            Próg działalności nierejestrowanej 2026: przychód miesięczny do 3 604,50 zł (75% min. wynagrodzenia).
            Wynik informacyjny — nie stanowi porady prawnej. Po przekroczeniu progu masz 7 dni na rejestrację w CEIDG.
        </div>
        """, unsafe_allow_html=True)

        if not IS_ACCOUNTANT:
            st.divider()
            st.markdown("### 📄 Raport PDF")
            if st.button("🖨️ Wygeneruj raport PDF", use_container_width=True):
                with st.spinner("Generuję raport PDF..."):
                    try:
                        bd = st.session_state.get("brand", {})
                        brand = BrandConfig(
                            office_name=bd.get("office_name", ""),
                            office_subtitle=bd.get("office_subtitle", ""),
                            contact_email=bd.get("contact_email", ""),
                            contact_phone=bd.get("contact_phone", ""),
                            consultation_url=bd.get("consultation_url", ""),
                            client_name=bd.get("client_name", ""),
                        )
                        html = build_report_html(result, [], error_info, "—", {}, [], brand,
                                                 is_unregistered=True)
                        st.session_state["report_pdf"] = render_pdf(html)
                    except Exception as e:
                        st.error(f"Nie udało się wygenerować PDF: {e}")
            if st.session_state.get("report_pdf"):
                st.download_button(
                    "📥 Pobierz raport PDF", data=st.session_state["report_pdf"],
                    file_name=f"raport-zus-{date.today():%Y-%m-%d}.pdf",
                    mime="application/pdf", use_container_width=True)

        st.divider()
        cc1, cc2 = st.columns([1, 1])
        with cc1:
            st.button("← Wstecz", on_click=go_prev, use_container_width=True)
        with cc2:
            st.button("↩ Zacznij od nowa", on_click=restart, use_container_width=True)
        st.stop()

    # Domknij kod do pełnej postaci 6-znakowej (rdzeń + 5. + 6. znak)
    core = result["current_code"].replace(" ", "")
    disability = d.get("disability", "0")
    full_code = adjust_code_for_person(core, d.get("special_status", "none"), disability)
    code_detail = describe_code(core, full_code.split()[2][0], full_code.split()[2][1])

    stage_end_str = result["stage_end"].strftime("%d.%m.%Y") if result["stage_end"] else "bezterminowo"
    st.markdown(f"""
    <div class="code-block">
        <div class="code-label">Aktualny kod tytułu ubezpieczenia (6-znakowy)</div>
        <div class="code-value">{full_code}</div>
        <div class="code-desc">{result['stage_label']}</div>
        <br>
        <div class="code-label">Obowiązuje od {result['stage_start'].strftime('%d.%m.%Y')} do {stage_end_str}</div>
    </div>
    """, unsafe_allow_html=True)

    # Rozbicie znaczenia znaków
    with st.expander("ℹ️ Co oznacza ten kod?"):
        st.markdown(f"**Rdzeń {full_code[:5]}** — {code_detail['name']}")
        st.caption(code_detail["desc"])
        st.markdown(f"**5. znak ({full_code.split()[2][0]})** — {code_detail['fifth_meaning']}")
        st.markdown(f"**6. znak ({full_code.split()[2][1]})** — {code_detail['sixth_meaning']}")
        if code_detail.get("base_info"):
            st.markdown(f"**Podstawa składek:** {code_detail['base_info']}")

    if error_info["cta_visible"] and not IS_ACCOUNTANT:
        st.markdown(f"""
        <div class="alert-error">
            <strong>⚠️ Sprawdź swój aktualny kod ZUS</strong><br>
            Prawidłowy kod to <strong>{result['current_code']}</strong>.
            Jeśli Twoje deklaracje wskazują inny — możesz mieć zaległości lub niedopłaty.
            <br><br>📅 <strong>Umów konsultację aby to zweryfikować.</strong>
        </div>
        """, unsafe_allow_html=True)
    elif error_info["cta_visible"] and IS_ACCOUNTANT:
        st.markdown(f"""
        <div class="alert-warning">
            <strong>⚠️ Klient powinien być na kodzie {result['current_code']}</strong> —
            zweryfikuj jego aktualne deklaracje ZUS.
        </div>
        """, unsafe_allow_html=True)

    for w in result["warnings"]:
        st.markdown(f'<div class="alert-warning">ℹ️ {w}</div>', unsafe_allow_html=True)

    if result.get("social_exempt"):
        st.markdown(
            '<div class="alert-success">✅ <strong>Zwolnienie ze składek społecznych</strong> — '
            'dzięki etatowi ≥ płacy minimalnej z działalności opłacasz tylko składkę zdrowotną. '
            'W harmonogramie poniżej składki społeczne wynoszą 0 zł.</div>',
            unsafe_allow_html=True)

    # Wykryj zwolnienie ze zdrowotnej (zdrowotna = 0 w całym harmonogramie)
    if timeline and all(r["monthly_healthcare"] == 0 for r in timeline):
        if d.get("special_status") == "retiree":
            st.markdown(
                '<div class="alert-success">✅ <strong>Zwolnienie ze składki zdrowotnej</strong> — '
                'jako emeryt o niskim świadczeniu (emerytura ≤ płaca minimalna i niski przychód z działalności) '
                'jesteś zwolniony z opłacania składki zdrowotnej z działalności.</div>',
                unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="alert-success">✅ <strong>Zwolnienie ze składki zdrowotnej</strong> — '
                'spełniasz warunki zwolnienia ze składki zdrowotnej z działalności '
                '(niska podstawa z etatu, ryczałt, niski przychód z działalności).</div>',
                unsafe_allow_html=True)

    st.subheader("Harmonogram składek ZUS")
    df = pd.DataFrame([{
        "Etap": r["stage_name"] + (" ⚠" if r["is_forecast"] else ""),
        "Kod": r["code"],
        "Od": r["date_from"].strftime("%d.%m.%Y"),
        "Do": r["date_to"].strftime("%d.%m.%Y") if r["date_to"] else "—",
        "Społeczne": f"{r['monthly_social']:.2f} zł",
        "Zdrowotna": f"{r['monthly_healthcare']:.2f} zł",
        "Łącznie/msc": f"{r['monthly_total']:.2f} zł",
    } for r in timeline])
    st.dataframe(df, use_container_width=True, hide_index=True)

    if any(r["is_forecast"] for r in timeline):
        st.caption("⚠️ Etapy oznaczone ⚠ mają kwoty prognozowane.")

    # --- RAPORT PDF (tylko tryb przedsiębiorcy) ---
    if not IS_ACCOUNTANT:
        st.divider()
        st.markdown("### 📄 Raport PDF")
        st.write("Profesjonalny raport z kodem, harmonogramem, wykresami, scenariuszami i wskazówkami.")

        if st.button("🖨️ Wygeneruj raport PDF", use_container_width=True):
            with st.spinner("Generuję raport PDF..."):
                try:
                    scenarios = compute_scenarios(inp, result, timeline)
                    bd = st.session_state.get("brand", {})
                    brand = BrandConfig(
                        office_name=bd.get("office_name", ""),
                        office_subtitle=bd.get("office_subtitle", ""),
                        contact_email=bd.get("contact_email", ""),
                        contact_phone=bd.get("contact_phone", ""),
                        consultation_url=bd.get("consultation_url", ""),
                        client_name=bd.get("client_name", ""),
                    )
                    html = build_report_html(
                        result, timeline, error_info, full_code, code_detail,
                        scenarios, brand, is_unregistered=result.get("is_unregistered", False),
                    )
                    pdf_bytes = render_pdf(html)
                    st.session_state["report_pdf"] = pdf_bytes
                except Exception as e:
                    st.error(f"Nie udało się wygenerować PDF: {e}")

        if st.session_state.get("report_pdf"):
            st.download_button(
                label="📥 Pobierz raport PDF",
                data=st.session_state["report_pdf"],
                file_name=f"raport-zus-{date.today():%Y-%m-%d}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
    else:
        st.divider()
        st.markdown('<div class="alert-info">ℹ️ W trybie biura zestawienia klientów eksportujesz do '
                    '<strong>Excela</strong> przez <strong>Import zbiorczy</strong> (panel boczny). '
                    'Elegancki raport PDF jest przeznaczony dla przedsiębiorcy.</div>',
                    unsafe_allow_html=True)

    # --- EKSPORT .ICS ---
    st.divider()
    st.markdown("### 📅 Dodaj do kalendarza")
    cyclic = st.checkbox("Dołącz cykliczne przypomnienia o zapłacie składek (15. dnia miesiąca)")

    ics_content = generate_ics(timeline, cyclic=cyclic)
    st.download_button(
        label="📥 Pobierz kalendarz (.ics)",
        data=ics_content.encode("utf-8"),
        file_name="harmonogram-zus.ics",
        mime="text/calendar",
        use_container_width=True,
    )
    st.caption("Plik otworzysz w Google Calendar, Apple Calendar, Outlook.")

    st.markdown("""
    <div class="legal">
        Wyniki mają charakter <strong>informacyjny</strong> i nie stanowią porady prawnej ani ubezpieczeniowej.
        Poprawność zależy od prawidłowości wprowadzonych danych.
    </div>
    """, unsafe_allow_html=True)

    st.divider()
    col1, col2 = st.columns([1, 1])
    with col1:
        st.button("← Wstecz", on_click=go_prev, use_container_width=True)
    with col2:
        st.button("↩ Zacznij od nowa", on_click=restart, use_container_width=True)
