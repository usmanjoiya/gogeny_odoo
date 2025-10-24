from odoo import _, api, fields, models

class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('cod', "Cash on Delivery")],
        ondelete={'cod': 'set default'},
    )

    def _get_default_cod_message(self):
        return _("""
            <div>
                <h5>Cash on Delivery Instructions</h5>
                <p>You will pay when the products are delivered to your address.</p>
                <p>Please ensure you have the exact amount ready for our delivery personnel.</p>
            </div>
        """)

    # 🧠 Tells Odoo which URL to hit after clicking "Pay Now"
    def _get_validation_url(self):
        self.ensure_one()
        if self.code == 'cod':
            return '/payment/cod/process'
        return super()._get_validation_url()

    # 🧠 Tells Odoo that COD is direct (no redirect or tokenization)
    def _get_payment_flow(self):
        self.ensure_one()
        if self.code == 'cod':
            return 'direct'
        return super()._get_payment_flow()

    # Optional – ensure message is there
    def action_recompute_pending_msg(self):
        for provider in self.filtered(lambda p: p.code == 'cod'):
            provider.pending_msg = self._get_default_cod_message()

    def _transfer_ensure_pending_msg_is_set(self):
        providers_without_msg = self.filtered(
            lambda p: p.code == 'cod' and not p.pending_msg
        )
        if providers_without_msg:
            providers_without_msg.action_recompute_pending_msg()
