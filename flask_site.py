import json
import random
import urllib.parse

from flask import Flask, redirect, render_template, request, url_for

import emails
import mindlib
import redcap_helpers

# The REDCap variable in this experiment's REDCap project that contains unique hashed C2C IDs
HASHED_ID_EXPERIMENT_REDCAP_VAR = "access_key"

# The REDCap variable in the C2Cv3 REDCap project that contains the same hashed IDs
HASHED_ID_C2C_REDCAP_VAR = "proj_pid_813"

# Configure this in tandem with c2c-id-hash.HASHED_ID_LENGTH (confirm w/ the REDCap projects)
EXPECTED_HASHED_ID_LENGTH = 12

BUBBLE_MESSAGES = {
    "bad_key": "Invalid key.",
    "missing_key": "Missing access key.",
    "unknown": "Unknown error.",
}

VIDEOS = mindlib.json_to_dict("./content/videos.json")
SUSPICIOUS_CHARS = [";", ":", "&", '"', "'", "`", ">", "<", "{", "}", "|", ".", "%"]


flask_app = Flask(__name__)
# flask_app.config["APPLICATION_ROOT"] = URL_PREFIX
flask_app.config.from_file("secrets.json", load=json.load)  # JSON keys must be in ALL CAPS


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
        flask_app.config["C2CV3_API_TOKEN"],
        flask_app.config["REDCAP_API_URL"],
        flask_app.config["C2CV3_TO_ACCESS_KEYS_REPORT_ID"],
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
        flask_app.config["C2CV3_API_TOKEN"],
        flask_app.config["REDCAP_API_URL"],
        flask_app.config["C2CV3_EMAILS_REPORT_ID"],
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


@flask_app.route("/", methods=["GET"])
def index():
    if "error_code" in request.args and len(request.args["error_code"]) > 0:
        error_code = request.args["error_code"]
        if error_code not in BUBBLE_MESSAGES:
            error_code = "unknown"
        return render_template("index.html", error_message=BUBBLE_MESSAGES[error_code])
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

        existing_dcv_video_data = redcap_helpers.export_dcv_video_data(
            flask_app.config["C2C_DCV_API_TOKEN"], flask_app.config["REDCAP_API_URL"], hashed_id
        )
        # print(survey_record)

        if len(existing_dcv_video_data) > 0:
            # The user has generated a set of videos already - they may have finished the survey already

            # TODO: Check the data from `existing_dcv_video_data` to set this bool
            participant_finished_survey = False
            if participant_finished_survey:
                return render_template(
                    "index.html",
                    key=hashed_id,
                    info_message="This survey has already been completed. Thank you for your participation!",
                )

            # Got video data but the user hasn't finished the survey yet - don't assign any more videos
            already_assigned_videos = [
                (r["video_a"], r["video_b"]) for r in existing_dcv_video_data
            ]
            print(
                f"Experiment record '{hashed_id}' (C2C ID {access_keys_to_c2c_ids[hashed_id]}) was already created with videos {already_assigned_videos})"
            )
            return render_template(
                "index.html", key=hashed_id, c2c_id=access_keys_to_c2c_ids[hashed_id]
            )
        else:
            # New survey participant
            # Shuffle all video keys, and save the first four from the shuffled list
            keys = list(VIDEOS.keys())
            random.shuffle(keys)
            four_videos = keys[0:4]

            # Add the record to the experiment's REDCap project and start the experiment
            new_record = [
                {
                    HASHED_ID_EXPERIMENT_REDCAP_VAR: hashed_id,
                    "c2c_id": access_keys_to_c2c_ids[hashed_id],
                },
                {
                    HASHED_ID_EXPERIMENT_REDCAP_VAR: hashed_id,
                    "redcap_event_name": "screen1_arm_1",
                    "video_a": four_videos[0],
                    "video_b": four_videos[1],
                },
                {
                    HASHED_ID_EXPERIMENT_REDCAP_VAR: hashed_id,
                    "redcap_event_name": "screen2_arm_1",
                    "video_a": four_videos[2],
                    "video_b": four_videos[3],
                },
                # Screen 3 video IDs are determined from the selections of Screens 1 and 2
                {
                    HASHED_ID_EXPERIMENT_REDCAP_VAR: hashed_id,
                    "redcap_event_name": "screen3_arm_1",
                    "video_a": "UNDEFINED",
                    "video_b": "UNDEFINED",
                },
            ]
            print(
                f"Creating NEW experiment record '{hashed_id}' (C2C ID {access_keys_to_c2c_ids[hashed_id]}) with the following videos: {four_videos}"
            )
            redcap_helpers.import_record(
                flask_app.config["C2C_DCV_API_TOKEN"],
                flask_app.config["REDCAP_API_URL"],
                new_record,
            )
            return render_template(
                "index.html", key=hashed_id, c2c_id=access_keys_to_c2c_ids[hashed_id]
            )
    return render_template("index.html")


@flask_app.route("/check", methods=["GET", "POST"])
def check():
    # "GET" request is needed so users can be redirected properly instead of seeing a "request not allowed" error
    # Endpoint that receives data from a user that manually input their key (hashed ID) to an HTML form on "/"
    # Redirect to "/" with that key to check
    if "key" in request.form and len(request.form["key"]) > 0:
        user_provided_key = request.form["key"].strip()
        if mindlib.is_valid_email_address(user_provided_key):
            check_email_addr_and_send_email(
                user_provided_key,
                flask_app.config["MAIL_SMTP_SERVER_ADDR"],
                flask_app.config["MAIL_C2C_NOREPLY_ADDR"],
                flask_app.config["MAIL_C2C_NOREPLY_DISPLAY_NAME"],
                flask_app.config["MAIL_C2C_NOREPLY_PASS"],
            )
            return redirect(url_for("index", sent_email="1"), code=301)

        # Not a valid email, so try interpreting this as a literal access key
        # Don't have to do any intensive sanitizing or checking here; index() will do that
        return redirect(url_for("index", key=user_provided_key), code=301)

    # Don't allow users to visit this endpoint directly
    return redirect(url_for("index"), code=301)


@flask_app.route("/videos", methods=["GET"])
def videos():
    if "key" in request.args and len(request.args["key"]) > 0:
        hashed_id = sanitize_key(request.args["key"])
        if len(hashed_id) < 1:
            print("This key failed sanitization:", request.args["key"])
            return redirect(url_for("index", error_code="bad_key"), code=301)

        access_keys_to_c2c_ids = create_id_mapping()

        if hashed_id not in access_keys_to_c2c_ids:
            print(f"Access key '{hashed_id}' not found in the report from C2Cv3")
            return redirect(url_for("index", error_code="bad_key"))

        print(f"Survey starting: {hashed_id}")
        return render_template("videos.html", vid_a_position="1", vid_b_position="2")
    return redirect(url_for("index", error_code="missing_key"), code=301)


@flask_app.errorhandler(404)
def page_not_found(err):
    return render_template("404.html"), 404
