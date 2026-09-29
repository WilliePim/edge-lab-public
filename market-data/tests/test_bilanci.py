"""Massimo e minimo dichiarati nell'Item 5 del 10-K, e il verdetto sui salti che ne esce.

Gli estratti sono copiati dai depositi veri, senza toccarli: il 10-K Apple dell'esercizio 2000 (accession
0000912057-00-053623), quello Apple del 1996 (0000320193-96-000023, che rimanda all'Item 8) e il 10-K Iconix
dell'esercizio 2016 (0001564590-17-004444). Nessuna chiamata di rete.
"""
import datetime as dt

from market_data.quality import bilanci as B

#  Apple, esercizio 2000. Nessuna colonna «High»/«Low»: i prezzi stanno su una riga etichettata.
APPLE_2000 = (
    "Item 5. Market for Registrant's Common Stock and Related Security Holder Matters The Company's Common Stock is "
    "traded on the over-the-counter market. As of December 1, 2000, there were 24,998 shareholders of record. On June "
    "21, 2000, the Company effected a two-for-one stock split in the form of a Common Stock dividend to shareholders "
    "of record as of May 19, 2000. The price range per share of common stock represents the highest and lowest prices "
    "for the Company's common stock on the Nasdaq National Market during each quarter. FOURTH QUARTER THIRD QUARTER "
    "SECOND QUARTER FIRST QUARTER Fiscal 2000 price range per common share $64.13-$25.38 $69.75-$40.19 $75.19-$43.25 "
    "$59.00-$28.72 Fiscal 1999 price range per common share $40.07-$21.19 $25.00-$16.72 $23.66-$16.00 $20.66-$14.25 "
    "ITEM 6. SELECTED FINANCIAL DATA The following selected financial information has been derived from the audited "
    "consolidated financial statements."
)

#  Apple, esercizio 1996: l'Item 5 rimanda all'Item 8, dove la riga dei prezzi sta in mezzo a ricavi e utili, e i
#  prezzi sono in ottavi.
APPLE_1996 = (
    "Item 5. Market for the Registrant's Common Equity and Related Stockholder Matters The Company's common stock is "
    "traded on the over-the-counter market and is quoted on the Nasdaq National Market under the symbol AAPL. "
    "Information regarding the Company's high and low reported closing prices for its common stock and the number of "
    "shareholders of record is set forth in Part II, Item 8 of this Form 10-K under the heading \"Selected Quarterly "
    "Financial Information (Unaudited)\", which information is hereby incorporated by reference. Item 6. Selected "
    "Financial Data (Dollars in millions, except per share amounts) Net sales $9,833 $11,062 $ 9,189 Net income "
    "(loss) $(816) $ 424 $ 310 Selected Quarterly Financial Information (Unaudited) (Tabular amounts in millions, "
    "except per share amounts) Fourth Third Second First Quarter Quarter Quarter Quarter 1996 Net sales $2,321 "
    "$2,179 $2,185 $3,148 Earnings (loss) per common and common equivalent share $ 0.20 $(0.26) $(5.99) $(0.56) "
    "Price range per common share $25.00 -$16.00 $28.88 -$19.63 $35.50 -$23.00 $42.50 -$31.44 1995 Net sales $3,003 "
    "$2,575 Price range per common share $49.88-$ 34.69 $50.13-$ 33.63 $48.00 -$ 33.88 $43.75-$ 32.50 At September "
    "27, 1996, there were 30,008 shareholders of record."
)

#  Iconix, esercizio 2016: griglia «High/Low» per trimestre, con i trimestri del 2015.
ICONIX_2016 = (
    "Item 5. Market for Registrant's Common Equity, Related Stockholder Matters and Issuer Purchases of Equity "
    "Securities The Company's common stock, $0.001 par value per share, its only class of common equity, is quoted "
    "on the NASDAQ Global Market tier of The NASDAQ Stock Market LLC under the symbol \"ICON\". The following table "
    "sets forth the high and low sales prices per share of the Company's common stock for the periods indicated, as "
    "reported on NASDAQ: High Low Year Ended December 31, 2016 Fourth Quarter $ 10.08 $ 6.76 Third Quarter 9.12 6.26 "
    "Second Quarter 9.27 6.30 First Quarter 10.30 4.67 Year Ended December 31, 2015 Fourth Quarter $ 16.88 $ 5.34 "
    "Third Quarter 26.00 11.32 Second Quarter 34.97 24.12 First Quarter 37.29 32.70 As of March 6, 2017, there were "
    "1,219 holders of record of the Company's common stock. Item 6. Selected Financial Data"
)

