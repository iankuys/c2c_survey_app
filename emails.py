import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# SSL port: 465
# unsecured SMTP connection via TLS port 587
PORT = 465

EMAIL_SUBJECT = "Your C2C survey access key"


def construct_plaintext_message(user_email_addr: str, subject: str, key: str) -> str:
    message_plaintext = f"""\
Subject: {subject}
    
Hello,

This is a TEST EMAIL sent to {user_email_addr}.

Your C2C survey access key is {key}.

From, MIND DEVs
"""
    return message_plaintext


def construct_html_message(from_addr: str, to_addr: str, subject: str, key: str) -> str:
    message_html = MIMEMultipart("alternative")
    message_html["Subject"] = subject
    message_html["From"] = from_addr
    message_html["To"] = to_addr

    contents_as_txt = construct_plaintext_message(to_addr, subject, key)
    contents_as_html = f"""\
<html>
<body>
    <h1>The UCI C2C Registry</h1>
    <p>This is a <b>TEST EMAIL</b> sent to <b>{to_addr}</b>.</p>
    <p>Your C2C survey access key is <b><code>{key}</code></b></p>
    <p>From, MIND Devs</p>
</body>
</html>
"""
    message_part1 = MIMEText(contents_as_txt, "plain")
    message_part2 = MIMEText(contents_as_html, "html")
    message_html.attach(message_part1)
    message_html.attach(message_part2)
    return message_html.as_string()


def send_mail(
    user_email_address: str,
    access_key: str,
    our_smtp_server_address: str,
    our_email_address: str,
    our_email_password: str,
) -> None:
    print(f"** SENDING AN EMAIL TO '{user_email_address}' with access key '{access_key}'")
    print(f"** FROM '{our_email_address}'@'{our_smtp_server_address}'")

    # DEBUG:
    # email_contents = construct_html_message(
    #     our_email_address, user_email_address, EMAIL_SUBJECT, access_key
    # )
    # print(email_contents)

    # context = ssl.create_default_context()
    # with smtplib.SMTP_SSL(our_smtp_server_address, PORT, context=context) as server:
    #     server.login(our_email_address, our_email_password)

    #     # Plaintext mail:
    #     email_contents = construct_plaintext_message(user_email_address, EMAIL_SUBJECT, access_key)
    #     # HTML mail:
    #     email_contents = construct_html_message(our_email_address, user_email_address, EMAIL_SUBJECT, access_key)

    #     server.sendmail(our_email_address, user_email_address, email_contents)
    return
