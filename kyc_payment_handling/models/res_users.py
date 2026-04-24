from odoo import api, models

MAIN_COMPANY_NAME = 'Gogenie'


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _ensure_main_company(self):
        main_company = self.env['res.company'].sudo().search(
            [('name', '=', MAIN_COMPANY_NAME)], limit=1
        )
        if not main_company:
            return
        for user in self:
            partner_company = user.partner_id.company_id
            if not partner_company or partner_company == main_company:
                continue
            if main_company not in user.company_ids:
                user.sudo().write({'company_ids': [(4, main_company.id)]})

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users._ensure_main_company()
        return users

    def write(self, vals):
        res = super().write(vals)
        if 'partner_id' in vals or 'company_ids' in vals or 'company_id' in vals:
            self._ensure_main_company()
        return res

    @api.model
    def _cron_ensure_main_company_on_all_users(self):
        main_company = self.env['res.company'].sudo().search(
            [('name', '=', MAIN_COMPANY_NAME)], limit=1
        )
        if not main_company:
            return
        users_missing = self.sudo().search([
            ('active', '=', True),
            ('company_ids', 'not in', main_company.ids),
        ])
        for user in users_missing:
            user.sudo().write({'company_ids': [(4, main_company.id)]})
