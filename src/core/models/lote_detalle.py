from src.core.database import db


class LoteDetalle(db.Model):
    __tablename__ = 'lote_detalles'

    id = db.Column(db.Integer, primary_key=True)
    lote_id = db.Column(db.Integer, db.ForeignKey('lotes_necesidades.id'), nullable=False, index=True)
    id_recurso = db.Column(db.Integer, db.ForeignKey('recursos_catalogo.id'), nullable=False)
    cantidad_necesaria = db.Column(db.Integer, nullable=False)
    cantidad_minima = db.Column(db.Integer, nullable=False)

    lote = db.relationship('LoteNecesidades', back_populates='detalles')
    recurso = db.relationship('RecursoCatalogo', back_populates='detalles_lote')

    def __repr__(self):
        return f'<LoteDetalle {self.id} - Lote: {self.lote_id}>'