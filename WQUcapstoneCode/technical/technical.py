import pandas as pd
import numpy as np
import datetime as dt

# import visual tools
import matplotlib as mpl
import matplotlib.pyplot as plt
import seaborn as sns

# Default Indicator class 
class _Indicator:

    def __call__(self, *args, **kwargs):
        return self.data

    def _switch(self):
        self.switch_up = self._get_up_cross(self.data)
        self.switch_down = self._get_down_cross(self.data)
        up = pd.Series(1, index=self.switch_up.index)
        down = pd.Series(-1, index=self.switch_down.index)
        self.data['side'] = pd.concat([up , down])
        self.data['side'] = self.data['side'].ffill()

    @staticmethod
    def _get_up_cross(df):
        raise ValueError('Please implement this class in child classes')

    @staticmethod
    def _get_down_cross(df):
        raise ValueError('Please implement this class in child classes')


class wr(_Indicator):
    '''William %R'''
    '''Here we adopt the standard William % R setup when the indicators just goes below 20% or goes above 80% '''

    def __init__(self, close, window = 14):
        self.data = pd.DataFrame({'price': close})
        low = close.rolling(window).min()
        high = close.rolling(window).max()
        self.data['wr'] = 100 * ((high - close) / (high - low))
        self._switch()

    @staticmethod
    def _get_down_cross(df):
        crit1 = df['wr'].shift(1) < 80
        crit2 = df['wr'] > 80
        return df.price[(crit1) & (crit2)]

    @staticmethod
    def _get_up_cross(df):
        crit1 = df['wr'].shift(1) > 20
        crit2 = df['wr'] < 20
        return df.price[(crit1) & (crit2)]


class EMA(_Indicator):
    '''Exponentially weighted moving average with slow MA(7) and faster MA(3)'''

    def __init__(self, close, fast_ma=3, slow_ma=7):
        self.data = pd.DataFrame({'price': close,
                                 'fast': close.ewm(fast_ma).mean(),
                                 'slow': close.ewm(slow_ma).mean()})
        self._switch()

    @staticmethod
    def _get_up_cross(df):
        crit1 = df.fast.shift(1) < df.slow.shift(1)
        crit2 = df.fast > df.slow
        return df.fast[(crit1) & (crit2)]

    @staticmethod
    def _get_down_cross(df):
        crit1 = df.fast.shift(1) > df.slow.shift(1)
        crit2 = df.fast < df.slow
        return df.fast[(crit1) & (crit2)]


class BollingerBands(_Indicator):
    
    '''BollingerBanks with standard 20-period window and 2 st.d.'''

    def __init__(self, close, window=20, numsd=2):
        self._calc_bbands(close, window, numsd)
        self._switch()

    def _calc_bbands(self, close, window=None, numsd=None):
        """ returns average, upper band, and lower band"""
        avg = close.rolling(window).mean()
        sd = close.rolling(window).std(ddof=0)
        upband = avg + (sd * numsd)
        dnband = avg - (sd * numsd)
        self.data = pd.DataFrame({'price': close,
                                  'average': avg,
                                  'upper_band': upband,
                                  'lower_band': dnband,
                                  'standard_deviation': sd
                                  })

    @staticmethod
    def _get_down_cross(df):
        crit1 = df.price.shift(1) < df.upper_band.shift(1)
        crit2 = df.price > df.upper_band
        return df.price[(crit1) & (crit2)]

    @staticmethod
    def _get_up_cross(df):
        crit1 = df.price.shift(1) > df.lower_band.shift(1)
        crit2 = df.price < df.lower_band
        return df.price[(crit1) & (crit2)]

class CCI:
    '''Commodity Channel Index with standard 20-period window and 0.015 divisor '''
    '''Here we do a modification by replacing typical price as the average of high, low and close price with closs price only '''
    def __init__(self, close, window=20):
        MA = close.rolling(window).mean()
        MeanDeviation = np.abs(close - MA).rolling(window).mean()
        self.data = pd.DataFrame({'price': close,
                                  'CCI': pd.Series((close - MA) / (0.015 * MeanDeviation))
                                  })
    def __call__(self, *args, **kwargs):
        return self.data

class Stochastic(_Indicator):
    '''Stochastic Oscillator with standard 20-period window, and overbought and oversell signal as 80 and 20'''
    def __init__(self, close, window=20, stoch_window=3):
        self.data = pd.DataFrame({'price': close})
        low = close.rolling(window).min()
        high = close.rolling(window).max()
        self.data['%K'] = 100 * ((close - low) / (high - low))
        self.data['%D'] = self.data['%K'].rolling(stoch_window).mean()
        self._switch()

    @staticmethod
    def _get_down_cross(df):
        crit1 = df['%K']>80
        crit2 = df['%D'].shift(1) > df['%K'].shift(1)
        crit3 = df['%D'] < df['%K']
        return df.price[(crit1) & (crit2) & (crit3)]

    @staticmethod
    def _get_up_cross(df):
        crit1 = df['%K'] < 20
        crit2 = df['%D'].shift(1) < df['%K'].shift(1)
        crit3 = df['%D'] > df['%K']
        return df.price[(crit1) & (crit2) & (crit3)]


