from odoo import http, fields
from odoo.http import request
from odoo.exceptions import ValidationError


try:
    from odoo.addons.website_sale.controllers.main import WebsiteSale
except ImportError:
    WebsiteSale = object


class WebsiteSaleInherit(WebsiteSale):
    @http.route(['/shop/<model("product.template"):product>'], type='http', auth="public", website=True, sitemap=True)
    def product(self, product, category='', search='', **kwargs):
        response = super().product(product, category=category, search=search, **kwargs)
        payment_terms = request.env['account.payment.term'].sudo().search([])
        # Default values
        partner_line_id = None
        partner_payment_term = None
        partner_project_state = None
        if not request.env.user._is_public():
            partner = request.env.user.partner_id
            partner_line = request.env['res.partner.project.line'].sudo().search([
                ('partner_id', '=', partner.id),
                ('product_id', '=', product.id),
            ], limit=1)
            if partner_line:
                partner_line_id = partner_line.id
                partner_payment_term = partner_line.payment_term_id.id
                partner_project_state = partner_line.state
            print("-------------------->>>>> Partner:", partner)
            print("-------------------->>>>> Partner Line:", partner_line)
            print("-------------------->>>>> Payment Term:", partner_payment_term)
            print("-------------------->>>>> State:", partner_project_state)
        ctx_update = {
            'payment_terms': payment_terms,
            'product_price': product.list_price,
            'currency_symbol': product.currency_id.symbol,
            'currency_position': product.currency_id.position,
            'partner_payment_term': partner_payment_term,
            'partner_project_state': partner_project_state,
            'partner_line_id': partner_line_id,
        }
        if hasattr(response, "qcontext"):
            response.qcontext.update(ctx_update)
        elif isinstance(response, dict):
            response.update(ctx_update)
        return response

    @http.route(['/shop/confirmation'], type='http', auth="public", website=True, sitemap=False)
    def shop_payment_confirmation(self, **post):
        sale_order_id = request.session.get('sale_last_order_id')
        if not sale_order_id:
            return request.redirect('/shop')
        order = request.env['sale.order'].sudo().browse(sale_order_id)
        if not order:
            return request.redirect('/shop')
        print("---------------->>>>> ORDER ID", order)
        # Default values
        values = self._prepare_shop_payment_confirmation_values(order)
        # Downpayment logic
        downpayment_amount = order.amount_total
        payment_term = order.payment_term_id
        print("---------------->>>>> Order Payment Term", payment_term.name if payment_term else "None")
        check_adv_payment = request.env['sale.advance.payment.inv'].sudo().search([('id', '=', order.id)])
        print("---------------->>>>> Order State: ", order.state)
        print("---------------->>>>> Got check_adv_payment: ", check_adv_payment)
        if payment_term and payment_term.line_ids:
            first_line = payment_term.line_ids[:1]
            percentage_value = first_line.value_amount
            downpayment_amount = (order.amount_total / 100.0) * percentage_value
            if not order.invoice_ids:
                invoice = order._create_invoices()
            else:
                invoice = order.invoice_ids.filtered(lambda inv: inv.state == 'draft')[:1]
            if invoice and invoice.state == 'draft':
                invoice.action_post()
                if invoice.amount_residual > 0:
                    payment_register = request.env['account.payment.register'].sudo().with_context(
                        active_model='account.move',
                        active_ids=invoice.ids
                    ).create({
                        'payment_date': fields.Date.context_today(request.env.user),
                    })
                    payment_register.action_create_payments()
        # --- Remove matching partner product line if approved ---
        if order.partner_id and order.partner_id.project_line_ids:
            print("-------------------->>>>> Order Partner:", order.partner_id.name)
            for so_line in order.order_line:
                print("------------->>>>> OL")
                for project in order.partner_id.project_line_ids:
                    if project.product_id.product_variant_id.id == so_line.product_id.id and project.payment_term_id.id == order.payment_term_id.id and project.state == 'approved':
                        print(f"---------------------------->>>>> Removing project line: {project}")
                        project.unlink()
        values.update({
            'downpayment_amount': downpayment_amount,
            'currency_symbol': order.currency_id.symbol,
        })
        return request.render("website_sale.confirmation", values)

    @http.route('/shop/payment/validate', type='http', auth="public", website=True, sitemap=False)
    def shop_payment_validate(self, sale_order_id=None, **post):
        print("------------------->>>>> I AM Called <<<<<-------------------")
        if sale_order_id is None:
            order = request.website.sale_get_order()
            if not order and 'sale_last_order_id' in request.session:
                last_order_id = request.session['sale_last_order_id']
                order = request.env['sale.order'].sudo().browse(last_order_id).exists()
        else:
            order = request.env['sale.order'].sudo().browse(sale_order_id)
            assert order.id == request.session.get('sale_last_order_id')
        errors = self._get_shop_payment_errors(order)
        if errors:
            first_error = errors[0]
            error_msg = f"{first_error[0]}\n{first_error[1]}"
            raise ValidationError(error_msg)
        tx_sudo = order.get_portal_last_transaction() if order else order.env['payment.transaction']
        if not order or (order.amount_total and not tx_sudo):
            return request.redirect('/shop')
        if order and not order.amount_total and not tx_sudo:
            if order.state != 'sale':
                order._validate_order()
            request.website.sale_reset()
            return request.redirect(order.get_portal_url())
        # :small_blue_diamond: Downpayment adjustment here
        if tx_sudo and tx_sudo.state in ('pending', 'done') and order.payment_term_id:
            first_line = order.payment_term_id.line_ids[:1]
            if first_line:
                if first_line.value == 'percent':
                    downpayment_amount = (order.amount_total / 100.0) * first_line.value_amount
                elif first_line.value == 'fixed':
                    downpayment_amount = first_line.value_amount
                else:
                    downpayment_amount = order.amount_total
                # Update transaction if mismatch
                if tx_sudo.amount != downpayment_amount:
                    tx_sudo.write({'amount': downpayment_amount})
                    print(f":white_check_mark: Updated TX {tx_sudo.id} to downpayment: {downpayment_amount}")
        # clean context and session
        request.website.sale_reset()
        if tx_sudo and tx_sudo.state == 'draft':
            return request.redirect('/shop')
        return request.redirect('/shop/confirmation')


