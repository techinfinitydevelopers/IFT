"""
Official India Zone / Region / State / City mapping.

Source of truth: client's ``India_Zone_Region_State_City_Mapping.xlsx``
(State Wise Mapping = 36 states/UTs, City Wise Mapping = 169 cities).
The values below are baked in from that file so there is no runtime
dependency on the spreadsheet.

Six zones: North, Central, West, East, South, Northeast.
In this dataset Region == Zone; ``resolve_region`` is provided for a future
Zonal Report where the two might diverge.

Public helpers:
    resolve_zone(state, city='')   -> zone   ('Unknown' if unrecognised)
    resolve_region(state, city='') -> region ('Unknown' if unrecognised)

Resolution is STATE-FIRST, city as a fallback: the school ``state`` field is
authoritative, and a state match avoids ambiguous city names (e.g. "Udaipur"
exists in both Rajasthan and Tripura; the official file lists only the Tripura
one). City lookup only fills in when the state is missing/unknown.
"""

import re

# ---------------------------------------------------------------------------
# Mapping data (generated from the official Excel; keys are normalised)
# ---------------------------------------------------------------------------

STATE_ZONE = {
    'andaman and nicobar islands': ('Central', 'Central'),
    'andhra pradesh': ('South', 'South'),
    'arunachal pradesh': ('Northeast', 'Northeast'),
    'assam': ('Northeast', 'Northeast'),
    'bihar': ('East', 'East'),
    'chandigarh': ('North', 'North'),
    'chhattisgarh': ('Central', 'Central'),
    'dadra and nagar haveli and daman and diu': ('West', 'West'),
    'delhi': ('North', 'North'),
    'goa': ('West', 'West'),
    'gujarat': ('West', 'West'),
    'haryana': ('North', 'North'),
    'himachal pradesh': ('North', 'North'),
    'jammu and kashmir': ('North', 'North'),
    'jharkhand': ('East', 'East'),
    'karnataka': ('South', 'South'),
    'kerala': ('South', 'South'),
    'ladakh': ('North', 'North'),
    'lakshadweep': ('North', 'North'),
    'madhya pradesh': ('Central', 'Central'),
    'maharashtra': ('West', 'West'),
    'manipur': ('Northeast', 'Northeast'),
    'meghalaya': ('Northeast', 'Northeast'),
    'mizoram': ('Northeast', 'Northeast'),
    'nagaland': ('Northeast', 'Northeast'),
    'odisha': ('East', 'East'),
    'puducherry': ('South', 'South'),
    'punjab': ('North', 'North'),
    'rajasthan': ('North', 'North'),
    'sikkim': ('Northeast', 'Northeast'),
    'tamil nadu': ('South', 'South'),
    'telangana': ('South', 'South'),
    'tripura': ('Northeast', 'Northeast'),
    'uttar pradesh': ('North', 'North'),
    'uttarakhand': ('North', 'North'),
    'west bengal': ('East', 'East'),
}

