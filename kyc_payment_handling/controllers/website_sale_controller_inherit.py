from odoo import http, fields
from odoo.http import request
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


try:
    from odoo.addons.website_sale.controllers.main import WebsiteSale
except ImportError:
    WebsiteSale = object

try:
    from odoo.addons.website_sale.controllers.delivery import Delivery
except ImportError:
    Delivery = object


class DeliveryInherit(Delivery):
    """When the JS refreshes totals after picking a carrier, return the
    state-matched delivery amount in `amount_delivery` so the `#order_delivery`
    td shows our computed value — not the raw carrier rate."""

    def _order_summary_values(self, order, **kwargs):
        values = super()._order_summary_values(order, **kwargs)
        Monetary = request.env['ir.qweb.field.monetary']
        values['amount_delivery'] = Monetary.value_to_html(
            order.state_matched_delivery_amount,
            {'display_currency': order.currency_id},
        )
        return values


class WebsiteSaleInherit(WebsiteSale):
    @http.route(['/shop/<model("product.template"):product>'], type='http', auth="public", website=True, sitemap=True)
    def product(self, product, category='', search='', **kwargs):
        response = super().product(product, category=category, search=search, **kwargs)
        payment_terms = request.env['account.payment.term'].sudo().search([ ('product_ids', 'in', [product.id]) ])
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
        print("---------------->>>>> shop_payment_confirmation")
        sale_order_id = request.session.get('sale_last_order_id')
        if not sale_order_id:
            return request.redirect('/shop')

        order = request.env['sale.order'].sudo().browse(sale_order_id)
        if not order:
            return request.redirect('/shop')
        print("---------------->>>>> ORDER ID", order)

        partner_company = order.partner_id.company_id
        if partner_company and order.company_id != partner_company:
            print("\n\n------------------->>>>> Updating Sale Order company to partner's company: ", partner_company.name)
            order.write({'company_id': partner_company.id})

        # Default values
        values = self._prepare_shop_payment_confirmation_values(order)

        # Downpayment logic
        downpayment_amount = order.amount_total
        payment_term = order.payment_term_id
        print("---------------->>>>> Order Payment Term", payment_term.name if payment_term else "None")

        # compute downpayment
        if order.payment_term_id and order.payment_term_id.line_ids:
            first_line = order.payment_term_id.line_ids[0]
            if first_line.value == "percent":
                values['downpayment_amount'] = (order.amount_total * first_line.value_amount) / 100.0

        # ----->>>>> PROJECT & SALE ORDER CONNECTION
        project_obj = request.env['project.project'].sudo()
        matching_project = project_obj.search([
            ('partner_id', '=', order.partner_id.id),
            ('payment_term_id', '=', order.payment_term_id.id),
            ('sale_order_id', '=', False),
            ('product_id', 'in', order.order_line.mapped('product_id.product_tmpl_id').ids),
        ], limit=1, order='id desc')

        print("\n\n\n-------->>> Matching Project Found:", matching_project)

        tx_sudo = order.get_portal_last_transaction()
        provider_code = tx_sudo.provider_code if tx_sudo else None
        is_cod = provider_code == 'custom'
        print("\n\n💰 Provider Code: ", provider_code, " | COD:", is_cod)

        if is_cod:
            order.write({'note': "Cash on Delivery order."})

        # ----->>>>> 1. Confirm the order
        # (We do NOT modify the is_delivery SO line; _create_split_invoices builds
        # the delivery invoice directly from carrier + state_matched_delivery_amount
        # so amount_total stays clean on the confirmation display.)
        if order.state != 'sale':
            order.action_confirm()
        print("---------------->>>>> Order State: ", order.state)

        # ----->>>>> 3. Create the installment invoice from the Sale Order
        # (Delivery invoice is NOT created here anymore — admin clicks the
        # "Delivery Invoice" button on the sale.order to produce it manually.)
        if not order.invoice_ids:
            invs = order._create_split_invoices()
            installment_invoice = invs['installment_invoice']
        else:
            installment_invoice = order.invoice_ids.filtered(lambda inv: inv.state == 'draft')[:1]

        # ----->>>>> 4. Link SO and Installment invoice to Project
        if matching_project:
            matching_sol = order.order_line.filtered(
                lambda l: l.product_id.product_tmpl_id.id == matching_project.product_id.id
            )[:1]
            if matching_sol:
                matching_project.sale_line_id = matching_sol.id
                print(f"✅ Linked project '{matching_project.name}' to SOL {matching_sol.id} (SO: {order.name})")

            if installment_invoice:
                if matching_project.invoice_date:
                    installment_invoice.invoice_date = matching_project.invoice_date
                matching_project.write({'invoice_ref_id': installment_invoice.id})
                print(f"✅ Linked project '{matching_project.name}' to Invoice {installment_invoice.id}")

        # ----->>>>> 5. Post the installment invoice
        if installment_invoice and installment_invoice.state == 'draft':
            installment_invoice.action_post()

        # ----->>>>> 6. Reconcile payment against the installment invoice ONLY (non-COD)
        if not is_cod and installment_invoice and installment_invoice.state == 'posted':
            payment = request.env['account.payment'].sudo().search([
                ('payment_transaction_id', '=', order.name)
            ], limit=1)

            print("---------------->>>>> Account Payment Record: ", payment)

            if payment:
                inv_lines = installment_invoice.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled)
                pay_lines = payment.move_id.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled)

                if inv_lines and pay_lines:
                    (inv_lines + pay_lines).reconcile()
                    print("---------------->>>>> Reconciled Payment %s with Invoice %s" % (payment.name, installment_invoice.name))
                else:
                    print("---------------->>>>> No receivable lines found to reconcile.")

        # ----->>>>> 6. Remove matching partner project line
        if order.partner_id and order.partner_id.project_line_ids:
            for so_line in order.order_line:
                for project_line in order.partner_id.project_line_ids:
                    if (project_line.product_id.product_variant_id.id == so_line.product_id.id
                            and project_line.payment_term_id.id == order.payment_term_id.id
                            and project_line.state == 'contract_sent'):
                        project_line.unlink()

        values.update({
            'cod_order': is_cod,
            'currency_symbol': order.currency_id.symbol,
            'downpayment_amount': values.get('downpayment_amount', order.amount_total),
        })

        # Render the template NOW (while the is_delivery SO line is still 0) so
        # the confirmation page shows clean totals. Then update the SO delivery
        # line, and ONLY THEN build the delivery invoice from that updated line
        # (so _prepare_invoice_line reads the state-matched price, not 0).
        response = request.render("website_sale.confirmation", values)
        response.flatten()
        order._apply_state_based_delivery_price()

        # Create + post the delivery invoice AFTER the SO line has the correct
        # price. Don't raise if there's no delivery line or it's already
        # invoiced — just skip quietly.
        delivery_invoice = order._create_delivery_invoice(raise_if_empty=False)
        if delivery_invoice and delivery_invoice.state == 'draft':
            delivery_invoice.action_post()

        return response

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

    def _prepare_address_form_values(
            self, order_sudo, partner_sudo, address_type, use_delivery_as_billing, callback='', **kwargs
    ):
        values = super(WebsiteSaleInherit, self)._prepare_address_form_values(
            order_sudo, partner_sudo, address_type, use_delivery_as_billing, callback, **kwargs
        )

        ResCountrySudo = request.env['res.country'].sudo()
        uae_country = ResCountrySudo.search([('code', '=', 'AE')], limit=1)

        values.update({
            'countries': uae_country,
            'country_states': uae_country.state_ids,
        })

        return values
    
    # def _cart_values(self, **kwargs):
    #     values = super()._cart_values(**kwargs)
    #     order = values.get('website_sale_order')
    #     if order and order.payment_term_id and order.payment_term_id.installment_amount:
    #         extra = order.payment_term_id.installment_amount
    #         down_percent = order.payment_term_id.line_ids[0].value_amount if order.payment_term_id.line_ids else 0
    #         final_amount = order.amount_untaxed + extra
    #         downpayment_amount = ((final_amount) * down_percent) / 100 if down_percent else 0

    #         # 🔹 add safe custom fields (not touching order.amount_total)
    #         values.update({
    #             'custom_extra_down_amount': extra,
    #             'custom_final_installment_amount': final_amount,
    #             'custom_downpayment_amount': downpayment_amount,
    #         })
    #     return values