# HA Vodarenska

Custom component pro Home Assistant – integrace s VAS Vodárenská API.

## Instalace
- Přes HACS nebo ručně:
  - `/config/custom_components/ha_vodarenska/` + všechny soubory
- Žádost o přístup k API dle dokumentace: https://vodarenska.cz/download/informace-o-api-smart-pro-zakaznika-vas/
- Poté, co do mailu dostanete přihlašovací údaje, stačí je vyplnit do UI při konfiguraci. 

## Senzory
- `ha_vodarenska_<meter_id>`: stav vodomeru
- `ha_vodarenska_<meter_id>_temperature`: teplota vodomeru
- `ha_vodarenska_<meter_id>_installed`: zda je vodomer nainstalován (binary_sensor)

### Atributy
- `last_seen`: kdy HA aktualizoval stav senzoru
- `last_update`: čas posledního odectu z API
- Další atributy: customer_id, město, ulice, číslo, technické číslo, MP_TYPE, radio_number atd.

## Konfigurace
- Přes UI konfiguraci – zadání uživatelského jména a hesla.
- Automaticky vytvoří senzory pro všechny měřiče vodomeru.
- Aktualizace hodnot probíhá jednou za 5 minut, ovšem nové hodnoty se do API načítají jednou za 6 hodin. 

## Hlášení chyb
Nejlépe přes https://github.com/petos/ha-vodarenska/issues
