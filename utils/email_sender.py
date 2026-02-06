"""
Email sending utility for attendance system
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from typing import Optional, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class EmailSender:
    """Класс для отправки email уведомлений"""
    
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "localhost")
        self.smtp_port = int(os.getenv("SMTP_PORT", "25"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_use_tls = os.getenv("SMTP_USE_TLS", "false").lower() == "true"
        self.from_email = os.getenv("SMTP_FROM_EMAIL", "noreply@attendance.local")
        self.enabled = os.getenv("SMTP_ENABLED", "false").lower() == "true"
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        attachments: Optional[List[Path]] = None
    ) -> bool:
        """
        Отправить email
        
        Args:
            to_email: Email получателя
            subject: Тема письма
            body: Текст письма
            html_body: HTML версия письма (опционально)
            attachments: Список путей к файлам для вложения
        
        Returns:
            True если отправка успешна, False иначе
        """
        if not self.enabled:
            logger.info(f"Email sending disabled, skipping email to {to_email}")
            return False
        
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Добавляем текстовую версию
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # Добавляем HTML версию если есть
            if html_body:
                msg.attach(MIMEText(html_body, 'html', 'utf-8'))
            
            # Добавляем вложения
            if attachments:
                for attachment_path in attachments:
                    if attachment_path.exists():
                        with open(attachment_path, 'rb') as f:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(f.read())
                            encoders.encode_base64(part)
                            part.add_header(
                                'Content-Disposition',
                                f'attachment; filename= {attachment_path.name}'
                            )
                            msg.attach(part)
            
            # Отправляем
            if self.smtp_use_tls:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            
            if self.smtp_user and self.smtp_password:
                server.login(self.smtp_user, self.smtp_password)
            
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
    def send_report_email(
        self,
        to_email: str,
        subject: str,
        report_file: Path,
        report_name: str = "Отчет"
    ) -> bool:
        """
        Отправить отчет по email
        
        Args:
            to_email: Email получателя
            subject: Тема письма
            report_file: Путь к файлу отчета
            report_name: Название отчета
        
        Returns:
            True если отправка успешна, False иначе
        """
        body = f"Во вложении находится {report_name}."
        html_body = f"<p>Во вложении находится <strong>{report_name}</strong>.</p>"
        
        return self.send_email(
            to_email=to_email,
            subject=subject,
            body=body,
            html_body=html_body,
            attachments=[report_file] if report_file.exists() else None
        )


# Глобальный экземпляр
email_sender = EmailSender()
