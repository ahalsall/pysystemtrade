"""READ-ONLY: how far back will IB serve the still-listed forward SOFR quarterly
contracts? The framework hardcodes a '1 Y' daily duration; here we ask for more to
see IB's true depth. Direct ib_async, no framework, nothing written.

Usage: uv run python -m sysinit.futures.ib_sofr_depth_probe
"""
from ib_async import IB, Future

PORT = 4002
CLIENTID = 77  # distinct from capture/stack
CONTRACTS = ["202609", "202612", "202703", "202709", "202803"]
DURATION = "6 Y"  # ask deep; IB returns whatever it has

ib = IB()
ib.connect("127.0.0.1", PORT, clientId=CLIENTID, timeout=15)
print(f"connected {PORT} clid {CLIENTID}\n")
print(f"{'contract':>10} | {'rows':>6} | {'first':>10} | {'last':>10}")
print("-" * 46)
for ym in CONTRACTS:
    c = Future(symbol="SOFR3", lastTradeDateOrContractMonth=ym,
               multiplier="2500", exchange="CME", currency="USD")
    try:
        [q] = ib.qualifyContracts(c)
    except Exception as e:
        print(f"{ym:>10} | qualify FAIL: {str(e)[:60]}"); continue
    bars = ib.reqHistoricalData(q, endDateTime="", durationStr=DURATION,
                                barSizeSetting="1 day", whatToShow="TRADES",
                                useRTH=False, formatDate=1)
    if not bars:
        print(f"{ym:>10} | {'0':>6} |  (no bars)"); continue
    print(f"{ym:>10} | {len(bars):>6} | {str(bars[0].date):>10} | {str(bars[-1].date):>10}")
ib.disconnect()
print("\n(read-only; nothing written)")
