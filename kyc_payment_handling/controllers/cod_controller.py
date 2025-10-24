from odoo import http
from odoo.addons.website_sale.controllers.main import WebsiteSale
import logging
import pprint
from odoo.http import Controller, request, route

_logger = logging.getLogger(__name__)

class CustomController(Controller):
    _process_url = '/payment/cod/process'

    @route(_process_url, type='http', auth='public', methods=['POST'], csrf=False)
    def custom_process_transaction(self, **post):
        _logger.info("Handling COD processing with data:\n%s", pprint.pformat(post))

        tx_env = request.env['payment.transaction'].sudo()
        tx = tx_env.search([('reference', '=', post.get('reference'))], limit=1)

        if tx:
            tx._set_done()
            tx._post_process_after_done()

        return request.redirect('/shop/confirmation')

class WebsiteSaleCOD(WebsiteSale):

    @http.route(['/shop/payment/transaction/<int:transaction_id>'], type='http', auth='public', website=True, csrf=False)
    def payment_transaction(self, transaction_id, **kwargs):
        """Override to handle Cash on Delivery confirmation"""
        tx = request.env['payment.transaction'].sudo().browse(transaction_id)
        if not tx:
            return request.not_found()

        # ✅ If provider is COD, confirm order directly
        if tx.provider_code == 'cod':
            order = tx.sale_order_ids and tx.sale_order_ids[0] or None
            if order:
                # Confirm the order
                order.action_confirm()

                # Mark transaction as done
                tx._set_done()

                # Redirect to confirmation page
                return request.redirect(f'/shop/confirmation/{order.id}')

        # Else use normal payment flow
        return super(WebsiteSaleCOD, self).payment_transaction(transaction_id, **kwargs)
