from app import db


class Cultivar(db.Model):
    __tablename__ = 'cultivar'

    id = db.Column(db.Integer, primary_key=True)
    cultivar = db.Column(db.String(200), nullable=False)
    epithet = db.Column(db.String(300), default='')
    category = db.Column(db.String(20), default='')
    color_form = db.Column(db.String(200), default='')
    tagline = db.Column(db.Text, default='')
    description = db.Column(db.Text, default='')
    notes = db.Column(db.Text, default='')
    image_url = db.Column(db.String(500), default='')
    photo_url = db.Column(db.String(500), default='')

    def to_dict(self):
        return {
            'id': self.id,
            'cultivar': self.cultivar,
            'epithet': self.epithet,
            'category': self.category,
            'color_form': self.color_form,
            'tagline': self.tagline,
            'description': self.description,
            'notes': self.notes,
            'image_url': self.image_url,
            'photo_url': self.photo_url,
        }
