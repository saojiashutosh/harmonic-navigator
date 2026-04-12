from src.celery import app
from django.conf import settings
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


@app.task(bind=True)
def send_email(self, receiver, subject, message, cc=''):
    try:
        # smtp setup to send email
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.set_debuglevel(0)  # 0 for no debugging
        server.ehlo()  # say hello to the server
        server.starttls()  # start TLS encryption
        server.login(settings.EMAIL, settings.PASSWORD)

        # Email Configuration
        body = MIMEMultipart("alternative")
        body["Subject"] = subject
        body["From"] = settings.EMAIL
        body["To"] = receiver   # send to single email
        body.attach(MIMEText(message, 'html'))
        if cc != "":
            body['Cc'] = cc
            rcpt = [receiver] + cc.split(',')
        else:
            rcpt = [receiver]
        server.sendmail(settings.EMAIL, rcpt, body.as_string())
        return True
    except:
        return False
