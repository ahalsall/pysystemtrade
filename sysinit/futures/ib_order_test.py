"""IB paper ORDER test (raw ib_async): submit a far-from-market limit, confirm
it's working, then cancel it. No position is taken (the limit won't fill).

Requires Read-Only API to be DISABLED in Gateway.
Usage: ib_order_test.py [host] [port] [clientId]   (paper port 4002)
"""
import sys
from ib_async import IB, ContFuture, LimitOrder

host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
port = int(sys.argv[2]) if len(sys.argv) > 2 else 4002
client_id = int(sys.argv[3]) if len(sys.argv) > 3 else 5002

ib = IB()
ib.connect(host, port, clientId=client_id, timeout=20)
print("connected:", ib.isConnected(), "| account:", ib.managedAccounts())

c = ContFuture("MES", "CME", "USD")
ib.qualifyContracts(c)
ib.reqMarketDataType(3)
tk = ib.reqMktData(c, "", False, False)
ib.sleep(3)
ref = tk.last or tk.close or tk.ask
print(f"MES ({c.localSymbol}) ref price: {ref}")

# limit 30% BELOW market, rounded to 0.25 tick -> will NOT fill
limit = round((ref * 0.70) / 0.25) * 0.25
order = LimitOrder("BUY", 1, limit)
print(f"placing BUY 1 MES LIMIT @ {limit} (far below market, should rest unfilled)")
trade = ib.placeOrder(c, order)
ib.sleep(4)
print("  status after submit:", trade.orderStatus.status, "| active:", trade.isActive())
if trade.orderStatus.status == "Inactive" or any("Read-Only" in str(l.message) for l in trade.log):
    print("  !! looks like Read-Only API is still ON — disable it in Gateway")

print("cancelling order...")
ib.cancelOrder(order)
ib.sleep(3)
print("  status after cancel:", trade.orderStatus.status)
print("  order log:", [f"{e.status}:{e.message}" for e in trade.log][-4:])

# confirm we hold no MES position
pos = [p for p in ib.positions() if p.contract.symbol == "MES"]
print("MES positions held:", pos if pos else "none (flat)")
ib.disconnect()
print("done")
