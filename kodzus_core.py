"""
KODZUS — Logika kalkulatora ZUS (Python).
Przeniesiona 1:1 z wersji PHP. Czysta logika — zero zależności od Streamlit.

Algorytm Pełnego Miesiąca (Wariant A — zgodny z ustawą):
  Start 1. dnia miesiąca  → 6 pełnych miesięcy od tego dnia
  Start N. dnia (N > 1)   → miesiąc startu NIE wlicza się,
                            liczymy od 1. dnia następnego miesiąca
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from dateutil.relativedelta import relativedelta
import calendar


# =============================================================================
# DANE KWOTOWE ZUS 2026 (źródła: ZUS, GUS, Biznes.gov.pl)
# =============================================================================

RATES_2026 = {
    "year": 2026,
    "is_forecast": False,
    "min_wage": 4806.00,
    "avg_wage_forecast": 9420.00,
    "preferential_base": 1441.80,
    "full_zus_base": 5652.00,
    "mzp_income_limit": 120000.00,
    "monthly_social": {
        "ulga": {"total_without_chorobowe": 0.0, "total_with_chorobowe": 0.0},
        "preferential": {
            "total_without_chorobowe": 420.89,
            "total_with_chorobowe": 456.21,
        },
        "full": {
            "total_with_fp_without_chorobowe": 1926.76,
            "total_with_chorobowe_and_fp": 2065.23,
        },
    },
    "healthcare": {
        "min_monthly_from_feb": 432.54,
        "min_monthly_january": 314.96,
        "rate_scale": 9.0,
        "rate_linear": 4.9,
        "min_base_scale_linear": 4806.00,
        "lump_sum": {
            "tier_1": {"income_max": 60000.0, "base": 5537.18, "monthly": 498.35},
            "tier_2": {"income_max": 300000.0, "base": 9228.64, "monthly": 830.58},
            "tier_3": {"base": 16611.55, "monthly": 1495.04},
        },
        "tax_card": {"base": 4806.00, "monthly": 432.54},
    },
}

RATES_2027_FORECAST = {
    "year": 2027,
    "is_forecast": True,
    "forecast_disclaimer": (
        "Kwoty na 2027 są prognozowane na podstawie trendów historycznych "
        "i nie są oficjalnymi danymi ZUS/GUS. Zaktualizuj po ogłoszeniu oficjalnych kwot."
    ),
    "min_wage": 4970.00,
    "avg_wage_forecast": 10200.00,
    "preferential_base": 1491.00,
    "full_zus_base": 6120.00,
    "mzp_income_limit": 120000.00,
    "monthly_social": {
        "ulga": {"total_without_chorobowe": 0.0, "total_with_chorobowe": 0.0},
        "preferential": {
            "total_without_chorobowe": 435.42,
            "total_with_chorobowe": 471.95,
        },
        "full": {
            "total_with_fp_without_chorobowe": 2086.96,
            "total_with_chorobowe_and_fp": 2236.90,
        },
    },
    "healthcare": {
        "min_monthly_from_feb": 447.30,
        "min_monthly_january": 432.54,
        "rate_scale": 9.0,
        "rate_linear": 4.9,
        "min_base_scale_linear": 4970.00,
        "lump_sum": {
            "tier_1": {"income_max": 60000.0, "base": 6000.00, "monthly": 540.00},
            "tier_2": {"income_max": 300000.0, "base": 10000.00, "monthly": 900.00},
            "tier_3": {"base": 18000.00, "monthly": 1620.00},
        },
        "tax_card": {"base": 4970.00, "monthly": 447.30},
    },
}


def get_rates(year: int) -> dict:
    """Zwraca dane kwotowe dla roku. Fallback na prognozę dla lat > 2027."""
    if year <= 2026:
        return RATES_2026
    if year == 2027:
        return RATES_2027_FORECAST
    # Lata > 2027 — użyj prognozy 2027 z disclaimerem
    rates = dict(RATES_2027_FORECAST)
    rates["year"] = year
    rates["forecast_disclaimer"] = (
        f"Kwoty dla roku {year} są prognozowane (dane z 2027). "
        "Rzeczywiste wartości będą inne."
    )
    return rates


# =============================================================================
# HELPER: Algorytm Pełnego Miesiąca
# =============================================================================

def last_day_of_month(d: date) -> int:
    return calendar.monthrange(d.year, d.month)[1]


def compute_stage_end(start: date, months: int) -> date:
    """
    Wariant A: koniec etapu trwającego `months` pełnych miesięcy.
    Start 1. dnia → liczymy od tego miesiąca.
    Start > 1. dnia → miesiąc startu nie wlicza się, liczymy od następnego.
    """
    if start.day == 1:
        first_full = start
    else:
        # Pierwszy dzień następnego miesiąca
        if start.month == 12:
            first_full = date(start.year + 1, 1, 1)
        else:
            first_full = date(start.year, start.month + 1, 1)

    # Przesuń o `months` miesięcy, cofnij 1 dzień
    end = first_full + relativedelta(months=months) - relativedelta(days=1)
    return end


def next_day(d: date) -> date:
    return d + relativedelta(days=1)


def months_between(d1: date, d2: date) -> int:
    """Liczba pełnych miesięcy między dwiema datami."""
    rd = relativedelta(d2, d1)
    return rd.years * 12 + rd.months


# =============================================================================
# KALKULATOR
# =============================================================================

MIN_WAGE_2026 = 4806.00
ULGA_MONTHS = 6
PREFERENTIAL_MONTHS = 24
MZP_MONTHS = 36
PREVIOUS_ACTIVITY_BLOCK_MONTHS = 60
# Działalność nierejestrowana: przychód miesięczny < 75% min. wynagrodzenia
UNREGISTERED_THRESHOLD_PCT = 0.75
# Najniższa emerytura 2026 (do progu zwolnienia emeryta ze zdrowotnej)
# Waloryzacja 1 marca 2026: do 29.02 = 1878,91; od 1.03 = 1978,49 (wskaźnik 5,3%)
LOWEST_PENSION_2026_JAN_FEB = 1878.91
LOWEST_PENSION_2026_FROM_MAR = 1978.49


def get_lowest_pension(d: date) -> float:
    """Najniższa emerytura na daną datę (waloryzacja 1 marca)."""
    if d.year < 2026:
        return LOWEST_PENSION_2026_JAN_FEB
    if d.year == 2026 and d.month < 3:
        return LOWEST_PENSION_2026_JAN_FEB
    # Od marca 2026 i później (dla lat kolejnych brak oficjalnych danych — przybliżenie)
    return LOWEST_PENSION_2026_FROM_MAR


@dataclass
class WizardInput:
    start_date: date
    calculation_date: date
    had_previous_activity: bool = False
    previous_end_date: date | None = None
    former_employer: bool = False
    employment_overlap: bool = False
    employment_type: str = "none"  # none | uop | other
    employment_salary: float = 0.0
    special_status: str = "none"  # none | retiree | disability_pensioner
    wants_ulga: bool = True
    wants_chorobowe: bool = False
    taxation_form: str = "scale"  # scale | linear | lump_sum | tax_card
    lump_sum_rate: float = 8.5
    estimated_monthly_income: float = 0.0
    estimated_annual_revenue: float = 0.0
    # Działalność nierejestrowana — sprawdzane PRZED ścieżką JDG
    check_unregistered: bool = False     # czy rozważa działalność nierejestrowaną
    monthly_revenue_unreg: float = 0.0   # szacowany przychód miesięczny (do progu 75%)
    # Dane do zwolnień ze składki ZDROWOTNEJ
    pension_amount: float = 0.0          # emerytura brutto/msc (zwolnienie emeryta)
    monthly_revenue_activity: float = 0.0  # przychód miesięczny z działalności (do progu 50%)


def _get_code(stage: str, wants_chorobowe: bool) -> str:
    codes = {
        "ulga": "05 40",
        "preferential": "05 72" if wants_chorobowe else "05 70",
        "mzp": "05 92" if wants_chorobowe else "05 90",
        "full": "05 12" if wants_chorobowe else "05 10",
    }
    return codes.get(stage, "05 10")


STAGE_LABELS = {
    "ulga": "Ulga na Start",
    "preferential": "Preferencyjny ZUS",
    "mzp": "Mały ZUS Plus",
    "full": "Pełny ZUS",
}


def _build_full_zus_result(inp: WizardInput, exclusion_reason: str | None,
                            warnings: list[str]) -> dict:
    code = "05 12" if inp.wants_chorobowe else "05 10"
    path = [{
        "stage": "full",
        "code": code,
        "label": "Pełny ZUS",
        "from": inp.start_date,
        "to": None,
    }]
    return {
        "current_code": code,
        "current_stage": "full",
        "stage_label": "Pełny ZUS",
        "stage_start": inp.start_date,
        "stage_end": None,
        "exclusion_reason": exclusion_reason,
        "warnings": warnings,
        "path": path,
        "wants_chorobowe": inp.wants_chorobowe,
        "has_ulga": False,
        "has_preferential": False,
        "can_mzp": False,
        "social_exempt": False,
        "start_date": inp.start_date,
        "calculation_date": inp.calculation_date,
    }


def _is_ulga_blocked(start: date, prev_end: date | None) -> bool:
    if prev_end is None:
        return True  # brak daty → bezpieczna strona
    return months_between(prev_end, start) < PREVIOUS_ACTIVITY_BLOCK_MONTHS


def _can_use_mzp(inp: WizardInput) -> bool:
    if inp.former_employer:
        return False
    if inp.estimated_annual_revenue > 120000:
        return False
    if inp.taxation_form == "tax_card":
        return False
    return True


def _check_unregistered(inp: WizardInput, min_wage: float) -> dict | None:
    """
    Sprawdza czy kwalifikuje się do działalności nierejestrowanej.
    Warunki (art. 5 ust. 1 Prawa przedsiębiorców):
      - przychód miesięczny < 75% minimalnego wynagrodzenia
      - brak działalności gospodarczej w ostatnich 60 miesiącach
    Zwraca dict-wynik jeśli kwalifikuje, w przeciwnym razie None.
    """
    threshold = round(min_wage * UNREGISTERED_THRESHOLD_PCT, 2)
    revenue = inp.monthly_revenue_unreg

    qualifies_revenue = revenue <= threshold
    qualifies_history = not inp.had_previous_activity

    if qualifies_revenue and qualifies_history:
        return {
            "current_code": "—",
            "current_stage": "unregistered",
            "stage_label": "Działalność nierejestrowana",
            "stage_start": inp.start_date,
            "stage_end": None,
            "exclusion_reason": None,
            "warnings": [
                f"Kwalifikujesz się do DZIAŁALNOŚCI NIEREJESTROWANEJ: przychód miesięczny "
                f"({revenue:.2f} PLN) nie przekracza progu 75% min. wynagrodzenia ({threshold:.2f} PLN) "
                f"i nie prowadziłeś działalności w ostatnich 60 miesiącach.",
                "W działalności nierejestrowanej NIE rejestrujesz firmy w CEIDG, NIE masz numeru ZUS "
                "i NIE płacisz składek (ani społecznych, ani zdrowotnej). Rozliczasz tylko podatek dochodowy.",
                "UWAGA: jeśli w którymkolwiek miesiącu przekroczysz próg przychodu, masz 7 dni na "
                "rejestrację w CEIDG — wtedy wchodzisz w normalną ścieżkę JDG (Ulga na Start itd.).",
            ],
            "path": [{
                "stage": "unregistered", "code": "—",
                "label": "Działalność nierejestrowana",
                "from": inp.start_date, "to": None,
            }],
            "wants_chorobowe": False,
            "has_ulga": False,
            "has_preferential": False,
            "can_mzp": False,
            "social_exempt": True,
            "is_unregistered": True,
            "unreg_threshold": threshold,
            "start_date": inp.start_date,
            "calculation_date": inp.calculation_date,
        }

    # Nie kwalifikuje — zwróć powód (jako ostrzeżenie do dalszej ścieżki JDG)
    reasons = []
    if not qualifies_revenue:
        reasons.append(
            f"przychód {revenue:.2f} PLN przekracza próg działalności nierejestrowanej "
            f"({threshold:.2f} PLN = 75% min. wynagrodzenia)"
        )
    if not qualifies_history:
        reasons.append("prowadziłeś działalność w ostatnich 60 miesiącach")
    return {"_unreg_rejected": "; ".join(reasons)}


def _find_current_stage(path: list[dict], calc_date: date) -> dict:
    for stage in path:
        after_start = calc_date >= stage["from"]
        before_end = stage["to"] is None or calc_date <= stage["to"]
        if after_start and before_end:
            return stage
    return path[0]


def calculate(inp: WizardInput) -> dict:
    """Główna funkcja kalkulacji kodu ZUS i ścieżki."""
    rates = get_rates(inp.calculation_date.year)
    min_wage = rates.get("min_wage", MIN_WAGE_2026)
    warnings: list[str] = []
    exclusion_reason = None

    # KROK 0: Działalność nierejestrowana (sprawdzana PRZED ścieżką JDG)
    if inp.check_unregistered:
        unreg = _check_unregistered(inp, min_wage)
        if unreg and unreg.get("is_unregistered"):
            return unreg
        if unreg and unreg.get("_unreg_rejected"):
            warnings.append(
                f"Nie kwalifikujesz się do działalności nierejestrowanej "
                f"({unreg['_unreg_rejected']}). Poniżej standardowa ścieżka JDG."
            )

    # KROK 1: Zbieg z UoP — NIE zmienia kodu ani ścieżki ulg.
    # Etat >= min. płacy → składki społeczne z działalności są ZWOLNIONE
    # (przedsiębiorca idzie normalną ścieżką 05 40 → 05 70 → ..., ale płaci tylko zdrowotną).
    # Źródło: art. 9 ustawy o sus + interpretacje ZUS (przykłady z dokumentu).
    social_exempt = False  # czy składki społeczne są zwolnione przez etat

    if inp.employment_overlap and inp.employment_type == "uop":
        if inp.employment_salary >= min_wage:
            social_exempt = True
            warnings.append(
                f"Zbieg z umową o pracę: wynagrodzenie z etatu ({inp.employment_salary:.2f} PLN) "
                f"≥ płacy minimalnej ({min_wage:.2f} PLN). Z działalności jesteś ZWOLNIONY ze składek "
                f"społecznych — opłacasz tylko składkę zdrowotną. Kod tytułu ubezpieczenia pozostaje "
                f"zgodny z Twoim etapem (ulga/preferencyjny/MZP/pełny), zmienia się tylko zakres składek."
            )
        elif inp.employment_salary > 0:
            warnings.append(
                f"Zbieg z umową o pracę: wynagrodzenie z etatu ({inp.employment_salary:.2f} PLN) "
                f"< płacy minimalnej ({min_wage:.2f} PLN). Obowiązują pełne składki ZUS z obu tytułów."
            )
        else:
            warnings.append(
                "Zbieg z umową o pracę — nie podano wynagrodzenia. Zakładamy poniżej płacy "
                "minimalnej (pełne składki z działalności). Podaj wynagrodzenie dla dokładnego wyniku."
            )

    if inp.employment_overlap and inp.employment_type == "other":
        warnings.append(
            "Zbieg tytułów ze zleceniem/innym tytułem — zasady zależą od indywidualnej "
            "sytuacji. Skonsultuj się z ZUS lub biurem rachunkowym."
        )

    # KROK 2: Status szczególny
    if inp.special_status in ("retiree", "disability_pensioner"):
        label = ("emeryt pobierający emeryturę" if inp.special_status == "retiree"
                 else "rencista pobierający rentę z tytułu niezdolności do pracy")
        return _build_full_zus_result(
            inp,
            f"Jako {label} podlegasz ubezpieczeniu emerytalnemu i rentowemu obowiązkowo.",
            warnings
        )

    # KROK 3: Były pracodawca
    if inp.former_employer:
        return _build_full_zus_result(
            inp,
            "Wykonujesz działalność na rzecz byłego pracodawcy w tym samym zakresie. "
            "Nie przysługuje Ulga na Start ani Preferencyjny ZUS.",
            warnings
        )

    # KROK 4: Poprzednia działalność blokuje Ulgę
    has_ulga = inp.wants_ulga

    # Chorobowe niedostępne gdy składki społeczne zwolnione przez etat
    if social_exempt and inp.wants_chorobowe:
        inp.wants_chorobowe = False
        warnings.append(
            "Dobrowolne ubezpieczenie chorobowe jest niedostępne: przy zbiegu z etatem "
            "≥ płacy minimalnej składki społeczne z działalności są dobrowolne, więc nie "
            "można zgłosić się do chorobowego z tytułu działalności."
        )

    if has_ulga and inp.had_previous_activity:
        if _is_ulga_blocked(inp.start_date, inp.previous_end_date):
            has_ulga = False
            exclusion_reason = (
                "Prowadziłeś/aś działalność w ciągu ostatnich 60 miesięcy — "
                "Ulga na Start nie przysługuje. Możesz skorzystać z Preferencyjnego ZUS."
            )
            warnings.append(exclusion_reason)

    # KROK 5: Buduj ścieżkę
    path = []
    preferential_start = inp.start_date

    if has_ulga:
        ulga_end = compute_stage_end(inp.start_date, ULGA_MONTHS)
        preferential_start = next_day(ulga_end)
        path.append({
            "stage": "ulga", "code": _get_code("ulga", inp.wants_chorobowe),
            "label": "Ulga na Start", "from": inp.start_date, "to": ulga_end,
        })

    preferential_end = compute_stage_end(preferential_start, PREFERENTIAL_MONTHS)
    mzp_start = next_day(preferential_end)
    path.append({
        "stage": "preferential", "code": _get_code("preferential", inp.wants_chorobowe),
        "label": "Preferencyjny ZUS", "from": preferential_start, "to": preferential_end,
    })

    can_mzp = _can_use_mzp(inp)
    if can_mzp:
        mzp_end = compute_stage_end(mzp_start, MZP_MONTHS)
        full_start = next_day(mzp_end)
        path.append({
            "stage": "mzp", "code": _get_code("mzp", inp.wants_chorobowe),
            "label": "Mały ZUS Plus", "from": mzp_start, "to": mzp_end,
        })
    else:
        full_start = mzp_start
        if inp.estimated_annual_revenue > 120000:
            warnings.append(
                "Roczny przychód przekracza 120 000 PLN — brak kwalifikacji do Małego ZUS Plus. "
                "Po Preferencyjnym przejdziesz na Pełny ZUS."
            )

    path.append({
        "stage": "full", "code": _get_code("full", inp.wants_chorobowe),
        "label": "Pełny ZUS", "from": full_start, "to": None,
    })

    current = _find_current_stage(path, inp.calculation_date)

    return {
        "current_code": current["code"],
        "current_stage": current["stage"],
        "stage_label": current["label"],
        "stage_start": current["from"],
        "stage_end": current["to"],
        "exclusion_reason": exclusion_reason,
        "warnings": warnings,
        "path": path,
        "wants_chorobowe": inp.wants_chorobowe,
        "has_ulga": has_ulga,
        "has_preferential": True,
        "can_mzp": can_mzp,
        "social_exempt": social_exempt,
        "start_date": inp.start_date,
        "calculation_date": inp.calculation_date,
    }


# =============================================================================
# HARMONOGRAM (TIMELINE)
# =============================================================================

def compute_social(stage: str, wants_chorobowe: bool, rates: dict) -> float:
    s = rates["monthly_social"]
    if stage == "ulga":
        return 0.0
    if stage in ("preferential", "mzp"):
        key = "total_with_chorobowe" if wants_chorobowe else "total_without_chorobowe"
        return s["preferential"][key]
    # full
    key = "total_with_chorobowe_and_fp" if wants_chorobowe else "total_with_fp_without_chorobowe"
    return s["full"][key]


def compute_healthcare(taxation_form: str, monthly_income: float,
                       annual_revenue: float, seg_from: date, rates: dict,
                       inp: "WizardInput | None" = None) -> float:
    hc = rates["healthcare"]
    is_january = seg_from.month == 1
    min_amount = hc["min_monthly_january"] if is_january else hc["min_monthly_from_feb"]
    min_wage = rates.get("min_wage", MIN_WAGE_2026)

    # --- ZWOLNIENIA ZE SKŁADKI ZDROWOTNEJ ---
    if inp is not None:
        # 1. Emeryt o niskim świadczeniu: emerytura brutto ≤ min. wynagrodzenie
        #    ORAZ (przychód z działalności ≤ 50% najniższej emerytury LUB karta podatkowa)
        if inp.special_status == "retiree" and inp.pension_amount > 0:
            lowest_pension = get_lowest_pension(seg_from)
            cond_pension = inp.pension_amount <= min_wage
            cond_revenue = (inp.monthly_revenue_activity <= 0.5 * lowest_pension
                            or taxation_form == "tax_card")
            if cond_pension and cond_revenue:
                return 0.0

        # 2. Pracownik o niskiej podstawie: podstawa z etatu ≤ min. wynagrodzenie
        #    ORAZ przychód z działalności ≤ 50% min. wynagrodzenia ORAZ ryczałt
        if (inp.employment_type == "uop" and 0 < inp.employment_salary <= min_wage
                and taxation_form == "lump_sum"
                and 0 < inp.monthly_revenue_activity <= 0.5 * min_wage):
            return 0.0

    if taxation_form == "scale":
        if monthly_income > 0:
            base = max(monthly_income, hc["min_base_scale_linear"])
            return round(base * hc["rate_scale"] / 100, 2)
        return min_amount

    if taxation_form == "linear":
        if monthly_income > 0:
            return round(max(monthly_income * hc["rate_linear"] / 100, min_amount), 2)
        return min_amount

    if taxation_form == "lump_sum":
        if is_january:
            return hc["min_monthly_january"]
        tiers = hc["lump_sum"]
        if annual_revenue <= tiers["tier_1"]["income_max"] or annual_revenue == 0:
            return tiers["tier_1"]["monthly"]
        if annual_revenue <= tiers["tier_2"]["income_max"]:
            return tiers["tier_2"]["monthly"]
        return tiers["tier_3"]["monthly"]

    if taxation_form == "tax_card":
        return hc["tax_card"]["monthly"]

    return min_amount


def split_by_year(d_from: date, d_to: date):
    """Dzieli okres na segmenty roczne."""
    segments = []
    seg_start = d_from
    while seg_start <= d_to:
        year_end = date(seg_start.year, 12, 31)
        seg_end = min(year_end, d_to)
        segments.append((seg_start, seg_end))
        seg_start = date(seg_start.year + 1, 1, 1)
    return segments


def generate_timeline(result: dict, inp: WizardInput) -> list[dict]:
    """Buduje harmonogram 5-letni z kwotami."""
    # Działalność nierejestrowana — brak składek ZUS, brak harmonogramu
    if result.get("is_unregistered"):
        return []

    path = result["path"]
    horizon = inp.calculation_date + relativedelta(years=5)
    timeline = []

    for stage_data in path:
        d_from = stage_data["from"]
        d_to = stage_data["to"] if stage_data["to"] else horizon

        for seg_from, seg_to in split_by_year(d_from, d_to):
            year = seg_from.year
            rates = get_rates(year)
            social = compute_social(stage_data["stage"], result["wants_chorobowe"], rates)
            # Zwolnienie ze składek społecznych przez etat ≥ min. płacy
            if result.get("social_exempt"):
                social = 0.0
            healthcare = compute_healthcare(
                inp.taxation_form, inp.estimated_monthly_income,
                inp.estimated_annual_revenue, seg_from, rates, inp
            )
            timeline.append({
                "stage_name": STAGE_LABELS.get(stage_data["stage"], stage_data["stage"]),
                "code": stage_data["code"],
                "date_from": seg_from,
                "date_to": seg_to,
                "monthly_social": round(social, 2),
                "monthly_healthcare": round(healthcare, 2),
                "monthly_total": round(social + healthcare, 2),
                "is_forecast": rates.get("is_forecast", False),
                "stage": stage_data["stage"],
            })

    # Scal segmenty tego samego etapu i roku
    merged = []
    for row in timeline:
        if (merged and merged[-1]["stage"] == row["stage"]
                and merged[-1]["date_to"].year == row["date_to"].year
                and merged[-1]["monthly_total"] == row["monthly_total"]):
            merged[-1]["date_to"] = row["date_to"]
        else:
            merged.append(row)
    return merged


# =============================================================================
# WYKRYWANIE BŁĘDNEGO KODU
# =============================================================================

def detect_error(result: dict) -> dict:
    """Wykrywa czy użytkownik powinien sprawdzić swój kod ZUS."""
    calc_date = result["calculation_date"]
    start_date = result["start_date"]
    days_active = (calc_date - start_date).days

    if days_active < 30:
        return {"cta_visible": False, "confidence": "low", "boundary_warning": None}

    confidence = "high"
    boundary_warning = None
    stage_end = result.get("stage_end")

    if stage_end is not None:
        days_to_end = (stage_end - calc_date).days
        if 0 <= days_to_end <= 30:
            confidence = "medium"
            boundary_warning = (
                f"Za {days_to_end} dni nastąpi zmiana kodu ZUS. "
                "Upewnij się że masz złożone wymagane dokumenty w ZUS."
            )

    return {
        "cta_visible": True,
        "confidence": confidence,
        "boundary_warning": boundary_warning,
        "should_be_code": result["current_code"],
    }
