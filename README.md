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
python main.py

# Press CTRL+C to close the development server

# Deactivate when done
deactivate
```

2. Create a file named `secrets.json` and populate it with the following data:
```
{
  "C2C_DCV_API_TOKEN": "(API token for the REDCap project created for this experiment, titled 'C2C - Retention - Discrete Choice Video')",
  "REDCAP_API_URL": "(Our REDCap API URL; can be found in any project's API Playground)"
}
```

3. Create a CSV file named `c2cv3-ids-access-keys.csv` in the `/content` folder. This CSV should be a spreadsheet containing 2 columns: `record_id` (containing C2Cv3 record IDs) and `access_key` (hashed strings derived from these IDs generated specially for this project; used as record IDs for the REDCap project specific to this survey/experiment). Each C2C record ID should correspond to the access key in its row.

## Other info

Participant access keys were generated using [this script](https://github.oit.uci.edu/mind/c2c-generate-unique-ids) (accessible to MIND staff only) and these parameters:
* `HASH_SALT_PREFIX = "retention_dce"`
* `HASHED_ID_LENGTH = 12`
* `REDCAP_HASHED_ID_VARIABLE = "proj_pid_813"`
* `REDCAP_INSTRUMENT = "projects"`

Old variables that _used_ to be required in `secrets.json`:
```
"C2CV3_API_TOKEN": "(API token for the main C2C project 'Consent to Contact (C2Cv3)')",
"C2CV3_EMAILS_REPORT_ID": "(numeric ID of the report in the C2Cv3 project titled 'Full Email List (+Current -Withdraw)')",
"C2CV3_TO_ACCESS_KEYS_REPORT_ID": "(numeric ID of the report in the C2Cv3 project titled 'PROJECT C2C DCV - Access keys (+Current -Withdraw)')",
"MAIL_SMTP_SERVER_ADDR": "mind.uci.edu",
"MAIL_C2C_NOREPLY_ADDR": "noreply@c2c.uci.edu",
"MAIL_C2C_NOREPLY_DISPLAY_NAME": "UCI C2C Registry",
"MAIL_C2C_NOREPLY_PASS": "(ask your supervisor)"
```
* "_REPORT_ID" values can be found in the URL when their corresponding reports are accessed in REDCap.
  * Example (the report ID is the group of "#####" characters): `.../redcap_v__.__.__/DataExport/index.php?pid=__&report_id=#####`
* The app now expects C2C IDs and access keys to be stored in a local CSV file, so nothing needed regarding the main C2Cv3 REDCap project.
* Reminder emails were removed from the requirements, so all mail-related keys are no longer needed either.

## Client Application Requirements:
* Valid C2C email
* Participant can only do the survey once
* Participant can only vote if both videos have been viewed
* Goal: Capture how many times a video was watched
* Goal: Capture what device was used - capture user agent
