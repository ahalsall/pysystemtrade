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

## Concrete setup (DECIDED 2026-07-01, this host) — KVM/QEMU
Host is ready: Intel VT-x, /dev/kvm live, andrew in libvirt+kvm groups, default NAT
net active (gateway **192.168.122.1** = how the guest reaches host Samba), 93GiB RAM /
22 cores / 1.5TB free. virtio-win 0.1.285 ISO downloaded to `~/VMs/iso/virtio-win.iso`.
Chosen: **KVM + Samba(force user=csi) + headless autostart** (see instrument work notes).

1. ISOs → system pool (qemu:///system can't read /home): download Win11 ISO from
   microsoft.com/software-download/windows11 → `~/VMs/iso/Win11.iso`, then
   `sudo mv ~/VMs/iso/{Win11.iso,virtio-win.iso} /var/lib/libvirt/images/`.
2. `sudo apt install -y ovmf swtpm swtpm-tools samba` (UEFI+TPM for Win11).
3. Samba: share snippet is at `~/VMs/csi_share.smb.conf` (path=csi landing dir,
   force user/group=csi, valid users=andrew). `sudo tee -a /etc/samba/smb.conf < ~/VMs/csi_share.smb.conf`;
   `sudo smbpasswd -a andrew`; `testparm`; `sudo systemctl restart smbd`; if ufw active
   `sudo ufw allow in on virbr0 to any port 445 proto tcp`.
4. Create VM (opens virt-viewer for the install):
   `virt-install --name win11-csi --osinfo win11 --memory 8192 --vcpus 4 --cpu host-passthrough
   --disk path=/var/lib/libvirt/images/win11-csi.qcow2,size=64,bus=virtio,format=qcow2
   --disk path=/var/lib/libvirt/images/virtio-win.iso,device=cdrom --cdrom /var/lib/libvirt/images/Win11.iso
   --network network=default,model=virtio --boot uefi --tpm emulator,model=tpm-crb,version=2.0
   --graphics spice --video qxl --sound none`
5. Win install: at empty disk step → Load driver → virtio CD `amd64\w11` → viostor. Skip MS
   account via Shift+F10 `oobe\bypassnro` (or detach NIC temporarily).
6. Guest: run `virtio-win-guest-tools.exe` from the virtio CD (net/balloon/spice). Map drive
   `\\192.168.122.1\csi` as Z: (user andrew + samba pw, reconnect at sign-in). Install UA →
   ASCII export `Time,Open,High,Low,Close,Volume`, files `<SYM>_<YYYYMM>.csv` → Z:\, daily.
7. Headless: `virsh autostart win11-csi`; Windows auto-login (netplwiz) + UA in Task Scheduler.

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
