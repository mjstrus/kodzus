"""
KODZUS — Integracja z GUS REGON API (Python).

Pobiera dane firmy po NIP: nazwa, REGON, miejscowość, data rejestracji.
Wymaga klucza API z https://api.stat.gov.pl/Home/RegonApi (bezpłatny).

Graceful degradation: brak klucza = funkcja zwraca None, wizard działa normalnie.
"""

from __future__ import annotations
import re
import requests
from xml.etree import ElementTree as ET


API_URL = "https://wyszukiwarkaregon.stat.gov.pl/wsBIR/UslugaBIRzewnPubl.svc"
TIMEOUT = 12


def validate_nip(nip: str) -> bool:
    """Walidacja NIP przez sumę kontrolną."""
    nip = re.sub(r"[^0-9]", "", nip)
    if len(nip) != 10:
        return False
    weights = [6, 5, 7, 2, 3, 4, 5, 6, 7]
    checksum = sum(int(nip[i]) * weights[i] for i in range(9)) % 11
    return checksum == int(nip[9])


def _soap_request(action: str, body: str, session_id: str | None = None) -> str:
    """Wysyła żądanie SOAP do GUS API."""
    headers = {
        "Content-Type": f'application/soap+xml;charset=UTF-8;action="{action}"',
    }
    if session_id:
        headers["sid"] = session_id

    resp = requests.post(API_URL, data=body.encode("utf-8"),
                         headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.text


def _login(api_key: str) -> str | None:
    """Logowanie do GUS — zwraca session ID."""
    body = f"""<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:ns="http://CIS/BIR/PUBL/2014/07">
<soap:Header xmlns:wsa="http://www.w3.org/2005/08/addressing">
<wsa:To>{API_URL}</wsa:To>
<wsa:Action>http://CIS/BIR/PUBL/2014/07/IUslugaBIRzewnPubl/Zaloguj</wsa:Action>
</soap:Header>
<soap:Body><ns:Zaloguj><ns:pKluczUzytkownika>{api_key}</ns:pKluczUzytkownika></ns:Zaloguj></soap:Body>
</soap:Envelope>"""

    try:
        raw = _soap_request(
            "http://CIS/BIR/PUBL/2014/07/IUslugaBIRzewnPubl/Zaloguj", body)
        # Wyciągnij session id z odpowiedzi
        match = re.search(r"<ZalogujResult>(.*?)</ZalogujResult>", raw)
        return match.group(1) if match else None
    except Exception:
        return None


def _search_nip(nip: str, session_id: str) -> dict | None:
    """Wyszukuje podmiot po NIP."""
    body = f"""<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:ns="http://CIS/BIR/PUBL/2014/07" xmlns:dat="http://CIS/BIR/PUBL/2014/07/DataContract">
<soap:Header xmlns:wsa="http://www.w3.org/2005/08/addressing">
<wsa:To>{API_URL}</wsa:To>
<wsa:Action>http://CIS/BIR/PUBL/2014/07/IUslugaBIRzewnPubl/DaneSzukajPodmioty</wsa:Action>
</soap:Header>
<soap:Body><ns:DaneSzukajPodmioty><ns:pParametryWyszukiwania>
<dat:Nip>{nip}</dat:Nip>
</ns:pParametryWyszukiwania></ns:DaneSzukajPodmioty></soap:Body>
</soap:Envelope>"""

    try:
        raw = _soap_request(
            "http://CIS/BIR/PUBL/2014/07/IUslugaBIRzewnPubl/DaneSzukajPodmioty",
            body, session_id)
        # Odpowiedź zawiera zagnieżdżony XML w CDATA
        match = re.search(r"<DaneSzukajPodmiotyResult>(.*?)</DaneSzukajPodmiotyResult>",
                          raw, re.DOTALL)
        if not match or not match.group(1).strip():
            return None

        inner = match.group(1)
        # Rozkoduj encje HTML
        inner = inner.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

        root = ET.fromstring(inner)
        dane = root.find("dane")
        if dane is None:
            return None

        def get(tag):
            el = dane.find(tag)
            return el.text if el is not None and el.text else ""

        return {
            "name": get("Nazwa"),
            "regon": get("Regon"),
            "city": get("Miejscowosc"),
            "nip": nip,
        }
    except Exception:
        return None


def lookup_nip(nip: str, api_key: str) -> dict | None:
    """
    Główna funkcja: NIP → dane firmy.
    Zwraca dict lub None (przy braku klucza, błędzie sieciowym, braku firmy).
    """
    nip = re.sub(r"[^0-9]", "", nip)

    if not validate_nip(nip):
        return {"error": "Nieprawidłowy NIP (błędna suma kontrolna)."}

    if not api_key:
        return {"error": "Brak klucza API GUS — autouzupełnianie wyłączone."}

    session_id = _login(api_key)
    if not session_id:
        return {"error": "Nie można połączyć z GUS. Sprawdź klucz API."}

    data = _search_nip(nip, session_id)
    if not data:
        return {"error": "Nie znaleziono firmy o tym NIP w GUS."}

    return data
