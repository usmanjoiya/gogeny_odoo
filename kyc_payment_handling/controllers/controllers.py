from odoo import http
from odoo.http import request


class CookPayController(http.Controller):

    @http.route('/cookpay', type='http', auth='public', website=True)
    def cookpay_page(self, **kw):
        return request.render('kyc_payment_handling.cookpay_template', {})

    @http.route('/cookpay/search', type='http', auth='public', website=True, methods=['POST'], csrf=False)
    def cookpay_search(self, **post):
        reference = post.get('customer_reference')

        if reference:
            partner = request.env['res.partner'].sudo().search(
                [('customer_reference', '=', reference)], limit=1
            )
            if partner:
                invoices = request.env['account.move'].sudo().search([
                    ('partner_id', '=', partner.id),
                    ('move_type', '=', 'out_invoice'),
                    ('payment_state', 'in', ['not_paid', 'partial'])
                ], order="invoice_date desc")

                status_map = {
                    'not_paid': 'Not Paid',
                    'partial': 'Partially Paid',
                    'paid': 'Paid',
                    'in_payment': 'In Payment'
                }

                invoice_list = []
                for inv in invoices:
                    invoice_list.append({
                        'id': inv.id,
                        'name': inv.name or inv.ref,
                        'amount': f"{inv.currency_id.symbol} {inv.amount_total:,.2f}",
                        'state': status_map.get(inv.payment_state, inv.payment_state),
                        'url': '/my/invoices/%s?access_token=%s' % (inv.id, inv._portal_ensure_token())
                    })

                return request.render('kyc_payment_handling.cookpay_template', {
                    'partner_name': partner.name,
                    'invoices': invoice_list
                })

            return request.render('kyc_payment_handling.cookpay_template', {
                'error_message': "Customer with this reference not found."
            })

        return request.render('kyc_payment_handling.cookpay_template', {
            'error_message': "Please provide a valid customer reference or invoice ID."
        })
