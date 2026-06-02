"""
KODZUS — Moduł importu zbiorczego dla biur rachunkowych.

Funkcje:
  - parse_import()    : wczytanie CSV/Excel z klientami
  - verify_batch()    : zbiorcza weryfikacja (prawidłowy vs aktualny kod)
  - build_report_df() : tabela raportu końcowego
  - export_excel()    : eksport raportu do .xlsx
  - build_batch_ics() : zbiorczy kalendarz zmian kodów dla wszystkich klientów

Szablon kolumn (CSV/Excel) — przygotowany pod docelowy import do Frappe:
  nip                 (wymagane)  10 cyfr
  nazwa               (wymagane)  nazwa klienta / firmy
  data_startu         (wymagane)  RRRR-MM-DD — data rozpoczęcia działalności
  aktualny_kod        (wymagane)  np. "05 70" — kod stosowany teraz
  forma_opodatkowania (opcjon.)   scale|linear|lump_sum|tax_card (domyślnie scale)
  byly_pracodawca     (opcjon.)   tak|nie (domyślnie nie)
  zbieg_uop           (opcjon.)   tak|nie (domyślnie nie)
  wynagrodzenie_uop   (opcjon.)   kwota brutto z UoP (domyślnie 0)
  status              (opcjon.)   brak|emeryt|rencista (domyślnie brak)
  chce_chorobowe      (opcjon.)   tak|nie (domyślnie nie)
  przychod_roczny     (opcjon.)   szacowany roczny przychód (domyślnie 0)
"""

from __future__ import annotations
import io
from datetime import date, datetime
import pandas as pd

from kodzus_core import WizardInput, calculate, generate_timeline
from kodzus_gus import validate_nip
from kodzus_ics import generate_ics, _make_event, PRODID


# Mapowanie wartości tekstowych z importu na enum kodu
_STATUS_MAP = {
    "brak": "none", "": "none", "none": "none",
    "emeryt": "retiree", "emerytka": "retiree",
    "rencista": "disability_pensioner", "rencistka": "disability_pensioner",
}
_TAX_MAP = {
    "scale": "scale", "skala": "scale", "skala podatkowa": "scale", "": "scale",
    "linear": "linear", "liniowy": "linear", "podatek liniowy": "linear",
    "lump_sum": "lump_sum", "ryczalt": "lump_sum", "ryczałt": "lump_sum",
    "tax_card": "tax_card", "karta": "tax_card", "karta podatkowa": "tax_card",
}

REQUIRED_COLUMNS = ["nip", "nazwa", "data_startu", "aktualny_kod"]

TEMPLATE_COLUMNS = [
    "nip", "nazwa", "data_startu", "aktualny_kod", "forma_opodatkowania",
    "byly_pracodawca", "zbieg_uop", "wynagrodzenie_uop", "status",
    "chce_chorobowe", "przychod_roczny",
]


def make_template_df() -> pd.DataFrame:
    """Tworzy pusty szablon z przykładowym wierszem."""
    example = {
        "nip": "5260250995",
        "nazwa": "Przykładowa Firma Sp. z o.o.",
        "data_startu": "2024-01-15",
        "aktualny_kod": "05 70",
        "forma_opodatkowania": "scale",
        "byly_pracodawca": "nie",
        "zbieg_uop": "nie",
        "wynagrodzenie_uop": 0,
        "status": "brak",
        "chce_chorobowe": "nie",
        "przychod_roczny": 80000,
    }
    return pd.DataFrame([example], columns=TEMPLATE_COLUMNS)


def _to_bool(val) -> bool:
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    return s in ("tak", "yes", "true", "1", "y", "t")


def _normalize_code(code: str) -> str:
    """Normalizuje kod do formatu 'XX XX' (np. '0570' → '05 70')."""
    digits = "".join(c for c in str(code) if c.isdigit())
    if len(digits) == 4:
        return f"{digits[:2]} {digits[2:]}"
    return str(code).strip()