CITY_ZONE = {
    'agartala': ('Northeast', 'Northeast'),
    'agatti': ('North', 'North'),
    'agra': ('North', 'North'),
    'ahmedabad': ('West', 'West'),
    'aizawl': ('Northeast', 'Northeast'),
    'ajmer': ('North', 'North'),
    'alwar': ('North', 'North'),
    'ambala': ('North', 'North'),
    'amritsar': ('North', 'North'),
    'anantnag': ('North', 'North'),
    'andrott': ('North', 'North'),
    'asansol': ('East', 'East'),
    'aurangabad chhatrapati sambhajinagar': ('West', 'West'),
    'baddi': ('North', 'North'),
    'baramulla': ('North', 'North'),
    'bareilly': ('North', 'North'),
    'bathinda': ('North', 'North'),
    'belagavi': ('South', 'South'),
    'bengaluru': ('South', 'South'),
    'berhampur': ('East', 'East'),
    'bhagalpur': ('East', 'East'),
    'bhavnagar': ('West', 'West'),
    'bhilai': ('Central', 'Central'),
    'bhopal': ('Central', 'Central'),
    'bhubaneswar': ('East', 'East'),
    'bikaner': ('North', 'North'),
    'bilaspur': ('Central', 'Central'),
    'bokaro': ('East', 'East'),
    'champhai': ('Northeast', 'Northeast'),
    'chandigarh': ('North', 'North'),
    'chennai': ('South', 'South'),
    'churachandpur': ('Northeast', 'Northeast'),
    'coimbatore': ('South', 'South'),
    'cuttack': ('East', 'East'),
    'daman': ('West', 'West'),
    'darbhanga': ('East', 'East'),
    'davanagere': ('South', 'South'),
    'dehradun': ('North', 'North'),
    'delhi': ('North', 'North'),
    'deoghar': ('East', 'East'),
    'dhanbad': ('East', 'East'),
    'dharamshala': ('North', 'North'),
    'dharmanagar': ('Northeast', 'Northeast'),
    'dibrugarh': ('Northeast', 'Northeast'),
    'diglipur': ('Central', 'Central'),
    'dimapur': ('Northeast', 'Northeast'),
    'diu': ('West', 'West'),
    'durg': ('Central', 'Central'),
    'durgapur': ('East', 'East'),
    'faridabad': ('North', 'North'),
    'gandhinagar': ('West', 'West'),
    'gangtok': ('Northeast', 'Northeast'),
    'gaya': ('East', 'East'),
    'ghaziabad': ('North', 'North'),
    'gorakhpur': ('North', 'North'),
    'guntur': ('South', 'South'),
    'gurugram': ('North', 'North'),
    'guwahati': ('Northeast', 'Northeast'),
    'gwalior': ('Central', 'Central'),
    'gyalshing': ('Northeast', 'Northeast'),
    'haldwani': ('North', 'North'),
    'haridwar': ('North', 'North'),
    'havelock swaraj dweep': ('Central', 'Central'),
    'hisar': ('North', 'North'),
    'howrah': ('East', 'East'),
    'hubballi': ('South', 'South'),
    'hyderabad': ('South', 'South'),
    'imphal': ('Northeast', 'Northeast'),
    'indore': ('Central', 'Central'),
    'itanagar': ('Northeast', 'Northeast'),
    'jabalpur': ('Central', 'Central'),
    'jaipur': ('North', 'North'),
    'jalandhar': ('North', 'North'),
    'jammu': ('North', 'North'),
    'jamnagar': ('West', 'West'),
    'jamshedpur': ('East', 'East'),
    'jodhpur': ('North', 'North'),
    'jorhat': ('Northeast', 'Northeast'),
    'jowai': ('Northeast', 'Northeast'),
    'kannur': ('South', 'South'),
    'kanpur': ('North', 'North'),
    'karaikal': ('South', 'South'),
    'kargil': ('North', 'North'),
    'karimnagar': ('South', 'South'),
    'karnal': ('North', 'North'),
    'kavaratti': ('North', 'North'),
    'khammam': ('South', 'South'),
    'kharagpur': ('East', 'East'),
    'kochi': ('South', 'South'),
    'kohima': ('Northeast', 'Northeast'),
    'kolhapur': ('West', 'West'),
    'kolkata': ('East', 'East'),
    'kollam': ('South', 'South'),
    'korba': ('Central', 'Central'),
    'kota': ('North', 'North'),
    'kozhikode': ('South', 'South'),
    'kurnool': ('South', 'South'),
    'leh': ('North', 'North'),
    'lucknow': ('North', 'North'),
    'ludhiana': ('North', 'North'),
    'lunglei': ('Northeast', 'Northeast'),
    'madurai': ('South', 'South'),
    'mandi': ('North', 'North'),
    'mangaluru': ('South', 'South'),
    'mapusa': ('West', 'West'),
    'margao': ('West', 'West'),
    'meerut': ('North', 'North'),
    'mohali': ('North', 'North'),
    'mokokchung': ('Northeast', 'Northeast'),
    'mumbai': ('West', 'West'),
    'muzaffarpur': ('East', 'East'),
    'mysuru': ('South', 'South'),
    'nagpur': ('West', 'West'),
    'naharlagun': ('Northeast', 'Northeast'),
    'namchi': ('Northeast', 'Northeast'),
    'nashik': ('West', 'West'),
    'navi mumbai': ('West', 'West'),
    'nellore': ('South', 'South'),
    'new delhi': ('North', 'North'),
    'nizamabad': ('South', 'South'),
    'noida': ('North', 'North'),
    'panaji': ('West', 'West'),
    'panipat': ('North', 'North'),
    'pasighat': ('Northeast', 'Northeast'),
    'patiala': ('North', 'North'),
    'patna': ('East', 'East'),
    'port blair': ('Central', 'Central'),
    'prayagraj': ('North', 'North'),
    'puducherry': ('South', 'South'),
    'pune': ('West', 'West'),
    'puri': ('East', 'East'),
    'purnia': ('East', 'East'),
    'raipur': ('Central', 'Central'),
    'rajkot': ('West', 'West'),
    'ranchi': ('East', 'East'),
    'rishikesh': ('North', 'North'),
    'roorkee': ('North', 'North'),
    'rourkela': ('East', 'East'),
    'sagar': ('Central', 'Central'),
    'salem': ('South', 'South'),
    'sambalpur': ('East', 'East'),
    'shillong': ('Northeast', 'Northeast'),
    'shimla': ('North', 'North'),
    'silchar': ('Northeast', 'Northeast'),
    'siliguri': ('East', 'East'),
    'silvassa': ('West', 'West'),
    'solan': ('North', 'North'),
    'solapur': ('West', 'West'),
    'srinagar': ('North', 'North'),
    'surat': ('West', 'West'),
    'tawang': ('Northeast', 'Northeast'),
    'tezpur': ('Northeast', 'Northeast'),
    'thane': ('West', 'West'),
    'thiruvananthapuram': ('South', 'South'),
    'thoubal': ('Northeast', 'Northeast'),
    'thrissur': ('South', 'South'),
    'tiruchirappalli': ('South', 'South'),
    'tirupati': ('South', 'South'),
    'tiruppur': ('South', 'South'),
    'tura': ('Northeast', 'Northeast'),
    'udaipur': ('Northeast', 'Northeast'),
    'ujjain': ('Central', 'Central'),
    'vadodara': ('West', 'West'),
    'varanasi': ('North', 'North'),
    'vasco da gama': ('West', 'West'),
    'vellore': ('South', 'South'),
    'vijayawada': ('South', 'South'),
    'visakhapatnam': ('South', 'South'),
    'warangal': ('South', 'South'),
}

