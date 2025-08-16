import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import ssl



# TODO : SHIVEN-SAINI : SETUP DOTENV FOR UTILS
def send_email_otp_for_verification(email: str, otp: str):
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_USERNAME
        msg["To"] = email
        msg["Subject"] = "OTP For Verification Account | CCTV AI"

        body = f"""\
Dear User,

We received a request to verify your account.

Your One-Time Password (OTP): {otp}

Need help?
Reach out to us at support@cctvai_vision.com

Thank you,  
The CCTV AI Team  
support@cctvai_vision.com
"""
        msg.attach(MIMEText(body, "plain"))

        # Create SSL context
        context = ssl.create_default_context()

        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
            server.login(EMAIL_USERNAME, EMAIL_PASSWORD)  # Authenticate

            # Send email and check if successful
            result = server.sendmail(EMAIL_USERNAME, email, msg.as_string())
            if result == {}:
                return {"status": "success", "message": "OTP sent successfully"}
            else:
                return {"status": "failed", "message": "Failed to send OTP"}

    except Exception as e:
        return {"status": "error", "message": str(e)}