def parse_import(file_bytes: bytes, filename: str) -> tuple[pd.DataFrame, list[str]]:
    """
    Wczytuje plik CSV lub Excel.
    Zwraca (DataFrame, lista_błędów_walidacji).
    """
    errors = []

    # Wczytaj w zależności od rozszerzenia
    try:
        if filename.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
        else:
            # CSV — spróbuj separatorów ; i ,
            text = file_bytes.decode("utf-8-sig")
            sep = ";" if text.count(";") > text.count(",") else ","
            df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str)
    except Exception as e:
        return pd.DataFrame(), [f"Nie można wczytać pliku: {e}"]

    # Normalizuj nazwy kolumn (lowercase, bez spacji)
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    # Sprawdź wymagane kolumny
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        errors.append(f"Brak wymaganych kolumn: {', '.join(missing)}")
        return df, errors

    # Usuń puste wiersze
    df = df.dropna(subset=["nip", "nazwa"], how="all").reset_index(drop=True)

    return df, errors


def verify_batch(df: pd.DataFrame, calc_date: date | None = None) -> pd.DataFrame:
    """
    Zbiorcza weryfikacja. Dla każdego wiersza liczy prawidłowy kod
    i porównuje z aktualnym. Dodaje kolumny wynikowe.
    """
    if calc_date is None:
        calc_date = date.today()

    results = []

    for _, row in df.iterrows():
        nip = "".join(c for c in str(row.get("nip", "")) if c.isdigit())
        nazwa = str(row.get("nazwa", "")).strip()
        aktualny_kod = _normalize_code(row.get("aktualny_kod", ""))

        record = {
            "nip": nip,
            "nazwa": nazwa,
            "aktualny_kod": aktualny_kod,
        }

        # Walidacja daty startu
        try:
            start = datetime.strptime(str(row.get("data_startu", "")).strip()[:10], "%Y-%m-%d").date()
        except Exception:
            record["prawidlowy_kod"] = "—"
            record["status"] = "BŁĄD DANYCH"
            record["uwagi"] = "Nieprawidłowa data startu (wymagany format RRRR-MM-DD)"
            record["_timeline"] = None
            results.append(record)
            continue

        # Walidacja NIP (ostrzeżenie, nie blokada)
        nip_ok = validate_nip(nip) if nip else False

        # Zbuduj input
        inp = WizardInput(
            start_date=start,
            calculation_date=calc_date,
            former_employer=_to_bool(row.get("byly_pracodawca", "nie")),
            employment_overlap=_to_bool(row.get("zbieg_uop", "nie")),
            employment_type="uop" if _to_bool(row.get("zbieg_uop", "nie")) else "none",
            employment_salary=float(row.get("wynagrodzenie_uop", 0) or 0),
            special_status=_STATUS_MAP.get(str(row.get("status", "brak")).strip().lower(), "none"),
            wants_chorobowe=_to_bool(row.get("chce_chorobowe", "nie")),
            taxation_form=_TAX_MAP.get(str(row.get("forma_opodatkowania", "scale")).strip().lower(), "scale"),
            estimated_annual_revenue=float(row.get("przychod_roczny", 0) or 0),
        )

        try:
            result = calculate(inp)
            timeline = generate_timeline(result, inp)
            prawidlowy = result["current_code"]

            record["prawidlowy_kod"] = prawidlowy
            record["_timeline"] = timeline
            record["_result"] = result

            # Porównanie
            if aktualny_kod == prawidlowy:
                record["status"] = "OK"
                record["uwagi"] = ""
            else:
                record["status"] = "BŁĄD KODU"
                record["uwagi"] = f"Stosowany {aktualny_kod}, powinien być {prawidlowy}"

            if not nip_ok and nip:
                record["uwagi"] = (record["uwagi"] + " | NIP: błędna suma kontrolna").strip(" |")

            # Data najbliższej zmiany kodu
            stage_end = result.get("stage_end")
            record["nastepna_zmiana"] = stage_end.strftime("%Y-%m-%d") if stage_end else "bezterminowo"

        except Exception as e:
            record["prawidlowy_kod"] = "—"
            record["status"] = "BŁĄD"
            record["uwagi"] = f"Błąd obliczeń: {e}"
            record["_timeline"] = None
            record["nastepna_zmiana"] = "—"

        results.append(record)

    return pd.DataFrame(results)


