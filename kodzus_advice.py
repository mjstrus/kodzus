"""
KODZUS — Generator warstwy doradczej (narracja + rekomendacje).

Zamienia liczby ze scenariuszy w słowne wnioski: co najlepiej zrobić i dlaczego,
konkretny plan krok-po-kroku dopasowany do daty startu i sytuacji, oraz
praktyczne pułapki i podpowiedzi.

To jest warstwa, która sprawia że raport DORADZA, a nie tylko liczy.
"""

from __future__ import annotations
from datetime import date
from dateutil.relativedelta import relativedelta


POLISH_MONTHS = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
                 "lipca", "sierpnia", "września", "października", "listopada", "grudnia"]


def _d(dt: date | None) -> str:
    if dt is None:
        return "bezterminowo"
    return f"{dt.day} {POLISH_MONTHS[dt.month-1]} {dt.year}"


def _money(v: float) -> str:
    return f"{v:,.0f} zł".replace(",", " ")


def build_recommendation(inp, result: dict, timeline: list[dict],
                         scenarios: list[dict], is_planning: bool = False) -> dict:
    """
    Buduje warstwę doradczą.

    Zwraca dict:
      headline       — jedno zdanie: główna rekomendacja
      reasoning      — 2-4 zdania uzasadnienia (dlaczego)
      steps          — lista kroków (str) co zrobić, w kolejności
      pitfalls       — lista pułapek/ostrzeżeń (str)
      recommended    — klucz rekomendowanego wariantu
    """
    rec = next((s for s in scenarios if s.get("recommended")), None)
    if rec is None and scenarios:
        rec = scenarios[0]

    priority = getattr(inp, "priority", "balanced")
    start = inp.start_date
    verb = "planujesz rozpocząć" if is_planning else "rozpocząłeś/aś"

    # --- HEADLINE wg priorytetu ---
    pr_name = {
        "cost": "minimalizację kosztów na starcie",
        "pension": "budowanie wyższej emerytury",
        "protection": "ochronę socjalną (zasiłki)",
        "balanced": "równowagę między kosztem a bezpieczeństwem",
    }.get(priority, "równowagę")

    headline = (f"Przy Twoim priorytecie — {pr_name} — rekomendujemy wariant "
                f"„{rec['name']}”." if rec else "Oto analiza Twojej sytuacji składkowej.")

    # --- REASONING: liczby z rekomendacji ---
    reasoning_parts = []
    if rec and rec.get("horizons"):
        h5 = rec["horizons"].get(60, {})
        reasoning_parts.append(
            f"W tym wariancie przez 5 lat zapłacisz na składki około {_money(h5.get('spent',0))}, "
            f"odkładając przy tym ok. {_money(h5.get('pension',0))} na przyszłą emeryturę.")
        if h5.get("tax_shield", 0) > 0:
            reasoning_parts.append(
                f"Dodatkowo składki obniżą Twój podatek dochodowy o ok. {_money(h5['tax_shield'])} "
                f"w tym okresie.")

    # Porównanie z najtańszym/najdroższym, by pokazać kontekst
    if len(scenarios) > 1:
        by_cost = sorted(scenarios, key=lambda s: s.get("cost_5y", 0))
        cheapest, priciest = by_cost[0], by_cost[-1]
        if rec and rec["key"] != cheapest["key"]:
            diff = rec["cost_5y"] - cheapest["cost_5y"]
            if diff > 0:
                reasoning_parts.append(
                    f"To nie najtańsza opcja — wariant „{cheapest['name']}” jest tańszy o ok. "
                    f"{_money(diff)} przez 5 lat — ale lepiej odpowiada Twojemu priorytetowi.")

    reasoning = " ".join(reasoning_parts)

    # --- KROKI: dopasowane do etapów harmonogramu i daty startu ---
    steps = []
    if not is_planning:
        steps.append(f"Działalność {verb} {_d(start)} — od tego dnia masz 7 dni na zgłoszenie do ZUS.")
    else:
        steps.append(f"Zgłoś działalność na planowaną datę {_d(start)} (CEIDG-1 = jednocześnie zgłoszenie do ZUS).")

    # przejdź po etapach harmonogramu jako plan działania
    seen_stages = []
    for row in timeline:
        if row["stage"] in seen_stages:
            continue
        seen_stages.append(row["stage"])
        code = row["code"]
        if row["stage"] == "ulga":
            steps.append(
                f"Na start zgłoś się z kodem {code} (Ulga na Start) — do {_d(row['date_to'])} "
                f"płacisz tylko składkę zdrowotną. Pamiętaj: na uldze nie masz chorobowego.")
        elif row["stage"] == "preferential":
            steps.append(
                f"Od {_d(row['date_from'])} przejdź na kod {code} (składki preferencyjne) — "
                f"tu możesz dołączyć dobrowolne chorobowe, jeśli zależy Ci na zasiłkach.")
        elif row["stage"] == "mzp":
            steps.append(
                f"Od {_d(row['date_from'])} — jeśli przychód nie przekroczy 120 000 zł rocznie — "
                f"zgłoś Mały ZUS Plus (kod {code}), składając oświadczenie do 31 stycznia.")
        elif row["stage"] == "full":
            steps.append(
                f"Od {_d(row['date_from'])} wchodzisz w pełny ZUS (kod {code}) — to docelowy poziom składek.")

    # --- PUŁAPKI: zależne od sytuacji ---
    pitfalls = []
    # start w trakcie miesiąca
    if start.day != 1:
        ulga_end = next((r["date_to"] for r in timeline if r["stage"] == "ulga"), None)
        pitfalls.append(
            f"Zaczynasz {start.day}. dnia miesiąca, więc miesiąc startu nie liczy się do okresu ulgi — "
            f"6 pełnych miesięcy liczymy od 1. dnia następnego miesiąca"
            + (f" (ulga do {_d(ulga_end)})." if ulga_end else "."))
    # forma opodatkowania a tarcza
    if inp.taxation_form == "scale":
        pitfalls.append(
            "Na skali podatkowej składki zdrowotnej NIE odliczysz od podatku — obniżają go tylko "
            "składki społeczne. Przy wyższych dochodach rozważ liniowy lub ryczałt.")
    elif inp.taxation_form == "linear":
        pitfalls.append(
            "Na liniowym odliczysz składkę zdrowotną od dochodu, ale tylko do limitu 14 100 zł rocznie.")
    elif inp.taxation_form == "lump_sum":
        pitfalls.append(
            "Na ryczałcie pilnuj progów przychodu (60 / 300 tys. zł) — przekroczenie skokowo podnosi "
            "składkę zdrowotną.")
    # MZP limit
    if any(r["stage"] == "mzp" for r in timeline):
        pitfalls.append(
            "Mały ZUS Plus wymaga przychodu poniżej 120 000 zł rocznie i nie łączy się z Ulgą na Start "
            "w tym samym okresie — oświadczenie złóż w terminie do 31 stycznia.")

    return {
        "headline": headline,
        "reasoning": reasoning,
        "steps": steps,
        "pitfalls": pitfalls,
        "recommended": rec["key"] if rec else None,
    }
