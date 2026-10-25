import math, datetime
def sun(date, lat, lon, rise=True, tz=9):
    # NOAA algorithm, zenith 90.833
    N=date.timetuple().tm_yday
    lngHour=lon/15
    t=N+((6 if rise else 18)-lngHour)/24
    M=0.9856*t-3.289
    L=(M+1.916*math.sin(math.radians(M))+0.020*math.sin(math.radians(2*M))+282.634)%360
    RA=math.degrees(math.atan(0.91764*math.tan(math.radians(L))))%360
    RA=(RA+(math.floor(L/90)*90-math.floor(RA/90)*90))/15
    sd=0.39782*math.sin(math.radians(L)); cd=math.cos(math.asin(sd))
    cH=(math.cos(math.radians(90.833))-sd*math.sin(math.radians(lat)))/(cd*math.cos(math.radians(lat)))
    H=(360-math.degrees(math.acos(cH))) if rise else math.degrees(math.acos(cH))
    H/=15
    T=H+RA-0.06571*t-6.622
    UT=(T-lngHour)%24
    loc=(UT+tz)%24
    m=round(loc*60); return f"{m//60}:{m%60:02d}"
P={'新潟':(37.912,139.061),'幕張':(35.648,140.035),'浦安':(35.632,139.880),'東京':(35.681,139.767),'奥多摩':(35.809,139.096)}
print('check okutama 2025-11-22 rise', sun(datetime.date(2025,11,22),*P['新潟']), 'set', sun(datetime.date(2025,11,22),*P['奥多摩'],False))
for d,a,b in [((2023,12,30),'新潟','幕張'),((2023,12,31),'浦安','浦安'),((2024,1,1),'浦安','浦安'),((2024,1,2),'浦安','東京')]:
    D=datetime.date(*d); print(D, a, sun(D,*P[a]), b, sun(D,*P[b],False))
