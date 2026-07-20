# systemd --user units for the rob_dynamic paper/live schedule (mirror)

These are copies of the live units in `~/.config/systemd/user/` (source of truth for `systemctl --user`),
kept here for version control + portability to the future 24/7 server (see memory deployment-target).

Daily cycle (weekdays, UTC):
- **pst-rob-refresh** @ 00:20 UTC -> sysinit/futures/rob_daily_refresh.py:
  csi_sync --auto -> run_systems -> stack-hygiene (clear stale un-worked orders) -> order_gen.
  Persistent=true (catches up on wake). NOT broker-facing.
- **pst-rob-stackhandler** @ 00:30 UTC -> sysinit/futures/run_stack_handler_gated.sh:
  waits for today's refresh to finish + IB Gateway up, THEN execs sysproduction.run_stack_handler.
  The ONLY broker-facing component. Persistent=false (a late unattended start is worse than none).

To (re)install on a host:
  cp notes/systemd/pst-rob-*.{service,timer} ~/.config/systemd/user/
  systemctl --user daemon-reload
  systemctl --user enable --now pst-rob-refresh.timer pst-rob-stackhandler.timer
  loginctl enable-linger "$USER"   # so --user timers run without an active login (server)

Rerun the handler manually once Gateway is up (if it exited waiting):
  systemctl --user start pst-rob-stackhandler.service
