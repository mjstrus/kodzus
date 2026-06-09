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

## Zwolnienia ze składki zdrowotnej (v9)

Dodano dwa zwolnienia ze składki ZDROWOTNEJ (kod się nie zmienia, zmienia się kwota):

1. **Emeryt o niskim świadczeniu** — zwolniony ze zdrowotnej z działalności, jeśli ŁĄCZNIE:
   emerytura brutto ≤ płaca minimalna (4 806 zł 2026) ORAZ
   przychód z działalności ≤ 50% najniższej emerytury (LUB karta podatkowa).
   Najniższa emerytura: 1 878,91 zł (do 29.02.2026), 1 978,49 zł (od 1.03.2026 — waloryzacja 5,3%).

2. **Pracownik o niskiej podstawie** — zwolniony ze zdrowotnej z działalności, jeśli ŁĄCZNIE:
   podstawa z etatu ≤ płaca minimalna ORAZ przychód z działalności ≤ 50% min. wynagrodzenia ORAZ ryczałt.

Zasada projektowa: kalkulator pilnuje wysokości KAŻDEJ składki, nie tylko kodu.
Każda reguła zmieniająca kwotę (nawet gdy kod zostaje) jest tak samo istotna.

### Walidacja
Dokument "Zbieg tytułów do ubezpieczeń" potwierdził: ścieżkę ulg, zwolnienie społeczne przy etacie,
emeryta/rencistę, kwoty zdrowotnej 2026. Ujawnił dwa powyższe zwolnienia ze zdrowotnej.
Poprzednie poradniki (umowy cywilnoprawne) — walidacja bez zmian, zlecenie/dzieło poza zakresem (JDG).

## Raport PDF (v10)

Na ekranie wyniku — przycisk "Wygeneruj raport PDF". Profesjonalny raport A4 zawiera:
- Nagłówek z brandingiem biura (gradient, nazwa, kontakt, "przygotowano dla")
- Aktualny kod 6-znakowy + objaśnienie znaków
- CTA przy błędnym kodzie (link do konsultacji / e-mail)
- Wykresy SVG: składki w czasie (słupkowy) + podział społeczne/zdrowotna (donut)
- Pełny harmonogram składek 5 lat z oznaczeniem prognoz
- Scenariusze (obecny / z chorobowym / docelowy Pełny ZUS) z różnicami kwot
- Wskazówki, ostrzeżenia, ważne terminy administracyjne
- Stopka z zastrzeżeniem prawnym i danymi biura

### Branding
Panel boczny → "🏢 Branding raportu PDF" — nazwa biura, kontakt, link do konsultacji,
imię klienta. Wszystko opcjonalne.

### Technologia
Raport: HTML → Chromium (playwright) → PDF. Wykresy jako inline SVG (bez JS).
Wymaga: playwright (requirements.txt) + biblioteki systemowe (packages.txt).
Na Streamlit Cloud chromium instaluje się automatycznie przy pierwszym raporcie.
Lokalnie: `playwright install chromium`.

## Tryb planowania działalności (v12)

Panel boczny (tryb przedsiębiorcy) → przełącznik "Mam już firmę" / "Planuję założyć działalność".

Ten sam silnik i te same pytania, inny język i framing:
- **Nagłówek**: "Kalkulator składek ZUS" zamiast "Kalkulator Kodów ZUS"
- **Krok 1**: "Kiedy planujesz rozpocząć?" + data tylko w przyszłości, bez pola NIP/GUS (nie ma jeszcze firmy)
- **Wynik**: "Kod na start" zamiast "aktualny kod", brak ostrzeżenia o błędnym kodzie
  (nie ma czego sprawdzać), zamiast tego zachęta "Zakładasz firmę? Zrób to dobrze od początku"
- **Raport PDF**: tytuł "plan składek na start", niebieski CTA do konsultacji przy zakładaniu

Cel: szerszy punkt wejścia — osoby planujące działalność szukają "ile ZUS na starcie",
co jest czystszym leadem niż osoby z już istniejącą firmą.

## Scenariusze strategii składkowych (v13)

Zamiast jednej ścieżki — 5 strategii, każda optymalizuje co innego:
- **Najniższe koszty** — maks. ulgi, minimum składek, bez chorobowego
- **Najwięcej na emeryturę** — rezygnacja z ulg, pełna podstawa
- **Bezpieczeństwo socjalne** — najwcześniejsze chorobowe (rezygnacja z ulgi)
- **Zrównoważony** — ulgi na starcie + chorobowe
- **Optymalny dla Ciebie** — dopasowany do priorytetu wskazanego w wizardzie

W kroku Preferencje użytkownik wskazuje priorytet (koszt / emerytura / ochrona / zrównoważony),
co steruje rekomendacją "optymalny".

Każdy scenariusz porównany w 3 wymiarach (jednolite okno 60 miesięcy):
- łączny koszt składek (5 lat)
- część emerytalna (szacunek 19,52% podstawy)
- poziom ochrony socjalnej (chorobowe/zasiłki)

Prezentacja: karty z rekomendacją "dla kogo" + tabela porównawcza.
W wyniku (Streamlit) i w raporcie PDF. Silnik: kodzus_scenarios.py.

## Wakacje składkowe (v14)

W kroku Preferencje: checkbox "Sprawdź czy kwalifikuję się do wakacji składkowych"
+ pytania o liczbę ubezpieczonych (≤10) i przychód < 2 mln euro.

Wakacje składkowe = zwolnienie ze składek SPOŁECZNYCH za 1 wybrany miesiąc w roku
(finansowane z budżetu). Zdrowotną nadal płacisz.

Warunki sprawdzane: nie na rzecz byłego/obecnego pracodawcy, ≤10 ubezpieczonych,
przychód < 2 mln euro, nie działalność nierejestrowana.

Wynik (Streamlit + raport PDF): kwalifikacja TAK/NIE z powodami, oszczędność miesięczna
na obecnym etapie, oraz WSKAZÓWKA STRATEGICZNA: o wakacje najlepiej wnioskować na miesiąc
przed miesiącem spodziewanego wysokiego przychodu (obniżają składki społeczne).
Wniosek RWS w eZUS w miesiącu poprzedzającym.

## Warstwa doradcza (v16)

Raport i wynik DORADZAJĄ, nie tylko liczą. Moduł kodzus_advice.py generuje:
- **Headline** — jedno zdanie rekomendacji wg priorytetu użytkownika
- **Uzasadnienie** — liczby (koszt/emerytura/podatek 5 lat) + kontekst vs najtańszy wariant
- **Plan krok po kroku** — z realnymi datami przejść między etapami (ulga→pref→MZP→pełny)
- **Pułapki** — dopasowane do sytuacji: start w trakcie miesiąca (algorytm pełnego miesiąca),
  forma opodatkowania a odliczenie zdrowotnej, limity MZP

Sekcja "Nasza rekomendacja" na górze raportu PDF (po kodzie) i w wyniku Streamlit.

### Pytania Ulga/chorobowe usunięte z wizarda (v15)
To były decyzje, których przedsiębiorca nie umie podjąć — teraz są osiami wariantów.
Kalkulator liczy wszystkie kombinacje i pokazuje obok siebie w 3 horyzontach (1/3/5 lat).
Stary prosty silnik scenariuszy (compute_scenarios) całkowicie usunięty.
