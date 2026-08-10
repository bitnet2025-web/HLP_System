from hlp_rates import HLP_RATES

# ---------- BASIC UTIL ----------
def consumption(opening, closing):
    if opening is None or closing is None:
        return 0
    return max(closing - opening, 0)


# ---------- ELECTRICAL ----------
def electricity_cost(kwh):
    rate = HLP_RATES["ELECTRICITY_KWH"]
    cost = kwh * rate
    return round(cost, 2)


# ---------- WATER ----------
def water_ncc_cost(ncc_units):
    rate = HLP_RATES["WATER_NCC"]
    return round(ncc_units * rate, 2)

def water_borehole_cost(borehole_units):
    rate = HLP_RATES["WATER_BOREHOLE"]
    return round(borehole_units * rate, 2)


# ---------- LPG ----------
def lpg_cost(percent_used):
    kg = percent_used * HLP_RATES["LPG_PERCENT"]
    cost = kg * HLP_RATES["LPG_SCM"]
    return round(cost, 2)


# ---------- DIESEL ----------
def diesel_cost(litres):
    rate = HLP_RATES["DIESEL"]
    return round(litres * rate, 2)


# ---------- TOTAL HLP ----------
def total_hlp_cost(electric, ncc, borehole, lpg, diesel):
    total = electric + ncc + borehole + lpg + diesel
    return round(total, 2)
