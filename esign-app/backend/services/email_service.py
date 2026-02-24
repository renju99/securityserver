import smtplib
import imaplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from sqlalchemy.orm import Session
import models

class EmailService:
    @staticmethod
    def send_email_notification(db: Session, to_email: str, subject: str, content: str, request_id: int):
        """Sends an email notification using the configured SMTP server."""
        config = db.query(models.EmailConfig).first()
        if not config:
            print("Email configuration not found")
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = f"{config.from_name} <{config.from_email}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(content, 'html'))

            if config.encryption == "ssl":
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(config.smtp_server, config.smtp_port, context=context)
            else:
                server = smtplib.SMTP(config.smtp_server, config.smtp_port)
                if config.encryption == "tls":
                    server.starttls()

            if config.username and config.password:
                server.login(config.username, config.password)

            server.send_message(msg)
            server.quit()

            # Log success
            log = models.EmailLog(
                recipient=to_email,
                subject=subject,
                status="Sent",
                request_id=request_id
            )
            db.add(log)
            db.commit()
            return True

        except Exception as e:
            print(f"Failed to send email: {e}")
            log = models.EmailLog(
                recipient=to_email,
                subject=subject,
                status="Failed",
                error_message=str(e),
                request_id=request_id
            )
            db.add(log)
            db.commit()
            return False

    @staticmethod
    def test_connection(config: models.EmailConfig, target_email: str):
        """Tests the SMTP connection and sends a test email."""
        try:
            msg = MIMEMultipart()
            msg['From'] = f"{config.from_name} <{config.from_email}>"
            msg['To'] = target_email
            msg['Subject'] = "eSign Portal - SMTP Test"
            msg.attach(MIMEText("This is a test email from your eSign Portal configuration.", 'plain'))

            if config.encryption == "ssl":
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(config.smtp_server, config.smtp_port, context=context)
            else:
                server = smtplib.SMTP(config.smtp_server, config.smtp_port)
                if config.encryption == "tls":
                    server.starttls()

            if config.username and config.password:
                server.login(config.username, config.password)

            server.send_message(msg)
            server.quit()
            return True, "Connection successful"
        except Exception as e:
            return False, str(e)

email_service = EmailService()
