"""Standalone IB connectivity + price test (raw ib_async, no pysystemtrade deps).

Usage: ib_conn_test.py [host] [port] [clientId]
  paper Gateway default port 4002; live Gateway 4001.
Uses DELAYED market data (type 3) so it works without a live data subscription.
"""
import sys
from ib_async import IB, ContFuture

host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
port = int(sys.argv[2]) if len(sys.argv) > 2 else 4002
client_id = int(sys.argv[3]) if len(sys.argv) > 3 else 5001

ib = IB()
print(f"connecting to {host}:{port} clientId={client_id} ...")
ib.connect(host, port, clientId=client_id, timeout=20)
print("connected:", ib.isConnected(), "| server version:", ib.client.serverVersion())
print("managed accounts:", ib.managedAccounts())

ib.reqMarketDataType(3)  # 3 = delayed, 4 = delayed-frozen (no subscription needed)

# liquid micro E-mini S&P 500 continuous future on CME
contract = ContFuture("MES", "CME", "USD")
ib.qualifyContracts(contract)
print("qualified contract:", contract.localSymbol, contract.lastTradeDateOrContractMonth)

ticker = ib.reqMktData(contract, "", False, False)
ib.sleep(4)
print(f"PRICE  last={ticker.last}  close={ticker.close}  bid={ticker.bid}  ask={ticker.ask}")

ib.disconnect()
print("disconnected — test complete")
