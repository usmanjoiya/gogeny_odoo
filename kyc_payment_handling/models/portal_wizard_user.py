from odoo import models, fields, api


class PortalWizardUser(models.TransientModel):
    _inherit = 'portal.wizard.user'

    portal_password = fields.Char(
        string="Password",
        compute='_compute_portal_password',
        inverse='_inverse_portal_password',
        readonly=False,
    )

    @api.depends('partner_id.portal_password')
    def _compute_portal_password(self):
        for rec in self:
            rec.portal_password = rec.partner_id.portal_password or ''

    def _inverse_portal_password(self):
        for rec in self:
            if rec.portal_password:
                rec.partner_id.portal_password = rec.portal_password
                if rec.user_id:
                    rec.user_id._change_password(rec.portal_password)

    def action_change_password(self):
        self.ensure_one()
        if not self.user_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': 'Change Password',
            'res_model': 'change.password.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': 'res.users',
                'active_ids': [self.user_id.id],
            },
        }


class ChangePasswordUser(models.TransientModel):
    _inherit = 'change.password.user'

    def change_password_button(self):
        passwords = {line.user_id.id: line.new_passwd for line in self if line.new_passwd}
        res = super().change_password_button()
        for user_id, passwd in passwords.items():
            user = self.env['res.users'].browse(user_id)
            if user.partner_id:
                user.partner_id.portal_password = passwd
        return res
