import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import os
from app.core.config import settings


class EmailService:
    def __init__(self):
        # Validate required email configuration
        if not settings.SMTP_SERVER:
            raise ValueError("SMTP_SERVER is required but not configured")
        if not settings.SMTP_PORT:
            raise ValueError("SMTP_PORT is required but not configured")
        if not settings.SMTP_USERNAME:
            raise ValueError("SMTP_USERNAME is required but not configured")
        if not settings.SMTP_PASSWORD:
            raise ValueError("SMTP_PASSWORD is required but not configured")
        if not settings.FROM_EMAIL:
            raise ValueError("FROM_EMAIL is required but not configured")
        if not settings.FRONTEND_URL:
            raise ValueError("FRONTEND_URL is required but not configured")
        
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = int(settings.SMTP_PORT)
        self.smtp_username = settings.SMTP_USERNAME
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.FROM_EMAIL
        self.frontend_url = settings.FRONTEND_URL
        

    def send_password_reset_email(self, to_email: str, reset_token: str, user_name: str = None, user_type: str = "user") -> bool:
        """
        Send password reset email to user
        """
        try:
            # Use the configured password reset URL (can be different from frontend URL)
            password_reset_base_url = getattr(settings, 'PASSWORD_RESET_BASE_URL', self.frontend_url)
            reset_url = f"{password_reset_base_url}/reset-password?token={reset_token}"
            
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "Reset Your ZivoHealth Password"
            msg["From"] = self.from_email
            msg["To"] = to_email

            # Create HTML content
            html_content = self._create_reset_email_html(reset_url, user_name or "User", user_type)
            
            # Create plain text content
            text_content = self._create_reset_email_text(reset_url, user_name or "User", user_type)

            # Attach parts
            part1 = MIMEText(text_content, "plain")
            part2 = MIMEText(html_content, "html")
            msg.attach(part1)
            msg.attach(part2)

            # Send email
            return self._send_email(msg, to_email)
            
        except Exception as e:
            print(f"Error sending password reset email: {e}")
            return False

    def _create_reset_email_html(self, reset_url: str, user_name: str, user_type: str = "user") -> str:
        """Create HTML email content"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Reset Your Password</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #e74c3c; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 30px; background-color: #f9f9f9; }}
                .button {{ display: inline-block; background-color: #e74c3c; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .footer {{ padding: 20px; text-align: center; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>ZivoHealth</h1>
                </div>
                <div class="content">
                    <h2>Password Reset Request</h2>
                    <p>Hello {user_name},</p>
                    <p>We received a request to reset your password for your ZivoHealth {user_type} account.</p>
                    <p>Click the button below to reset your password:</p>
                    <a href="{reset_url}" class="button">Reset Password</a>
                    <p>If the button doesn't work, copy and paste this link into your browser:</p>
                    <p><a href="{reset_url}">{reset_url}</a></p>
                    <p><strong>This link will expire in 30 minutes for security reasons.</strong></p>
                    <p>If you didn't request this password reset, please ignore this email.</p>
                </div>
                <div class="footer">
                    <p>© 2025 ZivoHealth. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

    def _create_reset_email_text(self, reset_url: str, user_name: str, user_type: str = "user") -> str:
        """Create plain text email content"""
        return f"""
        ZivoHealth - Password Reset Request
        
        Hello {user_name},
        
        We received a request to reset your password for your ZivoHealth {user_type} account.
        
        To reset your password, click the link below:
        {reset_url}
        
        This link will expire in 30 minutes for security reasons.
        
        If you didn't request this password reset, please ignore this email.
        
        Best regards,
        The ZivoHealth Team
        
        © 2025 ZivoHealth. All rights reserved.
        """

    def _send_email(self, msg: MIMEMultipart, to_email: str) -> bool:
        """Send email using SMTP"""
        try:
            if not self.smtp_username or not self.smtp_password:
                print("SMTP credentials not configured. Email not sent.")
                return False

            print(f"Attempting to send email via {self.smtp_server}:{self.smtp_port}")
            
            # Handle different SMTP configurations
            if self.smtp_port == 465:
                # SSL connection for port 465 (like Zoho)
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context) as server:
                    server.login(self.smtp_username, self.smtp_password)
                    server.send_message(msg)
            else:
                # STARTTLS for port 587 (like Gmail)
                context = ssl.create_default_context()
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls(context=context)
                    server.login(self.smtp_username, self.smtp_password)
                    server.send_message(msg)
            
            print(f"Password reset email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            print(f"Failed to send email: {e}")
            # For development, you might want to log the email content instead of failing
            if os.getenv("ENVIRONMENT") == "development":
                print(f"📧 [DEV] Would send email to {to_email}")
                print(f"📧 [DEV] Subject: {msg['Subject']}")
                password_reset_base_url = getattr(settings, 'PASSWORD_RESET_BASE_URL', self.frontend_url)
                print(f"📧 [DEV] Reset URL: {password_reset_base_url}/reset-password?token=...")
                return True  # Return True in dev mode to not break the flow
            return False

    def send_otp_email(self, to_email: str, otp_code: str, user_name: str = None) -> bool:
        """
        Send OTP code email to user
        """
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "Your ZivoHealth Login Code"
            msg["From"] = self.from_email
            msg["To"] = to_email

            # Create HTML content
            html_content = self._create_otp_email_html(otp_code, user_name or "User")
            
            # Create plain text content
            text_content = self._create_otp_email_text(otp_code, user_name or "User")

            # Attach parts
            part1 = MIMEText(text_content, "plain")
            part2 = MIMEText(html_content, "html")
            msg.attach(part1)
            msg.attach(part2)

            # Send email
            return self._send_email(msg, to_email)
            
        except Exception as e:
            print(f"Error sending OTP email: {e}")
            return False

    def _create_otp_email_html(self, otp_code: str, user_name: str) -> str:
        """Create HTML email content for OTP"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Your Login Code</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #e74c3c; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 30px; background-color: #f9f9f9; }}
                .otp-code {{ 
                    display: inline-block; 
                    background-color: #e74c3c; 
                    color: white; 
                    padding: 20px 30px; 
                    font-size: 32px; 
                    font-weight: bold; 
                    letter-spacing: 5px; 
                    border-radius: 8px; 
                    margin: 20px 0; 
                    text-align: center;
                    font-family: 'Courier New', monospace;
                }}
                .footer {{ padding: 20px; text-align: center; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>ZivoHealth</h1>
                </div>
                <div class="content">
                    <h2>Your Login Code</h2>
                    <p>Hello {user_name},</p>
                    <p>Use the following code to complete your login:</p>
                    <div class="otp-code">{otp_code}</div>
                    <p><strong>This code will expire in 10 minutes for security reasons.</strong></p>
                    <p>If you didn't request this login code, please ignore this email.</p>
                </div>
                <div class="footer">
                    <p>© 2025 ZivoHealth. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

    def _create_otp_email_text(self, otp_code: str, user_name: str) -> str:
        """Create plain text email content for OTP"""
        return f"""
        ZivoHealth - Your Login Code
        
        Hello {user_name},
        
        Use the following code to complete your login:
        
        {otp_code}
        
        This code will expire in 10 minutes for security reasons.
        
        If you didn't request this login code, please ignore this email.
        
        Best regards,
        The ZivoHealth Team
        
        © 2025 ZivoHealth. All rights reserved.
        """


# Create global instance
email_service = EmailService()
