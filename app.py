import json
import urllib.parse

from flask import Blueprint, Flask, redirect, render_template, request, url_for

import mindlib
import redcap_helpers

################################
############ CONFIG ############

URL_PREFIX = "/c2c-retention-dce"

EXPECTED_HASHED_ID_LENGTH = 10

################################
############ STARTUP ###########

# Use a Blueprint to prepend URL_PREFIX to all applicable pages
bp = Blueprint("main_blueprint", __name__, static_folder="static", template_folder="templates")

SUSPICIOUS_CHARS = [";", ":", "&", '"', "'", "`", ">", "<", "{", "}", "|", ".", "%"]

ERROR_MESSAGES = {
    "bad_key": "Invalid key.",
    "bad_email": "Couldn't get access key from email address.",
}

################################
############ HELPERS ###########


def sanitize_key(key_from_html_string: str) -> str:
    """Decodes and sanitizes user-provided 'keys' (intended to be hashed C2C IDs)."""
    result = urllib.parse.unquote_plus(key_from_html_string).strip()
    # Hashed IDs MUST be of a pre-specified length - any less or any more means they were hand-crafted.
    if len(result) == EXPECTED_HASHED_ID_LENGTH and not any(
        [s in result for s in SUSPICIOUS_CHARS]
    ):
        return result
    return ""


def hashed_id_is_valid_access_key(received_hashed_id: str) -> bool:
    print(f"Checking hashed ID {received_hashed_id}")
    all_c2c_dcv_id_records = redcap_helpers.export_redcap_report(
        app.config["C2C_DCV_API_TOKEN"],
        app.config["REDCAP_API_URL"],
        app.config["C2C_DCV_TO_ACCESS_KEYS_REPORT_ID"],
    )
    access_keys = set(
        r["retention_dce_access_key"]
        for r in all_c2c_dcv_id_records
        if "retention_dce_access_key" in r
    )
    return received_hashed_id in access_keys


def lookup_hashed_id_by_email(email_address: str) -> str:
    print(f"Checking email {email_address}")
    all_email_c2c_records = redcap_helpers.export_redcap_report(
        app.config["C2CV3_API_TOKEN"],
        app.config["REDCAP_API_URL"],
        app.config["C2CV3_ALL_EMAILS_REPORT_ID"],
    )
    emails_to_c2c_id = dict(
        [
            (r["start_email"], r["record_id"])
            for r in all_email_c2c_records
            if "start_email" in r and "record_id" in r
        ]
    )
    if email_address not in emails_to_c2c_id:
        return ""

    c2c_id = emails_to_c2c_id[email_address]
    print(f"Got C2C ID from email {email_address}: {c2c_id}")

    all_c2c_dcv_id_records = redcap_helpers.export_redcap_report(
        app.config["C2C_DCV_API_TOKEN"],
        app.config["REDCAP_API_URL"],
        app.config["C2C_DCV_TO_ACCESS_KEYS_REPORT_ID"],
    )
    c2c_ids_to_access_keys = dict(
        [
            (r["c2c_id"], r["retention_dce_access_key"])
            for r in all_c2c_dcv_id_records
            if "c2c_id" in r and "retention_dce_access_key" in r
        ]
    )
    if c2c_id not in c2c_ids_to_access_keys:
        return ""

    return c2c_ids_to_access_keys[c2c_id]


################################
########### ENDPOINTS ##########
# http://127.0.0.1:5000/c2c-retention-dce/


@bp.route("/", methods=["GET"])
def index():
    if "key" in request.args:
        if len(request.args["key"]) > 0:
            hashed_id = sanitize_key(request.args["key"])
            if len(hashed_id) < 1:
                # print("This key failed sanitization:", request.args["key"])
                return render_template("index.html", error_message=ERROR_MESSAGES["bad_key"])

            if not hashed_id_is_valid_access_key(hashed_id):
                return render_template("index.html", error_message=ERROR_MESSAGES["bad_key"])

            return render_template("index.html", key=hashed_id)
        else:
            if "by_email" in request.args:
                return render_template("index.html", error_message=ERROR_MESSAGES["bad_email"])
    return render_template("index.html")


@bp.route("/check", methods=["GET", "POST"])
def check():
    # Endpoint that receives data from a user that manually input their key (hashed ID) to an HTML form on "/"
    # Redirect to "/" with that key to check
    if "key" in request.form and len(request.form["key"]) > 0:
        user_provided_key = request.form["key"].strip()
        if mindlib.is_valid_email_address(user_provided_key):
            # print("User provided an email address")
            user_provided_key = lookup_hashed_id_by_email(user_provided_key)
            return redirect(
                url_for("main_blueprint.index", key=user_provided_key, by_email="1"), code=301
            )
        return redirect(url_for("main_blueprint.index", key=user_provided_key), code=301)
        # Don't do any intensive checking here; index() will do that

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
