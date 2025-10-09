from odoo import models, fields


class AccountPaymentTerm(models.Model):
    _inherit = "account.payment.term"

    installment_amount = fields.Float(string="Installment Markup Amount")
    product_ids = fields.Many2many('product.template', string="Allowed Products", help="Select products linked to this payment term.")