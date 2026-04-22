from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)
_DELIVERY_RATE_LOG = logging.getLogger("kyc_payment_handling.delivery_rate")

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    state_matched_delivery_amount = fields.Monetary(
        compute='_compute_state_matched_delivery_amount',
        currency_field='currency_id',
        string="State-Matched Delivery (display only)",
        help="Display-only: sum of delivery_rate_ids.amount from each non-delivery "
             "product whose rate matches the partner_shipping_id country + state. "
             "Does not affect amount_total, amount_delivery, any line price_unit, "
             "the payment transaction amount, or invoicing.",
    )

    @api.depends(
        'order_line.product_id.product_tmpl_id.delivery_rate_ids',
        'order_line.product_id.product_tmpl_id.delivery_rate_ids.amount',
        'order_line.product_id.product_tmpl_id.delivery_rate_ids.country_id',
        'order_line.product_id.product_tmpl_id.delivery_rate_ids.state_id',
        'partner_invoice_id.country_id',
        'partner_invoice_id.state_id',
    )
    def _compute_state_matched_delivery_amount(self):
        for order in self:
            # Source = partner_invoice_id: the billing address the customer
            # just submitted on /shop/address. partner_shipping_id can be a
            # stale anonymous child partner reused by Odoo's express-checkout
            # flow, which gave the wrong state earlier.
            country = order.partner_invoice_id.country_id
            state = order.partner_invoice_id.state_id
            _DELIVERY_RATE_LOG.info(
                "[SO %s] partner_invoice=%s country=%s(id=%s) state=%s(id=%s)",
                order.name or order.id,
                order.partner_invoice_id.display_name,
                country.name, country.id,
                state.name, state.id,
            )
            # No shipping address yet -> no meaningful match, show 0
            if not country or not state:
                _DELIVERY_RATE_LOG.info("[SO %s] no country/state -> total=0", order.name or order.id)
                order.state_matched_delivery_amount = 0.0
                continue
            total = 0.0
            seen_tmpl_ids = set()
            for line in order.order_line:
                if line.is_delivery:
                    continue
                tmpl = line.product_id.product_tmpl_id
                if not tmpl or tmpl.id in seen_tmpl_ids:
                    continue
                seen_tmpl_ids.add(tmpl.id)
                _DELIVERY_RATE_LOG.info(
                    "  product=%s rates=%s",
                    tmpl.display_name,
                    [(r.name, r.country_id.name, r.state_id.name, r.amount) for r in tmpl.delivery_rate_ids],
                )
                matched = False
                for rate in tmpl.delivery_rate_ids:
                    match = rate.country_id == country and rate.state_id == state
                    _DELIVERY_RATE_LOG.info(
                        "    rate=%s rate.country=%s(id=%s) rate.state=%s(id=%s) match=%s amount=%s",
                        rate.name,
                        rate.country_id.name, rate.country_id.id,
                        rate.state_id.name, rate.state_id.id,
                        match, rate.amount,
                    )
                    if match:
                        total += rate.amount
                        matched = True
                        break
                if not matched:
                    _DELIVERY_RATE_LOG.info("    -> product contributes 0 (no matching rate)")
            _DELIVERY_RATE_LOG.info("[SO %s] FINAL state_matched_delivery_amount=%s", order.name or order.id, total)
            order.state_matched_delivery_amount = total

    def _apply_state_based_delivery_price(self):
        """Write the state-matched delivery amount onto the SO's is_delivery
        line(s) so the backend sale.order view reflects the real price the
        customer was billed. Called AFTER the confirmation template has been
        rendered, so the website display stays clean."""
        for order in self:
            delivery_lines = order.order_line.filtered('is_delivery')
            if not delivery_lines:
                continue
            delivery_lines.write({'price_unit': order.state_matched_delivery_amount})

    def _create_split_invoices(self):
        """Create the installment invoice from every non-delivery SO line
        (payment term = order.payment_term_id). The delivery invoice is NOT
        auto-created anymore — it's triggered manually from the sale order
        form via `action_create_delivery_invoice`.
        """
        self.ensure_one()

        invoiceable = self._get_invoiceable_lines(final=True)
        other_lines = invoiceable.filtered(lambda l: not l.is_delivery)

        base_vals = self._prepare_invoice()
        AccountMove = self.env['account.move'].sudo()

        installment_inv = self.env['account.move']
        if other_lines:
            vals = dict(base_vals)
            vals['invoice_payment_term_id'] = self.payment_term_id.id if self.payment_term_id else False
            vals['invoice_line_ids'] = [
                (0, 0, line._prepare_invoice_line()) for line in other_lines
            ]
            installment_inv = AccountMove.create(vals)

        return {
            'delivery_invoice': self.env['account.move'],
            'installment_invoice': installment_inv,
        }

    def _create_delivery_invoice(self, raise_if_empty=True):
        """Create and return an `account.move` for the is_delivery SO line(s),
        payment term = empty. Returns an empty recordset (or raises, depending
        on `raise_if_empty`) if the order has no delivery line or it's already
        fully invoiced. Intended to be called from both the admin button and
        the website confirmation controller."""
        self.ensure_one()
        delivery_lines = self.order_line.filtered('is_delivery')
        if not delivery_lines:
            if raise_if_empty:
                raise UserError(_("This order has no delivery line."))
            return self.env['account.move']

        invoiceable = delivery_lines.filtered(lambda l: l.qty_to_invoice > 0)
        if not invoiceable:
            if raise_if_empty:
                raise UserError(_("The delivery line is already fully invoiced."))
            return self.env['account.move']

        base_vals = self._prepare_invoice()
        base_vals['invoice_payment_term_id'] = False  # empty payment term on delivery invoice
        base_vals['invoice_line_ids'] = [
            (0, 0, line._prepare_invoice_line()) for line in invoiceable
        ]
        return self.env['account.move'].sudo().create(base_vals)

    def action_create_delivery_invoice(self):
        """Button action: create the delivery invoice (raising if nothing to
        invoice) and open it in a form view."""
        self.ensure_one()
        invoice = self._create_delivery_invoice(raise_if_empty=True)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Delivery Invoice'),
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _apply_installment_product(self):
        for rec in self:
            installment_lines = rec.order_line.filtered(
                lambda l: l.product_id and l.product_id.product_tmpl_id.installment_product
            )
            rec.order_line -= installment_lines

            if rec.payment_term_id and rec.payment_term_id.installment_amount:
                # Find 5% VAT tax for the company
                vat_tax = self.env['account.tax'].search([
                    ('amount', '=', 5),
                    ('type_tax_use', '=', 'sale'),
                    ('amount_type', '=', 'percent'),
                    ('company_id', '=', rec.company_id.id),
                ], limit=1)
                tax_cmd = [(6, 0, vat_tax.ids)] if vat_tax else [(5, 0, 0)]

                product_name = f"Installment - {rec.payment_term_id.name} ({rec.payment_term_id.id})"

                product_tmpl = self.env['product.template'].search([
                    ('name', '=', product_name)
                ], limit=1)
                if not product_tmpl:
                    product_tmpl = self.env['product.template'].create({
                        'name': product_name,
                        'list_price': rec.payment_term_id.installment_amount,
                        'type': 'consu',
                        'taxes_id': tax_cmd,
                        'supplier_taxes_id': [(5, 0, 0)],
                        'installment_product': True,
                    })
                else:
                    if product_tmpl.list_price != rec.payment_term_id.installment_amount:
                        product_tmpl.list_price = rec.payment_term_id.installment_amount
                    if vat_tax:
                        product_tmpl.taxes_id = tax_cmd

                product = product_tmpl.product_variant_id
                if any(line.product_id.product_tmpl_id.id in rec.payment_term_id.product_ids.ids for line in rec.order_line):
                    rec.order_line += self.env['sale.order.line'].new({
                        'order_id': rec.id,
                        'product_id': product.id,
                        'product_uom_qty': 1,
                        'price_unit': product.list_price,
                        'tax_id': tax_cmd,
                    })

    @api.model_create_multi
    def create(self, vals_list):
        website_ids_to_set = []
        for vals in vals_list:
            website_id = vals.get('website_id')
            company_id = vals.get('company_id') or self.env.company.id
            website_ids_to_set.append(None)

            if website_id:
                website = self.env['website'].browse(website_id)
                if website.exists() and website.company_id.id != company_id:
                    _logger.warning(
                        "Bypassing website/company check for incoming SO: Website(%s) vs Company(%s)",
                        website.company_id.name,
                        self.env['res.company'].browse(company_id).name
                    )
                    website_ids_to_set[-1] = website_id
                    vals.pop('website_id', None)

                    partner_id = vals.get('partner_id')
                    if partner_id:
                        partner_company = self.env['res.partner'].browse(partner_id).company_id
                        if partner_company:
                            vals['company_id'] = partner_company.id

            # ✅ Fix pricelist mismatch before creation
            pricelist_id = vals.get('pricelist_id')
            if pricelist_id:
                pricelist = self.env['product.pricelist'].browse(pricelist_id)
                if pricelist.exists() and pricelist.company_id and pricelist.company_id.id != company_id:
                    _logger.warning(
                        "Switching pricelist from '%s' (%s) to match company '%s'",
                        pricelist.name,
                        pricelist.company_id.name,
                        self.env['res.company'].browse(company_id).name
                    )
                    correct_pricelist = self.env['product.pricelist'].search([
                        ('currency_id', '=', pricelist.currency_id.id),
                        ('company_id', '=', company_id)
                    ], limit=1)
                    if correct_pricelist:
                        vals['pricelist_id'] = correct_pricelist.id

        orders = super().create(vals_list)

        # ✅ Reattach website and context safely
        for so, ws_id in zip(orders, website_ids_to_set):
            if ws_id:
                try:
                    so.sudo().write({'website_id': ws_id})
                except Exception as e:
                    _logger.exception("Failed to reattach website_id for SO %s: %s", so.name, e)

            if hasattr(so, '_create_website_context'):
                try:
                    so._create_website_context()
                except Exception as e:
                    _logger.exception("Website context creation failed for SO %s: %s", so.name, e)

        # ✅ Apply installment logic after order is fully valid
        orders._apply_installment_product()
        return orders

    def write(self, vals):
        res = super().write(vals)
        if 'payment_term_id' in vals:
            self._apply_installment_product()
        return res

class ProductTemplate(models.Model):
    _inherit = "product.template"

    installment_product = fields.Boolean(default=False)
    product_blog_link = fields.Char(string="Blog Link")
    delivery_rate_ids = fields.Many2many(
        "kyc.delivery.rate",
        "product_template_delivery_rate_rel",
        "product_tmpl_id",
        "delivery_rate_id",
        string="Delivery Rates",
    )