import argparse
import random
import py_vollib.black_scholes as bs
import py_vollib.black_scholes.implied_volatility as bsiv
import py_vollib.black_scholes.greeks.analytical as bsga
import py_vollib.black_scholes.greeks.numerical as bsgn
import time
import numpy as np
import collections as col

from client.exchange_service.client import BaseExchangeServerClient
from protos.order_book_pb2 import Order
from protos.service_pb2 import PlaceOrderResponse


class ExampleMarketMaker(BaseExchangeServerClient):
    """A simple market making bot - shows the basics of subscribing
    to market updates and sending orders"""
    

    def __init__(self, *args, **kwargs):
        BaseExchangeServerClient.__init__(self, *args, **kwargs)
        self.hist_mids = {"C98PHX":[], "C99PHX":[], "C100PHX":[], "C101PHX":[], "C102PHX":[], "P98PHX":[], "P99PHX":[], "P100PHX":[], "P101PHX":[], "P102PHX":[], "IDX#PHX":[]}
        self.hist_vwmids = {"C98PHX":[], "C99PHX":[], "C100PHX":[], "C101PHX":[], "C102PHX":[], "P98PHX":[], "P99PHX":[], "P100PHX":[], "P101PHX":[], "P102PHX":[], "IDX#PHX":[]}
        self.theo_mids = {"C98PHX":100.0, "C99PHX":100.0, "C100PHX":100.0, "C101PHX":100.0, "C102PHX":100.0, "P98PHX":100.0, "P99PHX":100.0, "P100PHX":100.0, "P101PHX":100.0, "P102PHX":100.0, "IDX#PHX":100.0}
        self.theo_deltas = {"C98PHX": 0.0, "C99PHX": 0.0, "C100PHX": 0.0, "C101PHX": 0.0, "C102PHX": 0.0, "P98PHX": 0.0, "P99PHX": 0.0, "P100PHX": 0.0, "P101PHX": 0.0, "P102PHX": 0.0, "IDX#PHX": 0.0}
        self.theo_vegas = {"C98PHX": 0.0, "C99PHX": 0.0, "C100PHX": 0.0, "C101PHX": 0.0, "C102PHX": 0.0, "P98PHX": 0.0, "P99PHX": 0.0, "P100PHX": 0.0, "P101PHX": 0.0, "P102PHX": 0.0, "IDX#PHX": 0.0}
        self._orderids = set([])
        self.start_time = time.time()
        self.exposure_counter = col.Counter()
        self.delta_exposure = 0.0
        self.vega_exposure = 0.0
        self.strike_dict = {"C98PHX": 98, "C99PHX": 99, "C100PHX": 100, "C101PHX": 101, "C102PHX": 102, "P98PHX": 98, "P99PHX": 0.0, "P100PHX": 99, "P101PHX": 101, "P102PHX": 102,"IDX#PHX": 0.0}
        self.careful = False

    def _make_order(self, asset_code, quantity, base_price, spread, bid=True):
        return Order(asset_code = asset_code, quantity=quantity if bid else -1*quantity,
                     order_type = Order.ORDER_LMT,
                     price = base_price-spread/2 if bid else base_price+spread/2,
                     competitor_identifier = self._comp_id)

    def handle_exchange_update(self, exchange_update_response):
        print("exposure: " + str(abs(sum(self.exposure_counter.values()))))
        print(exchange_update_response.competitor_metadata)
        if exchange_update_response.competitor_metadata.pnl > 0:
            p = np.power((1/exchange_update_response.competitor_metadata.pnl),1/3)
        else:
            p = 0
        for fill in self.latest_fills:
            if self.exposure_counter[fill.order.order_id] > 0:
                self.exposure_counter[fill.order.order_id] = fill.remaining_quantity
            else:
                self.exposure_counter[fill.order.order_id] = -fill.remaining_quantity
        for market_update in exchange_update_response.market_updates:
            asset = market_update.asset.asset_code
            mid = market_update.mid_market_price
            K = self.strike_dict[asset]
            if (sum(b.size for b in market_update.bids) + sum(a.size for a in market_update.asks)) != 0:
                vwmid = (sum((b.price +K)* b.size for b in market_update.bids) + sum((a.price+K) * a.size for a in market_update.asks))/(sum(b.size for b in market_update.bids) + sum(a.size for a in market_update.asks)) 
            else:
                vwmid = mid
            if len(self.hist_mids[asset]) == 10:
                self.hist_mids[asset].append(p*mid+(1-p)*vwmid)
                self.hist_mids[asset].pop(0)
            else:
                self.hist_mids[asset].append(p*mid+(1-p)*vwmid)
        # place a bid and an ask for each asset
        for i, asset_code in enumerate(["C98PHX", "P98PHX", "C99PHX", "P99PHX", "C100PHX", "P100PHX", "C101PHX", "P101PHX", "C102PHX", "P102PHX"]):
            S = self.hist_mids['IDX#PHX'][-1]
            if i%2 == 0:
                flag = 'c'
            else:
                flag = 'p'
            K = 100 + (int(i/2)-2)
            r = 0.0
            t = (2700 - (time.time() - self.start_time))/10800
            if len(self.hist_mids['IDX#PHX']) > 1:
                sigma = (self.hist_mids['IDX#PHX'][-2] - S)/S
            else:
                #sigma = bsiv.implied_volatility(self.hist_mids[asset_code][-1], S, K, t, r, flag)
                sigma = 0.002
            theo_mid = bs.black_scholes(flag, S, K, t, r, sigma)
            self.theo_mids[asset_code] = theo_mid
            self.theo_deltas[asset_code] = bsga.delta(flag, S, K, t, r, sigma)
            self.theo_vegas[asset_code] = bsga.vega(flag, S, K, t, r, sigma)
            if theo_mid + K > S and abs(sum(self.exposure_counter.values())) < 3000:
                spread = 0.02
                if self.theo_deltas[asset_code] != 0:
                    bid_resp = self.place_order(self._make_order(asset_code, 100,
                                                                 round(self.hist_mids[asset_code][-1]), spread, False))
                    ask_resp = self.place_order(self._make_order('IDX#PHX', int(self.theo_deltas[asset_code] * 100),
                                                                 round(S), spread, flag == 'c'))
                    if type(bid_resp) != PlaceOrderResponse:
                        print(bid_resp)
                    else:
                        self._orderids.add(bid_resp.order_id)
                        if flag == 'c':
                            self.exposure_counter[bid_resp.order_id] = -100
                        else:
                            self.exposure_counter[bid_resp.order_id] = 100
        
                    if type(ask_resp) != PlaceOrderResponse:
                        print(ask_resp)
                    else:
                        self._orderids.add(ask_resp.order_id)
                        if flag == 'c':
                            self.exposure_counter[ask_resp.order_id] = int(self.theo_deltas[asset_code] * 100)
                        else:
                            self.exposure_counter[ask_resp.order_id] = -int(self.theo_deltas[asset_code] * 100)
            #calculating exposure
            while (abs(sum(self.exposure_counter.values())) > 3000):
                cancel = self._orderids.pop()
                del self.exposure_counter[cancel]
        
            '''
            quantity = random.randrange(1, 10)
            base_price = random.randrange((i + 1) * 100, (i+1) * 150)
            spread = random.randrange(5, 10)

            bid_resp = self.place_order(self._make_order(asset_code, quantity,
                base_price, spread, True))
            ask_resp = self.place_order(self._make_order(asset_code, quantity,
                base_price, spread, False))

            if type(bid_resp) != PlaceOrderResponse:
                print(bid_resp)
            else:
                self._orderids.add(bid_resp.order_id)

            if type(ask_resp) != PlaceOrderResponse:
                print(ask_resp)
            else:
                self._orderids.add(ask_resp.order_id)
            '''

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
