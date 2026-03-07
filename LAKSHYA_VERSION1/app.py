from flask import Flask, render_template, request, jsonify, redirect, url_for
import os
import csv
import socket
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta

app = Flask(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
# Temporary defaults for manual verification.
# Keep environment variables in Render to override these values in deployment.
SMTP_USER = os.getenv("SMTP_USER", "lakshyatechprojects@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "qqwcxrieeazogytm")
NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL", "lakshyatechprojects@gmail.com")

def get_default_express_deadline():
    return (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")


def send_submission_email(form_name, payload):
    if not SMTP_USER or not SMTP_PASSWORD or not NOTIFICATION_EMAIL:
        raise ValueError("SMTP configuration is incomplete.")

    subject = f"[Lakshya] New {form_name} submission"
    lines = [
        f"Form: {form_name}",
        f"Submitted At (UTC): {payload.get('submitted_at', '')}",
        "",
    ]

    for key, value in payload.items():
        if key == "submitted_at":
            continue
        label = key.replace("_", " ").title()
        lines.append(f"{label}: {value}")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = SMTP_USER
    message["To"] = NOTIFICATION_EMAIL
    message.set_content("\n".join(lines))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(message)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/begin-discussion")
def begin_discussion():
    return render_template("intake.html")

@app.route("/express-delivery")
def express_delivery():
    return render_template(
        "express_delivery.html",
        default_deadline=get_default_express_deadline(),
    )

@app.route("/privacy")
@app.route("/terms")
@app.route("/contact")
def legal_contact():
    return render_template("legal_contact.html")

@app.route("/cropsight-crop-disease-detection")
@app.route("/sample-project-1")
def cropsight_project():
    return render_template(
        "sample_project_1.html",
        request_status=request.args.get("request_status", "")
    )

@app.route("/vita-ai-health-monitoring")
@app.route("/sample-project-2")
def vita_project():
    return render_template(
        "sample_project_2.html",
        request_status=request.args.get("request_status", "")
    )

@app.route("/nuerovista-ml-visualization")
@app.route("/sample-project-3")
def nuerovista_project():
    return render_template(
        "sample_project_3.html",
        request_status=request.args.get("request_status", "")
    )

@app.route("/submit-project-interest", methods=["POST"])
def submit_project_interest():
    data = request.form
    page_key = data.get("project_page", "cropsight-crop-disease-detection")

    endpoint_map = {
        "cropsight-crop-disease-detection": "cropsight_project",
        "vita-ai-health-monitoring": "vita_project",
        "nuerovista-ml-visualization": "nuerovista_project",
        "sample-project-1": "cropsight_project",
        "sample-project-2": "vita_project",
        "sample-project-3": "nuerovista_project",
    }
    redirect_endpoint = endpoint_map.get(page_key, "cropsight_project")

    payload = {
        "project_page": page_key,
        "project_title": data.get("project_title", ""),
        "name": data.get("name", ""),
        "email": data.get("email", ""),
        "phone": data.get("phone", ""),
        "message": data.get("message", ""),
        "submitted_at": datetime.utcnow().isoformat()
    }

    required = ["name", "email", "phone"]
    missing = [k for k in required if not payload.get(k)]
    if missing:
        return redirect(url_for(redirect_endpoint, request_status="missing"))

    data_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(data_dir, exist_ok=True)
    csv_path = os.path.join(data_dir, "project_interest_submissions.csv")

    file_exists = os.path.exists(csv_path)
    with open(csv_path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "submitted_at",
                "project_page",
                "project_title",
                "name",
                "email",
                "phone",
                "message",
            ],
        )
        if not file_exists:
            writer.writeheader()
        writer.writerow(payload)

    try:
        send_submission_email("Project Interest", payload)
        return redirect(url_for(redirect_endpoint, request_status="success"))
    except Exception:
        app.logger.exception("Failed to send Project Interest email notification.")
        return redirect(url_for(redirect_endpoint, request_status="mail_error"))

@app.route("/submit-discussion", methods=["POST"])
def submit_discussion():
    data = request.get_json(silent=True) or request.form
    payload = {
        "level": data.get("level", ""),
        "branch": data.get("branch", ""),
        "email": data.get("email", ""),
        "phone": data.get("phone", ""),
        "stage": data.get("stage", ""),
        "timeline": data.get("timeline", ""),
        "problem": data.get("problem", ""),
        "submitted_at": datetime.utcnow().isoformat()
    }

    # Server-side validation: ensure all fields present
    required = ["level", "branch", "email", "phone", "stage", "timeline", "problem"]
    missing = [k for k in required if not payload.get(k)]
    if missing:
        msg = "Please fill all fields before submitting."
        if request.is_json:
            return jsonify({"status": "error", "message": msg, "missing": missing}), 400
        return render_template("intake.html", submitted=False, error=msg, payload=payload)

    print("New Discussion Received:")
    print(payload)

    # Persist to CSV (data/submissions.csv)
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(data_dir, exist_ok=True)
    csv_path = os.path.join(data_dir, "submissions.csv")

    file_exists = os.path.exists(csv_path)
    with open(csv_path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["submitted_at", "level", "branch", "email", "phone", "stage", "timeline", "problem"]
        )
        if not file_exists:
            writer.writeheader()
        writer.writerow(payload)

    mail_sent = False
    notification_warning = None
    try:
        send_submission_email("Normal Discuss Page Form", payload)
        mail_sent = True
    except Exception:
        app.logger.exception("Failed to send Project Discussion email notification.")
        notification_warning = "Form submitted, but email notification could not be sent."

    if request.is_json:
        return jsonify({"status": "success", "data": payload, "mail_sent": mail_sent})

    return render_template(
        "intake.html",
        submitted=True,
        payload=payload,
        notification_warning=notification_warning,
    )

@app.route("/submit-express", methods=["POST"])
def submit_express():
    data = request.get_json(silent=True) or request.form
    fixed_deadline = get_default_express_deadline()
    payload = {
        "name": data.get("name", ""),
        "email": data.get("email", ""),
        "phone": data.get("phone", ""),
        "branch": data.get("branch", ""),
        "project_title": data.get("project_title", ""),
        # Deadline is fixed to T+2 days for Express protocol.
        "deadline": fixed_deadline,
        "requirements": data.get("requirements", ""),
        "submitted_at": datetime.utcnow().isoformat()
    }

    required = ["name", "email", "phone", "branch", "project_title", "deadline", "requirements"]
    missing = [k for k in required if not payload.get(k)]
    if missing:
        msg = "Please fill all fields before submitting Express Delivery."
        if request.is_json:
            return jsonify({"status": "error", "message": msg, "missing": missing}), 400
        return render_template(
            "express_delivery.html",
            submitted=False,
            error=msg,
            payload=payload,
            default_deadline=get_default_express_deadline(),
        )

    print("New Express Delivery Request:")
    print(payload)

    data_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(data_dir, exist_ok=True)
    csv_path = os.path.join(data_dir, "express_submissions.csv")

    file_exists = os.path.exists(csv_path)
    with open(csv_path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "submitted_at",
                "name",
                "email",
                "phone",
                "branch",
                "project_title",
                "deadline",
                "requirements",
            ],
        )
        if not file_exists:
            writer.writeheader()
        writer.writerow(payload)

    mail_sent = False
    notification_warning = None
    try:
        send_submission_email("Express Delivery Page Form", payload)
        mail_sent = True
    except Exception:
        app.logger.exception("Failed to send Express Delivery email notification.")
        notification_warning = "Form submitted, but email notification could not be sent."

    if request.is_json:
        return jsonify({"status": "success", "data": payload, "mail_sent": mail_sent})

    return render_template(
        "express_delivery.html",
        submitted=True,
        payload=payload,
        notification_warning=notification_warning,
        default_deadline=get_default_express_deadline(),
    )


if __name__ == "__main__":
    # Use port from env if provided (e.g. PORT=5001), otherwise default to 5001.
    # This avoids conflicts on macOS where port 5000 is often in use.
    port = int(os.getenv("PORT", "5001"))
    app.run(debug=True, host="0.0.0.0", port=port)
