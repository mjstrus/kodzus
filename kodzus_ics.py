"""
KODZUS — Generator pliku .ics (iCalendar) w Pythonie.
Zgodny z RFC 5545. Wydarzenia graniczne + opcjonalne cykliczne przypomnienia.
"""

from __future__ import annotations
from datetime import datetime, date
import re


PRODID = "-//KODZUS//Kalkulator ZUS 1.0//PL"


def _escape(text: str) -> str:
    """Escapuje tekst zgodnie z RFC 5545."""
    text = text.replace("\\", "\\\\")
    text = text.replace(";", "\\;")
    text = text.replace(",", "\\,")
    text = text.replace("\r\n", "\\n").replace("\n", "\\n")
    return text


def _sanitize_uid(value: str) -> str:
    return re.sub(r"[^\w\-.@]", "", value)


def _fold(line: str) -> str:
    """Składa linie > 75 oktetów zgodnie z RFC 5545."""
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line
    result = ""
    current = line
    while len(current.encode("utf-8")) > 75:
        # Tnij po znakach żeby nie rozbić UTF-8
        chunk = current
        while len(chunk.encode("utf-8")) > 75:
            chunk = chunk[:-1]
        result += chunk + "\r\n "
        current = current[len(chunk):]
    result += current
    return result


def _make_event(uid: str, dtstamp: str, dtstart: date,
                summary: str, description: str, rrule: str | None = None) -> str:
    date_str = dtstart.strftime("%Y%m%d")
    lines = [
        "BEGIN:VEVENT",
        f"UID:{_sanitize_uid(uid + '@kodzus.pl')}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART;VALUE=DATE:{date_str}",
    ]
    if rrule:
        lines.append(f"RRULE:{rrule}")
    lines += [
        f"SUMMARY:{_escape(summary)}",
        f"DESCRIPTION:{_escape(description)}",
        "TRANSP:TRANSPARENT",
        "END:VEVENT",
    ]
    return "\r\n".join(_fold(l) for l in lines)


def generate_ics(timeline: list[dict], cyclic: bool = False) -> str:
    """
    Generuje zawartość pliku .ics.

    timeline — lista etapów z generate_timeline()
    cyclic   — czy dodać cykliczne przypomnienia miesięczne o zapłacie składek
    """
    events = []
    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    prev = None
    for idx, row in enumerate(timeline):
        stage_name = row["stage_name"]
        code = row["code"]
        d_from = row["date_from"]
        d_to = row["date_to"]

        # Wydarzenie startowe (pierwszy etap)
        if prev is None:
            events.append(_make_event(
                f"kodzus-start-{d_from}",
                dtstamp, d_from,
                f"Poczatek ubezpieczenia ZUS: {stage_name} ({code})",
                f"Kod tytulu ubezpieczenia: {code}\nEtap: {stage_name}\n\nWygenerowano przez KODZUS.",
            ))

        # Wydarzenie zmiany kodu
        if d_to is not None:
            from datetime import timedelta
            change_date = d_to + timedelta(days=1)
            nxt = timeline[idx + 1] if idx + 1 < len(timeline) else None
            next_code = nxt["code"] if nxt else "05 10"
            next_name = nxt["stage_name"] if nxt else "Pelny ZUS"

            # Tylko jeśli faktycznie zmienia się kod (nie segment tego samego etapu)
            if next_code != code:
                events.append(_make_event(
                    f"kodzus-change-{change_date}",
                    dtstamp, change_date,
                    f"Zmiana kodu ZUS: {code} -> {next_code}",
                    f"ZMIANA KODU TYTULU UBEZPIECZENIA ZUS\n\n"
                    f"Od dzisiaj: {next_name} ({next_code})\nBylo: {stage_name} ({code})\n\n"
                    f"Sprawdz czy deklaracje ZUS DRA/RCA sa zaktualizowane!\n\n"
                    f"Wygenerowano przez KODZUS.",
                ))

                # Przypomnienie 30 dni przed
                reminder = d_to - timedelta(days=30)
                events.append(_make_event(
                    f"kodzus-reminder-{change_date}",
                    dtstamp, reminder,
                    f"Za 30 dni zmiana kodu ZUS ({code} -> {next_code})",
                    f"Za 30 dni nastapi zmiana kodu ZUS.\n\n"
                    f"Aktualna: {stage_name} ({code})\nNastepna: {next_name} ({next_code})\n\n"
                    f"Zmiana: {d_to}\n\nSkontaktuj sie z biurem rachunkowym jesli potrzebujesz pomocy.",
                ))

        prev = stage_name

    # Terminy administracyjne — co rok
    if timeline:
        first_year = timeline[0]["date_from"].year
        last = timeline[-1]["date_to"]
        last_year = last.year if last else first_year + 5
        for y in range(first_year, min(last_year, first_year + 5) + 1):
            events.append(_make_event(
                f"kodzus-mzp-{y}", dtstamp, date(y, 1, 20),
                f"Sprawdz kwalifikacje do Malego ZUS Plus ({y})",
                f"Termin zlozenia oswiadczenia o Malym ZUS Plus: do 31 stycznia {y}.\n"
                f"Warunki: przychod z poprzedniego roku <= 120 000 PLN, dzialalnosc >= 60 dni.",
            ))
            events.append(_make_event(
                f"kodzus-health-{y}", dtstamp, date(y, 5, 10),
                f"Roczne rozliczenie skladki zdrowotnej za {y-1}",
                f"Termin: dokumenty ZUS DRA za kwiecien {y} = do 20 maja {y}.\n"
                f"Rozliczenie rocznej skladki zdrowotnej za {y-1}.",
            ))

    # Cykliczne przypomnienia miesięczne
    if cyclic and timeline:
        start = timeline[0]["date_from"]
        events.append(_make_event(
            "kodzus-monthly-payment", dtstamp,
            date(start.year, start.month, 15),
            "Oplac skladki ZUS do 20. dnia miesiaca",
            "Termin zaplaty skladek ZUS: 20. dzien miesiaca.\n\n"
            "Oplac przez portal PUE ZUS lub przelew na indywidualny numer rachunku.\n\n"
            "Wygenerowano przez KODZUS.",
            rrule="FREQ=MONTHLY;BYMONTHDAY=15",
        ))

    # Złóż plik
    header = "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Harmonogram ZUS - KODZUS",
        "X-WR-TIMEZONE:Europe/Warsaw",
    ])
    body = "\r\n".join(events)
    return header + "\r\n" + body + "\r\nEND:VCALENDAR\r\n"
