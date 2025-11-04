# app/models/wmi_factory.py
from app import db 
from sqlalchemy_serializer import SerializerMixin
from sqlalchemy.orm import relationship 

class WmiFactory(db.Model, SerializerMixin):
    __tablename__ = 'wmi_factories' # Renamed table

    id = db.Column(db.Integer, primary_key=True)
    
    # WMI: World Manufacturer Identifier (the first 3 characters of a VIN)
    wmi = db.Column(db.String(3), unique=True, nullable=False)
    
    # Manufacturer details
    name = db.Column(db.String(128), nullable=False)
    
    # Link to the Country table (Optional Foreign Key)
    country_id = db.Column(db.Integer, db.ForeignKey('countries.id'), nullable=True)
    country = relationship("Country") 
    
    # Region name (for regions like 'Asia' where there's no specific country)
    region = db.Column(db.String(64)) 
    
    # Status flags
    is_active = db.Column(db.Boolean, default=True)
    # created_at column REMOVED

    def __repr__(self):
        return f"<WmiFactory {self.wmi} ({self.name})>"

    @classmethod
    def find_by_wmi(cls, wmi_code):
        return cls.query.filter(cls.wmi == wmi_code.upper()).first()