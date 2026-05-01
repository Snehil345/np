import requests
from flask import Flask, render_template, request, Response
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")


def make_error(title, detail, fix=None):
    return {"title": title, "detail": detail, "fix": fix}


def check_credentials():
    if not TWILIO_ACCOUNT_SID:
        return False
    if not TWILIO_AUTH_TOKEN:
        return False
    if not TWILIO_ACCOUNT_SID.startswith("AC"):
        return False
    return True


def twilio_lookup(phone, country_code=''):
    url = f"https://lookups.twilio.com/v2/PhoneNumbers/{requests.utils.quote(phone)}"

    params = {
        "Fields": "line_type_intelligence,caller_name"
    }

    if country_code:
        params["CountryCode"] = country_code.upper()

    resp = requests.get(
        url,
        params=params,
        auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
        timeout=12
    )

    return resp.status_code, resp.json()


def parse_twilio(raw):

    lti = raw.get("line_type_intelligence") or {}
    caller_data = raw.get("caller_name") or {}

    caller_name = caller_data.get("caller_name") if caller_data else None
    caller_type = caller_data.get("caller_type") if caller_data else None

    country_code = raw.get("country_code", "")

    country_names = {
        "IN":"India",
        "US":"United States",
        "GB":"United Kingdom",
        "AU":"Australia",
        "CA":"Canada"
    }

    country_name = country_names.get(country_code, country_code)

    return {
        "valid": raw.get("valid", False),
        "num": raw.get("phone_number", ""),
        "intl_format": raw.get("phone_number", ""),
        "national_format": raw.get("national_format", ""),
        "calling_country_code": raw.get("calling_country_code", ""),
        "country_code": country_code,
        "country_name": country_name,
        "carrier": lti.get("carrier_name") or "—",
        "line_type": lti.get("type") or "—",
        "caller_name": caller_name,
        "caller_type": caller_type,
        "_raw": raw,
        "_lti": lti,
        "_caller": caller_data,
    }


def build_report(d, now):

    sep = "=" * 60

    lines = []

    lines.append(sep)
    lines.append("PHONE TRACE REPORT")
    lines.append(sep)

    lines.append(f"Generated : {now}")
    lines.append(f"Valid     : {d['valid']}")
    lines.append(f"Number    : {d['num']}")
    lines.append(f"Country   : {d['country_name']}")
    lines.append(f"Carrier   : {d['carrier']}")
    lines.append(f"Line Type : {d['line_type']}")

    if d['caller_name']:
        lines.append(f"Caller    : {d['caller_name']}")

    lines.append(sep)

    return "\n".join(lines)


def get_params():
    return (
        request.args.get('n', '').strip(),
        request.args.get('cc', '').strip(),
    )


@app.route('/')
def index():

    return render_template(
        "index.html",
        data=None,
        error=None,
        report="",
        form={"n": "", "cc": ""},
        cred_error=False
    )


@app.route('/scan')
def scan():

    num, cc = get_params()

    form = {"n": num, "cc": cc}

    cred_ok = check_credentials()

    if not num:
        return render_template(
            "index.html",
            data=None,
            error=None,
            report="",
            form=form,
            cred_error=not cred_ok
        )

    try:
        status, raw = twilio_lookup(num, cc)

    except Exception as e:

        err = make_error("Connection Error", str(e))

        return render_template(
            "index.html",
            data=None,
            error=err,
            report="",
            form=form,
            cred_error=False
        )

    if status != 200:

        err = make_error(
            f"Twilio Error ({status})",
            raw.get("message", "Unknown Error")
        )

        return render_template(
            "index.html",
            data=None,
            error=err,
            report="",
            form=form,
            cred_error=False
        )

    d = parse_twilio(raw)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = build_report(d, now)

    return render_template(
        "index.html",
        data=d,
        report=report,
        error=None,
        form=form,
        cred_error=False
    )


@app.route('/report')
def plain_report():

    num, cc = get_params()

    status, raw = twilio_lookup(num, cc)

    d = parse_twilio(raw)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = build_report(d, now)

    return Response(report, mimetype='text/plain')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)