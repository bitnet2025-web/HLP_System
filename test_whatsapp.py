import pywhatkit as kit
import datetime

# Replace with your WhatsApp number (Kenya format)
phone_number = "+254795554211"

# Message to send
message = "Test message from HLP Management System — WhatsApp integration successful!"

# Schedule message 1 minute from now
now = datetime.datetime.now()
send_hour = now.hour
send_minute = now.minute + 1

kit.sendwhatmsg(phone_number, message, send_hour, send_minute)

print("✅ WhatsApp message scheduled! Please ensure WhatsApp Web opens in your browser.")
