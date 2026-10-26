# HA Vodarenska

Custom component pro Home Assistant – integrace s VAS Vodárenská API.

## Instalace
- Přes HACS

  [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Petos&repository=ha-vodarenska)

  - Nainstalujte HACS
  - V HACS rozhraní kliknout v pravém horním rohu na tři svislé tečky
  - Kliknout na Vlastní repozitáře
  - Přidat adresu `https://github.com/petos/ha-vodarenska` a typ `Integrace`
  - Po přidání repozitáře vyhledat `Vodárenská Vodoměr (VAS API)` a nainstalovat
  - Po restartu Home Assistenta přidat jako Integraci v Nastavení -> Integrace
- Ručně:
  - `/config/custom_components/ha_vodarenska/` + všechny soubory
- Žádost o přístup k API dle dokumentace: https://vodarenska.cz/download/informace-o-api-smart-pro-zakaznika-vas/
- Poté, co do mailu dostanete přihlašovací údaje, stačí je vyplnit do UI při konfiguraci. 

## Senzory
- `sensor.vas_vodomer_<meter_id>`: stav vodomeru
- `sensor.vas_vodomer_<meter_id>_temperature`: teplota vodomeru
- `sensor.vas_vodomer_<meter_id>_installed`: zda je vodomer nainstalován (binary_sensor)

### Atributy
- `last_seen`: kdy HA aktualizoval stav senzoru
- `last_update`: čas posledního odectu z API
- Další atributy: customer_id, město, ulice, číslo, technické číslo, MP_TYPE, radio_number atd.

## Konfigurace
- Přes UI konfiguraci - zadání uživatelského jména a hesla.
- Automaticky vytvoří senzory pro všechny měřiče vodomeru.
- Aktualizace hodnot probíhá jednou za 5 minut, ovšem nové hodnoty se do API načítají jednou za 6 hodin. 
## Home Assistant Energy Dashboard

Integrace ukládá historická data o stavech vodoměrů do statistik Home Assistantu. Energy Dashboard z nich může vypočítávat spotřebu vody a zobrazovat její vývoj v čase, včetně hodinových údajů.

### Nastavení

1. Otevřete **Nastavení > Panely > Energie**.
2. V části **Voda** přidejte nový vodní zdroj.
3. Jako statistiku vyberte odpovídající vodoměr ve tvaru `ha_vodarenska:vas_vodomer_<meter_id>_vodomer`.
4. Uložte konfiguraci.

Energy Dashboard vypočítává spotřebu z rozdílů mezi kumulativními stavy vodoměru. Dostupnost historických a hodinových údajů závisí na datech poskytnutých API a na tom, od kdy jsou statistiky v Home Assistantu k dispozici. API neposkytuje nutně odečet přesně každou hodinu.

### Import kompletní historie

Služba `ha_vodarenska.import_full_history` umožňuje ručně importovat kompletní dostupnou historii všech vodoměrů od data jejich počátečního odečtu.

**Upozornění:** Kompletní import může výrazně zatížit API a jeho dokončení může trvat delší dobu. Spouštějte jej uvážlivě a pouze tehdy, když potřebujete doplnit nebo opravit historické statistiky.

Opakovaný import zapisuje historické časové body do statistik Home Assistantu, a může tak doplnit chybějící údaje i v již importovaném období.

## HelloWorld
- Existuje a je nadefinovany sensor pro HelloWorld, ktery je ovsem deaktivovany (disabled). Slouží především pro debug při problémy s API. 

## Hlášení chyb
Nejlépe přes https://github.com/petos/ha-vodarenska/issues
