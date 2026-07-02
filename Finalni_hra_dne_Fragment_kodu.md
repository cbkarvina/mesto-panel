# Finální hra dne -- Získání fragmentu Kódu města

## Účel

Každý den zakončí agenti svou práci závěrečnou misí, během které obnoví
jednu část města.

Během dne získali informace, vyřešili dílčí úkoly a opravili poškozený
systém. V závěrečné hře musí správně nastavit řídicí panel a zadat
získaný kód.

Po úspěšném ověření získají **jeden fragment Kódu města**.

Po celý týden lze získat celkem **pět fragmentů**, které budou v pátek
použity k aktivaci Centrálního řídicího centra.

---

# Průběh

1.  Agenti přijdou k řídicímu panelu.
2.  Nastaví přepínače, enkodéry nebo další ovládací prvky.
3.  Potvrdí zadání tlačítkem.
4.  Systém ověří správnost.
5.  Při úspěchu se spustí světelná a zvuková sekvence.
6.  Agenti získají fragment Kódu města.

---

# Úspěšné systémové hlášení

## Univerzální

> **„Přístup ověřen. Fragment kódu přijat. Obnova systému zahájena."**

---

## Elektrárna

> **„Přístup ověřen. Fragment energetického systému uložen. Dodávka
> energie byla obnovena."**

---

## Komunikace

> **„Přístup ověřen. Komunikační síť je opět online. Fragment kódu
> uložen."**

---

## Doprava

> **„Přístup ověřen. Dopravní systém synchronizován. Fragment kódu
> získán."**

---

## Záchranné složky

> **„Přístup ověřen. Nouzové komunikační kanály byly obnoveny. Fragment
> kódu uložen."**

---

## Řídicí centrum

> **„Přístup ověřen. Poslední fragment přijat. Centrální systém je
> připraven k aktivaci."**

---

# Chybová hlášení

> **„Ověření selhalo. Přístup zamítnut."**

> **„Neplatný řídicí kód. Zkontrolujte nastavení panelu."**

> **„Synchronizace systému nebyla dokončena."**

> **„Bezpečnostní protokol je stále aktivní. Opakujte postup."**

---

# Světelné a zvukové efekty

## Úspěch

- Zelená animace WS2812B
- Krátký zvuk potvrzení
- Rozsvícení segmentu obnoveného systému
- Uložení fragmentu do herního stavu

## Chyba

- Červené bliknutí
- Krátký varovný tón
- Zobrazení chybového hlášení

---

# Páteční finále

Po vložení všech pěti fragmentů systém oznámí:

> **„Bylo nalezeno všech pět fragmentů Kódu města."**

> **„Probíhá rekonstrukce hlavního řídicího klíče."**

_(3sekundová pauza, světelná animace panelu)_

> **„Rekonstrukce dokončena."**

> **„Centrální řídicí systém obnoven."**

> **„Vítejte, agenti. Tajemné město je opět v bezpečí."**

---

# Implementační poznámky

- Hlášení mohou být přehrávána pomocí TTS nebo předem nahraných zvuků.
- Po každé úspěšné misi se uloží získaný fragment.
- Obnovený systém změní stav na **OK** a rozsvítí odpovídající LED
  segment.
- V pátek se po získání všech pěti fragmentů odemkne závěrečná mise.

# Dny

## PONDĚLÍ

Po správném zadání části kódu se rozsvítí na mapě POŠTA

## ÚTERÝ

Po správném zadání části kódu se rozsvítí na mapě ZÁCHRANNÉ CENTRUM

## STŘEDA

Po správném zadání části kódu se rozsvítí na mapě ELEKTRÁRNA

## ČTVRTEK

Po správném zadání části kódu se rozsvítí na mapě DOPRAVNÍ CENTRUM A CESTY

## PÁTEK

ZÁVĚREČNÁ HRA Po správném zadání části kódu se rozsvítí na mapě RADNICE A ZBYTEK MĚSTA
