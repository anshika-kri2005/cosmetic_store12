import random

def send_otp(phone):
    otp = str(random.randint(1000,9999))
    print("OTP for", phone, "is:", otp)   # ← IMPORTANT
    return otp


