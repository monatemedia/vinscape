# app/models/wmi.py
from app import db # Assuming 'db' is initialized in app/__init__.py
from sqlalchemy_serializer import SerializerMixin
from sqlalchemy.orm import relationship

class WmiRegionCode(db.Model, SerializerMixin):
    __tablename__ = 'wmi_region_codes'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(2), nullable=False) # e.g., 'A', '1A'
    country_id = db.Column(db.Integer, db.ForeignKey('countries.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    # Ensure the combination of code and country_id is unique
    __table_args__ = (
        db.UniqueConstraint('code', 'country_id', name='_code_country_uc'),
    )

    # Relationship to Country model
    country = relationship("Country", back_populates="wmi_codes")

    def __repr__(self):
        return f"<WmiRegionCode {self.code} for {self.country.common_name if self.country else 'N/A'}>"