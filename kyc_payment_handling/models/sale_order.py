from odoo import api, fields, models

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
        orders = super().create(vals_list)
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