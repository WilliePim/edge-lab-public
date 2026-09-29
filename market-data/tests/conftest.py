"""market-data è una cartella sorella, non un pacchetto installato: i test la mettono nel path da soli."""
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))
