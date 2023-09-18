import json
import random
import urllib.parse

from flask import Flask, make_response, redirect, render_template, request, url_for

import emails
import mindlib
import redcap_helpers

FLASK_APP_PATH = "/c2c-retention-dce/survey"

# The REDCap variable in this experiment's REDCap project that contains unique hashed C2C IDs
HASHED_ID_EXPERIMENT_REDCAP_VAR = "access_key"

# The REDCap variable in the C2Cv3 REDCap project that contains the same hashed IDs
HASHED_ID_C2C_REDCAP_VAR = "proj_pid_813"

# Configure this in tandem with c2c-id-hash.HASHED_ID_LENGTH (confirm w/ the REDCap projects)
EXPECTED_HASHED_ID_LENGTH = 12

BUBBLE_MESSAGES = {
    "bad_key": "Invalid key.",
    "missing_key": "Missing access key.",
    "v01": "Failed to load videos. Please try starting the survey again.",  # missing cookies
    "v02": "Failed to load videos. Please try starting the survey again.",  # missing "screen" URL param
    "s01": "An error occured with loading the next page. Please contact UCI MIND IT and provide your access key.",  # Couldn't generate screen 3 due to missing video IDs
    "survey_completed": "This survey has been completed. Thank you for your participation!",
    "unknown": "Unknown error.",
}

# List of screen numbers that this survey has
# ALLOWED_SCREENS = [1, 2, 3, 4, 5, 6, 7]
MAX_SCREENS = 3  # Change to 7 when in production

