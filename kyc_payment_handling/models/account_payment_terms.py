from odoo import models, fields
from dateutil.relativedelta import relativedelta


class AccountPaymentTerm(models.Model):
    _inherit = "account.payment.term"

    installment_amount = fields.Float(string="Installment Markup Amount")
    product_ids = fields.Many2many('product.template', string="Allowed Products", help="Select products linked to this payment term.")


class AccountPaymentTermLine(models.Model):
    _inherit = "account.payment.term.line"

    def _get_due_date(self, date_ref):
        # Month arithmetic instead of "+nb_days then snap to day-of-month",
        # so each line lands on a distinct (year, month, day) and
        # account.move._compute_needed_terms has nothing to merge.
        self.ensure_one()
        if self.delay_type == 'days_end_of_month_on_the':
            invoice_date = fields.Date.from_string(date_ref) or fields.Date.today()
            try:
                target_day = int(self.days_next_month)
            except (TypeError, ValueError):
                target_day = 1
            months_offset = round((self.nb_days or 0) / 30) + 1
            if target_day == 0:
                return (invoice_date + relativedelta(months=months_offset)) + relativedelta(day=31)
            return invoice_date + relativedelta(months=months_offset, day=target_day)
        return super()._get_due_date(date_ref)