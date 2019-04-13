import argparse
import random
import numpy as np
import pandas as pd
import collections as col

from client.exchange_service.client import BaseExchangeServerClient
from protos.order_book_pb2 import Order
from protos.service_pb2 import PlaceOrderResponse


class ExampleMarketMaker(BaseExchangeServerClient):
    index = 0
    """A simple market making bot - shows the basics of subscribing
    to market updates and sending orders"""

    def __init__(self, *args, **kwargs):
        BaseExchangeServerClient.__init__(self, *args, **kwargs)
        self.hist_mids = {'K':[], 'M':[], 'N':[], 'Q':[], 'U':[],'V':[]}
        self.diff_series = {'1':[],'2':[],'3':[],'4':[],'5':[]}
        self._orderids = set([])
        self.long = False

    def _make_order(self, asset_code, quantity, base_price, spread, bid=True):
        return Order(asset_code = asset_code, quantity=quantity if bid else -1*quantity,
                     order_type = Order.ORDER_LMT,
                     price = np.round(base_price-spread/2,2) if bid else np.round(base_price+spread/2,2),
                     competitor_identifier = self._comp_id)

    def handle_exchange_update(self, exchange_update_response):
        print(exchange_update_response.competitor_metadata)
        for fill in self.latest_fills:
            if self.exposure_counter[fill.order.order_id] > 0:
                self.exposure_counter[fill.order.order_id] = fill.remaining_quantity
            else:
                self.exposure_counter[fill.order.order_id] = -fill.remaining_quantity
        print("number of orders: " + str(len(self._orderids)))
        print("long?: " + str(self.long))
        # 10% of the time, cancel two arbitrary orders
        for market_update in exchange_update_response.market_updates:
            asset = market_update.asset.asset_code
            mid = market_update.mid_market_price
            if len(self.hist_mids[asset]) == 20:
                self.hist_mids[asset].append(mid)
                self.hist_mids[asset].pop(0)
            else:
                self.hist_mids[asset].append(mid)
        self.diff_series['1'] = [a - b for a, b in zip(self.hist_mids['K'], self.hist_mids['M'])]
        self.diff_series['2'] = [a - b for a, b in zip(self.hist_mids['M'], self.hist_mids['N'])]
        self.diff_series['3'] = [a - b for a, b in zip(self.hist_mids['N'], self.hist_mids['Q'])]
        self.diff_series['4'] = [a - b for a, b in zip(self.hist_mids['Q'], self.hist_mids['U'])]
        self.diff_series['5'] = [a - b for a, b in zip(self.hist_mids['U'], self.hist_mids['V'])]
        
        # place a bid and an ask for each asset
        #for i, asset_code in enumerate(["K", "M", "N", "Q", "U", "V"]):
        q1 = 100
        q2 = 20
        n_price = self.hist_mids['N'][-1]
        m_price = self.hist_mids['M'][-1]
        spread = 0.02
        order_in = False
        if self.diff_series['2'][-1]-self.diff_series['2'][0] < -0.03 and not self.long:
            n_resp = self.place_order(self._make_order('N', q1,\
            n_price, spread, True))
            m_resp = self.place_order(self._make_order('M', q2,\
                                                    m_price, spread, False))
            order_in = True
            self.long = True
            action = "LONG N"
            print("LONG N")
        elif self.diff_series['2'][-1]-self.diff_series['2'][0] > 0.03 and self.long:
            n_resp = self.place_order(self._make_order('N', q1,\
            n_price, spread, False))
            m_resp = self.place_order(self._make_order('M', q2,\
                                               m_price, spread, True))
            order_in = True
            self.long = False
            print("SHORT N")
            action = "SHORT N"
        if order_in:
            if type(n_resp) != PlaceOrderResponse:
                print(n_resp)
            else:
                self._orderids.add(bid_resp.order_id)
            if action == "LONG N":
                    self.exposure_counter[n_resp.order_id] = q1
                else:
                    self.exposure_counter[n_resp.order_id] = -q1
            if type(m_resp) != PlaceOrderResponse:
                print(m_resp)
            else:
                self._orderids.add(m_resp.order_id)
                if action == "LONG N":
                    self.exposure_counter[m_resp.order_id] = -q2
                else:
                    self.exposure_counter[m_resp.order_id] = q2
        while (abs(sum(self.exposure_counter.values())) > 40):
            cancel = self._orderids.pop()
            del self.exposure_counter[cancel]
        ExampleMarketMaker.index+=1
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run the exchange client')
    parser.add_argument("--server_host", type=str, default="localhost")
    parser.add_argument("--server_port", type=str, default="50052")
    parser.add_argument("--client_id", type=str)
    parser.add_argument("--client_private_key", type=str)
    parser.add_argument("--websocket_port", type=int, default=5678)

    args = parser.parse_args()
    host, port, client_id, client_pk, websocket_port = (args.server_host, args.server_port,
                                        args.client_id, args.client_private_key,
                                        args.websocket_port)

    client = ExampleMarketMaker(host, port, client_id, client_pk, websocket_port)
    client.start_updates()
