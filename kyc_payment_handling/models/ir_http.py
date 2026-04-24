from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _frontend_pre_dispatch(cls):
        super()._frontend_pre_dispatch()

        user = request.env.user
        if not user or user._is_public():
            return

        user_company_ids = user.company_ids.ids
        if len(user_company_ids) <= 1:
            return

        website = request.env['website'].get_current_website()
        website_cid = website._get_cached('company_id')

        if website_cid and website_cid in user_company_ids:
            allowed = [website_cid] + [c for c in user_company_ids if c != website_cid]
        else:
            allowed = user_company_ids

        request.update_context(allowed_company_ids=allowed)
