# c2c-discrete-choice-video

Written with Python 3.11.3.

## Dev environment set up

1. Create a virtual environment for developing this app (example with PowerShell on Windows 11):
```
# Navigate to this repository's root folder

# Create a Python virtual environment (only need to do this once):
python -m venv .venv

# Activate the virtual environment:
.\.venv\Scripts\Activate.ps1
# On Windows: .ps1 for PowerShell or .bat for Command Prompt

# If using PowerShell and "running scripts is disabled on this system", need to
# enable running external scripts. Open PowerShell as admin and use this command:
set-executionpolicy remotesigned
# (only need to do this once)

# While in the virtual env, update pip and install packages (only need to do this once):
python -m pip install --upgrade pip
pip install -r requirements.txt

# Run the script: develop, debug, etc.
python app.py

# Press CTRL+C to close the development server

# Deactivate when done
deactivate
```

2. Create a file named `secrets.json` and populate it with the following data:
```
{
    "C2CV3_API_TOKEN": "API token for the main C2C project 'Consent to Contact (C2Cv3)'",
    "C2CV3_ALL_EMAILS_REPORT_ID": "numeric ID of the report in the C2Cv3 project titled 'Full Email List (+Current -Withdraw)'",
    "C2C_DCV_API_TOKEN": "API token for the REDCap project created for this experiment, titled 'C2C - Retention - Discrete Choice Video'",
    "C2C_DCV_TO_ACCESS_KEYS_REPORT_ID": "numeric ID of the report in the C2C-DCV project titled 'C2C IDs to Access Keys'",
    "REDCAP_API_URL": "Our REDCap API URL; can be found in any project's API Playground"
}
```
* The "C2CV3" keys are used when a user inputs their email address to be reminded of their access key for this experiment.
* The "C2C_DCV" keys are the main keys used throughout the app. Their corresponding REDCap project is where all of this experiment's data will be stored.
* "_REPORT_ID" values can be found in the URL when their corresponding reports are accessed in REDCap.
  * Example (the report ID is the group of "#####" characters): `.../redcap_v__.__.__/DataExport/index.php?pid=__&report_id=#####`
