# Městský dekodér

## Účel

Městský dekodér je univerzální převodní tabulka používaná během celé hry
**Tajemné město**. Každá informace může být reprezentována několika
způsoby:

-   barvou
-   symbolem
-   číslem
-   písmenem
-   Morseovou abecedou

Děti se během týdne učí, že všechny tyto zápisy představují stejnou
informaci.

## Dekódovací tabulka

    Č. Barva      Symbol           Číslo  Písmeno   Morse
  ---- ---------- -------------- ------- --------- -------
     1 Červená    ✴ Hvězda             1     A       .-
     2 Modrá      ✈ Letadlo            2     B      -...
     3 Zelená     🕯 Svíčka             3     C      -.-.
     4 Žlutá      🕒 Hodiny            4     D       -..
     5 Oranžová   💣 Bomba             5     E        .
     6 Fialová    ✁ Nůžky              6     F      ..-.
     7 Bílá       📖 Kniha             7     G       --.
     8 Černá      👁 Oko                8     H      ....
     9 Hnědá      🔔 Zvonek            9     I       ..
    10 Šedá       🎧 Sluchátka        10     J      .---

## Princip

Stejná hodnota může být zapsána různými způsoby.

Například hodnota **B** může být:

-   Modrá
-   ✈
-   2
-   B
-   -...

## Příklady použití

### Morse

Zadání:

``` text
-...
```

Řešení:

``` text
B → 2 → Modrá → ✈
```

------------------------------------------------------------------------

### Barevný kabel

Zadání:

``` text
Zapoj zelený vodič.
```

Řešení:

``` text
Zelená → 3
```

------------------------------------------------------------------------

### Symbolový zámek

Zadání:

``` text
👁 ✁ 🕯
```

Řešení:

``` text
H F C
```

------------------------------------------------------------------------

### Elektrárna

OLED zobrazí:

``` text
Zapni A a D.
```

Na panelu jsou pouze barevné přepínače.

Řešení:

``` text
A = Červená
D = Žlutá
```

------------------------------------------------------------------------

### Rádio

Přijde zpráva:

``` text
.- ....
```

Řešení:

``` text
A H
↓
1 8
```

## Softwarová implementace

Doporučený YAML formát:

``` yaml
A:
  number: 1
  color: red
  symbol: star
  morse: ".-"

B:
  number: 2
  color: blue
  symbol: airplane
  morse: "-..."
```

## API

``` python
decoder.encode("ACE", mode="morse")
# -> .- -.-. .

decoder.encode("ACE", mode="color")
# -> Červená, Zelená, Oranžová

decoder.encode("ACE", mode="symbol")
# -> ✴ 🕯 💣

decoder.decode(".-")
# -> A
```

## Přínosy

-   Jednotný systém šifer pro celý tábor.
-   Lze snadno vytvářet nové úkoly bez nových pravidel.
-   Propojuje elektronické panely, papírové šifry i týmovou spolupráci.
-   Každá mise může používat jiný způsob zápisu stejného kódu.
