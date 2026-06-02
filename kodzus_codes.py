"""
KODZUS — Baza wiedzy kodów ubezpieczenia ZUS dla przedsiębiorcy.

Domknięta do PEŁNEGO KATALOGU kodów które może przyjąć osoba prowadząca
działalność gospodarczą: rdzeń 05xx + struktura 5. i 6. znaku.

Źródła:
  - Lista_kodów_ZUS.xlsx (oficjalny katalog ZUS, rdzenie 05xx)
  - Kody_ubezpieczeń_ZUS.docx (struktura 6-znakowa, zasady)

STRUKTURA KODU (6 znaków): RRRR PN
  RRRR = rdzeń (podmiot podstawowy + rozszerzenie), np. 0510, 0570, 0590
  P    = 5. znak: prawo do emerytury/renty
         0 = brak prawa do emerytury/renty
         1 = ustalone prawo do emerytury
         2 = ustalone prawo do renty
  N    = 6. znak: stopień niepełnosprawności
         0 = brak orzeczenia
         1 = lekki stopień
         2 = umiarkowany stopień
         3 = znaczny stopień
         4 = orzeczenie wydane osobie do 16. r.ż.

Wyświetlany format: "05 70 00" (grupami po 2 znaki).
"""

from __future__ import annotations


# =============================================================================
# RDZENIE 05xx — pełny katalog z oficjalnej listy ZUS
# =============================================================================
# Pole 'role' określa rolę rdzenia w ścieżce kalkulatora (jeśli dotyczy).

