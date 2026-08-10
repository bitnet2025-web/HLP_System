# ==============================
# HLP Management System - Calculations Module
# ==============================
from datetime import datetime, timedelta
from hlp_core.database import get_summary_for_date
from hlp_core.config import METERS

# ------------------------------
# 1. DAILY HIGHEST CONSUMER
# ------------------------------
def get_highest_meter(summary):
    """
    Identify the highest-consuming meter (excluding main meter).
    summary: list of tuples [(meter_name, consumption, cost), ...]
    """
    filtered = [s for s in summary if "MAIN" not in s[0].upper()]
    if not filtered:
        return None
    highest = max(filtered, key=lambda x: x[1])
    return highest  # (meter_name, consumption, cost)

# ------------------------------
# 2. WEEKLY SUMMARY
# ------------------------------
def get_weekly_summary(db_func, start_date=None):
    """
    Aggregate readings by week number for each meter.
    db_func: function to fetch readings by date
    start_date: optional date string (YYYY-MM-DD)
    """
    today = datetime.now()
    if start_date:
        today = datetime.strptime(start_date, "%Y-%m-%d")

    # Determine start of the month
    first_day = today.replace(day=1)
    summaries = {}

    # Loop through all days of the current month
    for i in range((today - first_day).days + 1):
        date_str = (first_day + timedelta(days=i)).strftime("%Y-%m-%d")
        readings = db_func(date_str)
        if not readings:
            continue
        for _, meter_name, _, _, consumption, _ in readings:
            week_num = (i // 7) + 1
            summaries.setdefault(week_num, {}).setdefault(meter_name, 0)
            summaries[week_num][meter_name] += consumption

    return summaries  # {week_num: {meter_name: total_consumption}}

# ------------------------------
# 3. MONTHLY SUMMARY
# ------------------------------
def get_monthly_summary(db_func):
    """
    Summarize total consumption per meter for the current month.
    """
    today = datetime.now()
    first_day = today.replace(day=1)
    summaries = {m: 0 for m in METERS}

    for i in range((today - first_day).days + 1):
        date_str = (first_day + timedelta(days=i)).strftime("%Y-%m-%d")
        readings = db_func(date_str)
        for _, meter_name, _, _, consumption, _ in readings:
            summaries[meter_name] += consumption

    return summaries

# ------------------------------
# 4. AVERAGE CONSUMPTION
# ------------------------------
def calculate_averages(summary_dict):
    """
    Calculate average consumption per meter.
    Input: {meter_name: [daily consumptions]}
    Output: {meter_name: avg_consumption}
    """
    averages = {}
    for meter, values in summary_dict.items():
        if values:
            averages[meter] = sum(values) / len(values)
    return averages
