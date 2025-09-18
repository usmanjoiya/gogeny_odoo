from odoo import http
from odoo.http import request
import base64


class ProjectApplication(http.Controller):
    # ===== Start Now Button - Installments Cart =====
    @http.route(['/apply/<int:term_id>/<int:product_id>'], type='http', auth="public", website=True)
    def apply_project(self, term_id, product_id, **kw):
        term = request.env['account.payment.term'].sudo().browse(term_id)
        product = request.env['product.template'].sudo().browse(product_id)
        countries = request.env['res.country'].sudo().search([])
        states = request.env['res.country.state'].sudo().search([])
        values = {
            'payment_term': term,
            'product': product,
            'countries': countries,
            'states': states,
        }
        return request.render("kyc_payment_handling.project_application_template", values)

    # ===== KYC Details Submit - Button =====
    @http.route(['/apply/submit'], type='http', auth="public", website=True, csrf=False)
    def apply_submit(self, **post):
        files = request.httprequest.files
        id_photo_front_file = files.get('id_photo_front')
        id_photo_back_file = files.get('id_photo_back')
        bank_statement_file = files.get('3m_bank_statement')
        salary_certificate_file = files.get('salary_certificate')
        # ---------------- Partner Handling ----------------
        if request.env.user and request.env.user.partner_id:
            partner = request.env.user.partner_id
        else:
            first_name = post.get('first_name') or ''
            middle_name = post.get('middle_name') or ''
            last_name = post.get('last_name') or ''
            full_name = " ".join(part for part in [first_name, middle_name, last_name] if part)
            partner = request.env['res.partner'].sudo().search([
                ('name', '=', full_name),
                ('phone', '=', post.get('phone_number'))
            ], limit=1)
            if not partner:
                partner = request.env['res.partner'].sudo().create({
                    'name': full_name,
                    'phone': post.get('phone_number'),
                    'email': post.get('email'),
                    'street': post.get('street'),
                    'street2': post.get('street2'),
                    'city': post.get('city'),
                    'zip': post.get('zip'),
                    'customer_reference': post.get('uae_id_number'),
                })
                if post.get('country_id'):
                    partner['country_id'] = int(post.get('country_id'))
                if post.get('state_id'):
                    partner['state_id'] = int(post.get('state_id'))
        # ---------------- Product & Term ----------------
        product = request.env['product.template'].sudo().browse(int(post.get('product_id')))
        term = request.env['account.payment.term'].sudo().browse(int(post.get('term_id')))
        # ---------------- Project Creation ----------------
        project_vals = {
            'name': f"{product.name}",
            'partner_id': partner.id,
            'phone': post.get('phone_number'),
            'emergency_phone': post.get('emergency_phone_number'),
            'email': post.get('email'),
            'place_of_work': post.get('place_of_work'),
            'street': post.get('street'),
            'street2': post.get('street2'),
            'city': post.get('city'),
            'zip_code': post.get('zip'),
            'uae_id_number': post.get('uae_id_number'),
            'payment_term_id': term.id,
        }
        if post.get('country_id'):
            project_vals['country_id'] = int(post.get('country_id'))
        if post.get('state_id'):
            project_vals['state_id'] = int(post.get('state_id'))
        if id_photo_front_file:
            project_vals['id_photo_front'] = base64.b64encode(id_photo_front_file.read())
            project_vals['id_photo_front_filename'] = id_photo_front_file.filename
        if id_photo_back_file:
            project_vals['id_photo_back'] = base64.b64encode(id_photo_back_file.read())
            project_vals['id_photo_back_filename'] = id_photo_back_file.filename
        if bank_statement_file:
            project_vals['bank_statement'] = base64.b64encode(bank_statement_file.read())
            project_vals['bank_statement_filename'] = bank_statement_file.filename
        if salary_certificate_file:
            project_vals['salary_certificate'] = base64.b64encode(salary_certificate_file.read())
            project_vals['salary_certificate_filename'] = salary_certificate_file.filename
        project = request.env['project.project'].sudo().create(project_vals)
        for line in partner.project_line_ids:
            if line.product_id.id == product.id and line.payment_term_id.id == term.id and line.state == 'cancel':
                print(f"---------------------------->>>>> Removing project line: {line}")
                line.unlink()
        # ---------------- Link Project to Partner (new One2many line) ----------------
        request.env['res.partner.project.line'].sudo().create({
            'partner_id': partner.id,
            'project_id': project.id,
            'product_id': product.id,
            'payment_term_id': term.id,
        })

        # ---------------- Store Session Terms ----------------
        request.session.setdefault('apply_payment_terms', {})
        request.session['apply_payment_terms'][product.id] = term.id
        request.session.modified = True
        print("----------------------->>>>> Payment Terms Are: ", request.session['apply_payment_terms'])
        # ---------------- Redirect ----------------
        product_slug = product.name.lower().replace(' ', '-')
        return request.redirect('/shop/%s-%s?project_id=%s' % (
            product_slug, product.id, project.id
        ))

    # ===== Checkout Page - Adding installment info under Product cart =====
    @http.route(['/checkout/<int:product_id>/<int:term_id>/<int:project_line_id>'], type='http', auth="user", website=True)
    def checkout_with_term(self, product_id, term_id, project_line_id, **kw):
        # Get current sale order (cart)
        order = request.website.sale_get_order(force_create=True)
        # Find product (use product template id to get variant/product record)
        product = request.env['product.product'].sudo().search(
            [('product_tmpl_id', '=', product_id)], limit=1
        )
        if not product:
            return request.redirect('/shop')
        # Check if product already in cart
        existing_line = order.order_line.filtered(lambda l: l.product_id.id == product.id)
        if not existing_line:
            order._cart_update(product_id=product.id, add_qty=1)
        if term_id:
            order.sudo().write({'payment_term_id': term_id})
            print(">>>> Payment Term set on order:", order.payment_term_id.name)
        # Store payment term + project_line in session (not on SOL directly)
        request.session.setdefault('apply_payment_terms', {})
        request.session['apply_payment_terms'][str(product_id)] = {
            'term_id': term_id,
            'project_line_id': project_line_id,
        }
        request.session.modified = True
        # :white_check_mark: Redirect user to cart page
        return request.redirect('/shop/cart')
