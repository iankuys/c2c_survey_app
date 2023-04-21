import smtplib
from email.headerregistry import Address
from email.message import EmailMessage

# SSL port: 465
# unsecured SMTP connection via TLS port 587
PORT = 465

EMAIL_SUBJECT = "Your C2C survey access key"


def construct_plaintxt_body(user_email_addr: str, subject: str, key: str) -> str:
    message_plaintext = f"""\
Subject: {subject}

************* This is a TEST EMAIL sent to {user_email_addr}. *************

Hello,

This is a reminder email from an Internet survey operated by the UC Irvine Consent-to-Contact (C2C) Registry.

Click this link to access the survey - your access key should be automatically accepted:

https://go.c2c.uci.edu/c2c-dce?key={key}

If you receive a "We couldn't automatically detect an access key" error, you can copy+paste the following access key in the box that appears:

{key}

Thank you for your participation,
The UCI C2C Registry
https://c2c.uci.edu/
----

Please do not reply to this email, as this email inbox is not monitored.
If you have any questions, please contact ???.
"""
    return message_plaintext


def construct_html_body(user_email_addr: str, key: str) -> str:
    result = f"""<!DOCTYPE html>
<html>
<body>
    <h2>************* This is a <b>TEST EMAIL</b> sent to <b>{user_email_addr}</b>. ************* </h2>
    <p>Hello,</p>
    <p>This is a reminder email from an Internet survey operated by the UC Irvine Consent-to-Contact (C2C) Registry.</p>
    <p>Click this link to access the survey - your access key should be automatically accepted:</p>

    <p style="text-align: center;"><b><a href="https://go.c2c.uci.edu/c2c-dce?key={key}" target="_blank">https://go.c2c.uci.edu/c2c-dce?key={key}</a></b></p>

    <p>If you receive a "We couldn't automatically detect an access key" error, you can copy+paste the following access key in the box that appears:</p>

    <p style="text-align: center;"><b>{key}</b></p>
    
    <p>Thank you for your participation,<br />The UCI C2C Registry<br /><a href="https://c2c.uci.edu/" target="_blank">https://c2c.uci.edu/</a></p>
    <hr>

    <p>Please do not reply to this email, as this email inbox is not monitored.</p>
    <p>If you have any questions, please contact ???.</p>
</body>
</html>
"""
    return result


def construct_html_message(
    from_addr: str, from_addr_display_name: str, to_addr: str, subject: str, key: str
) -> EmailMessage:
    if "@" not in from_addr:
        raise ValueError(f"Malformed 'from' email: {from_addr}")
    from_addr_parts = from_addr.split("@")
    if len(from_addr_parts) != 2:
        raise ValueError(f"Malformed 'from' email: {from_addr}")

    message_html = EmailMessage()
    message_html["Subject"] = subject
    message_html["From"] = Address(
        display_name=from_addr_display_name, username=from_addr_parts[0], domain=from_addr_parts[1]
    )
    message_html["To"] = to_addr

    body_txt = construct_plaintxt_body(to_addr, subject, key)
    body_html = construct_html_body(to_addr, key)

    message_html.set_content(body_txt)
    message_html.add_alternative(body_html, subtype="html")
    return message_html


def send_mail(
    user_email_address: str,
    access_key: str,
    our_smtp_server_address: str,
    our_email_address: str,
    our_email_display_name: str,
    our_email_password: str,
) -> None:
    print(f"** SENDING AN EMAIL TO '{user_email_address}' with access key '{access_key}'")
    print(f"** FROM '{our_email_address}'@'{our_smtp_server_address}'")

    # DEBUG:
    # If an "=" appears in the console printout, that's a "soft line break" and it's normal:
    # https://stackoverflow.com/a/15621614 (email clients should handle those)
    # test_message = construct_html_message(
    #     our_email_address,
    #     our_email_display_name,
    #     user_email_address,
    #     EMAIL_SUBJECT,
    #     access_key,
    # )
    # print(test_message)

    try:
        with smtplib.SMTP_SSL(our_smtp_server_address, PORT) as smtp_server:
            smtp_server.login(our_email_address, our_email_password)
            message = construct_html_message(
                our_email_address,
                our_email_display_name,
                user_email_address,
                EMAIL_SUBJECT,
                access_key,
            )
            smtp_server.send_message(message)
    except Exception as e:
        print(
            f"Failed to send email to {user_email_address} (via {our_smtp_server_address}:{PORT})"
        )
        raise e
        # print(repr(e))
    return
