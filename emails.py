import smtplib
import ssl

# SSL port: 465
# unsecured SMTP connection via TLS port 587
PORT = 465


def send_mail(
    user_email_address: str,
    access_key: str,
    our_smtp_server_address: str,
    our_email_address: str,
    our_email_password: str,
) -> None:
    print(f"** SENDING AN EMAIL TO '{user_email_address}' with access key '{access_key}'")
    print(f"** FROM '{our_email_address}'@'{our_smtp_server_address}'")
    # context = ssl.create_default_context()

    # with smtplib.SMTP_SSL(our_smtp_server_address, PORT, context=context) as server:
    #     server.login(our_email_address, our_email_password)
    #     message_plaintext = f"""Test email! Hello, {user_email_address}

    # Your access key is {access_key}.

    # From, MIND DEVs"""
    # TODO
    return
