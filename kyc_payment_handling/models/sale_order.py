from odoo import api, fields, models, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _apply_installment_product(self):
        for rec in self:
            print("------------------->>>>><<<<<------------------------")
            installment_lines = rec.order_line.filtered(
                lambda l: l.product_id and l.product_id.product_tmpl_id.installment_product
            )
            rec.order_line -= installment_lines

            if rec.payment_term_id and rec.payment_term_id.installment_amount:
                product_name = f"Installment - {rec.payment_term_id.name} ({rec.payment_term_id.id})"

                product_tmpl = self.env['product.template'].search([
                    ('name', '=', product_name)
                ], limit=1)
                if not product_tmpl:
                    product_tmpl = self.env['product.template'].create({
                        'name': product_name,
                        'list_price': rec.payment_term_id.installment_amount,
                        'type': 'service',
                        'taxes_id': [(5, 0, 0)],
                        'supplier_taxes_id': [(5, 0, 0)],
                        'installment_product': True,
                    })
                    if product_tmpl.taxes_id:
                        product_tmpl.taxes_id = [(5, 0, 0)]
                    if product_tmpl.supplier_taxes_id:
                        product_tmpl.supplier_taxes_id = [(5, 0, 0)]
                else:
                    if product_tmpl.list_price != rec.payment_term_id.installment_amount:
                        product_tmpl.list_price = rec.payment_term_id.installment_amount
                    if product_tmpl.taxes_id:
                        product_tmpl.taxes_id = [(5, 0, 0)]
                    if product_tmpl.supplier_taxes_id:
                        product_tmpl.supplier_taxes_id = [(5, 0, 0)]

                print("------------------->>>>>product_tmpl: ", product_tmpl)

                product = product_tmpl.product_variant_id
                if any(line.product_id.product_tmpl_id.id in rec.payment_term_id.product_ids.ids for line in rec.order_line):
                    rec.order_line += self.env['sale.order.line'].new({
                        'order_id': rec.id,
                        'product_id': product.id,
                        'product_uom_qty': 1,
                        'price_unit': product.list_price,
                        'tax_id': [(5, 0, 0)],
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