def build_report_df(verified: pd.DataFrame) -> pd.DataFrame:
    """Buduje czytelną tabelę raportu (bez kolumn technicznych _)."""
    cols = ["nip", "nazwa", "aktualny_kod", "prawidlowy_kod", "status", "nastepna_zmiana", "uwagi"]
    cols = [c for c in cols if c in verified.columns]
    report = verified[cols].copy()
    report.columns = ["NIP", "Nazwa", "Kod aktualny", "Kod prawidłowy",
                      "Status", "Następna zmiana", "Uwagi"][:len(cols)]
    return report


def get_summary(verified: pd.DataFrame) -> dict:
    """Podsumowanie weryfikacji."""
    total = len(verified)
    ok = len(verified[verified["status"] == "OK"])
    errors = len(verified[verified["status"] == "BŁĄD KODU"])
    data_errors = len(verified[verified["status"].isin(["BŁĄD DANYCH", "BŁĄD"])])
    return {
        "total": total,
        "ok": ok,
        "errors": errors,
        "data_errors": data_errors,
        "error_pct": round(errors / total * 100, 1) if total else 0,
    }


def export_excel(report_df: pd.DataFrame, summary: dict) -> bytes:
    """Eksportuje raport do pliku Excel (.xlsx)."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Arkusz podsumowania
        summary_df = pd.DataFrame([
            ["Klientów łącznie", summary["total"]],
            ["Kod prawidłowy (OK)", summary["ok"]],
            ["Błędny kod", summary["errors"]],
            ["Błędy danych", summary["data_errors"]],
            ["% z błędnym kodem", f"{summary['error_pct']}%"],
            ["Data weryfikacji", date.today().strftime("%Y-%m-%d")],
        ], columns=["Metryka", "Wartość"])
        summary_df.to_excel(writer, sheet_name="Podsumowanie", index=False)

        # Arkusz szczegółów
        report_df.to_excel(writer, sheet_name="Weryfikacja", index=False)

        # Auto-szerokość kolumn
        for sheet_name in writer.sheets:
            ws = writer.sheets[sheet_name]
            for col_cells in ws.columns:
                length = max(len(str(c.value or "")) for c in col_cells)
                ws.column_dimensions[col_cells[0].column_letter].width = min(length + 3, 50)

    output.seek(0)
    return output.read()


def build_batch_ics(verified: pd.DataFrame) -> str:
    """
    Buduje zbiorczy plik .ics z datami zmian kodów wszystkich klientów.
    Jedno wydarzenie = jedna zmiana kodu dla jednego klienta.
    """
    events = []
    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    for _, row in verified.iterrows():
        timeline = row.get("_timeline")
        if not isinstance(timeline, list) or not timeline:
            continue
        nazwa = row.get("nazwa", "")
        nip = row.get("nip", "")

        from datetime import timedelta
        for idx, stage in enumerate(timeline):
            d_to = stage["date_to"]
            if d_to is None:
                continue
            nxt = timeline[idx + 1] if idx + 1 < len(timeline) else None
            if nxt is None or nxt["code"] == stage["code"]:
                continue
            change_date = d_to + timedelta(days=1)
            events.append(_make_event(
                f"kodzus-{nip}-{change_date}",
                dtstamp, change_date,
                f"ZUS {nazwa}: {stage['code']} -> {nxt['code']}",
                f"Klient: {nazwa} (NIP {nip})\n"
                f"Zmiana kodu ZUS z {stage['code']} na {nxt['code']}\n"
                f"Sprawdz deklaracje DRA/RCA.",
            ))

    header = "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        "X-WR-CALNAME:KODZUS - zmiany kodow klientow",
        "X-WR-TIMEZONE:Europe/Warsaw",
    ])
    body = "\r\n".join(events) if events else ""
    return header + "\r\n" + body + "\r\nEND:VCALENDAR\r\n"
