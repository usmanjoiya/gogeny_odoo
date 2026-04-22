from odoo import http
from odoo.http import request

class RecentProducts(http.Controller):

    @http.route('/recent/products', type='json', auth='public', website=True)
    def get_recent_products(self, product_ids=None):
        if not product_ids:
            return []

        try:
            product_ids = [int(pid) for pid in product_ids]
        except (TypeError, ValueError):
            return []

        products = request.env['product.template'].sudo().search([
            ('id', 'in', product_ids),
            ('is_published', '=', True),
        ])
        product_map = {p.id: p for p in products}

        currency = request.website.currency_id
        result = []
        for pid in product_ids:
            p = product_map.get(pid)
            if not p:
                continue
            result.append({
                'id': p.id,
                'name': p.name,
                'price': f"{p.list_price:.2f}",
                'currency': currency.symbol or currency.name,
                'image': f'/web/image/product.template/{p.id}/image_512',
                'url': p.website_url,
            })

        return result