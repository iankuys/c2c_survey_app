import re
import urllib.parse

from flask import Blueprint, Flask, redirect, render_template, request, url_for

################################
############ CONFIG ############

URL_PREFIX = "/c2c-retention-dce"

ERROR_MESSAGES = {"bad_key": "Invalid key."}

################################
############ STARTUP ###########

# Use a Blueprint to prepend URL_PREFIX to all applicable pages
bp = Blueprint("main_blueprint", __name__, static_folder="static", template_folder="templates")

# Starting with any number of alphanumeric characters (and '.', '+', '_', '-')
#   followed by a single '@'
#   followed by any number of alphanumeric characters (and '.', '_', '-')
#   followed by a single '.'
#   ending with any number of letters
EMAIL_REGEX = re.compile(r"^[A-Za-z0-9\.\+_-]+@[A-Za-z0-9\._-]+\.[a-zA-Z]*$")

################################
############ HELPERS ###########


def sanitize_key(key_from_html_string: str) -> str:
    """Decodes and sanitizes user-provided 'keys' (intended to be hashed C2C IDs)."""
    result = urllib.parse.unquote_plus(key_from_html_string).strip()
    # TODO: check for suspicious characters or substrings
    return result


def is_valid_email_address(potential_email_address: str) -> bool:
    return bool(EMAIL_REGEX.match(potential_email_address))


def lookup_hashed_id_by_email(email_address: str) -> str:
    # TODO
    return "Temporary value"


################################
########### ENDPOINTS ##########
# http://127.0.0.1:5000/c2c-retention-dce/


@bp.route("/", methods=["GET"])
def index():
    if "key" in request.args and len(request.args["key"]) > 0:
        hashed_id = sanitize_key(request.args["key"])
        if len(hashed_id) < 1:
            # print("This key failed sanitization:", request.args["key"])
            return render_template("index.html", error_message=ERROR_MESSAGES["bad_key"])

        # TODO: Check if the user's key is a valid C2C hashed ID

        return render_template("index.html", key=hashed_id)
    return render_template("index.html")


@bp.route("/check", methods=["GET", "POST"])
def check():
    # Endpoint that receives data from a user that manually input their key (hashed ID) to an HTML form on "/"
    # Redirect to "/" with that key to check
    if "key" in request.form and len(request.form["key"]) > 0:
        user_provided_key = request.form["key"].strip()
        if is_valid_email_address(user_provided_key):
            # print("User provided an email address")
            user_provided_key = lookup_hashed_id_by_email(user_provided_key)
        # print("Got fallback key", user_provided_key)
        # Don't do any intensive checking here; index() will do that
        return redirect(url_for("main_blueprint.index", key=user_provided_key), code=301)
    return redirect(url_for("main_blueprint.index"), code=301)


@bp.app_errorhandler(404)
def page_not_found(err):
    return render_template("404.html"), 404


################################
################################

app = Flask(__name__)
app.config["APPLICATION_ROOT"] = URL_PREFIX
app.register_blueprint(bp, url_prefix=URL_PREFIX)


if __name__ == "__main__":
    app.run()
