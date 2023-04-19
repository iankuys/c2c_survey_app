import json
import urllib.parse

from flask import Blueprint, Flask, redirect, render_template, request, url_for

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
    "email_sent": "Thank you! If your email address was registered with C2C, an email has been sent to you.",
}

SUSPICIOUS_CHARS = [";", ":", "&", '"', "'", "`", ">", "<", "{", "}", "|", ".", "%"]

# Use a Blueprint to prepend URL_PREFIX to all applicable pages
bp = Blueprint("main_blueprint", __name__, static_folder="static", template_folder="templates")

################################
############ HELPERS ###########


def sanitize_key(key_from_html_string: str) -> str:
    """Decodes and sanitizes user-provided 'keys' (intended to be hashed C2C IDs)."""
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


def email_user_access_key(email_address: str) -> None:
    """If applicable, sends a reminder email to a user containing their access key for this experiment."""
    print(f"Checking email {email_address}")
    active_c2cv3_emails = redcap_helpers.export_redcap_report(
        app.config["C2CV3_API_TOKEN"],
        app.config["REDCAP_API_URL"],
        app.config["C2CV3_EMAILS_REPORT_ID"],
    )
    for record in active_c2cv3_emails:
        if (
            "start_email" in record
            and "record_id" in record
            and email_address.lower() == record["start_email"].lower()
        ):
            c2c_id = record["record_id"]

            c2c_ids_to_access_keys = create_id_mapping(reversed=True)
            if c2c_id not in c2c_ids_to_access_keys:
                print(f"C2C ID {c2c_id} doesn't have an access key for this experiment")
                return

            access_key_to_send = c2c_ids_to_access_keys[c2c_id]
            # TODO: SEND MAIL
            print(
                f"** SENDING AN EMAIL TO '{record['start_email']}' (C2C ID {c2c_id}) with access key '{access_key_to_send}'"
            )
            return
    print(f"Email '{email_address}' not found in the list of active C2C participants")
    return


################################
########### ENDPOINTS ##########
# http://127.0.0.1:5000/c2c-retention-dce/


@bp.route("/", methods=["GET"])
def index():
    if "sent_email" in request.args and len(request.args["sent_email"]) > 0:
        # TODO: create new endpoint so users aren't confused
        return render_template("index.html", info_message=BUBBLE_MESSAGES["email_sent"])
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
        redcap_helpers.import_record(
            app.config["C2C_DCV_API_TOKEN"], app.config["REDCAP_API_URL"], new_record
        )
        return render_template(
            "index.html", key=hashed_id, c2c_id=access_keys_to_c2c_ids[hashed_id]
        )
    return render_template("index.html")


@bp.route("/check", methods=["GET", "POST"])
def check():
    # Endpoint that receives data from a user that manually input their key (hashed ID) to an HTML form on "/"
    # Redirect to "/" with that key to check
    if "key" in request.form and len(request.form["key"]) > 0:
        user_provided_key = request.form["key"].strip()
        if mindlib.is_valid_email_address(user_provided_key):
            email_user_access_key(user_provided_key)
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
