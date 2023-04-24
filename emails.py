import smtplib
from email.headerregistry import Address
from email.message import EmailMessage
from pathlib import Path

import html2text
from jinja2 import Template

# SSL port: 465
# unsecured SMTP connection via TLS port 587
PORT = 465

EMAIL_SUBJECT = "Your C2C survey access key"


def construct_message_contents(user_email_addr: str, subject: str, key: str) -> tuple[str, str]:
    """Returns a 2-tuple of strings containing content to place in an email.
    The first element is the message in plain text and the second element is the message in HTML.
    """
    with open(Path(".", "templates", "_reminder_email.html")) as infile:
        # HTML
        # Do this first so we can derive the plain text FROM it
        email_jinja_template = Template(infile.read())
        data = {"user_email_addr": user_email_addr, "key": key}
        html_message = email_jinja_template.render(data)

        # Plain text
        parser = html2text.HTML2Text()
        parser.ignore_emphasis = True
        parser.ignore_links = True
        converted_html_message = parser.handle(html_message)
        plaintext_message = f"Subject: {subject}\n\n{converted_html_message}"
        return (plaintext_message, html_message)


def construct_message(
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

    body_txt, body_html = construct_message_contents(to_addr, subject, key)

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
    # test_message = construct_message(
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
            message = construct_message(
                our_email_address,
                our_email_display_name,
                user_email_address,
                EMAIL_SUBJECT,
                access_key,
            )
            # print(message)
            smtp_server.send_message(message)
    except Exception as e:
        print(
            f"Failed to send email to {user_email_address} (via {our_smtp_server_address}:{PORT})"
        )
        raise e
        # print(repr(e))
    return
