# HA Vodarenska

Custom component pro Home Assistant - integrace s VAS Vodárenská API.

## Instalace

- Přes HACS

  [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Petos&repository=ha-vodarenska)

  - Nainstalujte HACS.
  - V rozhraní HACS klikněte v pravém horním rohu na tři svislé tečky.
  - Klikněte na **Vlastní repozitáře**.
  - Přidejte adresu `https://github.com/petos/ha-vodarenska` a typ `Integrace`.
  - Po přidání repozitáře vyhledejte `Vodárenská Vodoměr (VAS API)` a nainstalujte jej.
  - Po restartu Home Assistanta přidejte integraci v **Nastavení → Integrace**.

- Ručně:
  - Zkopírujte celý adresář integrace do `/config/custom_components/ha_vodarenska/`.

- Požádejte o přístup k API podle [dokumentace VAS](https://vodarenska.cz/download/informace-o-api-smart-pro-zakaznika-vas/).
- Po obdržení přihlašovacích údajů je zadejte při konfiguraci integrace v uživatelském rozhraní Home Assistantu.

## Senzory

- `sensor.vas_vodomer_<meter_id>`: stav vodoměru.
- `sensor.vas_vodomer_<meter_id>_temperature`: teplota vodoměru.
- `binary_sensor.vas_vodomer_<meter_id>_installed`: informace, zda je vodoměr nainstalován.

### Atributy

- `last_seen`: kdy Home Assistant naposledy aktualizoval stav senzoru.
- `last_update`: čas posledního odečtu z API.
- Další atributy: `customer_id`, město, ulice, číslo, technické číslo, `MP_TYPE`, `radio_number` atd.

## Konfigurace

- Integrace se konfiguruje přes uživatelské rozhraní zadáním uživatelského jména a hesla.
- Automaticky vytvoří senzory pro všechny dostupné vodoměry.
- Senzory se aktualizují každých 5 minut. Nová data z API se načítají jednou za 6 hodin.
- Pokud chcete v Home Assistantu zobrazovat historickou spotřebu vody, doporučujeme provést import historických dat podle následující sekce.

## Home Assistant Energy Dashboard

Integrace ukládá historické údaje o stavech vodoměrů do externích statistik Home Assistantu. Energy Dashboard z nich vypočítává spotřebu vody a zobrazuje její vývoj v čase.

### Nastavení

1. Otevřete **Nastavení → Panely → Energie**.
2. V části **Voda** přidejte nový vodní zdroj.
3. Jako statistiku vyberte odpovídající vodoměr ve tvaru `ha_vodarenska:vas_vodomer_<meter_id>_vodomer`.
4. Uložte konfiguraci.

Energy Dashboard vypočítává spotřebu z rozdílů mezi kumulativními stavy vodoměru.

Integrace zpracovává dostupné odečty do hodinových statistik. Pokud API poskytne v jedné hodině více záznamů, použije se nejnovější z nich. API však nemusí poskytovat odečet přesně každou hodinu, takže hodinové statistiky nemusejí obsahovat záznam pro každou hodinu.

Dostupnost historických údajů závisí na datech poskytovaných API a na tom, od kdy jsou statistiky v Home Assistantu k dispozici.

### Import kompletní historie

Služba `ha_vodarenska.import_full_history` umožňuje ručně importovat dostupnou historii všech vodoměrů do statistik Home Assistantu. Import probíhá na pozadí, takže není nutné čekat na jeho dokončení v rozhraní pro spouštění akcí.

Import lze omezit volitelnými parametry:

- **`from`** - počáteční datum ve formátu `YYYY-MM-DD`. Pokud není zadáno, použije se datum počátečního odečtu konkrétního vodoměru.
- **`to`** - koncové datum ve formátu `YYYY-MM-DD`. Pokud není zadáno, použije se aktuální datum.

Obě data jsou zahrnuta do importovaného období.

Příklady použití:

| Parametry | Rozsah importu |
|---|---|
| Bez parametrů | Od počátečního odečtu každého vodoměru do aktuálního data |
| Pouze `from` | Od zvoleného data do aktuálního data |
| Pouze `to` | Od počátečního odečtu každého vodoměru do zvoleného data |
| `from` i `to` | Pouze zvolené období včetně obou krajních dnů |

**Upozornění:** Kompletní import může výrazně zatížit API a jeho dokončení může trvat delší dobu. Spouštějte jej uvážlivě, zejména při prvním načítání historie nebo při opravě většího množství chybějících dat.

Import načítá data v dávkách. Opakovaný import může doplnit chybějící historické údaje a aktualizovat již existující časové body ve statistikách Home Assistantu.

Průběh a výsledek importu jsou oznamovány prostřednictvím trvalých oznámení v rozhraní Home Assistantu. Podrobnosti o případných chybách lze dohledat v logu Home Assistantu.

## HelloWorld

Existuje senzor `HelloWorld`, který je ve výchozím stavu deaktivovaný. Slouží především k ladění a diagnostice problémů s API.

## Hlášení chyb

Chyby a návrhy na vylepšení hlaste nejlépe přes [GitHub Issues](https://github.com/petos/ha-vodarenska/issues).
