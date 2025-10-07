from odoo import http
from odoo.http import request
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.exceptions import UserError
from markupsafe import Markup
import werkzeug

class CustomAuthSignup(AuthSignupHome):

    @http.route('/web/signup', type='http', auth='public', website=True, sitemap=False)
    def web_auth_signup(self, *args, **kw):
        first_name = kw.get('first_name', '').strip()
        middle_name = kw.get('middle_name', '').strip()
        last_name = kw.get('last_name', '').strip()

        full_name = ' '.join(filter(None, [first_name, middle_name, last_name]))
        if full_name:
            kw['name'] = full_name

        qcontext = self.get_auth_signup_qcontext()
        qcontext.update(kw)

        if not qcontext.get('token') and not qcontext.get('signup_enabled'):
            raise werkzeug.exceptions.NotFound()

        if 'error' not in qcontext and request.httprequest.method == 'POST':
            try:
                self.do_signup(qcontext)
                if request.session.uid is None:
                    public_user = request.env.ref('base.public_user')
                    request.update_env(user=public_user)
                User = request.env['res.users']
                user_sudo = User.sudo().search(
                    User._get_login_domain(qcontext.get('login')),
                    order=User._get_login_order(), limit=1
                )
                template = request.env.ref(
                    'auth_signup.mail_template_user_signup_account_created', raise_if_not_found=False
                )
                if user_sudo and template:
                    template.sudo().send_mail(user_sudo.id, force_send=True)
                return self.web_login(*args, **kw)
            except UserError as e:
                qcontext['error'] = e.args[0]
            except AssertionError as e:
                if request.env["res.users"].sudo().search_count([("login", "=", qcontext.get("login"))], limit=1):
                    qcontext["error"] = "Another user is already registered using this email address."
                else:
                    qcontext['error'] = "Could not create a new account." + Markup('<br/>') + str(e)

        elif 'signup_email' in qcontext:
            user = request.env['res.users'].sudo().search(
                [('email', '=', qcontext.get('signup_email')), ('state', '!=', 'new')], limit=1
            )
            if user:
                return request.redirect('/web/login?%s' % http.url_encode({'login': user.login, 'redirect': '/web'}))

        response = request.render('auth_signup.signup', qcontext)
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
        return response
