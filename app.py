import boto3
import json
import uuid
from flask import Flask, redirect, url_for, request, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy

# Create the Flask app globally
app = Flask(__name__)

# Set allowed file types
ALLOWED_EXTENSIONS = {"txt", "pdf", "png", "jpg", "jpeg", "bmp"}

# Configure the SQLAlchemy database
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite3"
db = SQLAlchemy(app)


# Define the file model
class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_filename = db.Column(db.String(100))
    filename = db.Column(db.String(100))
    bucket = db.Column(db.String(100))
    region = db.Column(db.String(100))


# Helper function to check allowed file types
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# Root route
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            uploaded_file = request.files["file-to-save"]
            if not allowed_file(uploaded_file.filename):
                return "FILE NOT ALLOWED!"

            # Generate a unique filename
            new_filename = (
                uuid.uuid4().hex
                + "."
                + uploaded_file.filename.rsplit(".", 1)[1].lower()
            )

            # Upload to S3
            bucket_name = "s3_bucket_name"
            s3 = boto3.resource("s3")
            s3.Bucket(bucket_name).upload_fileobj(uploaded_file, new_filename)

            # Save file info in the database
            file = File(
                original_filename=uploaded_file.filename,
                filename=new_filename,
                bucket=bucket_name,
                region="ap-southeast-1",
            )
            db.session.add(file)
            db.session.commit()

            # Invoke Lambda function
            lambda_client = boto3.client("lambda", region_name="ap-southeast-1")
            payload = {"bucket": bucket_name, "photo": new_filename}
            response = lambda_client.invoke(
                FunctionName="lambda_name",  # Replace with your Lambda function's name
                InvocationType="RequestResponse",  # Synchronous invocation
                Payload=json.dumps(payload),
            )

            # Read and process the Lambda response
            response_payload = response["Payload"].read().decode("utf-8")
            lambda_response = json.loads(response_payload)
            body = json.loads(lambda_response["body"])

            # Extract detected text
            if body:
                first_detected_text = body[0]
                detected_texts = [
                    {
                        "text": first_detected_text["DetectedText"],
                        "confidence": first_detected_text["Confidence"],
                    }
                ]
            else:
                detected_texts = []

            return render_template(
                "index.html", files=File.query.all(), detected_texts=detected_texts
            )

        except Exception as e:
            print(f"Error: {e}")
            return jsonify({"error": str(e)}), 500

    return render_template("index.html", files=File.query.all())


# Run the app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
