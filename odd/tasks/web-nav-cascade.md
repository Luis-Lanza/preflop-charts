# Web nav: three-step cascade

Replace the flat list of 114 spot chips with a cascade that mirrors how a hand is
built: your seat, then who is in the hand, then the situation that is unlocked.

## Specs

S1. User request, verbatim: "que yo pueda seleccionar mi posicion y la del rival, y en base a eso se ven desbloqueando las opciones de situaciones, igualmente si hay 3 involucrados como en un squeeze." Direction chosen: "me gusta la propuesta A".

S2. Step 1: six seat buttons (UTG, HJ, CO, BTN, SB, BB), always all enabled.

S3. Step 2: the rival row. One chip "Nobody" (everyone folded, i.e. your open) plus the five other seats, split into two visual groups: "acts before you" and "acts after you". Only chips with a chart stay enabled; the data guarantees all five exist.

S4. Step 3: the situation row shows exactly the 2-3 spots unlocked by the pair. Labels name the action waiting for you ("Rival opens", "Rival 4-bets", "Rival 4-bet jam", "Rival 3-bets", "Rival 5-bet jam"), with the source family as the sub-label.

S5. Two rivals: a "two players before you" toggle appears only for seats that have at least two earlier seats (CO 1 combination, BTN 3, SB 6, BB 10). Turning it on replaces the rival row with two rows, opener and third player, and the situation row always offers cold 4-bet and squeeze.

S6. Counts this must reproduce exactly: 5 solo spots, 30 pairs (21 with two situations, 9 with three), 20 triples (each with two) = 114.

S7. Data stays authoritative and precomputed: the builder emits a `nav` tree of ids plus per-spot `rivals`, so the client never derives poker structure. A test proves the bijection: every spot id appears exactly once across the tree and every leaf resolves.

S8. Unchanged: the 13x13 grid, the breadcrumb with bet sizes, the per-cell mix on hover, the copy-range button, and the PDF pipeline. Deep links keep working: `#<hero>/<spotId>` restores hero, rival, third player and situation.

## Tasks

| ID | Spec | Route | Status |
| --- | --- | --- | --- |
| T1 | S6 S7 | inline: structured steps + `nav` tree + bijection test | done — 114/114 in nav, bijection test green |
| T2 | S2 S3 | inline: seat buttons + rival row with before/after groups | done — separators are labels, not buttons |
| T3 | S4 S5 | inline: situation chips + two-rival toggle (opener/third rows) | done — "Two players" chip, OPENED and THEN rows |
| T4 | S8 | inline: deep link restores the full selection; keyboard kept | done — `#bb/squeezing-bb-vs-utg-open-hj-call` restores both rivals |
| T5 | S1 S6 | inline: tests, build, headless screenshots at 1280 and 390 | done — 26 tests, three screenshots reviewed |

## Log

L1. User: "bien pa ayudame a plantaer una mejora de UIUX. que yo pueda seleccionar mi posicion y la del rival, y en base a eso se ven desbloqueando las opciones de situaciones, igualmente si hay 3 involucrados como en un squeeze. coomo planteamos esto?"
L2. Measured from data: 5 solo, 30 pairs (21x2 + 9x3 situations), 20 triples (always 2). Pairs split 15 with the rival acting before hero and 15 after. Triples exist exactly for ordered pairs of earlier seats: CO 1, BTN 3, SB 6, BB 10.
L3. User: "me gusta la propuesta A" — cascade of steps, table map (proposal B) not built.
L4. Deviation kept from the spoken plan: the situation chip's sub-label is the source family name instead of "level N of M", because the main label already names the bet and a second numbering adds a concept without adding information. One-line change if the level number is preferred.

L5. Bug found while building: `rivals` was built from every action step, so a villain who both opened and 4-bet produced `["UTG","UTG"]` and 39 spots silently fell out of the nav tree. Deduplicated in first-action order; the bijection test now fails if it ever regresses.
L6. The big blind has no solo spot (it never opens), so `nav.bb.solo` is null and the "Nobody" chip renders disabled with the reason. Every other seat has one.
L7. Mobile fix: the `.step` mobile override was declared before the base rule and lost the cascade; the media query now sits at the end of the stylesheet, so labels stack above their chips on narrow screens.
