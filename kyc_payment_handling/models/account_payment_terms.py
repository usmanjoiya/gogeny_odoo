from odoo import models, fields


class AccountPaymentTerm(models.Model):
    _inherit = "account.payment.term"

    installment_amount = fields.Float(string="Installment Markup Amount")