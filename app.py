from flask import Blueprint, Flask, redirect, render_template, request, url_for

################################
############ CONFIG ############

URL_PREFIX = "/c2c-dvc"

################################
############ STARTUP ###########

# Use a Blueprint to prepend URL_PREFIX to all applicable pages
bp = Blueprint(
    "main_blueprint", __name__, static_folder="static", template_folder="templates"
)

################################
########### ENDPOINTS ##########
# http://127.0.0.1:5000/c2c-dvc/


@bp.route("/", methods=["GET"])
def index():
    # Get hashed C2C ID from URL parameter "id"
    return render_template("index.html")


################################
################################

app = Flask(__name__)
app.config["APPLICATION_ROOT"] = URL_PREFIX
app.register_blueprint(bp, url_prefix=URL_PREFIX)


if __name__ == "__main__":
    app.run()
