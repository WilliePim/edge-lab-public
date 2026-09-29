# Costi — misura del documento primario

Generato da `python -m edgar_llm.tools.measure_docs`. Il campione e' di 20 depositi, 5 per forma.

`raw` e' il file scaricato, `testo` cio' che resta dopo HTML->testo, `finestre` cio' che finisce davvero nel prompt.

| forma | n | testo mediano | finestre mediane | token stimati | resa |
|---|---:|---:|---:|---:|---:|
| 424B5 | 5 | 208,022 car. | 20,708 car. | ~5,177 | 10% |
| 424B3 | 5 | 1,724,091 car. | 24,695 car. | ~6,174 | 1% |
| 424B4 | 5 | 963,693 car. | 28,374 car. | ~7,094 | 3% |
| 8-K/2.01 | 5 | 11,890 car. | 11,890 car. | ~2,972 | 100% |

Mediana complessiva delle finestre: **20,803 caratteri**, ~**5,201 token** di input a 4 car./token.

## Costo

A $3.00/Mtok di input e $15.00/Mtok di output, con 400 token di output assunti per estrazione (**assunto, non misurato**: lo diventa dopo la prima corsa vera).

| | documenti | costo |
|---|---:|---:|
| per documento | 1 | **$0.0216** |
| per 1.000 filing | 1.000 | **$21.60** |
| al giorno | 29 | $0.63 |
| backfill una tantum | 764 | $16.50 |

La cache rende il costo NON ricorrente: un documento si paga una volta per (prompt, modello). Il costo al giorno e' quindi un tetto, non una rendita.


## Limiti

1. **La resa non e' uniforme.** Un 8-K entra quasi intero; un 424B3 che veicola un prospetto di fusione da 1,7 milioni di caratteri entra all'1%. La copertina e sei finestre bastano su un supplemento di prospetto e non e' detto che bastino li'. E' la prima cosa che le evals devono misurare, per forma.
2. **`token stimati` non e' un conteggio**: e' caratteri diviso 4. Il numero vero arriva dagli `usage` della prima corsa.
3. **Il campione e' di 20 depositi.** Serve a dimensionare, non a descrivere la popolazione.
4. **I prezzi sono argomenti di riga di comando**, non un fatto misurato: se il listino cambia, cambia la riga di comando.

EDGAR: 0 chiamate di rete, 99 dalla cache.