VIDEOS = mindlib.json_to_dict("./content/videos.json")
UNDEFINED_VID_ID_PLACEHOLDER = "UNDEFINED"
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
    print(f"[{user_submitted_email_address}] - checking email to send access key")
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
                print(f"[{user_submitted_email_address}] C2C ID {c2c_id} is not active")
                return

            access_key_to_send = c2c_ids_to_access_keys[c2c_id]
            if len(access_key_to_send) == 0:
                print(
                    f"[{user_submitted_email_address}] C2C ID {c2c_id} is active, but doesn't have an access key for this experiment"
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
    print(f"[{user_submitted_email_address}] not found in the list of active C2C participants")
    return


def get_user_agent() -> str:
    """Get the user-agent information (browser and device type) of the site's visitors"""
    return request.headers.get("User-Agent")


################################
########### ENDPOINTS ##########


@flask_app.route("/", methods=["GET"])
def index():
    if "error_code" in request.args and len(request.args["error_code"]) > 0:
        error_code = request.args["error_code"]
        if error_code not in BUBBLE_MESSAGES:
            error_code = "unknown"
        return render_template("index.html", error_message=BUBBLE_MESSAGES[error_code])

    if "msg" in request.args and len(request.args["msg"]) > 0:
        message_code = request.args["msg"]
        if message_code not in BUBBLE_MESSAGES:
            return render_template("index.html", error_message=BUBBLE_MESSAGES["unknown"])
        return render_template("index.html", info_message=BUBBLE_MESSAGES[message_code])

    if "sent_email" in request.args and len(request.args["sent_email"]) > 0:
        return render_template("email_sent.html")

    if "key" in request.args and len(request.args["key"]) > 0:
        hashed_id = sanitize_key(request.args["key"])
        if len(hashed_id) < 1:
            print("This key failed sanitization:", request.args["key"])
            return render_template("index.html", error_message=BUBBLE_MESSAGES["bad_key"])

        access_keys_to_c2c_ids = create_id_mapping()

        if hashed_id not in access_keys_to_c2c_ids:
            print(
                f"[{hashed_id}] key not found in the C2Cv3 report- if this key is a legitimate hashed ID, then the user has withdrawn from the C2C study."
            )
            return render_template("index.html", error_message=BUBBLE_MESSAGES["bad_key"])

        existing_dcv_video_data = redcap_helpers.export_dcv_video_data(
            flask_app.config["C2C_DCV_API_TOKEN"], flask_app.config["REDCAP_API_URL"], hashed_id
        )

        # print(survey_record)

        already_started_survey = len(existing_dcv_video_data) > 0
        if already_started_survey:
            # The user has generated a set of videos already - they may have finished the survey already

            # TODO: Check the data from `existing_dcv_video_data` to set this bool
            participant_finished_survey = False
            if participant_finished_survey:
                return render_template(
                    "index.html",
                    key=hashed_id,
                    info_message=BUBBLE_MESSAGES["survey_completed"],
                )

            # Got video data but the user hasn't finished the survey yet - don't assign any more videos
            # print(existing_dcv_video_data)
            fourteen_videos = []
            for r in existing_dcv_video_data:
                existing_vid_a_id = r["video_a"]
                existing_vid_b_id = r["video_b"]
                if (
                    len(existing_vid_a_id) > 0
                    and existing_vid_a_id != UNDEFINED_VID_ID_PLACEHOLDER
                    and len(existing_vid_b_id) > 0
                    and existing_vid_b_id != UNDEFINED_VID_ID_PLACEHOLDER
                    and len(fourteen_videos) < 14
                ):
                    fourteen_videos.append(r["video_a"])
                    fourteen_videos.append(r["video_b"])
            most_recent_completed_screen_from_redcap = redcap_helpers.get_most_recent_screen(
                flask_app.config["C2C_DCV_API_TOKEN"],
                flask_app.config["REDCAP_API_URL"],
                hashed_id,
            )
            print(
                f"[{hashed_id}] Experiment record (C2C ID {access_keys_to_c2c_ids[hashed_id]}) already created with videos {fourteen_videos} and completed screen {most_recent_completed_screen_from_redcap}"
            )
            if (
                int(most_recent_completed_screen_from_redcap) == MAX_SCREENS
            ):  # ALLOWED_SCREENS[-1]:
                # If they completed the final screen, serve the completion message
                return redirect(url_for("index", msg="survey_completed"), code=301)
        else:
            # New survey participant
            # Shuffle all video keys, and save the first fourteen from the shuffled list
            video_ids = list(VIDEOS.keys())
            random.shuffle(video_ids)
            fourteen_videos = video_ids[0:14]

            start_time = mindlib.timestamp_now()

            # Add the record to the experiment's REDCap project and start the experiment
            new_record = [
                {
                    HASHED_ID_EXPERIMENT_REDCAP_VAR: hashed_id,
                    "c2c_id": access_keys_to_c2c_ids[hashed_id],
                    "survey_tm_start": start_time,
                    "user_agent": get_user_agent(),
                },
                {
                    HASHED_ID_EXPERIMENT_REDCAP_VAR: hashed_id,
                    "redcap_event_name": "screen1_arm_1",
                    "video_a": fourteen_videos[0],
                    "video_b": fourteen_videos[1],
                },
                {
                    HASHED_ID_EXPERIMENT_REDCAP_VAR: hashed_id,
                    "redcap_event_name": "screen2_arm_1",
                    "video_a": fourteen_videos[2],
                    "video_b": fourteen_videos[3],
                },
                {
                    HASHED_ID_EXPERIMENT_REDCAP_VAR: hashed_id,
                    "redcap_event_name": "screen3_arm_1",
                    "video_a": fourteen_videos[4],
                    "video_b": fourteen_videos[5],
                },
                {
                    HASHED_ID_EXPERIMENT_REDCAP_VAR: hashed_id,
                    "redcap_event_name": "screen4_arm_1",
                    "video_a": fourteen_videos[6],
                    "video_b": fourteen_videos[7],
                },
                {
                    HASHED_ID_EXPERIMENT_REDCAP_VAR: hashed_id,
                    "redcap_event_name": "screen5_arm_1",
                    "video_a": fourteen_videos[8],
                    "video_b": fourteen_videos[9],
                },
                {
                    HASHED_ID_EXPERIMENT_REDCAP_VAR: hashed_id,
                    "redcap_event_name": "screen6_arm_1",
                    "video_a": fourteen_videos[10],
                    "video_b": fourteen_videos[11],
                },
                {
                    HASHED_ID_EXPERIMENT_REDCAP_VAR: hashed_id,
                    "redcap_event_name": "screen7_arm_1",
                    "video_a": fourteen_videos[12],
                    "video_b": fourteen_videos[13],
                },
            ]
            print(
                f"[{hashed_id}] Creating NEW record (C2C ID {access_keys_to_c2c_ids[hashed_id]}) with videos {fourteen_videos}"
            )
            redcap_helpers.import_record(
                flask_app.config["C2C_DCV_API_TOKEN"],
                flask_app.config["REDCAP_API_URL"],
                new_record,
            )

            resp = redirect(url_for("intro", key=hashed_id), code=301)

        if already_started_survey:
            resp = redirect(
                url_for("videos", key=hashed_id, screen=most_recent_completed_screen_from_redcap),
                code=301,
            )

        # resp.set_cookie(key="v1_id", value=fourteen_videos[0])
        # resp.set_cookie(key="v1_url", value=VIDEOS[fourteen_videos[0]])
        # resp.set_cookie(key="v2_id", value=fourteen_videos[1])
        # resp.set_cookie(key="v2_url", value=VIDEOS[fourteen_videos[1]])
        # resp.set_cookie(key="v3_id", value=fourteen_videos[2])
        # resp.set_cookie(key="v3_url", value=VIDEOS[fourteen_videos[2]])
        # resp.set_cookie(key="v4_id", value=fourteen_videos[3])
        # resp.set_cookie(key="v4_url", value=VIDEOS[fourteen_videos[3]])

        for i in range(14):
            resp.set_cookie(key=f"v{i + 1}_id", value=fourteen_videos[i])
            resp.set_cookie(key=f"v{i + 1}_url", value=VIDEOS[fourteen_videos[i]])

        # Set completed_screen cookie: the most recent screen the user completed
        # Needs to be served in a path because the JS script has limited scope to where it can place the cookie
        if not already_started_survey:
            # Fresh start: user has no REDCap data
            resp.set_cookie(key="completed_screen", value="0", path=FLASK_APP_PATH)
        elif "completed_screen" not in request.cookies:
            # User started the survey (they have REDCap data) and they cleared their cookies
            # Allows users to resume taking the survey
            print(f"[{hashed_id}] cleared cookies but is resuming survey")
            resp.set_cookie(
                key="completed_screen",
                value=most_recent_completed_screen_from_redcap,
                path=FLASK_APP_PATH,
            )
        return resp
    return render_template("index.html")


@flask_app.route("/intro", methods=["GET"])
def intro():
    # Endpoint if user is a new survey participant
    if "key" in request.args and len(request.args["key"]) > 0:
        hashed_id = sanitize_key(request.args["key"])
    # Debug: returns "hello intro!"
    return render_template("intro.html", key=hashed_id)


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
            print(f"This key failed sanitization: {request.args['key']}")
            return redirect(url_for("index", error_code="bad_key"), code=301)

        access_keys_to_c2c_ids = create_id_mapping()

        if hashed_id not in access_keys_to_c2c_ids:
            print(f"[{hashed_id}] key not found in the C2Cv3 report")
            return redirect(url_for("index", error_code="bad_key"))

        if (
            "screen" in request.args
            and len(request.args["screen"]) > 0
            and "completed_screen" in request.cookies
        ):
            try:
                scr = int(request.args["screen"])
            except ValueError:
                return render_template("videos.html")

            # Check for previous screen completion
            try:
                most_recent_completed_screen = int(request.cookies["completed_screen"])
                print(
                    f"[{hashed_id}] Most recent completed screen (via cookie): {most_recent_completed_screen}"
                )
                screen_to_serve = most_recent_completed_screen + 1
            except ValueError:
                return render_template("videos.html")

            if scr != screen_to_serve:
                print(
                    f"[{hashed_id}] Incorrect screen accessed ({scr})!! Serving screen {screen_to_serve}"
                )
                scr = screen_to_serve
                # From the user's perspective: the URL will contain an incorrect screen number but
                # the correct screen will be served

            # SERVE_SCREEN_3 = most_recent_completed_screen == 2
            # if SERVE_SCREEN_3:
            #     resp_screen3 = make_response(
            #         render_template("videos.html", screen=scr, vid_a_position=5, vid_b_position=6)
            #     )

            #     # List of 2 strings: each is the ID of a video that was previously selected
            #     chosen_video_ids = redcap_helpers.get_first_two_selected_videos(
            #         flask_app.config["C2C_DCV_API_TOKEN"],
            #         flask_app.config["REDCAP_API_URL"],
            #         hashed_id,
            #     )
            #     print(f"[{hashed_id}] Got previously selected videos: {chosen_video_ids}")
            #     if chosen_video_ids == ["", ""]:
            #         return redirect(url_for("index", error_code="s01"), code=301)

            #     _vid5_id_index = random.randint(0, 1)  # 0 or 1
            #     _vid6_id_index = _vid5_id_index - 1  # -1 or 0
            #     v5_id = chosen_video_ids[_vid5_id_index]
            #     v6_id = chosen_video_ids[_vid6_id_index]

            #     # Set cookies for proper frontend behavior
            #     resp_screen3.set_cookie(key="v5_id", value=v5_id)
            #     resp_screen3.set_cookie(key="v5_url", value=VIDEOS[v5_id])
            #     resp_screen3.set_cookie(key="v6_id", value=v6_id)
            #     resp_screen3.set_cookie(key="v6_url", value=VIDEOS[v6_id])

            #     # Create REDCap record with screen 3 data
            #     record_screen3 = [
            #         {
            #             HASHED_ID_EXPERIMENT_REDCAP_VAR: hashed_id,
            #             "redcap_event_name": "screen3_arm_1",
            #             "video_a": v5_id,
            #             "video_b": v6_id,
            #         }
            #     ]
            #     redcap_helpers.import_record(
            #         flask_app.config["C2C_DCV_API_TOKEN"],
            #         flask_app.config["REDCAP_API_URL"],
            #         record_screen3,
            #     )
            #     print(f"[{hashed_id}] Created REDCap record for Screen 3.")

            if scr > MAX_SCREENS:
                # could consult cookie here too
                most_recent_completed_screen_from_redcap = redcap_helpers.get_most_recent_screen(
                    flask_app.config["C2C_DCV_API_TOKEN"],
                    flask_app.config["REDCAP_API_URL"],
                    hashed_id,
                )
                if int(most_recent_completed_screen_from_redcap) == MAX_SCREENS:
                    # If they completed the final screen, serve the completion message
                    return redirect(url_for("index", msg="survey_completed"), code=301)
                return render_template("videos.html")

            # Get the correct video positions for the current screen:
            # screen 1 = videos 1 and 2,
            # screen 2 = videos 3 and 4,
            # screen 3 = videos 5 and 6, etc...
            vid_a_pos = (scr * 2) - 1
            vid_b_pos = scr * 2
            print(f"[{hashed_id}] Starting screen {scr} (videos {vid_a_pos} & {vid_b_pos})")

            if most_recent_completed_screen < MAX_SCREENS:
                return render_template(
                    "videos.html", screen=scr, vid_a_position=vid_a_pos, vid_b_position=vid_b_pos
                )
            # elif SERVE_SCREEN_3:  # most_recent_completed_screen == 2
            #     return resp_screen3
            elif most_recent_completed_screen == MAX_SCREENS:
                return redirect(url_for("outro"), code=301)

            # TODO: temporary end of survey; maybe add a new text section for screen 4
            return redirect(url_for("index", msg="survey_completed"), code=301)

        else:
            # No "screen" URL parameter
            return redirect(url_for("index", error_code="v02"), code=301)
    return redirect(url_for("index", error_code="missing_key"), code=301)


@flask_app.route("/outro", methods=["GET"])
def outro():
    # if "key" in request.args and len(request.args["key"]) > 0:
    #     hashed_id = sanitize_key(request.args["key"])

    return render_template("outro.html")


@flask_app.errorhandler(404)
def page_not_found(err):
    return render_template("404.html"), 404