CORE_CODES_05 = {
    "0510": {
        "name": "Działalność — zasady ogólne (Pełny ZUS)",
        "desc": "Osoba prowadząca pozarolniczą działalność gospodarczą niemająca "
                "ustalonego prawa do renty, dla której podstawę wymiaru składek stanowi "
                "zadeklarowana kwota nie niższa niż 60% przeciętnego wynagrodzenia. "
                "Także osoba prowadząca szkołę/placówkę oświatową oraz wolny zawód.",
        "stage": "full",
        "base_info": "Podstawa: min. 60% prognozowanego przeciętnego wynagrodzenia.",
    },
    "0511": {
        "name": "Osoba współpracująca (zdrowotne)",
        "desc": "Osoba współpracująca z osobą prowadzącą działalność oraz osobą fizyczną "
                "z art. 18 ust. 1 Prawa przedsiębiorców.",
        "stage": None,
        "base_info": "Składki jak dla osoby współpracującej.",
    },
    "0512": {
        "name": "Działalność — zasady ogólne, z prawem do renty",
        "desc": "Jak 0510, ale osoba MAJĄCA ustalone prawo do renty z tytułu "
                "niezdolności do pracy.",
        "stage": "full",
        "base_info": "Podstawa: min. 60% przeciętnego wynagrodzenia.",
    },
    "0513": {
        "name": "Niepełnosprawny przedsiębiorca (dofinansowanie PFRON — historyczny)",
        "desc": "Osoba niepełnosprawna, która po raz pierwszy podjęła działalność i "
                "skorzystała z dofinansowania składek z PFRON (przepisy do 2008 r.).",
        "stage": None,
        "base_info": "Przypadek historyczny — korekty za okres do 2007 r.",
    },
    "0514": {
        "name": "Działalność zwolniona ze składek (podstawa 60%)",
        "desc": "Osoba prowadząca działalność zwolniona z opłacania składek, dla której "
                "podstawę stanowi 60% prognozowanego przeciętnego wynagrodzenia.",
        "stage": None,
        "base_info": "Zwolnienie ze składek — przypadek szczególny.",
    },
    "0520": {
        "name": "Twórca",
        "desc": "Osoba prowadząca działalność twórczą.",
        "stage": None,
        "base_info": "Składki jak dla działalności.",
    },
    "0530": {
        "name": "Artysta",
        "desc": "Osoba prowadząca działalność artystyczną.",
        "stage": None,
        "base_info": "Składki jak dla działalności.",
    },
    "0540": {
        "name": "Ulga na Start",
        "desc": "Osoba korzystająca z Ulgi na Start — niepodlegająca ubezpieczeniom "
                "społecznym, podlegająca tylko zdrowotnemu, zgodnie z art. 18 ust. 1 "
                "Prawa przedsiębiorców. Przez 6 pełnych miesięcy.",
        "stage": "ulga",
        "base_info": "Brak składek społecznych. Tylko składka zdrowotna.",
    },
    "0543": {
        "name": "Wspólnik spółki / akcjonariusz PSA",
        "desc": "Wspólnik jednoosobowej sp. z o.o., wspólnicy spółki jawnej, "
                "komandytowej lub partnerskiej, komplementariusz w SKA, akcjonariusz "
                "prostej spółki akcyjnej wnoszący wkład w postaci pracy/usług.",
        "stage": None,
        "base_info": "Składki jak dla działalności (zasady ogólne).",
    },
    "0544": {
        "name": "Działalność — niepodlegająca zdrowotnemu (przepisy szczególne)",
        "desc": "Osoba prowadząca działalność, z mocy przepisów szczególnych "
                "niepodlegająca ubezpieczeniu zdrowotnemu.",
        "stage": None,
        "base_info": "Bez składki zdrowotnej (przepisy szczególne).",
    },
    "0545": {
        "name": "Osoba współpracująca — niepodlegająca zdrowotnemu",
        "desc": "Osoba współpracująca, z mocy przepisów szczególnych niepodlegająca "
                "ubezpieczeniu zdrowotnemu. Stosowany też gdy osoba współpracująca ma "
                "ustalone prawo do emerytury.",
        "stage": None,
        "base_info": "Bez składki zdrowotnej (przepisy szczególne).",
    },
    "0570": {
        "name": "Preferencyjny ZUS (mały ZUS)",
        "desc": "Osoba prowadząca działalność niemająca ustalonego prawa do renty, dla "
                "której podstawę stanowi zadeklarowana kwota nie niższa niż 30% "
                "minimalnego wynagrodzenia. Przez 24 miesiące po Uldze na Start.",
        "stage": "preferential",
        "base_info": "Podstawa: min. 30% minimalnego wynagrodzenia.",
    },
    "0572": {
        "name": "Preferencyjny ZUS, z prawem do renty",
        "desc": "Jak 0570, ale osoba MAJĄCA ustalone prawo do renty z tytułu "
                "niezdolności do pracy.",
        "stage": "preferential",
        "base_info": "Podstawa: min. 30% minimalnego wynagrodzenia.",
    },
    "0574": {
        "name": "Preferencyjny — zwolniony ze składek (podstawa 30%)",
        "desc": "Osoba prowadząca działalność zwolniona z opłacania składek, dla której "
                "podstawę stanowi 30% minimalnego wynagrodzenia.",
        "stage": None,
        "base_info": "Zwolnienie ze składek — przypadek szczególny.",
    },
    "0580": {
        "name": "Działalność — zasiłek macierzyński ≤ świadczenie rodzicielskie",
        "desc": "Osoba prowadząca działalność, której zasiłek macierzyński nie "
                "przekracza kwoty świadczenia rodzicielskiego.",
        "stage": None,
        "base_info": "Przypadek szczególny — okres macierzyński.",
    },
    "0581": {
        "name": "Osoba współpracująca — zasiłek macierzyński ≤ świadczenie rodzicielskie",
        "desc": "Osoba współpracująca, której zasiłek macierzyński nie przekracza kwoty "
                "świadczenia rodzicielskiego.",
        "stage": None,
        "base_info": "Przypadek szczególny — okres macierzyński.",
    },
    "0590": {
        "name": "Mały ZUS Plus",
        "desc": "Osoba prowadząca działalność niemająca ustalonego prawa do renty, dla "
                "której podstawa składek uzależniona jest od dochodu. Do 36 miesięcy w "
                "ciągu ostatnich 60 miesięcy. Limit przychodu: 120 000 zł.",
        "stage": "mzp",
        "base_info": "Podstawa zależna od dochodu z poprzedniego roku.",
    },
    "0592": {
        "name": "Mały ZUS Plus, z prawem do renty",
        "desc": "Jak 0590, ale osoba MAJĄCA ustalone prawo do renty z tytułu "
                "niezdolności do pracy.",
        "stage": "mzp",
        "base_info": "Podstawa zależna od dochodu.",
    },
    "0594": {
        "name": "Mały ZUS Plus — zwolniony ze składek",
        "desc": "Osoba prowadząca działalność zwolniona z opłacania składek, dla której "
                "podstawa uzależniona jest od dochodu.",
        "stage": None,
        "base_info": "Zwolnienie ze składek — przypadek szczególny.",
    },
}


