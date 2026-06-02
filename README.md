# KODZUS — Kalkulator Kodów ZUS (Streamlit)

Prototyp webowy kalkulatora ZUS. Wizard krok po kroku.

## Pliki

```
kodzus-streamlit/
├── app.py              ← aplikacja Streamlit (UI wizarda)
├── kodzus_core.py      ← logika ZUS (kalkulacja, harmonogram, wykrywanie błędów)
├── requirements.txt    ← zależności
└── README.md
```

## Uruchomienie lokalne

```bash
pip install -r requirements.txt
streamlit run app.py
```

Otworzy się w przeglądarce pod http://localhost:8501

## Hosting za darmo — Streamlit Community Cloud

1. Załóż konto na https://share.streamlit.io (logujesz się przez GitHub)
2. Wrzuć te pliki do publicznego (lub prywatnego) repozytorium GitHub
3. Na share.streamlit.io kliknij "New app", wskaż repozytorium i plik `app.py`
4. Deploy — w 2 minuty masz publiczny adres typu `https://kodzus.streamlit.app`

## Co działa

- Wizard: 7 pytań krok po kroku + wynik
- Algorytm Pełnego Miesiąca (Wariant A — zgodny z ustawą)
- Wszystkie ścieżki: Ulga → Preferencyjny → Mały ZUS Plus → Pełny ZUS
- Wykluczenia: były pracodawca, emeryt/rencista, zbieg tytułów z UoP
- Składka zdrowotna: skala, liniowy, ryczałt (3 progi), karta podatkowa
- Harmonogram 5-letni z kwotami + prognozy z oznaczeniem
- Wykrywanie błędnego kodu + alert CTA

## Czego jeszcze nie ma (do dodania)

- Zapis leadów do bazy (Streamlit nie ma wbudowanej bazy — trzeba podpiąć np. Google Sheets albo Supabase)
- Wysyłka emaila z wynikiem
- Eksport .ics (kalendarz)
- Formularz kontaktowy / gate
- Autouzupełnianie NIP z GUS
- Tryb biura rachunkowego

To prototyp do walidacji logiki. Gdy logika będzie potwierdzona na 100 klientach,
przejście na docelowy SaaS (Next.js + API) jest proste — `kodzus_core.py` przenosi się 1:1.

## Aktualizacja kwot ZUS

Kwoty są w `kodzus_core.py` w słownikach `RATES_2026` i `RATES_2027_FORECAST`.
Gdy ZUS ogłosi nowe oficjalne kwoty — zaktualizuj te słowniki.
