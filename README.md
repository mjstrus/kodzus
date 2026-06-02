# KODZUS — Kalkulator Kodów ZUS (Streamlit)

Webowy kalkulator ZUS. Wizard krok po kroku, eksport kalendarza, tryb biura.

## Pliki

```
kodzus-streamlit/
├── app.py                          ← aplikacja Streamlit (UI)
├── kodzus_core.py                  ← logika ZUS (kalkulacja, harmonogram)
├── kodzus_ics.py                   ← generator pliku .ics (kalendarz)
├── kodzus_gus.py                   ← autouzupełnianie NIP z GUS API
├── requirements.txt                ← zależności
├── .streamlit/secrets.toml.example ← szablon konfiguracji klucza GUS
└── README.md
```

## Uruchomienie lokalne

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Hosting za darmo — Streamlit Community Cloud

1. Konto na https://share.streamlit.io (logowanie przez GitHub)
2. Wrzuć pliki do repozytorium GitHub
3. "New app" → wskaż repo i app.py → Deploy
4. Publiczny adres typu https://kodzus.streamlit.app

## Funkcje

### Wizard (7 kroków + wynik)
Algorytm Pełnego Miesiąca, wszystkie ścieżki ZUS, wykluczenia, składka zdrowotna
(4 formy opodatkowania), harmonogram 5-letni, wykrywanie błędnego kodu.

### Eksport .ics (kalendarz)
Na ekranie wyniku — przycisk "Pobierz kalendarz". Plik zawiera:
- Wydarzenia zmiany kodu ZUS (każda granica etapu)
- Przypomnienia 30 dni przed zmianą
- Coroczne terminy: oświadczenie MZP (styczeń), rozliczenie zdrowotnej (maj)
- Opcjonalnie: cykliczne przypomnienia miesięczne o zapłacie składek

Otwiera się w Google Calendar, Apple Calendar, Outlook.

