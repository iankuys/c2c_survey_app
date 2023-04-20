# Standalone script to generate "access keys" (hashed IDs) of C2C participants.
# Outputs a CSV file that could be imported to a new REDCap project for a given experiment/initiative.

import csv
import hashlib

import requests

import mindlib
import redcap_helpers

# The name of the CSV file that will be written
CSV_FILENAME = "c2c_hashed_ids.csv"

# If False, hashed IDs of participants that have withdrawn from the study will NOT be written to the CSV
# Default: False
INCLUDE_WITHDRAWN_PARTICIPANTS = False

###########################
### Options for hashing ###

# String to prepend to the C2C record ID before hashing
# Different experiments should have different prefixes to make their generated IDs different
HASH_SALT_PREFIX = "retention_dce"

# Truncate hashed IDs to this length
# Each character increases the total amount of possible hashes by a factor of 16
# 1 char = 16 possible hashes
# 2 chars = 16*16 = 256 possible hashes
# 3 chars = 16^3 = 4096 possible hashes, etc...
HASHED_ID_LENGTH = 12

################################################################################
### Options concerning the NEW REDCap project for this experiment/initiative ###

# REDCap variable name that will contain the hashed ID
REDCAP_HASHED_ID_VARIABLE = "proj_pid_813"

# REDCap instrument that contains `REDCAP_HASHED_ID_VARIABLE` (can be found in the project's Codebook)
REDCAP_INSTRUMENT = "projects"


def export_original_c2c_ids(api_token: str, api_url: str) -> list[str]:
    """Returns a list of all record IDs in the main C2C REDCap project."""
    data = {
        "token": api_token,
        "content": "record",
        "action": "export",
        "format": "json",
        "type": "flat",
        "csvDelimiter": "",
        "fields[0]": "record_id",
        "events[0]": "enroll_arm_1",
        "rawOrLabel": "raw",
        "rawOrLabelHeaders": "raw",
        "exportCheckboxLabel": "false",
        "exportSurveyFields": "false",
        "exportDataAccessGroups": "false",
        "returnFormat": "json",
    }
    r = requests.post(api_url, data=data)
    # print("HTTP Status: " + str(r.status_code))
    response_dict = r.json()
    return [r["record_id"] for r in response_dict if "record_id" in r]


def hash_one_string(
    input_string: str, length=64, salt_prefix: str = "", salt_suffix: str = ""
) -> str:
    """Creates a SHA-256 hash digest for a given string (default length is the maximum of 64 digits).
    If length < 64, the resulting digest is truncated to that amount of digits.
    If length >= 64, the resulting digest will remain 64 digits long.
    Provide strings to salt_prefix and/or salt_suffix as necessary to produce different hashes."""
    h = hashlib.new("sha256")

    to_hash = f"{salt_prefix}{input_string}{salt_suffix}"
    h.update(to_hash.encode())

    result = h.hexdigest()
    return result[:length]


def create_hashed_ids(
    ids: list[str], hashed_id_length: int, pre_hash_prefix: str, max_retry_count=8
) -> dict[str:str]:
    """Returns a dictionary that maps SHA256-hashed IDs to their source C2C IDs."""
    hashes_to_original_ids = dict()
    for record_id in ids:
        the_hash = hash_one_string(record_id, length=hashed_id_length, salt_prefix=pre_hash_prefix)
        # print(f"Hashed {id} to {the_hash}")

        # Check for duplicates and retry, updating the salt for the newest ID along the way
        retry_count = 0
        while the_hash in hashes_to_original_ids and retry_count <= max_retry_count:
            retry_count += 1
            print(
                f"   Collision found: {the_hash} (IDs {record_id} and {hashes_to_original_ids[the_hash]}), retrying (attempt {retry_count})"
            )
            the_hash = hash_one_string(
                record_id,
                length=hashed_id_length,
                salt_prefix=pre_hash_prefix,
                salt_suffix=str(retry_count),
            )
        if retry_count >= max_retry_count:
            print(
                f"Failed to hash ID {record_id}, not adding to the CSV (tried {max_retry_count} times)"
            )
            continue

        hashes_to_original_ids[the_hash] = record_id

    return hashes_to_original_ids


def write_csv(
    csv_filename: str,
    hashes_to_original_ids: dict[str:str],
    current_ids: set[str],
    hashed_id_column_name: str,
    redcap_instrument: str,
    include_withdrawn_users: bool,
    redcap_instrument_completion: str = "1",
) -> None:
    """Write the CSV to contain the complete mapping of C2C ID to the new hashed IDs."""
    if redcap_instrument_completion not in ["0", "1", "2"]:
        # "0" = "Incomplete", red light in REDCap
        # "1" = "Unverified", yellow light in REDCap
        # "2" = "Complete", green light in REDCap
        raise ValueError(
            f'REDCap instrument completion can only be "1", "2", or "3" (got "{redcap_instrument_completion}")'
        )

    with open(csv_filename, "w+", newline="") as outfile:
        instrument_completion_variable_name = f"{redcap_instrument}_complete"
        fieldnames = [
            "record_id",
            "redcap_event_name",
            hashed_id_column_name,
            instrument_completion_variable_name,
        ]
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)

        writer.writeheader()
        for hashed_id in hashes_to_original_ids:
            row_to_write = {
                "record_id": hashes_to_original_ids[hashed_id],
                "redcap_event_name": "status_arm_1",
                hashed_id_column_name: hashed_id,
                instrument_completion_variable_name: redcap_instrument_completion,
            }
            if (
                not include_withdrawn_users
                and hashes_to_original_ids[hashed_id] not in current_ids
            ):
                # This participant withdrew from the study
                row_to_write[hashed_id_column_name] = ""
                row_to_write[instrument_completion_variable_name] = "0"
            writer.writerow(row_to_write)
    return


if __name__ == "__main__":
    secrets = mindlib.json_to_dict(
        "secrets.json", required_fields={"C2CV3_API_TOKEN", "REDCAP_API_URL"}
    )
    print("Getting all IDs from the C2C REDCap project....")
    all_ids = export_original_c2c_ids(secrets["C2CV3_API_TOKEN"], secrets["REDCAP_API_URL"])
    print("Getting active IDs from the C2C REDCap project....")
    current_c2c_ids = {
        r["record_id"]
        for r in redcap_helpers.export_redcap_report(
            secrets["C2CV3_API_TOKEN"],
            secrets["REDCAP_API_URL"],
            secrets["C2CV3_EMAILS_REPORT_ID"],
        )
    }

    print("Hashing IDs....")
    hashed_ids = create_hashed_ids(all_ids, HASHED_ID_LENGTH, HASH_SALT_PREFIX)
    print(f"Hashed {len(hashed_ids)}/{len(all_ids)} IDs ({len(hashed_ids)/len(all_ids)*100:.2f}%)")

    # Build a CSV of "record_id" and hashed IDs that can be imported to the new REDCap project for this experiment
    write_csv(
        CSV_FILENAME,
        hashed_ids,
        current_c2c_ids,
        REDCAP_HASHED_ID_VARIABLE,
        REDCAP_INSTRUMENT,
        INCLUDE_WITHDRAWN_PARTICIPANTS,
    )
    print(f"\nWrote '{CSV_FILENAME}'")