# Common alternate spellings / old names -> canonical normalised key.
_STATE_ALIASES = {
    'orissa': 'odisha',
    'pondicherry': 'puducherry',
    'nct of delhi': 'delhi',
    'national capital territory of delhi': 'delhi',
    'jammu kashmir': 'jammu and kashmir',
    'j and k': 'jammu and kashmir',
    'uttaranchal': 'uttarakhand',
    'daman and diu': 'dadra and nagar haveli and daman and diu',
    'dadra and nagar haveli': 'dadra and nagar haveli and daman and diu',
    'andaman nicobar': 'andaman and nicobar islands',
    'andaman and nicobar': 'andaman and nicobar islands',
    # No-space / common misspellings seen in manually-typed school data
    'tamilnadu': 'tamil nadu',
    'tamilnad': 'tamil nadu',
    'maharastra': 'maharashtra',
    'maharashta': 'maharashtra',
    'andhrapradesh': 'andhra pradesh',
    'andra pradesh': 'andhra pradesh',
    'madhyapradesh': 'madhya pradesh',
    'uttarpradesh': 'uttar pradesh',
    'westbengal': 'west bengal',
    'himachalpradesh': 'himachal pradesh',
    'arunachalpradesh': 'arunachal pradesh',
    'haryama': 'haryana',
    'chattisgarh': 'chhattisgarh',
    'pondichery': 'puducherry',
    # 2-letter state / UT codes (India vehicle/postal style)
    'mh': 'maharashtra', 'up': 'uttar pradesh', 'pb': 'punjab', 'ap': 'andhra pradesh',
    'ka': 'karnataka', 'tn': 'tamil nadu', 'gj': 'gujarat', 'rj': 'rajasthan',
    'mp': 'madhya pradesh', 'wb': 'west bengal', 'br': 'bihar', 'hr': 'haryana',
    'dl': 'delhi', 'ts': 'telangana', 'tg': 'telangana', 'kl': 'kerala',
    'od': 'odisha', 'or': 'odisha', 'jh': 'jharkhand', 'cg': 'chhattisgarh',
    'uk': 'uttarakhand', 'ua': 'uttarakhand', 'hp': 'himachal pradesh',
    'jk': 'jammu and kashmir', 'ga': 'goa', 'as': 'assam', 'ml': 'meghalaya',
    'mn': 'manipur', 'mz': 'mizoram', 'nl': 'nagaland', 'tr': 'tripura',
    'sk': 'sikkim', 'ar': 'arunachal pradesh', 'py': 'puducherry', 'pi': 'puducherry',
    'ch': 'chandigarh', 'an': 'andaman and nicobar islands', 'ld': 'lakshadweep',
    'dn': 'dadra and nagar haveli and daman and diu', 'la': 'ladakh',
}
_CITY_ALIASES = {
    'bangalore': 'bengaluru',
    'calcutta': 'kolkata',
    'bombay': 'mumbai',
    'madras': 'chennai',
    'trivandrum': 'thiruvananthapuram',
    'pondicherry': 'puducherry',
    'gurgaon': 'gurugram',
    'mysore': 'mysuru',
    'mangalore': 'mangaluru',
    'calicut': 'kozhikode',
    'cochin': 'kochi',
    'vizag': 'visakhapatnam',
    'allahabad': 'prayagraj',
    'gauhati': 'guwahati',
    'baroda': 'vadodara',
    'trichy': 'tiruchirappalli',
    'panjim': 'panaji',
}

