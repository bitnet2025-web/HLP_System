def generate_whatsapp_hlp(date, data):
    return f"""
*HLP REPORT*
Date {date}

Elect. Unit: {data['electricity']}
Rate/unit: 19.33
Cost: Ksh {data['electricity']}

Water NCC: {data['ncc']}
Rate: 67
Cost: Ksh {data['ncc']}

Water Borehole: {data['borehole']}
Rate: 68
Cost: Ksh {data['borehole']}

LPG:
Cost: Ksh {data['lpg']}

Diesel:
Cost: Ksh {data['diesel']}

*TOTAL HLP COST*
Ksh {data['total']}
"""
