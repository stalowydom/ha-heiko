# Helpery do panelu (SQL, history_stats, szablon)

Kafelki pod wykresem zużycia korzystają z trzech helperów **SQL** (Ustawienia → Urządzenia i usługi → Dodaj integrację → SQL).
Liczą z długoterminowych statystyk licznika energii pompy, więc pokazują pełny miesiąc także wstecz.
Zamień `sensor.tze284_dikb3dp6_ts0601_energia` na swój licznik energii (kWh, `total_increasing`).

Wspólny fragment:

```sql
-- SID
(SELECT id FROM statistics_meta WHERE statistic_id = 'sensor.tze284_dikb3dp6_ts0601_energia')
```

**Pompa ciepła – zużycie w miesiącu** (kolumna `v`, jednostka `kWh`, klasa `energy`)

```sql
SELECT ROUND(l.sum - p.sum, 2) AS v
FROM (SELECT sum FROM statistics WHERE metadata_id = SID ORDER BY start_ts DESC LIMIT 1) l,
     (SELECT sum FROM statistics WHERE metadata_id = SID
        AND start_ts < CAST(strftime('%s', date('now','localtime','start of month'), 'utc') AS REAL)
        ORDER BY start_ts DESC LIMIT 1) p
```

**Pompa ciepła – zużycie wczoraj** (kolumna `v`, `kWh`, `energy`)

```sql
SELECT ROUND(a.sum - b.sum, 2) AS v
FROM (SELECT sum FROM statistics WHERE metadata_id = SID
        AND start_ts < CAST(strftime('%s', date('now','localtime'), 'utc') AS REAL)
        ORDER BY start_ts DESC LIMIT 1) a,
     (SELECT sum FROM statistics WHERE metadata_id = SID
        AND start_ts < CAST(strftime('%s', date('now','localtime','-1 day'), 'utc') AS REAL)
        ORDER BY start_ts DESC LIMIT 1) b
```

**Pompa ciepła – średnio dziennie w miesiącu** (kolumna `srednia`, `kWh/dzień`, state_class `measurement`)

```sql
SELECT ROUND((l.sum - p.sum) / ((l.start_ts + 3600 - b.t0) / 86400.0), 2) AS srednia
FROM (SELECT CAST(strftime('%s', date('now','localtime','start of month'), 'utc') AS REAL) AS t0) b,
     (SELECT sum, start_ts FROM statistics WHERE metadata_id = SID ORDER BY start_ts DESC LIMIT 1) l,
     (SELECT sum FROM statistics WHERE metadata_id = SID
        AND start_ts < CAST(strftime('%s', date('now','localtime','start of month'), 'utc') AS REAL)
        ORDER BY start_ts DESC LIMIT 1) p
```

W każdym zapytaniu wstaw w miejsce `SID` wspólny fragment (w nawiasach). Działa z domyślną bazą SQLite.

**Pompa ciepła – kWh na stopień** (kafelek „kWh / stopień”, wynik z wczoraj; kolumna `v`, jednostka `kWh/K`). Wykres dzienny jest liczony przez samą integrację (`efficiency:` w README), ten helper służy tylko do kafelka.

```sql
SELECT CASE WHEN (i.m - o.m) > 1 THEN ROUND((a.sum - b.sum) / (i.m - o.m), 3) END AS v
FROM (SELECT sum FROM statistics WHERE metadata_id = SID
        AND start_ts < CAST(strftime('%s', date('now','localtime'), 'utc') AS REAL)
        ORDER BY start_ts DESC LIMIT 1) a,
     (SELECT sum FROM statistics WHERE metadata_id = SID
        AND start_ts < CAST(strftime('%s', date('now','localtime','-1 day'), 'utc') AS REAL)
        ORDER BY start_ts DESC LIMIT 1) b,
     (SELECT AVG(mean) AS m FROM statistics WHERE metadata_id = (SELECT id FROM statistics_meta WHERE statistic_id = 'sensor.TEMP_WEWN')
        AND start_ts >= CAST(strftime('%s', date('now','localtime','-1 day'), 'utc') AS REAL)
        AND start_ts <  CAST(strftime('%s', date('now','localtime'), 'utc') AS REAL)) i,
     (SELECT AVG(mean) AS m FROM statistics WHERE metadata_id = (SELECT id FROM statistics_meta WHERE statistic_id = 'sensor.TEMP_ZEWN')
        AND start_ts >= CAST(strftime('%s', date('now','localtime','-1 day'), 'utc') AS REAL)
        AND start_ts <  CAST(strftime('%s', date('now','localtime'), 'utc') AS REAL)) o
```

## Starty CO / CWU (helpery „Statystyki historii” + szablon)

- **Pompa ciepła – starty CO dzisiaj**: Statystyki historii, encja `sensor.heiko_tryb_pracy`, stan `2`, typ *liczba*, start `{{ today_at() }}`, koniec `{{ now() }}`.
- **Pompa ciepła – starty CWU dzisiaj**: tak samo, stan `1`.
- **Pompa ciepła – starty dziś (CO/CWU)**: szablon sensora (kafelek „Starty dziś (CO / CWU)”):

```jinja
{{ states('sensor.pompa_ciepla_ilosc_startow_dzisiaj') }} · CO {{ states('sensor.pompa_ciepla_starty_co_dzisiaj') }} · CWU {{ states('sensor.pompa_ciepla_starty_cwu_dzisiaj') }}
```

Liczone są wejścia pompy w grzanie CO albo CWU. Przełączenie CO → CWU bez zatrzymania sprężarki liczy się jako cykl CWU, więc suma CO + CWU może się różnić o jeden od liczby startów sprężarki.