#  Prezzi in ottavi, come li scrivevano i depositi prima del 2001.
FRAZIONI = ("Item 5. Market for Registrant's Common Equity The following table sets forth the high and low sales "
            "prices: High Low First Quarter 60-5/8 45 1/4 Second Quarter 58 1/2 41 3/8 Third Quarter 52 3/4 "
            "38 1/8 Fourth Quarter 47 1/4 29 7/8")


def test_riga_etichettata_senza_colonne_alto_basso():
    massimo, minimo, quanti = B.intervallo(APPLE_2000)
    assert massimo == 75.19                       # il massimo dei due esercizi riportati
    assert minimo == 14.25
    assert quanti == 16


def test_item5_che_rimanda_altrove():
    """Il 10-K del 1996 non ha i prezzi nell'Item 5: stanno nell'Item 8, in mezzo a ricavi e utili."""
    massimo, minimo, _ = B.intervallo(APPLE_1996)
    assert massimo == 50.13                       # prezzo, non «Net sales $9,833»
    assert minimo == 16.00


def test_griglia_alto_basso():
    massimo, minimo, _ = B.intervallo(ICONIX_2016)
    assert massimo == 37.29
    assert minimo == 4.67


def test_prezzi_in_ottavi():
    massimo, minimo, _ = B.intervallo(FRAZIONI)
    assert massimo == 60.625
    assert minimo == 29.875


def test_senza_tabella_dei_prezzi():
    assert B.intervallo("Item 5. Market for Registrant's Common Equity. No public market exists.") is None
    assert B.intervallo("") is None


def test_accettazione_apple_e_il_crollo_del_29_settembre_2000():
    """Il crollo vero: 53,50 -> 25,75, rapporto 0,4813, vicinissimo a 1/2. Tutte e due le chiusure stanno dentro
    l'intervallo che Apple dichiara, quindi il salto e' un movimento di mercato e la storia prima non si esclude."""
    massimo, minimo, quanti = B.intervallo(APPLE_2000, 2000)          # l'anno del salto, non i due della tabella
    assert (minimo, massimo, quanti) == (25.38, 75.19, 8)             # i quattro trimestri dell'esercizio 2000
    assert B.esamina(53.5024, 25.7488, massimo, minimo) == ("vero", None)


def test_accettazione_iconix_e_la_serie_fuori_scala_prima_del_17_dicembre_2015():
    """La chiusura del 16 dicembre 2015, 63,00, e' impossibile: Iconix dichiara un massimo di 37,29 in tutto il 2015
    e di 16,88 nel quarto trimestre. La chiusura del 17, 6,59, sta dentro. Il fattore e' vicino a 10."""
    massimo, minimo, _ = B.intervallo(ICONIX_2016, 2015)
    assert (minimo, massimo) == (5.34, 37.29)                         # il 2015, non il 2016 che sta nella stessa tabella
    esito, fattore = B.esamina(63.00, 6.59, massimo, minimo)
    assert esito == "fuori scala"
    assert 9.0 < fattore < 11.0


def test_tutte_e_due_fuori_dall_intervallo_e_incerto():
    """Due chiusure impossibili non dicono da che parte sta il guasto: non verificabile, quindi resta esclusa."""
    assert B.esamina(500.0, 250.0, 37.29, 4.67) == ("incerto", None)


def test_il_minimo_dichiarato_serve():
    """Affiliated Computer Services, 2 gennaio 2009: 13,15 -> 1,27, tutte e due **sotto** il minimo dichiarato di
    34,84. Col solo massimo passerebbe per «vera»: non e' la serie di quella societa'."""
    assert B.esamina(13.15, 1.27, 58.70, 34.84) == ("incerto", None)


def test_serie_scalata_verso_il_basso():
    """La chiusura di prima sfonda il minimo, quella dopo sta dentro: fuori scala come chi sfonda il massimo.
    Il fattore e' pre/post, quindi sotto 1 quando la serie precedente e' divisa invece che moltiplicata."""
    esito, fattore = B.esamina(1.8281, 14.50, 21.88, 13.00)
    assert esito == "fuori scala"
    assert 0.11 < fattore < 0.14                      # circa un ottavo


def test_la_tolleranza_non_ribalta_il_verdetto():
    """Una chiusura appena sopra il massimo dichiarato resta dentro: i bilanci arrotondano e gli esercizi non
    coincidono con i trimestri solari."""
    assert B.esamina(38.0, 30.0, 37.29, 4.67)[0] == "vero"          # +1,9%, dentro il 10%
    assert B.esamina(45.0, 30.0, 37.29, 4.67)[0] == "fuori scala"   # +20,7%, fuori


