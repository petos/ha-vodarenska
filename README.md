# HA Vodarenska

Custom component pro Home Assistant – integrace s VAS Vodárenská API.

## Instalace
- Přes HACS
  [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Petos&repository=https%3A%2F%2Fgithub.com%2Fpetos%2Fha-vodarenska)
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

## HelloWorld
- Existuje a je nadefinovany sensor pro HelloWorld, ktery je ovsem deaktivovany (disabled). Slouží především pro debug při problémy s API. 

## Hlášení chyb
Nejlépe přes https://github.com/petos/ha-vodarenska/issues
