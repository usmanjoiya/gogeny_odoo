from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    customer_reference = fields.Char(
        string="Customer Reference",
        help="Unique reference or code for this customer."
    )

    _sql_constraints = [
        (
            'unique_customer_reference',
            'unique(customer_reference)',
            'The Customer Reference must be unique.'
        )
    ]
