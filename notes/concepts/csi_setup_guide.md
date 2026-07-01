# CSI Data setup: Windows VM + shared folder → our pipeline

Goal: run CSI's **Unfair Advantage** (Windows-only) in a VM, auto-export per-contract
EOD CSVs to a folder shared with this Linux box, and have our `csi_pipeline` ingest
them → deep-history parquet/mongo for backtesting. See also `notes/concepts/csi_data.md`.

## Architecture
```
[Windows VM: Unfair Advantage] --export ASCII CSVs--> [shared folder]
        == /home/andrew/pysystemtrade/private/data/futures/csi  (owned by `csi` user, read-only to andrew)
                              |
                              v
   csi_pipeline --rename  (andrew reads raw, stages renamed Day_<PST>_<YYYYMM00>.csv)
        --> private/data/futures/csi_ingest  (andrew-writable)
                              |
                              v
   csi_pipeline --instruments ...  -> per-contract prices -> roll cal -> multiple -> adjusted (DB)
```
Note the **permission model** (already set up here): raw CSI lands in the `csi`-user-owned
`private/data/futures/csi/`; our pipeline (andrew) reads it and STAGES renamed files into
`private/data/futures/csi_ingest/` (andrew-owned). Keeps the CSI feed and our processing cleanly separated.

## 1. Windows VM on Linux
Two solid options:
- **KVM/QEMU + virt-manager** (native to Linux, best performance). Install: `sudo apt install qemu-kvm libvirt-daemon-system virt-manager`. Create a Windows 10/11 VM.
- **VirtualBox** (simpler shared-folder UX): `sudo apt install virtualbox`.
Give it ~4GB RAM, ~40GB disk. Unfair Advantage is light; a minimal Windows install is fine.

## 2. Shared folder (VM → Linux)
Make the VM write exports to a Linux folder. Options:
- **virtiofs / 9p (KVM):** in virt-manager add a Filesystem device, source = the Linux target dir, mount in Windows.
- **VirtualBox shared folder:** VM Settings → Shared Folders → add the Linux dir, auto-mount; appears as a drive in Windows.
- **Samba/CIFS (most robust, works with any hypervisor):** run Samba on Linux exporting the target dir; map it as a network drive in Windows. This is the recommended, decoupled approach.
Target the share at the `csi`-owned raw dir (or any dir; then point `csi_pipeline --export-dir` at it).

## 3. Unfair Advantage export config
- Install UA in the VM; log in with the CSI account.
- Build a **portfolio** of the instruments we trade (map PST codes → CSI symbols; extend `CSI_SYMBOL_MAP` in csi_pipeline.py).
- Set an **ASCII export** with layout `Date,Open,High,Low,Close,Volume` (our `CSI_CONFIG` expects `Time,Open,High,Low,Close,Volume` with ISO timestamps — match the header, or adjust CSI_CONFIG's `input_date_index_name`/`input_date_format` to UA's actual output).
- Per-contract files named `<CSISYM>_<YYYYMM>.csv` (UA delivery-month naming) into the shared folder.
- Enable **auto-refresh / scheduled export** so UA updates daily (UA is designed to be run once/day by a scheduler). Optionally use UA's OLE/COM "API2" (Python via win32com) for finer control.

## 4. Linux-side ingest (our code: sysinit/futures/csi_pipeline.py)
```
# stage raw CSI exports -> renamed Day_ files (andrew-writable), then process:
uv run python -m sysinit.futures.csi_pipeline --export-dir private.data.futures.csi --rename
uv run python -m sysinit.futures.csi_pipeline --instruments AEX,ALUMINIUM,...
```
- `--rename` maps `<CSISYM>_<YYYYMM>.csv` → `Day_<PST>_<YYYYMM00>.csv` via `CSI_SYMBOL_MAP` into `private/data/futures/csi_ingest/`.
- processing reuses the split-freq loader (CSI_CONFIG: FINAL="Close") + roll/multiple/adjusted stages.
- Later: a nightly cron mirroring the barchart build-out (respecting the `barchart_process_exclude` separation so pipelines don't collide).

## Validated (2026-07-01)
Rename + CSI_CONFIG parse verified on sample data: `AE_202411.csv`→`Day_AEX_20241100.csv`, AEX Dec-2024 contract parsed 259 daily rows back to 2023-12. Ingestion path works; CSI's real depth is decades.

## TODO to go live with CSI
1. Build the full **CSI_SYMBOL_MAP** (CSI symbol → exact PST code) for our universe — from CSI/UA's symbol list; verify spellings (e.g. ALUMINIUM not ALUMINUM).
2. Confirm UA's actual export **header/date format** and reconcile with CSI_CONFIG.
3. Decide the shared-folder mechanism (Samba recommended) + auto-export schedule.
4. Backfill deep history for the seasonals (CORN/WHEAT/CRUDE_W/SOYBEAN) → fixes the roll-calendar sparse-data problem so they trade correctly.
5. Verify first-notice/delivery handling once deep data enables proper roll calendars.
