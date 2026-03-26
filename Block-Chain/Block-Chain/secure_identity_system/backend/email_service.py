import os
import smtplib
import threading
from email.message import EmailMessage
from email.utils import formatdate

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USERNAME)

def _public_base_url() -> str:
    explicit = (os.getenv("APP_BASE_URL") or os.getenv("PUBLIC_APP_URL") or "").strip()
    if explicit:
        return explicit.rstrip("/")

    scheme = (os.getenv("APP_SCHEME") or "http").strip() or "http"
    host = (os.getenv("PUBLIC_HOST") or os.getenv("HOST") or "127.0.0.1").strip() or "127.0.0.1"
    port = (os.getenv("PUBLIC_PORT") or os.getenv("PORT") or "5055").strip() or "5055"

    if host in {"0.0.0.0", "::"}:
        host = "127.0.0.1"

    return f"{scheme}://{host}:{port}".rstrip("/")

def send_registration_email(to_email, name):
    """Sends a welcome email to the newly registered user synchronously."""
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        return False
        
    msg = EmailMessage()
    msg["Subject"] = "Welcome to Secure Identity!"
    msg["From"] = f"Secure Identity <{SMTP_FROM_EMAIL}>"
    msg["To"] = to_email
    msg["Date"] = formatdate(localtime=True)
    
    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
        <h2>Registration Successful</h2>
        <p>Hi <b>{name}</b>,</p>
        <p>Your digital identity has been successfully enrolled in the Secure Identity system.</p>
        <p>You can now use your biometric profile to authenticate safely and seamlessly.</p>
        <br>
        <p>Regards,<br>The Secure Identity Team</p>
      </body>
    </html>
    """
    
    msg.set_content("Your digital identity has been successfully registered in the Secure Identity system.", subtype="plain")
    msg.add_alternative(html_content, subtype="html")

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"[Email Error] Failed to send to {to_email}: {e}")
        return False

def send_registration_email_async(to_email, name):
    """Fires and forgets the email sending process so the HTTP response isn't blocked."""
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        print(f"[Email Skipped] SMTP credentials not configured. Skipping welcome email for {to_email}.")
        return
        
    thread = threading.Thread(target=send_registration_email, args=(to_email, name))
    thread.daemon = True
    thread.start()


def send_admin_approval_email(admin_name, admin_email, approval_token):
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        return False
        
    master_admin_email = "lakshyatechprojects@gmail.com"
    msg = EmailMessage()
    msg["Subject"] = "Admin Registration Approval Required"
    msg["From"] = f"Secure Identity <{SMTP_FROM_EMAIL}>"
    msg["To"] = master_admin_email
    msg["Date"] = formatdate(localtime=True)
    
    approval_link = f"{_public_base_url()}/api/admin/verify?token={approval_token}"
    
    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
        <h2>Admin Approval Required</h2>
        <p>A new user is requesting Administrator access to the Secure Identity system.</p>
        <ul>
            <li><b>Name:</b> {admin_name}</li>
            <li><b>Email:</b> {admin_email}</li>
        </ul>
        <p>To approve this request and grant Admin privileges, click the link below:</p>
        <p><a href="{approval_link}" style="display:inline-block; padding:10px 20px; background-color:#007BFF; color:#fff; text-decoration:none; border-radius:5px;">Approve Admin Registration</a></p>
        <br>
        <p>If you do not recognize this request, you may safely ignore this email.</p>
      </body>
    </html>
    """
    
    msg.set_content(f"Admin Approval Required for {admin_email}. Link: {approval_link}", subtype="plain")
    msg.add_alternative(html_content, subtype="html")

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"[Email Error] Failed to send approval email to master admin: {e}")
        return False


def send_admin_approval_email_async(admin_name, admin_email, approval_token):
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        print(f"[Email Skipped] SMTP credentials not configured. Skipping admin approval email.")
        return
        
    thread = threading.Thread(target=send_admin_approval_email, args=(admin_name, admin_email, approval_token))
    thread.daemon = True
    thread.start()
