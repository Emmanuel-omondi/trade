#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif
#include <stdlib.h>
#include <math.h>

static double mean(const double *arr, int n){
    if(n<=0) return 0.0;
    double s=0.0; for(int i=0;i<n;i++) s+=arr[i]; return s/n;
}

static double stddev(const double *arr, int n){
    if(n<=1) return 0.0;
    double m=mean(arr,n); double s=0.0; for(int i=0;i<n;i++){double d=arr[i]-m; s+=d*d;} return sqrt(s/(n-1));
}

EXPORT void compute_rsi(const double *close, int n, int period, double *out){
    if(n<=period){*out = NAN; return;}
    double gains=0, losses=0;
    for(int i=1;i<=period;i++){double d = close[n-i] - close[n-i-1]; if(d>0) gains+=d; else losses-=d;}
    double avg_gain = gains/period; double avg_loss = losses/period;
    double rs = avg_loss==0? (avg_gain>0?1e6:0.0) : avg_gain/avg_loss;
    *out = 100.0 - (100.0/(1.0+rs));
}

EXPORT void compute_macd(const double *close, int n, double *macd_out, double *signal_out, double *hist_out){
    int fast=12, slow=26, signal=9;
    if(n<slow){*macd_out = NAN; *signal_out = NAN; *hist_out = NAN; return;}
    double fast_ma=0, slow_ma=0;
    for(int i=0;i<fast;i++) fast_ma += close[n-1-i]; fast_ma /= fast;
    for(int i=0;i<slow;i++) slow_ma += close[n-1-i]; slow_ma /= slow;
    double macd = fast_ma - slow_ma;
    double sig = macd; *macd_out = macd; *signal_out = sig; *hist_out = macd - sig;
}

EXPORT void compute_atr(const double *high, const double *low, const double *close, int n, int period, double *out){
    if(n<=period){*out = NAN; return;}
    double tr_sum=0;
    for(int i=n-period;i<n;i++){
        double tr1 = high[i]-low[i];
        double tr2 = fabs(high[i] - close[i-1]);
        double tr3 = fabs(low[i] - close[i-1]);
        double tr = tr1; if(tr2>tr) tr=tr2; if(tr3>tr) tr=tr3; tr_sum += tr;
    }
    *out = tr_sum/period;
}

EXPORT void compute_bollinger(const double *close, int n, int period, double stddev_mul, double *upper, double *middle, double *lower){
    if(n<period){*upper = NAN; *middle = NAN; *lower = NAN; return;}
    double sum=0.0; for(int i=n-period;i<n;i++) sum+=close[i]; double m = sum/period;
    double s=0.0; for(int i=n-period;i<n;i++){ double d = close[i]-m; s += d*d; } double sd = sqrt(s/period);
    *middle = m; *upper = m + stddev_mul * sd; *lower = m - stddev_mul * sd;
}

EXPORT void compute_obv(const double *close, const double *volume, int n, double *out){
    if(n<1){*out = 0; return;}
    double obv = volume[0];
    for(int i=1;i<n;i++){
        if(close[i] > close[i-1]) obv += volume[i];
        else if(close[i] < close[i-1]) obv -= volume[i];
    }
    *out = obv;
}

EXPORT int compute_features(const double *high, const double *low, const double *close, const double *volume, int n, double *out_features, int out_len){
    if(n<=0 || out_len < 12) return -1;
    double rsi14; compute_rsi(close,n,14,&rsi14);
    double rsi7; compute_rsi(close,n,7,&rsi7);
    double macd, signal, hist; compute_macd(close,n,&macd,&signal,&hist);
    double atr14; compute_atr(high,low,close,n,14,&atr14);
    double atr20; compute_atr(high,low,close,n,20,&atr20);
    double upper, middle, lower; compute_bollinger(close,n,20,2.0,&upper,&middle,&lower);
    double obv; compute_obv(close,volume,n,&obv);
    double vol = stddev(close + (n>20? n-20:0), n>20?20:n);
    double ma20 = 0, ma50 = 0, ma200 = 0;
    int use20 = n>20?20:n; for(int i=n-use20;i<n;i++) ma20 += close[i]; ma20 /= use20;
    int use50 = n>50?50:n; for(int i=n-use50;i<n;i++) ma50 += close[i]; ma50 /= use50;
    int use200 = n>200?200:n; for(int i=n-use200;i<n;i++) ma200 += close[i]; ma200 /= use200;
    double direction = n>1 ? (close[n-1] > close[n-2] ? 1.0 : -1.0) : 0.0;
    double returns = n>1 ? (close[n-1] - close[n-2]) / close[n-2] : 0.0;
    out_features[0] = rsi14; out_features[1] = rsi7; out_features[2] = macd; out_features[3] = hist;
    out_features[4] = atr14; out_features[5] = atr20; out_features[6] = upper; out_features[7] = middle;
    out_features[8] = lower; out_features[9] = obv; out_features[10] = vol; out_features[11] = direction;
    return 0;
}

