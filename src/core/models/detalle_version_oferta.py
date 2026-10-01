from src.core.database import db
from sqlalchemy.orm import synonym

class DetalleVersionOferta(db.Model):
    __tablename__ = 'detalle_version_oferta'

    id = db.Column(db.Integer, primary_key=True)
    id_detalle = synonym('id')
    id_version = db.Column(db.Integer, db.ForeignKey('version_ofertas.id'), nullable=False)
    id_ong = db.Column(db.Integer, db.ForeignKey('ongs.id'), nullable=False)
    id_recurso = db.Column(db.Integer, db.ForeignKey('recursos_catalogo.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    cantidad_adjudicada = db.Column(db.Integer, nullable=False, default=0)

    version = db.relationship(
        'VersionOferta',
        back_populates='detalles'
    )

    ong = db.relationship(
        'ONG',
        foreign_keys=[id_ong]
    )

    recurso = db.relationship(
        'RecursoCatalogo',
        foreign_keys=[id_recurso]
    )

    __table_args__ = (
        db.CheckConstraint(
            'cantidad > 0',
            name='chk_cantidad_positiva'
        ),
        db.CheckConstraint(
            'cantidad_adjudicada >= 0 AND cantidad_adjudicada <= cantidad',
            name='chk_cantidad_adjudicada'
        ),
        db.UniqueConstraint(
            'id_version', 'id_ong', 'id_recurso',
            name='uq_version_ong_recurso'
        ),
    )

    def __repr__(self):
        return f'<DetalleVersionOferta {self.id_detalle} - Version: {self.id_version} - Recurso: {self.id_recurso}>'