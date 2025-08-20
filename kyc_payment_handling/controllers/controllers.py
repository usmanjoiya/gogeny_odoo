from odoo import http
from odoo.http import request

class CookPayController(http.Controller):

    @http.route('/cookpay', type='http', auth='public', website=True)
    def cookpay_page(self, **kw):
        return request.render('kyc_payment_handling.cookpay_template', {})

    @http.route('/cookpay/search', type='http', auth='public', website=True, methods=['POST'], csrf=False)
    def cookpay_search(self, **post):
        reference = post.get('customer_reference')
        partner = request.env['res.partner'].sudo().search([('customer_reference', '=', reference)], limit=1)

        if partner:
            invoice = request.env['account.move'].sudo().search([
                ('partner_id', '=', partner.id),
                ('move_type', '=', 'out_invoice'),
                ('payment_state', 'in', ['not_paid', 'partial'])
            ], order="invoice_date desc", limit=1)

            if invoice:
                invoice_portal_url = '/my/invoices/%s?access_token=%s' % (invoice.id, invoice._portal_ensure_token())
                return request.redirect(invoice_portal_url)
            else:
                return request.render('kyc_payment_handling.cookpay_template', {
                    'error_message': "No Unpaid Invoice Found.",
                })

        return request.render('kyc_payment_handling.cookpay_template', {
            'error_message': "Customer with this reference not found."
        })
