import pandas as pd

token = "19742bb454fb9924b28de6ed1870846898de8d07"

raw_data = pd.read_json("https://api.tiingo.com/tiingo/crypto/prices?tickers=dogeusd&resampleFreq=1min&startDate=2018-08-01&token=" + token)
data1 = pd.DataFrame(raw_data['priceData'][0]).set_index('date')
data1.to_csv("./dogeusd_1m_a.csv")

raw_data = pd.read_json("https://api.tiingo.com/tiingo/crypto/prices?tickers=dogeusd&resampleFreq=1min&startDate=2018-08-03&token=" + token)
data2 = pd.DataFrame(raw_data['priceData'][0]).set_index('date')
data2.to_csv("./dogeusd_1m_b.csv")

data = pd.concat([data1, data2]).drop_duplicates()
data.to_csv("./dogeusd_1m.csv")
