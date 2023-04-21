import json
import urllib.parse

from flask import Blueprint, Flask, redirect, render_template, request, url_for

import emails
import mindlib
import redcap_helpers

################################
############ CONFIG ############

URL_PREFIX = "/c2c-retention-dce"

# The REDCap variable in this experiment's REDCap project that contains unique hashed C2C IDs
HASHED_ID_EXPERIMENT_REDCAP_VAR = "access_key"
HASHED_ID_C2C_REDCAP_VAR = "proj_pid_813"

# Configure this in tandem with c2c-id-hash.HASHED_ID_LENGTH (and the contents of the REDCap project)
EXPECTED_HASHED_ID_LENGTH = 12

################################
############ STARTUP ###########

BUBBLE_MESSAGES = {
    "bad_key": "Invalid key.",
    "bad_email": "Couldn't get access key from email address.",
}

SUSPICIOUS_CHARS = [";", ":", "&", '"', "'", "`", ">", "<", "{", "}", "|", ".", "%"]

# Use a Blueprint to prepend URL_PREFIX to all applicable pages
bp = Blueprint("main_blueprint", __name__, static_folder="static", template_folder="templates")

################################
############ HELPERS ###########


def sanitize_key(key_from_html_string: str) -> str:
    """URL-decodes and sanitizes user-provided 'access keys' (intended to be hashed C2C IDs).
    Returns an empty string if a string fails sanitization.
    """
    result = urllib.parse.unquote_plus(key_from_html_string).strip()
    # Hashed IDs MUST be of a pre-specified length - anything else is suspicious.
    if len(result) == EXPECTED_HASHED_ID_LENGTH and not any(
        [s in result for s in SUSPICIOUS_CHARS]
    ):
        return result
    return ""


def create_id_mapping(reversed=False) -> dict[str:str]:
    """Returns a dict mapping hashed C2C IDs to their corresponding original C2C IDs.
    The report only includes C2C participants that have NOT withdrawn from the C2C study.
    If reversed = True, original C2C IDs will be mapped to their hashed IDs.
    """
    c2cv3_project_keys = redcap_helpers.export_redcap_report(
        app.config["C2CV3_API_TOKEN"],
        app.config["REDCAP_API_URL"],
        app.config["C2CV3_TO_ACCESS_KEYS_REPORT_ID"],
    )
    result = {
        record[HASHED_ID_C2C_REDCAP_VAR]: record["record_id"] for record in c2cv3_project_keys
    }
    if reversed:
        result = {
            record["record_id"]: record[HASHED_ID_C2C_REDCAP_VAR] for record in c2cv3_project_keys
        }
    return result


def check_email_addr_and_send_email(
    user_submitted_email_address: str,
    our_email_server_address: str,
    our_from_email_address: str,
    our_from_email_display_name: str,
    our_from_email_password: str,
) -> None:
    """If applicable, sends a reminder email to a user containing their access key for this experiment."""
    print(f"Checking email {user_submitted_email_address}")
    active_c2cv3_emails = redcap_helpers.export_redcap_report(
        app.config["C2CV3_API_TOKEN"],
        app.config["REDCAP_API_URL"],
        app.config["C2CV3_EMAILS_REPORT_ID"],
    )
    for record in active_c2cv3_emails:
        if (
            "start_email" in record
            and "record_id" in record
            and user_submitted_email_address.lower() == record["start_email"].lower()
        ):
            # User's email matches one found in the report
            c2c_id = record["record_id"]
            c2c_ids_to_access_keys = create_id_mapping(reversed=True)
            if c2c_id not in c2c_ids_to_access_keys:
                print(f"C2C ID {c2c_id} is not active")
                return

            access_key_to_send = c2c_ids_to_access_keys[c2c_id]
            if len(access_key_to_send) == 0:
                print(
                    f"C2C ID {c2c_id} is active, but doesn't have an access key for this experiment"
                )
                return

            emails.send_mail(
                record["start_email"],
                access_key_to_send,
                our_email_server_address,
                our_from_email_address,
                our_from_email_display_name,
                our_from_email_password,
            )
            return
    print(
        f"Email '{user_submitted_email_address}' not found in the list of active C2C participants"
    )
    return


################################
########### ENDPOINTS ##########
# http://127.0.0.1:5000/c2c-retention-dce/


@bp.route("/", methods=["GET"])
def index():
    if "sent_email" in request.args and len(request.args["sent_email"]) > 0:
        return render_template("email_sent.html")
    if "key" in request.args and len(request.args["key"]) > 0:
        hashed_id = sanitize_key(request.args["key"])
        if len(hashed_id) < 1:
            print("This key failed sanitization:", request.args["key"])
            return render_template("index.html", error_message=BUBBLE_MESSAGES["bad_key"])

        access_keys_to_c2c_ids = create_id_mapping()

        if hashed_id not in access_keys_to_c2c_ids:
            print(f"Access key '{hashed_id}' not found in the report from C2Cv3")
            print(
                "If this key is a legitimate hashed ID, then the user has withdrawn from the C2C study."
            )
            return render_template("index.html", error_message=BUBBLE_MESSAGES["bad_key"])

        # TODO: If they've already completed the experiment, display a "thank you" message

        # Add the record to the experiment's REDCap project and start the experiment
        new_record = [
            {
                HASHED_ID_EXPERIMENT_REDCAP_VAR: hashed_id,
                "c2c_id": access_keys_to_c2c_ids[hashed_id],
            }
        ]
        print(
            f"Creating experiment record '{hashed_id}' (C2C ID {access_keys_to_c2c_ids[hashed_id]})"
        )
        redcap_helpers.import_record(
            app.config["C2C_DCV_API_TOKEN"], app.config["REDCAP_API_URL"], new_record
        )
        return render_template(
            "index.html", key=hashed_id, c2c_id=access_keys_to_c2c_ids[hashed_id]
        )
    return render_template("index.html")


@bp.route("/check", methods=["POST"])
def check():
    # Endpoint that receives data from a user that manually input their key (hashed ID) to an HTML form on "/"
    # Redirect to "/" with that key to check
    if "key" in request.form and len(request.form["key"]) > 0:
        user_provided_key = request.form["key"].strip()
        if mindlib.is_valid_email_address(user_provided_key):
            check_email_addr_and_send_email(
                user_provided_key,
                app.config["MIND_SMTP_SERVER_ADDR"],
                app.config["MIND_C2C_NOREPLY_EMAIL_ADDR"],
                app.config["MIND_C2C_NOREPLY_EMAIL_DISPLAY_NAME"],
                app.config["MIND_C2C_NOREPLY_EMAIL_PASS"],
            )
            return redirect(url_for("main_blueprint.index", sent_email="1"), code=301)
        # Not a valid email, so try interpreting this as a literal access key
        # Don't have to do any intensive sanitizing or checking here; index() will do that
        # Success, send access key to index
        return redirect(url_for("main_blueprint.index", key=user_provided_key), code=301)

    # Don't allow users to visit this endpoint directly
    return redirect(url_for("main_blueprint.index"), code=301)


@bp.app_errorhandler(404)
def page_not_found(err):
    return render_template("404.html"), 404


################################
################################

app = Flask(__name__)
app.config["APPLICATION_ROOT"] = URL_PREFIX
app.config.from_file("secrets.json", load=json.load)  # JSON keys must be in ALL CAPS
app.register_blueprint(bp, url_prefix=URL_PREFIX)


if __name__ == "__main__":
    app.run()
