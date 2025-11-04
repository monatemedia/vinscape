# app/models/wmi_region.py
from app import db
from sqlalchemy_serializer import SerializerMixin
from sqlalchemy.orm import relationship

class WmiRegion(db.Model, SerializerMixin):
    __tablename__ = 'wmi_regions' # Renamed table

    id = db.Column(db.Integer, primary_key=True)
    
    # The 2-character WMI code (e.g., 'ZA', '1F', 'R1')
    code = db.Column(db.String(2), unique=True, nullable=False)
    
    # Link to the Country/Region table
    country_id = db.Column(db.Integer, db.ForeignKey('countries.id'), nullable=False)
    country = relationship("Country", back_populates="wmi_codes") 
    
    # Status flag
    is_active = db.Column(db.Boolean, default=True)
    # created_at column REMOVED

    def __repr__(self):
        return f"<WmiRegion {self.code} -> {self.country.common_name}>"