# =============================================================================
# 5. ZNAK — prawo do emerytury/renty
# =============================================================================

FIFTH_CHAR = {
    "0": "brak ustalonego prawa do emerytury lub renty",
    "1": "ustalone prawo do emerytury",
    "2": "ustalone prawo do renty",
}

# =============================================================================
# 6. ZNAK — stopień niepełnosprawności
# =============================================================================

SIXTH_CHAR = {
    "0": "brak orzeczenia o niepełnosprawności",
    "1": "lekki stopień niepełnosprawności",
    "2": "umiarkowany stopień niepełnosprawności",
    "3": "znaczny stopień niepełnosprawności",
    "4": "orzeczenie o niepełnosprawności (osoba do 16. r.ż.)",
}


# =============================================================================
# FUNKCJE POMOCNICZE
# =============================================================================

def format_code(core: str, fifth: str = "0", sixth: str = "0") -> str:
    """Formatuje pełny 6-znakowy kod do postaci 'RR RR PN'."""
    full = f"{core}{fifth}{sixth}"
    return f"{full[0:2]} {full[2:4]} {full[4:6]}"


def describe_code(core: str, fifth: str = "0", sixth: str = "0") -> dict:
    """
    Pełny opis kodu: rdzeń + interpretacja 5. i 6. znaku.
    """
    core_info = CORE_CODES_05.get(core)
    if not core_info:
        return {
            "code": format_code(core, fifth, sixth),
            "name": "Nieznany kod",
            "desc": "Kod spoza katalogu działalności gospodarczej (05xx).",
            "fifth_meaning": FIFTH_CHAR.get(fifth, "—"),
            "sixth_meaning": SIXTH_CHAR.get(sixth, "—"),
        }
    return {
        "code": format_code(core, fifth, sixth),
        "core": core,
        "name": core_info["name"],
        "desc": core_info["desc"],
        "base_info": core_info.get("base_info", ""),
        "stage": core_info.get("stage"),
        "fifth_meaning": FIFTH_CHAR.get(fifth, "—"),
        "sixth_meaning": SIXTH_CHAR.get(sixth, "—"),
    }


def adjust_code_for_person(base_core: str, special_status: str = "none",
                           disability: str = "0") -> str:
    """
    Domyka kod do pełnej postaci 6-znakowej na podstawie statusu osoby.

    base_core      — rdzeń wyliczony przez kalkulator (np. '0570')
    special_status — 'none' | 'retiree' | 'disability_pensioner'
    disability     — '0'..'4' (6. znak)

    Zwraca pełny 6-znakowy kod w formacie 'RR RR PN'.

    UWAGA: dla rencisty rdzeń często zmienia się sam (0570→0572),
    bo ZUS ma osobne rdzenie dla "z prawem do renty". 5. znak wtedy = 0.
    Dla emeryta rdzeń zostaje, ale 5. znak = 1.
    """
    fifth = "0"
    if special_status == "retiree":
        fifth = "1"  # emeryt — 5. znak = 1
    elif special_status == "disability_pensioner":
        # Rencista — rdzeń ma osobny wariant (np. 0572), 5. znak zostaje 0
        # Jeśli rdzeń nie ma wariantu rentowego, ustaw 5. znak = 2
        fifth = "0"

    sixth = disability if disability in SIXTH_CHAR else "0"
    return format_code(base_core, fifth, sixth)


def get_entrepreneur_catalog() -> list[dict]:
    """Zwraca pełny katalog rdzeni 05xx jako listę (do przeglądarki/tabeli)."""
    catalog = []
    for core, info in CORE_CODES_05.items():
        catalog.append({
            "Kod": format_code(core),
            "Rdzeń": core,
            "Nazwa": info["name"],
            "Opis": info["desc"],
            "Etap": info.get("stage") or "—",
        })
    return catalog
