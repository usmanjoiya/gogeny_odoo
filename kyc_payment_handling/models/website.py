from odoo import models, api, SUPERUSER_ID
from odoo.http import request

class Website(models.Model):
    _inherit = 'website'

    def sale_get_order(self, force_create=False):
        """Override to create Sale Order in the company of partner_id instead of website"""
        self.ensure_one()

        self = self.with_company(self.company_id)
        SaleOrder = self.env['sale.order'].sudo()
        sale_order_id = request.session.get('sale_order_id')

        if sale_order_id:
            sale_order_sudo = SaleOrder.browse(sale_order_id).exists()
        elif self.env.user and not self.env.user._is_public():
            sale_order_sudo = self.env.user.partner_id.last_website_so_id
            if sale_order_sudo:
                available_pricelists = self.get_pricelist_available()
                so_pricelist_sudo = sale_order_sudo.pricelist_id
                if so_pricelist_sudo and so_pricelist_sudo not in available_pricelists:
                    sale_order_sudo = SaleOrder
                else:
                    fpos = sale_order_sudo.env['account.fiscal.position'].with_company(
                        sale_order_sudo.company_id
                    )._get_fiscal_position(
                        sale_order_sudo.partner_id,
                        delivery=sale_order_sudo.partner_shipping_id
                    )
                    if fpos.id != sale_order_sudo.fiscal_position_id.id:
                        sale_order_sudo = SaleOrder
        else:
            sale_order_sudo = SaleOrder

        if sale_order_sudo and sale_order_sudo.get_portal_last_transaction().state in (
            'pending', 'authorized', 'done'
        ):
            sale_order_sudo = None

        if not (sale_order_sudo or force_create):
            if request.session.get('sale_order_id'):
                request.session.pop('sale_order_id')
                request.session.pop('website_sale_cart_quantity', None)
            return self.env['sale.order']

        partner_sudo = self.env.user.partner_id

        # ✅ Main change: set company as partner's company, not website's
        if not sale_order_sudo:
            so_data = self._prepare_sale_order_values(partner_sudo)

            if partner_sudo.company_id:
                so_data['company_id'] = partner_sudo.company_id.id

            sale_order_sudo = SaleOrder.with_user(SUPERUSER_ID).create(so_data)
            request.session['sale_order_id'] = sale_order_sudo.id
            request.session['website_sale_cart_quantity'] = sale_order_sudo.cart_quantity
            return sale_order_sudo.with_user(self.env.user).sudo()

        if not request.session.get('sale_order_id'):
            request.session['sale_order_id'] = sale_order_sudo.id
            request.session['website_sale_cart_quantity'] = sale_order_sudo.cart_quantity

        if partner_sudo.id not in (sale_order_sudo.partner_id.id, self.partner_id.id):
            sale_order_sudo._update_address(partner_sudo.id, ['partner_id'])

        return sale_order_sudo