_UNKNOWN = ('Unknown', 'Unknown')


def _normalize(value):
    """Lowercase, strip parentheticals, and collapse to a canonical token."""
    if not value:
        return ''
    s = str(value).strip().lower()
    s = re.sub(r'\s*\(.*?\)', '', s)          # drop "(NCT)" etc.
    s = s.replace('&', 'and').replace('/', ' ')
    s = re.sub(r'[^a-z0-9]+', ' ', s).strip()
    s = re.sub(r'\s+', ' ', s)
    return s


def _lookup(state='', city=''):
    """Return (region, zone). State-first, city as fallback."""
    s_raw = _normalize(state)
    if s_raw:
        s = _STATE_ALIASES.get(s_raw, s_raw)
        if s in STATE_ZONE:
            return STATE_ZONE[s]
        # user may have typed a CITY in the state field (e.g. "Bhopal")
        sc = _CITY_ALIASES.get(s_raw, s_raw)
        if sc in CITY_ZONE:
            return CITY_ZONE[sc]
    c_raw = _normalize(city)
    if c_raw:
        c = _CITY_ALIASES.get(c_raw, c_raw)
        if c in CITY_ZONE:
            return CITY_ZONE[c]
        # user may have typed a STATE in the city field
        cs = _STATE_ALIASES.get(c_raw, c_raw)
        if cs in STATE_ZONE:
            return STATE_ZONE[cs]
    return _UNKNOWN


def resolve_zone(state='', city=''):
    """Zone for a state (and optional city). 'Unknown' if unrecognised."""
    return _lookup(state, city)[1]


def resolve_region(state='', city=''):
    """Region for a state (and optional city). 'Unknown' if unrecognised."""
    return _lookup(state, city)[0]
