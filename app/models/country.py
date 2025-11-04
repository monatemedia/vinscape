# app/models/country.py
from app import db # Assuming 'db' is initialized in app/__init__.py
from sqlalchemy_serializer import SerializerMixin
from sqlalchemy.orm import relationship

class Country(db.Model, SerializerMixin):
    __tablename__ = 'countries'

    id = db.Column(db.Integer, primary_key=True)
    iso_alpha2 = db.Column(db.String(2), unique=True, nullable=False)
    iso_alpha3 = db.Column(db.String(3), unique=True)
    iso_numeric = db.Column(db.String(3))
    name = db.Column(db.String(128), nullable=False)
    common_name = db.Column(db.String(128))
    region = db.Column(db.String(64))
    subregion = db.Column(db.String(64))
    currency_code = db.Column(db.String(10))
    calling_code = db.Column(db.String(10))
    tld = db.Column(db.String(10))
    flag_emoji = db.Column(db.String(16))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    # Relationship to WmiRegionCode
    wmi_codes = relationship("WmiRegionCode", back_populates="country")

    def __repr__(self):
        return f"<Country {self.common_name} ({self.iso_alpha2})>"

    # Helper function to find a country by name
    @classmethod
    def find_by_name(cls, name):
        # Use common_name for robust lookup
        return cls.query.filter(
            db.func.lower(cls.common_name) == db.func.lower(name)
        ).first()

    # Helper function to find by ID (optional, but good practice)
    @classmethod
    def find_by_id(cls, id):
        return cls.query.get(id)