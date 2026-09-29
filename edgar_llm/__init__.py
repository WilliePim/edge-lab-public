"""Estrazione strutturata dai filing EDGAR, con un LLM.

Il perimetro di questo package e' PUBBLICO: tutto cio' che sta qui dentro puo'
finire su un repo aperto. Niente emittenti scelti da qualcuno, niente liste di
CIK cablate, niente path assoluti, niente nomi o indirizzi in chiaro. Gli
emittenti da elaborare arrivano SEMPRE come input.

`tools/perimeter_check.py` lo verifica e fa fallire la pubblicazione.

Il modulo e' un ARRICCHITORE, mai un cancello: aggiunge campi al materiale che
un umano legge, e non ha alcun diritto di bloccare, ordinare o punteggiare.
Se l'API non risponde, chi lo chiama deve girare identico a prima.
"""
