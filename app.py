from flask import Blueprint, Flask, redirect, render_template, request, url_for

################################
############ CONFIG ############

URL_PREFIX = "/c2c-retention-dce"

################################
############ STARTUP ###########

# Use a Blueprint to prepend URL_PREFIX to all applicable pages
bp = Blueprint(
    "main_blueprint", __name__, static_folder="static", template_folder="templates"
)

################################
############ HELPERS ###########

def sanitize_key(key_from_html_string: str) -> str:
    result = key_from_html_string
    # TODO
    return result.strip()

################################
########### ENDPOINTS ##########
# http://127.0.0.1:5000/c2c-retention-dce/


@bp.route("/", methods=["GET"])
def index():
    if ("key" in request.args and len(request.args["key"]) > 0):
        hashed_id = sanitize_key(request.args["key"])
        # Check if hashed_id is valid
        return render_template("index.html", key=hashed_id)
    return render_template("index.html")

@bp.route("/check", methods=["GET", "POST"])
def check():
    # Endpoint that receives data from a user that manually input their key (hashed ID)
    # to an HTML form on "/"
    # Redirect to "/" with that key to check
    return redirect(url_for("main_blueprint.index"), code=302)

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