### Autouzupełnianie NIP z GUS
Na pierwszym kroku — wpisz NIP, kliknij "Pobierz dane z GUS".
WYMAGA klucza API (bezpłatny z https://api.stat.gov.pl/Home/RegonApi).
Bez klucza — wizard działa normalnie, tylko bez autouzupełniania.

KONFIGURACJA KLUCZA:
- Lokalnie: skopiuj .streamlit/secrets.toml.example → .streamlit/secrets.toml, wstaw klucz
- Cloud: Settings → Secrets → wklej: gus_api_key = "TWOJ_KLUCZ"

### Tryb biura rachunkowego
Panel boczny (lewy) → przełącznik "Przedsiębiorca / Biuro rachunkowe".
W trybie biura: brak gate kontaktowego, alert błędnego kodu kierowany do księgowej
("Klient powinien być na kodzie X").

## Czego jeszcze nie ma

- Zapis leadów do bazy (Streamlit nie ma wbudowanej bazy — podepnij Google Sheets / Supabase)
- Wysyłka emaila z wynikiem
- Formularz kontaktowy / gate
- Płatności (paywall)

## Aktualizacja kwot ZUS

Kwoty w kodzus_core.py w słownikach RATES_2026 i RATES_2027_FORECAST.
Gdy ZUS ogłosi nowe oficjalne kwoty — zaktualizuj te słowniki.

## Import zbiorczy (tryb biura rachunkowego)

Panel boczny → "Biuro rachunkowe" → "Import zbiorczy".

1. **Pobierz szablon CSV** (rozwiń "Jak przygotować plik")
2. Wypełnij danymi klientów. Wymagane kolumny: `nip, nazwa, data_startu, aktualny_kod`
3. **Wgraj plik** (CSV lub Excel)
4. **Zweryfikuj wszystkich** — kalkulator liczy prawidłowy kod dla każdego i porównuje z aktualnym
5. Zobacz podsumowanie (ilu klientów ma błędny kod) + tabelę z podświetleniem błędów
6. **Eksport:**
   - Raport końcowy do Excel (podsumowanie + szczegóły)
   - Kalendarz .ics ze zmianami kodów wszystkich klientów

Kolumny opcjonalne (domyślnie brak wykluczeń, skala podatkowa):
forma_opodatkowania, byly_pracodawca, zbieg_uop, wynagrodzenie_uop, status, chce_chorobowe, przychod_roczny

Docelowo: eksport do Frappe zamiast Excela (struktura kolumn już pod to przygotowana).

## Katalog kodów + baza wiedzy (od v4)

### Przeglądarka katalogu kodów
Panel boczny → checkbox "📖 Przeglądarka katalogu kodów".
Pełny katalog kodów działalności gospodarczej (rdzeń 05xx) z wyszukiwarką.
Plus objaśnienie struktury 5. znaku (emerytura/renta) i 6. znaku (niepełnosprawność).

### Pełny kod 6-znakowy w wyniku
Wynik pokazuje teraz pełny 6-znakowy kod (RR RR PN):
- rdzeń wyliczony przez kalkulator (np. 05 70)
- 5. znak: automatycznie z statusu (emeryt → 1)
- 6. znak: ze stopnia niepełnosprawności podanego w kroku "Status"

Rozwijane "Co oznacza ten kod?" objaśnia każdy znak.

### Źródła danych
- kodzus_codes.py — katalog 19 rdzeni 05xx + struktura znaków
  (z oficjalnej listy ZUS i rozporządzenia MRiPS z 27.06.2025)

## Poprawki logiki — zbieg z etatem (v5)

Na podstawie zasad ZUS dla przedsiębiorcy na etacie:

1. **Zbieg z UoP ≥ płaca minimalna NIE zmienia kodu.** Przedsiębiorca przechodzi
   normalną ścieżkę ulg (05 40 → 05 70 → 05 90 → 05 10). Zmienia się tylko zakres:
   składki społeczne = 0 zł (zwolnione), płatna tylko zdrowotna.
   Wcześniej kalkulator błędnie wymuszał 05 10 — odbierając należne ulgi.

2. **"Były pracodawca" obejmuje też OBECNEGO pracodawcę** (interpretacja ZUS
   z 19.04.2018). Jeśli w działalności świadczysz usługi dla obecnego/byłego
   pracodawcy w pokrywającym się zakresie → brak ulg, kod 05 10.

3. **Dobrowolne chorobowe zablokowane przy etacie ≥ min.** Gdy składki społeczne
   z działalności są dobrowolne (przez etat), nie można zgłosić chorobowego z działalności.

Świadome uproszczenia (poza zakresem MVP): przesunięcie wypłaty na przełomie roku,
urlop bezpłatny, zwolnienie lekarskie wpływające na pojedynczy miesiąc.

## Działalność nierejestrowana (v6)

Na ostatnim kroku wizarda (Preferencje) — checkbox "Sprawdź czy kwalifikuję się
do działalności nierejestrowanej". Sprawdzane PRZED ścieżką JDG.

Warunki kwalifikacji (art. 5 ust. 1 Prawa przedsiębiorców):
- przychód miesięczny < 75% min. wynagrodzenia (3 604,50 zł w 2026)
- brak działalności gospodarczej w ostatnich 60 miesiącach

Jeśli kwalifikuje → wynik: brak rejestracji CEIDG, brak składek ZUS, tylko podatek.
Jeśli przekracza próg → przechodzi do normalnej ścieżki JDG z ostrzeżeniem.

### Walidacja logiki na podstawie dokumentów źródłowych
Dokumenty "umowa zlecenie/dzieło" i "optymalizacja składek" potwierdziły poprawność
ścieżki ulg i zwolnienia przy zbiegu z etatem. Świadomie NIE objęto zakresem (poza JDG):
umowa zlecenie (kod 04 11), umowa o dzieło (brak ZUS), sp. z o.o. wieloosobowa,
praca za granicą — to alternatywy dla JDG, nie warianty ścieżki przedsiębiorcy.
