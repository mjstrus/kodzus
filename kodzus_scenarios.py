"""
KODZUS — Silnik scenariuszy składkowych.

Liczy kilka realnych strategii opłacania składek ZUS i porównuje je w trzech
wymiarach: łączny koszt (5 lat), część emerytalna (ile odłożone na emeryturę),
poziom ochrony socjalnej (chorobowe/zasiłki).

Scenariusze:
  - cost        : Najniższe koszty (maks. ulgi, minimum podstawy, bez chorobowego)
  - pension     : Najwięcej na emeryturę (rezygnacja z ulg, pełna podstawa)
  - protection  : Bezpieczeństwo socjalne (chorobowe wszędzie gdzie można)
  - balanced    : Zrównoważony (ulgi na starcie + chorobowe)
  - optimal     : Optymalny — dopasowany do priorytetu użytkownika

Realne dźwignie wyboru (zgodne z przepisami):
  - rezygnacja z Ulgi na Start / Preferencyjnego (dobrowolna)
  - dobrowolne ubezpieczenie chorobowe (tak/nie)
  - (podstawa wyższa niż minimum — uproszczona jako wejście w pełną podstawę)
"""

from __future__ import annotations
from dataclasses import replace
from datetime import date


# Udział składki emerytalnej w bazie (do szacunku "ile na emeryturę")
PENSION_RATE = 0.1952


def _stage_base(stage: str, rates: dict) -> float:
    """Podstawa wymiaru składek społecznych dla etapu (do szacunku emerytalnej)."""
    if stage == "ulga":
        return 0.0
    if stage == "preferential":
        return rates.get("preferential_base", 0.0)
    if stage == "mzp":
        # MZP zależne od dochodu — przyjmij średnio ~50% pełnej podstawy jako przybliżenie
        return rates.get("full_zus_base", 0.0) * 0.5
    if stage == "full":
        return rates.get("full_zus_base", 0.0)
    return 0.0


def _metrics_for_timeline(timeline: list[dict], inp,
                          horizons=(12, 36, 60)) -> dict:
    """
    Liczy metryki w trzech horyzontach (domyślnie 1/3/5 lat = 12/36/60 msc).
    Dla każdego horyzontu: wydano (koszt składek), odłożono na emeryturę,
    obniżono podatek (tarcza podatkowa).

    Zwraca:
      horizons: {12: {...}, 36: {...}, 60: {...}}, gdzie każdy ma:
        spent, pension, tax_shield
      plus: has_sick (bool), any_social (bool)
    """
    from kodzus_core import get_rates, compute_tax_shield
    from dateutil.relativedelta import relativedelta

    out = {"horizons": {}, "has_sick": False, "any_social": False}
    if not timeline:
        for h in horizons:
            out["horizons"][h] = {"spent": 0.0, "pension": 0.0, "tax_shield": 0.0}
        return out

    start = timeline[0]["date_from"]
    max_h = max(horizons)

    # Akumulatory narastające
    acc_spent = 0.0
    acc_pension = 0.0
    acc_shield = 0.0
    snapshots = {}

    lump_rate = getattr(inp, "lump_sum_rate", 0.12) or 0.12
    monthly_income = getattr(inp, "estimated_monthly_income", 0.0) or 0.0

    cur = start
    month_idx = 0
    while month_idx < max_h:
        active = None
        for row in timeline:
            d_to = row["date_to"] or (start + relativedelta(months=max_h))
            if row["date_from"] <= cur <= d_to:
                active = row
                break
        if active:
            acc_spent += active["monthly_total"]
            if active["monthly_social"] > 0:
                out["any_social"] = True
                rates = get_rates(cur.year)
                base = _stage_base(active["stage"], rates)
                acc_pension += base * PENSION_RATE
            # tarcza podatkowa za ten miesiąc
            acc_shield += compute_tax_shield(
                inp.taxation_form, active["monthly_social"],
                active["monthly_healthcare"], monthly_income, lump_rate)

        month_idx += 1
        cur = cur + relativedelta(months=1)
        if month_idx in horizons:
            snapshots[month_idx] = {
                "spent": round(acc_spent, 2),
                "pension": round(acc_pension, 2),
                "tax_shield": round(acc_shield, 2),
            }

    out["horizons"] = snapshots

    for row in timeline:
        code = row["code"].replace(" ", "")
        if len(code) >= 4 and code[3] == "2":
            out["has_sick"] = True
            break

    return out


def _protection_level(has_sick: bool, any_social: bool) -> tuple[str, int]:
    """Zwraca (etykieta, poziom 0-3) ochrony socjalnej."""
    if has_sick:
        return ("Pełna (chorobowe + zasiłki)", 3)
    if any_social:
        return ("Podstawowa (bez chorobowego)", 1)
    return ("Brak (tylko zdrowotne)", 0)


