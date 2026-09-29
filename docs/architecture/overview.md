# Architettura di edge-lab: lo scanner Form 4

> Il giro quotidiano legge dalla SEC i moduli Form 4 e tiene gli acquisti veri degli insider. Poi valuta le società e
> lascia su disco un archivio, i rapporti da leggere e una tabella. Tutto il resto (ricerca, strumenti, verdetti) si
> lancia a mano.

<!-- diagramma: 00-panoramica.mmd -->
**[▶  Apri il diagramma nell'editor Mermaid](https://mermaid.live/edit#pako:eNqNVs1u20YQfpUBDTQJICWmSNmq4BjQHwUDcRJYcZA26mFFrqiBqV1muVQaB3mDoi3Qotf01EsvvfXQW_omfYI8Qmd3SSp2ZDg5RObuzDc733wzu2-9WCbc64PXbrfnQqPOeB9OMiiw0HzNAAWUAmKZ5RKSOzKOVyjnIpZiiWl_LgD0iq_JZcEK3nw-ZwrZIuOFtQBYSqFneElmc8_v5t_PPbeeoeAjmUllNvYOwsOwN6z34qykE6jhRWo3o24URNH1TakS7pwHh71hNHD7y0y-jldM6Sp8XKqNOyIWbiVnSYKCkP1wLmzmjQ88OnM2RblIFctX8PRk8PjJy7n3309_AQw2GyLA-87ZmH8JKh5rlAKeDberT_275JIwzN7cL1YtyJiIkWkJDNZMyKOFenBMjDLDbo5M4BJj2lbc7iR8WwGZc8U0bkzUe_1-HwVemho0kToU6JGEIlaYazoOMHNGi5MrnjPFILvD1gvkQjt4Xh0HMuPGhOCKwAl7WVWxzgHa7WMK4Ja4SObiGjfTkzNDzcf3v_4IMEUl4VUpNSaUkQT48DdcDXEba1OfwI4Wx75xPWMx6U6zoweLY3vsjKcpJ86yjMFsMgKEtUzKDCGSag1hxVxKC2WmcY1wsA8pSiVwV3bTjovVMbFmPOPEquBNME10cShInWAQWfyqpIIgbLhCa1CUGay5im1RqUZa7owSuCiByyhNVZnnbE2lkE0ohaXAIuZXAtU6oFxJB0VBPzJGrv_9fWeY0IUJTZjnLCs1u5pOghSzMEstUBSM2thIJcGsRGvZckmRBEkXjkUkB-qvFuQlKSdNcXeGXRe6a3kkEWpdqm3RmKJYpEcKy_JcKo0ukmYLm5yRui3SbnAnwWnH_QTuJ3Q_3Zt1OT6ZjZwwf_kDYCSJPsULTSSWlHMRf0kLn_sv7869QXV-sNTErq9KQXiYMqC6N3WBjeVds7l3z2RSZ_4JYscgnlU8mO63kq6a3rLAMuTURURlkaNoy-XS_E2iS7jWeDNyYJCfVZyOZs-bMVJze5NjaI_EU9IcxU04NsEqiBiNbNAUKrvjhhGNqZ2AuyoRnT85O7GV-OFnoD5TG9IbcDO-bV_eVoUXdpCadiceJuPp4Kyagw7ik1RedIzlN2wlJUQoaMLxG00DYzoQeqVkjrGTvmn1glMDxryQN3qG1rMWBQ3Yy8uKKRpHTF1w3U6sBj7330XPqbtbPr7_jdh5xDaksfquwOqu-AKSTs3crIrIKjnRxVJVsuosi7V1MeNvpks7BEjMsRll9aXRVhWWxp2-ZqhV45lXjbGqr5Y1FqXRx1W3T3J_2oGHD6l9ffdJLX7Uvk_9_KJeCOuF6uKZdqF9ny55CicFdd6HPzkFscPswz9zD6xtsLWlz3MfvqJ2M_8FV0EYLOnVQW2hZOX62FT0Md1a5gpuRnvCiwst8x2X7qmbSeeh-zwPHXBmmAaZUqvUPWfh6zF12rmW53ahQjoNrlu4eXfeNT06NopwXDvBKVeAz4dC_UZiRTHmS3Bnp7SzrL83jMbDaNIyzX7B-3ud7kEwGbZi-wjb8yfBoDeoNtuvMdGrfoeea1fxzISu0Cb7k8MoatAOgoODyK_RAr8z6fm3odXHrhBHo2gY-Q3i_vjrsNdrzheEk_DW81U9VwFG40lnEjaAw4nf645rwF7g98LgNkCj4hptMj4cDBq0yaDb2x_VaIejztjv7EDzWuDRU2HNMDFP7bdzzz6T5555utqXs_fO2LBSy9kbEdO6ViXd1F6Z0zDhY2Q0LdbbZSXLdEWfS5YV5jtn4lspa4N3_wMtwMN4)**

## Cosa racconta

Il diagramma ha cinque blocchi:
- **chi avvia il lavoro:** lo script `daily.sh`, lanciato a mano o da un pianificatore del sistema operativo;
- **le cinque fasi del giro quotidiano;**
- **cosa resta su disco;**
- **i servizi esterni** a cui lo scanner si collega;
- **i lavori che non partono da soli.**

Non ci sono server, code di messaggi né database: ogni giro è un programma che parte, lavora e finisce.

## I diagrammi, in ordine di lettura

| # | pagina | cosa spiega |
|:-:|---|---|
| 1 | [Il giro quotidiano](01-giro-quotidiano.md) | dall'avvio alla notifica, con i punti in cui il giro può fermarsi |
| 2 | [Come si giudica una società](02-valutazione-societa.md) | i due cancelli, il profilo di chi compra, il punteggio |
| 3 | [Come si chiede un documento alla SEC](03-richieste-sec.md) | copia su disco, pause, tentativi, errori |
| 4 | [Come nascono i rapporti del giorno](04-rapporto-giornaliero.md) | novità, colonna LLM, sorveglianza, scrittura |
| 6 | [Come si svolge uno studio di ricerca](06-studi-di-ricerca.md) | dalla pre-registrazione al referto |
| 7 | [I dati che lo scanner conserva](data-model.md) | i file di stato come tabelle, con le relazioni |

La pagina 5 del registro di lavoro (come l'operatore registra un verdetto) non fa parte di questa versione pubblica;
il codice del registro (`form4_scanner/verdicts.py`) sì.

## I pezzi del sistema

| pezzo | dove | chi lo fa partire |
|---|---|---|
| Giro quotidiano | `form4_scanner/`, avviato da `daily.sh` | a mano, o un pianificatore del sistema operativo |
| Colonna «emissione» | `edgar_llm/`, chiamato dai rapporti | solo se l'interruttore `EDGAR_LLM_DAILY` è acceso |
| Verdetti | `form4_scanner/verdicts.py` | l'operatore, a mano |
| Studi di ricerca | `backtest/` | a mano |
| Archivio prezzi | `market-data/`, letto solo tramite `market_data.api` | a mano (aggiornamento dell'archivio) |
| Strumenti di raccolta | `tools/` | a mano |

## Come si aggiornano i diagrammi

- I diagrammi stanno in [diagrammi/](diagrammi/), un file `.mmd` ciascuno.
- Dopo una modifica, `python docs/architecture/diagrammi/genera_link.py` riscrive i link di tutte le pagine.
- Il link contiene il diagramma stesso: aprirlo non richiede nient'altro.

## Note: dove la documentazione non dice quello che fa il codice

Segnalate durante la ricostruzione del 22-09-2026; il codice non è stato toccato per scriverle.

1. **`daily.sh` e `run.sh`.** Il README li descrive come «scan» e «scan + archive + reports». In realtà archivio e
   rapporti li scrivono tutti e due: cambia solo la notifica sul desktop.
2. **Chi dipende da chi.** Risolta il 27-09-2026: edge-lab non dipende da nessun repo esterno (ADR-054), market-data
   vive in `market-data/` di questo repo (ADR-055), e un test di confine sull'AST lo verifica.
3. **`xbrl.py`.** Il README lo mette nella pipeline, ma il giro quotidiano non lo usa: lo usano solo alcuni strumenti
   e studi.

Le incoerenze che riguardano un singolo flusso stanno nella pagina di quel flusso.