def test_scelta_del_bilancio_per_data():
    annuali = [("1997-12-05", "10-K", "1997-09-26", "a", ""),
               ("2000-12-14", "10-K", "2000-09-30", "b", ""),
               ("2001-12-21", "10-K", "2001-09-29", "c", "")]
    #  Il salto del 29 settembre 2000 cade nell'esercizio chiuso il 30 settembre 2000.
    assert B.annuale_per(annuali, dt.date(2000, 9, 29))[3] == "b"
    #  Un salto di ottobre 2000 cade nell'esercizio dopo.
    assert B.annuale_per(annuali, dt.date(2000, 10, 15))[3] == "c"
    #  Dopo l'ultimo bilancio non c'e' niente che copra il salto.
    assert B.annuale_per(annuali, dt.date(2010, 1, 1)) is None


def test_il_bilancio_deve_essere_vicino_al_salto():
    """Un bilancio di dieci anni dopo non dice niente sui prezzi dell'anno del salto."""
    annuali = [("2015-03-01", "10-K", "2014-12-31", "vecchio", "")]
    assert B.annuale_per(annuali, dt.date(2004, 6, 1)) is None


def test_un_minimo_letto_troppo_basso_allarga_e_non_sbaglia():
    """Il minimo letto puo' essere un dividendo invece di un prezzo. Allora la fascia e' piu' larga e il test piu'
    permissivo -- mai piu' severo: non dichiara «fuori scala» qualcosa che non lo e'."""
    assert B.esamina(10.0, 2.0, 50.13, 0.12) == ("vero", None)        # minimo contaminato: passa
    assert B.esamina(10.0, 2.0, 50.13, 16.00) == ("incerto", None)    # minimo vero: non verificabile


def test_i_prezzi_si_legano_all_anno_che_li_etichetta():
    """Una tabella dell'Item 5 riporta due esercizi. Presi insieme la fascia e' larga il doppio."""
    assert B.intervallo(APPLE_2000, 2000)[:2] == (75.19, 25.38)
    assert B.intervallo(APPLE_2000, 1999)[:2] == (40.07, 14.25)
    assert B.intervallo(APPLE_2000)[:2] == (75.19, 14.25)             # i due esercizi insieme: piu' larga
    assert B.intervallo(ICONIX_2016, 2016)[:2] == (10.30, 4.67)
    assert B.intervallo(ICONIX_2016, 2015)[:2] == (37.29, 5.34)


def test_l_anno_puo_precedere_l_etichetta():
    """«Fiscal 2000 price range per common share»: l'anno sta prima, i prezzi dopo."""
    assert B.intervallo(APPLE_1996, 1996)[:2] == (42.50, 16.00)
    assert B.intervallo(APPLE_1996, 1995)[:2] == (50.13, 32.50)


def test_i_prezzi_si_leggono_solo_dopo_l_etichetta():
    """Prima dell'etichetta stanno ricavi, utili e dividendi. Nel 10-K Apple del 1996 il minimo dell'esercizio e'
    16,00, non 0,12 (il dividendo) ne' 0,20 (l'utile del quarto trimestre)."""
    assert B.intervallo(APPLE_1996, 1996)[1] == 16.00


def test_anno_assente_dalla_tabella():
    """Il bilancio non dichiara i prezzi di quell'anno: non verificabile, quindi il salto resta escluso."""
    assert B.intervallo(ICONIX_2016, 2011) is None


def test_accettazione_continental_resources_e_la_scala_dimezzata():
    """Continental Resources il 20-12-2010 va da 28,58 a 57,64: la serie prima sta a meta' della scala vera. Con i
    due esercizi insieme (13,84-59,98) ci starebbe dentro e passerebbe per vera; con il solo 2010 no."""
    prezzi_2010 = ("High Low Year Ended December 31, 2010 Fourth Quarter $ 59.98 $ 44.10 Third Quarter 48.00 39.72 "
                   "Second Quarter 55.00 40.09 First Quarter 47.98 38.74 Year Ended December 31, 2009 Fourth "
                   "Quarter $ 45.47 $ 34.00 Third Quarter 38.00 25.00 Second Quarter 33.00 20.00 First Quarter "
                   "22.00 13.84")
    largo = B.intervallo(prezzi_2010)
    assert B.esamina(28.58, 57.64, largo[0], largo[1]) == ("vero", None)          # i due esercizi: sbagliato
    stretto = B.intervallo(prezzi_2010, 2010)
    assert B.esamina(28.58, 57.64, stretto[0], stretto[1])[0] == "fuori scala"    # il solo 2010: giusto
