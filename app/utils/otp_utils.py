import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import ssl
from ..config.settings import settings


# Setup dotenv
otp_storage = {}
def send_email_otp_for_verification(email: str, otp: str):
    try:
        msg = MIMEMultipart()
        msg["From"] = settings.email_username
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

        with smtplib.SMTP_SSL(settings.smtp_server, settings.smtp_port, context=context) as server:
            server.login(settings.email_username, settings.email_password)  # Authenticate

            # Send email and check if successful
            result = server.sendmail(settings.email_username, email, msg.as_string())
            if result == {}:
                return {"status": "success", "message": "OTP sent successfully"}
            else:
                return {"status": "failed", "message": "Failed to send OTP"}

    except Exception as e:
        return {"status": "error", "message": str(e)}

def send_email_otp(
        email: str,
        otp: str
        ):
    try:
        msg = MIMEMultipart()
        msg["From"] = settings.email_username
        msg["To"] = email
        msg["Subject"] = "OTP For Reset Password | CCTV AI"

        body = f"""\
        Dear User,

        We received a request to update or reset the password for your account.

        Your One-Time Password (OTP): {otp}

        Please use this OTP to proceed with updating your password. For security reasons, this OTP is valid for 10 minutes and can only be used once.

        If you did not request this change, please ignore this email or contact our support team immediately.

        Need help?
        Reach out to us at support@cctvai_vision.com

        Thank you,  
        The cctv ai Team  
        support@cctvai_vision.com
        """

        msg.attach(MIMEText(body, "plain"))


        # Create SSL context
        context = ssl.create_default_context()

        with smtplib.SMTP_SSL(settings.smtp_server, settings.smtp_port, context=context) as server:
            server.login(settings.email_username, settings.email_password)  # Authenticate

            if server.sendmail(settings.email_username, email, msg.as_string()) == {}:
                
                return {"status": "success", "message": "OTP sent successfully"}
            else:
                return {"status": "failed", "message": "Failed to send OTP"}

    except smtplib.SMTPAuthenticationError:
        print("SMTP Authentication Error: Invalid username/password")
        return {"status": "failed", "message": "SMTP Authentication failed"}
    except smtplib.SMTPException as e:
        print(f"SMTP Error: {e}")
        return {"status": "failed", "message": f"SMTP error: {str(e)}"}
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return {"status": "failed", "message": f"Unexpected error: {str(e)}"}
