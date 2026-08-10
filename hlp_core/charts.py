# ==============================
# HLP Management System - Charts Module
# ==============================
import os
import matplotlib.pyplot as plt
from datetime import datetime
from hlp_core.config import REPORTS_DIR, CHART_COLOR

# ------------------------------
# 1. DAILY CHART
# ------------------------------
def plot_daily(summary, date_str):
    """Generate a bar chart for daily consumption."""
    meters = [s[0] for s in summary]
    consumptions = [s[1] for s in summary]

    plt.figure(figsize=(10, 5))
    plt.bar(meters, consumptions, color=CHART_COLOR)
    plt.xticks(rotation=45, ha='right')
    plt.title(f"Daily Consumption - {date_str}")
    plt.ylabel("Units Consumed")
    plt.tight_layout()

    filename = f"Daily_Chart_{date_str.replace('-', '_')}.png"
    path = os.path.join(REPORTS_DIR, filename)
    plt.savefig(path)
    plt.close()
    print(f"📊 Daily chart saved: {path}")
    return path

# ------------------------------
# 2. WEEKLY CHART
# ------------------------------
def plot_weekly(weekly_data, month_name):
    """Generate weekly consumption chart (by week number)."""
    for meter_name in next(iter(weekly_data.values())).keys():
        weeks = []
        consumptions = []
        for week, meters in weekly_data.items():
            weeks.append(f"Week {week}")
            consumptions.append(meters.get(meter_name, 0))

        plt.figure(figsize=(8, 4))
        plt.plot(weeks, consumptions, marker='o', color=CHART_COLOR)
        plt.title(f"Weekly Consumption for {meter_name} - {month_name}")
        plt.xlabel("Week Number")
        plt.ylabel("Consumption (Units)")
        plt.tight_layout()

        filename = f"Weekly_{meter_name.replace(' ', '_')}_{month_name}.png"
        path = os.path.join(REPORTS_DIR, filename)
        plt.savefig(path)
        plt.close()
        print(f"📈 Weekly chart saved: {path}")

# ------------------------------
# 3. MONTHLY CHART
# ------------------------------
def plot_monthly(month_summary, month_name):
    """Generate a monthly total consumption chart."""
    meters = list(month_summary.keys())
    consumptions = list(month_summary.values())

    plt.figure(figsize=(10, 5))
    plt.barh(meters, consumptions, color=CHART_COLOR)
    plt.title(f"Monthly Consumption Summary - {month_name}")
    plt.xlabel("Units Consumed")
    plt.tight_layout()

    filename = f"Monthly_Chart_{month_name}.png"
    path = os.path.join(REPORTS_DIR, filename)
    plt.savefig(path)
    plt.close()
    print(f"📊 Monthly chart saved: {path}")
    return path
