# Historia zmian

## 2.0 — przepisanie na PySide6

Interfejs przeniesiony z tkinter na Qt 6, dane wyjęte z kodu do pliku JSON.

### Dodane
- Dodawanie, edycja i usuwanie komputerów w oknie programu, z walidacją.
- Monitorowanie dostępności w tle (sonda TCP lub ping) z kolumną stanu, czasem
  odpowiedzi i informacją „ostatnio online”.
- Panel szczegółów wybranej maszyny z akcjami.
- Wyszukiwarka, filtr „tylko online”, grupy i sortowanie kolumn.
- Dziennik zdarzeń ze znacznikami czasu.
- Ikona w zasobniku systemowym i powiadomienia o zmianie stanu.
- Import i eksport listy komputerów.
- Ustawienia: odstęp sprawdzania, limity czasu, liczba powtórzeń pakietu,
  czas oczekiwania na start, własny klient pulpitu zdalnego.
- Skróty klawiszowe i menu kontekstowe.
- Tryb `--demo` z przykładowymi danymi.

### Poprawione
- Błąd w liście komputerów: klucze `mac3`, `ip2`, `ip3` powodowały `KeyError`
  przy wyborze drugiej i trzeciej pozycji.
- Sztywne odliczanie 30 sekund zastąpione realnym odpytywaniem hosta co 3 sekundy.
- `time.sleep` wykonywany w wątku aktualizującym widżety zastąpiony pulą wątków Qt —
  interfejs nie zamiera podczas sprawdzania maszyn.
- Adres MAC przyjmowany w dowolnym zapisie zamiast dokładnie 12 znaków bez separatorów.
- Pakiet magiczny wysyłany kilkukrotnie, bo UDP nie gwarantuje dostarczenia.
- Plik `.rdp` tworzony w katalogu tymczasowym i kasowany po użyciu, zamiast lądować
  w katalogu programu.
- Rozdzielenie adresu komputera i celu pakietu WOL — pakiet powinien trafiać na adres
  rozgłoszeniowy sieci, a nie na IP wyłączonej maszyny.

## 1.0 — wersja pierwotna
- Okno tkinter z listą komputerów zapisaną w kodzie, wysyłką pakietu magicznego,
  paskiem postępu i otwieraniem pulpitu zdalnego.
