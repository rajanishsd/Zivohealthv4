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
            # Build reset URL using FRONTEND_URL only
            reset_url = f"{self.frontend_url.rstrip('/')}/reset-password?token={reset_token}"
            
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
            print(f"SMTP Username: {self.smtp_username}")
            print(f"From Email: {self.from_email}")
            
            # Zoho requires FROM_EMAIL to match SMTP_USERNAME
            if "zoho" in self.smtp_server.lower() and self.from_email != self.smtp_username:
                print(f"⚠️  WARNING: For Zoho SMTP, FROM_EMAIL ({self.from_email}) should match SMTP_USERNAME ({self.smtp_username})")
                print(f"⚠️  This mismatch will cause '553 Sender is not allowed to relay emails' error")
                # Update the From field to match the authenticated user
                msg.replace_header("From", self.smtp_username)
                print(f"✅ Automatically updated From header to: {self.smtp_username}")
            
            # Handle different SMTP configurations
            if self.smtp_port == 465:
                # SSL connection for port 465 (like Zoho)
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context) as server:
                    server.set_debuglevel(1)  # Enable debug output
                    server.login(self.smtp_username, self.smtp_password)
                    server.send_message(msg)
            else:
                # STARTTLS for port 587 (like Gmail and Zoho)
                context = ssl.create_default_context()
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.set_debuglevel(1)  # Enable debug output
                    server.starttls(context=context)
                    server.login(self.smtp_username, self.smtp_password)
                    server.send_message(msg)
            
            print(f"✅ Email sent successfully to {to_email}")
            return True
            
        except smtplib.SMTPException as e:
            print(f"❌ SMTP Error: {e}")
            if "553" in str(e) or "relay" in str(e).lower():
                print("💡 This is likely because FROM_EMAIL doesn't match SMTP_USERNAME for Zoho")
                print("💡 Solution: Set FROM_EMAIL = SMTP_USERNAME in your .env file")
            # For development, you might want to log the email content instead of failing
            if os.getenv("ENVIRONMENT") == "development":
                print(f"📧 [DEV] Would send email to {to_email}")
                print(f"📧 [DEV] Subject: {msg['Subject']}")
                return True  # Return True in dev mode to not break the flow
            return False
        except Exception as e:
            print(f"❌ Failed to send email: {e}")
            # For development, you might want to log the email content instead of failing
            if os.getenv("ENVIRONMENT") == "development":
                print(f"📧 [DEV] Would send email to {to_email}")
                print(f"📧 [DEV] Subject: {msg['Subject']}")
                return True  # Return True in dev mode to not break the flow
            return False

    def send_verification_email(self, to_email: str, verification_token: str, user_name: str = None) -> bool:
        """
        Send email verification email to user
        """
        try:
            # Build verification URL
            verification_url = f"{self.frontend_url.rstrip('/')}/verify-email?token={verification_token}"
            
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "Verify Your ZivoHealth Email Address"
            msg["From"] = self.from_email
            msg["To"] = to_email

            # Create HTML content
            html_content = self._create_verification_email_html(verification_url, user_name or "User")
            
            # Create plain text content
            text_content = self._create_verification_email_text(verification_url, user_name or "User")

            # Attach parts
            part1 = MIMEText(text_content, "plain")
            part2 = MIMEText(html_content, "html")
            msg.attach(part1)
            msg.attach(part2)

            # Send email
            return self._send_email(msg, to_email)
            
        except Exception as e:
            print(f"Error sending verification email: {e}")
            return False

    def _create_verification_email_html(self, verification_url: str, user_name: str) -> str:
        """Create HTML email content for email verification"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Verify Your Email</title>
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
                    <h2>Welcome to ZivoHealth!</h2>
                    <p>Hello {user_name},</p>
                    <p>Thank you for creating your ZivoHealth account. To complete your registration and start using our platform, please verify your email address.</p>
                    <p>Click the button below to verify your email:</p>
                    <a href="{verification_url}" class="button">Verify Email Address</a>
                    <p>If the button doesn't work, copy and paste this link into your browser:</p>
                    <p><a href="{verification_url}">{verification_url}</a></p>
                    <p><strong>This link will expire in 24 hours for security reasons.</strong></p>
                    <p>If you didn't create this account, please ignore this email.</p>
                </div>
                <div class="footer">
                    <p>© 2025 ZivoHealth. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

    def _create_verification_email_text(self, verification_url: str, user_name: str) -> str:
        """Create plain text email content for email verification"""
        return f"""
        ZivoHealth - Email Verification
        
        Hello {user_name},
        
        Thank you for creating your ZivoHealth account. To complete your registration and start using our platform, please verify your email address.
        
        Click the link below to verify your email:
        {verification_url}
        
        This link will expire in 24 hours for security reasons.
        
        If you didn't create this account, please ignore this email.
        
        Best regards,
        The ZivoHealth Team
        
        © 2025 ZivoHealth. All rights reserved.
        """

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

    def send_admin_otp_email(self, to_email: str, otp_code: str) -> bool:
        """
        Send OTP code email to admin for admin dashboard login
        """
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "Your ZivoHealth Admin Login Code"
            msg["From"] = self.from_email
            msg["To"] = to_email

            # Create HTML content for admin OTP
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Your Admin Login Code</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #2c3e50; color: white; padding: 20px; text-align: center; }}
                    .content {{ padding: 30px; background-color: #f9f9f9; }}
                    .otp-code {{ 
                        display: inline-block; 
                        background-color: #2c3e50; 
                        color: white; 
                        padding: 20px 30px; 
                        font-size: 32px; 
                        font-weight: bold; 
                        letter-spacing: 10px;
                        border-radius: 5px;
                        margin: 20px 0;
                    }}
                    .footer {{ padding: 20px; text-align: center; color: #666; font-size: 12px; }}
                    .warning {{ background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 10px; margin: 20px 0; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🔐 ZivoHealth Admin Dashboard</h1>
                    </div>
                    <div class="content">
                        <h2>Admin Login Code</h2>
                        <p>Use the following code to complete your admin login:</p>
                        <div style="text-align: center;">
                            <div class="otp-code">{otp_code}</div>
                        </div>
                        <p><strong>This code will expire in 10 minutes for security reasons.</strong></p>
                        <div class="warning">
                            <p><strong>⚠️ Security Notice:</strong></p>
                            <ul>
                                <li>This code is for admin dashboard access</li>
                                <li>Never share this code with anyone</li>
                                <li>If you didn't request this code, contact security immediately</li>
                            </ul>
                        </div>
                    </div>
                    <div class="footer">
                        <p>Best regards,<br>The ZivoHealth Security Team</p>
                        <p>© 2025 ZivoHealth. All rights reserved.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Create plain text content
            text_content = f"""
            ZivoHealth Admin Dashboard - Your Login Code
            
            Use the following code to complete your admin login:
            
            {otp_code}
            
            This code will expire in 10 minutes for security reasons.
            
            SECURITY NOTICE:
            - This code is for admin dashboard access
            - Never share this code with anyone
            - If you didn't request this code, contact security immediately
            
            Best regards,
            The ZivoHealth Security Team
            
            © 2025 ZivoHealth. All rights reserved.
            """

            # Attach parts
            part1 = MIMEText(text_content, "plain")
            part2 = MIMEText(html_content, "html")
            msg.attach(part1)
            msg.attach(part2)

            # Send email
            return self._send_email(msg, to_email)
            
        except Exception as e:
            print(f"Error sending admin OTP email: {e}")
            return False

    def send_admin_password_reset_email(self, to_email: str, reset_url: str, admin_name: str = None) -> bool:
        """
        Send password reset email to admin
        """
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "Reset Your ZivoHealth Admin Password"
            msg["From"] = self.from_email
            msg["To"] = to_email

            # Create HTML content
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Reset Your Admin Password</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #2c3e50; color: white; padding: 20px; text-align: center; }}
                    .content {{ padding: 30px; background-color: #f9f9f9; }}
                    .button {{ display: inline-block; background-color: #2c3e50; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                    .footer {{ padding: 20px; text-align: center; color: #666; font-size: 12px; }}
                    .warning {{ background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 10px; margin: 20px 0; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🔐 ZivoHealth Admin Dashboard</h1>
                    </div>
                    <div class="content">
                        <h2>Admin Password Reset Request</h2>
                        <p>Hello {admin_name or "Admin"},</p>
                        <p>We received a request to reset your password for your ZivoHealth admin account.</p>
                        <p>Click the button below to reset your password:</p>
                        <a href="{reset_url}" class="button">Reset Admin Password</a>
                        <p>If the button doesn't work, copy and paste this link into your browser:</p>
                        <p><a href="{reset_url}">{reset_url}</a></p>
                        <div class="warning">
                            <p><strong>⚠️ Security Notice:</strong></p>
                            <ul>
                                <li>This link will expire in 1 hour for security reasons</li>
                                <li>This is for admin dashboard access</li>
                                <li>If you didn't request this reset, contact security immediately</li>
                            </ul>
                        </div>
                    </div>
                    <div class="footer">
                        <p>Best regards,<br>The ZivoHealth Security Team</p>
                        <p>© 2025 ZivoHealth. All rights reserved.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Create plain text content
            text_content = f"""
            ZivoHealth Admin Dashboard - Password Reset Request
            
            Hello {admin_name or "Admin"},
            
            We received a request to reset your password for your ZivoHealth admin account.
            
            Use this link to reset your password:
            {reset_url}
            
            SECURITY NOTICE:
            - This link will expire in 1 hour for security reasons
            - This is for admin dashboard access
            - If you didn't request this reset, contact security immediately
            
            Best regards,
            The ZivoHealth Security Team
            
            © 2025 ZivoHealth. All rights reserved.
            """

            # Attach parts
            part1 = MIMEText(text_content, "plain")
            part2 = MIMEText(html_content, "html")
            msg.attach(part1)
            msg.attach(part2)

            # Send email
            return self._send_email(msg, to_email)
            
        except Exception as e:
            print(f"Error sending admin password reset email: {e}")
            return False


# Create global instance
email_service = EmailService()