def compute_strategy_scenarios(inp, selected: list[str] | None = None) -> list[dict]:
    """
    Liczy wybrane scenariusze strategii składkowych.

    inp       — WizardInput użytkownika
    selected  — lista kluczy scenariuszy do policzenia (None = wszystkie)

    Zwraca listę dict z polami:
      key, name, subtitle, for_whom, cost_5y, pension_5y, protection_label,
      protection_level, first_total, first_code, recommended (bool)
    """
    from kodzus_core import calculate, generate_timeline

    all_keys = ["cost", "pension", "protection", "balanced", "optimal"]
    keys = selected if selected else all_keys

    # Definicje scenariuszy jako transformacje wejścia
    def variant(key):
        """Zwraca zmodyfikowany input dla danego scenariusza."""
        if key == "cost":
            # Maks. ulgi, bez chorobowego
            return replace(inp, wants_ulga=True, wants_chorobowe=False)
        if key == "pension":
            # Rezygnacja z ulg → szybciej pełna podstawa (więcej emerytalnej)
            return replace(inp, wants_ulga=False, wants_chorobowe=False)
        if key == "protection":
            # Najwcześniejsza pełna ochrona: rezygnacja z ulgi (chorobowe niedostępne na uldze)
            # → od razu preferencyjny z chorobowym
            return replace(inp, wants_ulga=False, wants_chorobowe=True)
        if key == "balanced":
            # Ulgi na starcie + chorobowe (chorobowe wchodzi po uldze)
            return replace(inp, wants_ulga=True, wants_chorobowe=True)
        if key == "optimal":
            # Dopasowany do priorytetu użytkownika
            pr = getattr(inp, "priority", "balanced")
            if pr == "cost":
                return replace(inp, wants_ulga=True, wants_chorobowe=False)
            if pr == "pension":
                return replace(inp, wants_ulga=False, wants_chorobowe=False)
            if pr == "protection":
                return replace(inp, wants_ulga=True, wants_chorobowe=True)
            return replace(inp, wants_ulga=True, wants_chorobowe=True)
        return inp

    meta = {
        "cost": {
            "name": "Najniższe koszty",
            "subtitle": "Maksymalne ulgi, minimum składek, bez chorobowego",
            "for_whom": "Dla osób, które na starcie chcą płacić jak najmniej i godzą się na brak zasiłków.",
        },
        "pension": {
            "name": "Najwięcej na emeryturę",
            "subtitle": "Rezygnacja z ulg, składki od pełnej podstawy",
            "for_whom": "Dla osób, którym zależy na wyższej przyszłej emeryturze i stać je na wyższe składki od początku.",
        },
        "protection": {
            "name": "Bezpieczeństwo socjalne",
            "subtitle": "Najwcześniejsze chorobowe — rezygnacja z ulgi dla pełnej ochrony od startu",
            "for_whom": "Dla osób ceniących ochronę od pierwszego dnia: zasiłek chorobowy, macierzyński, opiekuńczy (np. planujący dziecko).",
        },
        "balanced": {
            "name": "Zrównoważony",
            "subtitle": "Ulgi na starcie + ochrona chorobowa",
            "for_whom": "Złoty środek: niski koszt gdy firma się rozkręca, ale z ochroną zasiłkową.",
        },
        "optimal": {
            "name": "Optymalny dla Ciebie",
            "subtitle": "Dopasowany do Twojego priorytetu",
            "for_whom": "Rekomendacja na podstawie tego, co wskazałeś jako najważniejsze.",
        },
    }

    scenarios = []
    for key in keys:
        if key not in meta:
            continue
        try:
            alt = variant(key)
            r = calculate(alt)
            tl = generate_timeline(r, alt)
            if not tl:
                continue
            m = _metrics_for_timeline(tl, alt)
            prot_label, prot_level = _protection_level(m["has_sick"], m["any_social"])
            first = tl[0]
            h = m["horizons"]
            scenarios.append({
                "key": key,
                "name": meta[key]["name"],
                "subtitle": meta[key]["subtitle"],
                "for_whom": meta[key]["for_whom"],
                "horizons": h,                       # {12:{spent,pension,tax_shield}, 36:..., 60:...}
                "cost_5y": h.get(60, {}).get("spent", 0.0),
                "pension_5y": h.get(60, {}).get("pension", 0.0),
                "tax_5y": h.get(60, {}).get("tax_shield", 0.0),
                "protection_label": prot_label,
                "protection_level": prot_level,
                "first_total": first["monthly_total"],
                "first_code": first["code"],
                "recommended": (key == "optimal"),
            })
        except Exception:
            continue

    return scenarios
