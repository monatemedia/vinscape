# app/models/factory_logo.py
from app import db
from sqlalchemy_serializer import SerializerMixin
from sqlalchemy.orm import relationship

class FactoryLogo(db.Model, SerializerMixin):
    __tablename__ = 'factory_logos'

    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign key to WmiFactory
    factory_id = db.Column(db.Integer, db.ForeignKey('wmi_factories.id', ondelete='CASCADE'), nullable=False)
    
    # Filename saved in the output directory (e.g., 'ford.png')
    logo_filename = db.Column(db.String(255), nullable=False)
    
    # Relationship to the factory model
    factory = relationship("WmiFactory", backref=db.backref('logos', lazy=True, cascade="all, delete-orphan"))
    
    # Ensure a factory only has a logo file listed once
    __table_args__ = (db.UniqueConstraint('factory_id', 'logo_filename'),)

    def __repr__(self):
        return f"<FactoryLogo {self.logo_filename} for Factory ID {self.factory_id}>"