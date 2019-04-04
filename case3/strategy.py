import numpy as np
import pickle


def load_object(file_name):
    """load the pickled object"""
    with open(file_name, 'rb') as f:
        return pickle.load(f)


def view_data(data_path):
    data = load_object(data_path)
    prices = data['prices']
    names = data['features']['names']
    features = data['features']['values']
    print(prices.shape)
    print(names)
    print(features.shape)
    return prices, features


class Strategy():
    def __init__(self):
        pass

    def handle_update(self, inx, price, factors):
        B = factors[:,[5,7,8,9]]
        f_cov = np.load('/Users/phillipseo/Docs/trading_platform/MWTC19Submit-master/case3/data/f_cov.npy')
        d_cov = np.load('/Users/phillipseo/Docs/trading_platform/MWTC19Submit-master/case3/data/d_cov.npy')
        mu_e = np.load('/Users/phillipseo/Docs/trading_platform/MWTC19Submit-master/case3/data/mu_e.npy')
        r_cov = np.add(np.matmul(np.matmul(B,f_cov),np.transpose(B)),d_cov) 
        r_cov_inv = np.linalg.inv(r_cov)
        one = np.repeat(1, r_cov.shape[0])
        denom_tan = np.matmul(np.matmul(np.transpose(one),r_cov_inv),mu_e)
        denom_gmv = np.matmul(np.matmul(np.transpose(one),r_cov_inv),one)
        w_gmv  = (1/denom_gmv) * np.matmul(r_cov_inv, one)
        w_tan = (1/denom_tan) * np.matmul(r_cov_inv, mu_e)
        w = np.add(1.1*w_gmv,(1-1.1)*w_tan)
        assert price.shape[0] == factors.shape[0]
        return w
