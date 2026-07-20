# Runbook: automate the CSI Unfair Advantage daily download (Windows VM)

Goal: fetch CSI's EOD distribution automatically each day and export the per-contract CSVs to `Z:\`
(-> `private/data/futures/csi/UA/Data/PST/`), so the Linux `pst-rob-refresh` cycle ingests fresh data
with no manual step. See also csi_setup_guide.md, csi_data.md, and memory deployment-target.

## Key fact (verified 2026-07-20)
The UA **"easy-download" app does download + export to `Z:\` + current data in ONE shot** (case b): after
running it, the raw CSV mtimes jumped to today and the latest bar advanced to the prior trading day. So the
automation is simply **"launch the easy-download app on a schedule"** — no separate export step.

## 1. Windows auto-login (unattended tasks need a logged-in session)
- `netplwiz` -> uncheck "Users must enter a user name and password" -> enter the VM password.

## 2. Determine how the easy-download starts
Double-click the easy-download app: does it **start the download on its own** (-> 3A), or do you **click a
button** inside it (-> 3B)?

## 3A. SIMPLE — Task Scheduler launches the app (if it auto-runs on launch)
Task Scheduler -> Create Task:
- General: name "CSI daily download"; "Run only when user is logged on" (pairs with auto-login).
- Triggers (two): "At log on" (fires on boot/wake) AND "Daily" at ~6:30pm ET (after US settlements + CSI's
  evening distribution); optionally "Repeat every 3 hours for 1 day" so a missed window self-heals while awake.
- Actions: Start a program -> the easy-download .exe.
- Conditions: "Start only if network available"; "Wake the computer to run this task" (for the 24/7 server).

## 3B. If it needs a CLICK — AutoHotkey wrapper
Install AutoHotkey; save (adjust window title/button to the actual app), compile to .exe, point Task
Scheduler at the .exe:
    Run, "C:\Path\To\EasyDownload.exe"
    WinWait, Easy Download,, 30      ; exact window title
    Sleep, 1500
    ControlClick, Download, Easy Download   ; button text/control
    Sleep, 90000                     ; wait for the download to finish
    WinClose, Easy Download

## 4. Verify (from the Linux side)
After a scheduled run, files under private/data/futures/csi/UA/Data/PST/ get fresh mtimes and the latest bar
date advances. Quick check: `tail -1 .../ES_202812.csv | cut -d, -f1` should show the prior trading day.

## Timing
- On the LAPTOP (current): "At log on" is what matters — it fetches whenever the VM is awake. T-1 is fine, so
  it never needs to race the clock; a staleness monitor (to build) catches any missed day.
- On the 24/7 SERVER (planned): the daily ~6:30pm ET time becomes the reliable anchor; keep the VM awake and
  UA will refresh at each CSI distribution. Note UA is Windows-only, so the server still needs a Windows VM.

## Related open item
Build a Linux-side staleness monitor (wrap data_freshness_audit.py in a systemd timer, weekend-aware) that
alerts if the export/DB falls behind — the safety net for the laptop-suspend fragility.
