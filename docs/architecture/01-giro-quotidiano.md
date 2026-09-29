# 1 · Il giro quotidiano

> Dall'avvio alla notifica sul desktop: cinque fasi. Il giro si ferma solo per un errore imprevisto in raccolta o
> in valutazione. Un problema nella scrittura produce un avviso e il giro prosegue.

<!-- diagramma: 01-giro-quotidiano.mmd -->
**[▶  Apri il diagramma nell'editor Mermaid](https://mermaid.live/edit#pako:eNqlVk2P2zYQ_SsD7SEtsJtYkr9iBFv4S0GAIkXtwgga90BLtDwIRSok5bQb5L_03t576C35Yx2Ksi07TnLoXrzizDwO38w88n2QqowHIwju7u7W0qIVfAQvBOSoFbytlMUMmVS3kDEhHrH9HhXQfwwkmbaYsrVMldxiPlpLALvjBcVvmOHHzxXTyDaCm9oDYKukXeIDua2DsFf-vg78ukDJp0oo7Qw3_e6gO5wcbKmojOV68iavjUkviZPk0qh0xn3weDCcJGNv3wr1Lt0xbZvt00rvfYpo_ErJsgwlIYfdtaxpOMbALzPvY6pNrlm5gyR8TWnDx39g7LhYB795B_c3Dr8jI5FXEmU1OVZpDoLJFBkIBSZlUnL9bKOf3BNrgIJoLDiQzyNeMPosuSZ_WM6nhPz9aDRCiQ-0zWmP6P06eFkHZVDHeDQEo6T6YR18oKCMp2hQSd7ODe7u7incL3GZ-X_GEa1TFrX1VX2AJcKW64K5Q6NVTSLGqnItL9mIyD9ybCxYmiphGWQcoVBZJfCMm0XokU2qNHGiconUY0rTzoLtlWYW96o-SsZzgVAJiwVCv-O9HBglsW0aq8F0XPxccdEg1eGePeCaASM2LfsyJ4uY4n98hDLDlNeJZ7xUBi02iRyAwSAInuf8K1hdX_pTAJVaWdbUmur18S_D5QMDv93Hf_2JnE8LpXdgiYaGmkUBQqJ0Ad0ahwsuqakQJKdh9EBXiem_r5Op6-BpoYSsVvuvsTF43QpyJzCMCno1zaFP03KZK3daGltwVWPp2woNJbjnGkd-44oguXaz4AtCWiKp9zNWj4mCUitqpqIgh1vPO-GIgpMp6j3udDqQKRIcfb0FfFsvonZXtDp60b00mE9_e0vcboQvhcRnIT3_028z3Y4cXBqOkcOrY3c0h59PVkwUx26yVkxUlj3UxWpP1MpN1PM26VQyjZVEmjHHK0mJUSly--lP3z3OgUzUB07ASW0MFhtXOmJ8o7Rh1xheRa9pn5_cvB7QSDGNIQCgDk2pE7GBp5blew6VhLKSluYFfe89w_s9pz3oJvGVhk707Ane03ZX9vMVXV0K1aLr18Pmc3D-OTz7TIjex07QIidoz91dtqVb61LNalcq8WO6NChrrrXTayxKzffEKE2fBN0IW30SBftTNQjSo7oYf2OuA_Dbfl5Ppw9dV89lqtHaSnup1EgDYmmmz2q7bNSSEYeVzI_4dRL1RazTHbq7mLIk2tW1yi2jg5ho0tZaSyiVUmnrhO5MNK9UqNtU6HPYuAXrbjewbMNdR02Xq4NwCn7qFjftG6FSkoCrarX0FV9G_ic-t7jaGO6JNind3O4NYkhLKIEdXVONaDQEOTUxPK94U4ll1Objf6PFF025anK-Mr9OyXuu3tMdVobKfVbgqSvwAnmJQuWt7a_xM62b-GXz3gInqBk3b6iDfTtICnWdmjJTj7Jv4y-8H6ae7OnleC1jv94M0Kvo6HZ4ZNHMz_gWPCBsUYjRzSSZTZL5rSFJecNHN1GvH88nt2n9irsJ5_F4OG6Md-8ws7tRRO-9czx31gZt3pkPkuSI1o_7_SQ8oMVhNB-G30I73msNZDKb9485jG5mTweDTv8AORjGvU7yLUh39R0SpBSSzhHtaXccT4an40ZP48m30JzwHHKbT8fTVm7TqB-dckvCWTi7ghbcQlC45xlm7tlOF339yl4H7uVbP7yDD86HVVYt_5AprVtdcVqpyowmcOZH_LSsVZXv6JNmwrjvkslflTo4fPgPuBDFDw)**

## Cosa racconta

Il percorso di un giro normale, con le domande che decidono se un giorno o un modulo si salta. Mostra anche dove un
errore ferma tutto e dove invece si scrive un avviso e si va avanti.

## Passo per passo

1. **Avvio.** Senza nome ed email per la SEC il giro non parte.
2. **Raccolta.** Per ogni giorno lavorativo degli ultimi 60:
   - i festivi e gli indici illeggibili si annotano come «senza indice»;
   - i moduli introvabili si saltano;
   - dei moduli trovati si tengono solo gli acquisti sul mercato aperto, non programmati, da almeno 25.000 dollari.
3. **Valutazione.** Gli acquisti si riuniscono per società e ognuna passa i cancelli (diagramma 2).
4. **Scrittura.** Archivio storico, rapporti (diagramma 4), tabella CSV. Archivio e rapporti hanno ciascuno una
   protezione: se falliscono, compare un avviso e il giro continua.
5. **Chiusura.** Riepilogo a schermo e notifica sul desktop, che arriva anche quando il giro fallisce.

## Dove sta nel codice

| passo | file e funzione |
|---|---|
| avvio | `daily.sh` (e `run.sh`, senza notifica), `form4_scanner/cli.py` → `main` |
| giorni e indici | `form4_scanner/scan.py` → `collect_buys`, `parse_master_index`; `form4_scanner/secdays.py` |
| moduli e filtro | `form4_scanner/parse.py` → `parse_ownership_xml`, `open_market_buys` |
| raggruppamento e simboli | `form4_scanner/cluster.py` → `group_by_issuer`; `form4_scanner/tickers.py` → `apply_to_clusters` |
| scrittura | `form4_scanner/observations.py` → `write`; `form4_scanner/breadth.py` → `write_weeks`; `cli.py` riga 339 per il CSV |
| notifica | `tools/notify.ps1`, chiamato da `daily.sh` |

## Note

- **Stato «ok» prima del CSV.** Lo stato dell'ultimo giro si scrive prima della tabella CSV. Se la tabella non si
  scrive, lo stato dice comunque «ok». In più `cli.py` non crea la cartella `out/`.
- **Il veto sulla diluizione è implementato, disattivato finché non è validato.** Per default
  (`EDGE_LAB_DILUTION_VETO` non acceso) il predicato si calcola e compare come flag, e nessuna società è bloccata.
- **Le società bloccate restano nell'archivio.** Con il veto acceso le società bloccate dalla diluizione
  entrano nell'archivio e non compaiono nei rapporti. Nella tabella CSV compaiono solo con l'opzione `--all`.
- **Un'opzione dal nome fuorviante.** `--observations-dir` è la radice di tutto lo stato del giro, non solo
  dell'archivio.
