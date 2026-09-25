from src.core.database import db

class DetalleVersionOferta(db.Model):
    __tablename__ = 'detalle_version_oferta'

    id_detalle = db.Column(db.Integer, primary_key=True)
    id_version = db.Column(db.Integer, db.ForeignKey('version_ofertas.id_version'), nullable=False)
    id_ong = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    id_recurso = db.Column(db.Integer, db.ForeignKey('inventario_ong.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    cantidad_adjudicada = db.Column(db.Integer, nullable=True)

    version = db.relationship(
        'OfertaVersion',
        back_populates='detalles'
    )

    ong = db.relationship(
        'Usuario',
        foreign_keys=[id_ong]
    )

    recurso = db.relationship(
        'InventarioONG',
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
    )

    def __repr__(self):
        return f'<DetalleVersionOferta {self.id_detalle} - Version: {self.id_version} - Recurso: {self.id_recurso}>'