class Ichimoku(_Indicator):
    '''Ichimoku Kinko Hyo standard setup for 9-period tenka_sen_window, 26-period kijun_sen_window and 52-period senkou_window'''
    def __init__(self, close, tenka_sen_window=9, kijun_sen_window=26, senkou_window=52):
        self.data = pd.DataFrame({'price': close})

        self.data['tenka_sen'] = self._sen(close, tenka_sen_window)
        self.data['kijun_sen'] = self._sen(close, kijun_sen_window)

        # Senkou Span A (Leading Span A): (Conversion Line + Base Line)/2))
        self.data['senkou_span_a'] = ((self.data['tenka_sen'] + self.data['kijun_sen']) / 2).shift(kijun_sen_window)

        # Senkou Span B (Leading Span B): (52-period high + 52-period low)/2))
        self.data['senkou_span_b'] = self._sen(close, senkou_window).shift(kijun_sen_window)

        # Chikou_span as last 26-period price
        self.data['chikou_span'] = self.data['price'].shift(26)

        self._switch()

        a = self.data['senkou_span_a'] < self.data.price
        b = self.data.price < self.data['senkou_span_b']
        # if between clouds, the direction is uncertain
        self.data.loc[(a & b) | ((~a) & (~b)),'side'] = 0

    @staticmethod
    def _sen(ds, window):
        period_high = ds.rolling(window).max()
        period_low = ds.rolling(window).min()
        return (period_high + period_low) / 2

    @staticmethod
    def _get_up_cross(df):
        crit1 = df['senkou_span_a'].shift(1) < df['senkou_span_b'].shift(1)
        crit2 = df['senkou_span_a'] > df['senkou_span_b']
        return df.price[(crit1) & (crit2)]

    @staticmethod
    def _get_down_cross(df):
        crit1 = df['senkou_span_a'].shift(1) > df['senkou_span_b'].shift(1)
        crit2 = df['senkou_span_a'] < df['senkou_span_b']
        return df.price[(crit1) & (crit2)]


class RSI(_Indicator):
    '''Relative Strength Index (using EMA) with standard setup of 14-period window, overbought and oversell signal of 70 and 30 '''
    def __init__(self, close, window=14):
        self.data = pd.DataFrame({'price': close})

        rtn = close.diff()
        up, down = rtn.copy(), rtn.copy()
        up[up < 0] = 0
        down[down > 0] = 0

        # Calculate the EWMA
        roll_up1 = up.ewm(span=window).mean()
        roll_down1 = down.abs().ewm(span=window).mean()

        # Calculate the RSI based on EWMA
        RS1 = roll_up1 / roll_down1
        self.data['RSI'] = 100.0 - (100.0 / (1.0 + RS1))
        self._switch()

        self.data.loc[(self.data.RSI > 30) & (self.data.RSI< 70), 'side'] = 0

    @staticmethod
    def _get_down_cross(df):
        crit1 = df['RSI'].shift(1) < 70
        crit2 = df['RSI'] > 70
        return df.price[(crit1) & (crit2)]

    @staticmethod
    def _get_up_cross(df):
        crit1 = df['RSI'].shift(1) > 30
        crit2 = df['RSI'] < 30
        return df.price[(crit1) & (crit2)]

# Plot helper functions
def plot_indicator(indicator, from_date = None):
    if from_date is None: from_date = indicator.index[0]
    f, ax = plt.subplots()#figsize=(11, 8))
    cols = [col for col in indicator.data.columns if col not in ['side','standard_deviation','%K','%D', 'wr','RSI']]
    indicator.data[cols].loc[from_date:].plot(ax=ax, alpha=.5)
    indicator.switch_up.loc[from_date:].plot(ax=ax, ls='', marker='^', markersize=7,
                                       alpha=0.75, label='buy', color='g')
    indicator.switch_down.loc[from_date:].plot(ax=ax, ls='', marker='v', markersize=7,
                                         alpha=0.75, label='sell', color='r')
    ax.legend()

# rolling correlation function with rolling 20-period window with 1 day lag
def rolling_autocorr(px, window=20, lag=1):
    return pd.Series(px
    .rolling(window=window, min_periods=window, center=False)
    .apply(lambda x: x.autocorr(lag=lag), raw=False), name = f'Autocor_{lag}_lag')


