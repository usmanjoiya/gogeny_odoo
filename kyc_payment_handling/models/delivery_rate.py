from odoo import fields, models


class KycDeliveryRate(models.Model):
    _name = "kyc.delivery.rate"
    _description = "Delivery/Shipping Rate by Region"
    _order = "country_id, state_id, name"

    name = fields.Char(required=True)
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id.id,
        required=True,
    )
    amount = fields.Monetary(currency_field="currency_id")
    country_id = fields.Many2one("res.country", string="Country")
    state_id = fields.Many2one(
        "res.country.state",
        string="State",
        domain="[('country_id', '=?', country_id)]",
    )
