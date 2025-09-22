from odoo import http, fields
from odoo.http import request
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


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

        print("---------------->>>>> Order State: ", order.state)

        # compute downpayment
        if order.payment_term_id and order.payment_term_id.line_ids:
            first_line = order.payment_term_id.line_ids[0]
            if first_line.value == "percent":
                values['downpayment_amount'] = (order.amount_total * first_line.value_amount) / 100.0
            elif first_line.value == "fixed":
                values['downpayment_amount'] = first_line.value_amount

        if order and not order.state == 'sale':
            order.action_confirm()

        if not order.invoice_ids:
            invoice = order._create_invoices()
        else:
            invoice = order.invoice_ids.filtered(lambda inv: inv.state == 'draft')[:1]

        if invoice and invoice.state == 'draft':
            invoice.action_post()


        payment = request.env['account.payment'].sudo().search([
            ('payment_transaction_id', '=', order.name)
        ], limit=1)

        print("---------------->>>>> Account Payment Record: ", payment)

        print("---------------->>>>> Invoice State: ", invoice.state)

        if invoice and invoice.state == 'posted' and payment:
            print("---------------->>>>> Linking payment to invoice")

            # Debug print all lines
            print("------ Invoice Lines ------")
            for l in invoice.line_ids:
                print(l.id, l.name, l.account_id.name, l.account_id.account_type, l.account_id.internal_group)

            print("------ Payment Move Lines ------")
            for l in payment.move_id.line_ids:
                print(l.id, l.name, l.account_id.name, l.account_id.account_type, l.account_id.internal_group)

            # Find receivable lines by partner+account
            inv_lines = invoice.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled)
            pay_lines = payment.move_id.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled)

            print("---------------->>>>> Invoice receivable lines:", inv_lines)
            print("---------------->>>>> Payment receivable lines:", pay_lines)

            if inv_lines and pay_lines:
                lines_to_reconcile = inv_lines + pay_lines
                lines_to_reconcile.reconcile()
                print("---------------->>>>> Reconciled Payment %s with Invoice %s" % (payment.name, invoice.name))
            else:
                print("---------------->>>>> No receivable lines found to reconcile.")

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
            'currency_symbol': order.currency_id.symbol,
            'downpayment_amount': values.get('downpayment_amount', order.amount_total),
        })
        print("---------------->>>>> I AM OUT <<<<<----------------")

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


    @http.route('/shop/address/submit', type='http', methods=['POST'], auth='public', website=True, sitemap=False)
    def shop_address_submit(self, partner_id=None, address_type='billing', use_delivery_as_billing=None, callback=None, required_fields=None, payment_term_id=None, **form_data):
        """Inherit default address submit and also attach payment term to the order"""
        # --- Call super to handle standard behavior ---
        response = super().shop_address_submit(
            partner_id=partner_id,
            address_type=address_type,
            use_delivery_as_billing=use_delivery_as_billing,
            callback=callback,
            required_fields=required_fields,
            **form_data
        )

         # 🔹 Get current order
        order = request.website.sale_get_order()
        if not order:
            return response

        # 🔹 Check if payment_term_id came from form
        term_id = payment_term_id or form_data.get('payment_term_id')
        print("--------------->>>>>Before If Payment term :", term_id)
        if term_id:
            term = request.env['account.payment.term'].sudo().browse(int(term_id))
            if term.exists():
                order.sudo().write({'payment_term_id': term.id})
                request.session['sale_order_payment_term'] = term.id
                print("---------------->>>>>Payment term", term)

        return response