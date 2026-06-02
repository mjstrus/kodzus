"""
KODZUS — Kalkulator Kodów ZUS (Streamlit)
Wizard krok po kroku z paskiem postępu.

Uruchomienie lokalne:  streamlit run app.py
Hosting:               Streamlit Community Cloud (share.streamlit.io)
"""

import streamlit as st
from datetime import date, datetime
import pandas as pd

from kodzus_core import (
    WizardInput, calculate, generate_timeline, detect_error,
    STAGE_LABELS, MIN_WAGE_2026,
)

# =============================================================================
# KONFIGURACJA STRONY
# =============================================================================

st.set_page_config(
    page_title="KODZUS — Kalkulator Kodów ZUS",
    page_icon="🧾",
    layout="centered",
)

# Kolor przewodni #003366 + style
st.markdown("""
<style>
    .stApp { background: #f8f9fc; }
    h1, h2, h3 { color: #003366 !important; }
    .kodzus-header {
        background: linear-gradient(135deg, #003366 0%, #1a5599 100%);
        color: white; padding: 24px 28px; border-radius: 10px; margin-bottom: 8px;
    }
    .kodzus-header h1 { color: white !important; margin: 0; font-size: 1.6rem; }
    .kodzus-header p { opacity: 0.85; margin: 4px 0 0; font-size: 0.92rem; }
    .stButton button {
        background: #003366; color: white; border: none; border-radius: 6px;
        padding: 8px 24px; font-weight: 600;
    }
    .stButton button:hover { background: #1a5599; color: white; }
    .code-block {
        font-family: 'Courier New', monospace; background: #0d1117; color: #e6edf3;
        border-radius: 8px; padding: 20px 24px; margin: 16px 0;
    }
    .code-label { color: #8b949e; font-size: 0.75rem; text-transform: uppercase; }
    .code-value { color: #79c0ff; font-weight: bold; font-size: 1.6rem; }
    .code-desc { color: #a5d6ff; font-size: 0.9rem; margin-top: 6px; }
    .alert-error {
        background: #fff5f5; border-left: 5px solid #c0392b; color: #7b1a1a;
        padding: 14px 18px; border-radius: 6px; margin: 12px 0;
    }
    .alert-warning {
        background: #fffbf0; border-left: 5px solid #e6a817; color: #7a5500;
        padding: 14px 18px; border-radius: 6px; margin: 12px 0;
    }
    .alert-info {
        background: #f0f4ff; border-left: 5px solid #0066cc; color: #003166;
        padding: 14px 18px; border-radius: 6px; margin: 12px 0;
    }
    .legal {
        font-size: 0.75rem; color: #6c757d; border-top: 1px solid #dee2e6;
        padding-top: 12px; margin-top: 20px;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# STAN SESJI
# =============================================================================

if "step" not in st.session_state:
    st.session_state.step = 0
if "data" not in st.session_state:
    st.session_state.data = {}

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


# =============================================================================
# HEADER + PASEK POSTĘPU
# =============================================================================

st.markdown("""
<div class="kodzus-header">
    <h1>🧾 Kalkulator Kodów ZUS</h1>
    <p>Sprawdź swój aktualny kod tytułu ubezpieczenia i harmonogram składek na 5 lat.</p>
</div>
""", unsafe_allow_html=True)

current_step = st.session_state.step
result_index = STEPS.index("result")
progress = min(current_step / result_index, 1.0)
st.progress(progress)

if STEPS[current_step] != "result":
    st.caption(f"Krok {current_step + 1} z {result_index} — {STEP_TITLES[STEPS[current_step]]}")


# =============================================================================
# KROKI WIZARDA
# =============================================================================

step_name = STEPS[current_step]
d = st.session_state.data

# --- KROK: START ---
if step_name == "start":
    st.subheader("📅 Kiedy zaczęłaś/zacząłeś działalność?")
    st.write("Podaj datę wpisaną do CEIDG jako dzień rozpoczęcia działalności gospodarczej.")

    d["start_date"] = st.date_input(
        "Data rozpoczęcia działalności",
        value=d.get("start_date", date.today()),
        min_value=date(2015, 1, 1),
        max_value=date(date.today().year + 5, 12, 31),
        format="DD.MM.YYYY",
    )
    st.caption("Jeśli planujesz dopiero założyć firmę — podaj planowaną datę.")

    col1, col2 = st.columns([1, 1])
    with col2:
        st.button("Dalej →", on_click=go_next, use_container_width=True)

# --- KROK: HISTORIA ---
elif step_name == "history":
    st.subheader("📋 Historia działalności gospodarczej")
    st.write("Czy prowadziłeś/aś działalność w ciągu ostatnich 60 miesięcy (5 lat) przed aktualną datą startu?")

    prev = st.radio(
        "Poprzednia działalność",
        options=["Nie — pierwsza działalność lub przerwa > 5 lat",
                 "Tak — prowadziłem/am w ciągu ostatnich 5 lat"],
        index=0 if not d.get("had_previous_activity") else 1,
        label_visibility="collapsed",
    )
    d["had_previous_activity"] = prev.startswith("Tak")

    if d["had_previous_activity"]:
        d["previous_end_date"] = st.date_input(
            "Data zamknięcia poprzedniej działalności",
            value=d.get("previous_end_date", date.today()),
            min_value=date(2010, 1, 1),
            max_value=date.today(),
            format="DD.MM.YYYY",
        )

    col1, col2 = st.columns([1, 1])
    with col1:
        st.button("← Wstecz", on_click=go_prev, use_container_width=True)
    with col2:
        st.button("Dalej →", on_click=go_next, use_container_width=True)

# --- KROK: BYŁY PRACODAWCA ---
elif step_name == "employer":
    st.subheader("🏢 Relacja z byłym pracodawcą")
    st.write("Czy w ciągu ostatnich 2 lat byłeś/aś na UoP i teraz wykonujesz tę samą działalność dla byłego pracodawcy?")
    st.markdown('<div class="alert-info">ℹ️ Jeśli TAK — tracisz prawo do Ulgi na Start i Preferencyjnego ZUS. Obowiązuje Pełny ZUS od pierwszego dnia.</div>', unsafe_allow_html=True)

    emp = st.radio(
        "Były pracodawca",
        options=["Nie — brak pracy dla byłego pracodawcy w tej samej działalności",
                 "Tak — świadczę usługi byłemu pracodawcy w tym samym zakresie"],
        index=0 if not d.get("former_employer") else 1,
        label_visibility="collapsed",
    )
    d["former_employer"] = emp.startswith("Tak")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.button("← Wstecz", on_click=go_prev, use_container_width=True)
    with col2:
        st.button("Dalej →", on_click=go_next, use_container_width=True)

# --- KROK: ZBIEG TYTUŁÓW ---
elif step_name == "titles":
    st.subheader("💼 Inne tytuły ubezpieczenia")
    st.write("Czy obok działalności masz inne źródło ubezpieczenia społecznego?")

    title = st.radio(
        "Zbieg tytułów",
        options=[
            "Tylko działalność — brak innych tytułów",
            "Umowa o pracę (UoP) — mam etat",
            "Umowa zlecenie / inne",
        ],
        index={"none": 0, "uop": 1, "other": 2}.get(d.get("employment_type", "none"), 0),
        label_visibility="collapsed",
    )

    if title.startswith("Tylko"):
        d["employment_type"] = "none"
        d["employment_overlap"] = False
        d["employment_salary"] = 0.0
    elif title.startswith("Umowa o pracę"):
        d["employment_type"] = "uop"
        d["employment_overlap"] = True
        st.info(f"Kluczowy próg: {MIN_WAGE_2026:.0f} zł brutto (min. płaca 2026). "
                "Jeśli zarabiasz tyle lub więcej — z działalności płacisz tylko składkę zdrowotną.")
        d["employment_salary"] = st.number_input(
            "Wynagrodzenie brutto z UoP (PLN/msc)",
            min_value=0.0, step=100.0,
            value=d.get("employment_salary", 0.0),
        )
    else:
        d["employment_type"] = "other"
        d["employment_overlap"] = True
        d["employment_salary"] = 0.0

    col1, col2 = st.columns([1, 1])
    with col1:
        st.button("← Wstecz", on_click=go_prev, use_container_width=True)
    with col2:
        st.button("Dalej →", on_click=go_next, use_container_width=True)

# --- KROK: STATUS SZCZEGÓLNY ---
elif step_name == "status":
    st.subheader("🧑‍⚕️ Status szczególny")
    st.write("Czy posiadasz jeden z poniższych statusów?")

    status = st.radio(
        "Status",
        options=["Brak — standardowa sytuacja",
                 "Emeryt — pobieram emeryturę",
                 "Rencista — pobieram rentę z tytułu niezdolności do pracy"],
        index={"none": 0, "retiree": 1, "disability_pensioner": 2}.get(d.get("special_status", "none"), 0),
        label_visibility="collapsed",
    )
    d["special_status"] = {"Brak — standardowa sytuacja": "none",
                            "Emeryt — pobieram emeryturę": "retiree",
                            "Rencista — pobieram rentę z tytułu niezdolności do pracy": "disability_pensioner"}[status]

    col1, col2 = st.columns([1, 1])
    with col1:
        st.button("← Wstecz", on_click=go_prev, use_container_width=True)
    with col2:
        st.button("Dalej →", on_click=go_next, use_container_width=True)

# --- KROK: FORMA OPODATKOWANIA ---
elif step_name == "taxation":
    st.subheader("💰 Forma opodatkowania")
    st.write("Wpływa na wysokość składki zdrowotnej.")

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
        rate = st.selectbox(
            "Stawka ryczałtu (%)",
            options=[2.0, 3.0, 5.5, 8.5, 10.0, 12.0, 15.0, 17.0],
            index=3,
        )
        d["lump_sum_rate"] = rate
        d["estimated_annual_revenue"] = st.number_input(
            "Szacowany roczny przychód (PLN)",
            min_value=0.0, step=1000.0,
            value=d.get("estimated_annual_revenue", 0.0),
            help="Próg dla składki zdrowotnej: 60k / 300k PLN",
        )
    else:
        d["estimated_monthly_income"] = st.number_input(
            "Szacowany miesięczny dochód (PLN) — opcjonalnie",
            min_value=0.0, step=100.0,
            value=d.get("estimated_monthly_income", 0.0),
            help="Do oszacowania składki zdrowotnej. Zostaw 0 = pokażemy minimum.",
        )
        d["estimated_annual_revenue"] = st.number_input(
            "Szacowany roczny przychód (PLN) — opcjonalnie",
            min_value=0.0, step=1000.0,
            value=d.get("estimated_annual_revenue", 0.0),
            help="Do oceny kwalifikacji do Małego ZUS Plus (limit 120 000 PLN).",
        )

    col1, col2 = st.columns([1, 1])
    with col1:
        st.button("← Wstecz", on_click=go_prev, use_container_width=True)
    with col2:
        st.button("Dalej →", on_click=go_next, use_container_width=True)

# --- KROK: PREFERENCJE ---
elif step_name == "preferences":
    st.subheader("⚙️ Twoje preferencje")

    d["wants_ulga"] = st.checkbox(
        "Chcę skorzystać z Ulgi na Start (05 40)",
        value=d.get("wants_ulga", True),
        help="6 pełnych miesięcy bez składek społecznych. Możesz zrezygnować i od razu wejść na Preferencyjny ZUS.",
    )

    chorobowe_disabled = d["wants_ulga"]
    d["wants_chorobowe"] = st.checkbox(
        "Chcę opłacać dobrowolne ubezpieczenie chorobowe",
        value=False if chorobowe_disabled else d.get("wants_chorobowe", False),
        disabled=chorobowe_disabled,
        help="Daje prawo do zasiłku chorobowego i macierzyńskiego. Niedostępne w trakcie Ulgi na Start.",
    )
    if chorobowe_disabled:
        st.caption("ℹ️ Dobrowolne chorobowe niedostępne w trakcie Ulgi na Start.")

    st.markdown('<div class="alert-info">Kliknij <strong>Oblicz</strong> żeby wygenerować pełny harmonogram składek ZUS.</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1])
    with col1:
        st.button("← Wstecz", on_click=go_prev, use_container_width=True)
    with col2:
        st.button("🧮 Oblicz harmonogram", on_click=go_next, use_container_width=True)

# --- KROK: WYNIK ---
elif step_name == "result":
    # Zbuduj input
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
    )

    result = calculate(inp)
    timeline = generate_timeline(result, inp)
    error_info = detect_error(result)

    # Blok kodu
    stage_end_str = result["stage_end"].strftime("%d.%m.%Y") if result["stage_end"] else "bezterminowo"
    st.markdown(f"""
    <div class="code-block">
        <div class="code-label">Aktualny kod tytułu ubezpieczenia</div>
        <div class="code-value">{result['current_code']}</div>
        <div class="code-desc">{result['stage_label']}</div>
        <br>
        <div class="code-label">Obowiązuje od {result['stage_start'].strftime('%d.%m.%Y')} do {stage_end_str}</div>
    </div>
    """, unsafe_allow_html=True)

    # Alert błędnego kodu
    if error_info["cta_visible"]:
        st.markdown(f"""
        <div class="alert-error">
            <strong>⚠️ Sprawdź swój aktualny kod ZUS</strong><br>
            Na podstawie daty startu i historii, Twój prawidłowy kod to <strong>{result['current_code']}</strong>.
            Jeśli Twoje deklaracje ZUS wskazują inny kod — możesz mieć zaległości lub niedopłaty.
            <br><br>📅 <strong>Umów konsultację aby to zweryfikować.</strong>
        </div>
        """, unsafe_allow_html=True)

    # Ostrzeżenia
    for w in result["warnings"]:
        st.markdown(f'<div class="alert-warning">ℹ️ {w}</div>', unsafe_allow_html=True)

    # Harmonogram
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
        st.caption("⚠️ Etapy oznaczone ⚠ mają kwoty prognozowane. Rzeczywiste wartości będą inne po ogłoszeniu oficjalnych wskaźników.")

    # Disclaimer prawny
    st.markdown("""
    <div class="legal">
        Wyniki mają charakter <strong>informacyjny</strong> i nie stanowią porady prawnej ani ubezpieczeniowej.
        Poprawność zależy od prawidłowości wprowadzonych danych. W razie wątpliwości skonsultuj się z biurem rachunkowym lub ZUS.
    </div>
    """, unsafe_allow_html=True)

    st.divider()
    col1, col2 = st.columns([1, 1])
    with col1:
        st.button("← Wstecz", on_click=go_prev, use_container_width=True)
    with col2:
        st.button("↩ Zacznij od nowa", on_click=restart, use_container_width=True)
