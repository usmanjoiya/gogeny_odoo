from odoo import http
from odoo.http import request

try:
    from odoo.addons.website_sale.controllers.main import WebsiteSale  # type: ignore
except ImportError:
    WebsiteSale = object


class WebsiteSaleInherit(WebsiteSale):
    @http.route(['/shop/<model("product.template"):product>'], type='http', auth="public", website=True, sitemap=True)
    def product(self, product, category='', search='', **kwargs):
        response = super().product(product, category=category, search=search, **kwargs)
        payment_terms = request.env['account.payment.term'].sudo().search([])
        print("\n\n-------------------->>>>>Payment Terms", payment_terms)
        # If response is a rendered object (most cases)
        if hasattr(response, "qcontext"):
            response.qcontext.update({
                'payment_terms': payment_terms,
                'product_price': product.list_price,
                'currency_symbol': product.currency_id.symbol,
                'currency_position': product.currency_id.position,  # optional: 'before' or 'after'
            })
        # If it's a dict (rare case, depending on context)
        elif isinstance(response, dict):
            response.update({
                'payment_terms': payment_terms,
                'product_price': product.list_price,
                'currency_symbol': product.currency_id.symbol,
                'currency_position': product.currency_id.position,
            })

        return response