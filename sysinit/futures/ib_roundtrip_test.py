import sys
from ib_async import IB, ContFuture, MarketOrder
host="127.0.0.1"; port=4002; cid=5003
ib=IB(); ib.connect(host,port,clientId=cid,timeout=20)
print("connected:", ib.isConnected(), "| account:", ib.managedAccounts())
c=ContFuture("MES","CME","USD"); ib.qualifyContracts(c)
print("contract:", c.localSymbol)

def place_and_wait(action):
    tr=ib.placeOrder(c, MarketOrder(action,1))
    for _ in range(40):
        ib.sleep(0.5)
        if tr.orderStatus.status=="Filled": break
    ib.sleep(1.0)  # let commissionReport arrive
    return tr

def mes_pos():
    return [(p.position,p.avgCost) for p in ib.positions() if p.contract.symbol=="MES"]

buy=place_and_wait("BUY")
print(f"BUY  -> status={buy.orderStatus.status} filled={buy.orderStatus.filled} avgFillPrice={buy.orderStatus.avgFillPrice}")
print("  position after BUY:", mes_pos() or "flat")
sell=place_and_wait("SELL")
print(f"SELL -> status={sell.orderStatus.status} filled={sell.orderStatus.filled} avgFillPrice={sell.orderStatus.avgFillPrice}")
print("  position after SELL:", mes_pos() or "FLAT")

for tr,label in [(buy,"BUY"),(sell,"SELL")]:
    for f in tr.fills:
        cr=f.commissionReport
        print(f"  {label} fill: {f.execution.shares} @ {f.execution.price} | commission={getattr(cr,'commission',None)} {getattr(cr,'currency','')} | realizedPNL={getattr(cr,'realizedPNL',None)}")
ib.disconnect(); print("done")
