# Dice che il report esiste.
#
# PERCHE'. Il giro scrive reports/daily_YYYY-MM-DD.md di mattina in una cartella
# che nessuno apre, e nessuno avvisa. Uno scheduler che lo lancia cattura
# l'output, quindi nemmeno cio' che stampa arriva a qualcuno.
# Quindici nomi da leggere restavano su un disco in silenzio.
#
# COSA LEGGE. Solo state/daily/last_run.json, che il giro scrive alla fine
# (form4_scanner/lastrun.py). Non apre il report, non conta niente da se', non
# sa come si chiamano i file: se il giro cambia i suoi percorsi, questo script
# non va toccato.
#
# COSA NON FA. Non decide se valga la pena avvisare -- avvisa che il giro e'
# finito, con i numeri. Una soglia sarebbe un giudizio, e i giudizi in questo
# repository non stanno nel codice.
#
# NON PUO' FAR FALLIRE IL GIRO. Esce 0 in ogni caso: file assente, JSON rotto,
# notifiche disattivate, WinRT non disponibile. Un avviso mancato e' un
# fastidio; un giro fallito per colpa dell'avviso sarebbe un danno.
#
#     powershell -NoProfile -ExecutionPolicy Bypass -File tools/notify.ps1
#     ... -Dry                     stampa il testo invece di mostrarlo
#     ... -Fail "uscita 1: ..."    il giro e' fallito: avvisa di quello
#     ... -StateDir C:\altro\state

[CmdletBinding()]
param(
  [string]$StateDir = "",
  [switch]$Dry,
  # Il giro e' fallito. Non si legge l'esito, che sarebbe quello di IERI: un
  # guasto alle 8:00 che annuncia i numeri del giorno prima e' peggio del
  # silenzio, perche' sembra riuscito.
  [string]$Fail = ""
)

$ErrorActionPreference = "Stop"

function Esc($t) {
  if ($null -eq $t) { return "" }
  return ($t -replace '&', '&amp;' -replace '<', '&lt;' -replace '>', '&gt;')
}

function Mostra($titolo, $riga2, $riga3, $uri) {
  # L'AppID e' quello di PowerShell, che e' registrato nel menu Start. Un
  # AppID non registrato fa apparire la notifica senza nome, e su alcune
  # configurazioni non la fa apparire affatto.
  $AppId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
  [void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
  [void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime]

  $xml = @"
<toast activationType="protocol" launch="$(Esc $uri)">
  <visual>
    <binding template="ToastGeneric">
      <text>$(Esc $titolo)</text>
      <text>$(Esc $riga2)</text>
      <text>$(Esc $riga3)</text>
    </binding>
  </visual>
</toast>
"@

  $doc = New-Object Windows.Data.Xml.Dom.XmlDocument
  $doc.LoadXml($xml)
  $toast = New-Object Windows.UI.Notifications.ToastNotification $doc
  [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($AppId).Show($toast)
}

try {
  # ---- il giro e' fallito -------------------------------------------------
  if ($Fail) {
    $t = "Form 4 - GIRO FALLITO"
    $r2 = $Fail
    $r3 = "il report di oggi non e' stato scritto"
    if ($Dry) { Write-Output $t; Write-Output $r2; Write-Output $r3; exit 0 }
    Mostra $t $r2 $r3 ""
    Write-Output ("notifica di guasto: " + $Fail)
    exit 0
  }

  if (-not $StateDir) {
    # tools/ sta dentro il repo: lo stato e' il fratello.
    $StateDir = Join-Path (Split-Path -Parent $PSScriptRoot) "state"
  }
  $json = Join-Path $StateDir "daily" | Join-Path -ChildPath "last_run.json"
  if (-not (Test-Path $json)) {
    Write-Output ("nessun esito in " + $json + " -- il giro non ha ancora scritto")
    exit 0
  }

  $d = Get-Content -Path $json -Raw -Encoding UTF8 | ConvertFrom-Json

  # ---- il testo, tre righe al massimo ------------------------------------
  $titolo = "Form 4 - " + $d.run_date

  $parti = @()
  if ($null -ne $d.new)               { $parti += ("" + $d.new + " nuovi") }
  if ($null -ne $d.repeat)            { $parti += ("" + $d.repeat + " gia visti") }
  if ($null -ne $d.issuers_evaluated) { $parti += ("" + $d.issuers_evaluated + " valutati") }
  $riga2 = $parti -join "  -  "

  $avvisi = @()
  if ($d.watch_hits -gt 0) {
    # La sorveglianza e' l'unica cosa che l'utente ha chiesto di guardare per
    # nome: se scatta, va davanti al resto.
    $avvisi += ("SORVEGLIANZA: " + $d.watch_hits)
  }
  $nonOsservati = @()
  if ($d.index_unreadable) { $nonOsservati = @($d.index_unreadable) }
  if ($nonOsservati.Count -eq 1) { $avvisi += "1 giorno non osservato" }
  elseif ($nonOsservati.Count -gt 1) { $avvisi += ("" + $nonOsservati.Count + " giorni non osservati") }
  if ($d.status -and $d.status -ne "ok") { $avvisi += ("stato: " + $d.status) }

  if ($avvisi.Count -gt 0) { $riga3 = $avvisi -join "  -  " }
  else {
    # Niente da segnalare: si mette il nome del file, che e' la cosa da aprire.
    if ($d.report) { $riga3 = Split-Path -Leaf $d.report } else { $riga3 = "" }
  }

  $uri = ""
  if ($d.report) { $uri = "file:///" + ($d.report -replace '\\', '/') }

  if ($Dry) {
    Write-Output $titolo
    Write-Output $riga2
    Write-Output $riga3
    Write-Output ("apre: " + $d.report)
    exit 0
  }

  Mostra $titolo $riga2 $riga3 $uri
  Write-Output ("notifica: " + $riga2)
  exit 0
}
catch {
  # Si dice cosa e' andato storto e si esce 0: vedi l'intestazione.
  Write-Output ("notifica non inviata: " + $_.Exception.Message)
  exit 0
}
