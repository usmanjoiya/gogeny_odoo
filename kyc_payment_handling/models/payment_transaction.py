from odoo import models


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    def _get_sale_order_downpayment(self, order):
        """Compute downpayment based on payment term."""
        if order.payment_term_id and order.payment_term_id.line_ids:
            first_line = order.payment_term_id.line_ids[0]
            if first_line.value == "percent":
                return (order.amount_total * first_line.value_amount) / 100.0
            elif first_line.value == "fixed":
                return first_line.value_amount
        return order.amount_total

    def _get_processing_values(self):
        """Override to use downpayment instead of full order total."""
        values = super()._get_processing_values()

        if self.sale_order_ids:
            order = self.sale_order_ids[0]
            downpayment_amount = self._get_sale_order_downpayment(order)
            values["amount"] = downpayment_amount
            self.amount = downpayment_amount  # update transaction amount

        return values
