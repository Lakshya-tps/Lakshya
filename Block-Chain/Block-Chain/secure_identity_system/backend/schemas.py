from pydantic import BaseModel, ValidationError, field_validator


def normalize_email(value):
    email = value.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValueError("Enter a valid email address.")
    return email


class CapturePayload(BaseModel):
    image: str

    @field_validator("image")
    @classmethod
    def validate_image(cls, value):
        if not value or not value.strip():
            raise ValueError("Capture image is required.")
        return value.strip()


class RegisterPayload(CapturePayload):
    name: str
    email: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("Full name must be at least 2 characters.")
        return cleaned

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        return normalize_email(value)


class LoginPayload(CapturePayload):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        return normalize_email(value)


class AdminRegisterPayload(RegisterPayload):
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        if len(value) < 6:
            raise ValueError("Password must be at least 6 characters.")
        return value


class AdminLoginPayload(LoginPayload):
    password: str


def validation_errors(exc: ValidationError):
    errors = []
    for error in exc.errors():
        location = ".".join(str(item) for item in error["loc"])
        errors.append({"field": location, "message": error["msg"]})
    return errors
